"""
Главное приложение для автоматической посадки в MSFS
с использованием VOR/NDB заходов
"""

import logging
import time
from enum import Enum
from typing import Optional

from modules.aircraft_adapter import AircraftCommandAdapter
from modules.approach_phases import (ApproachPhaseState, InitialPhaseState, LandingPhaseState)
from modules.approach_speed_calculator import ApproachSpeedCalculator
from modules.audio_alerts import get_audio_system
from modules.autopilot_takeover import AutopilotTakeover, TakeoverConfig
from modules.autothrottle import (AutothrottleController,
                                  VJoyThrottleIntegration)
from modules.connection_monitor import ConnectionMonitor
from modules.connection_optimizer import ConnectionOptimizer
from modules.control import MSFSControl
from modules.dme_navigation import DMENavigation
from modules.flare_controller import FlareController
from modules.fms_reader import FMSReader
from modules.ils_navigation import ILSNavigation
from modules.navigation import Navigation
from modules.types import ApproachConfig, NavStation
from modules.stabilized_approach import (StabilizedApproachMonitor,
                                         StabilizedCriteria)
from modules.structured_logger import LogCategory, init_logger
from modules.telemetry import MSFSTelemetry
from modules.turbulence_detector import TurbulenceDetector
from modules.virtual_joystick import VirtualJoystick
from modules.synthetic_glidepath import SyntheticGlidepath
from modules.wind_correction import WindCorrection
from modules.wind_shear_detector import WindShearDetector

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/autoland.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ApproachPhase(Enum):
    """Фазы захода на посадку"""
    IDLE = "IDLE"
    INITIAL = "INITIAL"
    INTERMEDIATE = "INTERMEDIATE"
    FINAL = "FINAL"
    LANDING = "LANDING"
    COMPLETED = "COMPLETED"


