"""Tests for Navigation (FIX-04)."""

import math


def test_landing_distance_zero_gs():
    """FIX-04: calculate_landing_distance must not raise ZeroDivisionError at GS=0."""
    from modules.navigation import Navigation

    nav = Navigation.__new__(Navigation)
    # Must not raise ZeroDivisionError
    result = nav.calculate_landing_distance(ground_speed=0, headwind=10)
    assert isinstance(result, float)

    result2 = nav.calculate_landing_distance(ground_speed=0, headwind=0)
    assert isinstance(result2, float)

    # Normal case still works
    result3 = nav.calculate_landing_distance(ground_speed=60, headwind=10)
    assert isinstance(result3, float)
    assert result3 > 0


# --- Finding 3: cos(lat) at poles ---

def test_glideslope_intercept_near_pole():
    """Finding 3: calculate_glideslope_intercept_point must not ZeroDivisionError at lat=90."""
    import math
    from modules.navigation import Navigation

    nav = Navigation.__new__(Navigation)
    result = nav.calculate_glideslope_intercept_point(
        runway_threshold_lat=89.999,
        runway_threshold_lon=0.0,
        runway_heading=0,
        runway_elevation=0,
        glideslope_angle=3.0,
    )
    assert isinstance(result, dict)
    assert 'latitude' in result
    assert 'longitude' in result
    assert math.isfinite(result['longitude'])


def test_runway_beacons_near_pole():
    """Finding 3: calculate_runway_beacons must not ZeroDivisionError at lat=90."""
    from modules.navigation import Navigation

    nav = Navigation.__new__(Navigation)
    result = nav.calculate_runway_beacons(
        runway_threshold_lat=89.999,
        runway_threshold_lon=0.0,
        runway_heading=0,
        runway_elevation=0,
    )
    assert isinstance(result, dict)
    assert 'outer' in result
    assert 'inner' in result


# --- NAV-F2: inbound bearing vs outbound radial ---

def test_vor_approach_exact_inbound_match():
    """NAV-F2 red-without-fix: aircraft exactly on inbound final course must give ~0° error."""
    from modules.navigation import Navigation
    from modules.types import ApproachConfig, NavStation

    nav = Navigation.__new__(Navigation)
    # VOR station at origin, final approach course = 090 (eastbound inbound)
    station = NavStation(name="TEST", frequency=110.0,
                         latitude=0.0, longitude=1.0, type="VOR")
    config = ApproachConfig(
        station=station,
        final_approach_course=90,
        glideslope_angle=3.0,
        decision_height=200,
        approach_speed=90,
        runway_elevation=0,
        runway_length=3000,
        runway_width=45,
        runway_threshold_lat=0.0,
        runway_threshold_lon=2.0,
    )
    # Aircraft west of station, bearing to station = 090 (exactly inbound)
    result = nav.calculate_vor_approach(
        aircraft_pos={'latitude': 0.0, 'longitude': 0.0, 'heading_magnetic': 90},
        nav_data={},
        config=config,
    )
    # cross_track_error must be near 0° (on course)
    assert abs(result['cross_track_error']) < 5.0, (
        f"NAV-F2 defect: aircraft on exact inbound course (bearing=90°) "
        f"got cross_track_error={result['cross_track_error']:.1f}°"
    )
    assert result['on_course'] is True
    # current_radial should still have outbound semantics (180° from bearing)
    assert abs(result['current_radial'] - 270.0) < 1.0


def test_vor_approach_opposite_outbound_no_false_error():
    """NAV-F2: opposite outbound radial must not create 180° false error."""
    from modules.navigation import Navigation
    from modules.types import ApproachConfig, NavStation

    nav = Navigation.__new__(Navigation)
    station = NavStation(name="TEST", frequency=110.0,
                         latitude=0.0, longitude=1.0, type="VOR")
    config = ApproachConfig(
        station=station,
        final_approach_course=90,
        glideslope_angle=3.0,
        decision_height=200,
        approach_speed=90,
        runway_elevation=0,
        runway_length=3000,
        runway_width=45,
        runway_threshold_lat=0.0,
        runway_threshold_lon=2.0,
    )
    # Aircraft east of station, bearing to station = 270 (opposite of inbound 090)
    # Inbound bearing is 270, final course is 90 → error should be 180° (off course)
    result = nav.calculate_vor_approach(
        aircraft_pos={'latitude': 0.0, 'longitude': 2.0, 'heading_magnetic': 270},
        nav_data={},
        config=config,
    )
    # This is legitimately off-course (180° error) — but NOT a false positive
    assert abs(abs(result['cross_track_error']) - 180.0) < 5.0
    assert result['on_course'] is False


def test_vor_approach_wrap_359_0():
    """NAV-F2: wrap boundary 359°/0° via angle_difference helper."""
    from modules.navigation import Navigation

    nav = Navigation.__new__(Navigation)
    # Direct angle_difference tests for wrap boundary
    # 359° vs 0° → should be -1° (not +359°)
    diff1 = nav.angle_difference(0, 359)
    assert abs(diff1 - (-1.0)) < 0.01, f"Expected -1°, got {diff1}"
    # 0° vs 359° → should be +1°
    diff2 = nav.angle_difference(359, 0)
    assert abs(diff2 - 1.0) < 0.01, f"Expected +1°, got {diff2}"
    # 1° vs 0° → +1°
    diff3 = nav.angle_difference(0, 1)
    assert abs(diff3 - 1.0) < 0.01
    # 0° vs 1° → -1°
    diff4 = nav.angle_difference(1, 0)
    assert abs(diff4 - (-1.0)) < 0.01


def test_vor_approach_symmetric_left_right():
    """NAV-F2: symmetric deviations give opposite signs."""
    from modules.navigation import Navigation
    from modules.types import ApproachConfig, NavStation

    nav = Navigation.__new__(Navigation)
    station = NavStation(name="TEST", frequency=110.0,
                         latitude=0.0, longitude=1.0, type="VOR")
    config = ApproachConfig(
        station=station,
        final_approach_course=90,
        glideslope_angle=3.0,
        decision_height=200,
        approach_speed=90,
        runway_elevation=0,
        runway_length=3000,
        runway_width=45,
        runway_threshold_lat=0.0,
        runway_threshold_lon=2.0,
    )
    # Left of course (bearing slightly less than 90)
    result_left = nav.calculate_vor_approach(
        aircraft_pos={'latitude': 0.01, 'longitude': 0.0, 'heading_magnetic': 90},
        nav_data={},
        config=config,
    )
    # Right of course (bearing slightly more than 90)
    result_right = nav.calculate_vor_approach(
        aircraft_pos={'latitude': -0.01, 'longitude': 0.0, 'heading_magnetic': 90},
        nav_data={},
        config=config,
    )
    # Opposite signs
    assert result_left['cross_track_error'] * result_right['cross_track_error'] < 0
    # Both should be small (< 10°)
    assert abs(result_left['cross_track_error']) < 10.0
    assert abs(result_right['cross_track_error']) < 10.0


