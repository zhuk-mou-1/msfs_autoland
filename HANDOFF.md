# HANDOFF.md

## MSFS AutoLand — актуальный handoff по состоянию репозитория

**Дата:** 2026-08-09  
**Последний зафиксированный commit в `master`:** `f253e89`  
**Последняя заметная активность:** 2026-07-22

---

## 1. Executive summary

Проект находится в состоянии **сильного инженерного прототипа / advanced beta**.

**Сильные стороны:**
- safety-first подход, ownership model, guarded control paths
- большой объём contract/safety тестов
- активный цикл fix/refactor в июле 2026
- хорошая проработка takeover / guard / final approach

**Слабые стороны:**
- монолитный orchestration (`AutoLandSystem` знает слишком много)
- actuator failures частично log-only вместо fail-closed
- schema drift в telemetry
- слабая release/process hygiene, нет releases/tags
- документация местами устарела относительно `master`

---

## 2. Что произошло недавно (июль 2026)

1. Удалён/упрощён pretakeover control layer
2. Ужесточён abort/safety contract
3. Исправлены ошибки вокруг SimConnect command contracts (axis clamp, flap/VS/AT paths)
4. Сильно вырос тестовый контур (contract, safety, architecture tests)

---

## 3. Архитектурная оценка по областям

### Runtime / orchestration
- `main.py` → `AutoLandSystem` — функционально мощный, архитектурно перегруженный
- **Риск:** высокая сложность изменений и регрессий

### Control layer (`modules/control.py`)
- Хорошо: единая отправка событий, SDK-only events, guards на диапазоны осей
- **Риск:** `except Exception` → `logger.error(...)` в actuator methods → **не полностью fail-closed**

### Command ownership (`modules/command_gateway.py`)
- Хорошо: ownership per channel, контекст источника, rejection при конфликте
- **Риск:** unscoped commands пока не полностью запрещены, implicit fallback к `AIRCRAFT_AP`

### Telemetry (`modules/telemetry.py`)
- Хорошо: широкий охват SimConnect данных
- **Риск:** snapshot = последовательные чтения → non-atomic state, schema drift

### Safety / approach phases
- `modules/approach_phases.py`, `modules/safety_guard.py`, `modules/autopilot_takeover.py`
- **Самая сильная часть проекта**
- Слабость: высокая сложность на границе orchestration

### GUI (`gui.py`)
- Функционально богатый, но тесно связан с runtime internals

---

## 4. Основные риски

### P0
1. Log-only failure handling в actuator layer
2. Telemetry/schema drift
3. Ошибки единиц измерения (kg/lbs, feet/meters, knots/fpm)
4. Incomplete fail-closed enforcement в command scoping
5. Монолитный orchestration runtime

### P1
1. GUI/runtime coupling
2. Non-atomic telemetry snapshot
3. Устаревшая документация vs реальный код
4. Dependency management drift
5. Слабая release/version discipline

---

## 5. Рекомендуемые следующие шаги

### P0 (немедленно)
1. Сделать actuator failures fail-closed, а не log-only
2. Нормализовать telemetry/weather schema
3. Централизовать policy по units/conversions
4. Довести CommandGateway до strict scoped mode
5. Добавить write verification/readback policy для critical commands

### P1 (ближайший спринт)
1. Разбить `AutoLandSystem` на меньшие orchestration components
2. Ввести typed telemetry snapshot model
3. Сделать telemetry snapshot quality-aware
4. Ослабить coupling GUI ↔ runtime
5. Сделать CI stricter для safety-core

### P2 (cleanup)
1. Переписать README под реальное состояние
2. Почистить корень репо
3. Упорядочить dependencies / lock strategy
4. Завести releases/tags
5. Перенести backlog из markdown в GitHub issues

---

## 6. Что считать источником истины прямо сейчас

**Надёжно:**
- Текущее содержимое `master`
- Последние июльские коммиты
- Тесты в `tests/`
- CI workflows в `.github/workflows/`
- Код в `modules/`

**С осторожностью:**
- `CURRENT_STATE.md`, `PROJECT_STATUS_2026-04-18.md` — полезный исторический контекст, но частично устарели
- README как единственный источник статуса

---

## 7. Файлы для чтения первыми

### Начать с:
1. `main.py`
2. `modules/approach_phases.py`
3. `modules/control.py`
4. `modules/command_gateway.py`
5. `modules/telemetry.py`

### Потом:
- `modules/autopilot_takeover.py`
- `modules/safety_guard.py`
- `modules/autothrottle.py`
- `gui.py`
- `.github/workflows/ci.yml`

### Исторический контекст:
- `CURRENT_STATE.md`
- `PROJECT_STATUS_2026-04-18.md`
- `PROJECT_ANALYSIS.md`
- `ARCHITECTURE.md`

---

## 8. Вердикт

> Это не production-ready система, но и не хаотичный pet-project.  
> Это **сильный инженерный прототип** с правильным safety-мышлением, серьёзной тестовой базой  
> и заметным техдолгом на границе runtime contracts, telemetry model и repo/process maturity.

---

## 9. Сопутствующие документы (рекомендуется завести)

- `BACKLOG.md`
- `SAFETY_CONTRACTS.md`
- `UNITS_POLICY.md`
- `RELEASE_PLAN.md`
- `KNOWN_RUNTIME_GAPS.md`
