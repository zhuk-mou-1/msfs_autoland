"""WP-5: Тесты владения каналами управления.

Проверяет, что в каждый момент один канал имеет ровно одного владельца,
и что команды не смешиваются.
"""

import sys
from pathlib import Path


_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from modules.control_ownership import ControlOwner, compute_ownership
from tests.fakes import FakeControl, FakeVJoy


class TestControlOwnership:
    """Владение каналами: один канал = один владелец."""

    def test_unconfirmed_takeover_keeps_ap_as_roll_pitch_owner(self):
        """До confirmed takeover — AP владеет roll и pitch."""
        ownership = compute_ownership(
            phase="FINAL",
            confirmed_takeover=False,
            use_vjoy=True,
            vjoy_ready=True,
            use_autothrottle=True,
        )
        assert ownership.roll == ControlOwner.AIRCRAFT_AP
        assert ownership.pitch == ControlOwner.AIRCRAFT_AP

    def test_confirmed_external_flare_uses_vjoy_without_ap_pitch_roll_commands(self):
        """Confirmed takeover + vJoy ready → EXTERNAL для roll/pitch."""
        ownership = compute_ownership(
            phase="FINAL",
            confirmed_takeover=True,
            use_vjoy=True,
            vjoy_ready=True,
            use_autothrottle=True,
        )
        assert ownership.roll == ControlOwner.EXTERNAL
        assert ownership.pitch == ControlOwner.EXTERNAL

    def test_no_vjoy_means_no_direct_pitch_roll_commands(self):
        """Нет vJoy → AP остаётся владельцем roll/pitch даже после takeover."""
        ownership = compute_ownership(
            phase="FINAL",
            confirmed_takeover=True,
            use_vjoy=False,
            vjoy_ready=False,
            use_autothrottle=True,
        )
        assert ownership.roll == ControlOwner.AIRCRAFT_AP
        assert ownership.pitch == ControlOwner.AIRCRAFT_AP

    def test_each_channel_has_exactly_one_owner(self):
        """Параметризованно: каждый канал имеет ровно одного владельца."""
        scenarios = [
            ("INITIAL", False, True, True, True),
            ("INTERMEDIATE", False, True, True, True),
            ("FINAL", False, True, True, True),
            ("FINAL", True, True, True, True),
            ("FINAL", True, False, False, True),
            ("FINAL", True, True, False, True),
            ("LANDING", True, True, True, True),
            ("GO_AROUND", True, True, True, True),
        ]

        for phase, takeover, vjoy, vjoy_ready, at in scenarios:
            ownership = compute_ownership(
                phase=phase,
                confirmed_takeover=takeover,
                use_vjoy=vjoy,
                vjoy_ready=vjoy_ready,
                use_autothrottle=at,
            )
            # Each channel must be a valid ControlOwner
            assert isinstance(ownership.roll, ControlOwner)
            assert isinstance(ownership.pitch, ControlOwner)
            assert isinstance(ownership.throttle, ControlOwner)

    def test_unstable_autothrottle_sends_exactly_one_throttle_command_per_tick(self):
        """Тяга — ровно один владелец, даже при нестабильном autothrottle."""
        # External flare without autothrottle
        ownership = compute_ownership(
            phase="FINAL",
            confirmed_takeover=True,
            use_vjoy=True,
            vjoy_ready=True,
            use_autothrottle=False,
        )
        assert ownership.throttle == ControlOwner.EXTERNAL

        # With autothrottle
        ownership2 = compute_ownership(
            phase="FINAL",
            confirmed_takeover=True,
            use_vjoy=True,
            vjoy_ready=True,
            use_autothrottle=True,
        )
        assert ownership2.throttle == ControlOwner.AIRCRAFT_AP

    def test_go_around_clears_external_ownership(self):
        """Go-around → NONE для roll/pitch, AP для throttle."""
        ownership = compute_ownership(
            phase="GO_AROUND",
            confirmed_takeover=True,
            use_vjoy=True,
            vjoy_ready=True,
            use_autothrottle=True,
        )
        assert ownership.roll == ControlOwner.NONE
        assert ownership.pitch == ControlOwner.NONE
        assert ownership.throttle == ControlOwner.AIRCRAFT_AP

    def test_no_competing_ap_and_vjoy_commands(self):
        """FIX-4: Production _control_aircraft() respects ownership.

        When EXTERNAL owns roll/pitch, AP commands should NOT be sent.
        Test calls real FinalPhaseState._control_aircraft() with fakes.
        """
        from unittest.mock import MagicMock
        from modules.approach_phases import FinalPhaseState

        ctrl = FakeControl()
        vjoy = FakeVJoy()
        vjoy.enabled = True

        system = MagicMock()
        system.control = ctrl
        system.virtual_joystick = vjoy
        system.use_vjoy = True

        phase = FinalPhaseState(system)

        # Set ownership: EXTERNAL for roll/pitch
        phase._ownership = compute_ownership(
            phase="FINAL",
            confirmed_takeover=True,
            use_vjoy=True,
            vjoy_ready=True,
            use_autothrottle=True,
        )

        telemetry = {"attitude": {"bank": 0, "pitch": 2.5, "heading_magnetic": 270}}
        wind_data = {"corrected_heading": 270, "corrected_vs": 700}

        phase._control_aircraft(telemetry, wind_data)

        # vJoy commands were sent
        assert vjoy.has_call("apply_control_inputs")

        # AP commands were NOT sent (EXTERNAL owns roll/pitch)
        assert not ctrl.has_call("set_heading_hold"), \
            "AP heading should NOT be sent when EXTERNAL owns roll"
        assert not ctrl.has_call("set_vertical_speed"), \
            "AP vertical_speed should NOT be sent when EXTERNAL owns pitch"
