"""F5 tests: defensive telemetry access in AutopilotTakeover."""
from modules.autopilot_takeover import AutopilotTakeover, TakeoverConfig
from tests.fakes import FakeClock


def _make_telemetry(alt=3000, agl=1500, ias=120, heading=270,
                    pitch=2, bank=0, vs=-500, on_ground=False):
    return {
        'position': {
            'altitude': alt,
            'altitude_agl': agl,
            'on_ground': on_ground,
        },
        'speed': {
            'airspeed_indicated': ias,
            'vertical_speed': vs,
        },
        'attitude': {
            'heading_magnetic': heading,
            'pitch': pitch,
            'bank': bank,
        },
    }


class TestSaveInitialParametersF5:
    def test_incomplete_telemetry_no_crash(self):
        """Missing keys → no crash, initial_parameters stays empty."""
        ctrl = AutopilotTakeover(clock=FakeClock(start=0))
        # Missing position entirely
        ctrl._save_initial_parameters({})
        assert ctrl.initial_parameters == {}

        # Missing speed
        ctrl._save_initial_parameters({
            'position': {'altitude': 3000, 'altitude_agl': 1500},
            'attitude': {'heading_magnetic': 270, 'pitch': 2, 'bank': 0},
            'speed': {},
        })
        assert ctrl.initial_parameters == {}

    def test_valid_telemetry_saves(self):
        """Complete telemetry → initial_parameters populated."""
        ctrl = AutopilotTakeover(clock=FakeClock(start=0))
        ctrl._save_initial_parameters(_make_telemetry())
        assert ctrl.initial_parameters['altitude'] == 3000
        assert ctrl.initial_parameters['airspeed'] == 120


class TestSafetyChecksF5:
    def test_missing_bank_fail_closed(self):
        """bank=None → attitude_safe=False (fail-closed, not 0.0)."""
        ctrl = AutopilotTakeover(config=TakeoverConfig())
        ctrl.initial_parameters = {'airspeed': 120, 'altitude': 3000}
        telemetry = _make_telemetry()
        telemetry['attitude']['bank'] = None
        checks = ctrl._perform_safety_checks(telemetry, 'VOR', 200)
        assert checks['attitude_safe'] is False

    def test_missing_airspeed_fail_closed(self):
        """airspeed=None → speed_stable=False."""
        ctrl = AutopilotTakeover(config=TakeoverConfig())
        ctrl.initial_parameters = {'airspeed': 120, 'altitude': 3000}
        telemetry = _make_telemetry()
        telemetry['speed']['airspeed_indicated'] = None
        checks = ctrl._perform_safety_checks(telemetry, 'VOR', 200)
        assert checks['speed_stable'] is False

    def test_missing_altitude_fail_closed(self):
        """altitude=None → altitude_stable=False."""
        ctrl = AutopilotTakeover(config=TakeoverConfig())
        ctrl.initial_parameters = {'airspeed': 120, 'altitude': 3000}
        telemetry = _make_telemetry()
        telemetry['position']['altitude'] = None
        checks = ctrl._perform_safety_checks(telemetry, 'VOR', 200)
        assert checks['altitude_stable'] is False

    def test_missing_vs_fail_closed(self):
        """vertical_speed=None → sink_rate_safe=False."""
        ctrl = AutopilotTakeover(config=TakeoverConfig())
        ctrl.initial_parameters = {'airspeed': 120, 'altitude': 3000}
        telemetry = _make_telemetry()
        telemetry['speed']['vertical_speed'] = None
        checks = ctrl._perform_safety_checks(telemetry, 'VOR', 200)
        assert checks['sink_rate_safe'] is False

    def test_missing_agl_fail_closed(self):
        """altitude_agl=None → altitude_safe=False."""
        ctrl = AutopilotTakeover(config=TakeoverConfig())
        ctrl.initial_parameters = {'airspeed': 120, 'altitude': 3000}
        telemetry = _make_telemetry()
        telemetry['position']['altitude_agl'] = None
        checks = ctrl._perform_safety_checks(telemetry, 'VOR', 200)
        assert checks['altitude_safe'] is False

    def test_no_initial_params_speed_stable_false(self):
        """No initial_parameters → speed_stable=False."""
        ctrl = AutopilotTakeover(config=TakeoverConfig())
        checks = ctrl._perform_safety_checks(_make_telemetry(), 'VOR', 200)
        assert checks['speed_stable'] is False
