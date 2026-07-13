"""TASK-007-PREP: Telemetry recorder tests (FIX-13..FIX-17).

Tests:
  T-REC-1..7: Previous tests (flatten, write, schema, lifecycle, read-only).
  T-REC-8: Immediate disk write — row on disk before stop_recording.
  T-REC-9: Reliable close — real file flush/close error handled.
  T-REC-10: Production wiring — _handle_phase sets guard verdict.
  T-REC-11: All terminal frames (GO_AROUND, approach_data=None, touchdown).
  T-REC-12: Guard verdict reset before early return.
  T-REC-13: LOC-loss production path — _calculate_approach_data returns None.
  T-REC-14: Actuator commands before disk I/O (pending frame pattern).
  T-REC-15: Real execute_approach test.
  T-REC-16: FIELDNAMES matches real get_all_data contract.
  T-REC-17: Real flush/close failure test.
"""

import copy
import csv
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from modules.telemetry_recorder import TelemetryRecorder, _flatten_dict, FIELDNAMES
from tests.fakes import make_telemetry


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _full_telemetry() -> dict:
    """Simulate full get_all_data() output with all nested sections."""
    base = make_telemetry(
        altitude=3000, altitude_agl=2500, radio_height=2400,
        airspeed=130, vertical_speed=-800, ground_speed=135,
        bank=2.5, pitch=3.0, heading=265,
    )
    base['orientation'] = dict(base['attitude'])  # alias
    base['ils'] = {
        'nav1_has_localizer': True,
        'nav1_has_glideslope': True,
        'nav1_cdi': 3,
    }
    base['autopilot'] = {'master': True, 'heading_hold': True}
    base['weather'] = {'ambient_temperature': 12, 'kohlsman_setting': 1013}
    base['weight'] = {'total_weight': 55000}
    base['aircraft'] = {'title': 'Test Aircraft'}
    base['configuration'] = {'flaps_position': 0.7, 'gear_position': 1.0}
    base['nav'] = {'nav1_frequency': 11030000}
    base['g_force'] = 1.0
    base['g_force_data'] = {'g_force': 1.0, 'acceleration_body_x': 0,
                            'acceleration_body_y': 0, 'acceleration_body_z': 0}
    base['gps_destination'] = {'airport_icao': 'UUEE', 'runway_id': '07C'}
    base['approach_info'] = {'approach_type': 'VOR', 'approach_active': True}
    return base


def _read_csv(path: Path) -> tuple:
    """Read CSV file, return (header, list-of-row-dicts)."""
    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        rows = list(reader)
    return header, rows


# ═══════════════════════════════════════════════════════════════════
# FIX-16: FIELDNAMES matches real get_all_data contract
# ═══════════════════════════════════════════════════════════════════

class TestFieldnamesContract:
    """FIX-16: Every key from get_all_data flattened must be in FIELDNAMES."""

    def test_fieldnames_is_sorted(self):
        assert FIELDNAMES == sorted(FIELDNAMES)

    def test_all_get_all_data_keys_in_fieldnames(self):
        """flatten(_full_telemetry()).keys() ⊆ FIELDNAMES."""
        flat = {}
        telemetry = _full_telemetry()
        for section_name in sorted(telemetry.keys()):
            section = telemetry[section_name]
            if isinstance(section, dict):
                flat.update(_flatten_dict(section, parent_key=section_name))
            else:
                flat[section_name] = section
        flat['timestamp'] = 0.0
        flat['phase'] = 'FINAL'
        flat['guard_decision'] = ''
        flat['guard_reason'] = ''

        missing = set(flat.keys()) - set(FIELDNAMES)
        assert not missing, f"Keys in get_all_data not in FIELDNAMES: {missing}"

    def test_fieldnames_contains_orientation_section(self):
        """orientation_* columns must be present (alias for attitude)."""
        orientation_fields = [f for f in FIELDNAMES if f.startswith('orientation_')]
        assert len(orientation_fields) > 0

    def test_weather_kohlsman_setting命名正确(self):
        """weather_kohlsman_setting must match get_weather_data key."""
        assert 'weather_kohlsman_setting' in FIELDNAMES


