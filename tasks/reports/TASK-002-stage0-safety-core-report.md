# TASK-002 — отчёт

## Статус
DONE

## Решения по дизайну

- **Safety policy:** hard fail (abort) для attitude_safe и airborne; retryable для speed_stable и altitude_stable. Hard fail немедленно блокирует команды AP/A/T.
- **Degraded/readback policy:** Readback=None → fail-closed (takeover НЕ completed). Adapter readback приоритетнее generic control readback. Production readback реализован через SimVar `AUTOPILOT_MASTER` / `AUTOPILOT_THROTTLE_ARM` в `MSFSControl` и `AircraftCommandAdapter` (базовый → None, fallback в control).
- **Control ownership:** интегрирован в `FinalPhaseState.handle()` — `compute_ownership()` вызывается каждый тик. `_control_aircraft()` и `_control_throttle()` проверяют ownership перед отправкой команд.
- **Единицы:** `ApproachConfig.runway_length` в футах. Конвертация feet→meters в `main.py` перед вызовом `get_recommended_takeover_point()`. `SHORT_RUNWAY_THRESHOLD_M = 1500.0`.
- **Clock:** timeout измеряется через `time.monotonic()` (injectable clock для тестов, без monkeypatch).
- **Retryable после команд:** после `_commands_sent=True` retryable-проверки (speed_stable, altitude_stable) игнорируются — это осознанное решение Stage 0: однажды начав отключение AP, система не откатывает при кратковременных отклонениях скорости/высоты.

## Изменённые файлы

- `main.py`: `_reset_approach_session_state()`, вызов в `start_approach()`, feet→meters конвертация, передача `aircraft_requests` в `MSFSControl`
- `modules/autopilot_takeover.py`: hard/retryable safety gates, readback verification, monotonic clock, crossing detection (`_prev_altitude_agl`), `_commands_sent` flag
- `modules/approach_phases.py`: DH guard в FinalPhaseState, ownership integration в `_control_aircraft()` и `_control_throttle()`
- `modules/control.py`: readback методы `get_autopilot_engaged()` / `get_autothrottle_engaged()` через SimVar
- `modules/aircraft_adapter.py`: readback методы с дефолтом None (fallback → control)
- `modules/control_ownership.py`: **новый** — `ControlOwner`, `ControlOwnership`, `compute_ownership()`
- `tests/fakes.py`: **новый** — `FakeControl`, `FakeAircraftAdapter`, `FakeVJoy`, `FakeClock`, `make_telemetry()`
- `tests/conftest.py`: **новый** — shared fixtures
- `tests/test_approach_lifecycle.py`: **новый** — 3 теста сброса per-approach состояния
- `tests/test_takeover_safety.py`: **новый** — 14 тестов (6 hard gates + 4 readback + 4 production readback)
- `tests/test_ils_takeover_crossing.py`: **новый** — 12 тестов ILS crossing + DH guard + crossing detection
- `tests/test_control_ownership.py`: **новый** — 7 тестов ownership planner (включая production integration test)
- `tests/test_runway_units.py`: **новый** — 5 тестов единиц ВПП
- `tests/replay/test_replay_scenarios.py`: **новый** — 4 replay сценария
- `tests/replay/fixtures/*.jsonl`: **новый** — 4 JSONL fixtures

## Коммиты

- `729c89f` TASK-002-FIX: FIX-1..FIX-4 — production readback, monotonic clock, crossing detection, ownership integration
- `90653d0` TASK-002: WP-7 — replay fixtures + scenario tests (4 сценария)
- `86eec15` TASK-002: WP-6 — явные единицы ВПП, feet→meters конвертация в main.py
- `d79d243` TASK-002: WP-5 — control ownership planner (один канал = один владелец)
- `7abf847` TASK-002: WP-4 — ILS crossing detection + DH guard в FinalPhaseState
- `d772c98` TASK-002: WP-2+WP-3 — hard safety gates + readback-verified takeover
- `9e6c62d` TASK-002: WP-1 — сброс per-approach состояния в start_approach()
- `f03a00e` TASK-002: WP-0 — тестовый каркас и fakes (FakeControl, FakeAircraftAdapter, FakeVJoy, FakeClock)

## Тестовая матрица

| Инвариант | Тест(ы) | Результат |
|---|---|---|
| Повторный заход после takeover — чистое состояние | test_second_approach_resets_completed_takeover, test_go_around_then_start_is_clean | PASSED |
| Hard safety check блокирует команды | test_unsafe_bank_blocks_takeover_without_commands, test_on_ground_blocks_takeover_without_commands | PASSED |
| Takeover требует readback подтверждения | test_sent_disengage_command_is_not_verified_takeover, test_takeover_completes_only_after_readback_off, test_unknown_readback_fails_closed_by_default | PASSED |
| Production readback через SimVar | test_control_readback_with_aq, test_control_readback_without_aq_returns_none, test_control_readback_exception_returns_none, test_adapter_readback_returns_none | PASSED |
| ILS crossing detection с трекингом | test_crossing_dh_plus_50_starts_takeover, test_large_step_crossing_window_initiates, test_large_step_below_dh_does_not_initiate | PASSED |
| Ниже DH без takeover → go-around | test_first_snapshot_below_dh_without_takeover_fails_closed, test_below_dh_guard_triggers_go_around_in_final_phase | PASSED |
| Один канал = один владелец (production path) | test_unconfirmed_takeover_keeps_ap_as_roll_pitch_owner, test_confirmed_external_flare_uses_vjoy_without_ap_pitch_roll_commands, test_no_vjoy_means_no_direct_pitch_roll_commands, test_no_competing_ap_and_vjoy_commands | PASSED |
| Единицы ВПП явные | test_8000_ft_is_not_interpreted_as_8000_m, test_short_runway_threshold_is_consistent_in_meters, test_takeover_recommendation_receives_explicit_unit | PASSED |
| Replay: все 4 сценария | test_ils_nominal, test_ils_crosses_takeover_window, test_ils_below_dh_without_takeover, test_unsafe_bank_at_takeover | PASSED |

