"""
Адаптер команд для кастомных самолётов
Преобразует стандартные команды в специфичные для каждого производителя
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AircraftCommandAdapter:
    """Адаптер команд для различных типов самолётов"""

    def __init__(self, control, telemetry):
        """
        Args:
            control: Экземпляр MSFSControl
            telemetry: Экземпляр MSFSTelemetry
        """
        self.control = control
        self.telemetry = telemetry
        self.profiles = self._load_profiles()
        self.current_profile = None
        self.aircraft_info = None
        self.wasm = None
        self.config_reader = None

        # Инициализация читателя конфигурационных файлов
        try:
            from modules.aircraft_config_reader import AircraftConfigReader
            self.config_reader = AircraftConfigReader()
            logger.info("Aircraft config reader initialized")
        except Exception as e:
            logger.warning("Failed to initialize config reader: %s", e)
            self.config_reader = None

        # Попытка подключения к MobiFlight WASM
        try:
            from modules.wasm_interface import MobiFlightWASM
            self.wasm = MobiFlightWASM(telemetry.sm)
            if self.wasm.connect():
                logger.info("MobiFlight WASM connected - LVAR support enabled")
            else:
                self.wasm = None
                logger.info("MobiFlight WASM not available - using SimConnect only")
        except ImportError:
            logger.info("WASM interface not available")
            self.wasm = None
        except Exception as e:
            logger.warning("Failed to initialize WASM: %s", e)
            self.wasm = None

    def _load_profiles(self) -> Dict:
        """Загрузить профили самолётов из JSON"""
        try:
            profile_path = Path(__file__).parent.parent / "config" / "aircraft_profiles.json"
            with open(profile_path, encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load aircraft profiles: %s", e)
            return {"aircraft_profiles": {}, "fallback": {}}

    def _detect_profile_by_title(self, title: str) -> Optional[str]:
        """
        Определить профиль по названию самолёта

        Args:
            title: Название самолёта из SimConnect (TITLE)

        Returns:
            Ключ профиля или None если не найден
        """
        if not title:
            return None

        title_upper = title.upper()

        # Паттерны для определения самолётов
        patterns = {
            'PMDG_737': ['PMDG', '737'],
            'PMDG_777': ['PMDG', '777'],
            'FENIX_A320': ['FENIX', 'A320'],
            'FSLABS_A32X': ['FSLABS', 'A32'],
            'FBW_A32NX': ['FLYBYWIRE', 'A32NX', 'FBW'],
            'INIBUILDS_A300': ['INIBUILDS', 'A300', 'INI A300'],
            'INIBUILDS_A310': ['INIBUILDS', 'A310', 'INI A310']
        }

        # Проверка каждого профиля
        for profile_key, keywords in patterns.items():
            # Для PMDG требуется оба ключевых слова (производитель + модель)
            if profile_key.startswith('PMDG'):
                if all(keyword in title_upper for keyword in keywords):
                    logger.info("Matched profile by title: %s (pattern: %s)", profile_key, keywords)
                    return profile_key
            # Для остальных достаточно одного совпадения
            else:
                if any(keyword in title_upper for keyword in keywords):
                    logger.info("Matched profile by title: %s (pattern: %s)", profile_key, keywords)
                    return profile_key

        return None

    def detect_and_configure(self) -> bool:
        """
        Определить тип самолёта и настроить адаптер

        Returns:
            True если профиль найден и настроен
        """
        self.aircraft_info = self.telemetry.get_aircraft_info()

        if not self.aircraft_info:
            logger.error("Failed to get aircraft info")
            return False

        autopilot_type = self.aircraft_info.get('autopilot_type', 'UNKNOWN')
        manufacturer = self.aircraft_info.get('aircraft_manufacturer', 'UNKNOWN')
        is_custom = self.aircraft_info.get('is_custom_aircraft', False)
        title = self.aircraft_info.get('title', '')

        logger.info("Detected aircraft: %s", title)
        logger.info("Manufacturer: %s, Autopilot Type: %s, Custom: %s", manufacturer, autopilot_type, is_custom)

        profile_key = None

        # Метод 1: Точное совпадение по autopilot_type
        if is_custom and autopilot_type in self.profiles['aircraft_profiles']:
            profile_key = autopilot_type
            logger.info("Profile matched by autopilot_type: %s", profile_key)

        # Метод 2: Поиск по паттернам в названии
        if not profile_key:
            profile_key = self._detect_profile_by_title(title)

        # Метод 3: Чтение конфигурационных файлов самолёта
        # Пропускаем для стандартных самолётов MSFS (они не имеют отдельных папок)
        if not profile_key and self.config_reader and manufacturer != "UNKNOWN":
            logger.info("Attempting to detect aircraft from config files...")
            try:
                profile_key = self.config_reader.detect_aircraft_profile(title)
                if profile_key:
                    logger.info("Profile matched by config files: %s", profile_key)
            except Exception as e:
                logger.warning("Error reading aircraft config files: %s", e)

        # Применение профиля
        if profile_key and profile_key in self.profiles['aircraft_profiles']:
            self.current_profile = self.profiles['aircraft_profiles'][profile_key]
            logger.info("Using custom profile: %s", self.current_profile['name'])
            return True
        else:
            self.current_profile = self.profiles['fallback']
            logger.info("Using standard SimConnect fallback")
            return True

    def set_heading(self, heading: int) -> bool:
        """
        Установить курс

        Args:
            heading: Курс в градусах (0-359)

        Returns:
            True если команда выполнена успешно
        """
        if not self.current_profile:
            logger.error("No profile configured")
            return False

        try:
            cmd = self.current_profile['autopilot']['commands']['heading']
            method = cmd.get('method', 'simconnect')

            if method == 'simconnect':
                # Стандартная команда SimConnect
                self.control.set_heading_hold(heading)
                logger.debug("Set heading via SimConnect: %s°", heading)
                return True

            elif method == 'lvar' and self.wasm:
                # Через WASM
                variable = cmd.get('variable')
                event = cmd.get('event')

                if self.wasm.write_lvar(variable, float(heading)):
                    if event:
                        self.wasm.trigger_event(event)
                    logger.debug("Set heading via LVAR: %s = %s°", variable, heading)
                    return True
                else:
                    # Fallback на SimConnect
                    logger.warning("LVAR write failed, using SimConnect fallback")
                    self.control.set_heading_hold(heading)
                    return True

            elif method == 'lvar':
                # WASM недоступен, fallback
                logger.warning("LVAR method requires WASM: %s", cmd.get('variable'))
                self.control.set_heading_hold(heading)
                return True

            else:
                logger.error("Unknown method: %s", method)
                return False

        except Exception as e:
            logger.error("Error setting heading: %s", e)
            return False

    def set_altitude(self, altitude: int) -> bool:
        """
        Установить высоту

        Args:
            altitude: Высота в футах

        Returns:
            True если команда выполнена успешно
        """
        if not self.current_profile:
            logger.error("No profile configured")
            return False

        try:
            cmd = self.current_profile['autopilot']['commands']['altitude']
            method = cmd.get('method', 'simconnect')

            if method == 'simconnect':
                self.control.set_altitude_hold(altitude)
                logger.debug("Set altitude via SimConnect: %sft", altitude)
                return True

            elif method == 'lvar' and self.wasm:
                # Через WASM
                variable = cmd.get('variable')
                event = cmd.get('event')

                if self.wasm.write_lvar(variable, float(altitude)):
                    if event:
                        self.wasm.trigger_event(event)
                    logger.debug("Set altitude via LVAR: %s = %sft", variable, altitude)
                    return True
                else:
                    logger.warning("LVAR write failed, using SimConnect fallback")
                    self.control.set_altitude_hold(altitude)
                    return True

            elif method == 'lvar':
                logger.warning("LVAR method requires WASM: %s", cmd.get('variable'))
                self.control.set_altitude_hold(altitude)
                return True

            else:
                logger.error("Unknown method: %s", method)
                return False

        except Exception as e:
            logger.error("Error setting altitude: %s", e)
            return False

    def set_vertical_speed(self, vs: int) -> bool:
        """
        Установить вертикальную скорость

        Args:
            vs: Вертикальная скорость в футах/мин

        Returns:
            True если команда выполнена успешно
        """
        if not self.current_profile:
            logger.error("No profile configured")
            return False

        try:
            cmd = self.current_profile['autopilot']['commands'].get('vertical_speed')

            if not cmd:
                # Если команда не определена, используем SimConnect
                self.control.set_vertical_speed(vs)
                return True

            method = cmd.get('method', 'simconnect')

            if method == 'simconnect':
                self.control.set_vertical_speed(vs)
                logger.debug("Set VS via SimConnect: %sfpm", vs)
                return True

            elif method == 'lvar' and self.wasm:
                variable = cmd.get('variable')
                event = cmd.get('event')

                if self.wasm.write_lvar(variable, float(vs)):
                    if event:
                        self.wasm.trigger_event(event)
                    logger.debug("Set VS via LVAR: %s = %sfpm", variable, vs)
                    return True
                else:
                    logger.warning("LVAR write failed, using SimConnect fallback")
                    self.control.set_vertical_speed(vs)
                    return True

            elif method == 'lvar':
                logger.warning("LVAR method requires WASM: %s", cmd.get('variable'))
                self.control.set_vertical_speed(vs)
                return True

            else:
                logger.error("Unknown method: %s", method)
                return False

        except Exception as e:
            logger.error("Error setting vertical speed: %s", e)
            return False

    def engage_approach_mode(self) -> bool:
        """
        Включить режим захода (Approach/APP)

        Returns:
            True если команда выполнена успешно
        """
        if not self.current_profile:
            logger.error("No profile configured")
            return False

        try:
            cmd = self.current_profile['autopilot']['commands'].get('approach_mode')

            if not cmd:
                logger.warning("Approach mode not defined in profile")
                return False

            method = cmd.get('method', 'simconnect')

            if method == 'simconnect':
                self.control.set_approach_hold(True)
                logger.info("Approach mode engaged via SimConnect")
                return True

            elif method == 'event' and self.wasm:
                event = cmd.get('event')
                if self.wasm.trigger_event(event):
                    logger.info("Approach mode engaged via event: %s", event)
                    return True
                else:
                    logger.warning("Event trigger failed, using SimConnect fallback")
                    self.control.set_approach_hold(True)
                    return True

            elif method == 'event':
                logger.warning("Event method requires WASM: %s", cmd.get('event'))
                self.control.set_approach_hold(True)
                return True

            else:
                logger.error("Unknown method: %s", method)
                return False

        except Exception as e:
            logger.error("Error engaging approach mode: %s", e)
            return False

    def engage_nav_mode(self) -> bool:
        """
        Включить режим NAV

        Returns:
            True если команда выполнена успешно
        """
        if not self.current_profile:
            logger.error("No profile configured")
            return False

        try:
            cmd = self.current_profile['autopilot']['commands'].get('nav_mode')

            if not cmd:
                logger.warning("NAV mode not defined in profile")
                return False

            method = cmd.get('method', 'simconnect')

            if method == 'simconnect':
                self.control.set_nav_hold(True)
                logger.info("NAV mode engaged via SimConnect")
                return True

            elif method == 'event' and self.wasm:
                event = cmd.get('event')
                if self.wasm.trigger_event(event):
                    logger.info("NAV mode engaged via event: %s", event)
                    return True
                else:
                    logger.warning("Event trigger failed, using SimConnect fallback")
                    self.control.set_nav_hold(True)
                    return True

            elif method == 'event':
                logger.warning("Event method requires WASM: %s", cmd.get('event'))
                self.control.set_nav_hold(True)
                return True

            else:
                logger.error("Unknown method: %s", method)
                return False

        except Exception as e:
            logger.error("Error engaging NAV mode: %s", e)
            return False

    def engage_autopilot(self) -> bool:
        """
        Включить автопилот

        Returns:
            True если команда выполнена успешно
        """
        if not self.current_profile:
            logger.error("No profile configured")
            return False

        try:
            cmd = self.current_profile['autopilot']['commands'].get('autopilot_master')

            if not cmd:
                # Fallback на SimConnect
                self.control.set_autopilot_master(True)
                logger.info("Autopilot engaged via SimConnect")
                return True

            method = cmd.get('method', 'simconnect')

            if method == 'simconnect':
                self.control.set_autopilot_master(True)
                logger.info("Autopilot engaged via SimConnect")
                return True

            elif method == 'event' and self.wasm:
                event = cmd.get('event')
                if self.wasm.trigger_event(event):
                    logger.info("Autopilot engaged via event: %s", event)
                    return True
                else:
                    self.control.set_autopilot_master(True)
                    return True

            elif method == 'lvar' and self.wasm:
                variable = cmd.get('variable')
                if self.wasm.write_lvar(variable, 1.0):
                    logger.info("Autopilot engaged via LVAR: %s", variable)
                    return True
                else:
                    self.control.set_autopilot_master(True)
                    return True

            else:
                self.control.set_autopilot_master(True)
                return True

        except Exception as e:
            logger.error("Error engaging autopilot: %s", e)
            return False

    def disengage_autopilot(self) -> bool:
        """
        Выключить автопилот

        Returns:
            True если команда выполнена успешно
        """
        if not self.current_profile:
            logger.error("No profile configured")
            return False

        try:
            cmd = self.current_profile['autopilot']['commands'].get('autopilot_master')

            if not cmd:
                self.control.set_autopilot_master(False)
                logger.info("Autopilot disengaged via SimConnect")
                return True

            method = cmd.get('method', 'simconnect')

            if method == 'simconnect':
                self.control.set_autopilot_master(False)
                logger.info("Autopilot disengaged via SimConnect")
                return True

            elif method == 'event' and self.wasm:
                event = cmd.get('event_off', cmd.get('event'))
                if self.wasm.trigger_event(event):
                    logger.info("Autopilot disengaged via event: %s", event)
                    return True
                else:
                    self.control.set_autopilot_master(False)
                    return True

            elif method == 'lvar' and self.wasm:
                variable = cmd.get('variable')
                if self.wasm.write_lvar(variable, 0.0):
                    logger.info("Autopilot disengaged via LVAR: %s", variable)
                    return True
                else:
                    self.control.set_autopilot_master(False)
                    return True

            else:
                self.control.set_autopilot_master(False)
                return True

        except Exception as e:
            logger.error("Error disengaging autopilot: %s", e)
            return False

    def set_speed(self, speed: int) -> bool:
        """
        Установить целевую скорость (для autothrottle)

        Args:
            speed: Скорость в узлах

        Returns:
            True если команда выполнена успешно
        """
        if not self.current_profile:
            logger.error("No profile configured")
            return False

        try:
            autothrottle = self.current_profile.get('autothrottle', {})

            if not autothrottle.get('supported', False):
                logger.warning("Autothrottle not supported for this aircraft")
                return False

            cmd = autothrottle.get('commands', {}).get('set_speed')

            if not cmd:
                logger.warning("Set speed command not defined")
                return False

            method = cmd.get('method', 'simconnect')

            if method == 'simconnect':
                self.control.set_airspeed_hold(speed)
                logger.debug("Set speed via SimConnect: %skts", speed)
                return True

            elif method == 'lvar' and self.wasm:
                variable = cmd.get('variable')
                event = cmd.get('event')

                if self.wasm.write_lvar(variable, float(speed)):
                    if event:
                        self.wasm.trigger_event(event)
                    logger.debug("Set speed via LVAR: %s = %skts", variable, speed)
                    return True
                else:
                    self.control.set_airspeed_hold(speed)
                    return True

            else:
                self.control.set_airspeed_hold(speed)
                return True

        except Exception as e:
            logger.error("Error setting speed: %s", e)
            return False

    def engage_autothrottle(self) -> bool:
        """
        Включить autothrottle

        Returns:
            True если команда выполнена успешно
        """
        if not self.current_profile:
            logger.error("No profile configured")
            return False

        try:
            autothrottle = self.current_profile.get('autothrottle', {})

            if not autothrottle.get('supported', False):
                logger.warning("Autothrottle not supported for this aircraft")
                return False

            cmd = autothrottle.get('commands', {}).get('engage')

            if not cmd:
                logger.warning("Autothrottle engage command not defined")
                return False

            method = cmd.get('method', 'simconnect')

            if method == 'simconnect':
                self.control.set_autothrottle(True)
                logger.info("Autothrottle engaged via SimConnect")
                return True

            elif method == 'event' and self.wasm:
                event = cmd.get('event')
                if self.wasm.trigger_event(event):
                    logger.info("Autothrottle engaged via event: %s", event)
                    return True
                else:
                    self.control.set_autothrottle(True)
                    return True

            elif method == 'lvar' and self.wasm:
                variable = cmd.get('variable')
                if self.wasm.write_lvar(variable, 1.0):
                    logger.info("Autothrottle engaged via LVAR: %s", variable)
                    return True
                else:
                    self.control.set_autothrottle(True)
                    return True

            else:
                self.control.set_autothrottle(True)
                return True

        except Exception as e:
            logger.error("Error engaging autothrottle: %s", e)
            return False

    def get_autopilot_status(self) -> Dict[str, Any]:
        """
        Получить статус автопилота

        Returns:
            Dict со статусом различных режимов
        """
        if not self.current_profile or not self.wasm:
            return {}

        try:
            status_vars = self.current_profile['autopilot'].get('status_variables', {})
            status = {}

            for key, var_name in status_vars.items():
                value = self.wasm.read_lvar(var_name)
                if value is not None:
                    status[key] = bool(value)

            return status

        except Exception as e:
            logger.error("Error getting autopilot status: %s", e)
            return {}

    def get_profile_info(self) -> Dict[str, Any]:
        """Получить информацию о текущем профиле"""
        if not self.current_profile:
            return {}

        return {
            'name': self.current_profile.get('name', 'Unknown'),
            'manufacturer': self.current_profile.get('manufacturer', 'Unknown'),
            'type': self.current_profile.get('type', 'Unknown'),
            'requires_lvars': self.current_profile.get('requires_lvars', False),
            'limitations': self.current_profile.get('limitations', {}),
            'autothrottle_supported': self.current_profile.get('autothrottle', {}).get('supported', False)
        }

    def check_compatibility(self) -> Dict[str, Any]:
        """
        Проверить совместимость текущего самолёта с AutoLand

        Returns:
            Dict с информацией о совместимости
        """
        if not self.current_profile or not self.aircraft_info:
            return {
                'compatible': False,
                'reason': 'No profile or aircraft info available'
            }

        profile_info = self.get_profile_info()
        requires_lvars = profile_info.get('requires_lvars', False)

        # Проверка наличия WASM если требуются LVARs
        if requires_lvars:
            has_lvar_support = self.wasm is not None and self.wasm.connected

            if not has_lvar_support:
                return {
                    'compatible': True,
                    'limited': True,
                    'reason': 'Custom aircraft detected but LVAR support not available',
                    'recommendation': 'Install MobiFlight WASM module for full functionality',
                    'fallback': 'Using SimConnect fallback (limited functionality)',
                    'wasm_available': False
                }
            else:
                return {
                    'compatible': True,
                    'limited': False,
                    'profile': profile_info.get('name'),
                    'manufacturer': profile_info.get('manufacturer'),
                    'autothrottle': profile_info.get('autothrottle_supported'),
                    'wasm_available': True,
                    'full_functionality': True
                }

        return {
            'compatible': True,
            'limited': False,
            'profile': profile_info.get('name'),
            'manufacturer': profile_info.get('manufacturer'),
            'autothrottle': profile_info.get('autothrottle_supported')
        }

    # ── Readback methods (WP-3 / FIX-1) ──────────────────────────

    def get_autopilot_engaged(self) -> Optional[bool]:
        """Readback: AP включён?

        Базовая реализация возвращает None (fallback → control readback).
        Кастомные адаптеры (PMDG, Fenix) могут переопределить через LVars.
        """
        return None

    def get_autothrottle_engaged(self) -> Optional[bool]:
        """Readback: A/T включён?

        Базовая реализация возвращает None (fallback → control readback).
        Кастомные адаптеры (PMDG, Fenix) могут переопределить через LVars.
        """
        return None
