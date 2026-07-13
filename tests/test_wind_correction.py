"""
Tests for wind_correction module — regression and validation.

Covers fixes: F-W1 (crab sign), F-W2 (input validation),
F-W3 (no headwind double-counting), F-W4 (glideslope validation),
F-W5 (drift sign, dead code removal).
"""

import math
import logging

import pytest

from modules.wind_correction import WindCorrection


# ── helpers ──────────────────────────────────────────────────────────

def _ground_track(heading: float, wind_from: float, TAS: float, W: float) -> float:
    """Ground track from heading + wind vector (FROM convention)."""
    air_x = TAS * math.sin(math.radians(heading))
    air_y = TAS * math.cos(math.radians(heading))
    wind_x = -W * math.sin(math.radians(wind_from))
    wind_y = -W * math.cos(math.radians(wind_from))
    return math.degrees(math.atan2(air_x + wind_x, air_y + wind_y)) % 360


def _angle_error(a: float, b: float) -> float:
    """Smallest angle between two headings."""
    err = abs(a - b)
    return 360 - err if err > 180 else err


def _make_telemetry(wind_speed=0, wind_direction=0,
                    airspeed_true=120, ground_speed=110,
                    airspeed_indicated=115):
    return {
        'weather': {
            'ambient_wind_velocity': wind_speed,
            'ambient_wind_direction': wind_direction,
        },
        'speed': {
            'airspeed_true': airspeed_true,
            'ground_speed': ground_speed,
            'airspeed_indicated': airspeed_indicated,
        },
    }


class _Config:
    def __init__(self, course=270, glideslope=3.0):
        self.final_approach_course = course
        self.glideslope_angle = glideslope


# ── 1. Ground track regression ──────────────────────────────────────

class TestGroundTrackMaintained:
    """F-W1 regression: corrected heading must maintain desired track."""

    @pytest.mark.parametrize("track, wind_from", [
        (0, 90), (0, 270), (90, 0), (90, 180),
    ])
    def test_ground_track_within_1_degree(self, track, wind_from):
        wc = WindCorrection()
        TAS, W = 120, 20
        heading = wc.calculate_corrected_heading(track, W, wind_from, TAS)
        gt = _ground_track(heading, wind_from, TAS, W)
        assert _angle_error(gt, track) < 1.0, (
            f"track={track}, wind_from={wind_from}: "
            f"heading={heading:.2f}, GT={gt:.2f}, error={_angle_error(gt, track):.2f}"
        )


# ── 2. Corrected heading both signs ─────────────────────────────────

class TestCorrectedHeadingBothSigns:
    """F-W1: wind from right → nose right; wind from left → nose left."""

    def test_wind_from_right(self):
        wc = WindCorrection()
        heading = wc.calculate_corrected_heading(0, 20, 90, 120)
        assert abs(heading - 9.59) < 0.1, f"expected ~9.59, got {heading}"

    def test_wind_from_left(self):
        wc = WindCorrection()
        heading = wc.calculate_corrected_heading(0, 20, 270, 120)
        assert abs(heading - 350.41) < 0.1, f"expected ~350.41, got {heading}"


# ── 3. Invalid wind fail-closed ─────────────────────────────────────

class TestInvalidWindFailClosed:
    """F-W2: NaN/inf/negative wind → zero corrections, no exception."""

    @pytest.mark.parametrize("wind_speed, wind_direction", [
        (float('nan'), 90),
        (float('inf'), 90),
        (-20, 90),
        (20, float('nan')),
        (20, float('inf')),
    ])
    def test_fail_closed(self, wind_speed, wind_direction, caplog):
        wc = WindCorrection()
        telemetry = _make_telemetry(wind_speed=wind_speed,
                                    wind_direction=wind_direction)
        config = _Config()

        with caplog.at_level(logging.WARNING):
            result = wc.apply_wind_corrections(telemetry, {}, config)

        assert result['corrected_heading'] == config.final_approach_course
        assert result['headwind'] == 0.0
        assert result['crosswind'] == 0.0
        assert result['drift_angle'] == 0.0
        assert result['recommended_bank'] == 0.0
        # vs_correction and corrected_vs from fail-closed path
        assert result['vs_correction'] == 0.0
        assert math.isfinite(result['corrected_vs'])
        assert "Invalid wind inputs" in caplog.text

    def test_all_outputs_finite(self):
        wc = WindCorrection()
        raw_keys = {'wind_speed', 'wind_direction'}
        for ws, wd in [(float('nan'), 90), (20, float('inf')), (-5, 0)]:
            telemetry = _make_telemetry(wind_speed=ws, wind_direction=wd)
            result = wc.apply_wind_corrections(telemetry, {}, _Config())
            for k, v in result.items():
                if k in raw_keys:
                    continue  # raw inputs returned as-is for logging
                assert math.isfinite(v), f"{k}={v} not finite (ws={ws}, wd={wd})"


