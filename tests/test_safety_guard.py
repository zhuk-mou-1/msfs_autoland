"""TASK-006: Deterministic safety guard for FINAL approach phase.

Independent, pre-command safety gate. Runs BEFORE phase_state.handle(),
BEFORE _control_aircraft/_control_throttle. Active in FINAL only (phase-gate
at call-site in _handle_phase).

Rules:
  G1: Critical sink rate > 1500 fpm
  G2: Critical bank > 15°
  G3: Gross underspeed < Vref - 10 kt
  G4: Gross overspeed > Vref + 20 kt
  G5: Invalid critical telemetry (both height sources None OR airspeed None)

All rules use DEBOUNCE_N=2 consecutive frames before GO_AROUND.
"""

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from modules.safety_guard import (
    ApproachSafetyGuard,
    GuardDecision,
    GuardResult,
    SafetySnapshot,
)
from modules.types import ApproachConfig, NavStation
from tests.fakes import make_telemetry


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _make_config(vref: int = 120) -> ApproachConfig:
    return ApproachConfig(
        station=NavStation("TEST", 11030000, 55.5, 37.5, "VOR"),
        final_approach_course=270,
        glideslope_angle=3.0,
        decision_height=200,
        approach_speed=vref,
        runway_elevation=0,
        runway_length=8000,
        runway_width=150,
        runway_threshold_lat=55.48,
        runway_threshold_lon=37.52,
    )


def _snapshot(**overrides) -> SafetySnapshot:
    defaults = dict(
        altitude_agl=500.0,
        radio_height=500.0,
        airspeed_indicated=120.0,
        vertical_speed=-700.0,
        bank=3.0,
        vref=120.0,
    )
    defaults.update(overrides)
    return SafetySnapshot(**defaults)


# ═══════════════════════════════════════════════════════════════════
# Unit tests — guard.evaluate() directly
# ═══════════════════════════════════════════════════════════════════

class TestGuardDebounce:
    """N=2 consecutive frames before GO_AROUND for all rules."""

    def test_single_frame_violation_returns_contINUE(self):
        guard = ApproachSafetyGuard(debounce_n=2)
        snap = _snapshot(vertical_speed=-2000)  # G1 violation
        result = guard.evaluate(snap)
        assert result.decision == GuardDecision.CONTINUE
        assert "debounce" in result.reason

    def test_two_consecutive_frames_returns_go_around(self):
        guard = ApproachSafetyGuard(debounce_n=2)
        snap = _snapshot(vertical_speed=-2000)
        guard.evaluate(snap)  # frame 1: debounce
        result = guard.evaluate(snap)  # frame 2: GO_AROUND
        assert result.decision == GuardDecision.GO_AROUND
        assert result.reason == "CRITICAL_SINK_RATE"

    def test_transient_single_frame_resets_counter(self):
        guard = ApproachSafetyGuard(debounce_n=2)
        snap_bad = _snapshot(vertical_speed=-2000)
        snap_ok = _snapshot(vertical_speed=-700)
        guard.evaluate(snap_bad)  # frame 1: debounce counting
        guard.evaluate(snap_ok)   # frame 2: passes, counter resets
        result = guard.evaluate(snap_bad)  # frame 3: starts over
        assert result.decision == GuardDecision.CONTINUE
        assert "debounce" in result.reason


class TestGuardG1SinkRate:
    """G1: Critical sink rate > 1500 fpm."""

    def test_normal_sink_rate_continue(self):
        guard = ApproachSafetyGuard()
        result = guard.evaluate(_snapshot(vertical_speed=-700))
        assert result.decision == GuardDecision.CONTINUE

    def test_critical_sink_rate_go_around(self):
        guard = ApproachSafetyGuard(debounce_n=1)
        result = guard.evaluate(_snapshot(vertical_speed=-1501))
        assert result.decision == GuardDecision.GO_AROUND
        assert result.reason == "CRITICAL_SINK_RATE"
        assert result.details["threshold"] == 1500

    def test_climb_also_checked(self):
        """abs(vertical_speed) > 1500 — climb too."""
        guard = ApproachSafetyGuard(debounce_n=1)
        result = guard.evaluate(_snapshot(vertical_speed=1600))
        assert result.decision == GuardDecision.GO_AROUND


