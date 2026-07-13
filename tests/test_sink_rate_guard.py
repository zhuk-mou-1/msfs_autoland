"""TASK-003: Sink rate guard for autopilot takeover.

Adds sink rate safety check to _perform_safety_checks().
Mode-dependent: hard fail for ILS, retryable wait for VOR/NDB.
Threshold: 1000 fpm descent (configurable via sink_rate_max).
"""

import sys
from pathlib import Path


_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from modules.autopilot_takeover import AutopilotTakeover, TakeoverConfig
from tests.fakes import FakeAircraftAdapter, FakeClock, FakeControl, make_telemetry


# ═══════════════════════════════════════════════════════════════════
# Bug test: reproduction of the original bug (pre-fix)
# ═══════════════════════════════════════════════════════════════════

class TestSinkRateBugReproduction:
    """Bug test: takeover succeeds with excessive sink rate because check is missing.

    This test MUST FAIL on pre-fix code (no sink_rate_safe check).
    """

    def test_ils_takeover_proceeds_with_excessive_sink_rate_pre_fix(self):
        """BUG: ILS takeover completes despite -1200 fpm descent.

        Pre-fix: no sink_rate_safe check exists, so takeover proceeds.
        Post-fix: hard fail blocks takeover for ILS.
        """
        clock = FakeClock(start=0.0)
        config = TakeoverConfig(sink_rate_max=1000.0)
        takeover = AutopilotTakeover(config=config, clock=clock)

        takeover.status.in_progress = True
        takeover.takeover_start_time = clock()
        takeover.initial_parameters = {"airspeed": 140, "altitude": 3000}

        # Excessive sink rate: -1200 fpm (exceeds 1000 limit)
        telemetry = make_telemetry(
            vertical_speed=-1200.0,
            altitude_agl=250.0,  # ILS at DH+50
        )

        ctrl = FakeControl()
        adapter = FakeAircraftAdapter()

        status = takeover.perform_takeover(
            telemetry, adapter, ctrl,
            approach_type="ILS",
            decision_height=200.0,
        )

        # Pre-fix: this assertion FAILS (takeover proceeds)
        # Post-fix: this assertion PASSES (takeover blocked)
        assert status.failed is True, \
            "BUG: ILS takeover should fail with excessive sink rate"
        assert "sink_rate" in status.error_message.lower() or \
               "hard safety" in status.error_message.lower()
        # No commands should be sent
        assert not ctrl.has_call("set_autopilot_master"), \
            "AP should NOT be disengaged after sink rate failure"

    def test_vor_takeover_waits_with_excessive_sink_rate_pre_fix(self):
        """BUG: VOR takeover proceeds despite -1100 fpm descent.

        Pre-fix: no sink_rate_safe check, takeover proceeds.
        Post-fix: retryable wait for VOR/NDB.
        """
        clock = FakeClock(start=0.0)
        config = TakeoverConfig(sink_rate_max=1000.0)
        takeover = AutopilotTakeover(config=config, clock=clock)

        takeover.status.in_progress = True
        takeover.takeover_start_time = clock()
        takeover.initial_parameters = {"airspeed": 140, "altitude": 3000}

        # Excessive sink rate: -1100 fpm
        telemetry = make_telemetry(
            vertical_speed=-1100.0,
            altitude_agl=2500.0,
        )

        ctrl = FakeControl()
        adapter = FakeAircraftAdapter()

        status = takeover.perform_takeover(
            telemetry, adapter, ctrl,
            approach_type="VOR",
        )

        # Pre-fix: this FAILS (takeover proceeds)
        # Post-fix: retryable wait, no commands sent
        assert status.failed is False, \
            "VOR sink rate should be retryable, not hard fail"
        assert status.in_progress is True
        assert "sink_rate_safe" in status.waiting_for
        assert not ctrl.has_call("set_autopilot_master"), \
            "AP should NOT be disengaged while waiting for sink rate"


# ═══════════════════════════════════════════════════════════════════
# Neighbour test: ILS happy path with safe sink rate
# ═══════════════════════════════════════════════════════════════════

