"""CSV telemetry recorder — read-only, never breaks the control loop.

Records every execute_approach frame (2 Hz) to a CSV file for offline analysis.
File opens at start_approach, closes at stop_approach. Any I/O error is
swallowed with a warning; the flight continues.

Schema: all rows are buffered in memory. Header is written at stop_recording
with the union of all keys across all frames — no dynamic schema drift.
"""

import csv
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _flatten_dict(d: dict, parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
    """Deterministically flatten nested dict into flat key-value pairs.

    Keys: section_subkey (e.g. position_altitude_agl, attitude_bank).
    Non-dict scalars are kept as-is; dicts are recursed.
    Lists/tuples are stringified (shouldn't appear in telemetry).
    """
    items: list = []
    for k, v in sorted(d.items()):  # sorted for deterministic column order
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep).items())
        elif isinstance(v, (list, tuple)):
            items.append((new_key, str(v)))
        else:
            items.append((new_key, v))
    return dict(items)


class TelemetryRecorder:
    """Append-only CSV recorder. Strictly read-only — no actuators, no telemetry writes.

    Rows are buffered in memory during recording. On stop_recording, the full
    schema (union of all keys) is computed and written as CSV header + all rows.
    This guarantees no columns are lost when early frames have incomplete data.
    """

    _session_counter: int = 0  # monotonic per-process counter for unique filenames

    def __init__(self, log_dir: str = 'logs') -> None:
        self._log_dir = Path(log_dir)
        self._file = None
        self._rows: List[Dict[str, Any]] = []
        self._all_keys: set = set()
        self._frame_count: int = 0

    @property
    def is_recording(self) -> bool:
        return self._file is not None and not self._file.closed

    def start_recording(self) -> None:
        """Open a new CSV file for this approach session."""
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            TelemetryRecorder._session_counter += 1
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            filepath = self._log_dir / f'telemetry_{timestamp}_{TelemetryRecorder._session_counter}.csv'
            self._file = open(filepath, 'w', newline='', encoding='utf-8')
            self._rows = []
            self._all_keys = set()
            self._frame_count = 0
            self._filepath = filepath
            logger.info("Telemetry recorder started: %s", filepath)
        except OSError as e:
            logger.warning("Telemetry recorder failed to open file: %s", e)
            self._file = None

    def stop_recording(self) -> None:
        """Flush buffered rows to CSV and close the file.

        Header is the sorted union of all keys seen across all frames.
        """
        try:
            if self._file and not self._file.closed:
                # Write header + all buffered rows
                if self._rows:
                    fieldnames = sorted(self._all_keys)
                    writer = csv.DictWriter(self._file, fieldnames=fieldnames,
                                            extrasaction='ignore')
                    writer.writeheader()
                    for row in self._rows:
                        writer.writerow(row)
                self._file.close()
                logger.info("Telemetry recorder stopped (%d frames written)",
                            self._frame_count)
        except OSError as e:
            logger.warning("Telemetry recorder close error: %s", e)
        finally:
            self._file = None
            self._rows = []
            self._all_keys = set()

    def write_frame(
        self,
        telemetry: dict,
        phase: str,
        guard_decision: Optional[str] = None,
        guard_reason: Optional[str] = None,
    ) -> None:
        """Buffer one telemetry frame. Never raises — errors are swallowed.

        Args:
            telemetry: Full get_all_data() dict (nested sections).
            phase: Current approach phase name (e.g. "FINAL").
            guard_decision: Guard verdict string if guard was active this frame.
            guard_reason: Guard reason code if guard was active this frame.
        """
        if not self.is_recording:
            return

        try:
            row: Dict[str, Any] = {}
            row['timestamp'] = time.time()
            row['phase'] = phase

            # Flatten all nested telemetry sections deterministically
            for section_name in sorted(telemetry.keys()):
                section = telemetry[section_name]
                if isinstance(section, dict):
                    flat = _flatten_dict(section, parent_key=section_name)
                    row.update(flat)
                else:
                    row[section_name] = section

            # Guard verdict columns
            row['guard_decision'] = guard_decision if guard_decision is not None else ''
            row['guard_reason'] = guard_reason if guard_reason is not None else ''

            # Track all keys for stable schema
            self._all_keys.update(row.keys())
            self._rows.append(row)
            self._frame_count += 1
        except Exception as e:
            # Swallow ALL errors — recorder must never break the control loop
            logger.warning("Telemetry recorder write error: %s", e)