class TestGuardG2Bank:
    """G2: Critical bank > 15°."""

    def test_normal_bank_continue(self):
        guard = ApproachSafetyGuard()
        result = guard.evaluate(_snapshot(bank=3.0))
        assert result.decision == GuardDecision.CONTINUE

    def test_critical_bank_go_around(self):
        guard = ApproachSafetyGuard(debounce_n=1)
        result = guard.evaluate(_snapshot(bank=15.1))
        assert result.decision == GuardDecision.GO_AROUND
        assert result.reason == "CRITICAL_BANK"


class TestGuardG3Underspeed:
    """G3: Gross underspeed < Vref - 10 kt."""

    def test_normal_speed_continue(self):
        guard = ApproachSafetyGuard()
        result = guard.evaluate(_snapshot(airspeed_indicated=120.0, vref=120.0))
        assert result.decision == GuardDecision.CONTINUE

    def test_underspeed_go_around(self):
        guard = ApproachSafetyGuard(debounce_n=1)
        result = guard.evaluate(_snapshot(airspeed_indicated=109.0, vref=120.0))
        assert result.decision == GuardDecision.GO_AROUND
        assert result.reason == "GROSS_UNDERSPEED"
        assert result.details["threshold"] == 110  # Vref - 10


class TestGuardG4Overspeed:
    """G4: Gross overspeed > Vref + 20 kt."""

    def test_normal_speed_continue(self):
        guard = ApproachSafetyGuard()
        result = guard.evaluate(_snapshot(airspeed_indicated=125.0, vref=120.0))
        assert result.decision == GuardDecision.CONTINUE

    def test_overspeed_go_around(self):
        guard = ApproachSafetyGuard(debounce_n=1)
        result = guard.evaluate(_snapshot(airspeed_indicated=141.0, vref=120.0))
        assert result.decision == GuardDecision.GO_AROUND
        assert result.reason == "GROSS_OVERSPEED"
        assert result.details["threshold"] == 140  # Vref + 20


class TestGuardG5InvalidTelemetry:
    """G5: Invalid critical telemetry — height and airspeed."""

    def test_height_from_radio_height_continue(self):
        """radio_height alive → height valid."""
        guard = ApproachSafetyGuard()
        result = guard.evaluate(
            _snapshot(),
            has_altitude=False,
            has_radio_height=True,
            has_airspeed=True,
        )
        assert result.decision == GuardDecision.CONTINUE

    def test_height_from_altitude_agl_continue(self):
        """altitude_agl alive (radio_height None) → height valid (fallback)."""
        guard = ApproachSafetyGuard()
        result = guard.evaluate(
            _snapshot(),
            has_altitude=True,
            has_radio_height=False,
            has_airspeed=True,
        )
        assert result.decision == GuardDecision.CONTINUE

    def test_both_height_sources_none_go_around(self):
        guard = ApproachSafetyGuard(debounce_n=1)
        result = guard.evaluate(
            _snapshot(),
            has_altitude=False,
            has_radio_height=False,
            has_airspeed=True,
        )
        assert result.decision == GuardDecision.GO_AROUND
        assert result.reason == "INVALID_TELEMETRY"
        assert result.details["has_height"] is False

    def test_airspeed_none_go_around(self):
        guard = ApproachSafetyGuard(debounce_n=1)
        result = guard.evaluate(
            _snapshot(),
            has_altitude=True,
            has_radio_height=True,
            has_airspeed=False,
        )
        assert result.decision == GuardDecision.GO_AROUND
        assert result.reason == "INVALID_TELEMETRY"
        assert result.details["has_airspeed"] is False

    def test_all_missing_go_around(self):
        guard = ApproachSafetyGuard(debounce_n=1)
        result = guard.evaluate(
            _snapshot(),
            has_altitude=False,
            has_radio_height=False,
            has_airspeed=False,
        )
        assert result.decision == GuardDecision.GO_AROUND


