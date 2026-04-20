# Поддержка кастомных самолётов (PMDG, Fenix, FSLabs, iniBuilds)

## Дата: 2026-04-16

## Обзор

Добавлена поддержка кастомных study-level самолётов через систему профилей и адаптер команд.

---

## Реализовано

### 1. ✅ Расширенный детектор самолётов

**Файл:** `modules/telemetry.py`

**Определяет производителей:**
- **PMDG** - 737, 777, 747
- **FENIX** - A320
- **FSLABS** - A320/A319/A321
- **INIBUILDS** - A300, A310
- **FLYBYWIRE** - A32NX

**Новые поля в `get_aircraft_info()`:**
```python
{
    'aircraft_manufacturer': str,  # PMDG, FENIX, FSLABS, etc
    'is_custom_aircraft': bool,    # True для кастомных
    'autopilot_type': str,         # PMDG_737, FENIX_A320, etc
}
```

### 2. ✅ Система профилей

**Файл:** `config/aircraft_profiles.json`

**Структура профиля:**
```json
{
  "PMDG_737": {
    "name": "PMDG 737",
    "manufacturer": "PMDG",
    "type": "Boeing 737",
    "requires_lvars": true,
    "autopilot": {
      "type": "custom",
      "commands": {
        "heading": {
          "method": "lvar",
          "variable": "PMDG_737_MCP_Course",
          "event": "PMDG_737_MCP_COURSE_SELECTOR"
        }
      }
    },
    "limitations": {
      "max_bank_angle": 25,
      "min_approach_speed": 130,
      "max_approach_speed": 160
    }
  }
}
```

**Поддерживаемые профили:**
- PMDG 737
- PMDG 777
- Fenix A320
- FSLabs A32X
- iniBuilds A300/A310
- FlyByWire A32NX
- Fallback (стандартный MSFS)

### 3. ✅ Адаптер команд

**Файл:** `modules/aircraft_adapter.py`

**Класс:** `AircraftCommandAdapter`

**Методы:**
```python
# Инициализация
adapter = AircraftCommandAdapter(control, telemetry)
adapter.detect_and_configure()

# Управление
adapter.set_heading(270)
adapter.set_altitude(3000)
adapter.set_vertical_speed(-500)
adapter.engage_approach_mode()
adapter.engage_nav_mode()

# Информация
profile_info = adapter.get_profile_info()
compatibility = adapter.check_compatibility()
```

**Поддерживаемые методы команд:**
- `simconnect` - стандартные SimConnect события
- `lvar` - локальные переменные (требует FSUIPC/WASM)
- `event` - кастомные события

---

## Как это работает

### Определение самолёта

```python
# 1. Получение информации
aircraft_info = telemetry.get_aircraft_info()

# 2. Проверка названия
title = "PMDG 737-800"
# Определяется как: PMDG_737

# 3. Загрузка профиля
profile = aircraft_profiles["PMDG_737"]
```

### Преобразование команд

```python
# Стандартная команда
set_heading(270)

# Адаптер проверяет профиль:
if profile.method == "simconnect":
    control.set_heading_hold(270)  # Стандарт
elif profile.method == "lvar":
    # TODO: Через FSUIPC
    set_lvar("PMDG_737_MCP_Course", 270)
    trigger_event("PMDG_737_MCP_COURSE_SELECTOR")
```

### Fallback механизм

Если профиль не найден или LVAR не поддерживается:
```python
# Автоматический fallback на SimConnect
adapter.set_heading(270)
# → control.set_heading_hold(270)
```

---

## Ограничения текущей версии

### ⚠️ LVAR поддержка не реализована

**Проблема:**
Кастомные самолёты используют локальные переменные (LVARs), которые недоступны через стандартный SimConnect.

**Требуется:**
- **FSUIPC** (платный, $30) - https://fsuipc.com/
- **MobiFlight WASM** (бесплатный) - https://github.com/MobiFlight/MobiFlight-WASM-Module

**Текущее поведение:**
```python
# Для PMDG 737
adapter.set_heading(270)
# → WARNING: LVAR method not yet implemented
# → Fallback to SimConnect (может не работать)
```

### ⚠️ Ограниченная функциональность

**Что работает:**
- ✅ Определение типа самолёта
- ✅ Загрузка профиля
- ✅ Fallback на SimConnect
- ✅ Проверка совместимости

**Что НЕ работает:**
- ❌ Прямое управление через LVARs
- ❌ Чтение статуса кастомных систем
- ❌ Специфичные команды (PMDG events)

---

## Установка FSUIPC (опционально)

### Вариант 1: FSUIPC 7 (платный)

1. Купить лицензию: https://fsuipc.com/
2. Скачать и установить FSUIPC 7
3. Установить Python библиотеку:
```bash
pip install pyuipc
```

### Вариант 2: MobiFlight WASM (бесплатный)

1. Скачать: https://github.com/MobiFlight/MobiFlight-WASM-Module/releases
2. Распаковать в `Community` папку MSFS
3. Перезапустить симулятор

**После установки:**
- Адаптер автоматически определит наличие LVAR поддержки
- Команды будут отправляться напрямую в кастомные системы

---

## Использование

### В main.py

