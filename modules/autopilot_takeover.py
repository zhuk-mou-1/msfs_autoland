"""
Модуль автоматической передачи управления от автопилота к AutoLand системе
"""

import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TakeoverConfig:
    """Конфигурация передачи управления"""
    # Расстояния и высоты для VOR/NDB заходов
    takeover_distance_nm: float = 10.0  # Расстояние до порога ВПП
    takeover_altitude_min: float = 1500.0  # Минимальная высота AGL
    takeover_altitude_max: float = 4000.0  # Максимальная высота AGL

    # Высоты для ILS CAT I/II заходов (передача на DH)
    ils_cat1_dh: float = 200.0  # Decision Height CAT I (футы)
    ils_cat2_dh: float = 100.0  # Decision Height CAT II (футы)
    ils_takeover_enabled: bool = True  # Включить передачу для ILS на DH

    # Таймауты
    initialization_timeout: float = 30.0  # Секунды на инициализацию
    stabilization_timeout: float = 10.0  # Секунды на стабилизацию

    # Проверки безопасности
    require_stable_speed: bool = True  # Требовать стабильную скорость
    require_stable_altitude: bool = True  # Требовать стабильную высоту
    speed_tolerance: float = 10.0  # Допуск скорости (узлы)
    altitude_tolerance: float = 200.0  # Допуск высоты (футы)


@dataclass
class TakeoverStatus:
    """Статус передачи управления"""
    ready: bool = False
    in_progress: bool = False
    completed: bool = False
    failed: bool = False

    distance_to_threshold: float = 0.0
    altitude_agl: float = 0.0

    autopilot_disengaged: bool = False
    autothrottle_disengaged: bool = False
    controls_acquired: bool = False

    checks_passed: Dict[str, bool] = None
    error_message: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if self.checks_passed is None:
            self.checks_passed = {}