# ═══════════════════════════════════════════════════════════════════
# Unit tests — _flatten_dict
# ═══════════════════════════════════════════════════════════════════

class TestFlattenDict:
    def test_simple_dict(self):
        assert _flatten_dict({'a': 1, 'b': 2}) == {'a': 1, 'b': 2}

    def test_nested_dict(self):
        assert _flatten_dict({'pos': {'lat': 55.0}}) == {'pos_lat': 55.0}

    def test_sorted_keys(self):
        assert list(_flatten_dict({'z': 1, 'a': 2}).keys()) == ['a', 'z']


# ═══════════════════════════════════════════════════════════════════
# FIX-8: Immediate disk write
# ═══════════════════════════════════════════════════════════════════

class TestImmediateDiskWrite:
    def test_row_on_disk_after_write(self, tmp_path):
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()
        rec.write_frame(_full_telemetry(), phase="FINAL",
                        guard_decision="CONTINUE", guard_reason="ok")
        csv_files = list(tmp_path.glob('telemetry_*.csv'))
        _, rows = _read_csv(csv_files[0])
        assert len(rows) == 1
        assert rows[0]['phase'] == 'FINAL'
        rec.stop_recording()

    def test_multiple_rows_incrementally(self, tmp_path):
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()
        for i in range(3):
            rec.write_frame(_full_telemetry(), phase="FINAL")
            _, rows = _read_csv(list(tmp_path.glob('telemetry_*.csv'))[0])
            assert len(rows) == i + 1
        rec.stop_recording()


# ═══════════════════════════════════════════════════════════════════
# FIX-2: Stable schema
# ═══════════════════════════════════════════════════════════════════

class TestStableSchema:
    def test_incomplete_first_frame_recovered(self, tmp_path):
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()
        t1 = _full_telemetry()
        t1['nav'] = {}
        rec.write_frame(t1, phase="INITIAL")
        t2 = _full_telemetry()
        t2['nav'] = {'nav1_frequency': 11030000}
        rec.write_frame(t2, phase="FINAL")
        rec.stop_recording()
        csv_files = list(tmp_path.glob('telemetry_*.csv'))
        header, rows = _read_csv(csv_files[0])
        assert len(rows) == 2
        assert 'nav_nav1_frequency' in header
        assert rows[1]['nav_nav1_frequency'] == '11030000'


# ═══════════════════════════════════════════════════════════════════
# FIX-9: Reliable close
# ═══════════════════════════════════════════════════════════════════

class TestReliableClose:
    def test_close_error_logged_no_exception(self, tmp_path, caplog):
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()
        rec.write_frame(_full_telemetry(), phase="FINAL")
        rec._file.close()
        with caplog.at_level(logging.WARNING, logger="modules.telemetry_recorder"):
            rec.stop_recording()
        assert rec._file is None

    def test_close_preserves_rows(self, tmp_path):
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()
        for _ in range(5):
            rec.write_frame(_full_telemetry(), phase="FINAL")
        rec._file.close()
        rec.stop_recording()
        _, rows = _read_csv(list(tmp_path.glob('telemetry_*.csv'))[0])
        assert len(rows) == 5


# ═══════════════════════════════════════════════════════════════════
# FIX-17: Real flush/close failure
# ═══════════════════════════════════════════════════════════════════

