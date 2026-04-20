# Работа с дальномером (DME)

## Обзор

Модуль DME Navigation предоставляет полный набор функций для работы с дальномером (Distance Measuring Equipment) в системе автоматической посадки.

## Возможности

### 1. Использование DME вместо GPS расстояния

DME данные автоматически используются для определения расстояния до станции:

```python
# DME автоматически считывается из MSFS
dme_distance = telemetry['nav']['nav1_dme_distance']

# Проверка точности DME
dme_check = dme_navigation.check_dme_accuracy(dme_distance, calculated_distance)
```

**Преимущества:**
- Точнее GPS для VOR/DME заходов
- Независимо от GPS
- Стандарт авиационной навигации

---

### 2. Контрольные точки DME (DME Fixes)

Определение контрольных точек по расстоянию и высоте:

```python
from modules.dme_navigation import DMEFix

# Создание контрольных точек
fixes = [
    DMEFix(distance=15.0, altitude=5000, name="OUTER"),
    DMEFix(distance=10.0, altitude=3500, name="MIDDLE"),
    DMEFix(distance=5.0, altitude=2000, name="INNER"),
]

# Добавление в систему
system.add_dme_fixes(fixes)
```

**Автоматическая проверка:**
- Система проверяет высоту на каждой точке
- Предупреждения при отклонении > 200 футов
- Критические предупреждения при отклонении > 400 футов

**Пример лога:**
```
Fix OUTER: Required 5000ft, Current 5150ft, Deviation +150ft - OK
Fix MIDDLE: Required 3500ft, Current 3200ft, Deviation -300ft - DEVIATION
```

---

### 3. Профили снижения по DME

Автоматический расчёт требуемой вертикальной скорости для достижения высоты на DME:

```python
# Расчёт требуемой VS для достижения 2000ft на 5 DME
required_vs = dme_navigation.calculate_required_vs_for_dme(
    ground_speed=120,      # узлы
    current_dme=10.0,      # текущее DME
    target_dme=5.0,        # целевое DME
    altitude_to_lose=1500  # футы
)
# Результат: ~600 fpm
```

**Расчёт профиля снижения:**
```python
profile = dme_navigation.calculate_descent_profile(
    current_dme=10.0,
    current_altitude=3500,
    target_dme=5.0,
    target_altitude=2000
)
# Возвращает: угол снижения, расстояние, высоту для потери
```

---

### 4. DME Arc заходы

Полёт по дуге на постоянном расстоянии от станции:

```python
from modules.dme_navigation import DMEArcConfig

# Конфигурация дуги
arc_config = DMEArcConfig(
    arc_radius=10.0,           # радиус дуги (морские мили)
    arc_start_radial=090,      # начальный радиал
    arc_end_radial=270,        # конечный радиал
    arc_altitude=3000,         # высота на дуге
    final_approach_radial=270  # радиал для перехода на финал
)

# Расчёт позиции на дуге
arc_position = dme_navigation.calculate_dme_arc_position(
    current_dme=10.2,
    current_radial=180,
    config=arc_config
)

# Расчёт курса для следования по дуге
arc_heading = dme_navigation.calculate_arc_heading(
    current_radial=180,
    arc_radius=10.0,
    turn_direction='right'  # или 'left'
)
```

**Параметры дуги:**
- `on_arc` - находимся ли на дуге
- `radius_error` - отклонение от радиуса (морские мили)
- `radials_to_go` - градусов до конца дуги
- `arc_distance_to_go` - расстояние по дуге (морские мили)
- `should_turn_inbound` - пора ли разворачиваться на финал

---

### 5. DME Hold (ожидание)

Удержание на заданном расстоянии от станции:

```python
hold_params = dme_navigation.calculate_dme_hold(
    current_dme=15.5,
    hold_distance=15.0,
    current_heading=270,
    station_bearing=090
)

# Действия:
# - MAINTAIN: удерживать текущий курс
# - TURN_TOWARDS: лететь к станции
# - TURN_AWAY: лететь от станции
```

**Использование:**
- Ожидание разрешения на заход
- Удержание на заданной дистанции
- Допуск ±0.2 морские мили

---

## Проверка точности DME

Автоматическое сравнение DME с расчётным расстоянием:

```python
accuracy = dme_navigation.check_dme_accuracy(
    dme_distance=10.5,
    calculated_distance=10.3,
    tolerance=0.5  # морские мили
)

# Статусы:
# - OK: расхождение < 0.5nm
# - WARNING: расхождение 0.5-1.0nm
# - CRITICAL: расхождение > 1.0nm
```

---

## Пример полного захода с DME

```python
from modules.dme_navigation import DMEFix

# 1. Создание системы
system = AutoLandSystem()
system.connect()

# 2. Настройка захода
config = ApproachConfig(
    station=NavStation(
        name="Moscow VOR/DME",
        frequency=11030000,
        latitude=55.5,
        longitude=37.5,
        type='VOR'
    ),
    final_approach_course=270,
    glideslope_angle=3.0,
    decision_height=200,
    approach_speed=120,
    runway_elevation=500,
    runway_length=8000,
    runway_width=150,
    runway_threshold_lat=55.48,
    runway_threshold_lon=37.52
)

# 3. Добавление DME контрольных точек
dme_fixes = [
    DMEFix(distance=20.0, altitude=6000, name="IAF"),      # Initial Approach Fix
    DMEFix(distance=15.0, altitude=5000, name="OUTER"),
    DMEFix(distance=10.0, altitude=3500, name="MIDDLE"),
    DMEFix(distance=5.0, altitude=2000, name="FAF"),       # Final Approach Fix
]
system.add_dme_fixes(dme_fixes)

# 4. Настройка и запуск
system.configure_approach(config)
system.start_approach()
system.execute_approach()
```

---

## Логи с DME

Примеры логов во время захода:

```
INITIAL: DME 18.5nm, XTE 2.3°, Wind: 15kt from 320°, Crosswind: 8.5kt
INTERMEDIATE: DME 12.3nm, Alt 4200ft (req 4000ft), Headwind: 12.5kt, Fix: OUTER (OK, +200ft)
FINAL: Distance to threshold 3.50nm, Radio height 1800ft, Crosswind: 8.5kt, Crab: 4.2°, VS: 650 fpm, Runway: OK (2500ft margin)
```

---

## Рекомендации

1. **Всегда добавляйте DME контрольные точки** для контроля профиля снижения
2. **Проверяйте точность DME** перед критическими фазами
3. **Используйте DME вместо GPS** для точных заходов
4. **DME Arc заходы** требуют практики - начните с простых VOR заходов
5. **Следите за предупреждениями** о расхождении высоты на контрольных точках

---

## Ограничения

- DME работает только если станция оборудована дальномером
- Максимальная дальность DME обычно ~200nm
- Точность DME снижается на больших расстояниях
- DME Arc заходы сложнее обычных VOR заходов

---

## Типичные DME контрольные точки

### Для лёгких самолётов (Cessna 172):
```python
DMEFix(distance=15.0, altitude=4000, name="OUTER"),
DMEFix(distance=10.0, altitude=3000, name="MIDDLE"),
DMEFix(distance=5.0, altitude=1500, name="FAF"),
```

### Для средних самолётов (Boeing 737):
```python
DMEFix(distance=25.0, altitude=8000, name="IAF"),
DMEFix(distance=20.0, altitude=6000, name="OUTER"),
DMEFix(distance=15.0, altitude=5000, name="MIDDLE"),
DMEFix(distance=10.0, altitude=3500, name="INNER"),
DMEFix(distance=5.0, altitude=2000, name="FAF"),
```
