"""
Модуль работы с дальномером (DME - Distance Measuring Equipment)
"""

import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DMEFix:
    """Контрольная точка по DME"""
    distance: float  # морские мили
    altitude: int  # футы MSL
    name: str  # название точки


@dataclass
class DMEArcConfig:
    """Конфигурация захода по дуге DME"""
    arc_radius: float  # радиус дуги (морские мили)
    arc_start_radial: int  # начальный радиал (градусы)
    arc_end_radial: int  # конечный радиал (градусы)
    arc_altitude: int  # высота на дуге (футы)
    final_approach_radial: int  # радиал для перехода на финал


class DMENavigation:
    """Класс для навигации с использованием DME"""

    def __init__(self):
        self.dme_fixes: List[DMEFix] = []

    def add_dme_fix(self, fix: DMEFix):
        """Добавить контрольную точку DME"""
        self.dme_fixes.append(fix)
        self.dme_fixes.sort(key=lambda x: x.distance, reverse=True)
        logger.info("Added DME fix: %s at %snm / %sft", fix.name, fix.distance, fix.altitude)

    def get_current_fix(self, dme_distance: float) -> Optional[DMEFix]:
        """Получить ближайшую контрольную точку"""
        for fix in self.dme_fixes:
            if dme_distance >= fix.distance - 0.5:  # допуск 0.5nm
                return fix
        return None

    def check_altitude_at_fix(self, dme_distance: float, current_altitude: int,
                             tolerance: int = 200) -> Dict[str, any]:
        """
        Проверка высоты на контрольной точке

        Args:
            dme_distance: Текущее расстояние DME (морские мили)
            current_altitude: Текущая высота (футы)
            tolerance: Допуск по высоте (футы)

        Returns:
            Dict с результатами проверки
        """
        fix = self.get_current_fix(dme_distance)

        if not fix:
            return {
                'has_fix': False,
                'on_profile': True,
                'deviation': 0
            }

        deviation = current_altitude - fix.altitude
        on_profile = abs(deviation) <= tolerance

        status = "OK" if on_profile else "DEVIATION"
        if abs(deviation) > tolerance * 2:
            status = "CRITICAL"

        logger.info(f"Fix {fix.name}: Required {fix.altitude}ft, "
                   f"Current {current_altitude}ft, Deviation {deviation:+d}ft - {status}")

        return {
            'has_fix': True,
            'fix': fix,
            'on_profile': on_profile,
            'deviation': deviation,
            'status': status,
            'required_altitude': fix.altitude
        }

    def calculate_descent_profile(self, current_dme: float, current_altitude: int,
                                  target_dme: float, target_altitude: int) -> Dict[str, float]:
        """
        Расчёт профиля снижения между двумя точками DME

        Args:
            current_dme: Текущее расстояние (морские мили)
            current_altitude: Текущая высота (футы)
            target_dme: Целевое расстояние (морские мили)
            target_altitude: Целевая высота (футы)

        Returns:
            Dict с параметрами снижения
        """
        distance_to_go = current_dme - target_dme
        altitude_to_lose = current_altitude - target_altitude

        if distance_to_go <= 0:
            return {
                'distance_to_go': 0,
                'altitude_to_lose': 0,
                'descent_angle': 0,
                'required_vs': 0,
                'on_profile': True
            }

        # Угол снижения
        distance_feet = distance_to_go * 6076.12
        descent_angle = math.degrees(math.atan(altitude_to_lose / distance_feet))

        return {
            'distance_to_go': distance_to_go,
            'altitude_to_lose': altitude_to_lose,
            'descent_angle': descent_angle,
            'on_profile': abs(descent_angle - 3.0) < 1.0  # допуск 1°
        }

    def calculate_required_vs_for_dme(self, ground_speed: float, current_dme: float,
                                     target_dme: float, altitude_to_lose: int) -> int:
        """
        Расчёт требуемой вертикальной скорости для достижения высоты на DME

        Args:
            ground_speed: Путевая скорость (узлы)
            current_dme: Текущее DME (морские мили)
            target_dme: Целевое DME (морские мили)
            altitude_to_lose: Высота для потери (футы)

        Returns:
            Требуемая вертикальная скорость (футы/мин)
        """
        distance_to_go = current_dme - target_dme

        if distance_to_go <= 0 or ground_speed <= 0:
            return 0

        # Время до точки (минуты)
        time_to_fix = (distance_to_go / ground_speed) * 60

        # Требуемая вертикальная скорость
        required_vs = altitude_to_lose / time_to_fix if time_to_fix > 0 else 0

        logger.debug(f"DME descent: {distance_to_go:.1f}nm to go, "
                    f"{altitude_to_lose}ft to lose, "
                    f"Required VS: {required_vs:.0f} fpm")

        return int(required_vs)

    def calculate_dme_arc_position(self, current_dme: float, current_radial: float,
                                   config: DMEArcConfig) -> Dict[str, any]:
        """
        Расчёт позиции на дуге DME

        Args:
            current_dme: Текущее расстояние DME (морские мили)
            current_radial: Текущий радиал (градусы)
            config: Конфигурация дуги

        Returns:
            Dict с параметрами позиции на дуге
        """
        # Отклонение от радиуса дуги
        radius_error = current_dme - config.arc_radius

        # Проверка, находимся ли на дуге
        on_arc_radial = self._is_radial_on_arc(
            current_radial,
            config.arc_start_radial,
            config.arc_end_radial
        )

        # Расстояние до конца дуги (по радиалу)
        radials_to_go = self._calculate_radials_to_go(
            current_radial,
            config.arc_end_radial
        )

        # Расстояние по дуге (морские мили)
        arc_distance_to_go = (radials_to_go / 360.0) * 2 * math.pi * config.arc_radius

        return {
            'on_arc': on_arc_radial and abs(radius_error) < 0.5,
            'radius_error': radius_error,
            'radials_to_go': radials_to_go,
            'arc_distance_to_go': arc_distance_to_go,
            'should_turn_inbound': abs(current_radial - config.final_approach_radial) < 10
        }

    def calculate_arc_heading(self, current_radial: float, arc_radius: float,
                             turn_direction: str = 'right') -> float:
        """
        Расчёт курса для следования по дуге DME

        Args:
            current_radial: Текущий радиал (градусы)
            arc_radius: Радиус дуги (морские мили)
            turn_direction: Направление разворота ('right' или 'left')

        Returns:
            Рекомендуемый курс (градусы)
        """
        # Курс перпендикулярен радиалу
        if turn_direction == 'right':
            heading = (current_radial + 90) % 360
        else:
            heading = (current_radial - 90) % 360

        # Коррекция для удержания на дуге (lead/lag)
        # Чем меньше радиус, тем больше коррекция
        lead_angle = min(10, 60 / arc_radius)

        if turn_direction == 'right':
            heading = (heading + lead_angle) % 360
        else:
            heading = (heading - lead_angle) % 360

        return heading

    def check_dme_accuracy(self, dme_distance: float, calculated_distance: float,
                          tolerance: float = 0.5) -> Dict[str, any]:
        """
        Проверка точности DME

        Args:
            dme_distance: Расстояние от DME (морские мили)
            calculated_distance: Расчётное расстояние (морские мили)
            tolerance: Допустимое расхождение (морские мили)

        Returns:
            Dict с результатами проверки
        """
        difference = abs(dme_distance - calculated_distance)
        is_accurate = difference <= tolerance

        status = "OK" if is_accurate else "WARNING"
        if difference > tolerance * 2:
            status = "CRITICAL"

        if not is_accurate:
            logger.warning(f"DME accuracy check: DME={dme_distance:.1f}nm, "
                         f"Calculated={calculated_distance:.1f}nm, "
                         f"Difference={difference:.1f}nm - {status}")

        return {
            'is_accurate': is_accurate,
            'dme_distance': dme_distance,
            'calculated_distance': calculated_distance,
            'difference': difference,
            'status': status
        }

    def calculate_dme_hold(self, current_dme: float, hold_distance: float,
                          current_heading: float, station_bearing: float) -> Dict[str, any]:
        """
        Расчёт параметров для удержания на заданном DME

        Args:
            current_dme: Текущее расстояние (морские мили)
            hold_distance: Требуемое расстояние (морские мили)
            current_heading: Текущий курс (градусы)
            station_bearing: Пеленг на станцию (градусы)

        Returns:
            Dict с рекомендациями
        """
        distance_error = current_dme - hold_distance

        # Определение действия
        if abs(distance_error) < 0.2:
            action = "MAINTAIN"
            recommended_heading = (station_bearing + 90) % 360  # перпендикулярно
        elif distance_error > 0:
            action = "TURN_TOWARDS"
            recommended_heading = station_bearing  # лететь к станции
        else:
            action = "TURN_AWAY"
            recommended_heading = (station_bearing + 180) % 360  # лететь от станции

        return {
            'distance_error': distance_error,
            'action': action,
            'recommended_heading': recommended_heading,
            'on_distance': abs(distance_error) < 0.2
        }

    @staticmethod
    def _is_radial_on_arc(current_radial: float, start_radial: float,
                         end_radial: float) -> bool:
        """Проверка, находится ли радиал в пределах дуги"""
        if start_radial <= end_radial:
            return start_radial <= current_radial <= end_radial
        else:
            return current_radial >= start_radial or current_radial <= end_radial

    @staticmethod
    def _calculate_radials_to_go(current_radial: float, end_radial: float) -> float:
        """Расчёт оставшихся градусов до конца дуги"""
        diff = end_radial - current_radial
        if diff < 0:
            diff += 360
        return diff