class TestSinkRateNeighbourILS:
    """Neighbour test: ILS takeover succeeds with safe sink rate."""

    def test_ils_takeover_completes_with_safe_sink_rate(self):
        """ILS takeover completes normally with -700 fpm (within limit)."""
        clock = FakeClock(start=0.0)
        config = TakeoverConfig(sink_rate_max=1000.0)
        takeover = AutopilotTakeover(config=config, clock=clock)

        takeover.status.in_progress = True
        takeover.takeover_start_time = clock()
        takeover.initial_parameters = {"airspeed": 140, "altitude": 3000}

        telemetry = make_telemetry(
            vertical_speed=-700.0,  # Within 1000 fpm limit
            altitude_agl=250.0,
            bank=0.0,
            pitch=2.5,
        )

        ctrl = FakeControl()
        adapter = FakeAircraftAdapter()
        ctrl.set_readback_ap(False)
        ctrl.set_readback_at(False)
        adapter._ap_state = False
        adapter._at_state = False

        status = takeover.perform_takeover(
            telemetry, adapter, ctrl,
            approach_type="ILS",
            decision_height=200.0,
        )

        # Should not fail due to sink rate
        assert status.failed is False, \
            f"ILS takeover should succeed with safe sink rate, got: {status.error_message}"
        # Commands should be sent
        assert ctrl.has_call("set_autopilot_master"), \
            "AP should be disengaged for safe ILS takeover"


# ═══════════════════════════════════════════════════════════════════
# Unit tests: _perform_safety_checks sink_rate_safe
# ═══════════════════════════════════════════════════════════════════

class TestSinkRateSafetyCheck:
    """Unit tests for sink_rate_safe in _perform_safety_checks."""

    def _make_takeover(self, sink_rate_max=1000.0):
        clock = FakeClock(start=0.0)
        config = TakeoverConfig(sink_rate_max=sink_rate_max)
        takeover = AutopilotTakeover(config=config, clock=clock)
        takeover.initial_parameters = {"airspeed": 140, "altitude": 5000}
        return takeover

    def test_sink_rate_within_limit_passes(self):
        """Normal descent (-500 fpm) passes."""
        takeover = self._make_takeover()
        telemetry = make_telemetry(vertical_speed=-500.0)
        checks = takeover._perform_safety_checks(telemetry)
        assert checks['sink_rate_safe'] is True

    def test_sink_rate_at_limit_passes(self):
        """Exactly -1000 fpm passes (boundary)."""
        takeover = self._make_takeover()
        telemetry = make_telemetry(vertical_speed=-1000.0)
        checks = takeover._perform_safety_checks(telemetry)
        assert checks['sink_rate_safe'] is True

    def test_sink_rate_exceeds_limit_fails(self):
        """-1100 fpm fails."""
        takeover = self._make_takeover()
        telemetry = make_telemetry(vertical_speed=-1100.0)
        checks = takeover._perform_safety_checks(telemetry)
        assert checks['sink_rate_safe'] is False

    def test_climb_always_passes(self):
        """Positive vertical speed passes."""
        takeover = self._make_takeover()
        telemetry = make_telemetry(vertical_speed=500.0)
        checks = takeover._perform_safety_checks(telemetry)
        assert checks['sink_rate_safe'] is True

    def test_level_flight_passes(self):
        """0 fpm passes."""
        takeover = self._make_takeover()
        telemetry = make_telemetry(vertical_speed=0.0)
        checks = takeover._perform_safety_checks(telemetry)
        assert checks['sink_rate_safe'] is True

    def test_custom_threshold_respected(self):
        """Custom 800 fpm limit: -850 fpm fails."""
        takeover = self._make_takeover(sink_rate_max=800.0)
        telemetry = make_telemetry(vertical_speed=-850.0)
        checks = takeover._perform_safety_checks(telemetry)
        assert checks['sink_rate_safe'] is False


# ═══════════════════════════════════════════════════════════════════
# Mode-dependent classification tests
# ═══════════════════════════════════════════════════════════════════

