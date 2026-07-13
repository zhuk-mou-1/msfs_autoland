"""WP-1: Тесты жизненного цикла захода — сброс состояния.

Дефект: start_approach() не вызывает AutopilotTakeover.reset()
и не сбрасывает takeover_initiated. Повторный заход не может
инициировать новый takeover.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock


_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from modules.autopilot_takeover import AutopilotTakeover
from tests.fakes import FakeControl


def _make_system_with_completed_takeover():
    """
    Создать AutoLandSystem с завершённым takeover.
    Используем минимальный mock чтобы не тянуть SimConnect.
    """
    from main import AutoLandSystem, ApproachPhase

    system = AutoLandSystem.__new__(AutoLandSystem)

    # Минимальная инициализация без SimConnect
    system.structured_logger = MagicMock()
    system.telemetry = MagicMock()
    system.control = FakeControl()
    system.navigation = MagicMock()
    system.wind_correction = MagicMock()
    system.dme_navigation = MagicMock()
    system.virtual_joystick = MagicMock()
    system.stabilized_monitor = MagicMock()
    system.flare_controller = MagicMock()
    system.ils_navigation = MagicMock()
    system.autothrottle = MagicMock()
    system.vjoy_throttle = None
    system.fms_reader = None
    system.aircraft_adapter = MagicMock()
    system.wind_shear_detector = MagicMock()
    system.turbulence_detector = MagicMock()
    system.audio_system = MagicMock()
    system.connection_optimizer = None
    system.connection_monitor = None
    system.speed_calculator = MagicMock()
    system.autopilot_takeover = AutopilotTakeover()
    system.approach_config = MagicMock()
    system.approach_config.station.type = "ILS"
    system.approach_config.decision_height = 200
    system.approach_config.approach_speed = 140
    system.approach_config.runway_length = 8000
    system.approach_params = None
    system.takeover_initiated = True  # <-- defect state
    system.phase = ApproachPhase.FINAL
    system.phase_state = None
    system.running = True
    system.use_vjoy = False
    system.use_ils = True
    system.use_autothrottle = True
    system.use_custom_autopilot = False
    system.audio_alerts_enabled = False
    system._last_fms_log_time = 0.0
    system._ils_info_logged = True
    system.telemetry_recorder = MagicMock()

    # Симулируем завершённый takeover
    system.autopilot_takeover.status.completed = True
    system.autopilot_takeover.status.in_progress = False

    return system


class TestApproachLifecycleReset:
    """WP-1: Повторный заход после takeover/go-around стартует с чистого состояния."""

    def test_second_approach_resets_completed_takeover(self):
        """После completed takeover, start_approach() должен сбросить всё."""
        system = _make_system_with_completed_takeover()

        # Проверяем что состояние "грязное"
        assert system.autopilot_takeover.status.completed is True
        assert system.takeover_initiated is True
        assert system._ils_info_logged is True

        # Мокаем telemetry для start_approach
        system.telemetry.get_all_data.return_value = {
            "weather": {},
            "aircraft": {"title": "Test"},
        }

        # Вызываем start_approach
        system.start_approach()

        # После start_approach состояние должно быть чистым
        assert system.autopilot_takeover.status.completed is False, \
            "takeover.status.completed should be False after reset"
        assert system.autopilot_takeover.status.in_progress is False, \
            "takeover.status.in_progress should be False after reset"
        assert system.takeover_initiated is False, \
            "takeover_initiated should be False after reset"
        assert system._ils_info_logged is False, \
            "_ils_info_logged should be False after reset"

    def test_go_around_then_start_is_clean(self):
        """После go-around + start_approach, takeover state должен быть чистым."""
        system = _make_system_with_completed_takeover()

        # Мокаем dependencies для go-around
        system.autothrottle.active = False
        system.vjoy_throttle = None

        # Выполняем go-around
        system.execute_go_around()

        # Проверяем что stop_approach сбросил phase
        from main import ApproachPhase
        assert system.phase == ApproachPhase.IDLE

        # Теперь стартуем новый заход
        system.telemetry.get_all_data.return_value = {
            "weather": {},
            "aircraft": {"title": "Test"},
        }
        system.approach_config = MagicMock()
        system.approach_config.station.type = "ILS"
        system.approach_config.decision_height = 200
        system.approach_config.approach_speed = 140
        system.approach_config.runway_length = 8000
        system.approach_config.station.frequency = 11030000
        system.approach_config.final_approach_course = 270

        system.start_approach()

        assert system.autopilot_takeover.status.completed is False
        assert system.takeover_initiated is False

    def test_reset_preserves_approach_configuration_and_connection(self):
        """Сброс НЕ должен удалять approach_config, control, telemetry."""
        system = _make_system_with_completed_takeover()

        original_config = system.approach_config
        original_control = system.control
        original_telemetry = system.telemetry

        system.telemetry.get_all_data.return_value = {
            "weather": {},
            "aircraft": {"title": "Test"},
        }

        system.start_approach()

        # Конфигурация и контроллер должны сохраниться
        assert system.approach_config is original_config
        assert system.control is original_control
        assert system.telemetry is original_telemetry
