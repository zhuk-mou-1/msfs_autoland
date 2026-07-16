"""
Автоматический контроллер тяги (Autothrottle) для фазы FINAL
с учётом веса, конфигурации, интеграцией с vJoy и детектором отказов двигателей
"""

import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from modules.base_controller import Controller
from modules.engine_failure_detector import EngineFailureDetector

logger = logging.getLogger(__name__)


@dataclass
class AutothrottleConfig:
    """Конфигурация автоматического контроллера тяги"""
    # PID коэффициенты
    kp: float = 0.05  # Пропорциональный коэффициент
    ki: float = 0.01  # Интегральный коэффициент
    kd: float = 0.02  # Дифференциальный коэффициент

    # Ограничения
    max_throttle: float = 1.0  # Максимальная тяга
    min_throttle: float = 0.0  # Минимальная тяга
    max_throttle_rate: float = 0.1  # Максимальная скорость изменения тяги (за цикл)

    # Целевые параметры
    target_speed_tolerance: float = 5.0  # Допустимое отклонение скорости (узлы)

    # Коррекция на конфигурацию
    flaps_drag_factor: float = 0.15  # Дополнительная тяга на каждую позицию закрылков
    gear_drag_factor: float = 0.10  # Дополнительная тяга при выпущенном шасси

    # Коррекция на вес
    weight_reference: float = 5000.0  # Референсный вес (фунты)
    weight_factor: float = 0.00002  # Коэффициент влияния веса

    # PID timing
    max_pid_dt_seconds: float = 2.0  # Максимальный допустимый dt для PID (секунды)