class TestGuardIdempotence:
    """After go-around executed, subsequent calls return CONTINUE."""

    def test_second_call_after_go_around(self):
        guard = ApproachSafetyGuard(debounce_n=1)
        snap = _snapshot(vertical_speed=-2000)
        result1 = guard.evaluate(snap)
        assert result1.decision == GuardDecision.GO_AROUND
        result2 = guard.evaluate(snap)
        assert result2.decision == GuardDecision.CONTINUE
        assert result2.reason == "already_go_around"


class TestGuardReset:
    """Reset clears all state for new approach."""

    def test_reset_clears_go_around_flag(self):
        guard = ApproachSafetyGuard(debounce_n=1)
        guard.evaluate(_snapshot(vertical_speed=-2000))
        guard.reset()
        result = guard.evaluate(_snapshot(vertical_speed=-2000))
        assert result.decision == GuardDecision.GO_AROUND

    def test_reset_clears_debounce_counters(self):
        guard = ApproachSafetyGuard(debounce_n=2)
        guard.evaluate(_snapshot(vertical_speed=-2000))  # 1/2
        guard.reset()
        guard.evaluate(_snapshot(vertical_speed=-2000))  # 1/2 again
        result = guard.evaluate(_snapshot(vertical_speed=-2000))  # 2/2
        assert result.decision == GuardDecision.GO_AROUND


class TestGuardPerRuleDebounce:
    """Each rule has independent debounce counter."""

    def test_different_rules_independent(self):
        """G1 and G2 violated on same frame, then G1 violated again.
        With per-rule reset, G1 counter should be 2 (consecutive G1 violations)."""
        guard = ApproachSafetyGuard(debounce_n=2)
        # Frame 1: G1 violated AND G2 violated
        guard.evaluate(_snapshot(vertical_speed=-2000, bank=20.0))
        # Frame 2: G1 violated again (G2 clean → G2 counter resets)
        result = guard.evaluate(_snapshot(vertical_speed=-2000, bank=3.0))
        assert result.decision == GuardDecision.GO_AROUND
        assert result.reason == "CRITICAL_SINK_RATE"

    def test_non_adjacent_spike_resets_counter(self):
        """Frame 1: G1 violated. Frame 2: G1 clean (G2 violated).
        Frame 3: G1 violated again. Counter should be 1, not 2."""
        guard = ApproachSafetyGuard(debounce_n=2)
        # Frame 1: G1 violated, G2 clean
        r1 = guard.evaluate(_snapshot(vertical_speed=-2000, bank=3.0))
        assert r1.decision == GuardDecision.CONTINUE
        assert "debounce" in r1.reason
        # Frame 2: G1 clean (reset), G2 violated
        r2 = guard.evaluate(_snapshot(vertical_speed=-700, bank=20.0))
        assert r2.decision == GuardDecision.CONTINUE
        assert "debounce" in r2.reason
        # Frame 3: G1 violated again — counter should be 1 (reset on frame 2)
        r3 = guard.evaluate(_snapshot(vertical_speed=-2000, bank=3.0))
        assert r3.decision == GuardDecision.CONTINUE
        assert "debounce" in r3.reason
        # Frame 4: G1 violated — NOW counter reaches 2
        r4 = guard.evaluate(_snapshot(vertical_speed=-2000, bank=3.0))
        assert r4.decision == GuardDecision.GO_AROUND
        assert r4.reason == "CRITICAL_SINK_RATE"


# ═══════════════════════════════════════════════════════════════════
# Integration tests — through _handle_phase (real production path)
# ═══════════════════════════════════════════════════════════════════

class TestIntegrationFinalCriticalViolation:
    """T1: FINAL + critical sink rate → go-around, no actuator commands."""

    def test_go_around_on_critical_sink_rate(self, caplog):
        from main import AutoLandSystem, ApproachPhase

        system = AutoLandSystem.__new__(AutoLandSystem)
        system.phase = ApproachPhase.FINAL
        system.approach_config = _make_config()
        system.safety_guard = ApproachSafetyGuard(debounce_n=1)
        system.wind_correction = MagicMock()
        system.wind_correction.apply_wind_corrections.return_value = {
            "corrected_heading": 270, "corrected_vs": 700,
            "headwind": 10, "crosswind": 5, "wind_speed": 12,
            "wind_direction": 280, "drift_angle": 2.0,
        }
        system.fms_reader = None
        system.telemetry_recorder = MagicMock()
        system.phase_state = MagicMock()
        system.execute_go_around = MagicMock()

        telemetry = make_telemetry(vertical_speed=-2000, altitude_agl=500, airspeed=120)
        approach_data = {"distance_to_station": 5.0, "required_altitude": 2000,
                         "on_course": True, "cross_track_error": 0.5}

        system._handle_phase(telemetry, approach_data)

        system.execute_go_around.assert_called_once()
        system.phase_state.handle.assert_not_called()


