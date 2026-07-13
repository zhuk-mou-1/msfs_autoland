"""F1 contract tests: all consumer keys present in producer returns."""
from modules.ils_navigation import ILSNavigation, ILSConfig
from modules.types import ApproachConfig, NavStation


def _make_ils_config():
    return ILSConfig(
        frequency=110300000,
        localizer_course=270,
        glideslope_angle=3.0,
        decision_height=200,
        approach_speed=120,
        runway_elevation=0,
        runway_length=8000,
        runway_threshold_lat=55.48,
        runway_threshold_lon=37.52,
    )


def _make_telemetry(lat=55.5, lon=37.5, alt=3000, gs=140, dme=None):
    nav = {}
    if dme is not None:
        nav['nav1_dme_distance'] = dme
    return {
        'position': {'altitude': alt, 'latitude': lat, 'longitude': lon},
        'speed': {'ground_speed': gs},
        'nav': nav,
    }


def _make_ils_data(has_loc=True, has_gs=True, cdi=0, gsi=0):
    return {
        'nav1_has_localizer': has_loc,
        'nav1_has_glideslope': has_gs,
        'nav1_cdi': cdi,   # raw CDI: -127..+127
        'nav1_gsi': gsi,   # raw GSI: -127..+127
    }


# ── ILS consumer keys ────────────────────────────────────────────

ILS_CONSUMER_KEYS = [
    'distance_to_station', 'cross_track_error', 'on_course',
    'required_altitude', 'corrected_heading',
]

LOC_CONSUMER_KEYS = [
    'distance_to_station', 'cross_track_error', 'on_course',
    'required_altitude', 'corrected_heading',
]

VOR_CONSUMER_KEYS = [
    'distance_to_station', 'cross_track_error', 'on_course',
    'required_altitude',
]


class TestILSContract:
    def test_ils_returns_all_consumer_keys(self):
        nav = ILSNavigation()
        nav.configure(_make_ils_config())
        result = nav.calculate_ils_approach(
            _make_telemetry(dme=5.0), _make_ils_data())
        for key in ILS_CONSUMER_KEYS:
            assert key in result, f"ILS missing key: {key}"

    def test_ils_keys_are_not_none(self):
        nav = ILSNavigation()
        nav.configure(_make_ils_config())
        result = nav.calculate_ils_approach(
            _make_telemetry(dme=5.0), _make_ils_data())
        for key in ILS_CONSUMER_KEYS:
            assert result[key] is not None, f"ILS key {key} is None"

    def test_ils_distance_geometric_fallback_no_dme(self):
        """When DME=0, distance_to_station must be geometric, not 0."""
        nav = ILSNavigation()
        nav.configure(_make_ils_config())
        result = nav.calculate_ils_approach(
            _make_telemetry(lat=55.5, lon=37.5, dme=0),
            _make_ils_data())
        assert result['distance_to_station'] > 0, (
            "Geometric distance should be > 0 when DME unavailable")

    def test_ils_cross_track_error_is_degrees(self):
        """cross_track_error for ILS is in degrees (negative = left of LOC)."""
        nav = ILSNavigation()
        nav.configure(_make_ils_config())
        # CDI=50 → positive deviation → cross_track_error = -degrees < 0
        result = nav.calculate_ils_approach(
            _make_telemetry(dme=5.0),
            _make_ils_data(cdi=50))
        assert isinstance(result['cross_track_error'], float)
        assert result['cross_track_error'] < 0, (
            f"Expected negative cross_track_error, got {result['cross_track_error']}")
        assert result['on_course'] is False


class TestLOCContract:
    def test_loc_returns_all_consumer_keys(self):
        nav = ILSNavigation()
        nav.configure(_make_ils_config())
        result = nav.calculate_loc_approach(
            _make_telemetry(), _make_ils_data(has_gs=False))
        for key in LOC_CONSUMER_KEYS:
            assert key in result, f"LOC missing key: {key}"

    def test_loc_keys_are_not_none(self):
        nav = ILSNavigation()
        nav.configure(_make_ils_config())
        result = nav.calculate_loc_approach(
            _make_telemetry(), _make_ils_data(has_gs=False))
        for key in LOC_CONSUMER_KEYS:
            assert result[key] is not None, f"LOC key {key} is None"

    def test_loc_required_altitude_from_glidepath_geometry(self):
        """LOC required_altitude should use synthetic glidepath geometry."""
        nav = ILSNavigation()
        nav.configure(_make_ils_config())
        result = nav.calculate_loc_approach(
            _make_telemetry(dme=5.0), _make_ils_data(has_gs=False))
        assert result['required_altitude'] > 0

    def test_loc_distance_geometric(self):
        nav = ILSNavigation()
        nav.configure(_make_ils_config())
        result = nav.calculate_loc_approach(
            _make_telemetry(), _make_ils_data(has_gs=False))
        assert result['distance_to_station'] > 0


class TestVORContract:
    def test_vor_returns_all_consumer_keys(self):
        """Regression: VOR still returns full key set."""
        from modules.navigation import Navigation
        nav = Navigation()
        config = ApproachConfig(
            station=NavStation("TestVOR", 11030000, 55.5, 37.5, 'VOR'),
            final_approach_course=270,
            glideslope_angle=3.0,
            decision_height=200,
            approach_speed=120,
            runway_elevation=0,
            runway_length=8000,
            runway_width=150,
            runway_threshold_lat=55.48,
            runway_threshold_lon=37.52,
        )
        result = nav.calculate_vor_approach(
            {'latitude': 55.5, 'longitude': 37.5},
            {},
            config,
        )
        for key in VOR_CONSUMER_KEYS:
            assert key in result, f"VOR missing key: {key}"