class AutothrottleController(Controller):
    """PID контроллер автоматической тяги с поддержкой отказов двигателей"""

    def __init__(self, config: Optional[AutothrottleConfig] = None,
                 engine_failure_detector: Optional[EngineFailureDetector] = None,
                 *, clock: Optional[Callable[[], float]] = None):
        self.config = config or AutothrottleConfig()
        self.engine_failure_detector = engine_failure_detector
        self._clock = clock or time.monotonic

        # Validate config
        if not math.isfinite(self.config.max_pid_dt_seconds) or self.config.max_pid_dt_seconds <= 0:
            raise ValueError(
                f"max_pid_dt_seconds must be a finite positive number, "
                f"got {self.config.max_pid_dt_seconds!r}"
            )

        # Состояние PID контроллера
        self.integral = 0.0
        self.previous_error = 0.0
        self.previous_time = None
        self.current_throttle = 0.5

        # Режим работы
        self.active = False
        self.asymmetric_mode = False  # Режим асимметричной тяги при отказе двигателя

        # Статистика
        self.total_corrections = 0

    def reset(self):
        """Сброс состояния контроллера"""
        self.integral = 0.0
        self.previous_error = 0.0
        self.previous_time = None
        self.active = False
        logger.info("Autothrottle reset")

    def activate(self, initial_throttle: float = 0.5):
        """Активация автоматического контроллера тяги"""
        self.active = True
        self.current_throttle = initial_throttle
        self.previous_time = self._clock()
        logger.info("Autothrottle activated at %.1f%%", initial_throttle*100)

    def deactivate(self):
        """Деактивация контроллера"""
        self.active = False
        logger.info("Autothrottle deactivated")

    def calculate_base_throttle(self,
                                aircraft_weight: float,
                                flaps_position: int,
                                gear_down: bool) -> float:
        """
        Расчёт базовой тяги с учётом веса и конфигурации

        Args:
            aircraft_weight: Вес самолёта (фунты)
            flaps_position: Позиция закрылков (0-4)
            gear_down: Шасси выпущено

        Returns:
            Базовая тяга (0.0 - 1.0)
        """
        # Базовая тяга для референсного веса
        base_throttle = 0.5

        # Коррекция на вес
        weight_correction = (aircraft_weight - self.config.weight_reference) * self.config.weight_factor
        base_throttle += weight_correction

        # Коррекция на закрылки (больше закрылки = больше сопротивление = больше тяга)
        flaps_correction = flaps_position * self.config.flaps_drag_factor
        base_throttle += flaps_correction

        # Коррекция на шасси
        if gear_down:
            base_throttle += self.config.gear_drag_factor

        # Ограничение
        base_throttle = max(self.config.min_throttle, min(self.config.max_throttle, base_throttle))

        logger.debug(f"Base throttle: {base_throttle:.3f} "
                    f"(weight: {aircraft_weight:.0f}lbs, flaps: {flaps_position}, gear: {gear_down})")

        return base_throttle

    def calculate_wind_correction(self, headwind: float, crosswind: float = 0.0) -> float:
        """
        Расчёт коррекции тяги на ветер с учётом встречного и бокового компонентов

        Args:
            headwind: Встречный ветер (узлы, + встречный, - попутный)
            crosswind: Боковой ветер (узлы, абсолютное значение)

        Returns:
            Коррекция тяги (-1.0 до +1.0)
        """
        # Встречный ветер требует больше тяги
        # Попутный ветер требует меньше тяги
        # ~1% тяги на каждые 5 узлов ветра
        headwind_correction = headwind * 0.002

        # Боковой ветер создаёт дополнительное сопротивление
        # из-за необходимости удержания курса (скольжение, крен)
        # ~0.5% тяги на каждые 10 узлов бокового ветра
        crosswind_correction = abs(crosswind) * 0.0005

        # Общая коррекция
        total_correction = headwind_correction + crosswind_correction

        # Ограничение коррекции
        total_correction = max(-0.2, min(0.2, total_correction))

        return total_correction

    def calculate_crosswind_drag_factor(self, crosswind: float, bank_angle: float = 0.0) -> float:
        """
        Расчёт дополнительного сопротивления от бокового ветра

        Args:
            crosswind: Боковой ветер (узлы)
            bank_angle: Угол крена для компенсации сноса (градусы)

        Returns:
            Коэффициент дополнительного сопротивления (0.0-0.1)
        """
        # Боковой ветер создаёт:
        # 1. Сопротивление от скольжения (sideslip)
        # 2. Индуктивное сопротивление от крена

        # Сопротивление от скольжения
        # Предполагаем ~2° скольжения на каждые 10 узлов бокового ветра
        sideslip_angle = abs(crosswind) * 0.2  # градусы
        sideslip_drag = sideslip_angle * 0.001  # ~0.1% на градус

        # Индуктивное сопротивление от крена
        # Увеличивается пропорционально квадрату угла крена
        bank_drag = (abs(bank_angle) / 100.0) ** 2 * 0.05

        # Общее сопротивление
        total_drag = sideslip_drag + bank_drag

        # Ограничение
        total_drag = min(0.1, total_drag)

        return total_drag

    def calculate_pid_correction(self,
                                 current_speed: float,
                                 target_speed: float,
                                 dt: float) -> float:
        """
        Расчёт PID коррекции для достижения целевой скорости

        Args:
            current_speed: Текущая скорость (узлы)
            target_speed: Целевая скорость (узлы)
            dt: Временной шаг (секунды)

        Returns:
            PID коррекция тяги
        """
        # Ошибка (положительная = слишком медленно, нужно больше тяги)
        error = target_speed - current_speed

        # Пропорциональная составляющая
        p_term = self.config.kp * error

        # Интегральная составляющая (накопленная ошибка)
        self.integral += error * dt
        # Ограничение интеграла (anti-windup)
        self.integral = max(-50, min(50, self.integral))
        i_term = self.config.ki * self.integral

        # Дифференциальная составляющая (скорость изменения ошибки)
        if dt > 0:
            derivative = (error - self.previous_error) / dt
        else:
            derivative = 0
        d_term = self.config.kd * derivative

        # Общая коррекция
        pid_correction = p_term + i_term + d_term

        # Сохранение для следующей итерации
        self.previous_error = error

        logger.debug(f"PID: error={error:.1f}kt, P={p_term:.3f}, I={i_term:.3f}, D={d_term:.3f}, "
                    f"total={pid_correction:.3f}")

        return pid_correction

    def calculate_throttle(self,
                          telemetry: Dict,
                          target_speed: float,
                          wind_data: Dict,
                          aircraft_weight: float = 5000.0) -> Dict[str, float]:
        """
        Основной метод расчёта тяги

        Args:
            telemetry: Телеметрия самолёта
            target_speed: Целевая скорость (узлы)
            wind_data: Данные о ветре (headwind, crosswind)
            aircraft_weight: Вес самолёта (фунты)

        Returns:
            Dict с командами управления тягой
        """
        if not self.active:
            return {
                'active': False,
                'throttle': self.current_throttle
            }

        # Текущие параметры
        speed_data = telemetry.get('speed', {})
        attitude_data = telemetry.get('attitude', {})
        current_speed = speed_data.get('airspeed_indicated')
        current_bank = attitude_data.get('bank', 0)

        # Защита: если airspeed отсутствует, удерживаем текущую тягу
        # (не используем 0 как fallback - это вызвало бы max throttle через PID)
        if current_speed is None or current_speed <= 0:
            logger.warning("Autothrottle: missing/invalid airspeed - holding current throttle")
            return {
                'active': True,
                'throttle': self.current_throttle,
                'is_stable': False,
                'reason': 'missing_airspeed'
            }

        # Конфигурация самолёта - читаем из SimConnect
        # FLAPS_HANDLE_PERCENT возвращает 0.0-1.0, конвертируем в позицию 0-4
        # GEAR_POSITION возвращает 0.0-1.0 (1.0 = полностью выпущено)
        config_data = telemetry.get('configuration', {})
        flaps_handle_percent = config_data.get('flaps_position', 1.0)  # 0.0-1.0
        flaps_position = int(round(flaps_handle_percent * 4))  # 0-4
        gear_down = config_data.get('gear_position', 1.0) > 0.5

        # Временной шаг
        current_time = self._clock()
        if self.previous_time is not None:
            dt = current_time - self.previous_time
        else:
            dt = 0.5

        # Validate dt: skip I/D update on anomalous values
        if not math.isfinite(dt) or dt <= 0 or dt > self.config.max_pid_dt_seconds:
            logger.warning(
                "Autothrottle: anomalous dt=%.3fs (max=%.1fs) — "
                "freezing I/D for this frame",
                dt, self.config.max_pid_dt_seconds,
            )
            dt = 0.0  # Safe value: integral unchanged, derivative = 0

        self.previous_time = current_time

        # 1. Базовая тяга (вес + конфигурация)
        base_throttle = self.calculate_base_throttle(aircraft_weight, flaps_position, gear_down)

        # 2. Коррекция на ветер (встречный + боковой)
        headwind = wind_data.get('headwind', 0)
        crosswind = wind_data.get('crosswind', 0)
        wind_correction = self.calculate_wind_correction(headwind, crosswind)

        # 3. Дополнительное сопротивление от бокового ветра
        crosswind_drag = self.calculate_crosswind_drag_factor(crosswind, current_bank)

        # 4. PID коррекция для точного контроля скорости
        pid_correction = self.calculate_pid_correction(current_speed, target_speed, dt)

        # 5. Итоговая тяга
        new_throttle = base_throttle + wind_correction + crosswind_drag + pid_correction

        # 6. Проверка отказов двигателей и переключение на асимметричный режим
        engine_throttles = None
        has_engine_failure = False

        if self.engine_failure_detector:
            # Обновление данных детектора
            self.engine_failure_detector.update_engine_data(telemetry)

            # Проверка наличия отказов
            if self.engine_failure_detector.has_engine_failure():
                has_engine_failure = True

                if not self.asymmetric_mode:
                    # Переключение в асимметричный режим
                    self.asymmetric_mode = True
                    failed_engines = self.engine_failure_detector.get_failed_engines()
                    logger.critical(f"SWITCHING TO ASYMMETRIC THRUST MODE - Failed engines: {failed_engines}")

                # Расчёт асимметричной тяги
                corrections = self.engine_failure_detector.calculate_asymmetric_thrust_correction()

                # Применение базовой тяги с коррекциями для каждого двигателя
                engine_throttles = {}
                for i in range(1, self.engine_failure_detector.number_of_engines + 1):
                    correction = corrections.get(f'engine_{i}', 1.0)
                    engine_throttles[i] = new_throttle * correction

                logger.warning(f"Asymmetric throttle: {engine_throttles}")

            else:
                # Нет отказов - симметричная тяга
                if self.asymmetric_mode:
                    # Выход из асимметричного режима
                    self.asymmetric_mode = False
                    logger.info("Exiting asymmetric thrust mode - all engines operational")

                # engine_throttles остаётся None для симметричного режима
        else:
            # Детектор не подключён - используем симметричную тягу
            engine_throttles = None

        # 7. Ограничение скорости изменения (плавность)
        throttle_change = new_throttle - self.current_throttle
        if abs(throttle_change) > self.config.max_throttle_rate:
            throttle_change = self.config.max_throttle_rate * (1 if throttle_change > 0 else -1)
            new_throttle = self.current_throttle + throttle_change

        # 8. Ограничение диапазона
        new_throttle = max(self.config.min_throttle, min(self.config.max_throttle, new_throttle))

        # Применение ограничений к индивидуальным двигателям
        if engine_throttles:
            for engine_idx in engine_throttles.keys():
                engine_throttles[engine_idx] = max(
                    self.config.min_throttle,
                    min(self.config.max_throttle, engine_throttles[engine_idx])
                )

        # Обновление состояния
        self.current_throttle = new_throttle
        self.total_corrections += 1

        # Проверка стабильности
        speed_error = abs(current_speed - target_speed)
        is_stable = speed_error < self.config.target_speed_tolerance

        # Логирование
        if has_engine_failure:
            logger.warning(f"Autothrottle (ASYMMETRIC): {new_throttle*100:.1f}% base "
                          f"(IAS: {current_speed:.0f}kt → {target_speed:.0f}kt, "
                          f"error: {speed_error:.1f}kt, engines: {engine_throttles})")
        else:
            logger.info(f"Autothrottle: {new_throttle*100:.1f}% "
                       f"(IAS: {current_speed:.0f}kt → {target_speed:.0f}kt, "
                       f"error: {speed_error:.1f}kt, "
                       f"wind: {headwind:+.0f}kt head / {abs(crosswind):.0f}kt cross, "
                       f"bank: {current_bank:+.1f}°)")

        return {
            'active': True,
            'throttle': new_throttle,
            'base_throttle': base_throttle,
            'wind_correction': wind_correction,
            'crosswind_drag': crosswind_drag,
            'pid_correction': pid_correction,
            'speed_error': speed_error,
            'is_stable': is_stable,
            'target_speed': target_speed,
            'current_speed': current_speed,
            'headwind': headwind,
            'crosswind': crosswind,
            'bank_angle': current_bank,
            'asymmetric_mode': self.asymmetric_mode,
            'engine_throttles': engine_throttles,  # None если симметричный режим, dict если асимметричный
            'has_engine_failure': has_engine_failure
        }

    def update(self, telemetry_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Реализация абстрактного метода Controller.update()

        Обёртка над calculate_throttle() для соответствия интерфейсу Controller

        Args:
            telemetry_data: Словарь с телеметрией, должен содержать:
                - 'telemetry': основная телеметрия
                - 'target_speed': целевая скорость (узлы)
                - 'wind_data': данные о ветре
                - 'aircraft_weight': вес самолёта (опционально)

        Returns:
            Результат работы контроллера (см. calculate_throttle)
        """
        # Извлекаем параметры из telemetry_data
        telemetry = telemetry_data.get('telemetry', telemetry_data)
        target_speed = telemetry_data.get('target_speed', 140.0)
        wind_data = telemetry_data.get('wind_data', {})
        aircraft_weight = telemetry_data.get('aircraft_weight', 5000.0)

        # Вызываем основной метод
        return self.calculate_throttle(
            telemetry=telemetry,
            target_speed=target_speed,
            wind_data=wind_data,
            aircraft_weight=aircraft_weight
        )

    def get_status(self) -> Dict[str, any]:
        """Получить статус контроллера"""
        return {
            'active': self.active,
            'current_throttle': self.current_throttle,
            'integral': self.integral,
            'total_corrections': self.total_corrections
        }


class VJoyThrottleIntegration:
    """Интеграция автоматической тяги с vJoy"""

    def __init__(self, virtual_joystick):
        """
        Args:
            virtual_joystick: Экземпляр VirtualJoystick
        """
        self.vjoy = virtual_joystick
        self.enabled = False

    def enable(self):
        """Включить управление тягой через vJoy"""
        if self.vjoy.enabled:
            self.enabled = True
            logger.info("vJoy throttle control enabled")
            return True
        else:
            logger.warning("vJoy not connected, throttle control disabled")
            return False

    def disable(self):
        """Отключить управление тягой через vJoy"""
        self.enabled = False
        logger.info("vJoy throttle control disabled")

    def set_throttle(self, throttle_value: float):
        """
        Установить тягу через vJoy

        Args:
            throttle_value: Значение тяги (0.0 - 1.0)
        """
        if not self.enabled or not self.vjoy.enabled:
            return False

        try:
            # VirtualJoystick.set_throttle expects 0.0–1.0
            self.vjoy.set_throttle(throttle_value)

            logger.debug("vJoy throttle set: %s", throttle_value)
            return True

        except Exception as e:
            logger.error("Error setting vJoy throttle: %s", e)
            return False