# ── 4. Descent rate validation ──────────────────────────────────────

class TestDescentRateValidation:
    """F-W4: glideslope angle outside (0, 10] → 0.0."""

    def test_normal_angle(self):
        wc = WindCorrection()
        assert abs(wc.calculate_descent_rate(100, 3.0) - 530.9) < 1.0

    def test_angle_90_returns_zero(self):
        wc = WindCorrection()
        assert wc.calculate_descent_rate(100, 90) == 0.0

    def test_angle_0_returns_zero(self):
        wc = WindCorrection()
        assert wc.calculate_descent_rate(100, 0) == 0.0

    def test_negative_angle_returns_zero(self):
        wc = WindCorrection()
        assert wc.calculate_descent_rate(100, -3) == 0.0

    def test_angle_11_returns_zero(self):
        wc = WindCorrection()
        assert wc.calculate_descent_rate(100, 11) == 0.0


# ── 5. No headwind double-counting ──────────────────────────────────

class TestNoHeadwindDoubleCounting:
    """F-W3: corrected_vs == base_vs regardless of headwind."""

    def test_same_vs_with_and_without_headwind(self):
        wc = WindCorrection()
        config = _Config()

        t0 = _make_telemetry(wind_speed=0, wind_direction=0)
        t20 = _make_telemetry(wind_speed=20, wind_direction=0)

        r0 = wc.apply_wind_corrections(t0, {}, config)
        r20 = wc.apply_wind_corrections(t20, {}, config)

        assert r0['corrected_vs'] == r20['corrected_vs'], (
            f"zero-wind VS={r0['corrected_vs']}, "
            f"20kt-headwind VS={r20['corrected_vs']}"
        )
        assert r0['vs_correction'] == 0.0
        assert r20['vs_correction'] == 0.0


# ── 6. Drift angle sign ─────────────────────────────────────────────

class TestDriftAngleSign:
    """F-W5: wind from right (CW>0) → drift < 0 (sideslip left)."""

    def test_positive_crosswind_negative_drift(self):
        wc = WindCorrection()
        drift = wc.calculate_drift_angle(20, 120)
        assert abs(drift - (-9.59)) < 0.1, f"expected ~-9.59, got {drift}"

    def test_negative_crosswind_positive_drift(self):
        wc = WindCorrection()
        drift = wc.calculate_drift_angle(-20, 120)
        assert abs(drift - 9.59) < 0.1, f"expected ~+9.59, got {drift}"


# ── 7. Saturated crosswind no exception ─────────────────────────────

class TestSaturatedCrosswind:
    """|crosswind| > TAS must not raise; |crab| = 90°."""

    def test_extreme_crosswind(self):
        wc = WindCorrection()
        # Wind speed 200, heading 0, wind from 90 → crosswind=200, TAS=120
        heading = wc.calculate_corrected_heading(0, 200, 90, 120)
        assert math.isfinite(heading)
        # Crab should be 90° (asin clamped to 1.0)
        expected = (0 + 90) % 360
        assert abs(heading - expected) < 0.1, f"expected ~{expected}, got {heading}"

    def test_extreme_negative_crosswind(self):
        wc = WindCorrection()
        heading = wc.calculate_corrected_heading(0, 200, 270, 120)
        assert math.isfinite(heading)
        expected = (0 - 90) % 360
        assert abs(heading - expected) < 0.1, f"expected ~{expected}, got {heading}"