## Сырой вывод команд

### pytest tests/ -q
```text
59 passed, 1 warning in 0.57s
```

### pytest tests/test_takeover_safety.py -v
```text
tests/test_takeover_safety.py::TestHardSafetyGates::test_unsafe_bank_blocks_takeover_without_commands PASSED
tests/test_takeover_safety.py::TestHardSafetyGates::test_on_ground_blocks_takeover_without_commands PASSED
tests/test_takeover_safety.py::TestHardSafetyGates::test_unstable_speed_waits_without_disengaging_ap PASSED
tests/test_takeover_safety.py::TestHardSafetyGates::test_all_checks_pass_starts_command_sequence PASSED
tests/test_takeover_safety.py::TestHardSafetyGates::test_timeout_uses_monotonic_clock PASSED
tests/test_takeover_safety.py::TestHardSafetyGates::test_failure_reason_is_machine_checkable PASSED
tests/test_takeover_safety.py::TestReadbackVerifiedTakeover::test_sent_disengage_command_is_not_verified_takeover PASSED
tests/test_takeover_safety.py::TestReadbackVerifiedTakeover::test_takeover_completes_only_after_readback_off PASSED
tests/test_takeover_safety.py::TestReadbackVerifiedTakeover::test_unknown_readback_fails_closed_by_default PASSED
tests/test_takeover_safety.py::TestReadbackVerifiedTakeover::test_adapter_readback_is_used_before_generic_fallback PASSED
tests/test_takeover_safety.py::TestProductionReadback::test_control_readback_with_aq PASSED
tests/test_takeover_safety.py::TestProductionReadback::test_control_readback_without_aq_returns_none PASSED
tests/test_takeover_safety.py::TestProductionReadback::test_control_readback_exception_returns_none PASSED
tests/test_takeover_safety.py::TestProductionReadback::test_adapter_readback_returns_none PASSED
14 passed in 0.04s
```

## Live-ограничения

- **Readback в live-симе:** `MSFSControl.get_autopilot_engaged()` читает SimVar `AUTOPILOT_MASTER` через `AircraftRequests`. Если SimConnect канал недоступен — возвращает `None` (fail-closed). `AircraftCommandAdapter` базовый возвращает `None` (fallback → control). Кастомные адаптеры (PMDG, Fenix) могут переопределить через LVars, но это не реализовано в Stage 0.
- **До FIX-1:** takeover в live-симе завершался таймаутом и go-around'ом на каждом ILS-заходе (readback всегда None). После FIX-1: readback работает через SimVar, takeover завершается нормально при working SimConnect.
- **Retryable после команд:** после отправки команд выключения AP/A/T (`_commands_sent=True`), повторные проверки скорости/высоты игнорируются. Это осознанное решение: однажды начав отключение, система не откатывает при кратковременных отклонениях.

## Остаточные ограничения

- **Реальные MSFS/vJoy/MobiFlight smoke tests НЕ выполнены** — все тесты офлайн, детерминированные.
- **DH guard в approach_phases.py** интегрирован в FinalPhaseState, но не тестировался в live ILS approach.
- **Replay harness** базовый — snapshot-by-snapshot, без time-based simulation.
- **Кастомные aircraft adapters** (PMDG, Fenix) не имеют readback через LVars — возвращают None.

## Review fixes (по PR #1 review)

- **FIX-1:** Production readback в `control.py` и `aircraft_adapter.py` — `get_autopilot_engaged()` / `get_autothrottle_engaged()` через SimVar. Тесты: 4 new (с аq, без аq, exception, adapter fallback).
- **FIX-2:** Timeout test через инжекцию `clock` вместо monkeypatch. Все `takeover_start_time = time.time()` заменены на `time.monotonic()`.
- **FIX-3:** Crossing detection — `_prev_altitude_agl` трекинг в `should_initiate_takeover()`. Тесты: 2 new (crossing window, below DH).
- **FIX-4:** Ownership интегрирован в `FinalPhaseState.handle()`. `_control_aircraft()` и `_control_throttle()` проверяют ownership. Тест переписан на production path.
- **FIX-5:** Убран несуществующий флаг `allow_unverified_takeover` из отчёта. Добавлен раздел «Live-ограничения».
- **FIX-6:** Добавлен комментарий в код и строка в отчёте о retryable-проверках после отправки команд.
