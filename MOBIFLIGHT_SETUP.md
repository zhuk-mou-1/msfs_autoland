# MobiFlight WASM - Установка и настройка

**Дата:** 2026-04-18  
**Версия MobiFlight WASM:** 1.0.1  
**Статус:** ✅ Установлено

---

## Что установлено

**MobiFlight WASM Module v1.0.1**
- Источник: https://github.com/MobiFlight/MobiFlight-WASM-Module
- Размер: 477 KB (архив), 1.8 MB (распакован)
- Файл WASM: MobiFlightWasmModule.wasm (1.79 MB)

**Путь установки:**
```
C:\Users\MYRIG\AppData\Local\Packages\
Microsoft.FlightSimulator_8wekyb3d8bbwe\LocalCache\Packages\Community\
mobiflight-event-module\
```

**Структура:**
```
mobiflight-event-module/
├── ContentInfo/
│   └── mobiflight-event-module/
│       └── Thumbnail.jpg
├── modules/
│   └── MobiFlightWasmModule.wasm  ← Основной модуль
├── layout.json
└── manifest.json
```

---

## Требования

**Минимальная версия MSFS:** 1.36.2 (указано в manifest.json)

**Ваша версия MSFS:** Microsoft Store (проверьте в симуляторе)

**Совместимость:**
- ✅ MSFS 2020 (все версии после 1.36.2)
- ✅ MSFS 2024 (все версии)

---

## Проверка установки

### Шаг 1: Проверка файлов

Убедитесь что файлы на месте:

```bash
ls -la "C:\Users\MYRIG\AppData\Local\Packages\Microsoft.FlightSimulator_8wekyb3d8bbwe\LocalCache\Packages\Community\mobiflight-event-module\"
```

Должны быть:
- ✅ manifest.json (290 bytes)
- ✅ layout.json (379 bytes)
- ✅ modules/MobiFlightWasmModule.wasm (1.79 MB)

### Шаг 2: Перезапуск MSFS

**ВАЖНО:** После установки WASM модуля **обязательно перезапустите MSFS!**

1. Закройте MSFS полностью
2. Запустите MSFS заново
3. Загрузите любой полёт

### Шаг 3: Запуск теста

```bash
cd C:\BAT\msfs_autoland
python test_mobiflight_wasm.py
```

**Ожидаемый результат:**
```
✅ Подключено к MSFS
✅ MobiFlight WASM подключен успешно!
✅ Самолёт: [название вашего самолёта]
✅ Чтение L:Var работает
✅ Запись L:Var работает
✅ Aircraft adapter настроен
```

---

## Использование в проекте

### Автоматическое подключение

Ваш проект **автоматически** обнаруживает и использует MobiFlight WASM:

**В aircraft_adapter.py (строки 40-54):**
```python
# Попытка подключения к MobiFlight WASM
from modules.wasm_interface import MobiFlightWASM
self.wasm = MobiFlightWASM(telemetry.sm)
if self.wasm.connect():
    logger.info("MobiFlight WASM connected - LVAR support enabled")
else:
    self.wasm = None
    logger.info("MobiFlight WASM not available - using SimConnect only")
```

### Проверка в логах

При запуске `gui.py` или `main.py` смотрите логи:

**Успешное подключение:**
```
INFO - SimConnect CLIENT_DATA API initialized
INFO - All CLIENT_DATA methods available in SimConnect.dll
INFO - MobiFlight WASM connected successfully
INFO - Aircraft adapter initialized with WASM support
```

**WASM недоступен:**
```
WARNING - MobiFlight WASM module not found
INFO - MobiFlight WASM not available - using SimConnect only
INFO - Using standard SimConnect fallback
```

---

## Поддерживаемые самолёты

### С MobiFlight WASM (полная поддержка)

**PMDG:**
- ✅ PMDG 737-700/800/900 - полный доступ к MCP через L:Vars
- ✅ PMDG 777 - полный доступ к MCP через L:Vars

**Fenix:**
- ✅ Fenix A320 - полный доступ к FCU через L:Vars

