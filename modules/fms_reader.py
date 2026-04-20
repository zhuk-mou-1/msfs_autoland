"""
Модуль чтения данных FMS (Flight Management System) из MSFS
Считывает маршрутные точки STAR и схемы захода
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Waypoint:
    """Маршрутная точка"""
    index: int
    id: str
    latitude: float
    longitude: float
    altitude: float  # футы
    distance: float  # морские мили от текущей позиции
    ete: float  # estimated time enroute (секунды)
    is_current: bool = False


class FMSReader:
    """Класс для чтения данных FMS из MSFS"""

    def __init__(self, telemetry):
        """
        Args:
            telemetry: Экземпляр MSFSTelemetry
        """
        self.telemetry = telemetry
        self.aq = telemetry.aq

    def get_gps_destination(self) -> Dict[str, any]:
        """Получить пункт назначения из GPS"""
        if not self.telemetry.connected:
            return {}

        try:
            return {
                'latitude': self.aq.get("GPS_WP_NEXT_LAT"),
                'longitude': self.aq.get("GPS_WP_NEXT_LON"),
                'altitude': self.aq.get("GPS_WP_NEXT_ALT"),  # футы
                'id': self.aq.get("GPS_WP_NEXT_ID"),
                'distance': self.aq.get("GPS_WP_DISTANCE"),  # метры
                'bearing': self.aq.get("GPS_WP_BEARING"),  # градусы
                'ete': self.aq.get("GPS_ETE"),  # секунды до следующей точки
            }
        except Exception as e:
            logger.error("Error getting GPS destination: %s", e)
            return {}

    def get_flight_plan_info(self) -> Dict[str, any]:
        """Получить общую информацию о плане полёта"""
        if not self.telemetry.connected:
            return {}

        try:
            return {
                'wp_count': int(self.aq.get("GPS_FLIGHT_PLAN_WP_COUNT")),
                'wp_index': int(self.aq.get("GPS_FLIGHT_PLAN_WP_INDEX")),
                'is_active_plan': bool(self.aq.get("GPS_IS_ACTIVE_FLIGHT_PLAN")),
                'is_active_way_point': bool(self.aq.get("GPS_IS_ACTIVE_WAY_POINT")),
                'is_arrived': bool(self.aq.get("GPS_IS_ARRIVED")),
                'is_directto_flightplan': bool(self.aq.get("GPS_IS_DIRECTTO_FLIGHTPLAN")),
            }
        except Exception as e:
            logger.error("Error getting flight plan info: %s", e)
            return {}

    def get_waypoint_by_index(self, index: int) -> Optional[Waypoint]:
        """
        Получить маршрутную точку по индексу

        Args:
            index: Индекс точки в плане полёта (0-based)

        Returns:
            Waypoint или None если ошибка
        """
        if not self.telemetry.connected:
            return None

        try:
            # SimConnect использует 1-based индексацию для waypoints
            # simconnect_index = index + 1  # Currently unused

            wp_id = self.aq.get("GPS_WP_PREV_ID")  # Для текущей точки
            if index > 0:
                # Для других точек используем общий запрос
                # Примечание: SimConnect не предоставляет прямой доступ к произвольным точкам
                # Можно получить только PREV, NEXT и несколько других
                logger.warning("Direct access to waypoint %s not available via SimConnect", index)
                return None

            lat = self.aq.get("GPS_WP_PREV_LAT")
            lon = self.aq.get("GPS_WP_PREV_LON")
            alt = self.aq.get("GPS_WP_PREV_ALT")
            distance = self.aq.get("GPS_WP_DISTANCE")
            ete = self.aq.get("GPS_ETE")

            return Waypoint(
                index=index,
                id=wp_id,
                latitude=lat,
                longitude=lon,
                altitude=alt,
                distance=distance / 1852.0,  # метры в морские мили
                ete=ete,
                is_current=False
            )

        except Exception as e:
            logger.error("Error getting waypoint %s: %s", index, e)
            return None

    def get_current_waypoint(self) -> Optional[Waypoint]:
        """Получить текущую активную маршрутную точку"""
        if not self.telemetry.connected:
            return None

        try:
            plan_info = self.get_flight_plan_info()
            if not plan_info.get('is_active_plan'):
                logger.warning("No active flight plan")
                return None

            current_index = plan_info.get('wp_index', 0)

            wp_id = self.aq.get("GPS_WP_NEXT_ID")
            lat = self.aq.get("GPS_WP_NEXT_LAT")
            lon = self.aq.get("GPS_WP_NEXT_LON")
            alt = self.aq.get("GPS_WP_NEXT_ALT")
            distance = self.aq.get("GPS_WP_DISTANCE")
            ete = self.aq.get("GPS_ETE")

            return Waypoint(
                index=current_index,
                id=wp_id,
                latitude=lat,
                longitude=lon,
                altitude=alt,
                distance=distance / 1852.0,  # метры в морские мили
                ete=ete,
                is_current=True
            )

        except Exception as e:
            logger.error("Error getting current waypoint: %s", e)
            return None

    def get_previous_waypoint(self) -> Optional[Waypoint]:
        """Получить предыдущую пройденную маршрутную точку"""
        if not self.telemetry.connected:
            return None

        try:
            plan_info = self.get_flight_plan_info()
            if not plan_info.get('is_active_plan'):
                return None

            current_index = plan_info.get('wp_index', 0)
            if current_index == 0:
                return None  # Нет предыдущей точки

            prev_index = current_index - 1

            wp_id = self.aq.get("GPS_WP_PREV_ID")
            lat = self.aq.get("GPS_WP_PREV_LAT")
            lon = self.aq.get("GPS_WP_PREV_LON")
            alt = self.aq.get("GPS_WP_PREV_ALT")

            return Waypoint(
                index=prev_index,
                id=wp_id,
                latitude=lat,
                longitude=lon,
                altitude=alt,
                distance=0.0,  # Уже пройдена
                ete=0.0,
                is_current=False
            )

        except Exception as e:
            logger.error("Error getting previous waypoint: %s", e)
            return None

    def get_star_waypoints(self) -> List[Waypoint]:
        """
        Получить все маршрутные точки STAR (Standard Terminal Arrival Route)

        Примечание: SimConnect не предоставляет прямой доступ ко всем точкам плана.
        Возвращает доступные точки: предыдущую, текущую и следующую.

        Returns:
            Список доступных waypoints
        """
        waypoints = []

        try:
            plan_info = self.get_flight_plan_info()
            if not plan_info.get('is_active_plan'):
                logger.warning("No active flight plan for STAR")
                return waypoints

            total_waypoints = plan_info.get('wp_count', 0)
            current_index = plan_info.get('wp_index', 0)

            logger.info("Flight plan: %s/%s waypoints", current_index + 1, total_waypoints)

            # Получаем предыдущую точку
            prev_wp = self.get_previous_waypoint()
            if prev_wp:
                waypoints.append(prev_wp)
                logger.debug("Previous WP: %s at %s, %s", prev_wp.id, prev_wp.latitude, prev_wp.longitude)

            # Получаем текущую точку
            current_wp = self.get_current_waypoint()
            if current_wp:
                waypoints.append(current_wp)
                logger.info(f"Current WP: {current_wp.id} at {current_wp.latitude:.4f}, {current_wp.longitude:.4f}, "
                           f"distance: {current_wp.distance:.1f}nm, ETE: {current_wp.ete/60:.1f}min")

            # Примечание: SimConnect не предоставляет доступ к следующим точкам после NEXT
            # Для полного списка STAR потребуется парсинг файлов навигационной базы данных

            logger.info("Retrieved %s waypoints from FMS", len(waypoints))

        except Exception as e:
            logger.error("Error getting STAR waypoints: %s", e)

        return waypoints

    def get_approach_waypoints(self) -> List[Waypoint]:
        """
        Получить маршрутные точки схемы захода (включая FINAL)

        Возвращает те же точки что и get_star_waypoints, так как SimConnect
        не различает STAR и подход на уровне API.
        """
        return self.get_star_waypoints()

    def get_fms_status(self) -> Dict[str, any]:
        """Получить полный статус FMS"""
        try:
            plan_info = self.get_flight_plan_info()
            current_wp = self.get_current_waypoint()

            return {
                'has_active_plan': plan_info.get('is_active_plan', False),
                'total_waypoints': plan_info.get('wp_count', 0),
                'current_waypoint_index': plan_info.get('wp_index', 0),
                'current_waypoint': current_wp.id if current_wp else None,
                'distance_to_next': current_wp.distance if current_wp else 0.0,
                'ete_to_next': current_wp.ete if current_wp else 0.0,
                'is_arrived': plan_info.get('is_arrived', False),
            }
        except Exception as e:
            logger.error("Error getting FMS status: %s", e)
            return {}

    def is_on_star_approach(self) -> bool:
        """
        Проверить, находится ли самолёт на схеме STAR/подхода

        Returns:
            True если активен план полёта и самолёт следует по нему
        """
        try:
            plan_info = self.get_flight_plan_info()
            return (plan_info.get('is_active_plan', False) and
                   plan_info.get('is_active_way_point', False) and
                   not plan_info.get('is_arrived', False))
        except Exception:
            return False