class AutoLandSystem:
    """Система автоматической посадки"""

    def __init__(self):
        # Инициализация структурированного логгера
        self.structured_logger = init_logger()
        self.structured_logger.info(LogCategory.SYSTEM, "AutoLandSystem initializing")

        self.telemetry = MSFSTelemetry()
        self.control: Optional[MSFSControl] = None
        self.navigation = Navigation()
        self.wind_correction = WindCorrection()
        self.dme_navigation = DMENavigation()
        self.virtual_joystick = VirtualJoystick()
        self.stabilized_monitor = StabilizedApproachMonitor()
        self.flare_controller = FlareController()
        self.ils_navigation = ILSNavigation()
        self.autothrottle = AutothrottleController()
        self.vjoy_throttle: Optional[VJoyThrottleIntegration] = None
        self.fms_reader: Optional[FMSReader] = None
        self.aircraft_adapter: Optional[AircraftCommandAdapter] = None
        self.wind_shear_detector = WindShearDetector()
        self.turbulence_detector = TurbulenceDetector()
        self.audio_system = get_audio_system()
        self.connection_optimizer: Optional[ConnectionOptimizer] = None
        self.connection_monitor: Optional[ConnectionMonitor] = None
        self.speed_calculator = ApproachSpeedCalculator()
        self.autopilot_takeover = AutopilotTakeover()
        self.synthetic_glidepath: Optional[SyntheticGlidepath] = None
        self.approach_config: Optional[ApproachConfig] = None
        self.approach_params: Optional[dict] = None
        self.takeover_initiated: bool = False
        self.phase = ApproachPhase.IDLE
        self.phase_state: Optional[ApproachPhaseState] = None  # State pattern
        self.running = False
        self.use_vjoy = False  # Флаг использования vJoy
        self.use_ils = False  # Флаг использования ILS
        self.use_autothrottle = True  # Флаг использования автоматической тяги
        self.use_custom_autopilot = False  # Флаг использования кастомного автопилота
        self.audio_alerts_enabled = True  # Флаг звуковых предупреждений
        self._last_fms_log_time = 0.0  # Время последнего логирования FMS

        self.structured_logger.info(LogCategory.SYSTEM, "AutoLandSystem initialized")

    def connect(self) -> bool:
        """Подключение к MSFS"""
        if self.telemetry.connect():
            self.control = MSFSControl(self.telemetry.ae, self.telemetry.aq)

            # Инициализация FMS reader
            self.fms_reader = FMSReader(self.telemetry)
            logger.info("FMS reader initialized")

            # Инициализация aircraft adapter
            self.aircraft_adapter = AircraftCommandAdapter(self.control, self.telemetry)
            if self.aircraft_adapter.detect_and_configure():
                profile_info = self.aircraft_adapter.get_profile_info()
                logger.info("Aircraft profile: %s", profile_info.get('name', 'Unknown'))

                # Проверка совместимости
                compat = self.aircraft_adapter.check_compatibility()
                if compat.get('compatible'):
                    if compat.get('limited'):
                        logger.warning("Limited compatibility: %s", compat.get('reason'))
                        logger.info("Fallback: %s", compat.get('fallback'))
                    else:
                        logger.info("Full aircraft compatibility confirmed")
                        self.use_custom_autopilot = True
                else:
                    logger.warning("Aircraft not compatible: %s", compat.get('reason'))
            else:
                logger.warning("Aircraft adapter initialization failed")

            # Предварительная генерация звуковых предупреждений в отдельном потоке
            if self.audio_system.is_available():
                logger.info("Starting audio alerts pregeneration in background...")
                def pregenerate_audio():
                    try:
                        self.audio_system.pregenerate_alerts()
                        logger.info("Audio alerts ready")
                    except Exception as e:
                        logger.warning("Failed to pregenerate audio alerts: %s", e)

                import threading
                threading.Thread(target=pregenerate_audio, daemon=True).start()
            else:
                logger.warning("Audio system not available. Install: pip install gtts pygame")

            # Попытка подключения к vJoy
            if self.virtual_joystick.connect():
                self.use_vjoy = True
                # Инициализация vJoy управления тягой
                self.vjoy_throttle = VJoyThrottleIntegration(self.virtual_joystick)
                self.vjoy_throttle.enable()
                logger.info("AutoLand system connected with vJoy support (including throttle)")
            else:
                self.use_vjoy = False
                logger.info("AutoLand system connected (vJoy not available)")

            # Тестирование методов подключения и выбор оптимального
            logger.info("Testing connection methods to determine optimal approach...")
            self.connection_optimizer = ConnectionOptimizer(
                self.telemetry,
                self.control,
                self.aircraft_adapter.wasm_interface if self.aircraft_adapter else None
            )

            # Запуск тестов
            self.connection_optimizer.test_all_methods()

            # Вывод отчёта
            report = self.connection_optimizer.get_performance_report()
            logger.info("\n%s", report)

            # Сохранение рекомендации
            recommended = self.connection_optimizer.get_recommended_method()
            logger.info("Recommended connection method: %s", recommended)

            # Применение рекомендации
            if recommended == 'L:Vars' and self.aircraft_adapter:
                logger.info("Using L:Vars for optimal performance")
                self.use_custom_autopilot = True
            elif recommended == 'WASM' and self.aircraft_adapter:
                logger.info("Using WASM for optimal performance")
                self.use_custom_autopilot = True
            else:
                logger.info("Using SimConnect (standard method)")
                self.use_custom_autopilot = False

            # Инициализация непрерывного мониторинга
            self.connection_monitor = ConnectionMonitor(
                self.connection_optimizer,
                self.telemetry,
                self.control,
                self.aircraft_adapter.wasm_interface if self.aircraft_adapter else None
            )

            # Запуск мониторинга
            aircraft_info = self.telemetry.get_aircraft_info()
            aircraft_title = aircraft_info.get('title', 'Unknown Aircraft')
            self.connection_monitor.start_monitoring(aircraft_title, recommended)
            logger.info("Connection monitoring started for %s", aircraft_title)

            return True
        return False

    def disconnect(self):
        """Отключение от MSFS"""
        # Сохранение профиля мониторинга перед отключением
        if self.connection_monitor:
            self.connection_monitor.save_profile()
            logger.info("Connection profile saved")

            # Экспорт финальных метрик
            try:
                self.connection_monitor.export_metrics_json('logs/connection_metrics.json')
                logger.info("Connection metrics exported")
            except Exception as e:
                logger.warning("Failed to export metrics: %s", e)

        self.telemetry.disconnect()
        if self.use_vjoy:
            self.virtual_joystick.disconnect()
        logger.info("AutoLand system disconnected")

    def configure_approach(self, config: ApproachConfig):
        """Настройка параметров захода"""
        self.approach_config = config

        # Определение типа захода
        if config.station.type == 'ILS':
            self.use_ils = True
            self.synthetic_glidepath = None
            logger.info("ILS approach configured: %s", config.station.name)
        elif config.station.type in ('VOR', 'NDB', 'LOC'):
            self.use_ils = False
            self.synthetic_glidepath = SyntheticGlidepath(self.navigation, config)
            logger.info("Approach configured: %s - %s (synthetic glidepath active)",
                        config.station.name, config.station.type)
        else:
            self.use_ils = False
            self.synthetic_glidepath = None
            logger.warning("Unsupported approach type '%s' for %s — "
                           "synthetic glidepath disabled",
                           config.station.type, config.station.name)

        # Расчёт параметров скорости захода
        self._calculate_approach_speeds(config)

        # Расчёт рекомендуемой точки передачи управления
        telemetry = self.telemetry.get_all_data()
        weather = telemetry.get('weather', {})

        # WP-6: ApproachConfig.runway_length is in FEET; convert to meters
        runway_length_ft = config.runway_length if hasattr(config, 'runway_length') else 8000
        runway_length_m = runway_length_ft / 3.28084  # feet → meters

        recommended_distance, recommended_altitude = self.autopilot_takeover.get_recommended_takeover_point(
            approach_type=config.station.type,
            runway_length_m=int(runway_length_m),
            weather_conditions=weather,
            decision_height=config.decision_height if config.station.type == 'ILS' else None
        )

        # Обновление конфигурации передачи управления
        takeover_config = TakeoverConfig(
            takeover_distance_nm=recommended_distance,
            takeover_altitude_min=max(1500.0, recommended_altitude - 500) if config.station.type != 'ILS' else 50.0,
            takeover_altitude_max=recommended_altitude + 1000 if config.station.type != 'ILS' else recommended_altitude + 100,
            ils_cat1_dh=200.0,
            ils_cat2_dh=100.0,
            ils_takeover_enabled=True
        )
        self.autopilot_takeover.config = takeover_config

        if config.station.type == 'ILS':
            logger.info("Autopilot takeover configured for ILS: at DH+50ft (%sft AGL)", recommended_altitude)
        else:
            logger.info(f"Autopilot takeover configured: {recommended_distance:.1f}nm, "
                       f"{recommended_altitude:.0f}ft AGL")

    def add_dme_fixes(self, fixes: list):
        """Добавить контрольные точки DME"""
        for fix in fixes:
            self.dme_navigation.add_dme_fix(fix)
        logger.info("Added %s DME fixes", len(fixes))

    def _reset_approach_session_state(self) -> None:
        """Сбросить per-approach состояние для чистого старта нового захода.

        Идемпотентно: безопасно вызывать повторно.
        Не рвёт подключение к MSFS, профили и connection monitor.
        """
        self.takeover_initiated = False
        self._ils_info_logged = False
        self.autopilot_takeover.reset()
        if hasattr(self, 'autothrottle') and hasattr(self.autothrottle, 'reset'):
            self.autothrottle.reset()
        if hasattr(self, 'flare_controller') and hasattr(self.flare_controller, 'reset'):
            self.flare_controller.reset()
        if hasattr(self, 'stabilized_monitor') and hasattr(self.stabilized_monitor, 'reset'):
            self.stabilized_monitor.reset()
        logger.info("Approach session state reset")

    def start_approach(self):
        """Начать заход на посадку"""
        if not self.approach_config:
            logger.error("Approach not configured")
            return

        # Сброс per-approach состояния перед новым заходом
        self._reset_approach_session_state()

        self.running = True
        self.phase = ApproachPhase.INITIAL
        self.phase_state = InitialPhaseState(self)  # Инициализация State pattern
        logger.info("Approach started")

        # Настройка критериев стабилизации
        criteria = StabilizedCriteria(
            speed_target=self.approach_config.approach_speed,
            stabilization_height=1000  # IMC по умолчанию
        )
        self.stabilized_monitor = StabilizedApproachMonitor(criteria)
        logger.info(f"Stabilization criteria: {criteria.stabilization_height}ft AGL, "
                   f"Speed: {criteria.speed_target}kt")

        # Настройка радио
        if self.approach_config.station.type == 'ILS':
            self.control.set_nav_frequency(1, self.approach_config.station.frequency)
            logger.info("ILS frequency set: %s MHz", self.approach_config.station.frequency/1000000)
        elif self.approach_config.station.type == 'LOC':
            self.control.set_nav_frequency(1, self.approach_config.station.frequency)
            logger.info("LOC frequency set: %s MHz", self.approach_config.station.frequency/1000000)
        elif self.approach_config.station.type == 'VOR':
            self.control.set_nav_frequency(1, self.approach_config.station.frequency)
            self.control.set_obs(1, self.approach_config.final_approach_course)
        else:  # NDB
            self.control.set_adf_frequency(self.approach_config.station.frequency)

        # Включение автопилота
        if self.use_custom_autopilot and self.aircraft_adapter:
            self.aircraft_adapter.engage_autopilot()
            self.aircraft_adapter.set_speed(self.approach_config.approach_speed)
            logger.info("Custom autopilot engaged via aircraft adapter")
        else:
            self.control.set_autopilot_master(True)
            self.control.set_airspeed_hold(self.approach_config.approach_speed)
            logger.info("Standard autopilot engaged")

    def stop_approach(self):
        """Остановить заход"""
        self.running = False
        self.phase = ApproachPhase.IDLE
        self.phase_state = None  # Сброс состояния
        logger.info("Approach stopped")

    def get_aircraft_info(self) -> dict:
        """
        Получить информацию о текущем самолёте

        Returns:
            Dict с информацией о самолёте и профиле
        """
        if not self.aircraft_adapter:
            return {'error': 'Aircraft adapter not initialized'}

        aircraft_info = self.aircraft_adapter.aircraft_info or {}
        profile_info = self.aircraft_adapter.get_profile_info()
        compat_info = self.aircraft_adapter.check_compatibility()

        return {
            'aircraft': aircraft_info,
            'profile': profile_info,
            'compatibility': compat_info,
            'using_custom_autopilot': self.use_custom_autopilot
        }

    def get_connection_monitor_status(self) -> dict:
        """
        Получить статус мониторинга подключения

        Returns:
            Dict со статусом мониторинга
        """
        if not self.connection_monitor:
            return {'error': 'Connection monitor not initialized'}

        return {
            'current_method': self.connection_monitor.current_method,
            'flight_phase': self.connection_monitor.current_phase.value,
            'metrics': self.connection_monitor.get_current_metrics(),
            'switch_history': self.connection_monitor.get_switch_history(limit=5),
            'aircraft': self.connection_monitor.aircraft_title,
            'total_switches': len(self.connection_monitor.switch_history)
        }

    def execute_go_around(self):
        """Выполнить уход на второй круг"""
        logger.critical("EXECUTING GO AROUND!")

        # 0. Деактивация autothrottle
        if self.autothrottle.active:
            self.autothrottle.deactivate()
            logger.info("Go-around: Autothrottle deactivated")

        # 1. Полный газ
        if self.vjoy_throttle and self.vjoy_throttle.enabled:
            self.vjoy_throttle.set_throttle(1.0)
        else:
            self.control.set_throttle(1.0)
        logger.info("Go-around: Full throttle")

        # 2. Установка тангажа на набор высоты
        self.control.set_vertical_speed(1500)  # 1500 fpm набор
        logger.info("Go-around: Climb 1500 fpm")

        # 3. Уборка закрылков (постепенно)
        self.control.set_flaps(2)  # Сначала до взлётной конфигурации
        logger.info("Go-around: Flaps to takeoff position")

        # 4. Уборка шасси (после положительного набора)
        # Шасси убираем только если набираем высоту
        logger.info("Go-around: Gear up after positive climb")

        # 5. Если vJoy доступен, центрируем управление
        if self.use_vjoy:
            self.virtual_joystick.center_all_axes()

        # 6. Сброс монитора стабилизации
        self.stabilized_monitor.reset()

        # 7. Остановка захода
        self.stop_approach()

        logger.critical("GO AROUND COMPLETED - Approach aborted")

    def _calculate_approach_speeds(self, config: ApproachConfig):
        """
        Расчёт параметров скорости захода (VREF/VAPP)

        Args:
            config: Конфигурация захода
        """
        try:
            # Получение телеметрии
            telemetry = self.telemetry.get_all_data()
            weather = telemetry.get('weather', {})
            aircraft = telemetry.get('aircraft', {})

            # Расчёт встречного ветра
            headwind = self._calculate_headwind(
                wind_direction=weather.get('wind_direction', 0),
                wind_speed=weather.get('wind_velocity', 0),
                runway_heading=config.final_approach_course
            )

            # Расчёт параметров захода
            self.approach_params = self.speed_calculator.calculate_approach_parameters(
                aircraft_title=aircraft.get('title', 'Unknown'),
                aircraft_weight_kg=aircraft.get('total_weight', 60000),
                runway_length_m=config.runway_length if hasattr(config, 'runway_length') else 2500,
                runway_elevation_ft=config.runway_elevation if hasattr(config, 'runway_elevation') else 0,
                temperature_c=weather.get('ambient_temperature', 15),
                headwind_kt=headwind,
                gust_kt=weather.get('wind_velocity', 0) + weather.get('wind_gust', 0)
            )

            # Логирование результатов
            logger.info("Approach speeds calculated:")
            logger.info("  Aircraft: %s", self.approach_params['aircraft_name'])
            logger.info("  Flaps: %s", self.approach_params['flaps_configuration'])
            logger.info("  VREF: %s kt", self.approach_params['vref'])
            logger.info("  VAPP: %s kt", self.approach_params['vapp'])
            logger.info(f"  Corrections: wind={self.approach_params['wind_correction']:.1f}, "
                       f"gust={self.approach_params['gust_correction']:.1f}, "
                       f"alt={self.approach_params['altitude_correction']:.1f}, "
                       f"temp={self.approach_params['temperature_correction']:.1f}")

            # Проверка веса
            if not self.approach_params['weight_ok']:
                logger.warning(f"Aircraft weight ({self.approach_params['aircraft_weight_kg']:.0f} kg) "
                             f"exceeds max landing weight ({self.approach_params['max_landing_weight_kg']:.0f} kg)")

            # Обновление целевой скорости в конфигурации
            config.approach_speed = self.approach_params['vapp']

        except Exception as e:
            logger.error("Failed to calculate approach speeds: %s", e)
            logger.warning("Using default approach speed from config")

    def _calculate_headwind(self, wind_direction: float, wind_speed: float,
                           runway_heading: float) -> float:
        """
        Расчёт встречного компонента ветра

        Args:
            wind_direction: Направление ветра (градусы)
            wind_speed: Скорость ветра (узлы)
            runway_heading: Курс ВПП (градусы)

        Returns:
            Встречный компонент ветра (узлы, положительный = встречный)
        """
        import math

        wind_angle = abs(wind_direction - runway_heading)
        if wind_angle > 180:
            wind_angle = 360 - wind_angle

        # Встречный компонент
        headwind = wind_speed * math.cos(math.radians(wind_angle))
        return headwind

    def execute_approach(self):
        """Основной цикл выполнения захода"""
        self._log_fms_data()

        consecutive_errors = 0
        max_consecutive_errors = 3

        while self.running:
            try:
                data = self._get_telemetry_with_monitoring()
                self._check_connection_optimization()
                approach_data = self._calculate_approach_data(data)
                self._handle_phase(data, approach_data)
                consecutive_errors = 0
                time.sleep(0.5)

            except KeyboardInterrupt:
                logger.warning("Approach interrupted by user")
                self.stop_approach()
                break

            except Exception as e:
                consecutive_errors += 1
                # Логируем с полным traceback - silent failure на финале опасен
                logger.exception(
                    "Error in approach execution (attempt %d/%d): %s",
                    consecutive_errors, max_consecutive_errors, e
                )

                # Звуковой alert (если доступен) - пилот не услышит просто лог
                if self.audio_alerts_enabled and self.audio_system and self.audio_system.is_available():
                    try:
                        # Используем существующий alert как proxy для критической ошибки
                        self.audio_system.play_alert("SINK_RATE")
                    except Exception:
                        pass

                # Останавливаем заход только после нескольких подряд ошибок,
                # чтобы transient SimConnect glitch не обрывал автолендинг сразу
                if consecutive_errors >= max_consecutive_errors:
                    logger.critical(
                        "Too many consecutive errors (%d) - stopping approach",
                        consecutive_errors
                    )
                    self.stop_approach()
                    break

                # Пауза перед retry, чтобы дать SimConnect восстановиться
                time.sleep(1.0)

    def _get_telemetry_with_monitoring(self) -> dict:
        """Получение телеметрии с мониторингом производительности"""
        start_time = time.perf_counter()
        data = self.telemetry.get_all_data()
        telemetry_time = (time.perf_counter() - start_time) * 1000

        if self.connection_monitor:
            self.connection_monitor.update_metrics(
                method=self.connection_monitor.current_method,
                operation='read',
                time_ms=telemetry_time,
                success=True
            )

            position = data['position']
            speed = data['speed']
            self.connection_monitor.update_flight_phase(
                altitude_agl=position['altitude_agl'],
                ground_speed=speed['ground_speed'],
                vertical_speed=speed['vertical_speed'],
                on_ground=position.get('on_ground', False)
            )

        return data

    def _check_connection_optimization(self):
        """Проверка и переключение метода подключения при необходимости"""
        if not self.connection_monitor:
            return

        better_method = self.connection_monitor.should_switch_method()
        if better_method and better_method != self.connection_monitor.current_method:
            logger.warning(
                f"Switching connection method: "
                f"{self.connection_monitor.current_method} -> {better_method}"
            )
            self.connection_monitor.switch_to_method(
                better_method, "Performance optimization"
            )

            # Применение нового метода
            self.use_custom_autopilot = better_method in ['L:Vars', 'WASM']

        # Периодическое активное тестирование
        if self.connection_monitor.should_perform_active_test():
            logger.info("Performing periodic connection test...")
            self.connection_monitor.perform_active_test()

    def _calculate_approach_data(self, data: dict) -> dict:
        """Расчёт параметров захода (ILS, LOC или VOR/NDB)"""
        position = data['position']
        attitude = data['attitude']
        nav = data['nav']
        ils = data.get('ils', {})

        if self.use_ils and ils.get('nav1_has_localizer'):
            return self.ils_navigation.calculate_ils_approach(data, ils)
        elif (self.approach_config is not None
              and self.approach_config.station.type == 'LOC'):
            # LOC: always route through calculate_loc_approach —
            # it handles signal loss internally (loc_available=False).
            loc_data = self.ils_navigation.calculate_loc_approach(data, ils)
            if not loc_data.get('loc_available', False):
                logger.warning("LOC signal lost — executing go-around")
                self.execute_go_around()
                return None
            return loc_data
        else:
            return self.navigation.calculate_vor_approach(
                {**position, **attitude},
                nav,
                self.approach_config
            )

    def _handle_phase(self, telemetry: dict, approach_data: dict):
        """
        Обработка текущей фазы захода (рефакторинг через State Pattern)

        Сложность снижена с CC=76 до CC=5
        """

        # Fail-closed: signal loss returns None from _calculate_approach_data
        if approach_data is None:
            return

        # Расчёт поправок на ветер
        wind_data = self.wind_correction.apply_wind_corrections(
            telemetry, approach_data, self.approach_config
        )

        # Периодическое логирование FMS данных
        self._log_fms_data()

        # Делегирование обработки к текущему состоянию
        if self.phase_state:
            new_state = self.phase_state.handle(telemetry, approach_data, wind_data)

            # Переход к новому состоянию (если есть)
            if new_state:
                self.phase_state = new_state
                self._update_phase_enum(new_state)

            # Проверка завершения посадки
            if isinstance(self.phase_state, LandingPhaseState):
                radio_height = telemetry['position'].get('radio_height',
                                                         telemetry['position']['altitude_agl'])
                if radio_height < 3:
                    logger.info("TOUCHDOWN!")
                    self.phase = ApproachPhase.COMPLETED
                    self.stop_approach()
                    logger.info("Landing completed!")

    def _log_fms_data(self):
        """Периодическое логирование FMS данных"""
        if self.fms_reader:
            current_time = time.time()
            if current_time - self._last_fms_log_time > 10:
                current_wp = self.fms_reader.get_current_waypoint()
                if current_wp:
                    logger.debug(f"FMS: Next waypoint {current_wp.id}, "
                               f"Distance: {current_wp.distance:.1f}nm, "
                               f"ETE: {current_wp.ete/60:.1f}min")
                self._last_fms_log_time = current_time

    def _update_phase_enum(self, state: ApproachPhaseState):
        """Обновление enum фазы на основе состояния"""
        phase_name = state.get_phase_name()
        if phase_name == "INITIAL":
            self.phase = ApproachPhase.INITIAL
        elif phase_name == "INTERMEDIATE":
            self.phase = ApproachPhase.INTERMEDIATE
        elif phase_name == "FINAL":
            self.phase = ApproachPhase.FINAL
        elif phase_name == "LANDING":
            self.phase = ApproachPhase.LANDING