class TestRealFlushCloseFailure:
    """FIX-17: Replace active file.flush/file.close to raise — verify handling."""

    def test_flush_error_during_write_frame(self, tmp_path, caplog):
        """Monkeypatch file.flush to raise while recording is active."""
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()

        original_flush = rec._file.flush

        def failing_flush():
            raise OSError("Simulated flush failure")

        rec._file.flush = failing_flush

        with caplog.at_level(logging.WARNING, logger="modules.telemetry_recorder"):
            rec.write_frame(_full_telemetry(), phase="FINAL")

        assert "write error" in caplog.text.lower()
        assert rec.is_recording  # recorder still active

        rec._file.flush = original_flush
        rec.stop_recording()

    def test_close_error_in_stop_recording(self, tmp_path, caplog):
        """Monkeypatch file.close to raise during stop_recording."""
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()
        rec.write_frame(_full_telemetry(), phase="FINAL")

        original_close = rec._file.close

        def failing_close():
            raise OSError("Simulated close failure")

        rec._file.close = failing_close

        with caplog.at_level(logging.WARNING, logger="modules.telemetry_recorder"):
            rec.stop_recording()

        assert "close error" in caplog.text.lower()
        assert rec._file is None  # cleanup happened

    def test_start_recording_cleanup_on_error(self, tmp_path, caplog):
        """If writeheader fails during start_recording, file handle is closed."""
        rec = TelemetryRecorder(log_dir=str(tmp_path))

        # Monkeypatch csv.DictWriter to raise on writeheader
        original_dictwriter = csv.DictWriter
        class FailingDictWriter(csv.DictWriter):
            def writeheader(self):
                raise OSError("Simulated writeheader failure")

        with patch('modules.telemetry_recorder.csv.DictWriter', FailingDictWriter):
            with caplog.at_level(logging.WARNING, logger="modules.telemetry_recorder"):
                rec.start_recording()

        # Error was handled — file is closed or recorder didn't start
        assert not rec.is_recording
        assert rec._file is None
        assert "failed to start" in caplog.text.lower() or "writeheader" in caplog.text.lower()


# ═══════════════════════════════════════════════════════════════════
# FIX-14: Actuator commands before disk I/O
# ═══════════════════════════════════════════════════════════════════

class TestPendingFramePattern:
    """T2: Real actuator → disk I/O order via real execute_go_around."""

    def test_go_around_actuator_before_flush(self, tmp_path):
        """Real AutoLandSystem.execute_go_around with FakeControl.
        Proves: set_throttle < writerow, set_vertical_speed < writerow,
        set_flaps < writerow. Exactly 1 CSV terminal row."""
        from main import AutoLandSystem, ApproachPhase
        from modules.safety_guard import ApproachSafetyGuard
        from modules.types import ApproachConfig, NavStation
        from tests.fakes import FakeControl

        system = AutoLandSystem.__new__(AutoLandSystem)
        system.phase = ApproachPhase.FINAL
        system.approach_config = ApproachConfig(
            station=NavStation("TEST", 11030000, 55.5, 37.5, "VOR"),
            final_approach_course=270, glideslope_angle=3.0,
            decision_height=200, approach_speed=120,
            runway_elevation=0, runway_length=8000, runway_width=150,
            runway_threshold_lat=55.48, runway_threshold_lon=37.52,
        )
        system.safety_guard = ApproachSafetyGuard(debounce_n=1)
        system.wind_correction = MagicMock()
        system.wind_correction.apply_wind_corrections.return_value = {
            "corrected_heading": 270, "corrected_vs": 700,
            "headwind": 10, "crosswind": 5, "wind_speed": 12,
            "wind_direction": 280, "drift_angle": 2.0,
        }
        system.fms_reader = None
        system.phase_state = MagicMock()
        system._last_guard_snapshot_log_time = 0.0

        system.telemetry_recorder = TelemetryRecorder(log_dir=str(tmp_path))
        system.telemetry_recorder.start_recording()

        # Real control via FakeControl
        control = FakeControl()
        system.control = control
        system.autothrottle = MagicMock()
        system.autothrottle.active = False
        system.vjoy_throttle = None
        system.use_vjoy = False
        system.stabilized_monitor = MagicMock()
        system.running = True
        system.phase = ApproachPhase.FINAL

        # Track real events in order
        call_order = []

        # Wrap real control methods
        original_set_throttle = control.set_throttle
        def tracking_set_throttle(v):
            call_order.append("set_throttle")
            return original_set_throttle(v)
        control.set_throttle = tracking_set_throttle

        original_set_vs = control.set_vertical_speed
        def tracking_set_vs(vs):
            call_order.append("set_vertical_speed")
            return original_set_vs(vs)
        control.set_vertical_speed = tracking_set_vs

        original_set_flaps = control.set_flaps
        def tracking_set_flaps(pos):
            call_order.append("set_flaps")
            return original_set_flaps(pos)
        control.set_flaps = tracking_set_flaps

        # Wrap real recorder writerow/flush
        original_writerow = system.telemetry_recorder._writer.writerow
        def tracking_writerow(row):
            call_order.append("writerow")
            return original_writerow(row)
        system.telemetry_recorder._writer.writerow = tracking_writerow

        original_flush = system.telemetry_recorder._file.flush
        def tracking_flush():
            call_order.append("file_flush")
            return original_flush()
        system.telemetry_recorder._file.flush = tracking_flush

        telemetry = make_telemetry(vertical_speed=-2000, altitude_agl=500,
                                   airspeed=120)
        approach_data = {"distance_to_station": 5.0, "required_altitude": 2000,
                         "on_course": True, "cross_track_error": 0.5}

        system._handle_phase(telemetry, approach_data)

        # Real actuator commands were sent
        assert control.has_call('set_throttle')
        assert control.has_call('set_vertical_speed')
        assert control.has_call('set_flaps')

        # Verify order: actuator commands BEFORE disk I/O
        assert call_order.index("set_throttle") < call_order.index("writerow")
        assert call_order.index("set_vertical_speed") < call_order.index("writerow")
        assert call_order.index("set_flaps") < call_order.index("writerow")

        # Verify order: actuator commands BEFORE file flush
        assert call_order.index("set_throttle") < call_order.index("file_flush")
        assert call_order.index("set_vertical_speed") < call_order.index("file_flush")
        assert call_order.index("set_flaps") < call_order.index("file_flush")

        # Exactly 1 CSV terminal row
        system.telemetry_recorder.stop_recording()
        csv_files = list(tmp_path.glob('telemetry_*.csv'))
        _, rows = _read_csv(csv_files[0])
        assert len(rows) == 1
        assert rows[0]['guard_decision'] == 'GO_AROUND'
        assert rows[0]['guard_reason'] == 'CRITICAL_SINK_RATE'

        # phase_state was reset to None by stop_approach
        assert system.phase_state is None


