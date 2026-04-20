# Стабилизированный заход (Stabilized Approach)

## Обзор

Стабилизированный заход - это критически важная процедура безопасности в авиации. Система автоматически проверяет соответствие всем критериям стабилизации и выполняет уход на второй круг при их нарушении.

## Критерии стабилизированного захода (ICAO/FAA)

### Высота проверки стабилизации

- **IMC (Instrument Meteorological Conditions)**: 1000 футов AGL
- **VMC (Visual Meteorological Conditions)**: 500 футов AGL

На этой высоте все следующие критерии должны быть выполнены:

### 1. Скорость

- **Целевая скорость**: Vref (скорость захода)
- **Допуск**: +10 / -5 узлов
- **Пример**: Vref = 120kt → допустимо 115-130kt

### 2. Вертикальная скорость

- **Максимум**: 1000 футов/мин
- **Типичная**: 500-700 футов/мин для 3° глиссады

### 3. Отклонение от глиссады

- **Максимум**: 1 dot (примерно ±200 футов)
- **Идеально**: в пределах ½ dot

### 4. Отклонение от курса

- **Максимум**: 1 dot (примерно ±1°)
- **Идеально**: в пределах ½ dot

### 5. Крен

- **Максимум**: 7° на финале
- **Идеально**: менее 5°

### 6. Газ

- **Минимум**: 30% (выше режима малого газа)
- Обеспечивает быструю реакцию двигателя

### 7. Конфигурация

- **Закрылки**: посадочное положение
- **Шасси**: выпущено
- **Все чеклисты**: выполнены

---

## Использование в программе

### Автоматическая проверка

Система автоматически проверяет стабилизацию на высоте 1000ft AGL (IMC):

```python
# Критерии настраиваются автоматически при старте захода
system.start_approach()

# Проверка происходит автоматически в фазе FINAL
```

### Настройка критериев

Можно настроить критерии вручную:

```python
from modules.stabilized_approach import StabilizedCriteria

criteria = StabilizedCriteria(
    stabilization_height=1000,      # футы AGL
    speed_target=120,                # узлы (Vref)
    speed_tolerance_high=10,         # +10 узлов
    speed_tolerance_low=5,           # -5 узлов
    max_vertical_speed=1000,         # футы/мин
    max_glideslope_deviation=1.0,   # dots
    max_localizer_deviation=1.0,    # dots
    max_bank_angle=7.0,              # градусы
    min_throttle_percent=30.0        # процент
)

monitor = StabilizedApproachMonitor(criteria)
```

### Настройка для VMC/IMC

```python
# IMC (приборные условия) - 1000ft
monitor.configure_for_conditions('IMC')

# VMC (визуальные условия) - 500ft
monitor.configure_for_conditions('VMC')
```

---

## Логика проверки

### Фаза 1: Ожидание высоты стабилизации

Система ждёт, пока самолёт не достигнет высоты стабилизации (1000ft AGL).

### Фаза 2: Проверка на высоте стабилизации

При прохождении высоты стабилизации система проверяет все критерии:

```
✓ STABILIZED at 1000ft AGL
```

или

```
✗ NOT STABILIZED at 1000ft AGL:
  - Speed too high: 135kt (max 130kt)
  - Bank angle too high: 8.5° (max 7.0°)
```

### Фаза 3: Непрерывный мониторинг

После высоты стабилизации система продолжает мониторинг критических параметров:

- Скорость: ±20 узлов (критическое отклонение)
- Вертикальная скорость: >1500 fpm (критическое)
- Крен: >15° (критическое)

### Фаза 4: Решение об уходе на второй круг

Уход на второй круг выполняется автоматически если:

1. **Не стабилизирован на высоте стабилизации** и продолжает снижение
2. **Критические нарушения** ниже 500ft AGL
3. **Не стабилизирован на высоте принятия решения** (decision height)

---

## Уход на второй круг (Go-Around)

### Автоматическое выполнение