def test_ndb_approach_inherits_vor_fix():
    """NAV-F2: NDB approach delegates to VOR and inherits the fix."""
    from modules.navigation import Navigation
    from modules.types import ApproachConfig, NavStation

    nav = Navigation.__new__(Navigation)
    station = NavStation(name="NDB_TEST", frequency=350,
                         latitude=0.0, longitude=1.0, type="NDB")
    config = ApproachConfig(
        station=station,
        final_approach_course=90,
        glideslope_angle=3.0,
        decision_height=200,
        approach_speed=90,
        runway_elevation=0,
        runway_length=3000,
        runway_width=45,
        runway_threshold_lat=0.0,
        runway_threshold_lon=2.0,
    )
    result = nav.calculate_ndb_approach(
        aircraft_pos={'latitude': 0.0, 'longitude': 0.0, 'heading_magnetic': 90},
        nav_data={},
        config=config,
    )
    # Should also have ~0° error (same logic as VOR)
    assert abs(result['cross_track_error']) < 5.0
    assert result['on_course'] is True


# --- NAV-F3: validation in calculate_runway_beacons ---

def test_runway_beacons_standard_config():
    """NAV-F3: standard 3°/5NM/1NM gives finite altitudes."""
    import math
    from modules.navigation import Navigation

    nav = Navigation.__new__(Navigation)
    result = nav.calculate_runway_beacons(
        runway_threshold_lat=45.0,
        runway_threshold_lon=90.0,
        runway_heading=90,
        runway_elevation=100,
        glideslope_angle=3.0,
        outer_distance_nm=5.0,
        inner_distance_nm=1.0,
    )
    assert math.isfinite(result['outer'].expected_altitude_agl)
    assert math.isfinite(result['inner'].expected_altitude_agl)
    assert result['outer'].expected_altitude_agl > 0
    assert result['inner'].expected_altitude_agl > 0
    assert result['outer'].expected_altitude_agl > result['inner'].expected_altitude_agl


def test_runway_beacons_invalid_glideslope_angle():
    """NAV-F3: glideslope_angle=0 or negative raises ValueError."""
    from modules.navigation import Navigation

    nav = Navigation.__new__(Navigation)
    # Zero angle
    try:
        nav.calculate_runway_beacons(
            runway_threshold_lat=45.0, runway_threshold_lon=90.0,
            runway_heading=90, runway_elevation=100,
            glideslope_angle=0.0,
        )
        raise AssertionError("Should have raised ValueError for glideslope_angle=0")
    except ValueError:
        pass

    # Negative angle
    try:
        nav.calculate_runway_beacons(
            runway_threshold_lat=45.0, runway_threshold_lon=90.0,
            runway_heading=90, runway_elevation=100,
            glideslope_angle=-3.0,
        )
        raise AssertionError("Should have raised ValueError for negative glideslope_angle")
    except ValueError:
        pass

    # NaN
    try:
        nav.calculate_runway_beacons(
            runway_threshold_lat=45.0, runway_threshold_lon=90.0,
            runway_heading=90, runway_elevation=100,
            glideslope_angle=float('nan'),
        )
        raise AssertionError("Should have raised ValueError for NaN glideslope_angle")
    except ValueError:
        pass

    # +inf
    try:
        nav.calculate_runway_beacons(
            runway_threshold_lat=45.0, runway_threshold_lon=90.0,
            runway_heading=90, runway_elevation=100,
            glideslope_angle=float('inf'),
        )
        raise AssertionError("Should have raised ValueError for +inf glideslope_angle")
    except ValueError:
        pass


def test_runway_beacons_invalid_distances():
    """NAV-F3: negative/NaN/inf distances raise ValueError."""
    from modules.navigation import Navigation

    nav = Navigation.__new__(Navigation)
    # Negative outer
    try:
        nav.calculate_runway_beacons(
            runway_threshold_lat=45.0, runway_threshold_lon=90.0,
            runway_heading=90, runway_elevation=100,
            outer_distance_nm=-1.0,
        )
        raise AssertionError("Should have raised ValueError for negative outer_distance_nm")
    except ValueError:
        pass

    # NaN inner
    try:
        nav.calculate_runway_beacons(
            runway_threshold_lat=45.0, runway_threshold_lon=90.0,
            runway_heading=90, runway_elevation=100,
            inner_distance_nm=float('nan'),
        )
        raise AssertionError("Should have raised ValueError for NaN inner_distance_nm")
    except ValueError:
        pass

    # +inf outer
    try:
        nav.calculate_runway_beacons(
            runway_threshold_lat=45.0, runway_threshold_lon=90.0,
            runway_heading=90, runway_elevation=100,
            outer_distance_nm=float('inf'),
        )
        raise AssertionError("Should have raised ValueError for +inf outer_distance_nm")
    except ValueError:
        pass


def test_runway_beacons_outer_less_than_inner():
    """NAV-F3: outer_distance_nm < inner_distance_nm raises ValueError."""
    from modules.navigation import Navigation

    nav = Navigation.__new__(Navigation)
    try:
        nav.calculate_runway_beacons(
            runway_threshold_lat=45.0, runway_threshold_lon=90.0,
            runway_heading=90, runway_elevation=100,
            outer_distance_nm=1.0,
            inner_distance_nm=5.0,
        )
        raise AssertionError("Should have raised ValueError for outer < inner")
    except ValueError:
        pass


def test_runway_beacons_invalid_coordinates():
    """NAV-F3: NaN/inf in coordinates raises ValueError."""
    from modules.navigation import Navigation

    nav = Navigation.__new__(Navigation)
    # NaN latitude
    try:
        nav.calculate_runway_beacons(
            runway_threshold_lat=float('nan'), runway_threshold_lon=90.0,
            runway_heading=90, runway_elevation=100,
        )
        raise AssertionError("Should have raised ValueError for NaN lat")
    except ValueError:
        pass

    # inf longitude
    try:
        nav.calculate_runway_beacons(
            runway_threshold_lat=45.0, runway_threshold_lon=float('inf'),
            runway_heading=90, runway_elevation=100,
        )
        raise AssertionError("Should have raised ValueError for inf lon")
    except ValueError:
        pass

    # Latitude out of range
    try:
        nav.calculate_runway_beacons(
            runway_threshold_lat=91.0, runway_threshold_lon=90.0,
            runway_heading=90, runway_elevation=100,
        )
        raise AssertionError("Should have raised ValueError for lat > 90")
    except ValueError:
        pass

    try:
        nav.calculate_runway_beacons(
            runway_threshold_lat=-91.0, runway_threshold_lon=90.0,
            runway_heading=90, runway_elevation=100,
        )
        raise AssertionError("Should have raised ValueError for lat < -90")
    except ValueError:
        pass