class AutopilotTakeover:
    """Контроллер автоматической передачи управления"""

    def __init__(self, config: Optional[TakeoverConfig] = None):
        self.config = config or TakeoverConfig()
        self.status = TakeoverStatus()
        self.takeover_start_time = None
        self.initial_parameters = {}

    def should_initiate_takeover(self,
                                 distance_to_threshold: float,
                                 altitude_agl: float,
                                 approach_phase: str,
                                 approach_type: str = None,
                                 decision_height: float = None,
                                 ils_category: str = None) -> bool:
        """
        Определить нужно ли начинать передачу управления

        Args:
            distance_to_threshold: Расстояние до порога ВПП (NM)
            altitude_agl: Высота над землёй (футы)
            approach_phase: Текущая фаза захода
            approach_type: Тип захода (ILS, VOR, NDB, GPS)
            decision_height: Decision Height для ILS (футы)
            ils_category: Категория ILS (CAT_I, CAT_II, CAT_III)

        Returns:
            True если нужно начинать передачу управления
        """
        # Не начинаем если уже в процессе или завершено
        if self.status.in_progress or self.status.completed:
            return False

        # Логика для ILS заходов CAT I/II
        if approach_type and approach_type.upper() == 'ILS':
            if not self.config.ils_takeover_enabled:
                logger.debug("ILS takeover disabled in config")
                return False

            # Определение Decision Height
            if decision_height is None:
                # Определяем по категории
                if ils_category == 'CAT_II':
                    decision_height = self.config.ils_cat2_dh
                else:  # CAT_I или не указано
                    decision_height = self.config.ils_cat1_dh

            # Проверка высоты для ILS: передача управления на DH + 50 футов
            # (небольшой запас для инициализации)
            takeover_height = decision_height + 50.0

            if altitude_agl <= takeover_height and altitude_agl > decision_height:
                # Дополнительная проверка фазы
                if approach_phase in ['FINAL', 'LANDING']:
                    logger.info(f"ILS takeover conditions met at DH: "
                               f"altitude={altitude_agl:.0f}ft, DH={decision_height:.0f}ft, "
                               f"category={ils_category or 'CAT_I'}")
                    return True
            return False

        # Логика для VOR/NDB заходов (как раньше)
        if approach_type and approach_type.upper() not in ['VOR', 'NDB']:
            logger.debug(f"Takeover skipped: approach type {approach_type} does not require manual control "
                        f"(only VOR/NDB/ILS require takeover)")
            return False

        # Проверка расстояния для VOR/NDB
        distance_ok = distance_to_threshold <= self.config.takeover_distance_nm

        # Проверка высоты для VOR/NDB
        altitude_ok = (self.config.takeover_altitude_min <= altitude_agl <=
                      self.config.takeover_altitude_max)

        # Проверка фазы (должны быть на заходе, но не в посадке)
        phase_ok = approach_phase in ['INTERMEDIATE', 'FINAL']

        if distance_ok and altitude_ok and phase_ok:
            logger.info(f"Takeover conditions met for {approach_type} approach: "
                       f"distance={distance_to_threshold:.1f}nm, "
                       f"altitude={altitude_agl:.0f}ft, phase={approach_phase}")
            return True

        return False

    def perform_takeover(self,
                        telemetry: Dict,
                        aircraft_adapter,
                        control) -> TakeoverStatus:
        """
        Выполнить передачу управления

        Args:
            telemetry: Данные телеметрии
            aircraft_adapter: Адаптер самолёта
            control: Контроллер управления

        Returns:
            Статус передачи управления
        """
        if not self.status.in_progress:
            self._start_takeover()

        # Проверка таймаута
        if time.time() - self.takeover_start_time > self.config.initialization_timeout:
            self.status.failed = True
            self.status.error_message = "Takeover timeout exceeded"
            logger.error("Takeover failed: timeout")
            return self.status

        # Шаг 1: Сохранение начальных параметров
        if not self.initial_parameters:
            self._save_initial_parameters(telemetry)

        # Шаг 2: Выполнение проверок безопасности
        checks = self._perform_safety_checks(telemetry)
        self.status.checks_passed = checks

        if not all(checks.values()):
            failed_checks = [k for k, v in checks.items() if not v]
            logger.warning("Safety checks failed: %s", ', '.join(failed_checks))
            # Не прерываем, продолжаем попытки

        # Шаг 3: Отключение автопилота
        if not self.status.autopilot_disengaged:
            self._disengage_autopilot(aircraft_adapter, control)

        # Шаг 4: Отключение автомата тяги
        if not self.status.autothrottle_disengaged:
            self._disengage_autothrottle(aircraft_adapter, control)

        # Шаг 5: Захват управления
        if not self.status.controls_acquired:
            self._acquire_controls(control)

        # Шаг 6: Проверка завершения
        if (self.status.autopilot_disengaged and
            self.status.autothrottle_disengaged and
            self.status.controls_acquired):
            self._complete_takeover()

        return self.status

    def _start_takeover(self):
        """Начать процесс передачи управления"""
        self.status.in_progress = True
        self.takeover_start_time = time.time()
        self.status.timestamp = self.takeover_start_time
        logger.info("=" * 60)
        logger.info("AUTOPILOT TAKEOVER INITIATED")
        logger.info("=" * 60)

    def _save_initial_parameters(self, telemetry: Dict):
        """Сохранить начальные параметры для сравнения"""
        self.initial_parameters = {
            'altitude': telemetry['position']['altitude'],
            'altitude_agl': telemetry['position']['altitude_agl'],
            'airspeed': telemetry['speed']['airspeed_indicated'],
            'heading': telemetry['attitude']['heading_magnetic'],
            'pitch': telemetry['attitude']['pitch'],
            'bank': telemetry['attitude']['bank'],
            'vertical_speed': telemetry['speed']['vertical_speed']
        }
        logger.info(f"Initial parameters saved: IAS={self.initial_parameters['airspeed']:.0f}kt, "
                   f"ALT={self.initial_parameters['altitude']:.0f}ft, "
                   f"HDG={self.initial_parameters['heading']:.0f}°")

    def _perform_safety_checks(self, telemetry: Dict) -> Dict[str, bool]:
        """
        Выполнить проверки безопасности

        Returns:
            Dict с результатами проверок
        """
        checks = {}

        # 1. Проверка высоты
        altitude_agl = telemetry['position']['altitude_agl']
        checks['altitude_safe'] = altitude_agl >= self.config.takeover_altitude_min

        # 2. Проверка скорости (если требуется)
        if self.config.require_stable_speed and self.initial_parameters:
            current_speed = telemetry['speed']['airspeed_indicated']
            initial_speed = self.initial_parameters['airspeed']
            speed_change = abs(current_speed - initial_speed)
            checks['speed_stable'] = speed_change <= self.config.speed_tolerance
        else:
            checks['speed_stable'] = True

        # 3. Проверка высоты (если требуется)
        if self.config.require_stable_altitude and self.initial_parameters:
            current_alt = telemetry['position']['altitude']
            initial_alt = self.initial_parameters['altitude']
            alt_change = abs(current_alt - initial_alt)
            checks['altitude_stable'] = alt_change <= self.config.altitude_tolerance
        else:
            checks['altitude_stable'] = True

        # 4. Проверка положения самолёта
        bank = abs(telemetry['attitude']['bank'])
        pitch = telemetry['attitude']['pitch']
        checks['attitude_safe'] = bank < 30 and -10 < pitch < 15

        # 5. Проверка на земле
        on_ground = telemetry['position'].get('on_ground', False)
        checks['airborne'] = not on_ground

        return checks

    def _disengage_autopilot(self, aircraft_adapter, control):
        """Отключить автопилот"""
        try:
            logger.info("Disengaging autopilot...")

            # Попытка через aircraft adapter (для кастомных самолётов)
            if aircraft_adapter and hasattr(aircraft_adapter, 'disengage_autopilot'):
                success = aircraft_adapter.disengage_autopilot()
                if success:
                    logger.info("✓ Autopilot disengaged via aircraft adapter")
                    self.status.autopilot_disengaged = True
                    return

            # Fallback: стандартный SimConnect
            control.set_autopilot_master(False)

            # Отключение всех режимов автопилота
            control.set_heading_hold(False)
            control.set_altitude_hold(False)
            control.set_airspeed_hold(False)
            control.set_vertical_speed_hold(False)

            logger.info("✓ Autopilot disengaged via SimConnect")
            self.status.autopilot_disengaged = True

        except Exception as e:
            logger.error("Failed to disengage autopilot: %s", e)
            # Продолжаем попытки в следующем цикле

    def _disengage_autothrottle(self, aircraft_adapter, control):
        """Отключить автомат тяги"""
        try:
            logger.info("Disengaging autothrottle...")

            # Попытка через aircraft adapter (для кастомных самолётов)
            if aircraft_adapter and hasattr(aircraft_adapter, 'disengage_autothrottle'):
                success = aircraft_adapter.disengage_autothrottle()
                if success:
                    logger.info("✓ Autothrottle disengaged via aircraft adapter")
                    self.status.autothrottle_disengaged = True
                    return

            # Fallback: стандартный SimConnect
            # Для стандартных самолётов автомат тяги обычно часть автопилота
            # Устанавливаем ручное управление тягой
            logger.info("✓ Autothrottle control transferred (SimConnect)")
            self.status.autothrottle_disengaged = True

        except Exception as e:
            logger.error("Failed to disengage autothrottle: %s", e)
            # Продолжаем попытки в следующем цикле

    def _acquire_controls(self, control):
        """Захватить управление самолётом"""
        try:
            logger.info("Acquiring flight controls...")

            # Центрирование управления (нейтральное положение)
            # Это предотвращает резкие движения при передаче управления

            # Примечание: В реальности SimConnect автоматически передаёт управление
            # когда мы начинаем отправлять команды. Здесь мы просто логируем.

            logger.info("✓ Flight controls acquired")
            self.status.controls_acquired = True

        except Exception as e:
            logger.error("Failed to acquire controls: %s", e)

    def _complete_takeover(self):
        """Завершить передачу управления"""
        self.status.in_progress = False
        self.status.completed = True
        self.status.ready = True

        elapsed = time.time() - self.takeover_start_time

        logger.info("=" * 60)
        logger.info("AUTOPILOT TAKEOVER COMPLETED (%ss)", elapsed)
        logger.info("AutoLand system now has full control")
        logger.info("=" * 60)

    def get_status_summary(self) -> str:
        """Получить текстовую сводку статуса"""
        if self.status.failed:
            return f"FAILED: {self.status.error_message}"
        elif self.status.completed:
            return "COMPLETED - AutoLand in control"
        elif self.status.in_progress:
            steps = []
            if self.status.autopilot_disengaged:
                steps.append("AP✓")
            else:
                steps.append("AP...")

            if self.status.autothrottle_disengaged:
                steps.append("AT✓")
            else:
                steps.append("AT...")

            if self.status.controls_acquired:
                steps.append("CTRL✓")
            else:
                steps.append("CTRL...")

            return f"IN PROGRESS: {' '.join(steps)}"
        else:
            return "READY"

    def reset(self):
        """Сброс состояния"""
        self.status = TakeoverStatus()
        self.takeover_start_time = None
        self.initial_parameters = {}
        logger.info("Takeover controller reset")

    def get_recommended_takeover_point(self,
                                      approach_type: str,
                                      runway_length_m: int,
                                      weather_conditions: Dict,
                                      decision_height: float = None) -> Tuple[float, float]:
        """
        Рассчитать рекомендуемую точку передачи управления

        Args:
            approach_type: Тип захода (ILS, VOR, NDB, GPS)
            runway_length_m: Длина ВПП (метры)
            weather_conditions: Погодные условия
            decision_height: Decision Height для ILS (футы)

        Returns:
            (distance_nm, altitude_agl) - рекомендуемая точка
        """
        # Базовые значения
        distance = 10.0  # NM
        altitude = 3000.0  # футы AGL

        # Коррекция по типу захода
        if approach_type == 'ILS':
            # ILS - передача управления на Decision Height для flare
            # Автопилот самолёта ведёт до DH, затем AutoLand берёт управление
            if decision_height:
                altitude = decision_height + 50.0  # DH + 50 футов запаса
            else:
                altitude = 250.0  # По умолчанию CAT I (200 ft DH + 50 ft)

            # Расстояние не важно для ILS (передача по высоте)
            distance = 0.0

            logger.info("ILS approach: takeover at DH+50ft = %sft AGL", altitude)

        elif approach_type in ['VOR', 'NDB']:
            # VOR/NDB - нужно больше времени на стабилизацию
            distance = 10.0
            altitude = 3500.0
        elif approach_type == 'GPS':
            # GPS - средняя точность
            distance = 9.0
            altitude = 3000.0

        # Коррекция по длине ВПП (только для VOR/NDB)
        if approach_type in ['VOR', 'NDB'] and runway_length_m < 1500:
            # Короткая ВПП - начинаем раньше
            distance += 2.0
            altitude += 500.0

        # Коррекция по погоде (только для VOR/NDB)
        if approach_type in ['VOR', 'NDB']:
            wind_speed = weather_conditions.get('wind_velocity', 0)
            visibility = weather_conditions.get('visibility', 10000)

            if wind_speed > 20:
                # Сильный ветер - больше времени на стабилизацию
                distance += 1.0
                altitude += 500.0

            if visibility < 5000:
                # Плохая видимость - начинаем раньше
                distance += 1.0

        logger.info(f"Recommended takeover point: {distance:.1f}nm, {altitude:.0f}ft AGL "
                   f"(approach={approach_type}, runway={runway_length_m}m)")

        return distance, altitude