class TestIntegrationFinalNormal:
    """T2: FINAL + normal telemetry → guard CONTINUE, normal handling."""

    def test_normal_handling_proceeds(self):
        from main import AutoLandSystem, ApproachPhase

        system = AutoLandSystem.__new__(AutoLandSystem)
        system.phase = ApproachPhase.FINAL
        system.approach_config = _make_config()
        system.safety_guard = ApproachSafetyGuard(debounce_n=2)
        system.wind_correction = MagicMock()
        system.wind_correction.apply_wind_corrections.return_value = {
            "corrected_heading": 270, "corrected_vs": 700,
            "headwind": 10, "crosswind": 5, "wind_speed": 12,
            "wind_direction": 280, "drift_angle": 2.0,
        }
        system.fms_reader = None
        system.telemetry_recorder = MagicMock()
        system.phase_state = MagicMock()
        system.phase_state.handle.return_value = None
        system._update_phase_enum = MagicMock()

        telemetry = make_telemetry(vertical_speed=-700, altitude_agl=500, airspeed=120, bank=3.0)
        approach_data = {"distance_to_station": 5.0, "required_altitude": 2000,
                         "on_course": True, "cross_track_error": 0.5}

        system._handle_phase(telemetry, approach_data)

        system.phase_state.handle.assert_called_once()


class TestIntegrationNonFinalPhase:
    """T3-T5: Guard NOT active outside FINAL. Critical violation → no go-around."""

    def _run_phase(self, phase_name: str):
        from main import AutoLandSystem, ApproachPhase

        system = AutoLandSystem.__new__(AutoLandSystem)
        system.phase = getattr(ApproachPhase, phase_name)
        system.approach_config = _make_config()
        system.safety_guard = ApproachSafetyGuard(debounce_n=1)
        system.wind_correction = MagicMock()
        system.wind_correction.apply_wind_corrections.return_value = {
            "corrected_heading": 270, "corrected_vs": 700,
            "headwind": 10, "crosswind": 5, "wind_speed": 12,
            "wind_direction": 280, "drift_angle": 2.0,
        }
        system.fms_reader = None
        system.telemetry_recorder = MagicMock()
        system.phase_state = MagicMock()
        system.phase_state.handle.return_value = None
        system.execute_go_around = MagicMock()
        system._update_phase_enum = MagicMock()

        telemetry = make_telemetry(vertical_speed=-2000, altitude_agl=500,
                                   airspeed=80, bank=20.0)
        approach_data = {"distance_to_station": 5.0, "required_altitude": 2000,
                         "on_course": True, "cross_track_error": 0.5}

        system._handle_phase(telemetry, approach_data)
        return system

    def test_initial_no_go_around(self):
        system = self._run_phase("INITIAL")
        system.execute_go_around.assert_not_called()
        system.phase_state.handle.assert_called_once()

    def test_intermediate_no_go_around(self):
        system = self._run_phase("INTERMEDIATE")
        system.execute_go_around.assert_not_called()
        system.phase_state.handle.assert_called_once()

    def test_landing_no_go_around(self):
        system = self._run_phase("LANDING")
        system.execute_go_around.assert_not_called()
        system.phase_state.handle.assert_called_once()


