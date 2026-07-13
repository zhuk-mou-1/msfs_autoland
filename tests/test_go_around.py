"""F3/F4 tests: execute_go_around re-engages AP + error budget go-around."""
from unittest.mock import MagicMock, patch
from tests.fakes import FakeControl


class TestGoAroundF3:
    def test_go_around_reengages_ap_master(self):
        """execute_go_around() must call set_autopilot_master(True)."""
        from main import AutoLandSystem
        system = AutoLandSystem.__new__(AutoLandSystem)
        system.control = FakeControl()
        system.autothrottle = MagicMock()
        system.autothrottle.active = False
        system.use_vjoy = False
        system.vjoy_throttle = None
        system.virtual_joystick = MagicMock()
        system.stabilized_monitor = MagicMock()
        system.telemetry_recorder = MagicMock()
        system.phase = MagicMock()
        system.phase.value = 'FINAL'

        system.execute_go_around()

        assert system.control.has_call('set_autopilot_master'), (
            "AP master should be re-engaged in go-around")
        # First call should be True (re-engage)
        ap_calls = system.control.calls_of('set_autopilot_master')
        assert ap_calls[0][1] is True, (
            f"AP master should be re-engaged to True, got {ap_calls[0][1]}")

    def test_go_around_sends_gear_up(self):
        """execute_go_around() must call set_gear(False) — real gear UP command."""
        from main import AutoLandSystem
        system = AutoLandSystem.__new__(AutoLandSystem)
        system.control = FakeControl()
        system.autothrottle = MagicMock()
        system.autothrottle.active = False
        system.use_vjoy = False
        system.vjoy_throttle = None
        system.virtual_joystick = MagicMock()
        system.stabilized_monitor = MagicMock()
        system.telemetry_recorder = MagicMock()
        system.phase = MagicMock()
        system.phase.value = 'FINAL'

        system.execute_go_around()

        assert system.control.has_call('set_gear'), "Gear command should be sent"
        gear_calls = system.control.calls_of('set_gear')
        assert gear_calls[0][1] is False, "Gear should be UP (False)"

    def test_go_around_sends_vs_and_throttle(self):
        """execute_go_around() sends VS=1500 and throttle=1.0."""
        from main import AutoLandSystem
        system = AutoLandSystem.__new__(AutoLandSystem)
        system.control = FakeControl()
        system.autothrottle = MagicMock()
        system.autothrottle.active = False
        system.use_vjoy = False
        system.vjoy_throttle = None
        system.virtual_joystick = MagicMock()
        system.stabilized_monitor = MagicMock()
        system.telemetry_recorder = MagicMock()
        system.phase = MagicMock()
        system.phase.value = 'FINAL'

        system.execute_go_around()

        assert system.control.has_call('set_vertical_speed')
        vs_calls = system.control.calls_of('set_vertical_speed')
        assert vs_calls[0][1] == 1500

        assert system.control.has_call('set_throttle')
        thr_calls = system.control.calls_of('set_throttle')
        assert thr_calls[0][1] == 1.0


class TestErrorBudgetF4:
    def test_error_budget_goaround_after_takeover(self):
        """3 errors + takeover.completed → execute_go_around (not stop)."""
        from main import AutoLandSystem
        system = AutoLandSystem.__new__(AutoLandSystem)
        system.control = FakeControl()
        system.autothrottle = MagicMock()
        system.autothrottle.active = False
        system.use_vjoy = False
        system.vjoy_throttle = None
        system.virtual_joystick = MagicMock()
        system.stabilized_monitor = MagicMock()
        system.telemetry_recorder = MagicMock()
        system.autopilot_takeover = MagicMock()
        system.autopilot_takeover.status.completed = True
        system.phase = MagicMock()
        system.phase.value = 'FINAL'
        system.running = True
        system.connection_monitor = None
        system.connection_optimizer = None
        system.audio_alerts_enabled = False
        system.audio_system = None
        system._last_guard_decision = None
        system._last_guard_reason = None
        system._last_fms_log_time = 0
        system._last_guard_snapshot_log_time = 0
        system.fms_reader = None
        system.safety_guard = None
        system.approach_config = MagicMock()
        system.approach_config.approach_speed = 120

        # Force 3 consecutive errors by making get_all_data raise
        system.telemetry = MagicMock()
        system.telemetry.get_all_data.side_effect = SimulatedError("test")

        with patch.object(system, 'execute_go_around') as mock_ga:
            with patch.object(system, 'stop_approach') as mock_stop:
                system.execute_approach()
                mock_ga.assert_called_once()
                mock_stop.assert_not_called()

    def test_error_budget_stop_before_takeover(self):
        """3 errors + takeover NOT completed → stop_approach (safe, AP on)."""
        from main import AutoLandSystem
        system = AutoLandSystem.__new__(AutoLandSystem)
        system.control = FakeControl()
        system.autothrottle = MagicMock()
        system.autothrottle.active = False
        system.use_vjoy = False
        system.vjoy_throttle = None
        system.virtual_joystick = MagicMock()
        system.stabilized_monitor = MagicMock()
        system.telemetry_recorder = MagicMock()
        system.autopilot_takeover = MagicMock()
        system.autopilot_takeover.status.completed = False
        system.phase = MagicMock()
        system.phase.value = 'FINAL'
        system.running = True
        system.connection_monitor = None
        system.connection_optimizer = None
        system.audio_alerts_enabled = False
        system.audio_system = None
        system._last_guard_decision = None
        system._last_guard_reason = None
        system._last_fms_log_time = 0
        system._last_guard_snapshot_log_time = 0
        system.fms_reader = None
        system.safety_guard = None
        system.approach_config = MagicMock()
        system.approach_config.approach_speed = 120

        system.telemetry = MagicMock()
        system.telemetry.get_all_data.side_effect = SimulatedError("test")

        with patch.object(system, 'execute_go_around') as mock_ga:
            with patch.object(system, 'stop_approach') as mock_stop:
                system.execute_approach()
                mock_stop.assert_called_once()
                mock_ga.assert_not_called()


class SimulatedError(Exception):
    pass
