"""
Модуль навигации для расчёта заходов по VOR и NDB
"""

import logging
import math
from typing import Dict

from modules.types import ApproachConfig, BeaconCheckResult, RunwayBeacon

logger = logging.getLogger(__name__)


class Navigation:
    """Класс для расчёта навигации и заходов"""

    @staticmethod
    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Расчёт расстояния между двумя точками (в морских милях)"""
        R = 3440.065  # Радиус Земли в морских милях

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
        c = 2 * math.asin(math.sqrt(a))

        return R * c

    @staticmethod
    def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Расчёт пеленга от точки 1 к точке 2 (в градусах)"""
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lon = math.radians(lon2 - lon1)

        x = math.sin(delta_lon) * math.cos(lat2_rad)
        y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)

        bearing = math.degrees(math.atan2(x, y))
        return (bearing + 360) % 360

    @staticmethod
    def normalize_angle(angle: float) -> float:
        """Нормализация угла к диапазону 0-360"""
        return angle % 360

    @staticmethod
    def angle_difference(angle1: float, angle2: float) -> float:
        """Разница между двумя углами (-180 до +180)"""
        diff = angle2 - angle1
        while diff > 180:
            diff -= 360
        while diff < -180:
            diff += 360
        return diff

    def calculate_intercept_heading(self, current_heading: float, target_radial: float,
                                   cross_track_error: float) -> float:
        """
        Расчёт курса для перехвата радиала

        Args:
            current_heading: Текущий курс самолёта
            target_radial: Целевой радиал
            cross_track_error: Боковое отклонение (градусы, + = справа)

        Returns:
            Рекомендуемый курс
        """
        # Угол перехвата зависит от бокового отклонения
        intercept_angle = min(45, abs(cross_track_error) * 3)

        if cross_track_error > 0:
            # Отклонились вправо, нужно лететь левее
            return self.normalize_angle(target_radial - intercept_angle)
        else:
            # Отклонились влево, нужно лететь правее
            return self.normalize_angle(target_radial + intercept_angle)

    def calculate_descent_rate(self, ground_speed: float, glideslope_angle: float) -> int:
        """
        Расчёт вертикальной скорости для глиссады

        Args:
            ground_speed: Путевая скорость (узлы)
            glideslope_angle: Угол глиссады (градусы)

        Returns:
            Вертикальная скорость (футы/мин)
        """
        # VS = GS * tan(angle) * 101.3
        vs = ground_speed * math.tan(math.radians(glideslope_angle)) * 101.3
        return int(vs)

    def calculate_required_altitude(self, distance_to_threshold: float,
                                   glideslope_angle: float,
                                   runway_elevation: int) -> int:
        """
        Расчёт требуемой высоты на глиссаде

        Args:
            distance_to_threshold: Расстояние до порога ВПП (морские мили)
            glideslope_angle: Угол глиссады (градусы)
            runway_elevation: Превышение ВПП (футы)

        Returns:
            Требуемая высота (футы MSL)
        """
        distance_feet = distance_to_threshold * 6076.12  # морские мили в футы
        altitude_agl = distance_feet * math.tan(math.radians(glideslope_angle))
        return int(altitude_agl + runway_elevation)

    def is_on_final_approach_course(self, current_heading: float,
                                    final_course: int,
                                    tolerance: float = 5.0) -> bool:
        """Проверка, находится ли самолёт на курсе посадки"""
        diff = abs(self.angle_difference(current_heading, final_course))
        return diff <= tolerance

    def calculate_vor_approach(self, aircraft_pos: Dict, nav_data: Dict,
                              config: ApproachConfig) -> Dict:
        """
        Расчёт параметров захода по VOR

        Returns:
            Dict с рекомендациями по управлению
        """
        # Расстояние до станции
        distance = self.calculate_distance(
            aircraft_pos['latitude'],
            aircraft_pos['longitude'],
            config.station.latitude,
            config.station.longitude
        )

        # Пеленг на станцию
        bearing_to_station = self.calculate_bearing(
            aircraft_pos['latitude'],
            aircraft_pos['longitude'],
            config.station.latitude,
            config.station.longitude
        )

        # Текущий радиал (обратный пеленг)
        current_radial = self.normalize_angle(bearing_to_station + 180)

        # Боковое отклонение от курса
        cross_track_error = self.angle_difference(current_radial, config.final_approach_course)

        # Требуемая высота на глиссаде
        required_altitude = self.calculate_required_altitude(
            distance,
            config.glideslope_angle,
            config.runway_elevation
        )

        return {
            'distance_to_station': distance,
            'bearing_to_station': bearing_to_station,
            'current_radial': current_radial,
            'cross_track_error': cross_track_error,
            'required_altitude': required_altitude,
            'recommended_heading': self.calculate_intercept_heading(
                aircraft_pos.get('heading_magnetic', 0),
                config.final_approach_course,
                cross_track_error
            ),
            'on_course': abs(cross_track_error) < 2.0,
        }

    def calculate_ndb_approach(self, aircraft_pos: Dict, nav_data: Dict,
                              config: ApproachConfig) -> Dict:
        """
        Расчёт параметров захода по NDB
        Аналогично VOR, но используется ADF
        """
        return self.calculate_vor_approach(aircraft_pos, nav_data, config)

    def calculate_landing_distance(self, ground_speed: float, weight_lbs: float = 5000,
                                   headwind: float = 0, runway_condition: str = 'dry') -> float:
        """
        Расчёт требуемой посадочной дистанции

        Args:
            ground_speed: Путевая скорость при касании (узлы)
            weight_lbs: Вес самолёта (фунты)
            headwind: Встречный ветер (узлы, положительный = встречный)
            runway_condition: Состояние ВПП ('dry', 'wet', 'icy')

        Returns:
            Требуемая дистанция (футы)
        """
        # Базовая формула: дистанция = (скорость^2) / (2 * замедление)
        # Упрощённый расчёт для лёгких самолётов

        # Коэффициенты состояния ВПП
        condition_factors = {
            'dry': 1.0,
            'wet': 1.3,
            'icy': 2.0
        }
        factor = condition_factors.get(runway_condition, 1.0)

        # Базовая дистанция (эмпирическая формула)
        # Примерно 1000 футов на 60 узлов для лёгкого самолёта
        base_distance = (ground_speed / 60.0) ** 2 * 1000

        # Коррекция на ветер (встречный ветер уменьшает дистанцию)
        wind_factor = 1.0 - (headwind / ground_speed * 0.3)
        wind_factor = max(0.5, min(1.5, wind_factor))

        # Коррекция на вес (больше вес = больше дистанция)
        weight_factor = weight_lbs / 5000.0

        total_distance = base_distance * factor * wind_factor * weight_factor

        logger.debug(f"Landing distance: {total_distance:.0f}ft "
                    f"(GS: {ground_speed}kt, Wind: {headwind}kt, "
                    f"Condition: {runway_condition})")

        return total_distance

    def check_runway_length(self, required_distance: float, runway_length: int,
                           safety_margin: float = 1.5) -> Dict[str, any]:
        """
        Проверка достаточности длины ВПП

        Args:
            required_distance: Требуемая посадочная дистанция (футы)
            runway_length: Длина ВПП (футы)
            safety_margin: Коэффициент запаса (1.5 = 50% запас)

        Returns:
            Dict с результатами проверки
        """
        required_with_margin = required_distance * safety_margin
        is_sufficient = runway_length >= required_with_margin
        remaining = runway_length - required_with_margin

        status = "OK" if is_sufficient else "WARNING"
        if remaining < 0:
            status = "CRITICAL"

        return {
            'is_sufficient': is_sufficient,
            'required_distance': required_distance,
            'required_with_margin': required_with_margin,
            'runway_length': runway_length,
            'remaining': remaining,
            'status': status,
            'margin_percent': (remaining / runway_length * 100) if runway_length > 0 else 0
        }

    def calculate_distance_to_threshold(self, aircraft_lat: float, aircraft_lon: float,
                                       config: ApproachConfig) -> float:
        """
        Расчёт расстояния до порога ВПП

        Args:
            aircraft_lat: Широта самолёта
            aircraft_lon: Долгота самолёта
            config: Конфигурация захода

        Returns:
            Расстояние до порога (морские мили)
        """
        return self.calculate_distance(
            aircraft_lat,
            aircraft_lon,
            config.runway_threshold_lat,
            config.runway_threshold_lon
        )

    def calculate_glideslope_distance(self, altitude_above_threshold: float,
                                     glideslope_angle: float) -> float:
        """
        Расчёт расстояния по глиссаде для заданной высоты и угла

        Формулы для разных углов глиссады:
        - 3.0° → 300 футов на милю (упрощённая)
        - 3.5° → 350 футов на милю
        - 4.0° → 400 футов на милю
        - 5.0° → 500 футов на милю

        Args:
            altitude_above_threshold: Высота над порогом ВПП (футы)
            glideslope_angle: Угол глиссады (градусы)

        Returns:
            Расстояние до порога ВПП (морские мили)
        """
        if glideslope_angle <= 0:
            logger.error("Invalid glideslope angle: %s", glideslope_angle)
            return 0.0

        # Точная формула через тангенс
        # distance_feet = altitude / tan(angle)
        # distance_nm = distance_feet / 6076.12

        angle_rad = math.radians(glideslope_angle)
        distance_feet = altitude_above_threshold / math.tan(angle_rad)
        distance_nm = distance_feet / 6076.12

        return distance_nm

    def calculate_glideslope_intercept_point(self,
                                            runway_threshold_lat: float,
                                            runway_threshold_lon: float,
                                            runway_heading: float,
                                            runway_elevation: float,
                                            glideslope_angle: float = 3.0,
                                            intercept_altitude_agl: float = 2000.0) -> Dict[str, any]:
        """
        Вычислить координаты точки входа в глиссаду

        Поддерживает стандартные и нестандартные углы глиссады:
        - 3.0° - стандарт ICAO (большинство аэропортов)
        - 3.5° - повышенный угол (некоторые аэропорты с препятствиями)
        - 4.0°-5.0° - крутая глиссада (горные аэропорты, шумоподавление)
        - 5.5°+ - очень крутая (London City, Lugano и др.)

        Args:
            runway_threshold_lat: Широта порога ВПП
            runway_threshold_lon: Долгота порога ВПП
            runway_heading: Курс ВПП (градусы)
            runway_elevation: Высота ВПП (футы MSL)
            glideslope_angle: Угол глиссады (градусы, обычно 3.0)
            intercept_altitude_agl: Высота входа в глиссаду (футы AGL)

        Returns:
            Dict с координатами точки входа, расстоянием и параметрами
        """
        # Расстояние до точки входа
        distance_nm = self.calculate_glideslope_distance(
            intercept_altitude_agl,
            glideslope_angle
        )

        # Обратный курс (от порога к точке входа)
        reverse_heading = (runway_heading + 180) % 360

        # Вычисление координат точки входа
        # 1 морская миля = 1/60 градуса широты
        lat_change = distance_nm * math.cos(math.radians(reverse_heading)) / 60.0
        lon_change = distance_nm * math.sin(math.radians(reverse_heading)) / \
                     (60.0 * math.cos(math.radians(runway_threshold_lat)))

        intercept_lat = runway_threshold_lat + lat_change
        intercept_lon = runway_threshold_lon + lon_change

        # Расчёт требуемой вертикальной скорости (для справки)
        # VS = Ground Speed * tan(glideslope_angle) * 101.3
        # Для 120 узлов и 3° = ~630 fpm
        # Для 120 узлов и 5° = ~1050 fpm

        return {
            'latitude': intercept_lat,
            'longitude': intercept_lon,
            'distance_from_threshold_nm': distance_nm,
            'altitude_agl': intercept_altitude_agl,
            'altitude_msl': intercept_altitude_agl + runway_elevation,
            'glideslope_angle': glideslope_angle,
            'runway_heading': runway_heading,
            'feet_per_nm': intercept_altitude_agl / distance_nm if distance_nm > 0 else 0
        }

    def should_start_descent(self,
                            current_lat: float,
                            current_lon: float,
                            current_altitude_agl: float,
                            intercept_point: Dict[str, any],
                            tolerance_nm: float = 0.5) -> Dict[str, any]:
        """
        Определить нужно ли начинать снижение по глиссаде

        Args:
            current_lat: Текущая широта
            current_lon: Текущая долгота
            current_altitude_agl: Текущая высота над землёй (футы)
            intercept_point: Точка входа в глиссаду (из calculate_glideslope_intercept_point)
            tolerance_nm: Допуск расстояния (морские мили)

        Returns:
            Dict с решением и параметрами
        """
        # Расстояние до точки входа
        distance_to_intercept = self.calculate_distance(
            current_lat, current_lon,
            intercept_point['latitude'], intercept_point['longitude']
        )

        # Идеальная высота для текущей позиции на глиссаде
        glideslope_angle = intercept_point['glideslope_angle']
        ideal_altitude = self.calculate_glideslope_distance(
            distance_to_intercept * (intercept_point['feet_per_nm']),
            glideslope_angle
        ) * intercept_point['feet_per_nm']

        # Или проще: пропорционально расстоянию
        if distance_to_intercept <= intercept_point['distance_from_threshold_nm']:
            # Находимся между точкой входа и порогом
            ideal_altitude = distance_to_intercept * intercept_point['feet_per_nm']
        else:
            # Ещё не достигли точки входа
            ideal_altitude = intercept_point['altitude_agl']

        # Разница высот
        altitude_error = current_altitude_agl - ideal_altitude

        # Вертикальное отклонение в точках (dots)
        # 1 dot = 0.35° для ILS glideslope
        # Full scale = ±2.5 dots = ±0.7°
        vertical_deviation_dots = 0.0
        if distance_to_intercept > 0.1:  # Избегаем деления на ноль
            actual_angle = math.degrees(math.atan(current_altitude_agl / (distance_to_intercept * 6076.12)))
            angle_error = actual_angle - glideslope_angle
            vertical_deviation_dots = angle_error / 0.35

        # Решение о начале снижения
        should_descend = False
        reason = ""
        status = "OK"

        if distance_to_intercept <= tolerance_nm:
            # Достигли точки входа
            should_descend = True
            reason = f"Reached glideslope intercept point ({distance_to_intercept:.1f} NM)"
            status = "INTERCEPT"
        elif altitude_error > 300:
            # Слишком высоко для текущей позиции
            should_descend = True
            reason = f"Too high by {altitude_error:.0f} ft - start early descent"
            status = "HIGH"
        elif altitude_error < -300:
            # Слишком низко - опасно!
            should_descend = False
            reason = f"Too low by {abs(altitude_error):.0f} ft - MAINTAIN or CLIMB"
            status = "LOW"
        elif abs(altitude_error) <= 200:
            # В пределах нормы
            should_descend = (distance_to_intercept <= tolerance_nm)
            reason = "On profile"
            status = "ON_PROFILE"
        else:
            # Небольшое отклонение
            should_descend = (distance_to_intercept <= tolerance_nm * 1.5)
            reason = f"Slight deviation: {altitude_error:+.0f} ft"
            status = "DEVIATION"

        return {
            'should_descend': should_descend,
            'distance_to_intercept_nm': distance_to_intercept,
            'ideal_altitude_agl': ideal_altitude,
            'altitude_error_ft': altitude_error,
            'vertical_deviation_dots': vertical_deviation_dots,
            'reason': reason,
            'status': status,
            'glideslope_angle': glideslope_angle
        }

    def get_glideslope_info(self, glideslope_angle: float) -> Dict[str, any]:
        """
        Получить информацию о параметрах глиссады для заданного угла

        Args:
            glideslope_angle: Угол глиссады (градусы)

        Returns:
            Dict с параметрами глиссады
        """
        # Точная формула
        angle_rad = math.radians(glideslope_angle)
        feet_per_nm_exact = math.tan(angle_rad) * 6076.12

        # Требуемая вертикальная скорость для разных скоростей
        # VS = GS * tan(angle) * 101.3
        vs_at_90kts = 90 * math.tan(angle_rad) * 101.3
        vs_at_120kts = 120 * math.tan(angle_rad) * 101.3
        vs_at_150kts = 150 * math.tan(angle_rad) * 101.3

        # Классификация
        if glideslope_angle < 2.5:
            category = "SHALLOW"
            description = "Пологая глиссада (нестандартная)"
        elif 2.5 <= glideslope_angle <= 3.2:
            category = "STANDARD"
            description = "Стандартная глиссада ICAO"
        elif 3.2 < glideslope_angle <= 4.0:
            category = "STEEP"
            description = "Повышенная глиссада (препятствия/шум)"
        elif 4.0 < glideslope_angle <= 5.5:
            category = "VERY_STEEP"
            description = "Крутая глиссада (горные аэропорты)"
        else:
            category = "EXTREME"
            description = "Экстремально крутая глиссада (требует сертификации)"

        return {
            'angle': glideslope_angle,
            'category': category,
            'description': description,
            'feet_per_nm': feet_per_nm_exact,
            'required_vs_90kts': vs_at_90kts,
            'required_vs_120kts': vs_at_120kts,
            'required_vs_150kts': vs_at_150kts,
            'distance_for_2000ft': self.calculate_glideslope_distance(2000, glideslope_angle),
            'distance_for_3000ft': self.calculate_glideslope_distance(3000, glideslope_angle)
        }

    def calculate_runway_beacons(self,
                                runway_threshold_lat: float,
                                runway_threshold_lon: float,
                                runway_heading: float,
                                runway_elevation: float,
                                glideslope_angle: float = 3.0,
                                outer_distance_nm: float = 5.0,
                                inner_distance_nm: float = 1.0) -> Dict[str, RunwayBeacon]:
        """
        Вычислить позиции дальнего и ближнего приводов ВПП

        Args:
            runway_threshold_lat: Широта порога ВПП
            runway_threshold_lon: Долгота порога ВПП
            runway_heading: Курс ВПП (градусы)
            runway_elevation: Высота ВПП (футы MSL)
            glideslope_angle: Угол глиссады (градусы)
            outer_distance_nm: Расстояние дальнего привода (морские мили)
            inner_distance_nm: Расстояние ближнего привода (морские мили)

        Returns:
            Dict с дальним и ближним приводами
        """
        # Обратный курс (от порога к приводам)
        reverse_heading = (runway_heading + 180) % 360

        # Расчёт ожидаемых высот на приводах
        outer_altitude_agl = self.calculate_glideslope_distance(outer_distance_nm, glideslope_angle) * \
                            (outer_distance_nm / self.calculate_glideslope_distance(
                                outer_distance_nm * math.tan(math.radians(glideslope_angle)) * 6076.12,
                                glideslope_angle)) * math.tan(math.radians(glideslope_angle)) * 6076.12

        # Упрощённый расчёт: высота = расстояние * тангенс угла * 6076.12
        outer_altitude_agl = outer_distance_nm * math.tan(math.radians(glideslope_angle)) * 6076.12
        inner_altitude_agl = inner_distance_nm * math.tan(math.radians(glideslope_angle)) * 6076.12

        # Координаты дальнего привода
        outer_lat_change = outer_distance_nm * math.cos(math.radians(reverse_heading)) / 60.0
        outer_lon_change = outer_distance_nm * math.sin(math.radians(reverse_heading)) / \
                          (60.0 * math.cos(math.radians(runway_threshold_lat)))

        outer_lat = runway_threshold_lat + outer_lat_change
        outer_lon = runway_threshold_lon + outer_lon_change

        # Координаты ближнего привода
        inner_lat_change = inner_distance_nm * math.cos(math.radians(reverse_heading)) / 60.0
        inner_lon_change = inner_distance_nm * math.sin(math.radians(reverse_heading)) / \
                          (60.0 * math.cos(math.radians(runway_threshold_lat)))

        inner_lat = runway_threshold_lat + inner_lat_change
        inner_lon = runway_threshold_lon + inner_lon_change

        # Создание объектов приводов
        outer_beacon = RunwayBeacon(
            name="OUTER",
            beacon_type="OUTER",
            latitude=outer_lat,
            longitude=outer_lon,
            frequency=0,  # Будет установлена из конфигурации
            distance_from_threshold_nm=outer_distance_nm,
            expected_altitude_agl=outer_altitude_agl,
            tolerance_altitude_ft=300.0,
            tolerance_course_deg=5.0
        )

        inner_beacon = RunwayBeacon(
            name="INNER",
            beacon_type="INNER",
            latitude=inner_lat,
            longitude=inner_lon,
            frequency=0,
            distance_from_threshold_nm=inner_distance_nm,
            expected_altitude_agl=inner_altitude_agl,
            tolerance_altitude_ft=200.0,
            tolerance_course_deg=3.0
        )

        return {
            'outer': outer_beacon,
            'inner': inner_beacon
        }

    def check_beacon_passage(self,
                            current_lat: float,
                            current_lon: float,
                            current_altitude_agl: float,
                            current_heading: float,
                            current_speed: float,
                            beacon: RunwayBeacon,
                            expected_course: float,
                            min_speed: float = 90.0,
                            max_speed: float = 160.0) -> BeaconCheckResult:
        """
        Проверить пролёт привода и параметры захода

        Args:
            current_lat: Текущая широта
            current_lon: Текущая долгота
            current_altitude_agl: Текущая высота над землёй (футы)
            current_heading: Текущий курс (градусы)
            current_speed: Текущая скорость (узлы)
            beacon: Объект привода
            expected_course: Ожидаемый курс захода (градусы)
            min_speed: Минимальная допустимая скорость (узлы)
            max_speed: Максимальная допустимая скорость (узлы)

        Returns:
            BeaconCheckResult с результатами проверки
        """
        import time

        # Расстояние до привода
        distance_to_beacon = self.calculate_distance(
            current_lat, current_lon,
            beacon.latitude, beacon.longitude
        )

        # Проверка пролёта (расстояние < 0.3 NM)
        passed_beacon = distance_to_beacon < 0.3 and not beacon.passed

        # Проверка высоты
        altitude_error = current_altitude_agl - beacon.expected_altitude_agl
        altitude_ok = abs(altitude_error) <= beacon.tolerance_altitude_ft

        # Проверка курса
        course_error = self.normalize_angle(current_heading - expected_course)
        course_ok = abs(course_error) <= beacon.tolerance_course_deg

        # Проверка скорости
        speed_ok = min_speed <= current_speed <= max_speed

        # Сбор нарушений
        violations = []
        recommendations = []

        if not altitude_ok:
            if altitude_error > 0:
                violations.append(f"Too high by {altitude_error:.0f} ft")
                recommendations.append("Increase descent rate")
            else:
                violations.append(f"Too low by {abs(altitude_error):.0f} ft")
                recommendations.append("CRITICAL: Reduce descent rate or go around")

        if not course_ok:
            violations.append(f"Course deviation: {course_error:+.1f}°")
            recommendations.append("Correct course to runway heading")

        if not speed_ok:
            if current_speed < min_speed:
                violations.append(f"Speed too low: {current_speed:.0f} kt")
                recommendations.append("Increase speed or check configuration")
            else:
                violations.append(f"Speed too high: {current_speed:.0f} kt")
                recommendations.append("Reduce speed")

        # Определение статуса
        if not violations:
            status = "OK"
        elif len(violations) == 1 and altitude_ok:
            status = "WARNING"
        else:
            status = "CRITICAL"

        # Специальные проверки для типа привода
        if beacon.beacon_type == "OUTER":
            # Дальний привод - проверка готовности к снижению
            if passed_beacon and status == "OK":
                recommendations.append("Begin descent on glideslope")
                recommendations.append("Configure aircraft for landing")
        elif beacon.beacon_type == "INNER":
            # Ближний привод - проверка готовности к посадке
            if passed_beacon and status == "OK":
                recommendations.append("Continue to landing")
                recommendations.append("Prepare for flare")
            elif passed_beacon and status == "CRITICAL":
                recommendations.append("GO AROUND - Unstabilized approach")

        return BeaconCheckResult(
            beacon_name=beacon.name,
            beacon_type=beacon.beacon_type,
            passed_beacon=passed_beacon,
            distance_to_beacon_nm=distance_to_beacon,
            altitude_ok=altitude_ok,
            current_altitude_agl=current_altitude_agl,
            expected_altitude_agl=beacon.expected_altitude_agl,
            altitude_error_ft=altitude_error,
            course_ok=course_ok,
            current_course=current_heading,
            expected_course=expected_course,
            course_error_deg=course_error,
            speed_ok=speed_ok,
            current_speed=current_speed,
            status=status,
            violations=violations,
            recommendations=recommendations,
            timestamp=time.time()
        )