def test_runway_beacons_invalid_heading_elevation():
    """NAV-F3: NaN/inf in heading or elevation raises ValueError."""
    from modules.navigation import Navigation

    nav = Navigation.__new__(Navigation)
    # NaN heading
    try:
        nav.calculate_runway_beacons(
            runway_threshold_lat=45.0, runway_threshold_lon=90.0,
            runway_heading=float('nan'), runway_elevation=100,
        )
        raise AssertionError("Should have raised ValueError for NaN heading")
    except ValueError:
        pass

    # inf elevation
    try:
        nav.calculate_runway_beacons(
            runway_threshold_lat=45.0, runway_threshold_lon=90.0,
            runway_heading=90, runway_elevation=float('inf'),
        )
        raise AssertionError("Should have raised ValueError for inf elevation")
    except ValueError:
        pass

    # -inf heading
    try:
        nav.calculate_runway_beacons(
            runway_threshold_lat=45.0, runway_threshold_lon=90.0,
            runway_heading=float('-inf'), runway_elevation=100,
        )
        raise AssertionError("Should have raised ValueError for -inf heading")
    except ValueError:
        pass


def test_runway_beacons_extreme_glideslope():
    """NAV-F3: glideslope > 15° raises ValueError."""
    from modules.navigation import Navigation

    nav = Navigation.__new__(Navigation)
    try:
        nav.calculate_runway_beacons(
            runway_threshold_lat=45.0, runway_threshold_lon=90.0,
            runway_heading=90, runway_elevation=100,
            glideslope_angle=20.0,
        )
        raise AssertionError("Should have raised ValueError for glideslope > 15°")
    except ValueError:
        pass


# --- NAV-F4: wrap bug in check_beacon_passage ---

def test_beacon_passage_wrap_359_0():
    """NAV-F4 red-without-fix: current=359°, expected=0° → error ≈ -1°, course_ok=True."""
    from modules.navigation import Navigation
    from modules.types import RunwayBeacon

    nav = Navigation.__new__(Navigation)
    beacon = RunwayBeacon(
        name="OUTER", beacon_type="OUTER",
        latitude=0.0, longitude=1.0, frequency=0,
        distance_from_threshold_nm=5.0,
        expected_altitude_agl=1000.0,
        tolerance_altitude_ft=300.0,
        tolerance_course_deg=5.0,
    )
    result = nav.check_beacon_passage(
        current_lat=0.0, current_lon=0.0,
        current_altitude_agl=1000.0,
        current_heading=359.0,
        current_speed=120.0,
        beacon=beacon,
        expected_course=0.0,
    )
    # NAV-F4: angle_difference(expected=0, current=359) = -1° (current is 1° less)
    assert abs(result.course_error_deg - (-1.0)) < 0.5, (
        f"NAV-F4 defect: 359° vs 0° gave course_error={result.course_error_deg:.1f}°"
    )
    assert result.course_ok is True


def test_beacon_passage_wrap_1_0():
    """NAV-F4: current=1°, expected=0° → error ≈ +1°."""
    from modules.navigation import Navigation
    from modules.types import RunwayBeacon

    nav = Navigation.__new__(Navigation)
    beacon = RunwayBeacon(
        name="OUTER", beacon_type="OUTER",
        latitude=0.0, longitude=1.0, frequency=0,
        distance_from_threshold_nm=5.0,
        expected_altitude_agl=1000.0,
        tolerance_altitude_ft=300.0,
        tolerance_course_deg=5.0,
    )
    result = nav.check_beacon_passage(
        current_lat=0.0, current_lon=0.0,
        current_altitude_agl=1000.0,
        current_heading=1.0,
        current_speed=120.0,
        beacon=beacon,
        expected_course=0.0,
    )
    # angle_difference(expected=0, current=1) = +1°
    assert abs(result.course_error_deg - 1.0) < 0.5
    assert result.course_ok is True


def test_beacon_passage_wrap_0_359():
    """NAV-F4: current=0°, expected=359° → error ≈ +1°."""
    from modules.navigation import Navigation
    from modules.types import RunwayBeacon

    nav = Navigation.__new__(Navigation)
    beacon = RunwayBeacon(
        name="OUTER", beacon_type="OUTER",
        latitude=0.0, longitude=1.0, frequency=0,
        distance_from_threshold_nm=5.0,
        expected_altitude_agl=1000.0,
        tolerance_altitude_ft=300.0,
        tolerance_course_deg=5.0,
    )
    result = nav.check_beacon_passage(
        current_lat=0.0, current_lon=0.0,
        current_altitude_agl=1000.0,
        current_heading=0.0,
        current_speed=120.0,
        beacon=beacon,
        expected_course=359.0,
    )
    # angle_difference(expected=359, current=0) = +1° (via wrap)
    assert abs(result.course_error_deg - 1.0) < 0.5
    assert result.course_ok is True


def test_beacon_passage_beyond_tolerance():
    """NAV-F4: deviation beyond tolerance remains a violation."""
    from modules.navigation import Navigation
    from modules.types import RunwayBeacon

    nav = Navigation.__new__(Navigation)
    beacon = RunwayBeacon(
        name="OUTER", beacon_type="OUTER",
        latitude=0.0, longitude=1.0, frequency=0,
        distance_from_threshold_nm=5.0,
        expected_altitude_agl=1000.0,
        tolerance_altitude_ft=300.0,
        tolerance_course_deg=5.0,
    )
    result = nav.check_beacon_passage(
        current_lat=0.0, current_lon=0.0,
        current_altitude_agl=1000.0,
        current_heading=20.0,  # 20° off from expected 0°
        current_speed=120.0,
        beacon=beacon,
        expected_course=0.0,
    )
    assert result.course_ok is False
    # angle_difference(expected=0, current=20) = +20°
    assert abs(result.course_error_deg - 20.0) < 0.5


def test_beacon_passage_altitude_speed_violations_unchanged():
    """NAV-F4: altitude and speed violations still work correctly."""
    from modules.navigation import Navigation
    from modules.types import RunwayBeacon

    nav = Navigation.__new__(Navigation)
    beacon = RunwayBeacon(
        name="INNER", beacon_type="INNER",
        latitude=0.0, longitude=1.0, frequency=0,
        distance_from_threshold_nm=1.0,
        expected_altitude_agl=300.0,
        tolerance_altitude_ft=200.0,
        tolerance_course_deg=3.0,
    )
    # Too high, too slow, off course
    result = nav.check_beacon_passage(
        current_lat=0.0, current_lon=0.0,
        current_altitude_agl=600.0,
        current_heading=15.0,
        current_speed=70.0,
        beacon=beacon,
        expected_course=0.0,
    )
    assert result.altitude_ok is False
    assert result.speed_ok is False
    assert result.course_ok is False
    assert result.status == "CRITICAL"


