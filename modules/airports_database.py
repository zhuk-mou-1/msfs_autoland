"""
Модуль для работы с базой данных аэропортов и заходов
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from modules.ils_navigation import ILSConfig
from modules.types import ApproachConfig, NavStation

logger = logging.getLogger(__name__)


@dataclass
class RunwayInfo:
    """Информация о ВПП"""
    name: str
    heading: int
    length: int
    width: int
    threshold_lat: float
    threshold_lon: float


@dataclass
class AirportInfo:
    """Информация об аэропорте"""
    icao: str
    name: str
    city: str
    country: str
    elevation: int
    runways: List[RunwayInfo]


class AirportsDatabase:
    """Класс для работы с базой данных аэропортов"""

    def __init__(self, db_path: str = "config/airports_database.json"):
        self.db_path = Path(db_path)
        self.data: Dict = {}
        self.load_database()

    def load_database(self) -> bool:
        """Загрузить базу данных из файла"""
        try:
            if not self.db_path.exists():
                logger.error("Database file not found: %s", self.db_path)
                return False

            with open(self.db_path, encoding='utf-8') as f:
                self.data = json.load(f)

            logger.info("Loaded %s airports from database", len(self.data.get('airports', {})))
            return True

        except Exception as e:
            logger.error("Error loading database: %s", e)
            return False

    def get_airport_list(self) -> List[str]:
        """Получить список ICAO кодов всех аэропортов"""
        return list(self.data.get('airports', {}).keys())

    def get_airport_info(self, icao: str) -> Optional[AirportInfo]:
        """
        Получить информацию об аэропорте

        Args:
            icao: ICAO код аэропорта (например, 'UUEE')

        Returns:
            AirportInfo или None если не найден
        """
        airports = self.data.get('airports', {})
        airport_data = airports.get(icao.upper())

        if not airport_data:
            logger.warning("Airport %s not found in database", icao)
            return None

        # Парсинг ВПП
        runways = []
        for rwy_name, rwy_data in airport_data.get('runways', {}).items():
            runways.append(RunwayInfo(
                name=rwy_name,
                heading=rwy_data['heading'],
                length=rwy_data['length'],
                width=rwy_data['width'],
                threshold_lat=rwy_data['threshold_lat'],
                threshold_lon=rwy_data['threshold_lon']
            ))

        return AirportInfo(
            icao=icao.upper(),
            name=airport_data['name'],
            city=airport_data['city'],
            country=airport_data['country'],
            elevation=airport_data['elevation'],
            runways=runways
        )

    def get_runway_list(self, icao: str) -> List[str]:
        """Получить список ВПП аэропорта"""
        airports = self.data.get('airports', {})
        airport_data = airports.get(icao.upper())

        if not airport_data:
            return []

        return list(airport_data.get('runways', {}).keys())

    def get_approach_list(self, icao: str, runway: str) -> List[str]:
        """Получить список заходов для ВПП"""
        airports = self.data.get('airports', {})
        airport_data = airports.get(icao.upper())

        if not airport_data:
            return []

        runway_data = airport_data.get('runways', {}).get(runway)
        if not runway_data:
            return []

        return list(runway_data.get('approaches', {}).keys())

    def get_approach_config(self, icao: str, runway: str, approach_type: str) -> Optional[ApproachConfig]:
        """
        Получить конфигурацию захода

        Args:
            icao: ICAO код аэропорта
            runway: Название ВПП (например, '07C')
            approach_type: Тип захода ('ILS', 'VOR', 'NDB')

        Returns:
            ApproachConfig или None
        """
        airports = self.data.get('airports', {})
        airport_data = airports.get(icao.upper())

        if not airport_data:
            logger.error("Airport %s not found", icao)
            return None

        runway_data = airport_data.get('runways', {}).get(runway)
        if not runway_data:
            logger.error("Runway %s not found at %s", runway, icao)
            return None

        approach_data = runway_data.get('approaches', {}).get(approach_type)
        if not approach_data:
            logger.error("Approach %s not found for %s %s", approach_type, icao, runway)
            return None

        # Создание NavStation
        if approach_data['type'] == 'VOR' or approach_data['type'] == 'NDB':
            station = NavStation(
                name=approach_data.get('station_name', f"{icao} {approach_data['type']}"),
                frequency=approach_data['frequency'],
                latitude=approach_data.get('station_lat', runway_data['threshold_lat']),
                longitude=approach_data.get('station_lon', runway_data['threshold_lon']),
                type=approach_data['type']
            )
        else:  # ILS
            station = NavStation(
                name=f"{icao} {runway} ILS",
                frequency=approach_data['frequency'],
                latitude=runway_data['threshold_lat'],
                longitude=runway_data['threshold_lon'],
                type='ILS'
            )

        # Создание ApproachConfig
        config = ApproachConfig(
            station=station,
            final_approach_course=approach_data['course'],
            glideslope_angle=approach_data['glideslope'],
            decision_height=approach_data['decision_height'],
            approach_speed=approach_data['approach_speed'],
            runway_elevation=airport_data['elevation'],
            runway_length=runway_data['length'],
            runway_width=runway_data['width'],
            runway_threshold_lat=runway_data['threshold_lat'],
            runway_threshold_lon=runway_data['threshold_lon']
        )

        logger.info("Loaded approach: %s %s %s", icao, runway, approach_type)
        return config

    def get_ils_config(self, icao: str, runway: str) -> Optional[ILSConfig]:
        """
        Получить конфигурацию ILS захода

        Args:
            icao: ICAO код аэропорта
            runway: Название ВПП

        Returns:
            ILSConfig или None
        """
        airports = self.data.get('airports', {})
        airport_data = airports.get(icao.upper())

        if not airport_data:
            return None

        runway_data = airport_data.get('runways', {}).get(runway)
        if not runway_data:
            return None

        approach_data = runway_data.get('approaches', {}).get('ILS')
        if not approach_data:
            return None

        config = ILSConfig(
            frequency=approach_data['frequency'],
            localizer_course=approach_data['course'],
            glideslope_angle=approach_data['glideslope'],
            decision_height=approach_data['decision_height'],
            approach_speed=approach_data['approach_speed'],
            runway_elevation=airport_data['elevation'],
            runway_length=runway_data['length'],
            runway_width=runway_data['width'],
            runway_threshold_lat=runway_data['threshold_lat'],
            runway_threshold_lon=runway_data['threshold_lon']
        )

        return config

    def search_airports(self, query: str) -> List[Dict[str, str]]:
        """
        Поиск аэропортов по названию, городу или ICAO коду

        Args:
            query: Поисковый запрос

        Returns:
            Список найденных аэропортов
        """
        query_lower = query.lower()
        results = []

        airports = self.data.get('airports', {})
        for icao, airport_data in airports.items():
            if (query_lower in icao.lower() or
                query_lower in airport_data['name'].lower() or
                query_lower in airport_data['city'].lower()):

                results.append({
                    'icao': icao,
                    'name': airport_data['name'],
                    'city': airport_data['city'],
                    'country': airport_data['country']
                })

        return results