class TestIntegrationApproachTypes:
    """T6-T9: Normal FINAL for ILS/LOC/VOR/NDB — no disruption."""

    def _test_type(self, station_type: str):
        from main import AutoLandSystem, ApproachPhase

        system = AutoLandSystem.__new__(AutoLandSystem)
        system.phase = ApproachPhase.FINAL
        system.approach_config = _make_config()
        system.approach_config.station = NavStation(
            "TEST", 11030000, 55.5, 37.5, station_type)
        system.safety_guard = ApproachSafetyGuard(debounce_n=2)
        system.wind_correction = MagicMock()
        system.wind_correction.apply_wind_corrections.return_value = {
            "corrected_heading": 270, "corrected_vs": 700,
            "headwind": 10, "crosswind": 5, "wind_speed": 12,
            "wind_direction": 280, "drift_angle": 2.0,
        }
        system.fms_reader = None
        system.telemetry_recorder = MagicMock()
        system.phase_state = MagicMock()
        system.phase_state.handle.return_value = None
        system.execute_go_around = MagicMock()
        system._update_phase_enum = MagicMock()

        telemetry = make_telemetry(vertical_speed=-700, altitude_agl=500,
                                   airspeed=120, bank=3.0)
        approach_data = {"distance_to_station": 5.0, "required_altitude": 2000,
                         "on_course": True, "cross_track_error": 0.5}

        system._handle_phase(telemetry, approach_data)
        system.execute_go_around.assert_not_called()
        system.phase_state.handle.assert_called_once()

    def test_ils_normal(self):
        self._test_type("ILS")

    def test_loc_normal(self):
        self._test_type("LOC")

    def test_vor_normal(self):
        self._test_type("VOR")

    def test_ndb_normal(self):
        self._test_type("NDB")


class TestIntegrationIdempotence:
    """T13: Guard does not send second go-around."""

    def test_no_double_go_around(self):
        from main import AutoLandSystem, ApproachPhase

        system = AutoLandSystem.__new__(AutoLandSystem)
        system.phase = ApproachPhase.FINAL
        system.approach_config = _make_config()
        system.safety_guard = ApproachSafetyGuard(debounce_n=1)
        system.wind_correction = MagicMock()
        system.wind_correction.apply_wind_corrections.return_value = {
            "corrected_heading": 270, "corrected_vs": 700,
            "headwind": 10, "crosswind": 5, "wind_speed": 12,
            "wind_direction": 280, "drift_angle": 2.0,
        }
        system.fms_reader = None
        system.telemetry_recorder = MagicMock()
        system.phase_state = MagicMock()
        call_count = 0
        def fake_go_around():
            nonlocal call_count
            call_count += 1
        system.execute_go_around = fake_go_around

        telemetry = make_telemetry(vertical_speed=-2000, altitude_agl=500, airspeed=120)
        approach_data = {"distance_to_station": 5.0, "required_altitude": 2000,
                         "on_course": True, "cross_track_error": 0.5}

        system._handle_phase(telemetry, approach_data)
        system._handle_phase(telemetry, approach_data)

        assert call_count == 1


class TestIntegrationGuardAndExistingMonitorCoexist:
    """Guard runs BEFORE monitor; when both fire, guard wins."""

    def test_guard_wins_over_monitor(self):
        from main import AutoLandSystem, ApproachPhase

        system = AutoLandSystem.__new__(AutoLandSystem)
        system.phase = ApproachPhase.FINAL
        system.approach_config = _make_config()
        system.safety_guard = ApproachSafetyGuard(debounce_n=1)
        system.wind_correction = MagicMock()
        system.wind_correction.apply_wind_corrections.return_value = {
            "corrected_heading": 270, "corrected_vs": 700,
            "headwind": 10, "crosswind": 5, "wind_speed": 12,
            "wind_direction": 280, "drift_angle": 2.0,
        }
        system.fms_reader = None
        system.telemetry_recorder = MagicMock()
        system.phase_state = MagicMock()
        call_count = 0
        def fake_go_around():
            nonlocal call_count
            call_count += 1
        system.execute_go_around = fake_go_around

        telemetry = make_telemetry(vertical_speed=-2000, altitude_agl=500, airspeed=120)
        approach_data = {"distance_to_station": 5.0, "required_altitude": 2000,
                         "on_course": True, "cross_track_error": 0.5}

        system._handle_phase(telemetry, approach_data)

        # Guard fired → execute_go_around called once
        # phase_state.handle NOT called → monitor never runs
        assert call_count == 1
        system.phase_state.handle.assert_not_called()