# --- NAV-F1: glidepath geometry in should_start_descent ---

def _make_nav_and_intercept():
    """Helper: create Navigation and intercept_point for standard 3° glideslope."""
    from modules.navigation import Navigation

    nav = Navigation.__new__(Navigation)
    # Runway threshold at (45N, 90E), heading 090, elevation 100ft
    # Intercept at ~2000ft AGL → ~3.94 NM from threshold
    intercept_point = nav.calculate_glideslope_intercept_point(
        runway_threshold_lat=45.0,
        runway_threshold_lon=90.0,
        runway_heading=90.0,
        runway_elevation=100.0,
        glideslope_angle=3.0,
        intercept_altitude_agl=2000.0,
    )
    return nav, intercept_point


def test_navf1_before_intercept_holds_altitude():
    """NAV-F1: before intercept, ideal_altitude == intercept_altitude_agl."""
    nav, ip = _make_nav_and_intercept()
    # Position far before intercept (2x distance from threshold)
    far_lat = ip['latitude'] + (ip['latitude'] - 45.0)  # Mirror: further out
    far_lon = ip['longitude'] + (ip['longitude'] - 90.0)
    result = nav.should_start_descent(
        current_lat=far_lat,
        current_lon=far_lon,
        current_altitude_agl=2000.0,
        intercept_point=ip,
    )
    # Before intercept: ideal should be intercept_altitude_agl (2000 ft)
    assert math.isfinite(result['ideal_altitude_agl'])
    assert result['ideal_altitude_agl'] == ip['altitude_agl']


def test_navf1_at_intercept_holds_altitude():
    """NAV-F1: exactly at intercept, ideal_altitude == intercept_altitude_agl."""
    nav, ip = _make_nav_and_intercept()
    result = nav.should_start_descent(
        current_lat=ip['latitude'],
        current_lon=ip['longitude'],
        current_altitude_agl=2000.0,
        intercept_point=ip,
    )
    assert math.isfinite(result['ideal_altitude_agl'])
    assert abs(result['ideal_altitude_agl'] - ip['altitude_agl']) < 1.0


def test_navf1_monotonic_decrease_after_intercept():
    """NAV-F1: between intercept and threshold, ideal_altitude decreases monotonically."""
    nav, ip = _make_nav_and_intercept()
    threshold_lat = 45.0
    threshold_lon = 90.0

    # Sample points: 75%, 50%, 25% of intercept→threshold path
    alts = []
    for frac in [0.75, 0.50, 0.25]:
        lat = ip['latitude'] * frac + threshold_lat * (1 - frac)
        lon = ip['longitude'] * frac + threshold_lon * (1 - frac)
        result = nav.should_start_descent(
            current_lat=lat, current_lon=lon,
            current_altitude_agl=500.0,
            intercept_point=ip,
        )
        alts.append(result['ideal_altitude_agl'])

    # Monotonic decrease
    assert alts[0] > alts[1] > alts[2], f"Not monotonic: {alts}"
    # All finite
    for a in alts:
        assert math.isfinite(a)


def test_navf1_near_threshold_approaches_zero():
    """NAV-F1: near threshold, ideal_altitude ≈ 0 (not intercept altitude)."""
    nav, ip = _make_nav_and_intercept()
    threshold_lat = 45.0
    threshold_lon = 90.0
    # Very close to threshold (0.1 NM away)
    close_lat = threshold_lat + 0.001
    close_lon = threshold_lon + 0.001
    result = nav.should_start_descent(
        current_lat=close_lat,
        current_lon=close_lon,
        current_altitude_agl=50.0,
        intercept_point=ip,
    )
    assert math.isfinite(result['ideal_altitude_agl'])
    assert result['ideal_altitude_agl'] < 200.0  # Should be near 0, not 2000


def test_navf1_after_threshold_clamped_non_negative():
    """NAV-F1: after threshold, ideal_altitude ≥ 0, no NaN/inf."""
    nav, ip = _make_nav_and_intercept()
    # Position beyond threshold (past the runway)
    past_lat = 45.0 - 0.01  # Past threshold
    past_lon = 90.0 + 0.5
    result = nav.should_start_descent(
        current_lat=past_lat,
        current_lon=past_lon,
        current_altitude_agl=0.0,
        intercept_point=ip,
    )
    assert math.isfinite(result['ideal_altitude_agl'])
    assert result['ideal_altitude_agl'] >= 0.0


def test_navf1_cross_track_does_not_affect_profile():
    """NAV-F1: same along-track progress with cross-track offset → similar altitude."""
    nav, ip = _make_nav_and_intercept()
    threshold_lat = 45.0
    threshold_lon = 90.0

    # 50% point on centerline
    lat_center = ip['latitude'] * 0.5 + threshold_lat * 0.5
    lon_center = ip['longitude'] * 0.5 + threshold_lon * 0.5
    result_center = nav.should_start_descent(
        current_lat=lat_center, current_lon=lon_center,
        current_altitude_agl=500.0, intercept_point=ip,
    )

    # 50% point with 0.5 NM cross-track offset (perpendicular)
    # Offset in latitude (perpendicular to heading 090)
    result_offset = nav.should_start_descent(
        current_lat=lat_center + 0.01,  # ~0.6 NM offset
        current_lon=lon_center,
        current_altitude_agl=500.0, intercept_point=ip,
    )

    # Altitudes should be similar (cross-track shouldn't change profile much)
    assert math.isfinite(result_center['ideal_altitude_agl'])
    assert math.isfinite(result_offset['ideal_altitude_agl'])
    ratio = result_offset['ideal_altitude_agl'] / max(result_center['ideal_altitude_agl'], 1.0)
    assert 0.5 < ratio < 2.0, f"Cross-track changed profile too much: {ratio}"


def test_navf1_regression_after_intercept_not_low():
    """NAV-F1 regression: after intercept, status is not LOW due to distance growth."""
    nav, ip = _make_nav_and_intercept()
    # Position 50% between intercept and threshold
    lat = ip['latitude'] * 0.5 + 45.0 * 0.5
    lon = ip['longitude'] * 0.5 + 90.0 * 0.5
    # At 50% path, ideal altitude ≈ 1000 ft. Use 900 ft (within tolerance).
    result = nav.should_start_descent(
        current_lat=lat, current_lon=lon,
        current_altitude_agl=900.0,
        intercept_point=ip,
    )
    # The old defect: status becomes LOW because distance_to_intercept grows
    # After fix: status should NOT be LOW for a well-positioned aircraft
    assert result['status'] != 'LOW', (
        f"NAV-F1 regression: status=LOW at 50% path with correct altitude. "
        f"distance_to_intercept={result['distance_to_intercept_nm']:.2f} NM, "
        f"ideal_altitude={result['ideal_altitude_agl']:.0f} ft"
    )
    assert math.isfinite(result['ideal_altitude_agl'])