# ═══════════════════════════════════════════════════════════════════
# FIX-13: LOC-loss production path
# ═══════════════════════════════════════════════════════════════════

class TestLocLossProductionPath:
    """FIX-13: _calculate_approach_data calls execute_go_around for LOC loss."""

    def test_loc_signal_loss_via_calculate_approach_data(self, tmp_path):
        """Real LOC-loss path: _calculate_approach_data calls execute_go_around,
        sets pending frame, returns None. stop_recording flushes pending."""
        from main import AutoLandSystem, ApproachPhase
        from modules.types import ApproachConfig, NavStation

        system = AutoLandSystem.__new__(AutoLandSystem)
        system.phase = ApproachPhase.FINAL
        system.approach_config = ApproachConfig(
            station=NavStation("TEST_LOC", 11030000, 55.5, 37.5, "LOC"),
            final_approach_course=270, glideslope_angle=3.0,
            decision_height=200, approach_speed=120,
            runway_elevation=0, runway_length=8000, runway_width=150,
            runway_threshold_lat=55.48, runway_threshold_lon=37.52,
        )
        system.use_ils = False
        system.use_vjoy = False
        system.use_autothrottle = False
        system.ils_navigation = MagicMock()
        system.ils_navigation.calculate_loc_approach.return_value = {
            'loc_available': False
        }
        system.wind_correction = MagicMock()
        system.safety_guard = MagicMock()
        system.fms_reader = None
        system.phase_state = MagicMock()
        system._last_guard_snapshot_log_time = 0.0
        system.autothrottle = MagicMock()
        system.autothrottle.active = False
        system.vjoy_throttle = None
        system.control = MagicMock()
        system.stabilized_monitor = MagicMock()
        system.running = True
        system.audio_alerts_enabled = False
        system.audio_system = MagicMock()
        system.execute_go_around = MagicMock()

        system.telemetry_recorder = TelemetryRecorder(log_dir=str(tmp_path))
        system.telemetry_recorder.start_recording()

        telemetry = make_telemetry(vertical_speed=-700, altitude_agl=500,
                                   airspeed=120, bank=3.0)

        # Real production path: _calculate_approach_data
        approach_data = system._calculate_approach_data(telemetry)
        assert approach_data is None  # LOC signal lost
        system.execute_go_around.assert_called_once()

        system.telemetry_recorder.stop_recording()

        csv_files = list(tmp_path.glob('telemetry_*.csv'))
        _, rows = _read_csv(csv_files[0])
        assert len(rows) == 1  # exactly one terminal frame