class TestSinkRateModeClassification:
    """Verify ILS=hard fail, VOR/NDB=retryable."""

    def _make_takeover(self, sink_rate_max=1000.0):
        clock = FakeClock(start=0.0)
        config = TakeoverConfig(sink_rate_max=sink_rate_max)
        takeover = AutopilotTakeover(config=config, clock=clock)
        takeover.status.in_progress = True
        takeover.takeover_start_time = clock()
        takeover.initial_parameters = {"airspeed": 140, "altitude": 3000}
        return takeover, FakeControl(), FakeAircraftAdapter()

    def test_ils_excessive_sink_rate_is_hard_fail(self):
        """ILS: sink_rate_safe failure → hard fail, takeover aborted."""
        takeover, ctrl, adapter = self._make_takeover()
        telemetry = make_telemetry(vertical_speed=-1200.0, altitude_agl=250.0)

        status = takeover.perform_takeover(
            telemetry, adapter, ctrl,
            approach_type="ILS",
            decision_height=200.0,
        )

        assert status.failed is True
        assert status.failure_reason == "hard_safety"
        assert "sink_rate_safe" in status.error_message.lower() or \
               "hard safety" in status.error_message.lower()

    def test_vor_excessive_sink_rate_is_retryable(self):
        """VOR: sink_rate_safe failure → retryable wait."""
        takeover, ctrl, adapter = self._make_takeover()
        telemetry = make_telemetry(vertical_speed=-1100.0, altitude_agl=2500.0)

        status = takeover.perform_takeover(
            telemetry, adapter, ctrl,
            approach_type="VOR",
        )

        assert status.failed is False
        assert status.in_progress is True
        assert "sink_rate_safe" in status.waiting_for

    def test_ndb_excessive_sink_rate_is_retryable(self):
        """NDB: same as VOR — retryable."""
        takeover, ctrl, adapter = self._make_takeover()
        telemetry = make_telemetry(vertical_speed=-1100.0, altitude_agl=2500.0)

        status = takeover.perform_takeover(
            telemetry, adapter, ctrl,
            approach_type="NDB",
        )

        assert status.failed is False
        assert "sink_rate_safe" in status.waiting_for

    def test_vor_retryable_recovery_when_sink_rate_improves(self):
        """VOR: first call -1100 fpm (wait), second call -500 fpm (proceeds)."""
        clock = FakeClock(start=0.0)
        config = TakeoverConfig(sink_rate_max=1000.0)
        takeover = AutopilotTakeover(config=config, clock=clock)

        takeover.status.in_progress = True
        takeover.takeover_start_time = clock()
        takeover.initial_parameters = {"airspeed": 140, "altitude": 3000}

        ctrl = FakeControl()
        adapter = FakeAircraftAdapter()

        # First call: excessive sink rate → waiting
        telemetry_bad = make_telemetry(vertical_speed=-1100.0, altitude_agl=2500.0)
        status1 = takeover.perform_takeover(
            telemetry_bad, adapter, ctrl,
            approach_type="VOR",
        )

        assert status1.failed is False
        assert "sink_rate_safe" in status1.waiting_for
        assert not ctrl.has_call("set_autopilot_master"), \
            "AP should NOT be disengaged while waiting"

        # Second call: sink rate improved → proceeds with commands
        ctrl.clear()
        adapter._ap_state = False
        adapter._at_state = False
        ctrl.set_readback_ap(False)
        ctrl.set_readback_at(False)

        telemetry_good = make_telemetry(vertical_speed=-500.0, altitude_agl=2500.0)
        status2 = takeover.perform_takeover(
            telemetry_good, adapter, ctrl,
            approach_type="VOR",
        )

        assert status2.failed is False
        assert status2.waiting_for == (), \
            f"waiting_for should be empty after recovery, got: {status2.waiting_for}"
        assert ctrl.has_call("set_autopilot_master"), \
            "AP should be disengaged after recovery"


# ═══════════════════════════════════════════════════════════════════
# Production-path test: through approach_phases
# ═══════════════════════════════════════════════════════════════════

