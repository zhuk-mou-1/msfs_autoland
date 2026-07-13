"""WP-2 + WP-3: Тесты безопасности takeover.

WP-2: Hard safety gates — провал проверки блокирует команды.
WP-3: Readback-verified takeover — управление требует подтверждения.
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock


_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from modules.autopilot_takeover import AutopilotTakeover, TakeoverConfig
from tests.fakes import FakeAircraftAdapter, FakeControl, make_telemetry


# ═══════════════════════════════════════════════════════════════════
# WP-2: Hard safety gates
# ═══════════════════════════════════════════════════════════════════

class TestHardSafetyGates:
    """Провал hard safety check НЕ может отключить AP/A/T."""

    def test_unsafe_bank_blocks_takeover_without_commands(self):
        """bank=31° → failed, никаких команд на AP/A/T."""
        ctrl = FakeControl()
        adapter = FakeAircraftAdapter()
        takeover = AutopilotTakeover()

        # Инициируем takeover
        takeover.status.in_progress = True
        takeover.takeover_start_time = time.monotonic()
        takeover.initial_parameters = {"airspeed": 140, "altitude": 3000}

        telemetry = make_telemetry(bank=31.0, altitude_agl=2500)
        status = takeover.perform_takeover(telemetry, adapter, ctrl)

        assert status.failed is True
        assert "unsafe" in status.error_message.lower() or "attitude" in status.error_message.lower()

        # Никаких команд на отключение AP/A/T
        assert not ctrl.has_call("set_autopilot_master"), \
            "AP should NOT be disengaged after unsafe bank"
        assert not adapter.has_call("disengage_autopilot"), \
            "Adapter disengage should NOT be called after unsafe bank"

    def test_on_ground_blocks_takeover_without_commands(self):
        """on_ground=True → failed, никаких команд."""
        ctrl = FakeControl()
        adapter = FakeAircraftAdapter()
        takeover = AutopilotTakeover()

        takeover.status.in_progress = True
        takeover.takeover_start_time = time.monotonic()
        takeover.initial_parameters = {"airspeed": 140, "altitude": 3000}

        telemetry = make_telemetry(on_ground=True, altitude_agl=0)
        status = takeover.perform_takeover(telemetry, adapter, ctrl)

        assert status.failed is True
        assert not ctrl.has_call("set_autopilot_master")

    def test_unstable_speed_waits_without_disengaging_ap(self):
        """Нестабильная скорость → in_progress/waiting, AP не отключается."""
        ctrl = FakeControl()
        adapter = FakeAircraftAdapter()
        config = TakeoverConfig(
            require_stable_speed=True,
            speed_tolerance=5.0,
        )
        takeover = AutopilotTakeover(config=config)

        takeover.status.in_progress = True
        takeover.takeover_start_time = time.monotonic()
        takeover.initial_parameters = {"airspeed": 140, "altitude": 3000}

        # Скорость отличается на 20 узлов — за пределами tolerance
        telemetry = make_telemetry(airspeed=160, altitude_agl=2500, bank=0)
        status = takeover.perform_takeover(telemetry, adapter, ctrl)

        # Не failed — это retryable
        assert status.failed is False
        assert status.in_progress is True

        # AP не отключался
        assert not ctrl.has_call("set_autopilot_master")

    def test_all_checks_pass_starts_command_sequence(self):
        """Все проверки пройдены → начинается отключение AP/A/T."""
        ctrl = FakeControl()
        adapter = FakeAircraftAdapter()
        takeover = AutopilotTakeover()

        takeover.status.in_progress = True
        takeover.takeover_start_time = time.monotonic()
        takeover.initial_parameters = {"airspeed": 140, "altitude": 3000}

        # Безопасный snapshot
        telemetry = make_telemetry(
            airspeed=140, altitude=3000, altitude_agl=2500, bank=0, pitch=2.5
        )
        status = takeover.perform_takeover(telemetry, adapter, ctrl)

        # AP/A/T commands were sent
        assert ctrl.has_call("set_autopilot_master") or \
               adapter.has_call("disengage_autopilot"), \
            "AP disengage command should be sent when all checks pass"

    def test_timeout_uses_monotonic_clock(self, clock):
        """Timeout использует time.monotonic, не time.time."""
        ctrl = FakeControl()
        adapter = FakeAircraftAdapter()
        config = TakeoverConfig(initialization_timeout=5.0)
        takeover = AutopilotTakeover(config=config, clock=clock)

        takeover.status.in_progress = True
        takeover.takeover_start_time = clock()
        takeover.initial_parameters = {"airspeed": 140, "altitude": 3000}

        # Продвигаем время за timeout
        clock.advance(10.0)

        telemetry = make_telemetry(bank=0, altitude_agl=2500)
        status = takeover.perform_takeover(telemetry, adapter, ctrl)

        assert status.failed is True
        assert "timeout" in status.error_message.lower()
        assert status.failure_reason == "timeout"

    def test_failure_reason_is_machine_checkable(self):
        """failure_reason — заполненная строка при failed, не пустая."""
        ctrl = FakeControl()
        adapter = FakeAircraftAdapter()
        takeover = AutopilotTakeover()

        takeover.status.in_progress = True
        takeover.takeover_start_time = time.monotonic()
        takeover.initial_parameters = {"airspeed": 140, "altitude": 3000}

        telemetry = make_telemetry(bank=35.0, altitude_agl=2500)
        status = takeover.perform_takeover(telemetry, adapter, ctrl)

        assert status.failed is True
        assert len(status.error_message) > 0, "error_message must describe the failure"


# ═══════════════════════════════════════════════════════════════════
# WP-3: Readback-verified takeover
# ═══════════════════════════════════════════════════════════════════

class TestReadbackVerifiedTakeover:
    """Takeover требует наблюдаемого подтверждения (readback)."""

    def test_sent_disengage_command_is_not_verified_takeover(self):
        """Отправка команды выключения AP ≠ подтверждённый takeover."""
        ctrl = FakeControl()
        ctrl.set_readback_ap(True)  # AP всё ещё включён по readback
        ctrl.set_readback_at(True)

        adapter = FakeAircraftAdapter()
        adapter._ap_state = True
        adapter._at_state = True

        takeover = AutopilotTakeover()
        takeover.status.in_progress = True
        takeover.takeover_start_time = time.monotonic()
        takeover.initial_parameters = {"airspeed": 140, "altitude": 3000}

        # Безопасный snapshot — все проверки пройдены
        telemetry = make_telemetry(bank=0, altitude_agl=2500, airspeed=140)
        status = takeover.perform_takeover(telemetry, adapter, ctrl)

        # Команды отправлены
        assert ctrl.has_call("set_autopilot_master") or \
               adapter.has_call("disengage_autopilot")

        # НО readback показывает AP включён → takeover НЕ verified
        assert status.autopilot_disengaged is False, \
            "autopilot_disengaged should be False when readback shows AP still on"
        assert status.completed is False
        assert status.controls_acquired is False

    def test_takeover_completes_only_after_readback_off(self):
        """Takeover завершается только когда readback подтверждает AP/A/T off."""
        ctrl = FakeControl()
        adapter = FakeAircraftAdapter()

        takeover = AutopilotTakeover()
        takeover.status.in_progress = True
        takeover.takeover_start_time = time.monotonic()
        takeover.initial_parameters = {"airspeed": 140, "altitude": 3000}

        # Tick 1: readback показывает AP/AT включены
        ctrl.set_readback_ap(True)
        ctrl.set_readback_at(True)
        adapter._ap_state = True
        adapter._at_state = True

        telemetry = make_telemetry(bank=0, altitude_agl=2500, airspeed=140)
        status1 = takeover.perform_takeover(telemetry, adapter, ctrl)
        assert status1.completed is False

        # Tick 2: readback показывает AP/AT выключены
        ctrl.set_readback_ap(False)
        ctrl.set_readback_at(False)
        adapter._ap_state = False
        adapter._at_state = False

        status2 = takeover.perform_takeover(telemetry, adapter, ctrl)
        assert status2.completed is True, \
            "Takeover should complete when readback confirms AP/AT off"

    def test_unknown_readback_fails_closed_by_default(self):
        """readback=None → takeover НЕ completed (fail-closed)."""
        ctrl = FakeControl()
        ctrl.set_readback_ap(None)  # Неизвестно
        ctrl.set_readback_at(None)

        adapter = FakeAircraftAdapter()
        adapter._ap_state = None
        adapter._at_state = None

        takeover = AutopilotTakeover()
        takeover.status.in_progress = True
        takeover.takeover_start_time = time.monotonic()
        takeover.initial_parameters = {"airspeed": 140, "altitude": 3000}

        telemetry = make_telemetry(bank=0, altitude_agl=2500, airspeed=140)
        status = takeover.perform_takeover(telemetry, adapter, ctrl)

        assert status.completed is False, \
            "Takeover should NOT complete with unknown readback (fail-closed)"
        assert status.autopilot_disengaged is False

    def test_adapter_readback_is_used_before_generic_fallback(self):
        """Adapter readback имеет приоритет над generic fallback."""
        ctrl = FakeControl()
        ctrl.set_readback_ap(True)  # Generic fallback говорит True

        adapter = FakeAircraftAdapter()
        adapter._ap_state = False  # Adapter чётко говорит False

        takeover = AutopilotTakeover()
        takeover.status.in_progress = True
        takeover.takeover_start_time = time.monotonic()
        takeover.initial_parameters = {"airspeed": 140, "altitude": 3000}

        telemetry = make_telemetry(bank=0, altitude_agl=2500, airspeed=140)
        status = takeover.perform_takeover(telemetry, adapter, ctrl)

        # Adapter readback False → autopilot_disengaged должен быть True
        assert status.autopilot_disengaged is True, \
            "Adapter readback should take priority over generic fallback"


# ═══════════════════════════════════════════════════════════════════
# FIX-1: Production readback
# ═══════════════════════════════════════════════════════════════════

class TestProductionReadback:
    """Production control.py и aircraft_adapter.py readback методы."""

    def test_control_readback_with_aq(self):
        """MSFSControl.get_autopilot_engaged читает SimVar через _aq."""
        from modules.control import MSFSControl

        mock_ae = MagicMock()
        mock_aq = MagicMock()
        mock_aq.get.return_value = True

        ctrl = MSFSControl(mock_ae, mock_aq)
        assert ctrl.get_autopilot_engaged() is True

        mock_aq.get.return_value = False
        assert ctrl.get_autopilot_engaged() is False

    def test_control_readback_without_aq_returns_none(self):
        """MSFSControl без _aq → readback возвращает None."""
        from modules.control import MSFSControl

        mock_ae = MagicMock()
        ctrl = MSFSControl(mock_ae)  # без _aq

        assert ctrl.get_autopilot_engaged() is None
        assert ctrl.get_autothrottle_engaged() is None

    def test_control_readback_exception_returns_none(self):
        """MSFSControl readback при исключении → None (не прокидывает)."""
        from modules.control import MSFSControl

        mock_ae = MagicMock()
        mock_aq = MagicMock()
        mock_aq.get.side_effect = Exception("SimConnect error")

        ctrl = MSFSControl(mock_ae, mock_aq)
        assert ctrl.get_autopilot_engaged() is None
        assert ctrl.get_autothrottle_engaged() is None

    def test_adapter_readback_returns_none(self):
        """AircraftCommandAdapter.readback → None (базовый fallback)."""
        from modules.aircraft_adapter import AircraftCommandAdapter

        mock_control = MagicMock()
        mock_telemetry = MagicMock()
        adapter = AircraftCommandAdapter(mock_control, mock_telemetry)

        assert adapter.get_autopilot_engaged() is None
        assert adapter.get_autothrottle_engaged() is None