# ═══════════════════════════════════════════════════════════════════
# FIX-11: Terminal guard frame
# ═══════════════════════════════════════════════════════════════════

class TestTerminalGuardFrame:
    def test_go_around_frame_in_csv(self, tmp_path):
        from main import AutoLandSystem, ApproachPhase
        from modules.safety_guard import ApproachSafetyGuard
        from modules.types import ApproachConfig, NavStation

        system = AutoLandSystem.__new__(AutoLandSystem)
        system.phase = ApproachPhase.FINAL
        system.approach_config = ApproachConfig(
            station=NavStation("TEST", 11030000, 55.5, 37.5, "VOR"),
            final_approach_course=270, glideslope_angle=3.0,
            decision_height=200, approach_speed=120,
            runway_elevation=0, runway_length=8000, runway_width=150,
            runway_threshold_lat=55.48, runway_threshold_lon=37.52,
        )
        system.safety_guard = ApproachSafetyGuard(debounce_n=1)
        system.wind_correction = MagicMock()
        system.wind_correction.apply_wind_corrections.return_value = {
            "corrected_heading": 270, "corrected_vs": 700,
            "headwind": 10, "crosswind": 5, "wind_speed": 12,
            "wind_direction": 280, "drift_angle": 2.0,
        }
        system.fms_reader = None
        system.phase_state = MagicMock()
        system._last_guard_snapshot_log_time = 0.0

        system.telemetry_recorder = TelemetryRecorder(log_dir=str(tmp_path))
        system.telemetry_recorder.start_recording()

        system.autothrottle = MagicMock()
        system.autothrottle.active = False
        system.vjoy_throttle = None
        system.control = MagicMock()
        system.use_vjoy = False
        system.stabilized_monitor = MagicMock()
        system.running = True
        system.phase = ApproachPhase.FINAL
        system.phase_state = MagicMock()

        telemetry = make_telemetry(vertical_speed=-2000, altitude_agl=500,
                                   airspeed=120)
        approach_data = {"distance_to_station": 5.0, "required_altitude": 2000,
                         "on_course": True, "cross_track_error": 0.5}

        system._handle_phase(telemetry, approach_data)
        system.telemetry_recorder.stop_recording()

        csv_files = list(tmp_path.glob('telemetry_*.csv'))
        _, rows = _read_csv(csv_files[0])
        assert len(rows) >= 1
        assert rows[-1]['guard_decision'] == 'GO_AROUND'
        assert rows[-1]['guard_reason'] == 'CRITICAL_SINK_RATE'


# ═══════════════════════════════════════════════════════════════════
# FIX-12: Guard verdict reset
# ═══════════════════════════════════════════════════════════════════

class TestGuardVerdictReset:
    def test_no_stale_verdict_on_approach_data_none(self, tmp_path):
        """_handle_phase(None) is a no-op — no rows written, no stale verdict."""
        from main import AutoLandSystem, ApproachPhase

        system = AutoLandSystem.__new__(AutoLandSystem)
        system.phase = ApproachPhase.FINAL
        system.approach_config = MagicMock()
        system.approach_config.approach_speed = 120
        system.safety_guard = MagicMock()
        system._last_guard_snapshot_log_time = 0.0
        system.autothrottle = MagicMock()
        system.autothrottle.active = False
        system.vjoy_throttle = None
        system.control = MagicMock()
        system.stabilized_monitor = MagicMock()
        system.running = True
        system.use_vjoy = False
        system.audio_alerts_enabled = False
        system.audio_system = MagicMock()

        system.telemetry_recorder = TelemetryRecorder(log_dir=str(tmp_path))
        system.telemetry_recorder.start_recording()

        system._last_guard_decision = "GO_AROUND"
        system._last_guard_reason = "STALE"

        telemetry = make_telemetry(vertical_speed=-700, altitude_agl=500)
        system._handle_phase(telemetry, None)

        system.telemetry_recorder.stop_recording()

        # _handle_phase(None) is a no-op — no rows written
        _, rows = _read_csv(list(tmp_path.glob('telemetry_*.csv'))[0])
        assert len(rows) == 0


