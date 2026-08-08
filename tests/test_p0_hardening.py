import pytest

from modules.command_gateway import CommandGateway, CommandRejected
from modules.control import MSFSControl
from modules.control_ownership import ControlOwner, ControlOwnership
from modules.telemetry import MSFSTelemetry


class FakeControl:
    def __init__(self):
        self.calls = []

    def set_throttle(self, value):
        self.calls.append(("set_throttle", value))


def ap_owner():
    return ControlOwnership(ControlOwner.AIRCRAFT_AP, ControlOwner.AIRCRAFT_AP, ControlOwner.AIRCRAFT_AP)


def test_command_gateway_strict_unscoped_rejects():
    raw = FakeControl()
    gw = CommandGateway(raw, ap_owner, strict_unscoped=True)

    with pytest.raises(CommandRejected, match="missing explicit command source"):
        gw.set_throttle(0.5)


class FakeEvent:
    def __init__(self, callback=None):
        self.callback = callback
        self.calls = []

    def __call__(self, value=None):
        self.calls.append(value)
        if self.callback is not None:
            self.callback(value)


class FakeAircraftEvents:
    def __init__(self, state):
        self._catalog = {
            "AUTOPILOT_OFF": FakeEvent(lambda _v: state.__setitem__("AUTOPILOT_MASTER", 0)),
            "AUTOPILOT_ON": FakeEvent(lambda _v: state.__setitem__("AUTOPILOT_MASTER", 1)),
            "AUTO_THROTTLE_ARM": FakeEvent(
                lambda _v: state.__setitem__(
                    "AUTOPILOT_THROTTLE_ARM",
                    0 if state.get("AUTOPILOT_THROTTLE_ARM") else 1,
                )
            ),
        }
        self.sm = object()

    def find(self, name):
        return self._catalog.get(name)


class FakeAircraftRequests:
    def __init__(self, state):
        self.state = state

    def get(self, name):
        return self.state.get(name)


def test_control_ap_disengage_is_readback_verified():
    state = {"AUTOPILOT_MASTER": 1, "AUTOPILOT_THROTTLE_ARM": 1}
    ae = FakeAircraftEvents(state)
    aq = FakeAircraftRequests(state)
    ctrl = MSFSControl(ae, aq)

    assert ctrl.disengage_autopilot() is True
    assert state["AUTOPILOT_MASTER"] == 0


def test_control_at_disengage_is_readback_verified():
    state = {"AUTOPILOT_MASTER": 1, "AUTOPILOT_THROTTLE_ARM": 1}
    ae = FakeAircraftEvents(state)
    aq = FakeAircraftRequests(state)
    ctrl = MSFSControl(ae, aq)

    assert ctrl.disengage_autothrottle() is True
    assert state["AUTOPILOT_THROTTLE_ARM"] == 0


class FakeTelemetryAQ:
    def get(self, name):
        values = {
            "BAROMETER_PRESSURE": 1013.25,
            "SEA_LEVEL_PRESSURE": 1012.8,
            "KOHLSMAN_SETTING_MB": 1013.25,
            "AMBIENT_TEMPERATURE": 12.0,
            "AMBIENT_WIND_VELOCITY": 18.0,
            "AMBIENT_WIND_DIRECTION": 220.0,
        }
        return values.get(name)


def test_weather_data_exposes_legacy_and_canonical_aliases():
    telemetry = MSFSTelemetry()
    telemetry.connected = True
    telemetry.aq = FakeTelemetryAQ()

    weather = telemetry.get_weather_data()

    assert weather["ambient_wind_velocity"] == 18.0
    assert weather["wind_velocity"] == 18.0
    assert weather["ambient_wind_direction"] == 220.0
    assert weather["wind_direction"] == 220.0
    assert weather["wind_speed_kt"] == 18.0
    assert weather["wind_direction_deg"] == 220.0