def test_navf1_all_values_finite():
    """NAV-F1: all computed numeric values must be finite."""
    nav, ip = _make_nav_and_intercept()
    result = nav.should_start_descent(
        current_lat=45.01, current_lon=90.1,
        current_altitude_agl=800.0,
        intercept_point=ip,
    )
    assert math.isfinite(result['ideal_altitude_agl'])
    assert math.isfinite(result['altitude_error_ft'])
    assert math.isfinite(result['vertical_deviation_dots'])
    assert math.isfinite(result['distance_to_intercept_nm'])


def test_navf1_downstream_synthetic_glidepath():
    """NAV-F1 downstream: SyntheticGlidepath.compute_target_vs() returns non-zero after intercept."""
    from modules.navigation import Navigation
    from modules.types import ApproachConfig, NavStation
    from modules.synthetic_glidepath import SyntheticGlidepath

    nav = Navigation.__new__(Navigation)
    station = NavStation(name="TEST", frequency=110.0,
                         latitude=45.0, longitude=90.0, type="VOR")
    config = ApproachConfig(
        station=station,
        final_approach_course=90,
        glideslope_angle=3.0,
        decision_height=200,
        approach_speed=90,
        runway_elevation=100,
        runway_length=3000,
        runway_width=45,
        runway_threshold_lat=45.0,
        runway_threshold_lon=90.0,
    )
    glidepath = SyntheticGlidepath(nav, config)

    # Position between intercept and threshold, above glideslope
    # Should command descent (positive VS)
    telemetry = {
        'position': {
            'latitude': 45.005,
            'longitude': 89.95,
            'altitude': 1500,  # MSL
            'altitude_agl': 1400,  # AGL
        }
    }
    vs = glidepath.compute_target_vs(telemetry, wind_correction_vs=0.0)
    # Should be positive (descent) since aircraft is above glideslope
    # and past intercept point
    assert vs > 0, f"NAV-F1 downstream: compute_target_vs returned {vs} (expected positive descent)"
    assert math.isfinite(vs)


# --- NAV-F1 strengthened tests (addendum requirements) ---

def test_navf1_after_threshold_strict_zero():
    """NAV-F1 addendum: after threshold on 0.1, 1, and 5 NM, ideal_altitude == 0."""
    nav, ip = _make_nav_and_intercept()
    threshold_lat = 45.0
    threshold_lon = 90.0
    cos_lat = math.cos(math.radians(threshold_lat))

    # Points past threshold along extended centerline (negative along-track)
    for past_nm in [0.1, 1.0, 5.0]:
        # Move past threshold in the direction away from approach (eastward for heading 090)
        past_lon = threshold_lon + past_nm / (60.0 * cos_lat)
        result = nav.should_start_descent(
            current_lat=threshold_lat,
            current_lon=past_lon,
            current_altitude_agl=0.0,
            intercept_point=ip,
        )
        assert math.isfinite(result['ideal_altitude_agl'])
        assert result['ideal_altitude_agl'] == 0.0, (
            f"After threshold at {past_nm} NM: expected 0 ft, got {result['ideal_altitude_agl']}"
        )


def test_navf1_before_intercept_strict_hold():
    """NAV-F1 addendum: before intercept on 0.1, 1, and 5 NM, altitude held at intercept."""
    nav, ip = _make_nav_and_intercept()
    threshold_lat = 45.0
    threshold_lon = 90.0

    intercept_alt = ip['altitude_agl']
    intercept_to_thresh = ip['intercept_to_threshold_nm']
    cos_lat = math.cos(math.radians(threshold_lat))

    # Points before intercept along extended centerline (beyond intercept)
    for extra_nm in [0.1, 1.0, 5.0]:
        total_nm = intercept_to_thresh + extra_nm
        # Move further from threshold than intercept (westward for heading 090)
        # 1 NM longitude = 1/(60*cos(lat)) degrees
        before_lon = threshold_lon - total_nm / (60.0 * cos_lat)
        result = nav.should_start_descent(
            current_lat=threshold_lat,
            current_lon=before_lon,
            current_altitude_agl=intercept_alt,
            intercept_point=ip,
        )
        assert math.isfinite(result['ideal_altitude_agl'])
        assert abs(result['ideal_altitude_agl'] - intercept_alt) < 1.0, (
            f"Before intercept at {extra_nm} NM extra: expected {intercept_alt}, "
            f"got {result['ideal_altitude_agl']}"
        )


def test_navf1_cross_track_strict_tolerance():
    """NAV-F1 addendum: same along-track with cross-track 0, 0.5, 2 NM → profile matches tightly."""
    import pytest
    nav, ip = _make_nav_and_intercept()
    threshold_lat = 45.0
    threshold_lon = 90.0

    # 50% point on centerline
    lat_center = ip['latitude'] * 0.5 + threshold_lat * 0.5
    lon_center = ip['longitude'] * 0.5 + threshold_lon * 0.5
    result_center = nav.should_start_descent(
        current_lat=lat_center, current_lon=lon_center,
        current_altitude_agl=500.0, intercept_point=ip,
    )
    center_alt = result_center['ideal_altitude_agl']

    # Cross-track offsets: 0.5 NM and 2 NM (perpendicular = latitude offset for heading 090)
    for ct_nm in [0.5, 2.0]:
        ct_deg = ct_nm / 60.0  # ~NM to degrees lat
        result_offset = nav.should_start_descent(
            current_lat=lat_center + ct_deg,
            current_lon=lon_center,
            current_altitude_agl=500.0, intercept_point=ip,
        )
        assert math.isfinite(result_offset['ideal_altitude_agl'])
        assert result_offset['ideal_altitude_agl'] == pytest.approx(
            center_alt, rel=1e-3, abs=1.0
        ), (
            f"Cross-track {ct_nm} NM changed profile: {center_alt} vs {result_offset['ideal_altitude_agl']}"
        )