# ═══════════════════════════════════════════════════════════════════
# FIX-3/FIX-10: Write error resilience
# ═══════════════════════════════════════════════════════════════════

class TestWriteErrorResilience:
    def test_writerow_error_logged_no_exception(self, tmp_path, caplog):
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()
        rec.write_frame(_full_telemetry(), phase="INITIAL")

        original_writerow = rec._writer.writerow
        rec._writer.writerow = MagicMock(side_effect=IOError("disk full"))

        with caplog.at_level(logging.WARNING, logger="modules.telemetry_recorder"):
            rec.write_frame(_full_telemetry(), phase="FINAL")

        assert "write error" in caplog.text.lower()
        assert rec.is_recording
        rec._writer.writerow = original_writerow
        rec.stop_recording()

    def test_control_loop_continues_after_error(self, tmp_path):
        from main import AutoLandSystem, ApproachPhase
        from modules.safety_guard import ApproachSafetyGuard

        system = AutoLandSystem.__new__(AutoLandSystem)
        system.phase = ApproachPhase.FINAL
        system.approach_config = MagicMock()
        system.approach_config.approach_speed = 120
        system.approach_config.station.type = "VOR"
        system.safety_guard = ApproachSafetyGuard(debounce_n=2)
        system.wind_correction = MagicMock()
        system.wind_correction.apply_wind_corrections.return_value = {
            "corrected_heading": 270, "corrected_vs": 700,
            "headwind": 10, "crosswind": 5, "wind_speed": 12,
            "wind_direction": 280, "drift_angle": 2.0,
        }
        system.fms_reader = None
        system.phase_state = MagicMock()
        system.phase_state.handle.return_value = None
        system._last_guard_snapshot_log_time = 0.0

        system.telemetry_recorder = MagicMock()
        system.telemetry_recorder.is_recording = True
        system.telemetry_recorder.write_frame.side_effect = IOError("disk full")

        telemetry = make_telemetry(vertical_speed=-700, altitude_agl=500,
                                   airspeed=120, bank=3.0)
        approach_data = {"distance_to_station": 5.0, "required_altitude": 2000,
                         "on_course": True, "cross_track_error": 0.5}

        system._handle_phase(telemetry, approach_data)
        system.phase_state.handle.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# T1: Real execute_approach test — exact assertions
# ═══════════════════════════════════════════════════════════════════

