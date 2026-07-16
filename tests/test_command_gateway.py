"""TEST-CG-02: Direct CommandGateway test coverage."""
import pytest
from modules.command_gateway import CommandGateway, CommandRejected, CommandSource


# ---------------------------------------------------------------------------
# Fake raw control with call ledger
# ---------------------------------------------------------------------------

class FakeControl:
    """Minimal fake control that records all calls."""
    def __init__(self):
        self.calls = []

    def set_throttle(self, v):
        self.calls.append(("set_throttle", v))

    def set_vertical_speed(self, v):
        self.calls.append(("set_vertical_speed", v))

    def set_aileron(self, v):
        self.calls.append(("set_aileron", v))

    def set_rudder(self, v):
        self.calls.append(("set_rudder", v))

    def set_heading_hold(self, v):
        self.calls.append(("set_heading_hold", v))

    def set_altitude_hold(self, v):
        self.calls.append(("set_altitude_hold", v))

    def set_flaps(self, v):
        self.calls.append(("set_flaps", v))

    def set_gear(self, v):
        self.calls.append(("set_gear", v))

    def set_nav_frequency(self, *args):
        self.calls.append(("set_nav_frequency", args))

    def set_adf_frequency(self, *args):
        self.calls.append(("set_adf_frequency", args))

    def set_obs(self, *args):
        self.calls.append(("set_obs", args))

    def set_autopilot_master(self, v):
        self.calls.append(("set_autopilot_master", v))

    def set_nav_hold(self, v):
        self.calls.append(("set_nav_hold", v))

    def set_approach_mode(self, v):
        self.calls.append(("set_approach_mode", v))

    def set_airspeed_hold(self, v):
        self.calls.append(("set_airspeed_hold", v))

    def set_throttle_engine(self, *args):
        self.calls.append(("set_throttle_engine", args))

    def set_throttle_asymmetric(self, v):
        self.calls.append(("set_throttle_asymmetric", v))

    # Non-channel method (readback/helper) — should NOT be guarded
    def get_throttle(self):
        self.calls.append(("get_throttle",))
        return 0.5


# ---------------------------------------------------------------------------
# Ownership providers
# ---------------------------------------------------------------------------

from modules.control_ownership import ControlOwner, ControlOwnership

def ap_owner():
    return ControlOwnership(ControlOwner.AIRCRAFT_AP, ControlOwner.AIRCRAFT_AP, ControlOwner.AIRCRAFT_AP)

def external_owner():
    return ControlOwnership(ControlOwner.EXTERNAL, ControlOwner.EXTERNAL, ControlOwner.EXTERNAL)

def mixed_owner():
    return ControlOwnership(ControlOwner.AIRCRAFT_AP, ControlOwner.AIRCRAFT_AP, ControlOwner.EXTERNAL)


# ---------------------------------------------------------------------------
# 1. AP owner + unscoped actuator → allowed (current compatibility contract)
# ---------------------------------------------------------------------------

def test_ap_owner_unscoped_allowed():
    """AP owner + unscoped actuator is currently allowed (default AIRCRAFT_AP)."""
    raw = FakeControl()
    gw = CommandGateway(raw, ap_owner)
    gw.set_throttle(0.5)
    assert raw.calls == [("set_throttle", 0.5)]


# ---------------------------------------------------------------------------
# 2. EXTERNAL owner + unscoped actuator → CommandRejected
# ---------------------------------------------------------------------------

def test_external_owner_unscoped_rejected():
    """EXTERNAL owner + unscoped actuator → CommandRejected."""
    raw = FakeControl()
    gw = CommandGateway(raw, external_owner)
    with pytest.raises(CommandRejected):
        gw.set_throttle(0.5)


# ---------------------------------------------------------------------------
# 3. EXTERNAL owner + explicit EXTERNAL scope → allowed
# ---------------------------------------------------------------------------

def test_external_owner_explicit_scope_allowed():
    """EXTERNAL owner + EXTERNAL scope → allowed."""
    raw = FakeControl()
    gw = CommandGateway(raw, external_owner)
    with gw.source_scope(CommandSource.EXTERNAL):
        gw.set_throttle(0.5)
    assert raw.calls == [("set_throttle", 0.5)]


# ---------------------------------------------------------------------------
# 4. AP owner + explicit EXTERNAL scope → rejected
# ---------------------------------------------------------------------------

def test_ap_owner_external_scope_rejected():
    """AP owner + EXTERNAL scope → CommandRejected."""
    raw = FakeControl()
    gw = CommandGateway(raw, ap_owner)
    with pytest.raises(CommandRejected):
        with gw.source_scope(CommandSource.EXTERNAL):
            gw.set_throttle(0.5)


# ---------------------------------------------------------------------------
# 5. SAFETY scope → allowed regardless of owner
# ---------------------------------------------------------------------------

def test_safety_scope_bypasses_authorization():
    """SAFETY scope allows any command regardless of owner."""
    raw = FakeControl()
    gw = CommandGateway(raw, external_owner)  # EXTERNAL owner
    with gw.source_scope(CommandSource.SAFETY):
        gw.set_throttle(1.0)
        gw.set_vertical_speed(1500)
    assert raw.calls == [("set_throttle", 1.0), ("set_vertical_speed", 1500)]


# ---------------------------------------------------------------------------
# 6. Scope restores after normal exit
# ---------------------------------------------------------------------------

