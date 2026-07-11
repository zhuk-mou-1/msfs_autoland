"""
Модуль фаз захода на посадку с использованием паттерна State
Рефакторинг main.py::_handle_phase() для снижения цикломатической сложности
"""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from modules.control_ownership import ControlOwner, compute_ownership

if TYPE_CHECKING:
    from main import AutoLandSystem

logger = logging.getLogger(__name__)


class ApproachPhaseState(ABC):
    """Базовый класс для состояния фазы захода"""

    def __init__(self, system: 'AutoLandSystem'):
        self.system = system

    @abstractmethod
    def handle(self, telemetry: dict, approach_data: dict, wind_data: dict) -> Optional['ApproachPhaseState']:
        """
        Обработка текущей фазы

        Args:
            telemetry: Телеметрия самолёта
            approach_data: Данные захода
            wind_data: Данные о ветре

        Returns:
            Новое состояние или None если остаёмся в текущем
        """
        pass

    @abstractmethod
    def get_phase_name(self) -> str:
        """Получить название фазы"""
        pass


class InitialPhaseState(ApproachPhaseState):
    """Начальная фаза: перехват курса"""

    def get_phase_name(self) -> str:
        return "INITIAL"

    def handle(self, telemetry: dict, approach_data: dict, wind_data: dict) -> Optional[ApproachPhaseState]:
        """Обработка начальной фазы"""

        distance = approach_data['distance_to_station']
        cross_track = approach_data['cross_track_error']
        dme_distance = telemetry['nav'].get('nav1_dme_distance', distance)

        # Проверка точности DME
        dme_check = self.system.dme_navigation.check_dme_accuracy(dme_distance, distance)
        if dme_check['status'] == 'CRITICAL':
            logger.warning("DME accuracy issue: using calculated distance")
            dme_distance = distance

        logger.info("INITIAL: DME %.1fnm, XTE %.1f°, Wind: %.0fkt from %.0f°, Crosswind: %.1fkt",
                   dme_distance, cross_track, wind_data['wind_speed'],
                   wind_data['wind_direction'], wind_data['crosswind'])

        # Установка курса с учётом ветра
        corrected_heading = wind_data['corrected_heading']
        self.system.control.set_heading_hold(int(corrected_heading))

        # Переход к промежуточной фазе при перехвате курса
        if approach_data['on_course'] and dme_distance < 15:
            logger.info("Transitioning to INTERMEDIATE phase")
            return IntermediatePhaseState(self.system)

        return None