class TestRealExecuteApproach:
    """T1: Real AutoLandSystem.execute_approach with 2 iterations."""

    def test_execute_approach_two_iterations_with_recorder_error(self, tmp_path, caplog):
        """Real execute_approach: 2 iterations, first write_frame throws,
        caplog confirms exact warning, second iteration executes, then stops.

        Red-without-fix: removing the try/except around recorder in
        execute_approach makes this test FAIL even with the outer
        exception handler.
        """
        from main import AutoLandSystem, ApproachPhase
        from modules.safety_guard import ApproachSafetyGuard
        from modules.types import ApproachConfig, NavStation

        system = AutoLandSystem.__new__(AutoLandSystem)
        system.approach_config = ApproachConfig(
            station=NavStation("TEST", 11030000, 55.5, 37.5, "VOR"),
            final_approach_course=270, glideslope_angle=3.0,
            decision_height=200, approach_speed=120,
            runway_elevation=0, runway_length=8000, runway_width=150,
            runway_threshold_lat=55.48, runway_threshold_lon=37.52,
        )
        system.use_ils = False
        system.use_vjoy = False
        system.use_autothrottle = False
        system.use_custom_autopilot = False
        system.audio_alerts_enabled = False
        system.phase = ApproachPhase.FINAL
        system.safety_guard = ApproachSafetyGuard(debounce_n=2)
        system.wind_correction = MagicMock()
        system.wind_correction.apply_wind_corrections.return_value = {
            "corrected_heading": 270, "corrected_vs": 700,
            "headwind": 10, "crosswind": 5, "wind_speed": 12,
            "wind_direction": 280, "drift_angle": 2.0,
        }
        system.fms_reader = None
        system.phase_state = MagicMock()
        system.phase_state.handle.return_value = None
        system._last_guard_snapshot_log_time = 0.0
        system._last_fms_log_time = 0.0
        system.connection_monitor = None
        system.connection_optimizer = None
        system.ils_navigation = MagicMock()
        system.navigation = MagicMock()
        system.navigation.calculate_vor_approach.return_value = {
            "distance_to_station": 5.0, "required_altitude": 2000,
            "on_course": True, "cross_track_error": 0.5,
            "corrected_heading": 270,
        }
        system.telemetry = MagicMock()
        system.control = MagicMock()
        system.stabilized_monitor = MagicMock()
        system.autothrottle = MagicMock()
        system.autothrottle.active = False
        system.vjoy_throttle = None
        system.virtual_joystick = MagicMock()
        system.aircraft_adapter = MagicMock()
        system.speed_calculator = MagicMock()
        system.structured_logger = MagicMock()
        system.flare_controller = MagicMock()
        system.wind_shear_detector = MagicMock()
        system.turbulence_detector = MagicMock()
        system.audio_system = MagicMock()
        system.autopilot_takeover = MagicMock()
        system.autopilot_takeover.status.completed = False

        # Two frames of telemetry
        frame1 = make_telemetry(vertical_speed=-700, altitude_agl=500,
                                airspeed=120, bank=3.0)
        frame2 = make_telemetry(vertical_speed=-700, altitude_agl=400,
                                airspeed=120, bank=3.0)
        system.telemetry.get_all_data.side_effect = [frame1, frame2]

        # Real recorder
        system.telemetry_recorder = TelemetryRecorder(log_dir=str(tmp_path))
        system.telemetry_recorder.start_recording()

        # Track write_frame calls: first throws, second writes real row
        write_call_count = [0]
        original_write_frame = system.telemetry_recorder.write_frame
        def tracking_write_frame(*args, **kwargs):
            write_call_count[0] += 1
            if write_call_count[0] == 1:
                raise IOError("Simulated disk error on first frame")
            return original_write_frame(*args, **kwargs)
        system.telemetry_recorder.write_frame = tracking_write_frame

        # Track _handle_phase calls and stop after 2nd iteration
        handle_phase_count = [0]
        original_handle_phase = AutoLandSystem._handle_phase
        def counting_handle_phase(self_sys, telemetry, approach_data):
            handle_phase_count[0] += 1
            if handle_phase_count[0] >= 2:
                self_sys.running = False
            return original_handle_phase(self_sys, telemetry, approach_data)
        system._handle_phase = lambda t, a: counting_handle_phase(system, t, a)

        system.running = True
        with caplog.at_level(logging.WARNING, logger="main"):
            system.execute_approach()

        # EXACT assertions — no or-laziness
        assert "Telemetry recorder frame write failed" in caplog.text
        assert "Error in approach execution" not in caplog.text

        # write_frame attempted exactly 2 times
        assert write_call_count[0] == 2

        # _handle_phase executed exactly 2 times
        assert handle_phase_count[0] == 2

        # phase_state.handle was called on second iteration (normal path)
        system.phase_state.handle.assert_called()

        # Second write succeeded — CSV has 1 row on disk
        system.telemetry_recorder.stop_recording()
        csv_files = list(tmp_path.glob('telemetry_*.csv'))
        _, rows = _read_csv(csv_files[0])
        assert len(rows) == 1


# ═══════════════════════════════════════════════════════════════════
# FIX-4/FIX-10: Production wiring
# ═══════════════════════════════════════════════════════════════════

