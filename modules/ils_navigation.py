"""
Модуль навигации по ILS (Instrument Landing System)
"""

import logging
import math
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ILSConfig:
    """Конфигурация ILS захода"""
    frequency: int  # Hz (например, 110300000 для 110.30 MHz)
    localizer_course: int  # градусы (курс localizer)
    glideslope_angle: float = 3.0  # градусы (обычно 3.0°)
    decision_height: int = 200  # футы
    approach_speed: int = 120  # узлы
    runway_elevation: int = 0  # футы MSL
    runway_length: int = 8000  # футы
    runway_width: int = 150  # футы
    runway_threshold_lat: float = 0.0
    runway_threshold_lon: float = 0.0


class ILSNavigation:
    """Класс для навигации по ILS"""

    # Константы для интерпретации отклонений
    CDI_FULL_SCALE = 127  # Полное отклонение CDI
    CDI_DOTS = 5  # Количество точек на индикаторе (обычно 5)
    LOCALIZER_FULL_SCALE_DEGREES = 2.5  # Полное отклонение localizer (градусы)

    GSI_FULL_SCALE = 127  # Полное отклонение GSI
    GSI_DOTS = 5  # Количество точек на индикаторе
    GLIDESLOPE_FULL_SCALE_DEGREES = 0.7  # Полное отклонение глиссады (градусы)

    def __init__(self):
        self.config: Optional[ILSConfig] = None

    def configure(self, config: ILSConfig):
        """Настроить параметры ILS захода"""
        self.config = config
        logger.info(f"ILS configured: {config.frequency/1000000:.2f} MHz, "
                   f"Course: {config.localizer_course}°, "
                   f"Glideslope: {config.glideslope_angle}°")

    def is_ils_available(self, ils_data: Dict) -> bool:
        """
        Проверка доступности ILS сигнала

        Args:
            ils_data: Данные ILS из телеметрии

        Returns:
            True если ILS доступен
        """
        has_loc = ils_data.get('nav1_has_localizer', False)
        has_gs = ils_data.get('nav1_has_glideslope', False)

        return has_loc and has_gs

    def is_loc_available(self, ils_data: Dict) -> bool:
        """Проверка доступности LOC (localizer only, без glideslope).

        Args:
            ils_data: Данные из телеметрии

        Returns:
            True если localizer доступен
        """
        return ils_data.get('nav1_has_localizer', False)

    def get_localizer_deviation(self, ils_data: Dict) -> Dict[str, float]:
        """
        Получить отклонение от курса localizer

        Args:
            ils_data: Данные ILS из телеметрии

        Returns:
            Dict с отклонением в градусах и точках
        """
        cdi_raw = ils_data.get('nav1_cdi', 0)

        # Преобразование в градусы
        # CDI: -127 (полное отклонение влево) до +127 (вправо)
        deviation_degrees = (cdi_raw / self.CDI_FULL_SCALE) * self.LOCALIZER_FULL_SCALE_DEGREES

        # Преобразование в точки индикатора
        deviation_dots = (cdi_raw / self.CDI_FULL_SCALE) * self.CDI_DOTS

        return {
            'raw': cdi_raw,
            'degrees': deviation_degrees,
            'dots': deviation_dots,
            'on_course': abs(deviation_dots) < 0.5  # В пределах половины точки
        }

    def get_glideslope_deviation(self, ils_data: Dict) -> Dict[str, float]:
        """
        Получить отклонение от глиссады

        Args:
            ils_data: Данные ILS из телеметрии

        Returns:
            Dict с отклонением в градусах и точках
        """
        gsi_raw = ils_data.get('nav1_gsi', 0)

        # Преобразование в градусы
        # GSI: -127 (ниже глиссады) до +127 (выше глиссады)
        deviation_degrees = (gsi_raw / self.GSI_FULL_SCALE) * self.GLIDESLOPE_FULL_SCALE_DEGREES

        # Преобразование в точки индикатора
        deviation_dots = (gsi_raw / self.GSI_FULL_SCALE) * self.GSI_DOTS

        return {
            'raw': gsi_raw,
            'degrees': deviation_degrees,
            'dots': deviation_dots,
            'on_glideslope': abs(deviation_dots) < 0.5  # В пределах половины точки
        }

    def calculate_ils_approach(self, telemetry: Dict, ils_data: Dict) -> Dict[str, any]:
        """
        Расчёт параметров ILS захода

        Args:
            telemetry: Телеметрия самолёта
            ils_data: Данные ILS

        Returns:
            Dict с параметрами захода
        """
        if not self.config:
            logger.error("ILS not configured")
            return {}

        # Проверка доступности ILS
        ils_available = self.is_ils_available(ils_data)

        if not ils_available:
            return {
                'ils_available': False,
                'error': 'ILS signal not available'
            }

        # Отклонения
        loc_dev = self.get_localizer_deviation(ils_data)
        gs_dev = self.get_glideslope_deviation(ils_data)

        # Текущие параметры
        altitude = telemetry['position'].get('altitude', 0)
        ground_speed = telemetry['speed'].get('ground_speed', 0)

        # Расчёт требуемой высоты на глиссаде
        dme_distance = telemetry['nav'].get('nav1_dme_distance', 0)
        if dme_distance > 0:
            distance_feet = dme_distance * 6076.12
            required_altitude_agl = distance_feet * math.tan(math.radians(self.config.glideslope_angle))
            required_altitude_msl = required_altitude_agl + self.config.runway_elevation
        else:
            required_altitude_msl = altitude

        # Расчёт вертикальной скорости для глиссады
        required_vs = ground_speed * math.tan(math.radians(self.config.glideslope_angle)) * 101.3

        # Расчёт корректирующего курса
        heading_correction = -loc_dev['degrees'] * 3  # Коэффициент усиления
        corrected_heading = (self.config.localizer_course + heading_correction) % 360

        return {
            'ils_available': True,
            'localizer': loc_dev,
            'glideslope': gs_dev,
            'dme_distance': dme_distance,
            'required_altitude': required_altitude_msl,
            'altitude_deviation': altitude - required_altitude_msl,
            'required_vs': required_vs,
            'corrected_heading': corrected_heading,
            'on_localizer': loc_dev['on_course'],
            'on_glideslope': gs_dev['on_glideslope'],
            'stabilized': loc_dev['on_course'] and gs_dev['on_glideslope']
        }

    def calculate_loc_approach(self, telemetry: Dict, ils_data: Dict) -> Dict[str, any]:
        """Расчёт параметров LOC захода (localizer only, без glideslope).

        Lateral: реальный localizer signal (NAV1 CDI).
        Vertical: synthetic glidepath (handled by SyntheticGlidepath module).
        Stabilized = only on_localizer (no glideslope check).

        Args:
            telemetry: Телеметрия самолёта
            ils_data: Данные из телеметрии (localizer signal)

        Returns:
            Dict с параметрами захода
        """
        if not self.config:
            logger.error("LOC not configured (no ILSConfig)")
            return {}

        if not self.is_loc_available(ils_data):
            return {
                'loc_available': False,
                'error': 'Localizer signal not available'
            }

        loc_dev = self.get_localizer_deviation(ils_data)

        heading_correction = -loc_dev['degrees'] * 3
        corrected_heading = (self.config.localizer_course + heading_correction) % 360

        return {
            'loc_available': True,
            'localizer': loc_dev,
            'corrected_heading': corrected_heading,
            'on_localizer': loc_dev['on_course'],
            'stabilized': loc_dev['on_course'],
        }

    def get_approach_guidance(self, approach_data: Dict) -> Dict[str, str]:
        """
        Получить текстовые рекомендации по заходу

        Args:
            approach_data: Данные захода из calculate_ils_approach

        Returns:
            Dict с рекомендациями
        """
        if not approach_data.get('ils_available'):
            return {'status': 'ILS NOT AVAILABLE'}

        loc = approach_data['localizer']
        gs = approach_data['glideslope']

        guidance = {}

        # Курс
        if abs(loc['dots']) < 0.5:
            guidance['lateral'] = "ON LOCALIZER"
        elif loc['dots'] > 0:
            guidance['lateral'] = f"RIGHT OF COURSE ({loc['dots']:.1f} dots) - FLY LEFT"
        else:
            guidance['lateral'] = f"LEFT OF COURSE ({abs(loc['dots']):.1f} dots) - FLY RIGHT"

        # Глиссада
        if abs(gs['dots']) < 0.5:
            guidance['vertical'] = "ON GLIDESLOPE"
        elif gs['dots'] > 0:
            guidance['vertical'] = f"ABOVE GLIDESLOPE ({gs['dots']:.1f} dots) - DESCEND"
        else:
            guidance['vertical'] = f"BELOW GLIDESLOPE ({abs(gs['dots']):.1f} dots) - CLIMB"

        # Общий статус
        if approach_data['stabilized']:
            guidance['status'] = "STABILIZED"
        else:
            guidance['status'] = "NOT STABILIZED"

        return guidance

    def calculate_glideslope_angle_from_geometry(self, altitude_agl: float,
                                                 distance_nm: float) -> float:
        """
        Расчёт фактического угла глиссады из геометрии

        Args:
            altitude_agl: Высота над землёй (футы)
            distance_nm: Расстояние до порога (морские мили)

        Returns:
            Угол глиссады (градусы)
        """
        if distance_nm <= 0:
            return 0.0

        distance_feet = distance_nm * 6076.12
        angle_rad = math.atan(altitude_agl / distance_feet)
        angle_deg = math.degrees(angle_rad)

        return angle_deg
