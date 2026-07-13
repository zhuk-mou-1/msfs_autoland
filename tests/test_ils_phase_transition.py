"""F2 tests: ILS INTERMEDIATE→FINAL transition (deadlock fix)."""
from unittest.mock import MagicMock
from modules.approach_phases import IntermediatePhaseState, FinalPhaseState


def _make_system(approach_type='ILS', takeover_completed=False,
                 on_localizer=True, distance=5.0, required_alt=1000,
                 altitude=1100):
    """Create a mock AutoLandSystem with minimal state for phase transition tests."""
    system = MagicMock()
    system.approach_config.station.type = approach_type
    system.approach_config.decision_height = 200
    system.approach_config.approach_speed = 120
    system.autopilot_takeover.status.completed = takeover_completed
    system.autopilot_takeover.status.failed = False
    system.takeover_initiated = takeover_completed
    system.use_autothrottle = False
    system.use_vjoy = False
    system.phase = MagicMock()
    system.phase.value = 'INTERMEDIATE'
    system.dme_navigation.check_dme_accuracy.return_value = {'status': 'OK'}
    system.dme_navigation.check_altitude_at_fix.return_value = {'has_fix': False}
    system.navigation.calculate_distance_to_threshold.return_value = distance
    return system


def _make_telemetry(alt=1100, agl=1100):
    return {
        'position': {'altitude': alt, 'altitude_agl': agl,
                     'latitude': 55.5, 'longitude': 37.5},
        'attitude': {'heading_magnetic': 270, 'bank': 0, 'pitch': 2},
        'speed': {'airspeed_indicated': 120, 'vertical_speed': -500,
                  'ground_speed': 140},
        'nav': {'nav1_dme_distance': 5.0},
    }


def _make_approach_data(distance=5.0, required_alt=1000,
                        on_localizer=True, on_course=True):
    return {
        'distance_to_station': distance,
        'required_altitude': required_alt,
        'cross_track_error': 0.5,
        'on_course': on_course,
        'on_localizer': on_localizer,
        'corrected_heading': 270,
    }


def _make_wind_data():
    return {
        'wind_speed': 10, 'wind_direction': 270,
        'headwind': 8, 'crosswind': 2,
        'corrected_heading': 270, 'corrected_vs': 500,
        'drift_angle': 1.0, 'base_vs': 500, 'vs_correction': 0,
    }


class TestILSIntermediateToFinal:
    def test_ils_transitions_on_loc_capture(self):
        """ILS: INTERMEDIATE → FINAL when LOC captured + distance < 8."""
        system = _make_system(approach_type='ILS', takeover_completed=False)
        # Prevent _check_autopilot_takeover from initiating takeover
        system.autopilot_takeover.should_initiate_takeover.return_value = False
        state = IntermediatePhaseState(system)
        result = state.handle(
            _make_telemetry(),
            _make_approach_data(distance=5.0, on_localizer=True),
            _make_wind_data(),
        )
        assert isinstance(result, FinalPhaseState), (
            "ILS should transition to FINAL on LOC capture without takeover.completed")

    def test_ils_no_final_without_loc(self):
        """ILS: INTERMEDIATE stays if LOC not captured."""
        system = _make_system(approach_type='ILS', takeover_completed=False)
        system.autopilot_takeover.should_initiate_takeover.return_value = False
        state = IntermediatePhaseState(system)
        result = state.handle(
            _make_telemetry(),
            _make_approach_data(distance=5.0, on_localizer=False),
            _make_wind_data(),
        )
        assert result is None, "ILS should NOT transition without LOC capture"

    def test_vor_requires_completed_takeover(self):
        """Non-ILS: INTERMEDIATE → FINAL only after takeover completed."""
        system = _make_system(approach_type='VOR', takeover_completed=False)
        state = IntermediatePhaseState(system)
        result = state.handle(
            _make_telemetry(),
            _make_approach_data(distance=5.0),
            _make_wind_data(),
        )
        assert result is None, "VOR should NOT transition without completed takeover"

    def test_vor_transitions_with_completed_takeover(self):
        """Non-ILS: INTERMEDIATE → FINAL when takeover completed."""
        system = _make_system(approach_type='VOR', takeover_completed=True)
        system.use_autothrottle = False
        state = IntermediatePhaseState(system)
        result = state.handle(
            _make_telemetry(),
            _make_approach_data(distance=5.0),
            _make_wind_data(),
        )
        assert isinstance(result, FinalPhaseState)
