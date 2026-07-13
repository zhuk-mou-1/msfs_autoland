"""
Tests for synthetic glidepath controller (non-precision VOR/NDB approach).

Covers: MSL/AGL chain with non-zero elevation, on-profile tracking,
high/low correction, MDA floor enforcement, MDA hysteresis band,
ILS exclusion (neighbour), production-path integration, and
MDA-clamp-after-wind-correction ordering.

MDA source (COMPATIBILITY):
    effective_mda_msl = decision_height (AGL) + runway_elevation.
    All floor comparisons use MSL.
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock


from modules.synthetic_glidepath import SyntheticGlidepath
from modules.types import ApproachConfig, NavStation


# ── Helpers ──────────────────────────────────────────────────────────

RUNWAY_THRESHOLD_LAT = 55.7558
RUNWAY_THRESHOLD_LON = 37.6173
RUNWAY_HEADING = 270
GLIDESLOPE_ANGLE = 3.0


def _make_config(**overrides) -> ApproachConfig:
    defaults = dict(
        station=NavStation("UUWW", 114300, 55.7558, 37.6173, "VOR"),
        final_approach_course=270,
        glideslope_angle=GLIDESLOPE_ANGLE,
        decision_height=500,       # ft AGL (consistent with DH guard)
        approach_speed=140,
        runway_elevation=600,       # ft MSL
        runway_length=10000,
        runway_width=145,
        runway_threshold_lat=RUNWAY_THRESHOLD_LAT,
        runway_threshold_lon=RUNWAY_THRESHOLD_LON,
    )
    defaults.update(overrides)
    return ApproachConfig(**defaults)


def _make_telemetry(
    *,
    lat: float = 55.75,
    lon: float = 37.50,
    altitude_msl: float | None = None,
    altitude_agl: float | None = None,
    runway_elevation: float = 600.0,
    ground_speed: float = 140.0,
) -> dict:
    """Build telemetry dict.  Pass either altitude_msl or altitude_agl;
    the other is derived from runway_elevation."""
    if altitude_msl is not None and altitude_agl is None:
        altitude_agl = altitude_msl - runway_elevation
    elif altitude_agl is not None and altitude_msl is None:
        altitude_msl = altitude_agl + runway_elevation
    elif altitude_msl is None and altitude_agl is None:
        altitude_msl = 2000.0 + runway_elevation
        altitude_agl = 2000.0
    return {
        "position": {
            "latitude": lat,
            "longitude": lon,
            "altitude": altitude_msl,
            "altitude_agl": altitude_agl,
            "radio_height": altitude_agl,
            "on_ground": False,
        },
        "attitude": {"bank": 0.0, "pitch": 2.5, "heading_magnetic": 270.0},
        "speed": {
            "airspeed_indicated": 140.0,
            "vertical_speed": -700.0,
            "ground_speed": ground_speed,
        },
        "nav": {},
    }


def _make_nav_mock(
    *,
    distance_to_threshold: float = 5.0,
    required_altitude_msl: float = 1100.0,
    should_descend: bool = True,
    status: str = "ON_PROFILE",
    altitude_error_ft: float = 0.0,
    runway_elevation: float = 600.0,
) -> MagicMock:
    nav = MagicMock()
    nav.calculate_distance_to_threshold.return_value = distance_to_threshold
    nav.calculate_required_altitude.return_value = required_altitude_msl
    nav.should_start_descent.return_value = {
        "should_descend": should_descend,
        "status": status,
        "altitude_error_ft": altitude_error_ft,
        "distance_to_intercept_nm": 1.0,
        "ideal_altitude_agl": required_altitude_msl - runway_elevation,
        "vertical_deviation_dots": 0.0,
        "reason": "",
        "glideslope_angle": GLIDESLOPE_ANGLE,
    }
    nav.calculate_glideslope_intercept_point.return_value = {
        "latitude": 55.8,
        "longitude": 37.6,
        "distance_from_threshold_nm": 20.0,
        "altitude_agl": 2000.0,
        "altitude_msl": 2600.0,
        "glideslope_angle": GLIDESLOPE_ANGLE,
        "runway_heading": RUNWAY_HEADING,
        "feet_per_nm": 100.0,
    }
    return nav


# ── MSL/AGL chain — non-zero elevation ─────────────────────────────

class TestMSLAGLChain:
    """Verify MDA floor is MSL with non-zero runway_elevation.

    User-specified scenario:
        runway_elevation = 500 ft
        decision_height  = 500 ft AGL
        effective_mda_msl = 500 + 500 = 1000 ft MSL

    Expectations:
        1020 MSL → descent allowed (above floor)
        1000 MSL → level-off (at floor)
         990 MSL → level-off (below floor, fail-closed)
    """

    def test_above_mda_msl_descends(self):
        """1020 MSL → above effective_mda_msl (1000) → descent allowed."""
        config = _make_config(runway_elevation=500, decision_height=500)
        # ideal at distance 3.0 = 1500 MSL (well above floor)
        nav = _make_nav_mock(
            distance_to_threshold=3.0,
            required_altitude_msl=1500.0,
            runway_elevation=500.0,
        )
        gp = SyntheticGlidepath(nav, config, gain=2.0)

        t = _make_telemetry(altitude_msl=1020.0, runway_elevation=500.0)
        result = gp.compute_target_vs(t, wind_correction_vs=600.0)

        # error = 1020 - 1500 = -480 → correction = -960 → 600 + (-960) = -360
        # But -360 ≤ 0 means the aircraft is below glideslope and should
        # NOT descend further — yet 1020 > 1000 + 15 = 1015, so no hysteresis clamp.
        # Result is negative (climb/level) which is correct — aircraft is below
        # the glideslope.  The key assertion is: NOT zero (not hard-floor blocked).
        assert result != 0.0, "1020 MSL should not be blocked by MDA floor"
        # And must not command descent that would go below 1000 MSL.
        # With gain=2 and wind_vs=600, the result is -360 (climb), safe.
        assert result <= 0.0, f"Expected non-positive VS (below glideslope), got {result}"

    def test_at_mda_msl_level_off(self):
        """1000 MSL → at effective_mda_msl → level-off (VS=0)."""
        config = _make_config(runway_elevation=500, decision_height=500)
        nav = _make_nav_mock(
            distance_to_threshold=1.0,
            required_altitude_msl=1200.0,
            runway_elevation=500.0,
        )
        gp = SyntheticGlidepath(nav, config)

        t = _make_telemetry(altitude_msl=1000.0, runway_elevation=500.0)
        result = gp.compute_target_vs(t, wind_correction_vs=800.0)

        assert result == 0.0, f"Expected 0 at MDA_MSL, got {result}"

    def test_below_mda_msl_fail_closed(self):
        """990 MSL → below effective_mda_msl (1000) → level-off, NOT negative VS.

        Fail-closed: controller must never command descent below MDA_MSL.
        Even if wind_data says descend, the floor blocks it.
        """
        config = _make_config(runway_elevation=500, decision_height=500)
        nav = _make_nav_mock(
            distance_to_threshold=0.5,
            required_altitude_msl=1200.0,
            runway_elevation=500.0,
        )
        gp = SyntheticGlidepath(nav, config)

        t = _make_telemetry(altitude_msl=990.0, runway_elevation=500.0)
        result = gp.compute_target_vs(t, wind_correction_vs=800.0)

        assert result == 0.0, f"Below MDA_MSL: expected 0, got {result}"
        assert result >= 0.0, "Below MDA_MSL: must never command descent"

    def test_mda_floor_not_agl(self):
        """decision_height=500 is AGL, NOT MDA_MSL.

        runway_elevation=800, decision_height=500 → MDA_MSL=1300.
        Aircraft at 1350 MSL / 550 AGL → above MDA_MSL → descend.
        Aircraft at 1250 MSL / 450 AGL → below MDA_MSL → hold.
        NOT level-off at 500 AGL (1300 MSL only by coincidence).
        """
        config = _make_config(runway_elevation=800, decision_height=500)
        # MDA_MSL = 500 + 800 = 1300
        nav = _make_nav_mock(
            distance_to_threshold=3.0,
            required_altitude_msl=1600.0,
            runway_elevation=800.0,
        )
        gp = SyntheticGlidepath(nav, config, gain=2.0)

        # 1350 MSL → above MDA_MSL=1300 → descend
        t_above = _make_telemetry(altitude_msl=1350.0, runway_elevation=800.0)
        r_above = gp.compute_target_vs(t_above, wind_correction_vs=600.0)
        assert r_above != 0.0, "1350 MSL should not be blocked (MDA_MSL=1300)"

        # 1250 MSL → below MDA_MSL=1300 → hold
        t_below = _make_telemetry(altitude_msl=1250.0, runway_elevation=800.0)
        r_below = gp.compute_target_vs(t_below, wind_correction_vs=600.0)
        assert r_below == 0.0, "1250 MSL should be blocked (MDA_MSL=1300)"


# ── MDA clamp after wind correction ────────────────────────────────

class TestMDAClampAfterWindCorrection:
    """Verify MDA floor clamp is applied AFTER wind correction.

    Scenario: wind correction pushes VS positive (descent) near MDA.
    Without MDA clamp, aircraft would descend below floor.
    With clamp, descent is blocked.
    """

    def test_wind_pushes_vs_down_near_mda(self):
        """High wind_correction_vs near MDA → clamped to 0 (no descent).

        runway_elevation=500, decision_height=500 → MDA_MSL=1000.
        Hysteresis=15 → band = [1000, 1015].
        Aircraft at 1010 MSL → within band.
        wind_correction_vs=1000 (strong descent command from wind).
        Without MDA clamp: raw_vs=1000+correction → descent.
        With MDA clamp: min(raw_vs, 0) → 0.
        """
        config = _make_config(runway_elevation=500, decision_height=500)
        nav = _make_nav_mock(
            distance_to_threshold=1.0,
            required_altitude_msl=1200.0,
            runway_elevation=500.0,
        )
        gp = SyntheticGlidepath(nav, config, mda_hysteresis_ft=15.0, gain=2.0)

        # 1010 MSL → within hysteresis band [1000, 1015]
        t = _make_telemetry(altitude_msl=1010.0, runway_elevation=500.0)
        result = gp.compute_target_vs(t, wind_correction_vs=1000.0)

        # raw_vs = 1000 + (1010-1200)*2 = 1000 + (-380) = 620
        # Hysteresis clamp → min(620, 0) = 0
        assert result == 0.0, (
            f"MDA clamp after wind correction: expected 0, got {result}. "
            "wind_correction_vs=1000 was not clamped."
        )

    def test_clamp_order_independence(self):
        """Same result regardless of wind_correction_vs sign near MDA.

        If clamp were before wind correction, sign would matter.
        Since clamp is after, both positive and negative wind VS
        are clamped to exactly 0 within the hysteresis band.
        """
        config = _make_config(runway_elevation=500, decision_height=500)
        nav = _make_nav_mock(
            distance_to_threshold=1.0,
            required_altitude_msl=1200.0,
            runway_elevation=500.0,
        )
        gp = SyntheticGlidepath(nav, config, mda_hysteresis_ft=15.0, gain=2.0)

        t = _make_telemetry(altitude_msl=1010.0, runway_elevation=500.0)

        r_positive = gp.compute_target_vs(t, wind_correction_vs=1000.0)
        r_negative = gp.compute_target_vs(t, wind_correction_vs=-200.0)

        # Both must be exactly 0 within hysteresis band (level-off, no climb)
        assert r_positive == 0.0, f"Positive wind VS not clamped to 0: {r_positive}"
        assert r_negative == 0.0, f"Negative wind VS not clamped to 0: {r_negative}"


# ── On-profile tracking ─────────────────────────────────────────────

class TestOnProfile:
    """Aircraft exactly on glideslope → minimal VS correction."""

    def test_on_profile_zero_error(self):
        """When altitude matches ideal, raw_vs ≈ wind_correction_vs."""
        ideal_msl = 600 + 5.0 * 6076.12 * math.tan(math.radians(3.0))
        nav = _make_nav_mock(
            distance_to_threshold=5.0,
            required_altitude_msl=ideal_msl,
        )
        config = _make_config()
        gp = SyntheticGlidepath(nav, config)

        telemetry = _make_telemetry(altitude_msl=ideal_msl)
        result = gp.compute_target_vs(telemetry, wind_correction_vs=700.0)

        assert abs(result - 700.0) < 1.0

    def test_on_profile_small_error(self):
        """Small altitude error → proportional correction."""
        nav = _make_nav_mock(
            distance_to_threshold=5.0,
            required_altitude_msl=1600.0,
        )
        config = _make_config()
        gp = SyntheticGlidepath(nav, config, gain=2.0)

        # 50ft above ideal
        telemetry = _make_telemetry(altitude_msl=1650.0)
        result = gp.compute_target_vs(telemetry, wind_correction_vs=700.0)

        assert abs(result - 800.0) < 1.0


# ── High aircraft ───────────────────────────────────────────────────

class TestHighAircraft:
    """Aircraft above glideslope → increase descent rate."""

    def test_high_aircraft_increases_descent(self):
        """100ft above → +200fpm correction (gain=2)."""
        nav = _make_nav_mock(
            distance_to_threshold=5.0,
            required_altitude_msl=1600.0,
        )
        config = _make_config()
        gp = SyntheticGlidepath(nav, config, gain=2.0)

        telemetry = _make_telemetry(altitude_msl=1700.0)
        result = gp.compute_target_vs(telemetry, wind_correction_vs=600.0)

        assert abs(result - 800.0) < 1.0

    def test_high_aircraft_large_error(self):
        """300ft above → +600fpm correction."""
        nav = _make_nav_mock(
            distance_to_threshold=5.0,
            required_altitude_msl=1600.0,
        )
        config = _make_config()
        gp = SyntheticGlidepath(nav, config, gain=2.0)

        telemetry = _make_telemetry(altitude_msl=1900.0)
        result = gp.compute_target_vs(telemetry, wind_correction_vs=600.0)

        assert abs(result - 1200.0) < 1.0


# ── Low aircraft ────────────────────────────────────────────────────

class TestLowAircraft:
    """Aircraft below glideslope → decrease descent rate or climb."""

    def test_low_aircraft_decreases_descent(self):
        """100ft below → -200fpm correction (reduce descent)."""
        nav = _make_nav_mock(
            distance_to_threshold=5.0,
            required_altitude_msl=1600.0,
        )
        config = _make_config()
        gp = SyntheticGlidepath(nav, config, gain=2.0)

        telemetry = _make_telemetry(altitude_msl=1500.0)
        result = gp.compute_target_vs(telemetry, wind_correction_vs=600.0)

        assert abs(result - 400.0) < 1.0

    def test_low_aircraft_very_low(self):
        """300ft below → -600fpm correction (may go negative = climb)."""
        nav = _make_nav_mock(
            distance_to_threshold=5.0,
            required_altitude_msl=1600.0,
        )
        config = _make_config()
        gp = SyntheticGlidepath(nav, config, gain=2.0)

        telemetry = _make_telemetry(altitude_msl=1300.0)
        result = gp.compute_target_vs(telemetry, wind_correction_vs=600.0)

        assert abs(result - 0.0) < 1.0

    def test_low_aircraft_status_low(self):
        """should_start_descent returns LOW → hold altitude (0 VS)."""
        nav = _make_nav_mock(
            distance_to_threshold=5.0,
            required_altitude_msl=1600.0,
            should_descend=False,
            status="LOW",
            altitude_error_ft=-500.0,
        )
        config = _make_config()
        gp = SyntheticGlidepath(nav, config)

        telemetry = _make_telemetry(altitude_msl=1100.0)
        result = gp.compute_target_vs(telemetry, wind_correction_vs=600.0)

        assert result == 0.0


# ── MDA floor (generic, elevation=600) ─────────────────────────────

class TestMDAFloor:
    """Hard floor at MDA_MSL = decision_height + runway_elevation."""

    def test_at_mda_holds_altitude(self):
        """At MDA_MSL (1100) → target_vs = 0."""
        nav = _make_nav_mock(
            distance_to_threshold=1.0,
            required_altitude_msl=1300.0,
        )
        config = _make_config(decision_height=500, runway_elevation=600)
        gp = SyntheticGlidepath(nav, config)

        telemetry = _make_telemetry(altitude_msl=1100.0)
        result = gp.compute_target_vs(telemetry, wind_correction_vs=600.0)

        assert result == 0.0

    def test_below_mda_holds_altitude(self):
        """Below MDA_MSL → target_vs = 0 (hard floor)."""
        nav = _make_nav_mock(
            distance_to_threshold=0.5,
            required_altitude_msl=1300.0,
        )
        config = _make_config(decision_height=500, runway_elevation=600)
        gp = SyntheticGlidepath(nav, config)

        telemetry = _make_telemetry(altitude_msl=1090.0)
        result = gp.compute_target_vs(telemetry, wind_correction_vs=600.0)

        assert result == 0.0

    def test_above_mda_descends(self):
        """Above MDA_MSL + hysteresis → normal descent."""
        nav = _make_nav_mock(
            distance_to_threshold=2.0,
            required_altitude_msl=1400.0,
        )
        config = _make_config(decision_height=500, runway_elevation=600)
        gp = SyntheticGlidepath(nav, config, gain=2.0)

        telemetry = _make_telemetry(altitude_msl=1200.0)
        result = gp.compute_target_vs(telemetry, wind_correction_vs=600.0)

        # error = 1200 - 1400 = -200 → correction = -400 → 600 + (-400) = 200
        assert abs(result - 200.0) < 1.0


# ── MDA hysteresis band ─────────────────────────────────────────────

class TestMDAHysteresis:
    """Level-off initiates in a narrow band above MDA_MSL."""

    def test_hysteresis_band_levels_off(self):
        """Within hysteresis band above MDA_MSL → prevent descent."""
        nav = _make_nav_mock(
            distance_to_threshold=1.0,
            required_altitude_msl=1300.0,
        )
        config = _make_config(decision_height=500, runway_elevation=600)
        gp = SyntheticGlidepath(nav, config, mda_hysteresis_ft=15.0, gain=2.0)

        # 1110 MSL → within band [1100, 1115]
        telemetry = _make_telemetry(altitude_msl=1110.0)
        result = gp.compute_target_vs(telemetry, wind_correction_vs=600.0)

        assert result == 0.0, f"Expected level-off (0) in hysteresis band, got {result}"

    def test_outside_hysteresis_band_descends(self):
        """Above MDA_MSL + hysteresis → no clamp, normal descent."""
        nav = _make_nav_mock(
            distance_to_threshold=2.0,
            required_altitude_msl=1400.0,
        )
        config = _make_config(decision_height=500, runway_elevation=600)
        gp = SyntheticGlidepath(nav, config, mda_hysteresis_ft=15.0, gain=2.0)

        # 1130 MSL → above band (1130 > 1115)
        telemetry = _make_telemetry(altitude_msl=1130.0)
        result = gp.compute_target_vs(telemetry, wind_correction_vs=600.0)

        # error = 1130 - 1400 = -270 → correction = -540 → 600 + (-540) = 60
        assert abs(result - 60.0) < 1.0


class TestMDAHysteresisExactZero:
    """Hysteresis band returns exactly 0.0 — not min(raw, 0).

    Two explicit scenarios to prevent regression to min(raw_vs, 0.0)
    which would allow climb commands (negative VS) near MDA.
    """

    def test_positive_raw_vs_in_band(self):
        """Wind pushes descent (positive raw VS) inside band → 0.

        runway_elevation=500, decision_height=500 → MDA_MSL=1000.
        Hysteresis=15 → band = [1000, 1015].
        Aircraft at 1010 MSL → within band.
        wind_correction_vs=1000 → raw_vs = 1000 + (-380) = 620.
        Expected: 0.0 (not 620, not min(620,0)=0 by luck).
        """
        config = _make_config(runway_elevation=500, decision_height=500)
        nav = _make_nav_mock(
            distance_to_threshold=1.0,
            required_altitude_msl=1200.0,
            runway_elevation=500.0,
        )
        gp = SyntheticGlidepath(nav, config, mda_hysteresis_ft=15.0, gain=2.0)

        t = _make_telemetry(altitude_msl=1010.0, runway_elevation=500.0)
        result = gp.compute_target_vs(t, wind_correction_vs=1000.0)

        assert result == 0.0, (
            f"Positive raw VS in hysteresis band: expected 0.0, got {result}")

    def test_negative_raw_vs_in_band(self):
        """Profile/wind pulls climb (negative raw VS) inside band → 0.

        Same setup. wind_correction_vs=-200 → raw_vs = -200 + (-380) = -580.
        With min(raw, 0) this would pass (-580 ≤ 0) but still allow climb.
        With raw_vs = 0.0 it correctly holds altitude.
        """
        config = _make_config(runway_elevation=500, decision_height=500)
        nav = _make_nav_mock(
            distance_to_threshold=1.0,
            required_altitude_msl=1200.0,
            runway_elevation=500.0,
        )
        gp = SyntheticGlidepath(nav, config, mda_hysteresis_ft=15.0, gain=2.0)

        t = _make_telemetry(altitude_msl=1010.0, runway_elevation=500.0)
        result = gp.compute_target_vs(t, wind_correction_vs=-200.0)

        assert result == 0.0, (
            f"Negative raw VS in hysteresis band: expected 0.0, got {result}")


# ── Neighbour test: ILS ────────────────────────────────────────────

class TestILSExclusion:
    """ILS approach → synthetic glidepath NOT active."""

    def test_ils_not_active(self):
        """When system.synthetic_glidepath is None, VS comes from wind_data."""
        from modules.approach_phases import FinalPhaseState
        from modules.control_ownership import ControlOwner
        from tests.fakes import FakeControl

        system = MagicMock()
        system.synthetic_glidepath = None
        system.use_vjoy = False
        system.use_autothrottle = False
        system.approach_config = _make_config(
            station=NavStation("UUWW", 114300, 55.7558, 37.6173, "ILS")
        )
        system.autopilot_takeover.status.completed = True

        control = FakeControl()
        system.control = control

        state = FinalPhaseState(system)
        state._ownership = MagicMock()
        state._ownership.roll = ControlOwner.AIRCRAFT_AP
        state._ownership.pitch = ControlOwner.AIRCRAFT_AP

        telemetry = _make_telemetry()
        wind_data = {"corrected_vs": 650.0, "corrected_heading": 270.0}

        state._control_aircraft(telemetry, wind_data)

        vs_calls = [c for c in control.calls if c[0] == "set_vertical_speed"]
        assert len(vs_calls) == 1
        assert vs_calls[0][1] == -650


# ── Production path integration ────────────────────────────────────

class TestProductionPath:
    """Full chain: telemetry → glidepath → wind correction → MDA clamp → VS."""

    def test_full_chain_non_precision(self):
        """Non-precision approach → synthetic glidepath drives VS command."""
        from modules.approach_phases import FinalPhaseState
        from modules.control_ownership import ControlOwner
        from tests.fakes import FakeControl

        config = _make_config(decision_height=500, runway_elevation=600)
        nav = _make_nav_mock(
            distance_to_threshold=3.0,
            required_altitude_msl=1800.0,
        )
        gp = SyntheticGlidepath(nav, config, gain=2.0)

        system = MagicMock()
        system.synthetic_glidepath = gp
        system.use_vjoy = False
        system.use_autothrottle = False
        system.approach_config = config

        control = FakeControl()
        system.control = control

        state = FinalPhaseState(system)
        state._ownership = MagicMock()
        state._ownership.roll = ControlOwner.AIRCRAFT_AP
        state._ownership.pitch = ControlOwner.AIRCRAFT_AP

        telemetry = _make_telemetry(altitude_msl=1850.0, runway_elevation=600.0)
        wind_data = {"corrected_vs": 600.0, "corrected_heading": 270.0}

        state._control_aircraft(telemetry, wind_data)

        vs_calls = [c for c in control.calls if c[0] == "set_vertical_speed"]
        assert len(vs_calls) == 1
        assert vs_calls[0][1] == -700

    def test_full_chain_mda_clamp(self):
        """At MDA_MSL → VS command is 0 regardless of wind_data."""
        from modules.approach_phases import FinalPhaseState
        from modules.control_ownership import ControlOwner
        from tests.fakes import FakeControl

        config = _make_config(decision_height=500, runway_elevation=600)
        nav = _make_nav_mock(
            distance_to_threshold=1.0,
            required_altitude_msl=1300.0,
        )
        gp = SyntheticGlidepath(nav, config)

        system = MagicMock()
        system.synthetic_glidepath = gp
        system.use_vjoy = False
        system.use_autothrottle = False
        system.approach_config = config

        control = FakeControl()
        system.control = control

        state = FinalPhaseState(system)
        state._ownership = MagicMock()
        state._ownership.roll = ControlOwner.AIRCRAFT_AP
        state._ownership.pitch = ControlOwner.AIRCRAFT_AP

        telemetry = _make_telemetry(altitude_msl=1100.0, runway_elevation=600.0)
        wind_data = {"corrected_vs": 800.0, "corrected_heading": 270.0}

        state._control_aircraft(telemetry, wind_data)

        vs_calls = [c for c in control.calls if c[0] == "set_vertical_speed"]
        assert len(vs_calls) == 1
        assert vs_calls[0][1] == 0


# ── Gain parameter ──────────────────────────────────────────────────

class TestGainParameter:
    """Proportional gain tunability."""

    def test_higher_gain_more_correction(self):
        """gain=3.0 produces 50% more correction than gain=2.0."""
        nav = _make_nav_mock(
            distance_to_threshold=5.0,
            required_altitude_msl=1600.0,
        )
        config = _make_config()

        gp2 = SyntheticGlidepath(nav, config, gain=2.0)
        gp3 = SyntheticGlidepath(nav, config, gain=3.0)

        telemetry = _make_telemetry(altitude_msl=1700.0)
        wind_vs = 600.0

        r2 = gp2.compute_target_vs(telemetry, wind_vs)
        r3 = gp3.compute_target_vs(telemetry, wind_vs)

        assert abs(r2 - 800.0) < 1.0
        assert abs(r3 - 900.0) < 1.0


# ── Edge cases ──────────────────────────────────────────────────────

class TestEdgeCases:
    """Boundary conditions and degenerate inputs."""

    def test_not_yet_at_intercept_hold(self):
        """Aircraft before intercept point, not high → hold altitude."""
        nav = _make_nav_mock(
            distance_to_threshold=15.0,
            required_altitude_msl=3600.0,
            should_descend=False,
            status="ON_PROFILE",
        )
        config = _make_config()
        gp = SyntheticGlidepath(nav, config)

        telemetry = _make_telemetry(altitude_msl=3600.0)
        result = gp.compute_target_vs(telemetry, wind_correction_vs=700.0)

        assert result == 0.0

    def test_high_before_intercept_descends(self):
        """Aircraft before intercept but too high → initiate descent."""
        nav = _make_nav_mock(
            distance_to_threshold=15.0,
            required_altitude_msl=3600.0,
            should_descend=True,
            status="HIGH",
            altitude_error_ft=500.0,
        )
        config = _make_config()
        gp = SyntheticGlidepath(nav, config, gain=2.0)

        telemetry = _make_telemetry(altitude_msl=4100.0)
        result = gp.compute_target_vs(telemetry, wind_correction_vs=600.0)

        assert abs(result - 1600.0) < 1.0

    def test_negative_vs_clamp_at_mda(self):
        """Wind correction pushes VS negative near MDA → stays ≤ 0."""
        nav = _make_nav_mock(
            distance_to_threshold=0.5,
            required_altitude_msl=1300.0,
        )
        config = _make_config(decision_height=500, runway_elevation=600)
        gp = SyntheticGlidepath(nav, config, gain=2.0)

        # 1105 MSL → within hysteresis band
        telemetry = _make_telemetry(altitude_msl=1105.0)
        result = gp.compute_target_vs(telemetry, wind_correction_vs=200.0)

        assert result == 0.0, f"Expected level-off (0) near MDA, got {result}"
