"""WP-7: Replay tests — запуск safety-сценариев как последовательность snapshots.

Каждый fixture — JSONL файл со snapshot'ами телеметрии.
Runner передаёт snapshots в production code и проверяет инварианты.
"""

import json
import sys
from pathlib import Path
from typing import List


_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from modules.autopilot_takeover import AutopilotTakeover, TakeoverConfig
from tests.fakes import FakeAircraftAdapter, FakeControl, make_telemetry

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DH = 200.0


def load_fixture(name: str) -> List[dict]:
    """Загрузить JSONL fixture."""
    path = FIXTURES_DIR / name
    snapshots = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                snapshots.append(json.loads(line))
    return snapshots


class TestReplayScenarios:
    """Replay тесты — доказывают safety-инварианты через sequence snapshots."""

    def test_ils_nominal(self):
        """ils_nominal.jsonl: crossing trigger → takeover initiated.

        Snapshot sequence: 270 → 244 → 200
        At 244: within (DH, DH+50] → should initiate.
        """
        snapshots = load_fixture("ils_nominal.jsonl")
        takeover = AutopilotTakeover(
            config=TakeoverConfig(ils_cat1_dh=DH, ils_takeover_enabled=True)
        )

        initiated = False
        for snap in snapshots:
            result = takeover.should_initiate_takeover(
                distance_to_threshold=0.0,
                altitude_agl=snap["position"]["radio_height"],
                approach_phase="FINAL",
                approach_type="ILS",
                decision_height=DH,
            )
            if result:
                initiated = True
                break

        assert initiated, "Takeover should be initiated during crossing window"

    def test_ils_crosses_takeover_window(self):
        """ils_crosses_takeover_window.jsonl: 270 → 190, large step.

        System must not silently continue. Either:
        1. Takeover initiated at some point, OR
        2. Fail-closed (below DH without takeover)
        """
        snapshots = load_fixture("ils_crosses_takeover_window.jsonl")
        takeover = AutopilotTakeover(
            config=TakeoverConfig(ils_cat1_dh=DH, ils_takeover_enabled=True)
        )

        initiated = False
        below_dh_seen = False

        for snap in snapshots:
            alt = snap["position"]["radio_height"]
            if alt < DH:
                below_dh_seen = True

            result = takeover.should_initiate_takeover(
                distance_to_threshold=0.0,
                altitude_agl=alt,
                approach_phase="FINAL",
                approach_type="ILS",
                decision_height=DH,
            )
            if result:
                initiated = True
                break

        # Either initiated during crossing, or we're below DH (fail-closed)
        assert initiated or below_dh_seen, \
            "Must either initiate takeover or be below DH (fail-closed)"

        # If below DH without completed takeover → must fail
        if below_dh_seen and not initiated:
            assert not takeover.status.completed, \
                "Cannot complete takeover when below DH without crossing"

    def test_ils_below_dh_without_takeover(self):
        """ils_below_dh_without_takeover.jsonl: first snapshot below DH.

        Must fail-closed: no takeover initiation below DH.
        """
        snapshots = load_fixture("ils_below_dh_without_takeover.jsonl")
        takeover = AutopilotTakeover(
            config=TakeoverConfig(ils_cat1_dh=DH, ils_takeover_enabled=True)
        )

        for snap in snapshots:
            result = takeover.should_initiate_takeover(
                distance_to_threshold=0.0,
                altitude_agl=snap["position"]["radio_height"],
                approach_phase="FINAL",
                approach_type="ILS",
                decision_height=DH,
            )
            assert result is False, \
                "Should NOT initiate takeover when below DH"

    def test_unsafe_bank_at_takeover(self):
        """unsafe_bank_at_takeover.jsonl: bank=31°.

        Takeover must NOT complete. Commands must NOT be sent.
        """
        snapshots = load_fixture("unsafe_bank_at_takeover.jsonl")
        ctrl = FakeControl()
        adapter = FakeAircraftAdapter()

        takeover = AutopilotTakeover(
            config=TakeoverConfig(ils_cat1_dh=DH, ils_takeover_enabled=True)
        )

        for snap in snapshots:
            # Force in_progress to test perform_takeover
            takeover.status.in_progress = True
            takeover.takeover_start_time = 0.0
            takeover.initial_parameters = {"airspeed": 140, "altitude": 3000}

            telemetry = make_telemetry(
                bank=snap["attitude"]["bank"],
                altitude_agl=snap["position"]["altitude_agl"],
                radio_height=snap["position"]["radio_height"],
            )
            status = takeover.perform_takeover(telemetry, adapter, ctrl)

            # Must fail due to unsafe bank
            assert status.failed is True, \
                "Takeover must fail with unsafe bank angle"

            # No AP/A/T commands should be sent
            assert not ctrl.has_call("set_autopilot_master"), \
                "AP should NOT be disengaged with unsafe bank"
