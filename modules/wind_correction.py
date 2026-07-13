"""
Модуль коррекции ветра для точного захода на посадку
"""

import logging
import math
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class WindCorrection:
    """Класс для расчёта и применения поправок на ветер"""

    @staticmethod
    def calculate_wind_components(wind_speed: float, wind_direction: float,
                                  aircraft_heading: float) -> Tuple[float, float]:
        """
        Расчёт компонентов ветра относительно курса самолёта

        Args:
            wind_speed: Скорость ветра (узлы)
            wind_direction: Направление ветра (градусы, откуда дует)
            aircraft_heading: Курс самолёта (градусы)

        Returns:
            (headwind, crosswind) - встречный и боковой ветер (узлы)
            headwind > 0 = встречный, < 0 = попутный
            crosswind > 0 = справа, < 0 = слева
        """
        # Угол между направлением ветра и курсом самолёта
        wind_angle = math.radians(wind_direction - aircraft_heading)

        # Встречная составляющая (положительная = встречный)
        headwind = wind_speed * math.cos(wind_angle)

        # Боковая составляющая (положительная = справа)
        crosswind = wind_speed * math.sin(wind_angle)

        return headwind, crosswind

    @staticmethod
    def calculate_drift_angle(crosswind: float, true_airspeed: float) -> float:
        """
        Расчёт угла сноса

        Args:
            crosswind: Боковой ветер (узлы, > 0 = справа)
            true_airspeed: Истинная воздушная скорость (узлы)

        Returns:
            Угол сноса (градусы): отрицательный = снос влево,
            положительный = снос вправо.
            Ветер справа (crosswind > 0) → снос влево (drift < 0).
        """
        if true_airspeed <= 0:
            return 0.0

        ratio = max(-1.0, min(1.0, -crosswind / true_airspeed))
        return math.degrees(math.asin(ratio))

    def calculate_corrected_heading(self, desired_track: float, wind_speed: float,
                                   wind_direction: float, true_airspeed: float) -> float:
        """
        Расчёт скорректированного курса для следования по заданному пути

        Args:
            desired_track: Желаемый путевой угол (градусы)
            wind_speed: Скорость ветра (узлы)
            wind_direction: Направление ветра (градусы)
            true_airspeed: Истинная воздушная скорость (узлы)

        Returns:
            Скорректированный курс (градусы)
        """
        # Компоненты ветра относительно желаемого пути
        headwind, crosswind = self.calculate_wind_components(
            wind_speed, wind_direction, desired_track
        )

        # Угол упреждения: crosswind > 0 (справа) → crab > 0 (нос вправо)
        if true_airspeed > 0:
            ratio = max(-1.0, min(1.0, crosswind / true_airspeed))
            crab = math.degrees(math.asin(ratio))
        else:
            crab = 0.0

        corrected_heading = (desired_track + crab) % 360

        logger.debug(f"Track: {desired_track}°, Wind: {wind_speed}kt from {wind_direction}°, "
                    f"Crosswind: {crosswind:.1f}kt, Crab: {crab:.1f}°, "
                    f"Corrected heading: {corrected_heading:.1f}°")

        return corrected_heading

    @staticmethod
    def calculate_bank_angle_for_crosswind(crosswind: float, airspeed: float,
                                          max_bank: float = 15.0) -> float:
        """
        Расчёт крена для компенсации бокового ветра (метод wing-low)

        Args:
            crosswind: Боковой ветер (узлы)
            airspeed: Приборная скорость (узлы)
            max_bank: Максимальный крен на финале (градусы)

        Returns:
            Рекомендуемый крен (градусы)
        """
        if airspeed <= 0:
            return 0.0

        # Упрощённый расчёт: крен пропорционален боковому ветру
        # Примерно 1° крена на 2 узла бокового ветра
        bank = (crosswind / 2.0)

        # Ограничение крена
        bank = max(-max_bank, min(max_bank, bank))

        return bank

    def calculate_pitch_correction(self, headwind: float, target_vs: float,
                                  airspeed: float) -> float:
        """
        .. deprecated::
            Не использовать. VS = GS × tan(γ) уже полностью определяет
            вертикальную скорость; headwind * 10 — недокументированная
            эвристика, повторно учитывающая ветер. Оставлен для совместимости.

        Args:
            headwind: Встречный ветер (узлы, + встречный, - попутный)
            target_vs: Целевая вертикальная скорость (футы/мин)
            airspeed: Приборная скорость (узлы)

        Returns:
            Коррекция вертикальной скорости (футы/мин)
        """
        correction = headwind * 10

        logger.debug("Headwind: %skt, VS correction: %s fpm", headwind, correction)

        return correction

    def apply_wind_corrections(self, telemetry: Dict, approach_data: Dict,
                              config) -> Dict[str, float]:
        """
        Применить все поправки на ветер

        Args:
            telemetry: Данные телеметрии
            approach_data: Данные захода
            config: Конфигурация захода

        Returns:
            Dict с скорректированными параметрами
        """
        weather = telemetry.get('weather', {})
        speed = telemetry.get('speed', {})

        wind_speed = weather.get('ambient_wind_velocity', 0)
        wind_direction = weather.get('ambient_wind_direction', 0)
        true_airspeed = speed.get('airspeed_true', 0)
        ground_speed = speed.get('ground_speed', 0)

        # Желаемый путевой угол (курс посадки)
        # For LOC: use localizer-derived heading from approach_data
        # if available; otherwise fall back to config.final_approach_course.
        desired_track = approach_data.get('corrected_heading',
                                          config.final_approach_course)

        # F-W2: fail-closed on invalid wind inputs
        if (not math.isfinite(wind_speed)
                or not math.isfinite(wind_direction)
                or wind_speed < 0):
            logger.warning(
                "Invalid wind inputs: speed=%s, direction=%s; "
                "returning zero corrections",
                wind_speed, wind_direction,
            )
            base_vs = self.calculate_descent_rate(
                ground_speed, config.glideslope_angle
            )
            return {
                'wind_speed': wind_speed,
                'wind_direction': wind_direction,
                'headwind': 0.0,
                'crosswind': 0.0,
                'drift_angle': 0.0,
                'corrected_heading': desired_track,
                'recommended_bank': 0.0,
                'base_vs': base_vs,
                'vs_correction': 0.0,
                'corrected_vs': base_vs,
            }

        # Компоненты ветра
        headwind, crosswind = self.calculate_wind_components(
            wind_speed, wind_direction, desired_track
        )

        # Скорректированный курс
        corrected_heading = self.calculate_corrected_heading(
            desired_track, wind_speed, wind_direction, true_airspeed
        )

        # Угол сноса
        drift_angle = self.calculate_drift_angle(crosswind, true_airspeed)

        # Рекомендуемый крен для компенсации
        recommended_bank = self.calculate_bank_angle_for_crosswind(
            crosswind, speed.get('airspeed_indicated', 0)
        )

        # F-W3: corrected_vs = base_vs (geometric VS = GS × tan(γ))
        base_vs = self.calculate_descent_rate(ground_speed, config.glideslope_angle)

        return {
            'wind_speed': wind_speed,
            'wind_direction': wind_direction,
            'headwind': headwind,
            'crosswind': crosswind,
            'drift_angle': drift_angle,
            'corrected_heading': corrected_heading,
            'recommended_bank': recommended_bank,
            'base_vs': base_vs,
            'vs_correction': 0.0,
            'corrected_vs': base_vs,
        }

    @staticmethod
    def calculate_descent_rate(ground_speed: float, glideslope_angle: float) -> float:
        """
        Расчёт базовой вертикальной скорости для глиссады

        Args:
            ground_speed: Путевая скорость (узлы)
            glideslope_angle: Угол глиссады (градусы)

        Returns:
            Вертикальная скорость (футы/мин). 0.0 если угол вне (0, 10].
        """
        if glideslope_angle <= 0 or glideslope_angle > 10:
            logger.warning(
                "Glideslope angle %.1f° outside valid range (0, 10]; returning 0.0",
                glideslope_angle,
            )
            return 0.0
        vs = ground_speed * math.tan(math.radians(glideslope_angle)) * 101.3
        return vs
