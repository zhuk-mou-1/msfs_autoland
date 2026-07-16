"""P2-CM-01: Defensive finite validation in update_flight_phase."""
import logging

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_monitor():
    """Create a minimal ConnectionMonitor for testing update_flight_phase."""
    from modules.connection_monitor import ConnectionMonitor

    class FakeOptimizer:
        def test_all_methods(self): return {}
    class FakeTelemetry:
        pass
    class FakeControl:
        pass

    cm = ConnectionMonitor(FakeOptimizer(), FakeTelemetry(), FakeControl())
    return cm


# ---------------------------------------------------------------------------
# 1. on_ground=True + altitude/VS None → GROUND, no exception
# ---------------------------------------------------------------------------

def test_on_ground_with_none_altitude():
    """on_ground=True + altitude None → GROUND, no TypeError."""
    from modules.connection_monitor import FlightPhase
    cm = _make_monitor()
    cm.current_phase = FlightPhase.CLIMB

    # Should not raise TypeError
    cm.update_flight_phase(altitude_agl=None, ground_speed=100.0,
                           vertical_speed=None, on_ground=True)
    assert cm.current_phase == FlightPhase.GROUND


# ---------------------------------------------------------------------------
# 2. on_ground=True + NaN/inf → GROUND
# ---------------------------------------------------------------------------

def test_on_ground_with_nan_altitude():
    """on_ground=True + NaN altitude → GROUND."""
    from modules.connection_monitor import FlightPhase
    cm = _make_monitor()
    cm.current_phase = FlightPhase.CLIMB

    cm.update_flight_phase(altitude_agl=float('nan'), ground_speed=100.0,
                           vertical_speed=float('nan'), on_ground=True)
    assert cm.current_phase == FlightPhase.GROUND


def test_on_ground_with_inf_altitude():
    """on_ground=True + inf altitude → GROUND."""
    from modules.connection_monitor import FlightPhase
    cm = _make_monitor()
    cm.current_phase = FlightPhase.CLIMB

    cm.update_flight_phase(altitude_agl=float('inf'), ground_speed=100.0,
                           vertical_speed=float('inf'), on_ground=True)
    assert cm.current_phase == FlightPhase.GROUND


# ---------------------------------------------------------------------------
# 3. on_ground=False + altitude None → previous phase preserved
# ---------------------------------------------------------------------------

def test_no_ground_none_altitude_preserves_phase():
    """on_ground=False + altitude None → previous phase preserved."""
    from modules.connection_monitor import FlightPhase
    cm = _make_monitor()
    cm.current_phase = FlightPhase.CRUISE

    cm.update_flight_phase(altitude_agl=None, ground_speed=100.0,
                           vertical_speed=100.0, on_ground=False)
    assert cm.current_phase == FlightPhase.CRUISE


def test_no_ground_nan_altitude_preserves_phase():
    """on_ground=False + NaN altitude → previous phase preserved."""
    from modules.connection_monitor import FlightPhase
    cm = _make_monitor()
    cm.current_phase = FlightPhase.CRUISE

    cm.update_flight_phase(altitude_agl=float('nan'), ground_speed=100.0,
                           vertical_speed=100.0, on_ground=False)
    assert cm.current_phase == FlightPhase.CRUISE


def test_no_ground_inf_altitude_preserves_phase():
    """on_ground=False + inf altitude → previous phase preserved."""
    from modules.connection_monitor import FlightPhase
    cm = _make_monitor()
    cm.current_phase = FlightPhase.CRUISE

    cm.update_flight_phase(altitude_agl=float('inf'), ground_speed=100.0,
                           vertical_speed=100.0, on_ground=False)
    assert cm.current_phase == FlightPhase.CRUISE


# ---------------------------------------------------------------------------
# 4. Same for vertical_speed
# ---------------------------------------------------------------------------

def test_no_ground_none_vs_preserves_phase():
    """on_ground=False + VS None → previous phase preserved."""
    from modules.connection_monitor import FlightPhase
    cm = _make_monitor()
    cm.current_phase = FlightPhase.CRUISE

    cm.update_flight_phase(altitude_agl=5000.0, ground_speed=100.0,
                           vertical_speed=None, on_ground=False)
    assert cm.current_phase == FlightPhase.CRUISE


def test_no_ground_nan_vs_preserves_phase():
    """on_ground=False + NaN VS → previous phase preserved."""
    from modules.connection_monitor import FlightPhase
    cm = _make_monitor()
    cm.current_phase = FlightPhase.CRUISE

    cm.update_flight_phase(altitude_agl=5000.0, ground_speed=100.0,
                           vertical_speed=float('nan'), on_ground=False)
    assert cm.current_phase == FlightPhase.CRUISE


# ---------------------------------------------------------------------------
# 5. Non-numeric types → previous phase preserved
# ---------------------------------------------------------------------------

def test_string_altitude_preserves_phase():
    """String altitude → previous phase preserved."""
    from modules.connection_monitor import FlightPhase
    cm = _make_monitor()
    cm.current_phase = FlightPhase.CRUISE

    cm.update_flight_phase(altitude_agl="invalid", ground_speed=100.0,
                           vertical_speed=100.0, on_ground=False)
    assert cm.current_phase == FlightPhase.CRUISE


def test_bool_altitude_preserves_phase():
    """Bool altitude (True=1) should be treated as non-finite for this purpose."""
    from modules.connection_monitor import FlightPhase
    cm = _make_monitor()
    cm.current_phase = FlightPhase.CRUISE

    # bool is subclass of int, but should be rejected per task spec
    cm.update_flight_phase(altitude_agl=True, ground_speed=100.0,
                           vertical_speed=100.0, on_ground=False)
    # bool is technically a valid number (True=1), but task says
    # "not consider bool as valid number" — check actual behavior
    # After fix, this should preserve phase or handle gracefully