class IntermediatePhaseState(ApproachPhaseState):
    """Промежуточная фаза: следование по курсу, снижение"""

    def get_phase_name(self) -> str:
        return "INTERMEDIATE"

    def handle(self, telemetry: dict, approach_data: dict, wind_data: dict) -> Optional[ApproachPhaseState]:
        """Обработка промежуточной фазы"""

        distance = approach_data['distance_to_station']
        altitude = telemetry['position']['altitude']
        altitude_agl = telemetry['position']['altitude_agl']
        required_alt = approach_data['required_altitude']
        position = telemetry['position']

        dme_distance = telemetry['nav'].get('nav1_dme_distance', distance)

        # Проверка точности DME
        dme_check = self.system.dme_navigation.check_dme_accuracy(dme_distance, distance)
        if dme_check['status'] == 'CRITICAL':
            logger.warning("DME accuracy issue: using calculated distance")
            dme_distance = distance

        # Проверка необходимости передачи управления от автопилота
        if not self.system.takeover_initiated:
            self._check_autopilot_takeover(position, altitude_agl, telemetry)

        # Выполнение передачи управления (если инициирована)
        if self.system.takeover_initiated and not self.system.autopilot_takeover.status.completed:
            if not self._perform_takeover(telemetry):
                return None  # Takeover failed, go around executed

        # Проверка высоты на контрольных точках DME
        fix_check = self.system.dme_navigation.check_altitude_at_fix(dme_distance, altitude)
        fix_info = ""
        if fix_check['has_fix']:
            fix_info = f", Fix: {fix_check['fix'].name} ({fix_check['status']}, {fix_check['deviation']:+d}ft)"

        logger.info("INTERMEDIATE: DME %.1fnm, Alt %.0fft (req %.0fft), Headwind: %.1fkt%s",
                   dme_distance, altitude, required_alt, wind_data['headwind'], fix_info)

        # Установка скорректированного курса (только если передача управления завершена)
        if self.system.autopilot_takeover.status.completed:
            corrected_heading = wind_data['corrected_heading']
            self.system.control.set_heading_hold(int(corrected_heading))

            # Снижение до глиссады с учётом встречного ветра
            if altitude > required_alt + 200:
                vs = -500
                self.system.control.set_vertical_speed(vs)

        # Переход к финальной фазе (только если передача управления завершена)
        if distance < 8 and abs(altitude - required_alt) < 300:
            if not self.system.autopilot_takeover.status.completed:
                logger.warning("Waiting for takeover completion before transitioning to FINAL")
            else:
                # Активация автоматической тяги для фазы FINAL
                if self.system.use_autothrottle:
                    self.system.autothrottle.activate(initial_throttle=0.5)
                    logger.info("Autothrottle activated for FINAL phase")

                logger.info("Transitioning to FINAL phase")
                return FinalPhaseState(self.system)

        return None

    def _check_autopilot_takeover(self, position: dict, altitude_agl: float, telemetry: dict):
        """Проверка необходимости передачи управления от автопилота"""

        distance_to_threshold = self.system.navigation.calculate_distance_to_threshold(
            position['latitude'],
            position['longitude'],
            self.system.approach_config
        )

        # Определение категории ILS (если применимо)
        ils_category = None
        if self.system.approach_config.station.type == 'ILS':
            if self.system.approach_config.decision_height <= 100:
                ils_category = 'CAT_II'
            else:
                ils_category = 'CAT_I'

        # Информационное сообщение для ILS заходов (только один раз)
        if self.system.approach_config.station.type == 'ILS' and distance_to_threshold <= 10.0:
            if not hasattr(self.system, '_ils_info_logged'):
                logger.info("=" * 60)
                logger.info("ILS %s APPROACH DETECTED", ils_category)
                logger.info("Decision Height: %s ft", self.system.approach_config.decision_height)
                logger.info("Aircraft autopilot will handle approach to DH")
                logger.info("AutoLand will take control at DH+50ft for flare")
                logger.info("=" * 60)
                self.system._ils_info_logged = True

        if self.system.autopilot_takeover.should_initiate_takeover(
            distance_to_threshold=distance_to_threshold,
            altitude_agl=altitude_agl,
            approach_phase="INTERMEDIATE",
            approach_type=self.system.approach_config.station.type,
            decision_height=self.system.approach_config.decision_height,
            ils_category=ils_category
        ):
            approach_type = self.system.approach_config.station.type

            if approach_type == 'ILS':
                logger.warning("=" * 60)
                logger.warning("INITIATING AUTOPILOT TAKEOVER (ILS %s - AT DECISION HEIGHT)", ils_category)
                logger.warning("Altitude AGL: %s ft", altitude_agl)
                logger.warning("Decision Height: %s ft", self.system.approach_config.decision_height)
                logger.warning("Taking control for automatic flare and landing")
                logger.warning("=" * 60)
            elif approach_type == 'LOC':
                logger.warning("=" * 60)
                logger.warning("INITIATING AUTOPILOT TAKEOVER (LOC APPROACH)")
                logger.warning("Distance to threshold: %s NM", distance_to_threshold)
                logger.warning("Altitude AGL: %s ft", altitude_agl)
                logger.warning("LOC: lateral via localizer, vertical via synthetic glidepath")
                logger.warning("=" * 60)
            else:
                logger.warning("=" * 60)
                logger.warning("INITIATING AUTOPILOT TAKEOVER (%s APPROACH)", approach_type)
                logger.warning("Distance to threshold: %s NM", distance_to_threshold)
                logger.warning("Altitude AGL: %s ft", altitude_agl)
                logger.warning("VOR/NDB approach requires manual control")
                logger.warning("=" * 60)

            self.system.takeover_initiated = True

    def _perform_takeover(self, telemetry: dict) -> bool:
        """
        Выполнение передачи управления

        Returns:
            True если успешно, False если ошибка (go around executed)
        """
        takeover_status = self.system.autopilot_takeover.perform_takeover(
            telemetry=telemetry,
            aircraft_adapter=self.system.aircraft_adapter,
            control=self.system.control,
            approach_type=self.system.approach_config.station.type,
            decision_height=self.system.approach_config.decision_height,
        )

        # Логирование прогресса
        status_summary = self.system.autopilot_takeover.get_status_summary()
        logger.info("Takeover status: %s", status_summary)

        # Проверка на ошибку
        if takeover_status.failed:
            logger.critical("TAKEOVER FAILED: %s", takeover_status.error_message)
            logger.critical("Aborting approach - GO AROUND")
            self.system.execute_go_around()
            return False

        return True