def test_scope_restores_after_normal_exit():
    """After source_scope context manager exits, default source is restored."""
    raw = FakeControl()
    gw = CommandGateway(raw, external_owner)

    with gw.source_scope(CommandSource.EXTERNAL):
        gw.set_throttle(0.5)

    # After scope exits, unscoped call should be rejected (external owner)
    with pytest.raises(CommandRejected):
        gw.set_throttle(0.7)


# ---------------------------------------------------------------------------
# 7. Scope restores after exception inside context manager
# ---------------------------------------------------------------------------

def test_scope_restores_after_exception():
    """After exception inside source_scope, default source is restored."""
    raw = FakeControl()
    gw = CommandGateway(raw, external_owner)

    try:
        with gw.source_scope(CommandSource.SAFETY):
            gw.set_throttle(1.0)
            raise ValueError("test exception")
    except ValueError:
        pass

    # After exception, unscoped call should be rejected (external owner)
    with pytest.raises(CommandRejected):
        gw.set_throttle(0.7)


# ---------------------------------------------------------------------------
# 8. Nested scopes restore LIFO
# ---------------------------------------------------------------------------

def test_nested_scopes_lifo():
    """Nested source_scope contexts restore in LIFO order."""
    raw = FakeControl()
    gw = CommandGateway(raw, ap_owner)

    with gw.source_scope(CommandSource.EXTERNAL):
        # Inside EXTERNAL scope — AP owner, EXTERNAL source → rejected
        with pytest.raises(CommandRejected):
            gw.set_throttle(0.5)

        with gw.source_scope(CommandSource.SAFETY):
            # Inside SAFETY scope → allowed
            gw.set_throttle(1.0)

        # Back to EXTERNAL scope — rejected again
        with pytest.raises(CommandRejected):
            gw.set_throttle(0.5)

    # Back to default — AP owner, AP source → allowed
    gw.set_throttle(0.3)
    assert raw.calls == [("set_throttle", 1.0), ("set_throttle", 0.3)]


# ---------------------------------------------------------------------------
# 9. Guarded closure captures authorization at call time, not definition time
# ---------------------------------------------------------------------------

def test_guarded_closure_authorizes_at_call_time():
    """Guarded closure checks authorization when called, not when captured."""
    raw = FakeControl()
    gw = CommandGateway(raw, ap_owner)

    # Capture reference to guarded method BEFORE entering scope
    throttle_fn = gw.set_throttle

    # Default scope (AP) + AP owner → allowed
    throttle_fn(0.5)
    assert raw.calls == [("set_throttle", 0.5)]

    # EXTERNAL scope + AP owner → rejected
    with pytest.raises(CommandRejected):
        with gw.source_scope(CommandSource.EXTERNAL):
            throttle_fn(0.7)

    # Back to default → allowed again
    throttle_fn(0.3)
    assert raw.calls == [("set_throttle", 0.5), ("set_throttle", 0.3)]


# ---------------------------------------------------------------------------
# 10. ContextVar isolation across separate contexts
# ---------------------------------------------------------------------------

def test_contextvar_isolation():
    """ContextVar isolation: separate context managers don't leak."""
    raw1 = FakeControl()
    raw2 = FakeControl()
    gw1 = CommandGateway(raw1, ap_owner)
    gw2 = CommandGateway(raw2, external_owner)

    # gw1 uses AP owner (default scope → AP source → allowed)
    # gw2 uses EXTERNAL owner (default scope → AP source → rejected)
    gw1.set_throttle(0.5)
    with pytest.raises(CommandRejected):
        gw2.set_throttle(0.5)

    assert raw1.calls == [("set_throttle", 0.5)]
    assert raw2.calls == []


# ---------------------------------------------------------------------------
# 11. Configuration/navigation/autopilot channels covered
# ---------------------------------------------------------------------------

def test_config_channels():
    """Configuration channels (set_flaps, set_gear) work through gateway."""
    raw = FakeControl()
    gw = CommandGateway(raw, ap_owner)

    gw.set_flaps(2)
    gw.set_gear(True)
    assert raw.calls == [("set_flaps", 2), ("set_gear", True)]


def test_nav_channels():
    """Navigation channels work through gateway."""
    raw = FakeControl()
    gw = CommandGateway(raw, ap_owner)

    gw.set_nav_frequency(1, 110500000)
    gw.set_adf_frequency(1, 375000)
    gw.set_obs(1, 45)
    assert len(raw.calls) == 3


def test_autopilot_channels():
    """Autopilot channels work through gateway."""
    raw = FakeControl()
    gw = CommandGateway(raw, ap_owner)

    gw.set_autopilot_master(True)
    gw.set_nav_hold(True)
    gw.set_approach_mode(True)
    gw.set_airspeed_hold(140)
    assert len(raw.calls) == 4


# ---------------------------------------------------------------------------
# 12. Unknown readback/helper method delegated without authorization
# ---------------------------------------------------------------------------

def test_readback_method_not_guarded():
    """Non-channel method (readback/helper) is delegated without authorization."""
    raw = FakeControl()
    gw = CommandGateway(raw, external_owner)

    # get_throttle is NOT in _CHANNELS → should NOT be guarded
    result = gw.get_throttle()
    assert result == 0.5
    assert raw.calls == [("get_throttle",)]


def test_unknown_method_delegated():
    """Unknown method not in _CHANNELS is delegated to raw control."""
    raw = FakeControl()
    gw = CommandGateway(raw, external_owner)

    # Add a method to raw that's not in _CHANNELS
    raw.custom_method = lambda: "custom"
    result = gw.custom_method()
    assert result == "custom"