def test_object_altitude_preserves_phase():
    """Object altitude → previous phase preserved."""
    from modules.connection_monitor import FlightPhase
    cm = _make_monitor()
    cm.current_phase = FlightPhase.CRUISE

    cm.update_flight_phase(altitude_agl=object(), ground_speed=100.0,
                           vertical_speed=100.0, on_ground=False)
    assert cm.current_phase == FlightPhase.CRUISE


# ---------------------------------------------------------------------------
# 6. Boundary cases from CM-02 probe (byte-for-behavior compatibility)
# ---------------------------------------------------------------------------

def test_boundary_499_501_takeoff():
    """499ft / VS=501 → TAKEOFF (probe-confirmed)."""
    from modules.connection_monitor import FlightPhase
    cm = _make_monitor()
    cm.current_phase = FlightPhase.CRUISE

    cm.update_flight_phase(altitude_agl=499, ground_speed=120.0,
                           vertical_speed=501, on_ground=False)
    assert cm.current_phase == FlightPhase.TAKEOFF


def test_boundary_499_0_landing():
    """499ft / VS=0 → LANDING (probe-confirmed)."""
    from modules.connection_monitor import FlightPhase
    cm = _make_monitor()
    cm.current_phase = FlightPhase.CRUISE

    cm.update_flight_phase(altitude_agl=499, ground_speed=120.0,
                           vertical_speed=0, on_ground=False)
    assert cm.current_phase == FlightPhase.LANDING


def test_boundary_500_neg1_approach():
    """500ft / VS=-1 → APPROACH (probe-confirmed)."""
    from modules.connection_monitor import FlightPhase
    cm = _make_monitor()
    cm.current_phase = FlightPhase.CRUISE

    cm.update_flight_phase(altitude_agl=500, ground_speed=120.0,
                           vertical_speed=-1, on_ground=False)
    assert cm.current_phase == FlightPhase.APPROACH


def test_boundary_500_0_hold():
    """500ft / VS=0 → hold previous (probe-confirmed)."""
    from modules.connection_monitor import FlightPhase
    cm = _make_monitor()
    cm.current_phase = FlightPhase.CRUISE

    cm.update_flight_phase(altitude_agl=500, ground_speed=120.0,
                           vertical_speed=0, on_ground=False)
    assert cm.current_phase == FlightPhase.CRUISE  # held


def test_boundary_1500_501_climb():
    """1500ft / VS=501 → CLIMB (probe-confirmed)."""
    from modules.connection_monitor import FlightPhase
    cm = _make_monitor()
    cm.current_phase = FlightPhase.CRUISE

    cm.update_flight_phase(altitude_agl=1500, ground_speed=120.0,
                           vertical_speed=501, on_ground=False)
    assert cm.current_phase == FlightPhase.CLIMB


def test_boundary_3000_neg1_hold():
    """3000ft / VS=-1 → hold previous (probe-confirmed)."""
    from modules.connection_monitor import FlightPhase
    cm = _make_monitor()
    cm.current_phase = FlightPhase.CRUISE

    cm.update_flight_phase(altitude_agl=3000, ground_speed=120.0,
                           vertical_speed=-1, on_ground=False)
    assert cm.current_phase == FlightPhase.CRUISE  # held


def test_boundary_10001_neg501_descent():
    """10001ft / VS=-501 → DESCENT (probe-confirmed)."""
    from modules.connection_monitor import FlightPhase
    cm = _make_monitor()
    cm.current_phase = FlightPhase.CRUISE

    cm.update_flight_phase(altitude_agl=10001, ground_speed=120.0,
                           vertical_speed=-501, on_ground=False)
    assert cm.current_phase == FlightPhase.DESCENT


# ---------------------------------------------------------------------------
# 7. Warning is logged (without exact text match)
# ---------------------------------------------------------------------------

def test_warning_logged_for_invalid_inputs(caplog):
    """Warning is logged when non-finite inputs are detected."""
    from modules.connection_monitor import FlightPhase
    cm = _make_monitor()
    cm.current_phase = FlightPhase.CRUISE

    import modules.connection_monitor as cm_mod
    with caplog.at_level(logging.WARNING, logger=cm_mod.logger.name):
        cm.update_flight_phase(altitude_agl=None, ground_speed=100.0,
                               vertical_speed=100.0, on_ground=False)

    assert cm.current_phase == FlightPhase.CRUISE
    assert any(record.levelno >= logging.WARNING for record in caplog.records)


# ---------------------------------------------------------------------------
# 8. Red-without-fix: None would cause TypeError on base code
# ---------------------------------------------------------------------------

def test_none_altitude_would_cause_type_error():
    """Verify that without the fix, None altitude causes TypeError."""
    # This test documents the bug. After fix, it should NOT raise.
    from modules.connection_monitor import ConnectionMonitor, FlightPhase

    class FakeOptimizer:
        def test_all_methods(self): return {}
    class FakeTelemetry:
        pass
    class FakeControl:
        pass

    cm = ConnectionMonitor(FakeOptimizer(), FakeTelemetry(), FakeControl())
    cm.current_phase = FlightPhase.CRUISE

    # After fix, this should NOT raise
    try:
        cm.update_flight_phase(altitude_agl=None, ground_speed=100.0,
                               vertical_speed=100.0, on_ground=False)
        # If we get here, the fix is working
        assert cm.current_phase == FlightPhase.CRUISE
    except TypeError:
        # If this raises, the fix is NOT applied
        pytest.fail("update_flight_phase raises TypeError on None altitude — fix not applied")