class TestSinkRateProductionPath:
    """Production-path test via approach_phases._perform_takeover()."""

    def test_ils_sink_rate_failure_triggers_go_around(self):
        """ILS excessive sink rate → takeover failed → go around executed."""
        from unittest.mock import MagicMock
        from modules.approach_phases import FinalPhaseState

        # Mock system with required attributes
        system = MagicMock()
        system.approach_config.station.type = "ILS"
        system.approach_config.decision_height = 200.0

        clock = FakeClock(start=0.0)
        config = TakeoverConfig(sink_rate_max=1000.0)
        system.autopilot_takeover = AutopilotTakeover(config=config, clock=clock)
        system.autopilot_takeover.status.in_progress = True
        system.autopilot_takeover.takeover_start_time = clock()
        system.autopilot_takeover.initial_parameters = {"airspeed": 140, "altitude": 3000}

        system.control = FakeControl()
        system.aircraft_adapter = FakeAircraftAdapter()

        telemetry = make_telemetry(
            vertical_speed=-1200.0,
            altitude_agl=250.0,
        )

        # Create FinalPhaseState instance to access _perform_takeover
        state = FinalPhaseState(system)

        result = state._perform_takeover(telemetry)

        # Should return False (takeover failed)
        assert result is False
        # Go around should be triggered
        system.execute_go_around.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# FakeClock tests
# ═══════════════════════════════════════════════════════════════════

class TestSinkRateWithFakeClock:
    """Verify timeout interaction with sink rate checks."""

    def test_timeout_takes_priority_over_sink_rate(self):
        """If both timeout and sink rate fail, timeout error is returned."""
        clock = FakeClock(start=0.0)
        config = TakeoverConfig(
            sink_rate_max=1000.0,
            initialization_timeout=30.0,
        )
        takeover = AutopilotTakeover(config=config, clock=clock)

        takeover.status.in_progress = True
        takeover.takeover_start_time = clock()
        takeover.initial_parameters = {"airspeed": 140, "altitude": 3000}

        # Advance clock past timeout
        clock.advance(35.0)

        # Also have excessive sink rate
        telemetry = make_telemetry(vertical_speed=-1200.0, altitude_agl=250.0)

        ctrl = FakeControl()
        adapter = FakeAircraftAdapter()

        status = takeover.perform_takeover(
            telemetry, adapter, ctrl,
            approach_type="ILS",
            decision_height=200.0,
        )

        # Timeout is checked first (line 148-156), before safety checks
        assert status.failed is True
        assert "timeout" in status.error_message.lower()

    def test_sink_rate_retryable_respects_timeout(self):
        """VOR sink rate retryable: if timeout expires, fails with timeout."""
        clock = FakeClock(start=0.0)
        config = TakeoverConfig(
            sink_rate_max=1000.0,
            initialization_timeout=30.0,
        )
        takeover = AutopilotTakeover(config=config, clock=clock)

        takeover.status.in_progress = True
        takeover.takeover_start_time = clock()
        takeover.initial_parameters = {"airspeed": 140, "altitude": 3000}

        # First call: within timeout, sink rate retryable
        clock.advance(5.0)
        telemetry = make_telemetry(vertical_speed=-1100.0, altitude_agl=2500.0)
        ctrl = FakeControl()
        adapter = FakeAircraftAdapter()

        status1 = takeover.perform_takeover(
            telemetry, adapter, ctrl,
            approach_type="VOR",
        )
        assert status1.failed is False
        assert "sink_rate_safe" in status1.waiting_for

        # Second call: past timeout
        clock.advance(30.0)
        status2 = takeover.perform_takeover(
            telemetry, adapter, ctrl,
            approach_type="VOR",
        )
        assert status2.failed is True
        assert "timeout" in status2.error_message.lower()


# ═══════════════════════════════════════════════════════════════════
# Config tests
# ═══════════════════════════════════════════════════════════════════

class TestSinkRateConfig:
    """Configuration tests."""

    def test_default_sink_rate_threshold(self):
        """Default threshold is 1000 fpm."""
        config = TakeoverConfig()
        assert config.sink_rate_max == 1000.0

    def test_custom_sink_rate_threshold(self):
        """Custom threshold is settable."""
        config = TakeoverConfig(sink_rate_max=800.0)
        assert config.sink_rate_max == 800.0
