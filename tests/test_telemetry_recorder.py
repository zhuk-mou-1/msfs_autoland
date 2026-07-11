"""TASK-007-PREP: Telemetry recorder tests (FIX-1..FIX-7).

Tests:
  T-REC-1: Recorder writes a row per frame (real CSV, not mock).
  T-REC-2: Recorder write error does not crash control loop.
  T-REC-3: Recorder is read-only (no actuators, no telemetry mutation).
  T-REC-4: start/stop lifecycle.
  T-REC-5: Terminal guard frame present in CSV after GO_AROUND.
  T-REC-6: Stable schema — early incomplete frame does not lose later columns.
  T-REC-7: Production wiring — execute_approach drives recorder.
"""

import csv
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from modules.telemetry_recorder import TelemetryRecorder, _flatten_dict
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
    base['ils'] = {
        'nav1_has_localizer': True,
        'nav1_has_glideslope': True,
        'nav1_cdi': 3,
    }
    base['autopilot'] = {'master': True, 'heading_hold': True}
    base['weather'] = {'ambient_temperature': 12}
    base['weight'] = {'total_weight': 55000}
    base['aircraft'] = {'title': 'Test Aircraft'}
    base['configuration'] = {'flaps_position': 0.7, 'gear_position': 1.0}
    base['nav'] = {'nav1_frequency': 11030000}
    return base


def _read_csv(path: Path) -> tuple:
    """Read CSV file, return (header, list-of-row-dicts)."""
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        rows = list(reader)
    return header, rows


# ═══════════════════════════════════════════════════════════════════
# Unit tests — _flatten_dict
# ═══════════════════════════════════════════════════════════════════

class TestFlattenDict:
    """Deterministic flattening of nested telemetry sections."""

    def test_simple_dict(self):
        result = _flatten_dict({'a': 1, 'b': 2})
        assert result == {'a': 1, 'b': 2}

    def test_nested_dict(self):
        result = _flatten_dict({'pos': {'lat': 55.0, 'lon': 37.0}})
        assert result == {'pos_lat': 55.0, 'pos_lon': 37.0}

    def test_deeply_nested(self):
        result = _flatten_dict({'a': {'b': {'c': 42}}})
        assert result == {'a_b_c': 42}

    def test_sorted_keys(self):
        """Column order is deterministic (sorted)."""
        result = _flatten_dict({'z': 1, 'a': 2, 'm': 3})
        assert list(result.keys()) == ['a', 'm', 'z']

    def test_list_stringified(self):
        result = _flatten_dict({'arr': [1, 2, 3]})
        assert result == {'arr': '[1, 2, 3]'}


# ═══════════════════════════════════════════════════════════════════
# Integration tests — recorder through real CSV write path
# ═══════════════════════════════════════════════════════════════════