def test_navf1_past_threshold_not_before_intercept():
    """NAV-F1 addendum: points past threshold never classified as before-intercept."""
    nav, ip = _make_nav_and_intercept()
    threshold_lat = 45.0
    threshold_lon = 90.0
    cos_lat = math.cos(math.radians(threshold_lat))

    for past_nm in [0.1, 1.0, 5.0, 50.0]:
        past_lon = threshold_lon + past_nm / (60.0 * cos_lat)
        result = nav.should_start_descent(
            current_lat=threshold_lat,
            current_lon=past_lon,
            current_altitude_agl=0.0,
            intercept_point=ip,
        )
        # ideal_altitude should be 0, not intercept altitude (2000)
        assert result['ideal_altitude_agl'] == 0.0, (
            f"Past threshold at {past_nm} NM got ideal={result['ideal_altitude_agl']} "
            f"(should be 0, not intercept altitude)"
        )


def test_navf1_near_threshold_vertical_deviation_finite():
    """NAV-F1 addendum: near-threshold vertical deviation uses along-track and stays finite."""
    nav, ip = _make_nav_and_intercept()
    threshold_lat = 45.0
    threshold_lon = 90.0
    cos_lat = math.cos(math.radians(threshold_lat))

    # Very close to threshold (0.05 NM)
    close_lon = threshold_lon + 0.05 / (60.0 * cos_lat)
    result = nav.should_start_descent(
        current_lat=threshold_lat,
        current_lon=close_lon,
        current_altitude_agl=10.0,
        intercept_point=ip,
    )
    assert math.isfinite(result['vertical_deviation_dots'])
    assert math.isfinite(result['ideal_altitude_agl'])


def test_navf1_downstream_no_false_profile_after_threshold():
    """NAV-F1 addendum: SyntheticGlidepath doesn't get false profile after threshold."""
    from modules.navigation import Navigation
    from modules.types import ApproachConfig, NavStation
    from modules.synthetic_glidepath import SyntheticGlidepath

    nav = Navigation.__new__(Navigation)
    station = NavStation(name="TEST", frequency=110.0,
                         latitude=45.0, longitude=90.0, type="VOR")
    config = ApproachConfig(
        station=station,
        final_approach_course=90,
        glideslope_angle=3.0,
        decision_height=200,
        approach_speed=90,
        runway_elevation=100,
        runway_length=3000,
        runway_width=45,
        runway_threshold_lat=45.0,
        runway_threshold_lon=90.0,
    )
    glidepath = SyntheticGlidepath(nav, config)

    # Position past threshold (east of threshold for heading 090)
    telemetry_past = {
        'position': {
            'latitude': 45.0,
            'longitude': 90.5,  # ~30 NM past threshold
            'altitude': 100,  # MSL (at runway elevation)
            'altitude_agl': 0,
        }
    }
    vs_past = glidepath.compute_target_vs(telemetry_past, wind_correction_vs=0.0)
    # After threshold: should not command descent (VS <= 0)
    assert vs_past <= 0, (
        f"NAV-F1 downstream: past threshold got VS={vs_past} (should be <= 0)"
    )


# --- NAV-F1 addendum-2: on-profile decision logic tests ---

def test_navf1_on_profile_75_50_25_should_descend():
    """NAV-F1 addendum-2: on-profile at 75/50/25% → ON_PROFILE, should_descend=True."""
    nav, ip = _make_nav_and_intercept()
    threshold_lat = 45.0
    threshold_lon = 90.0
    cos_lat = math.cos(math.radians(threshold_lat))
    intercept_to_thresh = ip['intercept_to_threshold_nm']

    for pct in [0.75, 0.50, 0.25]:
        along_nm = intercept_to_thresh * pct
        lon_offset = along_nm / (60.0 * cos_lat)
        lat = threshold_lat
        lon = threshold_lon - lon_offset

        # Get ideal altitude
        result = nav.should_start_descent(
            current_lat=lat, current_lon=lon,
            current_altitude_agl=ip['altitude_agl'],
            intercept_point=ip,
        )
        ideal = result['ideal_altitude_agl']

        # Test with aircraft exactly on profile
        result_on = nav.should_start_descent(
            current_lat=lat, current_lon=lon,
            current_altitude_agl=ideal,
            intercept_point=ip,
        )
        assert result_on['status'] == 'ON_PROFILE', (
            f"At {pct*100:.0f}% path: expected ON_PROFILE, got {result_on['status']}"
        )
        assert result_on['should_descend'] is True, (
            f"At {pct*100:.0f}% path: expected should_descend=True, got False"
        )


def test_navf1_on_profile_downstream_positive_vs():
    """NAV-F1 addendum-2: on-profile at 50% via SyntheticGlidepath → non-negative VS."""
    from modules.navigation import Navigation
    from modules.types import ApproachConfig, NavStation
    from modules.synthetic_glidepath import SyntheticGlidepath

    nav = Navigation.__new__(Navigation)
    station = NavStation(name="TEST", frequency=110.0,
                         latitude=45.0, longitude=90.0, type="VOR")
    config = ApproachConfig(
        station=station,
        final_approach_course=90,
        glideslope_angle=3.0,
        decision_height=200,
        approach_speed=90,
        runway_elevation=100,
        runway_length=3000,
        runway_width=45,
        runway_threshold_lat=45.0,
        runway_threshold_lon=90.0,
    )
    glidepath = SyntheticGlidepath(nav, config)

    ip = nav.calculate_glideslope_intercept_point(
        45.0, 90.0, 90.0, 100.0, 3.0,
    )
    intercept_to_thresh = ip['intercept_to_threshold_nm']
    cos_lat = math.cos(math.radians(45.0))

    along_nm = intercept_to_thresh * 0.5
    lon_offset = along_nm / (60.0 * cos_lat)
    ideal_agl = along_nm * ip['feet_per_nm']

    telemetry = {
        'position': {
            'latitude': 45.0,
            'longitude': 90.0 - lon_offset,
            'altitude': 100 + ideal_agl,
            'altitude_agl': ideal_agl,
        }
    }
    vs = glidepath.compute_target_vs(telemetry, wind_correction_vs=0.0)
    descent_info = nav.should_start_descent(
        current_lat=45.0, current_lon=90.0 - lon_offset,
        current_altitude_agl=ideal_agl, intercept_point=ip,
    )
    assert descent_info['should_descend'] is True, (
        "NAV-F1 addendum-2: on-profile should_descend should be True"
    )
    assert descent_info['status'] == 'ON_PROFILE'
    # VS is 0 (proportional controller has no error) — accept tiny floating point noise
    assert abs(vs) < 1e-6, f"On-profile VS should be ~0, got {vs}"


def test_navf1_before_intercept_no_descend():
    """NAV-F1 addendum-2: before intercept → should_descend=False."""
    nav, ip = _make_nav_and_intercept()
    threshold_lat = 45.0
    threshold_lon = 90.0
    cos_lat = math.cos(math.radians(threshold_lat))
    intercept_to_thresh = ip['intercept_to_threshold_nm']

    before_nm = intercept_to_thresh + 1.0
    lon_offset = before_nm / (60.0 * cos_lat)
    result = nav.should_start_descent(
        current_lat=threshold_lat,
        current_lon=threshold_lon - lon_offset,
        current_altitude_agl=ip['altitude_agl'],
        intercept_point=ip,
    )
    assert result['should_descend'] is False
    assert result['status'] == 'OK'