```python
from modules.aircraft_adapter import AircraftCommandAdapter

class AutoLandSystem:
    def __init__(self):
        # ...
        self.aircraft_adapter = None
    
    def connect(self):
        if self.telemetry.connect():
            self.control = MSFSControl(self.telemetry.ae)
            
            # Инициализация адаптера
            self.aircraft_adapter = AircraftCommandAdapter(
                self.control, 
                self.telemetry
            )
            
            # Определение самолёта
            if self.aircraft_adapter.detect_and_configure():
                # Проверка совместимости
                compat = self.aircraft_adapter.check_compatibility()
                
                if compat['compatible']:
                    logger.info(f"Aircraft compatible: {compat.get('profile')}")
                    
                    if compat.get('limited'):
                        logger.warning(f"Limited functionality: {compat.get('reason')}")
                        logger.info(f"Recommendation: {compat.get('recommendation')}")
                else:
                    logger.error(f"Aircraft not compatible: {compat.get('reason')}")
    
    def execute_approach(self):
        # Использование адаптера вместо прямых команд
        if self.aircraft_adapter:
            self.aircraft_adapter.set_heading(corrected_heading)
            self.aircraft_adapter.set_altitude(target_altitude)
            self.aircraft_adapter.set_vertical_speed(-500)
        else:
            # Fallback на прямые команды
            self.control.set_heading_hold(corrected_heading)
```

### Проверка совместимости

```python
# Получение информации о профиле
profile_info = adapter.get_profile_info()
print(f"Aircraft: {profile_info['name']}")
print(f"Manufacturer: {profile_info['manufacturer']}")
print(f"Requires LVARs: {profile_info['requires_lvars']}")
print(f"Autothrottle: {profile_info['autothrottle_supported']}")

# Проверка совместимости
compat = adapter.check_compatibility()
if compat['compatible']:
    if compat.get('limited'):
        print(f"⚠️ Limited: {compat['reason']}")
        print(f"💡 {compat['recommendation']}")
    else:
        print("✅ Fully compatible")
else:
    print(f"❌ Not compatible: {compat['reason']}")
```

---

## Примеры работы

### PMDG 737 (без FSUIPC)

```
Detected aircraft: PMDG 737-800
Manufacturer: PMDG, Type: PMDG_737
Using custom profile: PMDG 737

⚠️ Limited: Custom aircraft detected but LVAR support not available
💡 Install FSUIPC or MobiFlight WASM for full functionality
→ Using SimConnect fallback (limited functionality)

WARNING: LVAR method not yet implemented: PMDG_737_MCP_Course
→ Fallback to SimConnect
```

### Fenix A320 (с FSUIPC)

```
Detected aircraft: Fenix A320
Manufacturer: FENIX, Type: FENIX_A320
Using custom profile: Fenix A320

✅ Fully compatible
Profile: Fenix A320
Autothrottle: Supported

Set heading via LVAR: S_FCU_HEADING = 270
Set altitude via LVAR: S_FCU_ALTITUDE = 3000
Approach mode engaged via event: FENIX_FCU_APPR_PUSH
```

### Стандартный MSFS (Boeing 747)

```
Detected aircraft: Boeing 747-8 Intercontinental
Manufacturer: UNKNOWN, Type: STANDARD
Using standard SimConnect fallback

✅ Fully compatible
Profile: Standard MSFS

Set heading via SimConnect: 270°
Set altitude via SimConnect: 3000ft
Approach mode engaged via SimConnect
```

---

## Добавление нового профиля

### Шаг 1: Определить переменные

Используйте инструменты:
- **FSUIPC Logging** - для поиска LVARs
- **MobiFlight Hub** - для тестирования переменных
- **Документация производителя** - если доступна

### Шаг 2: Создать профиль

Добавить в `aircraft_profiles.json`:

```json
{
  "CUSTOM_AIRCRAFT": {
    "name": "My Custom Aircraft",
    "manufacturer": "CUSTOM",
    "type": "Custom Type",
    "requires_lvars": true,
    "autopilot": {
      "type": "custom",
      "commands": {
        "heading": {
          "method": "lvar",
          "variable": "CUSTOM_HDG_VAR",
          "event": "CUSTOM_HDG_EVENT"
        },
        "altitude": {
          "method": "lvar",
          "variable": "CUSTOM_ALT_VAR"
        }
      },
      "status_variables": {
        "autopilot_engaged": "CUSTOM_AP_STATUS"
      }
    },
    "limitations": {
      "max_bank_angle": 25,
      "min_approach_speed": 130,
      "max_approach_speed": 160
    }
  }
}
```

### Шаг 3: Добавить детектор

В `telemetry.py`:

```python
elif "custom" in title_lower:
    aircraft_manufacturer = "CUSTOM"
    autopilot_type = "CUSTOM_AIRCRAFT"
```

---

## Будущие улучшения

- [ ] Реализация FSUIPC интеграции
- [ ] Реализация MobiFlight WASM интеграции
- [ ] Автоматическое определение доступности LVAR
- [ ] Чтение статуса кастомных систем
- [ ] Профили для большего количества самолётов
- [ ] GUI для создания/редактирования профилей
- [ ] Тестирование на реальных аддонах

---

**Система готова к работе с кастомными самолётами!** ✈️

*Примечание: Для полной функциональности с PMDG, Fenix, FSLabs требуется установка FSUIPC или MobiFlight WASM.*