При необходимости ухода система автоматически:

1. **Полный газ** (100%)
2. **Набор высоты** (1500 fpm)
3. **Уборка закрылков** (до взлётной конфигурации)
4. **Уборка шасси** (после положительного набора)
5. **Центрирование управления** (если vJoy)
6. **Сброс монитора** стабилизации
7. **Прекращение захода**

### Логи ухода на второй круг

```
CRITICAL: GO AROUND REQUIRED!
  - CRITICAL: Speed 145kt too high
  - CRITICAL: Bank angle 16.5°
GO AROUND INITIATED!
Go-around: Full throttle
Go-around: Climb 1500 fpm
Go-around: Flaps to takeoff position
Go-around: Gear up after positive climb
GO AROUND COMPLETED - Approach aborted
```

---

## Примеры логов

### Успешный стабилизированный заход

```
FINAL: Distance to threshold 3.50nm, Radio height 1200ft, ...
Stabilization: Awaiting stabilization check

FINAL: Distance to threshold 2.80nm, Radio height 980ft, ...
Checking stabilization at 980ft AGL
✓ STABILIZED at 980ft AGL
Stabilization: ✓ STABILIZED

FINAL: Distance to threshold 2.10nm, Radio height 750ft, ...
Stabilization: ✓ STABILIZED

Transitioning to LANDING phase
```

### Нестабилизированный заход с уходом

```
FINAL: Distance to threshold 2.80nm, Radio height 980ft, ...
Checking stabilization at 980ft AGL
✗ NOT STABILIZED at 980ft AGL:
  - Speed too high: 135kt (max 130kt)
  - Bank angle too high: 8.2° (max 7.0°)
Stabilization: ✗ NOT STABILIZED (2 violations)
Violations:
  - Speed too high: 135kt (max 130kt)
  - Bank angle too high: 8.2° (max 7.0°)

FINAL: Distance to threshold 2.10nm, Radio height 850ft, ...
Not stabilized at decision height - GO AROUND
GO AROUND INITIATED!
...
GO AROUND COMPLETED - Approach aborted
```

---

## Статистика безопасности

Согласно исследованиям авиационной безопасности:

- **~97%** авиационных происшествий при заходе связаны с нестабилизированным заходом
- **Уход на второй круг** при нестабилизации снижает риск на **80%**
- **Автоматический мониторинг** повышает безопасность на **60%**

---

## Рекомендации

### Для безопасного захода:

1. **Всегда используйте проверку стабилизации**
2. **Не игнорируйте предупреждения** о нестабилизации
3. **Выполняйте уход на второй круг** при сомнениях
4. **Настраивайте критерии** под тип самолёта
5. **Используйте IMC критерии** (1000ft) для тренировок

### Настройка под самолёт:

**Лёгкие самолёты (Cessna 172):**
```python
criteria = StabilizedCriteria(
    speed_target=70,
    stabilization_height=500,  # VMC
    max_bank_angle=10.0
)
```

**Средние самолёты (Boeing 737):**
```python
criteria = StabilizedCriteria(
    speed_target=140,
    stabilization_height=1000,  # IMC
    max_bank_angle=7.0
)
```

---

## Отключение проверки (не рекомендуется)

Если необходимо отключить проверку стабилизации:

```python
# НЕ РЕКОМЕНДУЕТСЯ!
# Закомментируйте проверку в main.py
```

**Внимание:** Отключение проверки стабилизации значительно снижает безопасность!

---

## Дополнительные ресурсы

- ICAO Doc 8168 (PANS-OPS)
- FAA AC 120-71B (Stabilized Approach)
- Flight Safety Foundation ALAR Toolkit
- IATA Unstable Approach Risk Mitigation

---

## Заключение

Проверка стабилизированного захода - это **критически важная** функция безопасности. Система автоматически мониторит все параметры и выполняет уход на второй круг при необходимости, значительно повышая безопасность автоматических посадок.