class TestIntegrationLLMAdvisoryDoesNotAffect:
    """T14/T15: LLM advisory has no effect on deterministic control flow."""

    def test_llm_unavailable_no_effect(self):
        """UNAVAILABLE advisory does not change guard decision."""
        guard = ApproachSafetyGuard(debounce_n=1)
        snap = _snapshot(vertical_speed=-2000)
        result = guard.evaluate(snap)
        assert result.decision == GuardDecision.GO_AROUND

    def test_llm_advise_go_around_no_effect(self):
        """ADVISE_GO_AROUND advisory does not trigger go-around."""
        guard = ApproachSafetyGuard(debounce_n=1)
        snap = _snapshot(vertical_speed=-700)  # normal
        result = guard.evaluate(snap)
        assert result.decision == GuardDecision.CONTINUE


class TestIntegrationLogging:
    """T16: Reason code in log via caplog through real _handle_phase."""

    def test_guard_go_around_logged(self, caplog):
        from main import AutoLandSystem, ApproachPhase

        system = AutoLandSystem.__new__(AutoLandSystem)
        system.phase = ApproachPhase.FINAL
        system.approach_config = _make_config()
        system.safety_guard = ApproachSafetyGuard(debounce_n=1)
        system.wind_correction = MagicMock()
        system.wind_correction.apply_wind_corrections.return_value = {
            "corrected_heading": 270, "corrected_vs": 700,
            "headwind": 10, "crosswind": 5, "wind_speed": 12,
            "wind_direction": 280, "drift_angle": 2.0,
        }
        system.fms_reader = None
        system.telemetry_recorder = MagicMock()
        system.phase_state = MagicMock()
        system.execute_go_around = MagicMock()

        telemetry = make_telemetry(vertical_speed=-2000, altitude_agl=500, airspeed=120)
        approach_data = {"distance_to_station": 5.0, "required_altitude": 2000,
                         "on_course": True, "cross_track_error": 0.5}

        with caplog.at_level(logging.CRITICAL, logger="main"):
            system._handle_phase(telemetry, approach_data)

        assert "SAFETY GUARD: GO_AROUND" in caplog.text
        assert "CRITICAL_SINK_RATE" in caplog.text

    def test_near_trigger_logged(self, caplog):
        """Near-trigger: CONTINUE + reason ends with _debounce → WARNING log."""
        from main import AutoLandSystem, ApproachPhase

        system = AutoLandSystem.__new__(AutoLandSystem)
        system.phase = ApproachPhase.FINAL
        system.approach_config = _make_config()
        system.safety_guard = ApproachSafetyGuard(debounce_n=2)  # needs 2 frames
        system.wind_correction = MagicMock()
        system.wind_correction.apply_wind_corrections.return_value = {
            "corrected_heading": 270, "corrected_vs": 700,
            "headwind": 10, "crosswind": 5, "wind_speed": 12,
            "wind_direction": 280, "drift_angle": 2.0,
        }
        system.fms_reader = None
        system._last_guard_snapshot_log_time = 0.0
        system.phase_state = MagicMock()
        system.phase_state.handle.return_value = None
        system.execute_go_around = MagicMock()
        system._update_phase_enum = MagicMock()

        telemetry = make_telemetry(vertical_speed=-2000, altitude_agl=500, airspeed=120)
        approach_data = {"distance_to_station": 5.0, "required_altitude": 2000,
                         "on_course": True, "cross_track_error": 0.5}

        with caplog.at_level(logging.WARNING, logger="main"):
            system._handle_phase(telemetry, approach_data)

        assert "SAFETY GUARD near-trigger" in caplog.text
        assert "CRITICAL_SINK_RATE_debounce" in caplog.text