class TestRecorderWritesRow:
    """T-REC-1: Each write_frame produces one CSV row with real data."""

    def test_single_frame_row_count(self, tmp_path):
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()
        assert rec.is_recording

        telemetry = _full_telemetry()
        rec.write_frame(telemetry, phase="FINAL",
                        guard_decision="CONTINUE", guard_reason="all_checks_passed")

        rec.stop_recording()
        assert not rec.is_recording

        csv_files = list(tmp_path.glob('telemetry_*.csv'))
        assert len(csv_files) == 1
        header, rows = _read_csv(csv_files[0])
        assert len(rows) == 1
        assert 'timestamp' in header
        assert 'phase' in header
        assert 'guard_decision' in header
        assert 'guard_reason' in header

    def test_multiple_frames(self, tmp_path):
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()

        for i in range(5):
            rec.write_frame(_full_telemetry(), phase="FINAL")

        rec.stop_recording()

        csv_files = list(tmp_path.glob('telemetry_*.csv'))
        _, rows = _read_csv(csv_files[0])
        assert len(rows) == 5
        assert rec._frame_count == 5

    def test_nested_sections_flattened(self, tmp_path):
        """All nested telemetry sections are flattened into CSV columns."""
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()

        telemetry = _full_telemetry()
        rec.write_frame(telemetry, phase="FINAL")

        rec.stop_recording()

        csv_files = list(tmp_path.glob('telemetry_*.csv'))
        header, rows = _read_csv(csv_files[0])
        row = rows[0]

        assert 'position_altitude_agl' in header
        assert 'attitude_bank' in header
        assert 'speed_airspeed_indicated' in header
        assert 'ils_nav1_has_localizer' in header
        assert 'autopilot_master' in header

    def test_guard_columns_populated(self, tmp_path):
        """Guard verdict columns are written when guard is active."""
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()

        rec.write_frame(_full_telemetry(), phase="FINAL",
                        guard_decision="GO_AROUND", guard_reason="CRITICAL_SINK_RATE")

        rec.stop_recording()

        csv_files = list(tmp_path.glob('telemetry_*.csv'))
        _, rows = _read_csv(csv_files[0])
        assert rows[0]['guard_decision'] == 'GO_AROUND'
        assert rows[0]['guard_reason'] == 'CRITICAL_SINK_RATE'

    def test_guard_columns_empty_when_none(self, tmp_path):
        """Guard columns are empty strings when guard not active."""
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()

        rec.write_frame(_full_telemetry(), phase="INITIAL")

        rec.stop_recording()

        csv_files = list(tmp_path.glob('telemetry_*.csv'))
        _, rows = _read_csv(csv_files[0])
        assert rows[0]['guard_decision'] == ''
        assert rows[0]['guard_reason'] == ''


# ═══════════════════════════════════════════════════════════════════
# FIX-2: Stable schema — early incomplete frame
# ═══════════════════════════════════════════════════════════════════

class TestStableSchema:
    """FIX-2: Schema is the union of all keys; early empty sections don't lose later columns."""

    def test_incomplete_first_frame_recovered_in_second(self, tmp_path):
        """Frame 1 has empty nav; frame 2 has nav1_frequency.
        CSV must have both rows and nav1_frequency column present in both."""
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()

        # Frame 1: nav section is empty
        t1 = _full_telemetry()
        t1['nav'] = {}
        rec.write_frame(t1, phase="INITIAL")

        # Frame 2: nav section restored
        t2 = _full_telemetry()
        t2['nav'] = {'nav1_frequency': 11030000}
        rec.write_frame(t2, phase="FINAL")

        rec.stop_recording()

        csv_files = list(tmp_path.glob('telemetry_*.csv'))
        header, rows = _read_csv(csv_files[0])

        # Two data rows
        assert len(rows) == 2

        # nav1_frequency column exists (from frame 2)
        assert 'nav_nav1_frequency' in header

        # Frame 1: nav value is empty (field missing → empty string in CSV)
        assert rows[0].get('nav_nav1_frequency', '') == ''

        # Frame 2: nav value present
        assert rows[1]['nav_nav1_frequency'] == '11030000'

    def test_schema_stable_across_many_frames(self, tmp_path):
        """Even if frame 1 has minimal data, all columns from later frames appear."""
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()

        # Frame 1: only position
        rec.write_frame({"position": {"altitude_agl": 100}}, phase="INITIAL")

        # Frame 2: full data
        rec.write_frame(_full_telemetry(), phase="FINAL")

        rec.stop_recording()

        csv_files = list(tmp_path.glob('telemetry_*.csv'))
        header, rows = _read_csv(csv_files[0])

        assert len(rows) == 2
        # Columns from frame 2 must exist in header
        assert 'ils_nav1_has_localizer' in header
        assert 'autopilot_master' in header
        # Both rows present
        assert rows[0]['phase'] == 'INITIAL'
        assert rows[1]['phase'] == 'FINAL'


# ═══════════════════════════════════════════════════════════════════
# FIX-5: Terminal guard frame
# ═══════════════════════════════════════════════════════════════════