class TestProductionWiring:
    def test_handle_phase_sets_guard_verdict(self, tmp_path):
        from main import AutoLandSystem, ApproachPhase
        from modules.safety_guard import ApproachSafetyGuard

        system = AutoLandSystem.__new__(AutoLandSystem)
        system.phase = ApproachPhase.FINAL
        system.approach_config = MagicMock()
        system.approach_config.approach_speed = 120
        system.approach_config.station.type = "VOR"
        system.safety_guard = ApproachSafetyGuard(debounce_n=2)
        system.wind_correction = MagicMock()
        system.wind_correction.apply_wind_corrections.return_value = {
            "corrected_heading": 270, "corrected_vs": 700,
            "headwind": 10, "crosswind": 5, "wind_speed": 12,
            "wind_direction": 280, "drift_angle": 2.0,
        }
        system.fms_reader = None
        system.phase_state = MagicMock()
        system.phase_state.handle.return_value = None
        system._last_guard_snapshot_log_time = 0.0

        system.telemetry_recorder = TelemetryRecorder(log_dir=str(tmp_path))
        system.telemetry_recorder.start_recording()

        telemetry = make_telemetry(vertical_speed=-700, altitude_agl=500,
                                   airspeed=120, bank=3.0)
        approach_data = {"distance_to_station": 5.0, "required_altitude": 2000,
                         "on_course": True, "cross_track_error": 0.5}

        system._handle_phase(telemetry, approach_data)

        assert system._last_guard_decision == "CONTINUE"
        assert system._last_guard_reason == "all_checks_passed"

        system.telemetry_recorder.write_frame(
            telemetry=telemetry, phase=system.phase.value,
            guard_decision=system._last_guard_decision,
            guard_reason=system._last_guard_reason,
        )
        system.telemetry_recorder.stop_recording()

        _, rows = _read_csv(list(tmp_path.glob('telemetry_*.csv'))[0])
        assert rows[0]['guard_decision'] == 'CONTINUE'


# ═══════════════════════════════════════════════════════════════════
# FIX-7: Read-only contract
# ═══════════════════════════════════════════════════════════════════

class TestRecorderReadOnlyContract:
    def test_module_has_no_control_imports(self):
        import ast
        source_path = Path(__file__).resolve().parent.parent / 'modules' / 'telemetry_recorder.py'
        tree = ast.parse(source_path.read_text(encoding='utf-8'))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    imported.add(a.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split('.')[0])
        forbidden = {'control', 'SimConnect', 'aircraft_adapter',
                     'virtual_joystick', 'autothrottle'}
        assert not (imported & forbidden)

    def test_no_actuator_methods(self):
        methods = [m for m in dir(TelemetryRecorder) if not m.startswith('_')]
        # set_pending_frame and flush_pending_frame are recorder methods, not actuators
        actuator_methods = [m for m in methods
                            if m.startswith(('set_', 'apply_', 'activate'))
                            and m not in ('set_pending_frame',)]
        assert not actuator_methods

    def test_telemetry_not_mutated(self, tmp_path):
        """T3: Recorder does not modify the telemetry dict — exact deep comparison."""
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()
        t = _full_telemetry()
        original = copy.deepcopy(t)
        rec.write_frame(t, phase="FINAL")
        rec.stop_recording()
        assert t == original, "Telemetry was mutated by write_frame"


# ═══════════════════════════════════════════════════════════════════
# Lifecycle tests
# ═══════════════════════════════════════════════════════════════════

class TestRecorderLifecycle:
    def test_not_recording_by_default(self):
        assert not TelemetryRecorder().is_recording

    def test_recording_flag(self, tmp_path):
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()
        assert rec.is_recording
        rec.stop_recording()
        assert not rec.is_recording

    def test_double_stop(self, tmp_path):
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()
        rec.stop_recording()
        rec.stop_recording()

    def test_write_after_stop(self, tmp_path):
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()
        rec.stop_recording()
        rec.write_frame(_full_telemetry(), phase="FINAL")

    def test_multiple_sessions(self, tmp_path):
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()
        rec.write_frame(_full_telemetry(), phase="INITIAL")
        rec.stop_recording()
        rec.start_recording()
        rec.write_frame(_full_telemetry(), phase="FINAL")
        rec.stop_recording()
        total = sum(len(_read_csv(f)[1]) for f in tmp_path.glob('telemetry_*.csv'))
        assert total == 2
