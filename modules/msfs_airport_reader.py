"""
Модуль для получения данных аэропортов из MSFS через SimConnect
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from modules.navigraph_parser import create_navigraph_parser

logger = logging.getLogger(__name__)


@dataclass
class MSFSAirportData:
    """Данные аэропорта из MSFS"""
    icao: str
    name: str
    latitude: float
    longitude: float
    elevation: float
    runways: List[Dict]
    ils_frequencies: List[Dict]


class MSFSAirportReader:
    """Класс для чтения данных аэропортов из MSFS"""

    def __init__(self, telemetry):
        """
        Args:
            telemetry: Экземпляр MSFSTelemetry с активным подключением
        """
        self.telemetry = telemetry
        self.aq = telemetry.aq

        # Инициализация Navigraph parser (опционально)
        self.navigraph_parser = create_navigraph_parser()
        if self.navigraph_parser:
            logger.info("Navigraph parser initialized successfully")
        else:
            logger.warning("Navigraph parser not available, will use fallback values")

    def get_nearest_airport(self) -> Optional[str]:
        """
        Получить ICAO код ближайшего аэропорта

        Returns:
            ICAO код или None
        """
        try:
            # SimConnect предоставляет информацию о ближайшем аэропорте
            icao = self.aq.get("GPS_WP_NEXT_ID")
            if icao:
                return icao.strip()
            return None
        except Exception as e:
            logger.error("Error getting nearest airport: %s", e)
            return None

    def get_destination_airport(self) -> Optional[str]:
        """
        Получить ICAO код аэропорта назначения из FMS

        Returns:
            ICAO код или None
        """
        try:
            # Получаем пункт назначения из GPS
            dest_icao = self.aq.get("GPS_WP_NEXT_ID")
            if dest_icao:
                return dest_icao.strip()
            return None
        except Exception as e:
            logger.error("Error getting destination airport: %s", e)
            return None

    def get_current_airport_info(self) -> Optional[Dict]:
        """
        Получить информацию о текущем аэропорте (где находится самолёт)

        Returns:
            Dict с информацией об аэропорте
        """
        try:
            # Получаем данные о текущей позиции
            lat = self.aq.get("PLANE_LATITUDE")
            lon = self.aq.get("PLANE_LONGITUDE")
            alt = self.aq.get("PLANE_ALTITUDE")

            # Проверяем, находимся ли мы на земле
            on_ground = self.aq.get("SIM_ON_GROUND")

            if on_ground:
                # Если на земле, можем получить данные аэропорта
                info = {
                    'latitude': lat,
                    'longitude': lon,
                    'altitude': alt,
                    'on_ground': bool(on_ground)
                }
                return info

            return None

        except Exception as e:
            logger.error("Error getting airport info: %s", e)
            return None

    def get_active_runway_info(self) -> Optional[Dict]:
        """
        Получить информацию об активной ВПП (если настроена в GPS/FMC)

        Returns:
            Dict с информацией о ВПП
        """
        try:
            # GPS данные о пункте назначения
            dest_lat = self.aq.get("GPS_WP_NEXT_LAT")
            dest_lon = self.aq.get("GPS_WP_NEXT_LON")
            dest_alt = self.aq.get("GPS_WP_NEXT_ALT")
            dest_id = self.aq.get("GPS_WP_NEXT_ID")

            if dest_lat and dest_lon:
                return {
                    'latitude': dest_lat,
                    'longitude': dest_lon,
                    'altitude': dest_alt,
                    'id': dest_id.strip() if dest_id else None
                }

            return None

        except Exception as e:
            logger.error("Error getting runway info: %s", e)
            return None

    def get_magnetic_variation(self) -> Optional[float]:
        """
        Получить магнитное склонение в текущей позиции

        Returns:
            Магнитное склонение в градусах или None
        """
        try:
            mag_var = self.aq.get("MAGVAR")
            if mag_var is not None:
                return mag_var
            return None
        except Exception as e:
            logger.error("Error getting magnetic variation: %s", e)
            return None

    def get_ils_frequency_from_nav(self) -> Optional[Tuple[float, int]]:
        """
        Получить частоту ILS из настроенного NAV радио

        Returns:
            Tuple (frequency_mhz, course) или None
        """
        try:
            # Проверяем NAV1
            has_localizer = bool(self.aq.get("NAV_HAS_LOCALIZER:1"))

            if has_localizer:
                freq_hz = self.aq.get("NAV_ACTIVE_FREQUENCY:1")
                course = self.aq.get("NAV_LOCALIZER:1")

                if freq_hz and course:
                    freq_mhz = freq_hz / 1000000.0
                    return (freq_mhz, int(course))

            return None

        except Exception as e:
            logger.error("Error getting ILS frequency: %s", e)
            return None

    def get_glideslope_info(self) -> Optional[Dict]:
        """
        Получить информацию о глиссаде ILS

        Returns:
            Dict с данными глиссады или None
        """
        try:
            has_glideslope = bool(self.aq.get("NAV_HAS_GLIDE_SLOPE:1"))

            if has_glideslope:
                gs_angle = self.aq.get("NAV_GLIDE_SLOPE_ANGLE:1")
                gs_error = self.aq.get("NAV_GSI:1")

                return {
                    'has_glideslope': True,
                    'angle': gs_angle if gs_angle else 3.0,
                    'error': gs_error
                }

            return None

        except Exception as e:
            logger.error("Error getting glideslope info: %s", e)
            return None

    def detect_approach_from_position(self) -> Optional[Dict]:
        """
        Определить параметры захода на основе текущей позиции и настроек

        Returns:
            Dict с параметрами захода
        """
        try:
            # Получаем текущую позицию
            lat = self.aq.get("PLANE_LATITUDE")
            lon = self.aq.get("PLANE_LONGITUDE")
            alt = self.aq.get("PLANE_ALTITUDE")
            heading = self.aq.get("PLANE_HEADING_DEGREES_MAGNETIC")

            # Проверяем ILS
            ils_data = self.get_ils_frequency_from_nav()

            # Проверяем GPS пункт назначения
            dest_data = self.get_active_runway_info()

            approach_info = {
                'current_position': {
                    'latitude': lat,
                    'longitude': lon,
                    'altitude': alt,
                    'heading': heading
                },
                'ils': None,
                'destination': None
            }

            if ils_data:
                freq_mhz, course = ils_data
                approach_info['ils'] = {
                    'frequency': int(freq_mhz * 1000000),  # Hz
                    'course': course,
                    'type': 'ILS'
                }
                logger.info("Detected ILS: %s MHz, Course: %s°", freq_mhz, course)

            if dest_data:
                approach_info['destination'] = dest_data
                logger.info("Destination: %s, %s", dest_data['latitude'], dest_data['longitude'])

            return approach_info

        except Exception as e:
            logger.error("Error detecting approach: %s", e)
            return None

    def auto_configure_approach(self) -> Optional[Dict]:
        """
        Автоматически настроить заход на основе данных из MSFS

        Returns:
            Dict с конфигурацией захода или None
        """
        logger.info("Auto-configuring approach from MSFS data...")

        approach_info = self.detect_approach_from_position()

        if not approach_info:
            logger.warning("Could not detect approach parameters from MSFS")
            return None

        # Получаем дополнительные данные
        mag_var = self.get_magnetic_variation()
        dest_airport = self.get_destination_airport()
        glideslope_info = self.get_glideslope_info()

        # Получаем информацию о пункте назначения из GPS
        gps_dest = self.telemetry.get_gps_destination()

        # Получаем информацию об активном заходе (DH, тип)
        approach_data = self.telemetry.get_approach_info()

        # Обновляем dest_airport и runway из GPS если доступно
        if gps_dest.get('airport_icao'):
            dest_airport = gps_dest['airport_icao']
        dest_runway = gps_dest.get('runway_id', '')

        # Если есть ILS
        if approach_info.get('ils'):
            ils = approach_info['ils']
            dest = approach_info.get('destination', {})

            # Получаем данные из Navigraph (длина/ширина ВПП, угол глиссады)
            nav_data = None
            data_source = "msfs"  # По умолчанию

            if self.navigraph_parser and dest_airport and dest_runway:
                nav_data = self.navigraph_parser.get_runway_data(dest_airport, dest_runway, 'ILS')
                if nav_data:
                    data_source = "navigraph"
                    logger.info(f"Navigraph data loaded for {dest_airport} RWY {dest_runway}")

            # Определяем угол глиссады с fallback логикой
            glideslope_angle = 3.0  # По умолчанию
            glideslope_source = "standard"

            if nav_data and nav_data.glideslope_angle:
                # Приоритет 1: Navigraph база данных
                glideslope_angle = nav_data.glideslope_angle
                glideslope_source = "navigraph"
            elif glideslope_info and glideslope_info.get('angle'):
                # Приоритет 2: MSFS (если есть)
                glideslope_angle = glideslope_info['angle']
                glideslope_source = "msfs"

            # Читаем Decision Height из MSFS (если доступен)
            decision_height = approach_data.get('decision_height')

            # Если DH не получен из MSFS, используем значение по умолчанию
            if not decision_height or decision_height <= 0:
                # Определяем категорию по наличию glideslope
                if approach_data.get('glideslope_valid'):
                    decision_height = 200  # CAT I по умолчанию
                else:
                    decision_height = 250  # Localizer only
                logger.info("Using default Decision Height: %s ft", decision_height)
            else:
                logger.info("Decision Height from MSFS: %s ft", decision_height)

            # Получаем превышение аэропорта
            runway_elevation = dest.get('altitude', 0)
            if nav_data and nav_data.airport_elevation:
                runway_elevation = nav_data.airport_elevation

            config = {
                'type': 'ILS',
                'frequency': ils['frequency'],
                'course': ils['course'],
                'glideslope': glideslope_angle,
                'decision_height': int(decision_height),
                'approach_speed': 140,
                'runway_threshold_lat': dest.get('latitude', 0),
                'runway_threshold_lon': dest.get('longitude', 0),
                'runway_elevation': runway_elevation,
                'airport_icao': dest_airport,
                'runway_id': dest_runway,
                'magnetic_variation': mag_var,
                # Добавляем данные из Navigraph
                'runway_length': nav_data.length if nav_data else None,
                'runway_width': nav_data.width if nav_data else None,
                # Метаданные об источниках данных
                'data_source': data_source,
                'glideslope_source': glideslope_source,
            }

            logger.info(f"Auto-configured ILS approach: {ils['frequency']/1000000:.2f} MHz, "
                       f"Glideslope: {glideslope_angle}° (source: {glideslope_source}), DH: {decision_height} ft")
            if dest_airport:
                logger.info("Destination: %s RWY %s (data source: %s)", dest_airport, dest_runway if dest_runway else 'N/A', data_source)
            return config

        # Если только GPS пункт назначения
        if approach_info.get('destination'):
            dest = approach_info['destination']

            # Получаем данные из Navigraph (длина/ширина ВПП)
            nav_data = None
            data_source = "msfs"

            if self.navigraph_parser and dest_airport and dest_runway:
                nav_data = self.navigraph_parser.get_runway_data(dest_airport, dest_runway, 'GPS')
                if nav_data:
                    data_source = "navigraph"
                    logger.info(f"Navigraph data loaded for {dest_airport} RWY {dest_runway}")

            # Для GPS заходов используем MDA вместо DH
            minimum_descent_altitude = approach_data.get('minimum_descent_altitude')
            if not minimum_descent_altitude or minimum_descent_altitude <= 0:
                minimum_descent_altitude = 400  # По умолчанию для GPS
                logger.info("Using default MDA: %s ft", minimum_descent_altitude)
            else:
                logger.info("MDA from MSFS: %s ft", minimum_descent_altitude)

            # Угол глиссады для GPS: стандарт 3.0°
            glideslope_angle = 3.0
            glideslope_source = "standard"

            # Получаем превышение аэропорта
            runway_elevation = dest['altitude']
            if nav_data and nav_data.airport_elevation:
                runway_elevation = nav_data.airport_elevation

            config = {
                'type': 'GPS',
                'glideslope': glideslope_angle,
                'decision_height': int(minimum_descent_altitude),  # Для совместимости используем DH
                'approach_speed': 120,
                'runway_threshold_lat': dest['latitude'],
                'runway_threshold_lon': dest['longitude'],
                'runway_elevation': runway_elevation,
                'airport_icao': dest_airport,
                'runway_id': dest_runway,
                'magnetic_variation': mag_var,
                # Добавляем данные из Navigraph
                'runway_length': nav_data.length if nav_data else None,
                'runway_width': nav_data.width if nav_data else None,
                # Метаданные об источниках данных
                'data_source': data_source,
                'glideslope_source': glideslope_source,
            }

            logger.info("Auto-configured GPS approach")
            if dest_airport:
                logger.info("Destination: %s RWY %s (data source: %s)", dest_airport, dest_runway if dest_runway else 'N/A', data_source)
            return config

        logger.warning("No approach data available in MSFS")
        return None


def create_approach_config_from_msfs(telemetry) -> Optional[Dict]:
    """
    Удобная функция для создания конфигурации захода из MSFS

    Args:
        telemetry: Экземпляр MSFSTelemetry

    Returns:
        Dict с конфигурацией или None
    """
    reader = MSFSAirportReader(telemetry)
    return reader.auto_configure_approach()