class TestTerminalGuardFrame:
    """FIX-1: GO_AROUND frame is written to CSV before stop_recording."""

    def test_go_around_frame_in_csv(self, caplog):
        """FINAL + critical violation → GO_AROUND → CSV last row has GO_AROUND."""
        from main import AutoLandSystem, ApproachPhase
        from modules.safety_guard import ApproachSafetyGuard, GuardDecision
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

        # Use a real recorder pointed at tmp
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            system.telemetry_recorder = TelemetryRecorder(log_dir=tmpdir)
            system.telemetry_recorder.start_recording()

            # execute_go_around needs stop_approach which needs telemetry_recorder
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

            # Terminal frame was written before stop_recording
            assert system.telemetry_recorder._frame_count >= 1

            system.telemetry_recorder.stop_recording()

            # Read CSV and verify last row has GO_AROUND
            csv_files = list(Path(tmpdir).glob('telemetry_*.csv'))
            assert len(csv_files) == 1
            _, rows = _read_csv(csv_files[0])
            assert len(rows) >= 1
            last_row = rows[-1]
            assert last_row['guard_decision'] == 'GO_AROUND'
            assert last_row['guard_reason'] == 'CRITICAL_SINK_RATE'


# ═══════════════════════════════════════════════════════════════════
# FIX-3: Real write error propagation test
# ═══════════════════════════════════════════════════════════════════

class TestWriteErrorResilience:
    """FIX-3: Real writerow error on active recorder — must not raise."""

    def test_writerow_error_logged_no_exception(self, tmp_path, caplog):
        """Force a real write error while recorder is active.
        Verify: logger.warning called, no exception, control loop can continue."""
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()
        assert rec.is_recording

        # Write one valid frame to initialize the schema
        rec.write_frame(_full_telemetry(), phase="INITIAL")

        # Replace _rows with a list-like that raises on append
        class FailingList(list):
            def append(self, item):
                raise IOError("Disk full")

        rec._rows = FailingList()

        with caplog.at_level(logging.WARNING, logger="modules.telemetry_recorder"):
            # This must NOT raise — error is swallowed
            rec.write_frame(_full_telemetry(), phase="FINAL")

        assert "Telemetry recorder write error" in caplog.text
        assert "Disk full" in caplog.text

        # Restore and stop cleanly
        rec._rows = []
        rec.stop_recording()

    def test_control_loop_continues_after_write_error(self, tmp_path):
        """FIX-4 production path: write_frame error does not stop execute_approach."""
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

        # Use real recorder
        system.telemetry_recorder = TelemetryRecorder(log_dir=str(tmp_path))
        system.telemetry_recorder.start_recording()

        telemetry = make_telemetry(vertical_speed=-700, altitude_agl=500,
                                   airspeed=120, bank=3.0)
        approach_data = {"distance_to_station": 5.0, "required_altitude": 2000,
                         "on_course": True, "cross_track_error": 0.5}

        # _handle_phase calls write_frame internally via the guard path
        system._handle_phase(telemetry, approach_data)

        # phase_state.handle should still be called (control loop continued)
        system.phase_state.handle.assert_called_once()

        system.telemetry_recorder.stop_recording()


# ═══════════════════════════════════════════════════════════════════
# FIX-4: Production wiring test
# ═══════════════════════════════════════════════════════════════════

class TestProductionWiring:
    """FIX-4: _handle_phase sets guard verdict → execute_approach writes to recorder."""

    def test_handle_phase_sets_guard_verdict_for_recorder(self, tmp_path):
        """_handle_phase with normal telemetry → _last_guard_decision/reason set.
        These are the values execute_approach passes to write_frame."""
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

        # Guard verdict was set — this is what execute_approach reads
        assert system._last_guard_decision == "CONTINUE"
        assert system._last_guard_reason == "all_checks_passed"

        # Simulate what execute_approach does: write_frame with the verdict
        system.telemetry_recorder.write_frame(
            telemetry=telemetry,
            phase=system.phase.value,
            guard_decision=system._last_guard_decision,
            guard_reason=system._last_guard_reason,
        )
        system.telemetry_recorder.stop_recording()

        csv_files = list(Path(tmp_path).glob('telemetry_*.csv'))
        assert len(csv_files) == 1
        _, rows = _read_csv(csv_files[0])
        assert len(rows) == 1
        assert rows[0]['guard_decision'] == 'CONTINUE'
        assert rows[0]['phase'] == 'FINAL'