def main():
    """Главная функция"""
    print("=" * 60)
    print("MSFS AutoLand System - VOR/NDB Approach")
    print("=" * 60)

    # Создание системы
    system = AutoLandSystem()

    # Подключение к MSFS
    print("\nConnecting to MSFS...")
    if not system.connect():
        print("Failed to connect to MSFS. Make sure the simulator is running.")
        return

    print("Connected successfully!")

    # Пример конфигурации захода (нужно заменить на реальные данные)
    example_station = NavStation(
        name="Example VOR",
        frequency=11030000,  # 110.30 MHz в Hz
        latitude=55.5,
        longitude=37.5,
        type='VOR'
    )

    example_config = ApproachConfig(
        station=example_station,
        final_approach_course=270,  # курс посадки
        glideslope_angle=3.0,
        decision_height=200,
        approach_speed=120,
        runway_elevation=500,
        runway_length=8000,  # длина ВПП в футах
        runway_width=150,  # ширина ВПП в футах
        runway_threshold_lat=55.48,  # широта порога ВПП
        runway_threshold_lon=37.52  # долгота порога ВПП
    )

    # Настройка захода
    system.configure_approach(example_config)

    print("\nApproach configured. Press Enter to start approach (or 'q' to quit)...")
    user_input = input()

    if user_input.lower() != 'q':
        print("\nStarting approach...")
        system.start_approach()
        system.execute_approach()

    # Отключение
    system.disconnect()
    print("\nDisconnected. Goodbye!")


if __name__ == "__main__":
    main()
