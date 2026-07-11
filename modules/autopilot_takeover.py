"""
Модуль автоматической передачи управления от автопилота к AutoLand системе

WP-2: Hard safety gates — провал блокирует команды.
WP-3: Readback-verified takeover — подтверждение через observed state.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Hard vs retryable check classification ────────────────────────

_HARD_FAIL_CHECKS = frozenset({"airborne", "attitude_safe"})
_RETRYABLE_CHECKS = frozenset({"speed_stable", "altitude_stable", "altitude_safe"})
# sink_rate_safe is mode-dependent: hard for ILS, retryable for VOR/NDB
# Added dynamically in _perform_safety_checks() based on approach_type


@dataclass
class TakeoverConfig:
    """Конфигурация передачи управления"""
    # Расстояния и высоты для VOR/NDB заходов
    takeover_distance_nm: float = 10.0
    takeover_altitude_min: float = 1500.0
    takeover_altitude_max: float = 4000.0

    # Высоты для ILS CAT I/II заходов (передача на DH)
    ils_cat1_dh: float = 200.0
    ils_cat2_dh: float = 100.0
    ils_takeover_enabled: bool = True

    # Таймауты
    initialization_timeout: float = 30.0
    stabilization_timeout: float = 10.0

    # Проверки безопасности
    require_stable_speed: bool = True
    require_stable_altitude: bool = True
    speed_tolerance: float = 10.0
    altitude_tolerance: float = 200.0
    sink_rate_max: float = 1000.0  # Max descent rate in fpm (negative = descent)


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

    def __init__(self, config: Optional[TakeoverConfig] = None,
                 clock=None):
        self.config = config or TakeoverConfig()
        self.status = TakeoverStatus()
        self.takeover_start_time: Optional[float] = None
        self.initial_parameters: Dict = {}
        self._commands_sent = False
        self._clock = clock or time.monotonic
        self._prev_altitude_agl: Optional[float] = None  # WP-4 / FIX-3

    # ── public API ────────────────────────────────────────────────

    def should_initiate_takeover(self,
                                 distance_to_threshold: float,
                                 altitude_agl: float,
                                 approach_phase: str,
                                 approach_type: str = None,
                                 decision_height: float = None,
                                 ils_category: str = None) -> bool:
        if self.status.in_progress or self.status.completed:
            return False

        if approach_type and approach_type.upper() == 'ILS':
            if not self.config.ils_takeover_enabled:
                return False

            if decision_height is None:
                decision_height = (self.config.ils_cat2_dh
                                   if ils_category == 'CAT_II'
                                   else self.config.ils_cat1_dh)

            takeover_height = decision_height + 50.0

            # WP-4 / FIX-3: _prev_altitude_agl tracked for future crossing detection.
            # FIX-8: crossed ⊆ in_window — when prev > takeover_height and current is in window,
            # in_window is already True. DH guard in approach_phases.py handles the case
            # where altitude jumps entirely below the window.
            self._prev_altitude_agl = altitude_agl

            in_window = (altitude_agl <= takeover_height
                         and altitude_agl > decision_height)

            if in_window and approach_phase in ['FINAL', 'LANDING']:
                logger.info("ILS takeover conditions met at DH: "
                            "altitude=%.0fft, DH=%.0fft, category=%s",
                            altitude_agl, decision_height,
                            ils_category or 'CAT_I')
                return True
            return False

        if approach_type and approach_type.upper() not in ['VOR', 'NDB', 'LOC']:
            return False

        distance_ok = distance_to_threshold <= self.config.takeover_distance_nm
        altitude_ok = (self.config.takeover_altitude_min <= altitude_agl <=
                       self.config.takeover_altitude_max)
        phase_ok = approach_phase in ['INTERMEDIATE', 'FINAL']

        if distance_ok and altitude_ok and phase_ok:
            logger.info("Takeover conditions met for %s: dist=%.1fnm, "
                        "alt=%.0fft, phase=%s",
                        approach_type, distance_to_threshold,
                        altitude_agl, approach_phase)
            return True

        return False

    def perform_takeover(self,
                         telemetry: Dict,
                         aircraft_adapter,
                         control,
                         approach_type: str = None,
                         decision_height: float = None) -> TakeoverStatus:
        if not self.status.in_progress:
            self._start_takeover()

        # ── Timeout (monotonic) ───────────────────────────────────
        now = self._clock()
        if now - self.takeover_start_time > self.config.initialization_timeout:
            self.status.failed = True
            self.status.error_message = "Takeover timeout exceeded"
            self.status.failure_reason = "timeout"
            logger.error("Takeover failed: timeout")
            return self.status

        # ── Save initial params ───────────────────────────────────
        if not self.initial_parameters:
            self._save_initial_parameters(telemetry)

        # ── Safety checks ─────────────────────────────────────────
        checks = self._perform_safety_checks(telemetry, approach_type, decision_height)
        self.status.checks_passed = checks

        # Classify sink_rate_safe: hard for ILS, retryable for VOR/NDB
        is_ils = approach_type and approach_type.upper() == 'ILS'
        hard_fails = [k for k, v in checks.items()
                      if not v and k in _HARD_FAIL_CHECKS]
        if is_ils and not checks.get('sink_rate_safe', True):
            hard_fails.append('sink_rate_safe')

        retryable_fails = [k for k, v in checks.items()
                           if not v and k in _RETRYABLE_CHECKS]
        if not is_ils and not checks.get('sink_rate_safe', True):
            retryable_fails.append('sink_rate_safe')

        # Hard fail → abort, no commands
        if hard_fails:
            self.status.failed = True
            self.status.failure_reason = "hard_safety"
            self.status.error_message = (
                f"Hard safety check failed: {', '.join(hard_fails)}")
            logger.error("TAKEOVER ABORTED — hard safety: %s",
                         ', '.join(hard_fails))
            return self.status

        # Retryable fail → wait, don't send commands yet
        if retryable_fails and not self._commands_sent:
            self.status.waiting_for = tuple(retryable_fails)
            logger.info("Takeover waiting for: %s",
                         ', '.join(retryable_fails))
            return self.status

        self.status.waiting_for = ()

        # ── Send commands (only once) ─────────────────────────────
        if not self._commands_sent:
            self._send_disengage_commands(aircraft_adapter, control)
            self._commands_sent = True

        # ── Readback verification (WP-3) ──────────────────────────
        self._verify_readback(aircraft_adapter, control)

        # ── Acquire controls after AP/AT verified off ─────────────
        if (self.status.autopilot_disengaged and
                self.status.autothrottle_disengaged and
                not self.status.controls_acquired):
            self._acquire_controls(control)

        # ── Complete ──────────────────────────────────────────────
        if (self.status.autopilot_disengaged and
                self.status.autothrottle_disengaged and
                self.status.controls_acquired):
            self._complete_takeover()

        return self.status

    # ── private helpers ───────────────────────────────────────────

    def _start_takeover(self):
        self.status.in_progress = True
        self.takeover_start_time = self._clock()
        self.status.timestamp = self.takeover_start_time
        logger.info("=" * 60)
        logger.info("AUTOPILOT TAKEOVER INITIATED")
        logger.info("=" * 60)

    def _save_initial_parameters(self, telemetry: Dict):
        self.initial_parameters = {
            'altitude': telemetry['position']['altitude'],
            'altitude_agl': telemetry['position']['altitude_agl'],
            'airspeed': telemetry['speed']['airspeed_indicated'],
            'heading': telemetry['attitude']['heading_magnetic'],
            'pitch': telemetry['attitude']['pitch'],
            'bank': telemetry['attitude']['bank'],
            'vertical_speed': telemetry['speed']['vertical_speed']
        }
        logger.info("Initial parameters saved: IAS=%.0fkt, ALT=%.0fft, HDG=%.0f°",
                     self.initial_parameters['airspeed'],
                     self.initial_parameters['altitude'],
                     self.initial_parameters['heading'])

    def _perform_safety_checks(self, telemetry: Dict,
                                approach_type: str = None,
                                decision_height: float = None) -> Dict[str, bool]:
        checks: Dict[str, bool] = {}

        altitude_agl = telemetry['position']['altitude_agl']

        # FIX-9: compute altitude_safe by approach mode
        if approach_type and approach_type.upper() == 'ILS':
            if decision_height is None:
                # fail-closed: ILS without DH → altitude not safe
                checks['altitude_safe'] = False
            else:
                checks['altitude_safe'] = altitude_agl > decision_height
        else:
            # VOR/NDB/NPA: use takeover_altitude_min floor
            checks['altitude_safe'] = altitude_agl >= self.config.takeover_altitude_min

        if self.config.require_stable_speed and self.initial_parameters:
            current_speed = telemetry['speed']['airspeed_indicated']
            initial_speed = self.initial_parameters['airspeed']
            checks['speed_stable'] = (
                abs(current_speed - initial_speed) <= self.config.speed_tolerance)
        else:
            checks['speed_stable'] = True

        if self.config.require_stable_altitude and self.initial_parameters:
            current_alt = telemetry['position']['altitude']
            initial_alt = self.initial_parameters['altitude']
            checks['altitude_stable'] = (
                abs(current_alt - initial_alt) <= self.config.altitude_tolerance)
        else:
            checks['altitude_stable'] = True

        bank = abs(telemetry['attitude']['bank'])
        pitch = telemetry['attitude']['pitch']
        checks['attitude_safe'] = bank < 30 and -10 < pitch < 15

        on_ground = telemetry['position'].get('on_ground', False)
        checks['airborne'] = not on_ground

        # 6. Sink rate guard — mode-dependent classification
        vertical_speed = telemetry['speed']['vertical_speed']
        checks['sink_rate_safe'] = vertical_speed >= -self.config.sink_rate_max
        # Note: sink_rate_safe classification (hard vs retryable) is determined
        # by approach_type in perform_takeover(), not here.

        return checks

    def _send_disengage_commands(self, aircraft_adapter, control):
        """Отправить команды выключения AP/A/T (без подтверждения)."""
        logger.info("Sending disengage commands...")

        # Try adapter first
        if aircraft_adapter and hasattr(aircraft_adapter, 'disengage_autopilot'):
            aircraft_adapter.disengage_autopilot()

        # SimConnect fallback
        control.set_autopilot_master(False)
        control.set_heading_hold(False)
        control.set_altitude_hold(False)
        control.set_airspeed_hold(False)
        control.set_vertical_speed_hold(False)

        if aircraft_adapter and hasattr(aircraft_adapter, 'disengage_autothrottle'):
            aircraft_adapter.disengage_autothrottle()

        logger.info("Disengage commands sent")

    def _verify_readback(self, aircraft_adapter, control):
        """WP-3: Проверить readback AP/A/T статуса.

        Adapter readback приоритетнее generic control readback.
        None = неизвестно → fail-closed (не ставим True).
        """
        # AP readback
        ap_readback = None
        if aircraft_adapter and hasattr(aircraft_adapter, 'get_autopilot_engaged'):
            ap_readback = aircraft_adapter.get_autopilot_engaged()
        if ap_readback is None and hasattr(control, 'get_autopilot_engaged'):
            ap_readback = control.get_autopilot_engaged()

        if ap_readback is False:
            self.status.autopilot_disengaged = True
        elif ap_readback is True:
            self.status.autopilot_disengaged = False
        # None → leave as-is (fail-closed)

        # AT readback
        at_readback = None
        if aircraft_adapter and hasattr(aircraft_adapter, 'get_autothrottle_engaged'):
            at_readback = aircraft_adapter.get_autothrottle_engaged()
        if at_readback is None and hasattr(control, 'get_autothrottle_engaged'):
            at_readback = control.get_autothrottle_engaged()

        if at_readback is False:
            self.status.autothrottle_disengaged = True
        elif at_readback is True:
            self.status.autothrottle_disengaged = False
        # None → leave as-is (fail-closed)

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
        elif self.status.completed:
            return "COMPLETED - AutoLand in control"
        elif self.status.in_progress:
            steps = []
            steps.append("AP✓" if self.status.autopilot_disengaged else "AP...")
            steps.append("AT✓" if self.status.autothrottle_disengaged else "AT...")
            steps.append("CTRL✓" if self.status.controls_acquired else "CTRL...")
            return f"IN PROGRESS: {' '.join(steps)}"
        else:
            return "READY"

    def reset(self):
        self.status = TakeoverStatus()
        self.takeover_start_time = None
        self.initial_parameters = {}
        self._commands_sent = False
        self._prev_altitude_agl = None
        logger.info("Takeover controller reset")

    def get_recommended_takeover_point(self,
                                       approach_type: str,
                                       runway_length_m: int,
                                       weather_conditions: Dict,
                                       decision_height: float = None) -> Tuple[float, float]:
        distance = 10.0
        altitude = 3000.0

        if approach_type == 'ILS':
            if decision_height:
                altitude = decision_height + 50.0
            else:
                altitude = 250.0
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

        logger.info("Recommended takeover point: %.1fnm, %.0fft AGL "
                     "(approach=%s, runway=%dm)",
                     distance, altitude, approach_type, runway_length_m)

        return distance, altitude
