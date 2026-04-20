# Определение типа самолёта и автопилота

## Дата: 2026-04-16

## Обзор

Добавлена возможность автоматического определения типа самолёта и его автопилота через SimConnect API.

---

## Новый метод get_aircraft_info()

### Файл: `modules/telemetry.py`

```python
def get_aircraft_info(self) -> Dict[str, any]:
    """Получить информацию о самолёте и его системах"""
    return {
        'title': str,              # Название самолёта
        'atc_type': str,           # Тип для ATC
        'atc_model': str,          # Модель для ATC
        'category': str,           # Категория (Airplane, Helicopter, etc)
        'engine_type': int,        # Код типа двигателя
        'engine_type_name': str,   # Название типа двигателя
        'number_of_engines': int,  # Количество двигателей
        'autopilot_available': bool,      # Доступен ли автопилот
        'autopilot_type': str,            # Тип автопилота
        'autopilot_max_bank': float,      # Максимальный крен
        'is_gear_retractable': bool,      # Убираемое шасси
        'is_tail_dragger': bool,          # Хвостовое колесо
    }
```

---

## Типы двигателей

| Код | Название | Описание |
|-----|----------|----------|
| 0 | Piston | Поршневой двигатель |
| 1 | Jet | Реактивный двигатель |
| 2 | None | Нет двигателя (планер) |
| 3 | Helo Turbine | Вертолётная турбина |
| 4 | Unsupported | Не поддерживается |
| 5 | Turboprop | Турбовинтовой |

---

## Типы автопилота

Система определяет тип автопилота на основе доступных режимов:

### NONE
- Автопилот отсутствует
- Самолёт не имеет систем автопилота
- **Совместимость:** ❌ Требуется vJoy для управления

### LIMITED
- Ограниченный автопилот
- Доступны только некоторые режимы
- **Совместимость:** ⚠️ Частичная

### BASIC
- Базовый автопилот
- Heading Hold + Altitude Hold
- **Совместимость:** ⚠️ Ограниченная (нет NAV/Approach)

### STANDARD
- Стандартный автопилот MSFS
- Все основные режимы: Heading, Altitude, NAV, Approach
- Max Bank ≤ 25°
- **Совместимость:** ✅ Полная

### ADVANCED
- Продвинутый автопилот
- Все режимы + расширенные возможности
- Max Bank > 25°
- Возможно кастомный или study-level
- **Совместимость:** ✅ Полная (возможно лучше)

---

## Алгоритм определения

```python
if autopilot_available:
    has_approach = AUTOPILOT_APPROACH_HOLD
    has_nav = AUTOPILOT_NAV1_LOCK
    has_altitude = AUTOPILOT_ALTITUDE_LOCK
    has_heading = AUTOPILOT_HEADING_LOCK
    
    if has_approach and has_nav and has_altitude and has_heading:
        if autopilot_max_bank > 25:
            return "ADVANCED"  # Кастомный/продвинутый
        else:
            return "STANDARD"  # Стандартный MSFS
    elif has_heading and has_altitude:
        return "BASIC"  # Базовый
    else:
        return "LIMITED"  # Ограниченный
else:
    return "NONE"  # Нет автопилота
```

---

## SimConnect переменные

### Базовая информация
- `TITLE` - полное название самолёта
- `ATC_TYPE` - тип для ATC (например "Boeing")
- `ATC_MODEL` - модель для ATC (например "737")
- `CATEGORY` - категория (Airplane, Helicopter, etc)

### Двигатели
- `ENGINE_TYPE` - тип двигателя (0-5)
- `NUMBER_OF_ENGINES` - количество двигателей

### Автопилот
- `AUTOPILOT_AVAILABLE` - доступен ли автопилот
- `AUTOPILOT_MAX_BANK` - максимальный крен автопилота
- `AUTOPILOT_MASTER` - включён ли автопилот
- `AUTOPILOT_HEADING_LOCK` - режим удержания курса
- `AUTOPILOT_ALTITUDE_LOCK` - режим удержания высоты
- `AUTOPILOT_NAV1_LOCK` - режим следования по NAV
- `AUTOPILOT_APPROACH_HOLD` - режим захода на посадку
- `AUTOPILOT_AIRSPEED_HOLD` - режим удержания скорости

### Дополнительно
- `IS_GEAR_RETRACTABLE` - убираемое шасси
- `IS_TAIL_DRAGGER` - хвостовое колесо

