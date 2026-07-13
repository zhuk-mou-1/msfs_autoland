"""
Spy/fake-объекты для офлайн тестирования AutoLand.

Fake не дублирует production algorithm; его задача —
запомнить команды и выдать заранее установленный observed state.
"""

from __future__ import annotations

from typing import Any, List, Tuple


class FakeControl:
    """Spy для MSFSControl — записывает все команды."""

    def __init__(self) -> None:
        self.calls: List[Tuple[str, Any]] = []
        self.autopilot_master: bool = True
        self.autothrottle_active: bool = True

        # Readback state — что «видит» система при опросе
        self._ap_engaged_readback: bool | None = True
        self._at_engaged_readback: bool | None = True

    # ── command recording ──────────────────────────────────────────

    def set_autopilot_master(self, state: bool) -> None:
        self.calls.append(("set_autopilot_master", state))
        self.autopilot_master = state

    def set_heading_hold(self, heading=None) -> None:
        self.calls.append(("set_heading_hold", heading))

    def set_altitude_hold(self, altitude=None) -> None:
        self.calls.append(("set_altitude_hold", altitude))

    def set_airspeed_hold(self, speed=None) -> None:
        self.calls.append(("set_airspeed_hold", speed))

    def set_vertical_speed_hold(self, enabled: bool = True) -> None:
        self.calls.append(("set_vertical_speed_hold", enabled))

    def set_vertical_speed(self, vs: int) -> None:
        self.calls.append(("set_vertical_speed", vs))

    def set_throttle(self, value: float) -> None:
        self.calls.append(("set_throttle", value))

    def set_throttle_engine(self, engine_index: int, percent: float) -> None:
        self.calls.append(("set_throttle_engine", (engine_index, percent)))

    def set_throttle_asymmetric(self, throttle_values: dict) -> None:
        self.calls.append(("set_throttle_asymmetric", throttle_values))

    def set_rudder(self, percent: float) -> None:
        self.calls.append(("set_rudder", percent))

    def set_aileron(self, percent: float) -> None:
        self.calls.append(("set_aileron", percent))

    def set_flaps(self, position: int) -> None:
        self.calls.append(("set_flaps", position))

    def set_gear(self, state: bool) -> None:
        self.calls.append(("set_gear", state))

    def set_nav_frequency(self, nav_index: int, frequency: int) -> None:
        self.calls.append(("set_nav_frequency", (nav_index, frequency)))

    def set_adf_frequency(self, frequency: int) -> None:
        self.calls.append(("set_adf_frequency", frequency))

    def set_obs(self, nav_index: int, course: int) -> None:
        self.calls.append(("set_obs", (nav_index, course)))

    def set_approach_mode(self, state: bool) -> None:
        self.calls.append(("set_approach_mode", state))

    def set_nav_hold(self, state: bool) -> None:
        self.calls.append(("set_nav_hold", state))

    # ── readback helpers ───────────────────────────────────────────

    def get_autopilot_engaged(self) -> bool | None:
        """Readback текущего состояния AP."""
        return self._ap_engaged_readback

    def get_autothrottle_engaged(self) -> bool | None:
        """Readback текущего состояния A/T."""
        return self._at_engaged_readback

    def set_readback_ap(self, engaged: bool | None) -> None:
        """Тест-хелпер: установить что readback вернёт."""
        self._ap_engaged_readback = engaged

    def set_readback_at(self, engaged: bool | None) -> None:
        """Тест-хелпер: установить что readback вернёт."""
        self._at_engaged_readback = engaged

    # ── inspection ─────────────────────────────────────────────────

    def has_call(self, method: str) -> bool:
        return any(c[0] == method for c in self.calls)

    def calls_of(self, method: str) -> list:
        return [c for c in self.calls if c[0] == method]

    def calls_except(self, *methods: str) -> list:
        return [c for c in self.calls if c[0] not in methods]

    def clear(self) -> None:
        self.calls.clear()


class FakeAircraftAdapter:
    """Spy для AircraftCommandAdapter."""

    def __init__(self) -> None:
        self.calls: List[Tuple[str, Any]] = []
        self._disengage_ap_result: bool = True
        self._disengage_at_result: bool = True
        self._ap_state: bool | None = True
        self._at_state: bool | None = True

    def disengage_autopilot(self) -> bool:
        self.calls.append(("disengage_autopilot", None))
        return self._disengage_ap_result

    def disengage_autothrottle(self) -> bool:
        self.calls.append(("disengage_autothrottle", None))
        return self._disengage_at_result

    def engage_autopilot(self) -> bool:
        self.calls.append(("engage_autopilot", None))
        return True

    def set_speed(self, speed: int) -> bool:
        self.calls.append(("set_speed", speed))
        return True

    def get_autopilot_engaged(self) -> bool | None:
        return self._ap_state

    def get_autothrottle_engaged(self) -> bool | None:
        return self._at_state

    def has_call(self, method: str) -> bool:
        return any(c[0] == method for c in self.calls)


class FakeVJoy:
    """Spy для VirtualJoystick."""

    def __init__(self) -> None:
        self.calls: List[Tuple[str, Any]] = []
        self.enabled: bool = True

    def apply_control_inputs(self, aileron: float = 0.0,
                             elevator: float = 0.0,
                             rudder: float = 0.0) -> None:
        self.calls.append(("apply_control_inputs",
                           {"aileron": aileron, "elevator": elevator, "rudder": rudder}))

    def set_elevator(self, value: float) -> None:
        self.calls.append(("set_elevator", value))

    def set_aileron(self, value: float) -> None:
        self.calls.append(("set_aileron", value))

    def center_all_axes(self) -> None:
        self.calls.append(("center_all_axes", None))

    def calculate_heading_correction(self, current_hdg, target_hdg,
                                     current_bank, max_bank=10.0) -> float:
        return 0.0

    def calculate_bank_correction(self, current_bank, target_bank,
                                  max_input=0.2) -> float:
        return 0.0

    def calculate_pitch_correction(self, current_pitch, target_pitch,
                                   max_input=0.15) -> float:
        return 0.0

    def has_call(self, method: str) -> bool:
        return any(c[0] == method for c in self.calls)


class FakeClock:
    """Подмена time.monotonic() для детерминированных тестов."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start
        self._calls: List[float] = []

    def __call__(self) -> float:
        self._calls.append(self._now)
        return self._now

    def advance(self, dt: float) -> None:
        self._now += dt


def make_telemetry(
    *,
    altitude: float = 3000.0,
    altitude_agl: float = 2500.0,
    radio_height: float | None = None,
    on_ground: bool = False,
    airspeed: float = 140.0,
    vertical_speed: float = -700.0,
    ground_speed: float = 140.0,
    bank: float = 0.0,
    pitch: float = 2.5,
    heading: float = 270.0,
) -> dict:
    """Фабрика telemetry dict для тестов."""
    if radio_height is None:
        radio_height = altitude_agl
    return {
        "position": {
            "altitude": altitude,
            "altitude_agl": altitude_agl,
            "radio_height": radio_height,
            "on_ground": on_ground,
            "latitude": 55.5,
            "longitude": 37.5,
        },
        "attitude": {
            "bank": bank,
            "pitch": pitch,
            "heading_magnetic": heading,
        },
        "speed": {
            "airspeed_indicated": airspeed,
            "vertical_speed": vertical_speed,
            "ground_speed": ground_speed,
        },
        "nav": {},
    }