class FinalPhaseState(ApproachPhaseState):
    """Финальная фаза: точное следование по глиссаде"""

    def get_phase_name(self) -> str:
        return "FINAL"

    def handle(self, telemetry: dict, approach_data: dict, wind_data: dict) -> Optional[ApproachPhaseState]:
        """Обработка финальной фазы"""

        altitude_agl = telemetry['position']['altitude_agl']
        radio_height = telemetry['position'].get('radio_height', altitude_agl)
        position = telemetry['position']

        # Проверка передачи управления для ILS на Decision Height
        if not self.system.takeover_initiated and self.system.approach_config.station.type == 'ILS':
            self._check_ils_takeover(position, altitude_agl, radio_height, telemetry)

        # Выполнение передачи управления (если инициирована)
        if self.system.takeover_initiated and not self.system.autopilot_takeover.status.completed:
            if not self._perform_takeover(telemetry):
                return None  # Takeover failed

        # Проверка сдвига ветра и турбулентности
        if not self._check_weather_conditions(telemetry, wind_data, radio_height):
            return None  # Go around executed

        # WP-5 / FIX-4: compute control ownership
        self._ownership = compute_ownership(
            phase="FINAL",
            confirmed_takeover=self.system.autopilot_takeover.status.completed,
            use_vjoy=self.system.use_vjoy,
            vjoy_ready=(hasattr(self.system.virtual_joystick, 'enabled')
                        and self.system.virtual_joystick.enabled),
            use_autothrottle=self.system.use_autothrottle,
        )

        # Расчёт и логирование параметров захода
        self._log_approach_parameters(telemetry, approach_data, wind_data, radio_height)

        # Управление самолётом
        self._control_aircraft(telemetry, wind_data)

        # Управление тягой
        self._control_throttle(telemetry, wind_data)

        # Проверка стабилизации
        if not self._check_stabilization(telemetry, approach_data, wind_data, radio_height):
            return None  # Go around executed

        # Выпуск закрылков и шасси
        self._deploy_flaps_and_gear(radio_height)

        # Переход к посадке
        if radio_height < self.system.approach_config.decision_height:
            # WP-4 DH guard: ниже DH без confirmed takeover → go-around
            if (self.system.use_ils and
                    not self.system.autopilot_takeover.status.completed):
                logger.critical(
                    "DH GUARD: Below DH (%.0fft) without confirmed takeover "
                    "- GO AROUND", radio_height)
                self.system.execute_go_around()
                return None

            if not self._check_final_stabilization(radio_height):
                return None  # Go around executed

            # Деактивация autothrottle перед фазой LANDING
            if self.system.autothrottle.active:
                self.system.autothrottle.deactivate()
                logger.info("Autothrottle deactivated for LANDING phase")

            logger.info("Transitioning to LANDING phase")
            return LandingPhaseState(self.system)

        return None

    def _check_ils_takeover(self, position: dict, altitude_agl: float, radio_height: float, telemetry: dict):
        """Проверка передачи управления для ILS"""

        distance_to_threshold = self.system.navigation.calculate_distance_to_threshold(
            position['latitude'],
            position['longitude'],
            self.system.approach_config
        )

        ils_category = 'CAT_II' if self.system.approach_config.decision_height <= 100 else 'CAT_I'

        if self.system.autopilot_takeover.should_initiate_takeover(
            distance_to_threshold=distance_to_threshold,
            altitude_agl=altitude_agl,
            approach_phase="FINAL",
            approach_type=self.system.approach_config.station.type,
            decision_height=self.system.approach_config.decision_height,
            ils_category=ils_category
        ):
            logger.warning("=" * 60)
            logger.warning("INITIATING AUTOPILOT TAKEOVER (ILS %s - AT DECISION HEIGHT)", ils_category)
            logger.warning("Radio Height: %s ft", radio_height)
            logger.warning("Decision Height: %s ft", self.system.approach_config.decision_height)
            logger.warning("Taking control for automatic flare and landing")
            logger.warning("=" * 60)
            self.system.takeover_initiated = True

    def _perform_takeover(self, telemetry: dict) -> bool:
        """Выполнение передачи управления"""

        takeover_status = self.system.autopilot_takeover.perform_takeover(
            telemetry=telemetry,
            aircraft_adapter=self.system.aircraft_adapter,
            control=self.system.control,
            approach_type=self.system.approach_config.station.type,
            decision_height=self.system.approach_config.decision_height,
        )

        status_summary = self.system.autopilot_takeover.get_status_summary()
        logger.info("Takeover status: %s", status_summary)

        if takeover_status.failed:
            logger.critical("TAKEOVER FAILED: %s", takeover_status.error_message)
            logger.critical("Aborting approach - GO AROUND")
            self.system.execute_go_around()
            return False

        return True

    def _check_weather_conditions(self, telemetry: dict, wind_data: dict, radio_height: float) -> bool:
        """
        Проверка погодных условий (сдвиг ветра, турбулентность)

        Returns:
            False если нужен go around
        """
        # Проверка сдвига ветра
        wind_shear_alert = self.system.wind_shear_detector.update(telemetry, wind_data)
        if wind_shear_alert:
            if wind_shear_alert.severity in ['CRITICAL', 'WARNING']:
                logger.critical(f"WIND SHEAR {wind_shear_alert.severity}: {wind_shear_alert.type} - "
                              f"Magnitude: {wind_shear_alert.magnitude:.1f} - "
                              f"{wind_shear_alert.recommendation}")

                if self.system.audio_alerts_enabled:
                    from modules.audio_alerts import play_windshear_alert
                    play_windshear_alert(wind_shear_alert.severity)

        # Проверка турбулентности
        turbulence_alert = self.system.turbulence_detector.update(telemetry)
        if turbulence_alert and turbulence_alert.intensity != 'SMOOTH':
            logger.warning("TURBULENCE %s (%s): G-std: %.3f, Bank osc: %.1f° - %s",
                         turbulence_alert.intensity, turbulence_alert.type,
                         turbulence_alert.g_force_std, turbulence_alert.bank_oscillation,
                         turbulence_alert.recommendation)

        # При критическом сдвиге ветра - автоматический уход на второй круг
        if wind_shear_alert and wind_shear_alert.severity == 'CRITICAL' and radio_height < 500:
            logger.critical("CRITICAL WIND SHEAR BELOW 500ft - EXECUTING GO AROUND!")
            self.system.execute_go_around()
            return False

        return True

    def _log_approach_parameters(self, telemetry: dict, approach_data: dict, wind_data: dict, radio_height: float):
        """Логирование параметров захода"""

        distance_to_threshold = self.system.navigation.calculate_distance_to_threshold(
            telemetry['position']['latitude'],
            telemetry['position']['longitude'],
            self.system.approach_config
        )

        ground_speed = telemetry['speed']['ground_speed']
        required_landing_dist = self.system.navigation.calculate_landing_distance(
            ground_speed,
            headwind=wind_data['headwind']
        )
        runway_check = self.system.navigation.check_runway_length(
            required_landing_dist,
            self.system.approach_config.runway_length
        )

        logger.info("FINAL: Distance to threshold %.2fnm, Radio height %.0fft, "
                   "Crosswind: %.1fkt, Crab: %.1f°, VS: %.0f fpm, "
                   "Runway: %s (%.0fft margin)",
                   distance_to_threshold, radio_height, wind_data['crosswind'],
                   wind_data['drift_angle'], wind_data['corrected_vs'],
                   runway_check['status'], runway_check['remaining'])

        if runway_check['status'] == 'CRITICAL':
            logger.warning("CRITICAL: Runway too short! Required: %.0fft, Available: %dft",
                         runway_check['required_with_margin'], runway_check['runway_length'])

    def _control_aircraft(self, telemetry: dict, wind_data: dict):
        """Управление самолётом (курс, крен, тангаж)"""

        ownership = getattr(self, '_ownership', None)
        corrected_heading = wind_data['corrected_heading']

        # AP commands only when roll/pitch owner is AIRCRAFT_AP
        if ownership is None or ownership.roll == ControlOwner.AIRCRAFT_AP:
            self.system.control.set_heading_hold(int(corrected_heading))

        # vJoy commands only when roll/pitch owner is EXTERNAL
        if (self.system.use_vjoy and
                ownership is not None and
                ownership.roll == ControlOwner.EXTERNAL):
            current_bank = telemetry['attitude']['bank']
            current_pitch = telemetry['attitude']['pitch']
            current_heading = telemetry['attitude']['heading_magnetic']

            target_bank = self.system.virtual_joystick.calculate_heading_correction(
                current_heading, corrected_heading, current_bank, max_bank=10.0
            )

            aileron_input = self.system.virtual_joystick.calculate_bank_correction(
                current_bank, target_bank, max_input=0.2
            )

            target_pitch = 2.5
            elevator_input = self.system.virtual_joystick.calculate_pitch_correction(
                current_pitch, target_pitch, max_input=0.15
            )

            self.system.virtual_joystick.apply_control_inputs(
                aileron=aileron_input,
                elevator=elevator_input,
                rudder=0.0
            )

        # Вертикальная скорость — only if pitch owner is AP
        if ownership is None or ownership.pitch == ControlOwner.AIRCRAFT_AP:
            if self.system.synthetic_glidepath is not None:
                vs = self.system.synthetic_glidepath.compute_target_vs(
                    telemetry, wind_data['corrected_vs']
                )
            else:
                vs = wind_data['corrected_vs']
            self.system.control.set_vertical_speed(-int(vs))

    def _control_throttle(self, telemetry: dict, wind_data: dict):
        """Управление тягой — с учётом ownership (WP-5)."""
        ownership = getattr(self, '_ownership', None)

        if self.system.use_autothrottle and self.system.autothrottle.active:
            # Определение целевой скорости
            if self.system.approach_params:
                target_speed = self.system.approach_params['vapp']
            else:
                target_speed = self.system.approach_config.approach_speed

            # Получение веса самолёта
            aircraft_weight = self._get_aircraft_weight(telemetry)

            throttle_data = self.system.autothrottle.calculate_throttle(
                telemetry,
                target_speed,
                wind_data,
                aircraft_weight
            )

            # Применение тяги — only if throttle owner is AIRCRAFT_AP
            if ownership is None or ownership.throttle == ControlOwner.AIRCRAFT_AP:
                if throttle_data.get('asymmetric_mode', False):
                    engine_throttles = throttle_data.get('engine_throttles', {})
                    if engine_throttles:
                        logger.warning("Applying asymmetric thrust: %s", engine_throttles)
                        self.system.control.set_throttle_asymmetric(engine_throttles)
                    else:
                        self.system.control.set_throttle(throttle_data['throttle'])
                else:
                    if self.system.vjoy_throttle and self.system.vjoy_throttle.enabled:
                        self.system.vjoy_throttle.set_throttle(throttle_data['throttle'])
                    else:
                        self.system.control.set_throttle(throttle_data['throttle'])

                if throttle_data.get('is_stable', False):
                    logger.debug("Autothrottle: %.1f%% (stable)", throttle_data['throttle']*100)
        else:
            # No autothrottle — EXTERNAL owns throttle if vJoy ready
            if (ownership is not None and
                    ownership.throttle == ControlOwner.EXTERNAL):
                pass  # vJoy throttle handled externally
            else:
                self.system.control.set_throttle(0.5)

    def _get_aircraft_weight(self, telemetry: dict) -> float:
        """Получение веса самолёта"""

        if self.system.approach_params:
            aircraft_weight = self.system.approach_params['aircraft_weight_kg']
            logger.debug("Using aircraft weight from VAPP calculator: %s kg", aircraft_weight)
            return aircraft_weight
        elif hasattr(self.system.approach_config, 'aircraft_weight'):
            return self.system.approach_config.aircraft_weight
        else:
            weight_data = telemetry.get('weight', {})
            if weight_data and 'total_weight' in weight_data:
                aircraft_weight = weight_data['total_weight']
                logger.debug("Using aircraft weight from SimConnect: %s lbs", aircraft_weight)
                return aircraft_weight

        return 5000.0  # Default

    def _check_stabilization(self, telemetry: dict, approach_data: dict, wind_data: dict, radio_height: float) -> bool:
        """
        Проверка стабилизированного захода

        Returns:
            False если нужен go around
        """
        stabilization_check = self.system.stabilized_monitor.check_stabilization(
            telemetry, approach_data, wind_data
        )

        if stabilization_check['checked']:
            status = self.system.stabilized_monitor.get_status_summary()
            logger.info("Stabilization: %s", status)

            if not stabilization_check['is_stabilized']:
                logger.warning("Violations:")
                for violation in stabilization_check['violations']:
                    logger.warning("  - %s", violation)

        self.system.stabilized_monitor.check_continuous_monitoring(telemetry, approach_data)

        if self.system.stabilized_monitor.should_go_around(radio_height):
            logger.critical("GO AROUND INITIATED!")
            self.system.execute_go_around()
            return False

        return True

    def _deploy_flaps_and_gear(self, radio_height: float):
        """Выпуск закрылков и шасси (идемпотентно, без спама SimConnect)"""

        # Состояние храним на phase state — чтобы не дёргать SimConnect каждые 0.5s
        if not hasattr(self, '_flaps_2_deployed'):
            self._flaps_2_deployed = False
        if not hasattr(self, '_flaps_3_deployed'):
            self._flaps_3_deployed = False
        if not hasattr(self, '_gear_deployed'):
            self._gear_deployed = False

        if radio_height < 2000 and not self._flaps_2_deployed:
            self.system.control.set_flaps(2)
            self._flaps_2_deployed = True
            logger.info("Flaps 2 deployed at %.0fft AGL", radio_height)

        if radio_height < 1500:
            if not self._gear_deployed:
                self.system.control.set_gear(True)
                self._gear_deployed = True
                logger.info("Gear DOWN at %.0fft AGL", radio_height)
            if not self._flaps_3_deployed:
                self.system.control.set_flaps(3)
                self._flaps_3_deployed = True
                logger.info("Flaps 3 deployed at %.0fft AGL", radio_height)

    def _check_final_stabilization(self, radio_height: float) -> bool:
        """
        Финальная проверка стабилизации перед посадкой

        Returns:
            False если нужен go around
        """
        if not self.system.stabilized_monitor.is_stabilized and radio_height > 200:
            logger.warning("Not stabilized at decision height - GO AROUND")
            self.system.execute_go_around()
            return False

        return True