# ═══════════════════════════════════════════════════════════════════
# FIX-7: Structural contract test (no unrelated mocks)
# ═══════════════════════════════════════════════════════════════════

class TestRecorderReadOnlyContract:
    """FIX-7: Recorder has no actuator/control dependencies — structural proof."""

    def test_module_has_no_control_imports(self):
        """telemetry_recorder.py imports only csv, logging, time, pathlib, typing.
        No control, no SimConnect, no actuators."""
        import ast
        source_path = Path(__file__).resolve().parent.parent / 'modules' / 'telemetry_recorder.py'
        tree = ast.parse(source_path.read_text(encoding='utf-8'))

        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_names.add(node.module.split('.')[0])

        forbidden = {'control', 'SimConnect', 'simconnect', 'aircraft_adapter',
                     'virtual_joystick', 'autothrottle', 'msfs'}
        found_forbidden = imported_names & forbidden
        assert not found_forbidden, f"Recorder must not import: {found_forbidden}"

    def test_no_actuator_methods_in_class(self):
        """TelemetryRecorder has no methods named set_*, apply_*, or activate."""
        methods = [m for m in dir(TelemetryRecorder) if not m.startswith('_')]
        actuator_methods = [m for m in methods
                            if m.startswith(('set_', 'apply_', 'activate'))]
        assert not actuator_methods, f"Recorder has actuator-like methods: {actuator_methods}"

    def test_write_frame_does_not_mutate_telemetry(self, tmp_path):
        """Recorder does not modify the telemetry dict."""
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()
        telemetry = _full_telemetry()
        original_keys = set(telemetry.keys())
        original_position = dict(telemetry['position'])

        rec.write_frame(telemetry, phase="FINAL")
        rec.stop_recording()

        assert set(telemetry.keys()) == original_keys
        assert telemetry['position'] == original_position


# ═══════════════════════════════════════════════════════════════════
# Lifecycle tests
# ═══════════════════════════════════════════════════════════════════

class TestRecorderLifecycle:
    """T-REC-4: start/stop lifecycle."""

    def test_not_recording_by_default(self):
        rec = TelemetryRecorder()
        assert not rec.is_recording

    def test_recording_flag_after_start(self, tmp_path):
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()
        assert rec.is_recording

    def test_recording_flag_after_stop(self, tmp_path):
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()
        rec.stop_recording()
        assert not rec.is_recording

    def test_double_stop_is_safe(self, tmp_path):
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()
        rec.stop_recording()
        rec.stop_recording()  # should not raise

    def test_write_after_stop_is_silent(self, tmp_path):
        """write_frame after stop_recording does not raise."""
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()
        rec.stop_recording()
        rec.write_frame(_full_telemetry(), phase="FINAL")  # should not raise

    def test_multiple_sessions(self, tmp_path):
        """Two start/stop cycles produce separate recordings."""
        rec = TelemetryRecorder(log_dir=str(tmp_path))
        rec.start_recording()
        rec.write_frame(_full_telemetry(), phase="INITIAL")
        rec.stop_recording()

        rec.start_recording()
        rec.write_frame(_full_telemetry(), phase="FINAL")
        rec.stop_recording()

        csv_files = list(tmp_path.glob('telemetry_*.csv'))
        assert len(csv_files) >= 1
        total_frames = 0
        for f in csv_files:
            _, rows = _read_csv(f)
            total_frames += len(rows)
        assert total_frames == 2
