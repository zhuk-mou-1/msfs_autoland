"""WP-0 smoke: test fakes are functional, AutopilotTakeover can be created offline."""

from modules.autopilot_takeover import AutopilotTakeover
from tests.fakes import FakeControl, make_telemetry


def test_fake_control_records_commands():
    ctrl = FakeControl()
    ctrl.set_autopilot_master(False)
    ctrl.set_throttle(0.5)

    assert ctrl.has_call("set_autopilot_master")
    assert ctrl.calls_of("set_autopilot_master") == [("set_autopilot_master", False)]
    assert ctrl.autopilot_master is False


def test_fake_control_readback():
    ctrl = FakeControl()
    assert ctrl.get_autopilot_engaged() is True

    ctrl.set_readback_ap(False)
    assert ctrl.get_autopilot_engaged() is False

    ctrl.set_readback_ap(None)
    assert ctrl.get_autopilot_engaged() is None


def test_takeover_instantiated_offline():
    """AutopilotTakeover can be created without SimConnect."""
    takeover = AutopilotTakeover()
    assert takeover.status.completed is False
    assert takeover.status.in_progress is False


def test_telemetry_factory():
    t = make_telemetry(altitude_agl=250, bank=5.0)
    assert t["position"]["altitude_agl"] == 250
    assert t["attitude"]["bank"] == 5.0