class LandingPhaseState(ApproachPhaseState):
    """Фаза посадки с автоматическим выравниванием"""

    def get_phase_name(self) -> str:
        return "LANDING"

    def handle(self, telemetry: dict, approach_data: dict, wind_data: dict) -> Optional[ApproachPhaseState]:
        """Обработка фазы посадки"""

        # Защищённое чтение ключевых параметров - flare математика безопасна только с валидными данными
        position_data = telemetry.get('position', {})
        attitude_data = telemetry.get('attitude', {})
        speed_data = telemetry.get('speed', {})

        altitude_agl = position_data.get('altitude_agl')
        radio_height = position_data.get('radio_height', altitude_agl)
        current_pitch = attitude_data.get('pitch')
        current_vs = speed_data.get('vertical_speed')
        ground_speed = speed_data.get('ground_speed', 0)

        # Если ключевые параметры отсутствуют - не запускаем flare (опасно при ложных данных)
        if altitude_agl is None or current_pitch is None or current_vs is None:
            logger.error("LANDING phase: missing critical telemetry (alt_agl=%s, pitch=%s, vs=%s) - holding",
                         altitude_agl, current_pitch, current_vs)
            return None

        # Проверка начала выравнивания
        if self.system.flare_controller.should_start_flare(radio_height, current_vs):
            adjusted_config = self.system.flare_controller.adjust_for_wind(
                wind_data['headwind'],
                self.system.flare_controller.config
            )
            self.system.flare_controller.config = adjusted_config
            self.system.flare_controller.start_flare(radio_height)

        # Расчёт параметров выравнивания
        flare_params = self.system.flare_controller.calculate_flare_parameters(
            radio_height, current_pitch, current_vs, ground_speed,
            engine_failure_detector=self.system.engine_failure_detector if hasattr(self.system, 'engine_failure_detector') else None
        )

        flare_status = self.system.flare_controller.get_flare_status(radio_height)
        logger.info("LANDING: %s, Pitch %s°, VS %sfpm", flare_status, current_pitch, current_vs)

        if flare_params['flare_active']:
            self._perform_active_flare(flare_params, current_pitch, current_vs, telemetry)
        else:
            self._maintain_glideslope(radio_height, flare_params)

        # Завершение посадки
        if radio_height < 3:
            logger.info("TOUCHDOWN!")
            return None  # Завершение, система остановит заход

        return None

    def _get_target_speed(self) -> float:
        """Получение целевой скорости для выравнивания"""

        if self.system.approach_params:
            target_speed = self.system.approach_params['vref']
            logger.debug("Landing phase: target speed = VREF %s kt", target_speed)
            return target_speed
        else:
            return self.system.approach_config.approach_speed - 5

    def _perform_active_flare(self, flare_params: dict, current_pitch: float, current_vs: float, telemetry: dict):
        """Выполнение активного выравнивания"""

        target_pitch = flare_params['target_pitch']

        # Коррекция тангажа на основе вертикальной скорости
        vs_correction = self.system.flare_controller.calculate_vs_correction(
            current_vs, flare_params['target_vs']
        )
        target_pitch += vs_correction

        # Управление через vJoy (если доступен)
        if self.system.use_vjoy:
            elevator_input = self.system.flare_controller.calculate_pitch_input(
                current_pitch, target_pitch
            )
            self.system.virtual_joystick.set_elevator(elevator_input)
            logger.debug("Flare vJoy: elevator=%s", elevator_input)

        # Управление газом с поддержкой асимметричной тяги
        if flare_params.get('has_engine_failure', False):
            # Асимметричная тяга при отказе двигателя
            engine_throttles = flare_params.get('engine_throttles', {})
            if engine_throttles:
                logger.warning(f"Flare with engine failure: applying asymmetric thrust {engine_throttles}")
                self.system.control.set_throttle_asymmetric(engine_throttles)

                # Компенсация рулём направления
                if hasattr(self.system, 'rudder_compensation') and self.system.rudder_compensation:
                    current_speed = telemetry['speed'].get('airspeed_indicated', 140)
                    self.system.rudder_compensation.apply_compensation(
                        engine_throttles,
                        current_speed,
                        self.system.control
                    )

                    # Компенсация крена элеронами
                    if hasattr(self.system, 'aileron_compensation') and self.system.aileron_compensation:
                        rudder_deflection = self.system.rudder_compensation.current_rudder
                        self.system.aileron_compensation.apply_compensation(
                            engine_throttles,
                            rudder_deflection,
                            current_speed,
                            self.system.control
                        )
            else:
                # Fallback на симметричную тягу
                self.system.control.set_throttle(flare_params['throttle'])
        else:
            # Симметричная тяга - нормальный режим
            self.system.control.set_throttle(flare_params['throttle'])

        # Логирование прогресса
        if flare_params['progress'] > 0.1:
            logger.info("Flare progress: %.0f%%, Target pitch: %.1f°, Target VS: %.0ffpm",
                       flare_params['progress']*100, target_pitch, flare_params['target_vs'])

    def _maintain_glideslope(self, radio_height: float, flare_params: dict):
        """Поддержание глиссады до начала выравнивания"""

        if radio_height < 50:
            throttle = 0.3 * (radio_height / 50.0)

            # Проверка на отказ двигателей
            if flare_params.get('has_engine_failure', False):
                engine_throttles = flare_params.get('engine_throttles', {})
                if engine_throttles:
                    # Применяем асимметричную тягу
                    asymmetric_throttles = {
                        idx: throttle * (engine_throttles[idx] / flare_params['throttle'])
                        for idx in engine_throttles.keys()
                    }
                    self.system.control.set_throttle_asymmetric(asymmetric_throttles)
                else:
                    self.system.control.set_throttle(throttle)
            else:
                self.system.control.set_throttle(throttle)
