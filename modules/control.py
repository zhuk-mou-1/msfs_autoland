"""
Модуль управления самолётом через SimConnect API
"""

import math
import logging
from typing import Optional

from SimConnect import AircraftEvents
from SimConnect.EventList import Event

logger = logging.getLogger(__name__)


class ControlCommandError(RuntimeError):
    """Fail-closed command error for safety-critical actuator paths."""


# SDK-only events absent from SimConnect v0.4.26 static EventList
# but confirmed in official MSFS 2020 SDK.
SDK_ONLY_EVENTS = frozenset({
    "AP_VS_ON",
    "NAV1_RADIO_SET_HZ",
    "NAV2_RADIO_SET_HZ",
    "AUTO_THROTTLE_ARM",
})

AXIS_ABS_MAX = 16383  # SDK limit for *_SET axis events


class MSFSControl:
    """Класс для управления самолётом через SimConnect"""

    FLAPS_EVENTS = {
        0: "FLAPS_UP",
        1: "FLAPS_1",
        2: "FLAPS_2",
        3: "FLAPS_3",
    }

    def __init__(self, aircraft_events: AircraftEvents, aircraft_requests=None):
        self.ae = aircraft_events
        self._aq = aircraft_requests  # Optional: для readback SimVars
        self._dynamic_events: dict[str, Event] = {}

    # ── SimConnect event dispatch (A-DISP-1) ─────────────────────

    def _resolve_event(self, name: str):
        event = self.ae.find(name)
        if event is not None:
            if not callable(event):
                raise TypeError(f"SimConnect event {name!r} is not callable")
            return event

        if name not in SDK_ONLY_EVENTS:
            raise ValueError(f"Unknown SimConnect event: {name}")

        event = self._dynamic_events.get(name)
        if event is None:
            sm = getattr(self.ae, "sm", None)
            if sm is None:
                raise RuntimeError(
                    f"Cannot register SDK-only event {name!r}: "
                    "AircraftEvents.sm unavailable"
                )
            event = Event(
                name.encode("ascii"), sm,
                _dec="Official MSFS SDK event missing from SimConnect 0.4.26 EventList",
            )
            self._dynamic_events[name] = event
        return event

    def _send_event(self, name: str, value=None):
        event = self._resolve_event(name)
        if value is None:
            event()
        else:
            event(value)

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _bounded_number(value, *, name, minimum, maximum):
        if isinstance(value, bool):
            raise ValueError(f"{name} must be numeric, not bool")
        try:
            value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric") from exc
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
        bounded = max(minimum, min(maximum, value))
        if bounded != value:
            logger.warning("Clamped %s from %s to %s", name, value, bounded)
        return bounded

    @classmethod
    def _unit_input(cls, value, *, name):
        return cls._bounded_number(value, name=name, minimum=-1.0, maximum=1.0)

    @classmethod
    def _throttle_input(cls, value, *, name="throttle"):
        return cls._bounded_number(value, name=name, minimum=0.0, maximum=1.0)

    @staticmethod
    def _raise_command_error(action: str, exc: Exception):
        logger.exception("%s failed", action)
        raise ControlCommandError(f"{action} failed: {exc}") from exc

    def _readback_bool(self, simvar_name: str) -> Optional[bool]:
        if self._aq is None:
            return None
        try:
            raw = self._aq.get(simvar_name)
        except Exception as exc:
            logger.warning("Readback failed for %s: %s", simvar_name, exc)
            return None
        if raw is None:
            return None
        return bool(raw)

    def _require_verified_bool_state(self, simvar_name: str, expected_state: bool, *, retries: int = 1) -> bool:
        observed = None
        for _ in range(retries + 1):
            observed = self._readback_bool(simvar_name)
            if observed is expected_state:
                return True
        if observed is None:
            raise ControlCommandError(
                f"Unable to verify {simvar_name}: readback unavailable"
            )
        raise ControlCommandError(
            f"Readback mismatch for {simvar_name}: expected {expected_state}, observed {observed}"
        )

    # ── Commands ─────────────────────────────────────────────────

    def set_autopilot_master(self, state: bool) -> bool:
        """Включить/выключить автопилот"""
        action = f"set autopilot master={state}"
        try:
            if state:
                self._send_event("AUTOPILOT_ON")
            else:
                self._send_event("AUTOPILOT_OFF")
            if self._aq is not None:
                self._require_verified_bool_state("AUTOPILOT_MASTER", state)
            logger.info("Autopilot master: %s", state)
            return True
        except Exception as e:
            self._raise_command_error(action, e)

    def disengage_autopilot(self) -> bool:
        """Disengage AP with readback verification when available."""
        return self.set_autopilot_master(False)

    def set_heading_hold(self, heading: Optional[int] = None) -> bool:
        """Установить режим удержания курса"""
        action = f"set heading hold heading={heading}"
        try:
            self._send_event("AP_HDG_HOLD_ON")
            if heading is not None:
                self._send_event("HEADING_BUG_SET", int(heading))
            logger.info("Heading hold ON, heading: %s", heading)
            return True
        except Exception as e:
            self._raise_command_error(action, e)

    def set_altitude_hold(self, altitude: Optional[int] = None) -> bool:
        """Установить режим удержания высоты"""
        action = f"set altitude hold altitude={altitude}"
        try:
            self._send_event("AP_ALT_HOLD_ON")
            if altitude is not None:
                self._send_event("AP_ALT_VAR_SET_ENGLISH", int(altitude))
            logger.info("Altitude hold ON, altitude: %s", altitude)
            return True
        except Exception as e:
            self._raise_command_error(action, e)

    def set_nav_hold(self, state: bool) -> bool:
        """Включить/выключить режим NAV (следование по VOR)"""
        action = f"set nav hold state={state}"
        try:
            if state:
                self._send_event("AP_NAV1_HOLD_ON")
            else:
                self._send_event("AP_NAV1_HOLD_OFF")
            logger.info("NAV hold: %s", state)
            return True
        except Exception as e:
            self._raise_command_error(action, e)

    def set_approach_mode(self, state: bool) -> bool:
        """Включить/выключить режим захода на посадку"""
        action = f"set approach mode state={state}"
        try:
            if state:
                self._send_event("AP_APR_HOLD_ON")
            else:
                self._send_event("AP_APR_HOLD_OFF")
            logger.info("Approach mode: %s", state)
            return True
        except Exception as e:
            self._raise_command_error(action, e)

    def set_airspeed_hold(self, speed: Optional[int] = None) -> bool:
        """Установить режим удержания скорости"""
        action = f"set airspeed hold speed={speed}"
        try:
            self._send_event("AP_AIRSPEED_ON")
            if speed is not None:
                self._send_event("AP_SPD_VAR_SET", int(speed))
            logger.info("Airspeed hold ON, speed: %s", speed)
            return True
        except Exception as e:
            self._raise_command_error(action, e)

    def set_vertical_speed(self, vs: int) -> bool:
        """Установить вертикальную скорость (футы/мин)

        Uses deterministic AP_VS_ON (not toggle AP_VS_HOLD).
        """
        action = f"set vertical speed vs={vs}"
        try:
            self._send_event("AP_VS_ON")
            self._send_event("AP_VS_VAR_SET_ENGLISH", int(vs))
            logger.info("Vertical speed set: %s fpm", vs)
            return True
        except Exception as e:
            self._raise_command_error(action, e)

    def set_nav_frequency(self, nav_index: int, frequency: int) -> bool:
        """Установить частоту NAV радио (в Hz)"""
        action = f"set NAV{nav_index} frequency={frequency}Hz"
        try:
            if nav_index == 1:
                self._send_event("NAV1_RADIO_SET_HZ", frequency)
            elif nav_index == 2:
                self._send_event("NAV2_RADIO_SET_HZ", frequency)
            else:
                raise ValueError(f"Invalid NAV index: {nav_index}")
            logger.info("NAV%s frequency set: %s Hz", nav_index, frequency)
            return True
        except Exception as e:
            self._raise_command_error(action, e)

    def set_adf_frequency(self, frequency: int) -> bool:
        """Установить частоту ADF (в Hz)"""
        action = f"set ADF frequency={frequency}Hz"
        try:
            self._send_event("ADF_COMPLETE_SET", frequency)
            logger.info("ADF frequency set: %s Hz", frequency)
            return True
        except Exception as e:
            self._raise_command_error(action, e)

    def set_obs(self, nav_index: int, course: int) -> bool:
        """Установить OBS (курс на VOR)"""
        action = f"set NAV{nav_index} OBS={course}"
        try:
            if nav_index == 1:
                self._send_event("VOR1_SET", int(course))
            elif nav_index == 2:
                self._send_event("VOR2_SET", int(course))
            else:
                raise ValueError(f"Invalid NAV index: {nav_index}")
            logger.info("NAV%s OBS set: %s°", nav_index, course)
            return True
        except Exception as e:
            self._raise_command_error(action, e)

    def set_flaps(self, position: int) -> bool:
        """Установить закрылки (логический детент 0-3 через дискретные события)"""
        action = f"set flaps position={position}"
        try:
            position = int(self._bounded_number(position, name="flaps", minimum=0, maximum=3))
            event_name = self.FLAPS_EVENTS[position]
            self._send_event(event_name)
            logger.info("Flaps set: %s (%s)", position, event_name)
            return True
        except Exception as e:
            self._raise_command_error(action, e)

    def set_gear(self, state: bool) -> bool:
        """Выпустить/убрать шасси"""
        action = f"set gear state={state}"
        try:
            if state:
                self._send_event("GEAR_DOWN")
            else:
                self._send_event("GEAR_UP")
            logger.info("Gear: %s", "DOWN" if state else "UP")
            return True
        except Exception as e:
            self._raise_command_error(action, e)

    def set_throttle(self, percent: float) -> bool:
        """
        Установить газ на всех двигателях (0.0 - 1.0)

        Args:
            percent: Процент тяги (0.0 - 1.0)
        """
        action = f"set throttle percent={percent}"
        try:
            percent = self._throttle_input(percent)
            value = min(AXIS_ABS_MAX, int(percent * 16384))
            self._send_event("THROTTLE_SET", value)
            logger.info("Throttle set: %.1f%%", percent * 100)
            return True
        except Exception as e:
            self._raise_command_error(action, e)

    def set_throttle_engine(self, engine_index: int, percent: float) -> bool:
        """
        Установить газ на конкретном двигателе (0.0 - 1.0)

        Args:
            engine_index: Номер двигателя (1-4)
            percent: Процент тяги (0.0 - 1.0)
        """
        action = f"set engine {engine_index} throttle percent={percent}"
        try:
            percent = self._throttle_input(percent, name=f"engine_{engine_index}_throttle")
            value = min(AXIS_ABS_MAX, int(percent * 16384))

            event_map = {
                1: "THROTTLE1_SET",
                2: "THROTTLE2_SET",
                3: "THROTTLE3_SET",
                4: "THROTTLE4_SET",
            }
            if engine_index not in event_map:
                raise ValueError(f"Invalid engine index: {engine_index} (must be 1-4)")

            self._send_event(event_map[engine_index], value)
            logger.info("Engine %s throttle set: %.1f%%", engine_index, percent * 100)
            return True
        except Exception as e:
            self._raise_command_error(action, e)

    def set_throttle_asymmetric(self, throttle_values: dict) -> bool:
        """
        Установить асимметричную тягу (разные значения для каждого двигателя)

        Args:
            throttle_values: Словарь {engine_index: percent}
                            Например: {1: 0.8, 2: 0.0, 3: 0.8, 4: 0.0}
        """
        action = f"set asymmetric throttle values={throttle_values}"
        try:
            for engine_idx, percent in throttle_values.items():
                self.set_throttle_engine(engine_idx, percent)
            logger.info("Asymmetric throttle set: %s", throttle_values)
            return True
        except Exception as e:
            self._raise_command_error(action, e)

    def set_rudder(self, percent: float) -> bool:
        """
        Установить руль направления (-1.0 до +1.0)
        """
        action = f"set rudder percent={percent}"
        try:
            percent = self._unit_input(percent, name="rudder")
            value = max(-AXIS_ABS_MAX, min(AXIS_ABS_MAX, int(percent * 16384)))
            self._send_event("RUDDER_SET", value)
            logger.debug("Rudder set: %+0.2f (%s)", percent, value)
            return True
        except Exception as e:
            self._raise_command_error(action, e)

    def set_aileron(self, percent: float) -> bool:
        """
        Установить элероны (-1.0 до +1.0)
        """
        action = f"set aileron percent={percent}"
        try:
            percent = self._unit_input(percent, name="aileron")
            value = max(-AXIS_ABS_MAX, min(AXIS_ABS_MAX, int(percent * 16384)))
            self._send_event("AILERON_SET", value)
            logger.debug("Aileron set: %+0.2f (%s)", percent, value)
            return True
        except Exception as e:
            self._raise_command_error(action, e)

    def set_elevator(self, percent: float) -> bool:
        """
        Установить руль высоты (-1.0 до +1.0)
        """
        action = f"set elevator percent={percent}"
        try:
            percent = self._unit_input(percent, name="elevator")
            value = max(-AXIS_ABS_MAX, min(AXIS_ABS_MAX, int(percent * 16384)))
            self._send_event("ELEVATOR_SET", value)
            logger.debug("Elevator set: %+0.2f (%s)", percent, value)
            return True
        except Exception as e:
            self._raise_command_error(action, e)

    # ── Readback methods (WP-3 / FIX-1) ──────────────────────────

    def get_autopilot_engaged(self) -> Optional[bool]:
        """Readback: AP включён?"""
        return self._readback_bool("AUTOPILOT_MASTER")

    def get_autothrottle_engaged(self) -> Optional[bool]:
        """Readback: A/T включён?"""
        return self._readback_bool("AUTOPILOT_THROTTLE_ARM")

    def arm_autothrottle(self) -> bool:
        """Arm onboard autothrottle with readback verification when available."""
        if self._aq is None:
            self._send_event("AUTO_THROTTLE_ARM")
            return True

        current = self.get_autothrottle_engaged()
        if current is True:
            return True
        if current is None:
            raise ControlCommandError("Cannot arm A/T: readback unavailable")

        self._send_event("AUTO_THROTTLE_ARM")
        return self._require_verified_bool_state("AUTOPILOT_THROTTLE_ARM", True)

    def disengage_autothrottle(self) -> bool:
        """Disengage onboard autothrottle via readback-verified toggle.

        Returns True if confirmed disengaged, False otherwise.
        None readback → fail-closed (return False).
        """
        if self._aq is None:
            logger.warning("Cannot disengage A/T: no readback available")
            return False

        current = self.get_autothrottle_engaged()
        if current is None:
            logger.warning("AUTOPILOT_THROTTLE_ARM readback unavailable")
            return False
        if current is False:
            return True

        self._send_event("AUTO_THROTTLE_ARM")
        try:
            return self._require_verified_bool_state("AUTOPILOT_THROTTLE_ARM", False)
        except ControlCommandError as exc:
            logger.warning("A/T disengage verification failed: %s", exc)
            return False
