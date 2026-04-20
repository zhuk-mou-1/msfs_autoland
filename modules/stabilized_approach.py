"""
Модуль проверки критериев стабилизированного захода
Stabilized Approach Criteria (ICAO/FAA standards)
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from .thresholds_config import get_thresholds

logger = logging.getLogger(__name__)


class StabilizationGate(Enum):
    """Высоты проверки стабилизации"""
    IMC_1000 = 1000  # IMC (Instrument Meteorological Conditions)
    VMC_500 = 500    # VMC (Visual Meteorological Conditions)


@dataclass
class StabilizedCriteria:
    """Критерии стабилизированного захода"""
    # Высота проверки
    stabilization_height: int = 1000  # футы AGL

    # Допуски скорости
    speed_target: int = 120  # узлы (Vref)
    speed_tolerance_high: int = 10
    speed_tolerance_low: int = 5

    # Вертикальная скорость
    max_vertical_speed: int = 1000

    # Отклонение от глиссады
    max_glideslope_deviation: float = 1.0

    # Отклонение от курса
    max_localizer_deviation: float = 1.0

    # Крен
    max_bank_angle: float = 7.0

    # Газ
    min_throttle_percent: float = 30.0

    # Конфигурация
    require_landing_config: bool = True

    @classmethod
    def from_thresholds(cls, speed_target: int = 120) -> 'StabilizedCriteria':
        """Создать критерии из централизованных порогов"""
        config = get_thresholds().stabilized_approach
        return cls(
            speed_target=speed_target,
            speed_tolerance_high=int(config.speed_tolerance_high),
            speed_tolerance_low=int(config.speed_tolerance_low),
            max_vertical_speed=config.max_vertical_speed,
            max_glideslope_deviation=config.max_glideslope_deviation,
            max_localizer_deviation=config.max_localizer_deviation,
            max_bank_angle=config.max_bank_angle,
            min_throttle_percent=config.min_throttle_percent
        )


class StabilizedApproachMonitor:
    """Монитор стабилизированного захода"""

    def __init__(self, criteria: Optional[StabilizedCriteria] = None):
        self.criteria = criteria or StabilizedCriteria()
        self.is_stabilized = False
        self.violations: List[str] = []
        self.stabilization_checked = False
        self.go_around_required = False

    def check_stabilization(self, telemetry: Dict, approach_data: Dict,
                           wind_data: Dict) -> Dict[str, any]:
        """
        Проверка критериев стабилизированного захода

        Args:
            telemetry: Данные телеметрии
            approach_data: Данные захода
            wind_data: Данные ветра

        Returns:
            Dict с результатами проверки
        """
        self.violations = []

        # Получение данных
        radio_height = telemetry['position'].get('radio_height',
                                                 telemetry['position']['altitude_agl'])
        airspeed = telemetry['speed']['airspeed_indicated']
        vertical_speed = telemetry['speed']['vertical_speed']
        bank_angle = abs(telemetry['attitude']['bank'])

        # Проверка высоты стабилизации
        if radio_height > self.criteria.stabilization_height:
            return {
                'is_stabilized': None,
                'checked': False,
                'violations': [],
                'message': f"Above stabilization height ({self.criteria.stabilization_height}ft)"
            }

        # Если уже прошли высоту стабилизации
        if not self.stabilization_checked:
            self.stabilization_checked = True
            logger.info("Checking stabilization at %sft AGL", radio_height)

        # 1. Проверка скорости
        speed_deviation = airspeed - self.criteria.speed_target
        if speed_deviation > self.criteria.speed_tolerance_high:
            self.violations.append(f"Speed too high: {airspeed:.0f}kt "
                                 f"(max {self.criteria.speed_target + self.criteria.speed_tolerance_high}kt)")
        elif speed_deviation < -self.criteria.speed_tolerance_low:
            self.violations.append(f"Speed too low: {airspeed:.0f}kt "
                                 f"(min {self.criteria.speed_target - self.criteria.speed_tolerance_low}kt)")

        # 2. Проверка вертикальной скорости
        if abs(vertical_speed) > self.criteria.max_vertical_speed:
            self.violations.append(f"Vertical speed too high: {abs(vertical_speed):.0f} fpm "
                                 f"(max {self.criteria.max_vertical_speed} fpm)")

        # 3. Проверка отклонения от глиссады
        altitude_deviation = telemetry['position']['altitude'] - approach_data.get('required_altitude', 0)
        # Преобразование в "dots" (примерно 200ft = 1 dot)
        glideslope_dots = abs(altitude_deviation) / 200.0
        if glideslope_dots > self.criteria.max_glideslope_deviation:
            self.violations.append(f"Glideslope deviation: {glideslope_dots:.1f} dots "
                                 f"(max {self.criteria.max_glideslope_deviation} dots)")

        # 4. Проверка отклонения от курса
        cross_track_error = abs(approach_data.get('cross_track_error', 0))
        if cross_track_error > self.criteria.max_localizer_deviation:
            self.violations.append(f"Localizer deviation: {cross_track_error:.1f}° "
                                 f"(max {self.criteria.max_localizer_deviation}°)")

        # 5. Проверка крена
        if bank_angle > self.criteria.max_bank_angle:
            self.violations.append(f"Bank angle too high: {bank_angle:.1f}° "
                                 f"(max {self.criteria.max_bank_angle}°)")

        # 6. Проверка конфигурации (закрылки и шасси)
        if self.criteria.require_landing_config:
            config = telemetry.get('configuration', {})
            flaps_position = config.get('flaps_position', 0.0)
            gear_position = config.get('gear_position', 0.0)

            # Закрылки должны быть выпущены минимум на 90%
            if flaps_position < 0.9:
                self.violations.append(f"Flaps not in landing position: {flaps_position*100:.0f}% "
                                     f"(required ≥90%)")

            # Шасси должно быть выпущено и заблокировано (≥95%)
            if gear_position < 0.95:
                self.violations.append(f"Gear not down and locked: {gear_position*100:.0f}% "
                                     f"(required ≥95%)")

        # Определение стабилизации
        self.is_stabilized = len(self.violations) == 0

        # Логирование
        if self.is_stabilized:
            logger.info("✓ STABILIZED at %sft AGL", radio_height)
        else:
            logger.warning("✗ NOT STABILIZED at %sft AGL:", radio_height)
            for violation in self.violations:
                logger.warning("  - %s", violation)

        return {
            'is_stabilized': self.is_stabilized,
            'checked': True,
            'violations': self.violations.copy(),
            'radio_height': radio_height,
            'speed': airspeed,
            'vertical_speed': vertical_speed,
            'bank_angle': bank_angle,
            'glideslope_deviation': glideslope_dots,
            'localizer_deviation': cross_track_error,
            'flaps_position': telemetry.get('configuration', {}).get('flaps_position', 0.0),
            'gear_position': telemetry.get('configuration', {}).get('gear_position', 0.0)
        }

    def check_continuous_monitoring(self, telemetry: Dict, approach_data: Dict) -> Dict[str, any]:
        """
        Непрерывный мониторинг после прохождения высоты стабилизации

        Args:
            telemetry: Данные телеметрии
            approach_data: Данные захода

        Returns:
            Dict с результатами мониторинга
        """
        if not self.stabilization_checked:
            return {'monitoring': False, 'go_around': False}

        radio_height = telemetry['position'].get('radio_height',
                                                 telemetry['position']['altitude_agl'])

        # Критические нарушения ниже высоты стабилизации
        critical_violations = []

        # Проверка критических параметров
        airspeed = telemetry['speed']['airspeed_indicated']
        vertical_speed = telemetry['speed']['vertical_speed']
        bank_angle = abs(telemetry['attitude']['bank'])

        # Критические отклонения скорости (более строгие)
        if airspeed > self.criteria.speed_target + 20:
            critical_violations.append(f"CRITICAL: Speed {airspeed:.0f}kt too high")
        elif airspeed < self.criteria.speed_target - 10:
            critical_violations.append(f"CRITICAL: Speed {airspeed:.0f}kt too low")

        # Критическая вертикальная скорость
        if abs(vertical_speed) > 1500:
            critical_violations.append(f"CRITICAL: Vertical speed {abs(vertical_speed):.0f} fpm")

        # Критический крен
        if bank_angle > 15.0:
            critical_violations.append(f"CRITICAL: Bank angle {bank_angle:.1f}°")

        # Решение об уходе на второй круг
        if critical_violations and radio_height < 500:
            self.go_around_required = True
            logger.critical("GO AROUND REQUIRED!")
            for violation in critical_violations:
                logger.critical("  - %s", violation)

        return {
            'monitoring': True,
            'go_around': self.go_around_required,
            'critical_violations': critical_violations,
            'radio_height': radio_height
        }

    def should_go_around(self, radio_height: float) -> bool:
        """
        Определение необходимости ухода на второй круг

        Args:
            radio_height: Высота над землёй (футы)

        Returns:
            True если нужен уход на второй круг
        """
        # Если не стабилизирован на высоте стабилизации
        if self.stabilization_checked and not self.is_stabilized:
            if radio_height < self.criteria.stabilization_height - 100:
                logger.warning("NOT STABILIZED - GO AROUND RECOMMENDED")
                return True

        # Если есть критические нарушения
        if self.go_around_required:
            return True

        return False

    def reset(self):
        """Сброс состояния монитора"""
        self.is_stabilized = False
        self.violations = []
        self.stabilization_checked = False
        self.go_around_required = False
        logger.info("Stabilization monitor reset")

    def get_status_summary(self) -> str:
        """Получить краткую сводку статуса"""
        if not self.stabilization_checked:
            return "Awaiting stabilization check"
        elif self.is_stabilized:
            return "✓ STABILIZED"
        elif self.go_around_required:
            return "✗ GO AROUND REQUIRED"
        else:
            return f"✗ NOT STABILIZED ({len(self.violations)} violations)"

    def configure_for_conditions(self, conditions: str = 'IMC'):
        """
        Настройка критериев в зависимости от условий

        Args:
            conditions: 'IMC' (приборные) или 'VMC' (визуальные)
        """
        if conditions == 'IMC':
            self.criteria.stabilization_height = 1000
            logger.info("Configured for IMC (1000ft stabilization)")
        elif conditions == 'VMC':
            self.criteria.stabilization_height = 500
            logger.info("Configured for VMC (500ft stabilization)")