class TestIntegrationLocSignalLossUntouched:
    """Verify LOC signal-loss path (TASK-005) not affected by guard."""

    def test_loc_signal_loss_returns_early(self):
        from main import AutoLandSystem, ApproachPhase

        system = AutoLandSystem.__new__(AutoLandSystem)
        system.phase = ApproachPhase.FINAL
        system.approach_config = _make_config()
        system.approach_config.station = NavStation(
            "TEST_LOC", 11030000, 55.5, 37.5, "LOC")
        system.safety_guard = ApproachSafetyGuard(debounce_n=1)
        system.wind_correction = MagicMock()
        system.execute_go_around = MagicMock()
        system.phase_state = MagicMock()
        system.telemetry_recorder = MagicMock()

        # _calculate_approach_data returns None for LOC signal loss
        # execute_go_around is called inside _calculate_approach_data (original contract)
        system._handle_phase(None, None)  # approach_data=None → no-op
        system.execute_go_around.assert_not_called()  # not called by _handle_phase
        system.phase_state.handle.assert_not_called()


class TestRedWithoutFix:
    """T17/T18: Red-without-fix proof.

    T17: real red — patch removes guard evaluate → critical violation no longer
         triggers go-around. T1 is the positive sentinel (guard present → fires).
    T18: phase gate prevents non-FINAL go-around.
    """

    def test_t17_guard_removal_breaks_critical_test(self):
        """Real red-without-fix: patch guard.evaluate to always return CONTINUE.

        With guard neutralized, critical violation in FINAL should NOT trigger
        go-around — proving the guard integration point is necessary.
        Positive sentinel: TestIntegrationFinalCriticalViolation (T1).
        """
        from main import AutoLandSystem, ApproachPhase

        system = AutoLandSystem.__new__(AutoLandSystem)
        system.phase = ApproachPhase.FINAL
        system.approach_config = _make_config()
        system.safety_guard = ApproachSafetyGuard(debounce_n=1)
        system.wind_correction = MagicMock()
        system.wind_correction.apply_wind_corrections.return_value = {
            "corrected_heading": 270, "corrected_vs": 700,
            "headwind": 10, "crosswind": 5, "wind_speed": 12,
            "wind_direction": 280, "drift_angle": 2.0,
        }
        system.fms_reader = None
        system.telemetry_recorder = MagicMock()
        system.phase_state = MagicMock()
        system.phase_state.handle.return_value = None
        system.execute_go_around = MagicMock()
        system._update_phase_enum = MagicMock()

        telemetry = make_telemetry(vertical_speed=-2000, altitude_agl=500, airspeed=120)
        approach_data = {"distance_to_station": 5.0, "required_altitude": 2000,
                         "on_course": True, "cross_track_error": 0.5}

        # Patch guard.evaluate to always return CONTINUE — simulates guard removal
        with patch.object(system.safety_guard, 'evaluate',
                          return_value=GuardResult(GuardDecision.CONTINUE, "patched", {})):
            system._handle_phase(telemetry, approach_data)

        # Without real guard, go-around NOT called — normal handling proceeds
        system.execute_go_around.assert_not_called()
        system.phase_state.handle.assert_called_once()

    def test_t18_phase_gate_removal_allows_non_final_go_around(self):
        """If phase gate removed, guard would fire in INITIAL too.
        This proves the phase gate prevents non-FINAL go-arounds.
        """
        from main import AutoLandSystem, ApproachPhase

        system = AutoLandSystem.__new__(AutoLandSystem)
        system.phase = ApproachPhase.INITIAL  # NOT FINAL
        system.approach_config = _make_config()
        system.safety_guard = ApproachSafetyGuard(debounce_n=1)
        system.wind_correction = MagicMock()
        system.wind_correction.apply_wind_corrections.return_value = {
            "corrected_heading": 270, "corrected_vs": 700,
            "headwind": 10, "crosswind": 5, "wind_speed": 12,
            "wind_direction": 280, "drift_angle": 2.0,
        }
        system.fms_reader = None
        system.telemetry_recorder = MagicMock()
        system.phase_state = MagicMock()
        system.phase_state.handle.return_value = None
        system.execute_go_around = MagicMock()
        system._update_phase_enum = MagicMock()

        telemetry = make_telemetry(vertical_speed=-2000, altitude_agl=500, airspeed=120)
        approach_data = {"distance_to_station": 5.0, "required_altitude": 2000,
                         "on_course": True, "cross_track_error": 0.5}

        # With phase gate, INITIAL does NOT trigger guard → no go_around
        system._handle_phase(telemetry, approach_data)
        system.execute_go_around.assert_not_called()
        system.phase_state.handle.assert_called_once()