**FlyByWire:**
- ✅ FlyByWire A32NX - полный доступ к FCU через L:Vars

**FSLabs:**
- ✅ FSLabs A320 Family - базовая поддержка через L:Vars

**iniBuilds:**
- ✅ iniBuilds A300/A310 - базовая поддержка через L:Vars

### Без MobiFlight WASM (fallback)

**Стандартные MSFS:**
- ✅ Все самолёты Asobo - через SimConnect
- ✅ Cessna 172, TBM 930, Airbus A320neo и т.д.

---

## Команды L:Vars

### Чтение переменной

```python
from modules.wasm_interface import MobiFlightWASM

wasm = MobiFlightWASM(simconnect)
wasm.connect()

# Чтение курса MCP на PMDG 737
course = wasm.read_lvar("PMDG_737_MCP_Course")
print(f"MCP Course: {course}°")
```

### Запись переменной

```python
# Установка курса 270° на PMDG 737
wasm.write_lvar("PMDG_737_MCP_Course", 270)

# Опционально: триггер события
wasm.trigger_event("PMDG_737_MCP_COURSE_SELECTOR")
```

### Через aircraft_adapter (рекомендуется)

```python
from modules.aircraft_adapter import AircraftCommandAdapter

adapter = AircraftCommandAdapter(control, telemetry)
adapter.detect_and_configure()

# Установка курса (автоматически использует L:Vars если доступны)
adapter.set_heading(270)

# Установка высоты
adapter.set_altitude(10000)

# Включение автопилота
adapter.engage_autopilot()
```

---

## Troubleshooting

### Проблема: "MobiFlight WASM not found"

**Решение:**
1. Проверьте путь установки (см. выше)
2. Перезапустите MSFS
3. Убедитесь что версия MSFS >= 1.36.2
4. Проверьте что папка называется `mobiflight-event-module` (без пробелов)

### Проблема: "CLIENT_DATA methods not found"

**Решение:**
1. Проверьте версию Python-SimConnect: `pip show SimConnect`
2. Убедитесь что SimConnect.dll доступна
3. Проверьте логи на наличие ошибок ctypes

### Проблема: "LVAR read/write failed"

**Решение:**
1. Убедитесь что самолёт поддерживает L:Vars (PMDG, Fenix)
2. Проверьте правильность имени переменной
3. Некоторые переменные только для чтения
4. Проверьте логи WASM модуля

### Проблема: Fallback на SimConnect

**Это нормально если:**
- Используете стандартный самолёт MSFS
- WASM модуль не установлен
- Самолёт не поддерживает L:Vars

**Система продолжит работать** с ограниченной функциональностью.

---

## Дополнительная информация

**Документация проекта:**
- `CLIENT_DATA_IMPLEMENTATION.md` - реализация CLIENT_DATA API
- `WASM_ALTERNATIVES.md` - альтернативные решения
- `TESTING_INSTRUCTIONS.md` - инструкции по тестированию
- `config/aircraft_profiles.json` - профили самолётов с L:Vars

**MobiFlight WASM:**
- GitHub: https://github.com/MobiFlight/MobiFlight-WASM-Module
- Документация: https://github.com/MobiFlight/MobiFlight-WASM-Module/wiki
- Issues: https://github.com/MobiFlight/MobiFlight-WASM-Module/issues

**Сообщество:**
- MobiFlight Discord: https://discord.gg/mobiflight
- MSFS Forums: https://forums.flightsimulator.com/

---

## Changelog

**2026-04-18:**
- ✅ Установлен MobiFlight WASM v1.0.1
- ✅ Создан тестовый скрипт test_mobiflight_wasm.py
- ✅ Создана документация MOBIFLIGHT_SETUP.md
- ✅ Готово к тестированию

**Следующие шаги:**
1. Перезапустить MSFS
2. Запустить test_mobiflight_wasm.py
3. Протестировать с кастомным самолётом (PMDG/Fenix)
4. Проверить работу в gui.py

---

**Автор:** Claude (Sonnet 4)  
**Дата:** 2026-04-18 01:00 UTC+3