def test_navf1_after_threshold_no_descend():
    """NAV-F1 addendum-2: after threshold → should_descend=False."""
    nav, ip = _make_nav_and_intercept()
    threshold_lat = 45.0
    threshold_lon = 90.0
    cos_lat = math.cos(math.radians(threshold_lat))

    past_nm = 1.0
    lon_offset = past_nm / (60.0 * cos_lat)
    result = nav.should_start_descent(
        current_lat=threshold_lat,
        current_lon=threshold_lon + lon_offset,
        current_altitude_agl=0.0,
        intercept_point=ip,
    )
    assert result['should_descend'] is False
    assert result['status'] == 'PAST_THRESHOLD'


# --- NAV-F1 addendum-3: HIGH before intercept ---

def test_navf1_before_intercept_at_altitude_no_descend():
    """NAV-F1 addendum-3: before intercept at intercept altitude → should_descend=False."""
    nav, ip = _make_nav_and_intercept()
    threshold_lat = 45.0
    threshold_lon = 90.0
    cos_lat = math.cos(math.radians(threshold_lat))
    intercept_to_thresh = ip['intercept_to_threshold_nm']

    before_nm = intercept_to_thresh + 1.0
    lon_offset = before_nm / (60.0 * cos_lat)
    result = nav.should_start_descent(
        current_lat=threshold_lat,
        current_lon=threshold_lon - lon_offset,
        current_altitude_agl=ip['altitude_agl'],  # At intercept altitude
        intercept_point=ip,
    )
    assert result['should_descend'] is False
    assert result['status'] == 'OK'


def test_navf1_before_intercept_high_should_descend():
    """NAV-F1 addendum-3: before intercept 301ft above → HIGH, should_descend=True."""
    nav, ip = _make_nav_and_intercept()
    threshold_lat = 45.0
    threshold_lon = 90.0
    cos_lat = math.cos(math.radians(threshold_lat))
    intercept_to_thresh = ip['intercept_to_threshold_nm']

    before_nm = intercept_to_thresh + 1.0
    lon_offset = before_nm / (60.0 * cos_lat)
    result = nav.should_start_descent(
        current_lat=threshold_lat,
        current_lon=threshold_lon - lon_offset,
        current_altitude_agl=ip['altitude_agl'] + 301,  # 301ft above intercept
        intercept_point=ip,
    )
    assert result['should_descend'] is True
    assert result['status'] == 'HIGH'


def test_navf1_before_intercept_low_no_descend():
    """NAV-F1 addendum-3: before intercept below profile → no false descent."""
    nav, ip = _make_nav_and_intercept()
    threshold_lat = 45.0
    threshold_lon = 90.0
    cos_lat = math.cos(math.radians(threshold_lat))
    intercept_to_thresh = ip['intercept_to_threshold_nm']

    before_nm = intercept_to_thresh + 1.0
    lon_offset = before_nm / (60.0 * cos_lat)
    result = nav.should_start_descent(
        current_lat=threshold_lat,
        current_lon=threshold_lon - lon_offset,
        current_altitude_agl=ip['altitude_agl'] - 100,  # 100ft below intercept
        intercept_point=ip,
    )
    assert result['should_descend'] is False


# --- NAV-F3 addendum-2: boundary tests ---

def test_runway_beacons_longitude_boundary():
    """NAV-F3: longitude boundary — -180, 180 ok; out of range raises ValueError."""
    from modules.navigation import Navigation

    nav = Navigation.__new__(Navigation)
    nav.calculate_runway_beacons(
        runway_threshold_lat=45.0, runway_threshold_lon=-180.0,
        runway_heading=90, runway_elevation=100,
    )
    nav.calculate_runway_beacons(
        runway_threshold_lat=45.0, runway_threshold_lon=180.0,
        runway_heading=90, runway_elevation=100,
    )
    try:
        nav.calculate_runway_beacons(
            runway_threshold_lat=45.0, runway_threshold_lon=181.0,
            runway_heading=90, runway_elevation=100,
        )
        raise AssertionError("Should have raised ValueError for lon > 180")
    except ValueError:
        pass
    try:
        nav.calculate_runway_beacons(
            runway_threshold_lat=45.0, runway_threshold_lon=-181.0,
            runway_heading=90, runway_elevation=100,
        )
        raise AssertionError("Should have raised ValueError for lon < -180")
    except ValueError:
        pass
    try:
        nav.calculate_runway_beacons(
            runway_threshold_lat=45.0, runway_threshold_lon=1000.0,
            runway_heading=90, runway_elevation=100,
        )
        raise AssertionError("Should have raised ValueError for lon=1000")
    except ValueError:
        pass


def test_runway_beacons_heading_normalization():
    """NAV-F3: heading is normalized to [0, 360) via % 360."""
    from modules.navigation import Navigation

    nav = Navigation.__new__(Navigation)
    result = nav.calculate_runway_beacons(
        runway_threshold_lat=45.0, runway_threshold_lon=90.0,
        runway_heading=360.0, runway_elevation=100,
    )
    assert result['outer'] is not None

    result = nav.calculate_runway_beacons(
        runway_threshold_lat=45.0, runway_threshold_lon=90.0,
        runway_heading=450.0, runway_elevation=100,
    )
    assert result['outer'] is not None

    result = nav.calculate_runway_beacons(
        runway_threshold_lat=45.0, runway_threshold_lon=90.0,
        runway_heading=-90.0, runway_elevation=100,
    )
    assert result['outer'] is not None

    result = nav.calculate_runway_beacons(
        runway_threshold_lat=45.0, runway_threshold_lon=90.0,
        runway_heading=100000.0, runway_elevation=100,
    )
    assert result['outer'] is not None


# --- NAV-F1 addendum-3: SyntheticGlidepath single profile source ---