---

## Использование

### Тестовый скрипт

```bash
cd C:/BAT/msfs_autoland
python test_aircraft_detection.py
```

**Вывод:**
```
==============================================================
AIRCRAFT INFORMATION
==============================================================
Title:              Boeing 737-800
ATC Type:           Boeing
ATC Model:          737
Category:           Airplane

==============================================================
ENGINE INFORMATION
==============================================================
Engine Type:        Jet (1)
Number of Engines:  2

==============================================================
AUTOPILOT INFORMATION
==============================================================
Autopilot Available: True
Autopilot Type:      STANDARD
Max Bank Angle:      25.0°

==============================================================
AUTOPILOT TYPE INTERPRETATION
==============================================================
✅ Standard autopilot
   Full-featured standard MSFS autopilot
   Supports: Heading, Altitude, NAV, Approach modes

==============================================================
RECOMMENDATIONS FOR AUTOLAND SYSTEM
==============================================================
✅ This aircraft is COMPATIBLE with AutoLand system
   Full autopilot functionality available
```

### В коде программы

```python
from modules.telemetry import MSFSTelemetry

telemetry = MSFSTelemetry()
telemetry.connect()

# Получение информации
aircraft_info = telemetry.get_aircraft_info()

# Проверка совместимости
autopilot_type = aircraft_info['autopilot_type']

if autopilot_type in ['STANDARD', 'ADVANCED']:
    print("✅ Aircraft compatible with AutoLand")
    use_autopilot_commands = True
elif autopilot_type == 'BASIC':
    print("⚠️ Limited compatibility - some features unavailable")
    use_autopilot_commands = True
    use_vjoy_fallback = True
else:
    print("❌ Use vJoy for direct control")
    use_autopilot_commands = False
    use_vjoy_required = True
```

---

## Примеры самолётов

### Стандартные MSFS самолёты

**Cessna 172 Skyhawk:**
- Autopilot Type: BASIC
- Engine: Piston (1 engine)
- Compatibility: ⚠️ Limited (no NAV/Approach modes)

**Airbus A320neo:**
- Autopilot Type: STANDARD
- Engine: Jet (2 engines)
- Compatibility: ✅ Full

**Boeing 747-8:**
- Autopilot Type: STANDARD
- Engine: Jet (4 engines)
- Compatibility: ✅ Full

### Study-level аддоны

**PMDG 737:**
- Autopilot Type: ADVANCED (вероятно)
- Engine: Jet (2 engines)
- Compatibility: ✅ Full (кастомная логика)

**FlyByWire A32NX:**
- Autopilot Type: ADVANCED (вероятно)
- Engine: Jet (2 engines)
- Compatibility: ✅ Full (кастомная логика)

---

## Ограничения

⚠️ **Определение типа автопилота - эвристическое**

Система использует доступные SimConnect переменные для определения типа, но:

1. **Кастомные автопилоты** могут не полностью соответствовать стандартным переменным
2. **Study-level аддоны** часто имеют собственную логику, не видимую через SimConnect
3. **Максимальный крен** - приблизительный индикатор продвинутости

**Рекомендация:** Используйте тестовый скрипт для проверки конкретного самолёта перед использованием AutoLand системы.

---

## Интеграция в main.py

Информация о самолёте логируется при подключении:

```python
def connect(self):
    if self.telemetry.connect():
        # Получение информации о самолёте
        aircraft_info = self.telemetry.get_aircraft_info()
        
        logger.info(f"Aircraft: {aircraft_info['title']}")
        logger.info(f"Engine: {aircraft_info['engine_type_name']} "
                   f"({aircraft_info['number_of_engines']} engines)")
        logger.info(f"Autopilot: {aircraft_info['autopilot_type']}")
        
        # Адаптация поведения системы
        if aircraft_info['autopilot_type'] in ['STANDARD', 'ADVANCED']:
            self.use_autopilot = True
        else:
            self.use_autopilot = False
            logger.warning("Limited autopilot - using vJoy for control")
```

---

## Будущие улучшения

- [ ] База данных известных самолётов и их особенностей
- [ ] Автоматическая настройка параметров под тип самолёта
- [ ] Определение кастомных систем (PMDG, FBW, etc)
- [ ] Профили для разных типов автопилотов
- [ ] Предупреждения о несовместимости

---

**Система теперь может определить тип самолёта и автопилота!** ✈️
