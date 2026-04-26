"""
Модуль телеметрии для чтения данных из Microsoft Flight Simulator
через SimConnect API
"""

import logging
from typing import Dict, Optional

from SimConnect import AircraftEvents, AircraftRequests, SimConnect

logger = logging.getLogger(__name__)


class MSFSTelemetry:
    """Класс для чтения телеметрии из MSFS"""

    def __init__(self):
        self.sm: Optional[SimConnect] = None
        self.aq: Optional[AircraftRequests] = None
        self.ae: Optional[AircraftEvents] = None
        self.connected = False

    def connect(self) -> bool:
        """Подключение к MSFS через SimConnect"""
        try:
            self.sm = SimConnect()
            self.aq = AircraftRequests(self.sm, _time=200)
            self.ae = AircraftEvents(self.sm)
            self.connected = True
            logger.info("Successfully connected to MSFS")
            return True
        except Exception as e:
            logger.error("Failed to connect to MSFS: %s", e)
            self.connected = False
            return False

    def disconnect(self):
        """Отключение от MSFS"""
        if self.sm:
            self.sm.exit()
            self.connected = False
            logger.info("Disconnected from MSFS")

    def get_position(self) -> Dict[str, float]:
        """Получить текущую позицию самолёта"""
        if not self.connected:
            return {}

        try:
            return {
                'latitude': self.aq.get("PLANE_LATITUDE"),
                'longitude': self.aq.get("PLANE_LONGITUDE"),
                'altitude': self.aq.get("PLANE_ALTITUDE"),  # футы MSL
                'altitude_agl': self.aq.get("PLANE_ALT_ABOVE_GROUND"),  # футы над землёй
                'radio_height': self.aq.get("RADIO_HEIGHT"),  # футы (радиовысотомер)
            }
        except Exception as e:
            logger.error("Error getting position: %s", e)
            return {}

    def get_attitude(self) -> Dict[str, float]:
        """Получить ориентацию самолёта"""
        if not self.connected:
            return {}

        try:
            return {
                'pitch': self.aq.get("PLANE_PITCH_DEGREES"),  # градусы
                'bank': self.aq.get("PLANE_BANK_DEGREES"),  # градусы
                'heading_true': self.aq.get("PLANE_HEADING_DEGREES_TRUE"),  # истинный курс
                'heading_magnetic': self.aq.get("PLANE_HEADING_DEGREES_MAGNETIC"),  # магнитный курс
            }
        except Exception as e:
            logger.error("Error getting attitude: %s", e)
            return {}

    def get_g_force_data(self) -> Dict[str, float]:
        """Получить данные о перегрузках и ускорениях"""
        if not self.connected:
            return {}

        try:
            return {
                'g_force': self.aq.get("G_FORCE"),  # вертикальная перегрузка (G)
                'acceleration_body_x': self.aq.get("ACCELERATION_BODY_X"),  # м/с² (продольное)
                'acceleration_body_y': self.aq.get("ACCELERATION_BODY_Y"),  # м/с² (вертикальное)
                'acceleration_body_z': self.aq.get("ACCELERATION_BODY_Z"),  # м/с² (боковое)
            }
        except Exception as e:
            logger.error("Error getting g-force data: %s", e)
            return {
                'g_force': 1.0,  # fallback значение
                'acceleration_body_x': 0.0,
                'acceleration_body_y': 0.0,
                'acceleration_body_z': 0.0
            }

    def get_speed(self) -> Dict[str, float]:
        """Получить скорости самолёта"""
        if not self.connected:
            return {}

        try:
            return {
                'airspeed_indicated': self.aq.get("AIRSPEED_INDICATED"),  # узлы
                'airspeed_true': self.aq.get("AIRSPEED_TRUE"),  # узлы
                'ground_speed': self.aq.get("GROUND_VELOCITY"),  # узлы
                'vertical_speed': self.aq.get("VERTICAL_SPEED"),  # футы/мин
            }
        except Exception as e:
            logger.error("Error getting speed: %s", e)
            return {}

    def get_nav_data(self) -> Dict[str, any]:
        """Получить навигационные данные (VOR/NDB)"""
        if not self.connected:
            return {}

        try:
            return {
                # NAV1 (обычно VOR)
                'nav1_frequency': self.aq.get("NAV_ACTIVE_FREQUENCY:1"),
                'nav1_radial': self.aq.get("NAV_RADIAL:1"),
                'nav1_signal': self.aq.get("NAV_HAS_NAV:1"),
                'nav1_dme_distance': self.aq.get("NAV_DME:1"),
                'nav1_obs': self.aq.get("NAV_OBS:1"),

                # NAV2
                'nav2_frequency': self.aq.get("NAV_ACTIVE_FREQUENCY:2"),
                'nav2_radial': self.aq.get("NAV_RADIAL:2"),
                'nav2_signal': self.aq.get("NAV_HAS_NAV:2"),
                'nav2_dme_distance': self.aq.get("NAV_DME:2"),
                'nav2_obs': self.aq.get("NAV_OBS:2"),

                # ADF (NDB)
                'adf_frequency': self.aq.get("ADF_ACTIVE_FREQUENCY:1"),
                'adf_signal': self.aq.get("ADF_SIGNAL:1"),
                'adf_radial': self.aq.get("ADF_RADIAL:1"),
            }
        except Exception as e:
            logger.error("Error getting nav data: %s", e)
            return {}

    def get_ils_data(self) -> Dict[str, any]:
        """Получить данные ILS (Instrument Landing System)"""
        if not self.connected:
            return {}

        try:
            return {
                # Localizer (курсовой маяк)
                'nav1_has_localizer': bool(self.aq.get("NAV_HAS_LOCALIZER:1")),
                'nav1_localizer_crs': self.aq.get("NAV_LOCALIZER:1"),  # курс localizer
                'nav1_cdi': self.aq.get("NAV_CDI:1"),  # отклонение от курса (-127 до +127)

                # Glideslope (глиссада)
                'nav1_has_glideslope': bool(self.aq.get("NAV_HAS_GLIDE_SLOPE:1")),
                'nav1_gsi': self.aq.get("NAV_GSI:1"),  # отклонение от глиссады (-127 до +127)
                'nav1_gs_flag': bool(self.aq.get("NAV_GS_FLAG:1")),  # флаг глиссады

                # Дополнительно
                'nav1_to_from': self.aq.get("NAV_TOFROM:1"),  # 0=OFF, 1=TO, 2=FROM
                'nav1_ident': self.aq.get("NAV_IDENT:1"),  # идентификатор станции

                # NAV2 ILS (резервный)
                'nav2_has_localizer': bool(self.aq.get("NAV_HAS_LOCALIZER:2")),
                'nav2_localizer_crs': self.aq.get("NAV_LOCALIZER:2"),
                'nav2_cdi': self.aq.get("NAV_CDI:2"),
                'nav2_has_glideslope': bool(self.aq.get("NAV_HAS_GLIDE_SLOPE:2")),
                'nav2_gsi': self.aq.get("NAV_GSI:2"),
            }
        except Exception as e:
            logger.error("Error getting ILS data: %s", e)
            return {}

    def get_weather_data(self) -> Dict[str, float]:
        """Получить атмосферные данные"""
        if not self.connected:
            return {}

        try:
            return {
                'barometer_pressure': self.aq.get("BAROMETER_PRESSURE"),  # миллибары (hPa)
                'sea_level_pressure': self.aq.get("SEA_LEVEL_PRESSURE"),  # миллибары
                'kohlsman_setting': self.aq.get("KOHLSMAN_SETTING_MB"),  # установка альтиметра (мб)
                'ambient_temperature': self.aq.get("AMBIENT_TEMPERATURE"),  # Цельсий
                'ambient_wind_velocity': self.aq.get("AMBIENT_WIND_VELOCITY"),  # узлы
                'ambient_wind_direction': self.aq.get("AMBIENT_WIND_DIRECTION"),  # градусы
            }
        except Exception as e:
            logger.error("Error getting weather data: %s", e)
            return {}

    def get_aircraft_weight(self) -> Dict[str, float]:
        """Получить вес самолёта"""
        if not self.connected:
            return {}

        try:
            return {
                'total_weight': self.aq.get("TOTAL_WEIGHT"),  # фунты
                'empty_weight': self.aq.get("EMPTY_WEIGHT"),  # фунты
                'fuel_weight': self.aq.get("FUEL_TOTAL_QUANTITY_WEIGHT"),  # фунты
                'payload_weight': self.aq.get("TOTAL_WEIGHT") - self.aq.get("EMPTY_WEIGHT") - self.aq.get("FUEL_TOTAL_QUANTITY_WEIGHT"),  # фунты
            }
        except Exception as e:
            logger.error("Error getting aircraft weight: %s", e)
            return {}

    def get_aircraft_configuration(self) -> Dict[str, float]:
        """Получить конфигурацию самолёта (закрылки, шасси)"""
        if not self.connected:
            return {}

        try:
            return {
                'flaps_position': self.aq.get("FLAPS_HANDLE_PERCENT") / 100.0,  # 0.0-1.0
                'gear_position': self.aq.get("GEAR_POSITION"),  # 0.0-1.0 (0=убрано, 1=выпущено)
                'spoilers_position': self.aq.get("SPOILERS_HANDLE_POSITION") / 100.0,  # 0.0-1.0
            }
        except Exception as e:
            logger.error("Error getting aircraft configuration: %s", e)
            return {
                'flaps_position': 0.0,
                'gear_position': 0.0,
                'spoilers_position': 0.0
            }

    def _decode_simconnect_string(self, raw_value) -> str:
        """Декодировать строку из SimConnect"""
        if isinstance(raw_value, bytes):
            return raw_value.decode('utf-8')
        return str(raw_value) if raw_value else ""

    def _detect_custom_aircraft(self, title: str) -> tuple[str, str]:
        """
        Определить кастомный самолёт по названию

        Returns:
            (manufacturer, autopilot_type)
        """
        title_lower = title.lower() if title else ""

        # PMDG
        if "pmdg" in title_lower:
            if "737" in title_lower:
                return "PMDG", "PMDG_737"
            elif "777" in title_lower:
                return "PMDG", "PMDG_777"
            elif "747" in title_lower:
                return "PMDG", "PMDG_747"
            else:
                return "PMDG", "PMDG_CUSTOM"

        # Fenix
        if "fenix" in title_lower or ("a320" in title_lower and "fenix" in title_lower):
            return "FENIX", "FENIX_A320"

        # FSLabs
        if "fslabs" in title_lower or "flight sim labs" in title_lower:
            if any(model in title_lower for model in ["a320", "a319", "a321"]):
                return "FSLABS", "FSLABS_A32X"
            return "FSLABS", "FSLABS_CUSTOM"

        # iniBuilds
        if "inibuilds" in title_lower or "ini builds" in title_lower:
            if "a300" in title_lower:
                return "INIBUILDS", "INIBUILDS_A300"
            elif "a310" in title_lower:
                return "INIBUILDS", "INIBUILDS_A310"
            else:
                return "INIBUILDS", "INIBUILDS_CUSTOM"

        # FlyByWire
        if "flybywire" in title_lower or "fbw" in title_lower:
            return "FLYBYWIRE", "FBW_A32NX"

        return "UNKNOWN", "NONE"

    def _detect_standard_autopilot(self, autopilot_max_bank: float) -> str:
        """
        Определить тип стандартного автопилота MSFS

        Returns:
            autopilot_type
        """
        has_approach = bool(self.aq.get("AUTOPILOT_APPROACH_HOLD"))
        has_nav = bool(self.aq.get("AUTOPILOT_NAV1_LOCK"))
        has_altitude = bool(self.aq.get("AUTOPILOT_ALTITUDE_LOCK"))
        has_heading = bool(self.aq.get("AUTOPILOT_HEADING_LOCK"))

        if has_approach and has_nav and has_altitude and has_heading:
            if autopilot_max_bank and autopilot_max_bank > 25:
                return "ADVANCED"
            return "STANDARD"
        elif has_heading and has_altitude:
            return "BASIC"
        else:
            return "LIMITED"

    def get_aircraft_info(self) -> Dict[str, any]:
        """Получить информацию о самолёте и его системах"""
        if not self.connected:
            return {}

        try:
            # Базовая информация о самолёте
            title = self._decode_simconnect_string(self.aq.get("TITLE"))
            atc_type = self._decode_simconnect_string(self.aq.get("ATC_TYPE"))
            atc_model = self._decode_simconnect_string(self.aq.get("ATC_MODEL"))

            # Информация о категории
            category = self.aq.get("CATEGORY")
            engine_type = self.aq.get("ENGINE_TYPE")
            number_of_engines = self.aq.get("NUMBER_OF_ENGINES")

            # Возможности автопилота
            autopilot_available = bool(self.aq.get("AUTOPILOT_AVAILABLE"))
            autopilot_max_bank = self.aq.get("AUTOPILOT_MAX_BANK")

            # Дополнительные системы
            is_gear_retractable = bool(self.aq.get("IS_GEAR_RETRACTABLE"))
            is_tail_dragger = bool(self.aq.get("IS_TAIL_DRAGGER"))

            # Определение типа самолёта
            aircraft_manufacturer, autopilot_type = self._detect_custom_aircraft(title)

            # Если не кастомный, определяем стандартный тип
            if aircraft_manufacturer == "UNKNOWN" and autopilot_available:
                autopilot_type = self._detect_standard_autopilot(autopilot_max_bank)

            return {
                'title': title,
                'atc_type': atc_type,
                'atc_model': atc_model,
                'category': category,
                'engine_type': engine_type,
                'engine_type_name': self._get_engine_type_name(engine_type),
                'number_of_engines': number_of_engines,
                'autopilot_available': autopilot_available,
                'autopilot_type': autopilot_type,
                'autopilot_max_bank': autopilot_max_bank,
                'aircraft_manufacturer': aircraft_manufacturer,
                'is_custom_aircraft': aircraft_manufacturer != "UNKNOWN",
                'is_gear_retractable': is_gear_retractable,
                'is_tail_dragger': is_tail_dragger,
            }
        except Exception as e:
            logger.error("Error getting aircraft info: %s", e)
            return {}

    def _get_engine_type_name(self, engine_type: int) -> str:
        """Преобразовать код типа двигателя в название"""
        engine_types = {
            0: "Piston",
            1: "Jet",
            2: "None",
            3: "Helo Turbine",
            4: "Unsupported",
            5: "Turboprop"
        }
        return engine_types.get(engine_type, "Unknown")

    def get_autopilot_capabilities(self) -> Dict[str, any]:
        """Получить возможности автопилота (какие режимы доступны)"""
        if not self.connected:
            return {}

        try:
            # Проверка наличия autothrottle
            has_autothrottle = False
            try:
                # Проверяем доступность autothrottle через несколько переменных
                at_available = self.aq.get("AUTOPILOT_THROTTLE_ARM")
                if at_available is not None:
                    has_autothrottle = True
            except Exception:
                pass

            return {
                'available': bool(self.aq.get("AUTOPILOT_AVAILABLE")),
                'max_bank': self.aq.get("AUTOPILOT_MAX_BANK"),  # Максимальный крен
                'has_autothrottle': has_autothrottle,  # Наличие автоматического управления тягой
            }
        except Exception as e:
            logger.error("Error getting autopilot capabilities: %s", e)
            return {}

    def get_gps_destination(self) -> Dict[str, any]:
        """
        Получить информацию о пункте назначения из GPS/FMC

        Returns:
            Dict с информацией о пункте назначения:
            - airport_icao: ICAO код аэропорта
            - runway_id: ID ВПП (например "07L", "25R")
            - latitude: Широта точки назначения
            - longitude: Долгота точки назначения
            - altitude: Высота точки назначения (футы MSL)
            - distance: Расстояние до точки назначения (NM)
            - bearing: Пеленг на точку назначения (градусы)
        """
        if not self.connected:
            return {}

        try:
            # GPS данные о следующей точке маршрута (обычно это пункт назначения)
            dest_lat = self.aq.get("GPS_WP_NEXT_LAT")
            dest_lon = self.aq.get("GPS_WP_NEXT_LON")
            dest_alt = self.aq.get("GPS_WP_NEXT_ALT")
            dest_id = self.aq.get("GPS_WP_NEXT_ID")

            # Расстояние и пеленг до пункта назначения
            distance = self.aq.get("GPS_WP_DISTANCE")  # метры
            bearing = self.aq.get("GPS_WP_BEARING")  # градусы

            # Декодирование ID (может содержать ICAO + runway)
            dest_id_str = ""
            if dest_id:
                if isinstance(dest_id, bytes):
                    dest_id_str = dest_id.decode('utf-8', errors='ignore').strip()
                else:
                    dest_id_str = str(dest_id).strip()

            # Попытка разделить ICAO и runway ID
            airport_icao = ""
            runway_id = ""

            if dest_id_str:
                # Формат может быть "UUEE07C" или "UUEE-07C" или просто "UUEE"
                # Пытаемся извлечь ICAO (первые 4 символа) и runway
                if len(dest_id_str) >= 4:
                    airport_icao = dest_id_str[:4].upper()

                    # Остаток может быть runway ID
                    remainder = dest_id_str[4:].strip('-').strip()
                    if remainder:
                        runway_id = remainder.upper()

            # Конвертация расстояния из метров в морские мили
            distance_nm = (distance / 1852.0) if distance else 0.0

            result = {
                'airport_icao': airport_icao,
                'runway_id': runway_id,
                'latitude': dest_lat if dest_lat else 0.0,
                'longitude': dest_lon if dest_lon else 0.0,
                'altitude': dest_alt if dest_alt else 0.0,
                'distance_nm': distance_nm,
                'bearing': bearing if bearing else 0.0,
                'raw_id': dest_id_str
            }

            if airport_icao:
                logger.debug(f"GPS destination: {airport_icao} RWY {runway_id if runway_id else 'N/A'}, "
                           f"Distance: {distance_nm:.1f}nm")

            return result

        except Exception as e:
            logger.error("Error getting GPS destination: %s", e)
            return {}

    def get_approach_info(self) -> Dict[str, any]:
        """
        Получить информацию об активном заходе на посадку

        Returns:
            Dict с информацией о заходе:
            - approach_type: Тип захода (ILS, VOR, NDB, GPS, RNAV)
            - decision_height: Decision Height (футы AGL)
            - minimum_descent_altitude: MDA для non-precision заходов (футы MSL)
            - approach_active: Активен ли режим захода
            - ils_frequency: Частота ILS (Hz)
            - localizer_valid: Валиден ли сигнал localizer
            - glideslope_valid: Валиден ли сигнал glideslope
        """
        if not self.connected:
            return {}

        try:
            # Статус режима захода
            approach_active = bool(self.aq.get("AUTOPILOT_APPROACH_HOLD"))

            # ILS данные
            ils_frequency = self.aq.get("NAV_ACTIVE_FREQUENCY:1")  # Hz
            localizer_valid = bool(self.aq.get("NAV_HAS_LOCALIZER:1"))
            glideslope_valid = bool(self.aq.get("NAV_HAS_GLIDE_SLOPE:1"))

            # Попытка получить Decision Height / MDA
            # MSFS может предоставлять эти данные через разные переменные
            decision_height = None
            minimum_descent_altitude = None

            try:
                # GPS_APPROACH_ALTITUDE1 - минимальная высота для GPS захода
                gps_approach_alt = self.aq.get("GPS_APPROACH_ALTITUDE1")
                if gps_approach_alt and gps_approach_alt > 0:
                    # Это может быть DH или MDA в зависимости от типа захода
                    decision_height = gps_approach_alt
            except Exception:
                pass

            try:
                # Альтернативный способ - через DECISION_HEIGHT (если доступно)
                dh = self.aq.get("DECISION_HEIGHT")
                if dh and dh > 0:
                    decision_height = dh
            except Exception:
                pass

            # Определение типа захода
            approach_type = "UNKNOWN"
            if localizer_valid and glideslope_valid:
                approach_type = "ILS"
            elif localizer_valid:
                approach_type = "LOC"  # Localizer only
            elif approach_active:
                # Если approach mode активен, но нет ILS - возможно GPS/RNAV
                approach_type = "GPS"

            result = {
                'approach_type': approach_type,
                'decision_height': decision_height,
                'minimum_descent_altitude': minimum_descent_altitude,
                'approach_active': approach_active,
                'ils_frequency': ils_frequency if ils_frequency else 0,
                'localizer_valid': localizer_valid,
                'glideslope_valid': glideslope_valid
            }

            if approach_active:
                logger.debug("Approach active: %s, DH: %s", approach_type, decision_height if decision_height else 'N/A')

            return result

        except Exception as e:
            logger.error("Error getting approach info: %s", e)
            return {}

    def get_autopilot_state(self) -> Dict[str, bool]:
        """Получить состояние автопилота"""
        if not self.connected:
            return {}

        try:
            return {
                'master': bool(self.aq.get("AUTOPILOT_MASTER")),
                'heading_hold': bool(self.aq.get("AUTOPILOT_HEADING_LOCK")),
                'altitude_hold': bool(self.aq.get("AUTOPILOT_ALTITUDE_LOCK")),
                'nav_hold': bool(self.aq.get("AUTOPILOT_NAV1_LOCK")),
                'approach_hold': bool(self.aq.get("AUTOPILOT_APPROACH_HOLD")),
                'airspeed_hold': bool(self.aq.get("AUTOPILOT_AIRSPEED_HOLD")),
            }
        except Exception as e:
            logger.error("Error getting autopilot state: %s", e)
            return {}

    def get_all_data(self) -> Dict[str, any]:
        """Получить все данные одним запросом"""
        # Получаем базовые данные
        attitude_data = self.get_attitude()
        g_force_data = self.get_g_force_data()

        return {
            'position': self.get_position(),
            'attitude': attitude_data,
            'orientation': attitude_data,  # Алиас для совместимости
            'speed': self.get_speed(),
            'nav': self.get_nav_data(),
            'ils': self.get_ils_data(),
            'autopilot': self.get_autopilot_state(),
            'weather': self.get_weather_data(),
            'weight': self.get_aircraft_weight(),
            'aircraft': self.get_aircraft_info(),
            'configuration': self.get_aircraft_configuration(),  # Конфигурация (flaps/gear)
            'g_force': g_force_data.get('g_force', 1.0),  # Для удобного доступа
            'g_force_data': g_force_data,
            'gps_destination': self.get_gps_destination(),  # Информация о пункте назначения
            'approach_info': self.get_approach_info(),  # Информация о заходе
        }
