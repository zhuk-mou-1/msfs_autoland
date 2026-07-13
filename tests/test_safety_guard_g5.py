"""F6 tests: G5 expansion — safety guard triggers on missing VS/bank."""
from modules.safety_guard import (
    ApproachSafetyGuard, SafetySnapshot, GuardDecision,
)


def _snapshot(vs=0.0, bank=0.0, ias=120.0, rh=200.0, agl=200.0):
    return SafetySnapshot(
        altitude_agl=agl,
        radio_height=rh,
        airspeed_indicated=ias,
        vertical_speed=vs,
        bank=bank,
        vref=120.0,
    )


class TestGuardG5Expansion:
    def test_vs_missing_triggers_g5(self):
        """has_vs=False → G5 INVALID_TELEMETRY → debounce → GO_AROUND."""
        guard = ApproachSafetyGuard(debounce_n=2)
        snap = _snapshot()
        # First frame: debounce
        r1 = guard.evaluate(snap, has_vs=False)
        assert r1.decision == GuardDecision.CONTINUE
        assert "debounce" in r1.reason
        # Second frame: GO_AROUND
        r2 = guard.evaluate(snap, has_vs=False)
        assert r2.decision == GuardDecision.GO_AROUND
        assert r2.reason == "INVALID_TELEMETRY"

    def test_bank_missing_triggers_g5(self):
        """has_bank=False → G5 INVALID_TELEMETRY → debounce → GO_AROUND."""
        guard = ApproachSafetyGuard(debounce_n=2)
        snap = _snapshot()
        r1 = guard.evaluate(snap, has_bank=False)
        assert r1.decision == GuardDecision.CONTINUE
        r2 = guard.evaluate(snap, has_bank=False)
        assert r2.decision == GuardDecision.GO_AROUND
        assert r2.reason == "INVALID_TELEMETRY"

    def test_all_present_no_g5(self):
        """All channels present → G5 passes."""
        guard = ApproachSafetyGuard(debounce_n=2)
        snap = _snapshot()
        r = guard.evaluate(snap, has_vs=True, has_bank=True)
        assert r.decision == GuardDecision.CONTINUE
        assert r.reason == "all_checks_passed"

    def test_height_missing_still_triggers(self):
        """has_altitude=False + has_radio_height=False → G5."""
        guard = ApproachSafetyGuard(debounce_n=2)
        snap = _snapshot()
        r1 = guard.evaluate(snap, has_altitude=False, has_radio_height=False)
        assert r1.decision == GuardDecision.CONTINUE
        r2 = guard.evaluate(snap, has_altitude=False, has_radio_height=False)
        assert r2.decision == GuardDecision.GO_AROUND