def test_synthetic_glidepath_cross_track_consistency():
    """NAV-F1 addendum-3: same along-track with cross-track 0, 0.5, 2 NM → same VS."""
    import pytest
    from modules.navigation import Navigation
    from modules.types import ApproachConfig, NavStation
    from modules.synthetic_glidepath import SyntheticGlidepath

    nav = Navigation.__new__(Navigation)
    station = NavStation(name="TEST", frequency=110.0,
                         latitude=45.0, longitude=90.0, type="VOR")
    config = ApproachConfig(
        station=station,
        final_approach_course=90,
        glideslope_angle=3.0,
        decision_height=200,
        approach_speed=90,
        runway_elevation=100,
        runway_length=3000,
        runway_width=45,
        runway_threshold_lat=45.0,
        runway_threshold_lon=90.0,
    )
    glidepath = SyntheticGlidepath(nav, config)

    ip = nav.calculate_glideslope_intercept_point(45.0, 90.0, 90.0, 100.0, 3.0)
    intercept_to_thresh = ip['intercept_to_threshold_nm']
    cos_lat = math.cos(math.radians(45.0))

    # 50% point on centerline
    along_nm = intercept_to_thresh * 0.5
    lon_offset = along_nm / (60.0 * cos_lat)
    ideal_agl = along_nm * ip['feet_per_nm']

    base_vs = 500.0  # Non-zero wind correction

    # Centerline
    vs_center = glidepath.compute_target_vs({
        'position': {
            'latitude': 45.0,
            'longitude': 90.0 - lon_offset,
            'altitude': 100 + ideal_agl,
            'altitude_agl': ideal_agl,
        }
    }, wind_correction_vs=base_vs)

    # 0.5 NM cross-track (latitude offset)
    ct_deg = 0.5 / 60.0
    vs_05 = glidepath.compute_target_vs({
        'position': {
            'latitude': 45.0 + ct_deg,
            'longitude': 90.0 - lon_offset,
            'altitude': 100 + ideal_agl,
            'altitude_agl': ideal_agl,
        }
    }, wind_correction_vs=base_vs)

    # 2 NM cross-track
    ct_deg = 2.0 / 60.0
    vs_2 = glidepath.compute_target_vs({
        'position': {
            'latitude': 45.0 + ct_deg,
            'longitude': 90.0 - lon_offset,
            'altitude': 100 + ideal_agl,
            'altitude_agl': ideal_agl,
        }
    }, wind_correction_vs=base_vs)

    # All should be approximately equal (cross-track shouldn't affect VS)
    assert vs_center == pytest.approx(vs_05, rel=1e-3, abs=1.0), (
        f"Cross-track 0.5 NM changed VS: {vs_center} vs {vs_05}"
    )
    assert vs_center == pytest.approx(vs_2, rel=1e-3, abs=1.0), (
        f"Cross-track 2 NM changed VS: {vs_center} vs {vs_2}"
    )


def test_synthetic_glidepath_on_profile_with_wind():
    """NAV-F1 addendum-3: on-profile with wind_correction_vs=500 → positive descent."""
    import pytest
    from modules.navigation import Navigation
    from modules.types import ApproachConfig, NavStation
    from modules.synthetic_glidepath import SyntheticGlidepath

    nav = Navigation.__new__(Navigation)
    station = NavStation(name="TEST", frequency=110.0,
                         latitude=45.0, longitude=90.0, type="VOR")
    config = ApproachConfig(
        station=station,
        final_approach_course=90,
        glideslope_angle=3.0,
        decision_height=200,
        approach_speed=90,
        runway_elevation=100,
        runway_length=3000,
        runway_width=45,
        runway_threshold_lat=45.0,
        runway_threshold_lon=90.0,
    )
    glidepath = SyntheticGlidepath(nav, config)

    ip = nav.calculate_glideslope_intercept_point(45.0, 90.0, 90.0, 100.0, 3.0)
    intercept_to_thresh = ip['intercept_to_threshold_nm']
    cos_lat = math.cos(math.radians(45.0))

    along_nm = intercept_to_thresh * 0.5
    lon_offset = along_nm / (60.0 * cos_lat)
    ideal_agl = along_nm * ip['feet_per_nm']

    wind_vs = 500.0
    vs = glidepath.compute_target_vs({
        'position': {
            'latitude': 45.0,
            'longitude': 90.0 - lon_offset,
            'altitude': 100 + ideal_agl,
            'altitude_agl': ideal_agl,
        }
    }, wind_correction_vs=wind_vs)

    # On-profile: altitude_error=0, so VS = wind_correction_vs + 0 = 500
    assert vs > 0, f"On-profile with wind should descend, got VS={vs}"
    assert vs == pytest.approx(wind_vs, rel=1e-3), (
        f"Expected VS≈{wind_vs}, got {vs}"
    )


def test_synthetic_glidepath_mda_floor():
    """NAV-F1 addendum-3: at/below MDA → VS=0."""
    from modules.navigation import Navigation
    from modules.types import ApproachConfig, NavStation
    from modules.synthetic_glidepath import SyntheticGlidepath

    nav = Navigation.__new__(Navigation)
    station = NavStation(name="TEST", frequency=110.0,
                         latitude=45.0, longitude=90.0, type="VOR")
    config = ApproachConfig(
        station=station,
        final_approach_course=90,
        glideslope_angle=3.0,
        decision_height=200,
        approach_speed=90,
        runway_elevation=100,
        runway_length=3000,
        runway_width=45,
        runway_threshold_lat=45.0,
        runway_threshold_lon=90.0,
    )
    glidepath = SyntheticGlidepath(nav, config)

    # MDA = 200 + 100 = 300 MSL
    # At MDA
    vs_at_mda = glidepath.compute_target_vs({
        'position': {
            'latitude': 45.0,
            'longitude': 89.95,
            'altitude': 300,  # At MDA
            'altitude_agl': 200,
        }
    }, wind_correction_vs=500.0)
    assert vs_at_mda == 0.0

    # Below MDA
    vs_below = glidepath.compute_target_vs({
        'position': {
            'latitude': 45.0,
            'longitude': 89.95,
            'altitude': 250,  # Below MDA
            'altitude_agl': 150,
        }
    }, wind_correction_vs=500.0)
    assert vs_below == 0.0


def test_synthetic_glidepath_past_threshold_no_descent():
    """NAV-F1 addendum-3: past threshold → no descent command."""
    from modules.navigation import Navigation
    from modules.types import ApproachConfig, NavStation
    from modules.synthetic_glidepath import SyntheticGlidepath

    nav = Navigation.__new__(Navigation)
    station = NavStation(name="TEST", frequency=110.0,
                         latitude=45.0, longitude=90.0, type="VOR")
    config = ApproachConfig(
        station=station,
        final_approach_course=90,
        glideslope_angle=3.0,
        decision_height=200,
        approach_speed=90,
        runway_elevation=100,
        runway_length=3000,
        runway_width=45,
        runway_threshold_lat=45.0,
        runway_threshold_lon=90.0,
    )
    glidepath = SyntheticGlidepath(nav, config)

    vs_past = glidepath.compute_target_vs({
        'position': {
            'latitude': 45.0,
            'longitude': 90.5,  # Past threshold
            'altitude': 100,
            'altitude_agl': 0,
        }
    }, wind_correction_vs=500.0)
    assert vs_past <= 0, f"Past threshold should not descend, got VS={vs_past}"
