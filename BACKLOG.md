# BACKLOG.md

## MSFS AutoLand — инженерный backlog

**Дата:** 2026-08-09  
**Источник:** аудит кода + code review `master` @ `f253e89`

> Этот беклог предназначен для переноса в GitHub Issues.  
> Приоритеты: **P0** = критические риски безопасности/корректности, **P1** = серьёзные архитектурные проблемы, **P2** = техдолг/cleanup.

---

## P0 — блокеры (решать в первую очередь)

### P0-1: Actuator failures — fail-closed, а не log-only
**Область:** `modules/control.py`  
**Проблема:** Многие actuator methods перехватывают `Exception` и только логируют ошибку. Orchestration не знает, что команда реально провалилась.  
**Требуемое действие:**
- заменить `except Exception: logger.error(...)` на явное бросание / propagation;
- actuator method должен возвращать success/failure вызывающему коду;
- orchestration loop должен обрабатывать failure и инициировать abort при критических ошибках.

**Labels:** `bug`, `safety`, `P0`

---

### P0-2: Telemetry — нормализовать schema и убрать drift
**Область:** `modules/telemetry.py`  
**Проблема:** Snapshot собирается как набор последовательных чтений — возможен non-atomic state. Есть несогласованность ключей weather/telemetry между производителем и потребителям.  
**Требуемое действие:**
- ввести typed snapshot model (например, dataclass или TypedDict);
- зафиксировать контракт имён / единиц измерения между producer и consumer;
- добавить snapshot quality flag (насколько данные актуальны).

**Labels:** `bug`, `safety`, `telemetry`, `P0`

---

### P0-3: Units policy — централизовать конверсию единиц
**Область:** весь проект  
**Проблема:** Риск ошибок единиц измерения: kg/lbs, feet/meters, knots/fpm. Конверсии разбросаны по коду.  
**Требуемое действие:**
- создать `UNITS_POLICY.md` с зафиксированными соглашениями;
- вынести все conversions в единый модуль;
- проверить все места использования на соответствие.

**Labels:** `bug`, `safety`, `P0`

---

### P0-4: CommandGateway — strict scoped mode, убрать implicit fallback
**Область:** `modules/command_gateway.py`  
**Проблема:** Unscoped команды пока трактуются как implicit `AIRCRAFT_AP`. Это позволяет командам пропускать овнершип-защиту.  
**Требуемое действие:**
- запретить unscoped команды полностью;
- проверить все пути вызова на scope;
- добавить контрактные тесты на режекцию.

**Labels:** `bug`, `safety`, `P0`

---

### P0-5: Critical commands — добавить write verification / readback
**Область:** `modules/control.py`, `modules/command_gateway.py`  
**Проблема:** Отсутствует readback-политика для critical commands: послал команду — нет гарантии, что состояние AP/AT изменилось.  
**Требуемое действие:**
- определить список critical commands;
- для каждого добавить readback-проверку через telemetry;
- при несовпадении — retry или abort.

**Labels:** `enhancement`, `safety`, `P0`

---

## P1 — архитектурные исправления

### P1-1: Разбить `AutoLandSystem` на меньшие components
**Область:** `main.py`  
**Проблема:** `AutoLandSystem` совмещает lifecycle, config, loop, safety, telemetry, monitoring, GUI-interaction. Слишком большая зона изменений.  
**Требуемое действие:** выделить отдельные orchestration components (например, `ApproachOrchestrator`, `ConnectionManager`, `TelemetryRecorder`).

**Labels:** `refactor`, `architecture`, `P1`

---

### P1-2: Typed telemetry snapshot model
**Область:** `modules/telemetry.py`  
**Проблема:** Телеметрия работает с dict-like снапшотами, что затрудняет mypy-проверку и позволяет schema drift.  
**Требуемое действие:** ввести `TelemetrySnapshot` dataclass, перевести потребителей на typed snapshot.

**Labels:** `refactor`, `telemetry`, `P1`

---

### P1-3: Telemetry snapshot — quality-aware
**Область:** `modules/telemetry.py`  
**Проблема:** Нет механизма оценки свежести данных в snapshot.  
**Требуемое действие:** добавить timestamp и quality flag; safety guard должен отказываться работать с stale snapshot.

**Labels:** `enhancement`, `telemetry`, `safety`, `P1`

---

### P1-4: Ослабить coupling GUI ↔ runtime
**Область:** `gui.py`, `main.py`  
**Проблема:** GUI напрямую обращается к runtime-внутренностям, что делает изолированное тестирование рантайма невозможным.  
**Требуемое действие:** ввести чёткий интерфейс/протокол между GUI и runtime (callback / event bus / фасад-объект).

**Labels:** `refactor`, `architecture`, `P1`

---

### P1-5: CI — ужесточить для safety-core
**Область:** `.github/workflows/ci.yml`  
**Проблема:** Не все проверки blocking. Часть шагов допускает error-tolerant режим.  
**Требуемое действие:**
- сделать safety/contract-тесты blocking при merge;
- `continue-on-error: false` для safety-критичных шагов;
- добавить отдельный CI-шаг для проверки units consistency.

**Labels:** `ci`, `safety`, `P1`

---

## P2 — техдолг / cleanup

### P2-1: Обновить README под реальное состояние
**Labels:** `docs`, `P2`

### P2-2: Почистить корень репо от старых док-артефактов анализа
**Labels:** `chore`, `P2`

### P2-3: Упорядочить dependency strategy
**Проблема:** `requirements.txt` и `requirements_locked.txt` расходятся. Нет политики lock в `pyproject.toml`.  
**Labels:** `chore`, `dependencies`, `P2`

### P2-4: Завести releases и tags
**Проблема:** В репо нет ни одного release или tag. Нет возможности пиннить конкретную рабочую версию.  
**Labels:** `chore`, `release`, `P2`

### P2-5: Перенести backlog из этого файла в GitHub Issues
**Labels:** `chore`, `P2`

---

## Связанные документы

- [`HANDOFF.md`](./HANDOFF.md) — актуальный инженерный handoff
- `SAFETY_CONTRACTS.md` — рекомендуется создать
- `UNITS_POLICY.md` — рекомендуется создать
