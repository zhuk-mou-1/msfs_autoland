"""
Общие типы данных для модулей MSFS AutoLand

Этот модуль содержит dataclasses используемые в разных частях системы.
Вынесены в отдельный модуль для избежания циклических зависимостей.
"""

from dataclasses import dataclass


@dataclass
class NavStation:
    """Навигационная станция (VOR, NDB, ILS или LOC)"""
    name: str
    frequency: int  # Hz
    latitude: float
    longitude: float
    type: str  # 'VOR', 'NDB', 'ILS', или 'LOC'


@dataclass
class RunwayBeacon:
    """Привод ВПП (NDB beacon для VOR/NDB заходов)"""
    name: str  # Название привода (например, "ШР", "ВН")
    beacon_type: str  # 'OUTER' (дальний) или 'INNER' (ближний)
    latitude: float
    longitude: float
    frequency: int  # кГц (190-1750)
    distance_from_threshold_nm: float
    expected_altitude_agl: float  # Ожидаемая высота при пролёте
    tolerance_altitude_ft: float = 300.0  # Допуск по высоте
    tolerance_course_deg: float = 5.0  # Допуск по курсу
    passed: bool = False  # Флаг пролёта
    pass_timestamp: float = 0.0  # Время пролёта


@dataclass
class BeaconCheckResult:
    """Результат проверки при пролёте привода"""
    beacon_name: str
    beacon_type: str
    passed_beacon: bool
    distance_to_beacon_nm: float
    altitude_ok: bool
    current_altitude_agl: float
    expected_altitude_agl: float
    altitude_error_ft: float
    course_ok: bool
    current_course: float
    expected_course: float
    course_error_deg: float
    speed_ok: bool
    current_speed: float
    status: str  # 'OK', 'WARNING', 'CRITICAL'
    violations: list
    recommendations: list
    timestamp: float


@dataclass
class ApproachConfig:
    """Конфигурация захода на посадку"""
    station: NavStation
    final_approach_course: int  # градусы
    glideslope_angle: float  # градусы (обычно 3.0)
    decision_height: int  # футы
    approach_speed: int  # узлы
    runway_elevation: int  # футы
    runway_length: int  # футы (длина ВПП)
    runway_width: int  # футы (ширина ВПП)
    runway_threshold_lat: float  # широта порога ВПП
    runway_threshold_lon: float  # долгота порога ВПП
