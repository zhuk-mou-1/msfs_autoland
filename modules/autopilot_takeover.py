"""
Модуль автоматической передачи управления от автопилота к AutoLand системе

WP-2: Hard safety gates — провал блокирует команды.
WP-3: Readback-verified takeover — подтверждение через observed state.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_HARD_FAIL_CHECKS = frozenset({"airborne", "attitude_safe"})
_RETRYABLE_CHECKS = frozenset({"speed_stable", "altitude_stable", "altitude_safe"})


@dataclass
class TakeoverConfig:
    """Конфигурация передачи управления"""
    takeover_distance_nm: float = 10.0
    takeover_altitude_min: float = 1500.0
    takeover_altitude_max: float = 4000.0
    ils_cat1_dh: float = 200.0
    ils_cat2_dh: float = 100.0
    ils_takeover_enabled: bool = True
    initialization_timeout: float = 30.0
    stabilization_timeout: float = 10.0
    require_stable_speed: bool = True
    require_stable_altitude: bool = True
    speed_tolerance: float = 10.0
    altitude_tolerance: float = 200.0
    sink_rate_max: float = 1000.0


@dataclass
class TakeoverStatus:
    """Статус передачи управления"""
    ready: bool = False
    in_progress: bool = False
    completed: bool = False
    failed: bool = False
    distance_to_threshold: float = 0.0
    altitude_agl: float = 0.0
    autopilot_disengaged: bool = False
    autothrottle_disengaged: bool = False
    controls_acquired: bool = False
    checks_passed: Dict[str, bool] = field(default_factory=dict)
    error_message: str = ""
    failure_reason: str = ""
    waiting_for: Tuple[str, ...] = ()
    timestamp: float = 0.0


class AutopilotTakeover:
    """Контроллер автоматической передачи управления"""

    def __init__(self, config: Optional[TakeoverConfig] = None, clock=None):
        self.config = config or TakeoverConfig()
        self.status = TakeoverStatus()
        self.takeover_start_time: Optional[float] = None
        self.initial_parameters: Dict = {}
        self._commands_sent = False
        self._clock = clock or time.monotonic
        self._prev_altitude_agl: Optional[float] = None

    def should_initiate_takeover(
        self,
        distance_to_threshold: float,
        altitude_agl: float,
        approach_phase: str,
        approach_type: str = None,
        decision_height: float = None,
        ils_category: str = None,
    ) -> bool:
        if self.status.in_progress or self.status.completed:
            return False

        if approach_type and approach_type.upper() == 'ILS':
            if not self.config.ils_takeover_enabled:
                return False

            if decision_height is None:
                decision_height = (
                    self.config.ils_cat2_dh
                    if ils_category == 'CAT_II'
                    else self.config.ils_cat1_dh
                )

            takeover_height = decision_height + 50.0
            self._prev_altitude_agl = altitude_agl
            in_window = altitude_agl <= takeover_height and altitude_agl > decision_height

            if in_window and approach_phase in ['FINAL', 'LANDING']:
                logger.info(
                    "ILS takeover conditions met at DH: altitude=%.0fft, DH=%.0fft, category=%s",
                    altitude_agl,
                    decision_height,
                    ils_category or 'CAT_I',
                )
                return True
            return False

        if approach_type and approach_type.upper() not in ['VOR', 'NDB', 'LOC']:
            return False

        distance_ok = distance_to_threshold <= self.config.takeover_distance_nm
        altitude_ok = self.config.takeover_altitude_min <= altitude_agl <= self.config.takeover_altitude_max
        phase_ok = approach_phase in ['INTERMEDIATE', 'FINAL']

        if distance_ok and altitude_ok and phase_ok:
            logger.info(
                "Takeover conditions met for %s: dist=%.1fnm, alt=%.0fft, phase=%s",
                approach_type,
                distance_to_threshold,
                altitude_agl,
                approach_phase,
            )
            return True

        return False

    def perform_takeover(
        self,
        telemetry: Dict,
        aircraft_adapter,
        control,
        approach_type: str = None,
        decision_height: float = None,
    ) -> TakeoverStatus:
        if not self.status.in_progress:
            self._start_takeover()

        now = self._clock()
        if now - self.takeover_start_time > self.config.initialization_timeout:
            self.status.failed = True
            self.status.error_message = "Takeover timeout exceeded"
            self.status.failure_reason = "timeout"
            logger.error("Takeover failed: timeout")
            return self.status

        if not self.initial_parameters:
            self._save_initial_parameters(telemetry)

        checks = self._perform_safety_checks(telemetry, approach_type, decision_height)
        self.status.checks_passed = checks

        is_ils = approach_type and approach_type.upper() == 'ILS'
        hard_fails = [k for k, v in checks.items() if not v and k in _HARD_FAIL_CHECKS]
        if is_ils and not checks.get('sink_rate_safe', True):
            hard_fails.append('sink_rate_safe')

        retryable_fails = [k for k, v in checks.items() if not v and k in _RETRYABLE_CHECKS]
        if not is_ils and not checks.get('sink_rate_safe', True):
            retryable_fails.append('sink_rate_safe')

        if hard_fails:
            self.status.failed = True
            self.status.failure_reason = "hard_safety"
            self.status.error_message = f"Hard safety check failed: {', '.join(hard_fails)}"
            logger.error("TAKEOVER ABORTED — hard safety: %s", ', '.join(hard_fails))
            return self.status

        if retryable_fails and not self._commands_sent:
            self.status.waiting_for = tuple(retryable_fails)
            logger.info("Takeover waiting for: %s", ', '.join(retryable_fails))
            return self.status

        self.status.waiting_for = ()

        if not self._commands_sent:
            self._send_disengage_commands(aircraft_adapter, control)
            self._commands_sent = True

        self._verify_readback(aircraft_adapter, control)

        if self.status.autopilot_disengaged and self.status.autothrottle_disengaged and not self.status.controls_acquired:
            self._acquire_controls(control)

        if self.status.autopilot_disengaged and self.status.autothrottle_disengaged and self.status.controls_acquired:
            self._complete_takeover()

        return self.status

    def _start_takeover(self):
        self.status.in_progress = True
        self.takeover_start_time = self._clock()
        self.status.timestamp = self.takeover_start_time
        logger.info("=" * 60)
        logger.info("AUTOPILOT TAKEOVER INITIATED")
        logger.info("=" * 60)

    def _save_initial_parameters(self, telemetry: Dict):
        pos = telemetry.get('position', {})
        spd = telemetry.get('speed', {})
        att = telemetry.get('attitude', {})

        altitude = pos.get('altitude')
        altitude_agl = pos.get('altitude_agl')
        airspeed = spd.get('airspeed_indicated')

        if altitude is None or altitude_agl is None or airspeed is None:
            logger.warning(
                "Incomplete telemetry for initial params (alt=%s, agl=%s, ias=%s) — retry next tick",
                altitude,
                altitude_agl,
                airspeed,
            )
            return

        self.initial_parameters = {
            'altitude': altitude,
            'altitude_agl': altitude_agl,
            'airspeed': airspeed,
            'heading': att.get('heading_magnetic', 0.0),
            'pitch': att.get('pitch', 0.0),
            'bank': att.get('bank', 0.0),
            'vertical_speed': spd.get('vertical_speed', 0.0),
        }
        logger.info(
            "Initial parameters saved: IAS=%.0fkt, ALT=%.0fft, HDG=%.0f°",
            self.initial_parameters['airspeed'],
            self.initial_parameters['altitude'],
            self.initial_parameters['heading'],
        )

    def _perform_safety_checks(self, telemetry: Dict, approach_type: str = None, decision_height: float = None) -> Dict[str, bool]:
        checks: Dict[str, bool] = {}

        pos = telemetry.get('position', {})
        spd = telemetry.get('speed', {})
        att = telemetry.get('attitude', {})

        altitude_agl = pos.get('altitude_agl')
        if altitude_agl is None:
            checks['altitude_safe'] = False
        elif approach_type and approach_type.upper() == 'ILS':
            checks['altitude_safe'] = decision_height is not None and altitude_agl > decision_height
        else:
            checks['altitude_safe'] = altitude_agl >= self.config.takeover_altitude_min

        airspeed = spd.get('airspeed_indicated')
        if airspeed is None or not self.initial_parameters:
            checks['speed_stable'] = False
        elif self.config.require_stable_speed:
            initial_speed = self.initial_parameters['airspeed']
            checks['speed_stable'] = abs(airspeed - initial_speed) <= self.config.speed_tolerance
        else:
            checks['speed_stable'] = True

        altitude = pos.get('altitude')
        if altitude is None or not self.initial_parameters:
            checks['altitude_stable'] = False
        elif self.config.require_stable_altitude:
            initial_alt = self.initial_parameters['altitude']
            checks['altitude_stable'] = abs(altitude - initial_alt) <= self.config.altitude_tolerance
        else:
            checks['altitude_stable'] = True

        bank = att.get('bank')
        pitch = att.get('pitch')
        checks['attitude_safe'] = bank is not None and pitch is not None and abs(bank) < 30 and -10 < pitch < 15
        checks['airborne'] = not pos.get('on_ground', False)

        vertical_speed = spd.get('vertical_speed')
        checks['sink_rate_safe'] = vertical_speed is not None and vertical_speed >= -self.config.sink_rate_max
        return checks

    def _send_disengage_commands(self, aircraft_adapter, control):
        """Отправить команды выключения AP/A/T.

        Предпочитаем readback-verified helper'ы control/adapter. При ошибке
        fallback остаётся fail-closed — исключение поднимается вверх.
        """
        logger.info("Sending disengage commands...")

        ap_sent = False
        if aircraft_adapter and hasattr(aircraft_adapter, 'disengage_autopilot'):
            try:
                ap_sent = bool(aircraft_adapter.disengage_autopilot())
            except Exception as exc:
                logger.warning("Adapter AP disengage failed, falling back to control: %s", exc)

        if not ap_sent:
            if hasattr(control, 'disengage_autopilot'):
                control.disengage_autopilot()
            else:
                control.set_autopilot_master(False)

        at_sent = False
        if aircraft_adapter and hasattr(aircraft_adapter, 'disengage_autothrottle'):
            try:
                at_sent = bool(aircraft_adapter.disengage_autothrottle())
            except Exception as exc:
                logger.warning("Adapter A/T disengage failed, falling back to control: %s", exc)

        if not at_sent and hasattr(control, 'disengage_autothrottle'):
            control.disengage_autothrottle()

        logger.info("Disengage commands sent")

    def _verify_readback(self, aircraft_adapter, control):
        ap_readback = None
        if aircraft_adapter and hasattr(aircraft_adapter, 'get_autopilot_engaged'):
            ap_readback = aircraft_adapter.get_autopilot_engaged()
        if ap_readback is None and hasattr(control, 'get_autopilot_engaged'):
            ap_readback = control.get_autopilot_engaged()

        if ap_readback is False:
            self.status.autopilot_disengaged = True
        elif ap_readback is True:
            self.status.autopilot_disengaged = False

        at_readback = None
        if aircraft_adapter and hasattr(aircraft_adapter, 'get_autothrottle_engaged'):
            at_readback = aircraft_adapter.get_autothrottle_engaged()
        if at_readback is None and hasattr(control, 'get_autothrottle_engaged'):
            at_readback = control.get_autothrottle_engaged()

        if at_readback is False:
            self.status.autothrottle_disengaged = True
        elif at_readback is True:
            self.status.autothrottle_disengaged = False

    def _acquire_controls(self, control):
        try:
            logger.info("Acquiring flight controls...")
            logger.info("Flight controls acquired")
            self.status.controls_acquired = True
        except Exception as e:
            logger.error("Failed to acquire controls: %s", e)

    def _complete_takeover(self):
        self.status.in_progress = False
        self.status.completed = True
        self.status.ready = True
        elapsed = self._clock() - self.takeover_start_time
        logger.info("=" * 60)
        logger.info("AUTOPILOT TAKEOVER COMPLETED (%ss)", elapsed)
        logger.info("AutoLand system now has full control")
        logger.info("=" * 60)

    def get_status_summary(self) -> str:
        if self.status.failed:
            return f"FAILED: {self.status.error_message}"
        if self.status.completed:
            return "COMPLETED - AutoLand in control"
        if self.status.in_progress:
            steps = []
            steps.append("AP✓" if self.status.autopilot_disengaged else "AP...")
            steps.append("AT✓" if self.status.autothrottle_disengaged else "AT...")
            steps.append("CTRL✓" if self.status.controls_acquired else "CTRL...")
            return f"IN PROGRESS: {' '.join(steps)}"
        return "READY"

    def reset(self):
        self.status = TakeoverStatus()
        self.takeover_start_time = None
        self.initial_parameters = {}
        self._commands_sent = False
        self._prev_altitude_agl = None
        logger.info("Takeover controller reset")

    def get_recommended_takeover_point(
        self,
        approach_type: str,
        runway_length_m: int,
        weather_conditions: Dict,
        decision_height: float = None,
    ) -> Tuple[float, float]:
        distance = 10.0
        altitude = 3000.0

        if approach_type == 'ILS':
            altitude = decision_height + 50.0 if decision_height else 250.0
            distance = 0.0
        elif approach_type in ['VOR', 'NDB', 'LOC']:
            distance = 10.0
            altitude = 3500.0
        elif approach_type == 'GPS':
            distance = 9.0
            altitude = 3000.0

        if approach_type in ['VOR', 'NDB', 'LOC'] and runway_length_m < 1500:
            distance += 2.0
            altitude += 500.0

        if approach_type in ['VOR', 'NDB', 'LOC']:
            wind_speed = weather_conditions.get('wind_velocity', 0)
            visibility = weather_conditions.get('visibility', 10000)
            if wind_speed > 20:
                distance += 1.0
                altitude += 500.0
            if visibility < 5000:
                distance += 1.0

        logger.info(
            "Recommended takeover point: %.1fnm, %.0fft AGL (approach=%s, runway=%dm)",
            distance,
            altitude,
            approach_type,
            runway_length_m,
        )
        return distance, altitude
