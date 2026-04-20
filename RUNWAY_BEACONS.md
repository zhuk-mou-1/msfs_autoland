# Система проверки приводов ВПП (Runway Beacons)

## Обзор

Система автоматической проверки пролёта дальнего и ближнего приводов ВПП для VOR/NDB заходов. Контролирует высоту, курс и скорость при снижении по глиссаде.

**Файл:** `modules/navigation.py` (новые классы и методы)  
**Дата создания:** 2026-04-17

## Что такое приводы ВПП?

**Приводы ВПП** - это радиомаяки NDB, установленные на продолжении оси ВПП для обеспечения точного захода на посадку при отсутствии ILS.

### Типы приводов

| Тип | Название | Расстояние | Высота | Назначение |
|-----|----------|------------|--------|------------|
| **ДПРМ** | Дальний Привод | 4-7 NM | 1400-2000 ft AGL | Начало снижения |
| **БПРМ** | Ближний Привод | 0.5-1.5 NM | 200-400 ft AGL | Контроль финала |

### Отличия от ILS маркеров

| Параметр | Приводы NDB | ILS Маркеры |
|----------|-------------|-------------|
| Тип сигнала | Радиомаяк NDB | Маркерный радиомаяк |
| Частота | 190-1750 кГц | 75 МГц |
| Применение | VOR/NDB/RNAV заходы | Только ILS |
| Навигация | Пеленг (ADF) | Вертикальный луч |
| Идентификация | Морзе код | Тональный сигнал |

## Классы данных

### RunwayBeacon

```python
@dataclass
class RunwayBeacon:
    """Привод ВПП"""
    name: str  # Название (например, "ШР", "ВН")
    beacon_type: str  # 'OUTER' или 'INNER'
    latitude: float
    longitude: float
    frequency: int  # кГц
    distance_from_threshold_nm: float
    expected_altitude_agl: float
    tolerance_altitude_ft: float = 300.0  # Допуск по высоте
    tolerance_course_deg: float = 5.0  # Допуск по курсу
    passed: bool = False
    pass_timestamp: float = 0.0
```

### BeaconCheckResult

```python
@dataclass
class BeaconCheckResult:
    """Результат проверки при пролёте привода"""
    beacon_name: str
    beacon_type: str
    passed_beacon: bool
    distance_to_beacon_nm: float
    altitude_ok: bool
    current_altitude_agl: float
    expected_altitude_agl: float
    altitude_error_ft: float
    course_ok: bool
    current_course: float
    expected_course: float
    course_error_deg: float
    speed_ok: bool
    current_speed: float
    status: str  # 'OK', 'WARNING', 'CRITICAL'
    violations: list
    recommendations: list
    timestamp: float
```

## Методы

### 1. calculate_runway_beacons()

Автоматический расчёт позиций приводов на основе параметров ВПП.

```python
beacons = navigation.calculate_runway_beacons(
    runway_threshold_lat=55.9728,
    runway_threshold_lon=37.4106,
    runway_heading=244,
    runway_elevation=622,
    glideslope_angle=3.0,
    outer_distance_nm=5.0,  # Дальний привод на 5 NM
    inner_distance_nm=1.0   # Ближний привод на 1 NM
)

# Результат:
{
    'outer': RunwayBeacon(
        name='OUTER',
        beacon_type='OUTER',
        latitude=55.9895,
        longitude=37.5234,
        distance_from_threshold_nm=5.0,
        expected_altitude_agl=1591.0,  # ~1600 футов
        tolerance_altitude_ft=300.0,
        tolerance_course_deg=5.0
    ),
    'inner': RunwayBeacon(
        name='INNER',
        beacon_type='INNER',
        latitude=55.9779,
        longitude=37.4547,
        distance_from_threshold_nm=1.0,
        expected_altitude_agl=318.0,  # ~300 футов
        tolerance_altitude_ft=200.0,
        tolerance_course_deg=3.0
    )
}
```

### 2. check_beacon_passage()

Проверка пролёта привода и параметров захода.

```python
# В основном цикле execute_approach()
telemetry = self.telemetry.get_all_data()

check_result = navigation.check_beacon_passage(
    current_lat=telemetry['position']['latitude'],
    current_lon=telemetry['position']['longitude'],
    current_altitude_agl=telemetry['position']['altitude_agl'],
    current_heading=telemetry['attitude']['heading_magnetic'],
    current_speed=telemetry['speed']['airspeed_indicated'],
    beacon=outer_beacon,
    expected_course=244,  # Курс ВПП
    min_speed=90.0,
    max_speed=160.0
)

# Результат:
BeaconCheckResult(
    beacon_name='OUTER',
    beacon_type='OUTER',
    passed_beacon=True,  # Пролетели привод
    distance_to_beacon_nm=0.2,
    altitude_ok=True,
    current_altitude_agl=1650.0,
    expected_altitude_agl=1591.0,
    altitude_error_ft=59.0,  # Немного высоко
    course_ok=True,
    current_course=242.0,
    expected_course=244.0,
    course_error_deg=-2.0,
    speed_ok=True,
    current_speed=120.0,
    status='OK',
    violations=[],
    recommendations=['Begin descent on glideslope', 'Configure aircraft for landing'],
    timestamp=1713364794.193
)
```

## Проверки при пролёте приводов

### Дальний привод (OUTER)

**Проверяется:**
- ✅ Высота: 1400-2000 ft AGL (±300 ft)
- ✅ Курс: отклонение < 5°
- ✅ Скорость: 90-160 узлов
- ✅ Расстояние до привода < 0.3 NM

**Рекомендации при OK:**
- Begin descent on glideslope
- Configure aircraft for landing

**Действия при нарушениях:**
- Too high → Increase descent rate
- Too low → CRITICAL: Reduce descent rate or go around
- Course deviation → Correct course to runway heading
- Speed issues → Adjust speed or check configuration

### Ближний привод (INNER)

**Проверяется:**
- ✅ Высота: 200-400 ft AGL (±200 ft)
- ✅ Курс: отклонение < 3° (строже!)
- ✅ Скорость: 90-160 узлов
- ✅ Расстояние до привода < 0.3 NM

**Рекомендации при OK:**
- Continue to landing
- Prepare for flare

**Действия при нарушениях:**
- CRITICAL status → GO AROUND - Unstabilized approach

## Интеграция в main.py

### Настройка приводов

```python
def configure_approach(self, runway_data: dict):
    """Настройка параметров захода"""
    
    # Расчёт приводов
    self.runway_beacons = self.navigation.calculate_runway_beacons(
        runway_threshold_lat=runway_data['threshold_lat'],
        runway_threshold_lon=runway_data['threshold_lon'],
        runway_heading=runway_data['heading'],
        runway_elevation=runway_data['elevation'],
        glideslope_angle=runway_data.get('glideslope_angle', 3.0),
        outer_distance_nm=runway_data.get('outer_beacon_distance', 5.0),
        inner_distance_nm=runway_data.get('inner_beacon_distance', 1.0)
    )
    
    # Установка частот из конфигурации (если есть)
    if 'outer_beacon_freq' in runway_data:
        self.runway_beacons['outer'].frequency = runway_data['outer_beacon_freq']
        self.runway_beacons['outer'].name = runway_data.get('outer_beacon_name', 'OUTER')
    
    if 'inner_beacon_freq' in runway_data:
        self.runway_beacons['inner'].frequency = runway_data['inner_beacon_freq']
        self.runway_beacons['inner'].name = runway_data.get('inner_beacon_name', 'INNER')
    
    logger.info(f"Runway beacons configured:")
    logger.info(f"  Outer: {self.runway_beacons['outer'].name} at "
                f"{self.runway_beacons['outer'].distance_from_threshold_nm:.1f} NM, "
                f"expected altitude {self.runway_beacons['outer'].expected_altitude_agl:.0f} ft")
    logger.info(f"  Inner: {self.runway_beacons['inner'].name} at "
                f"{self.runway_beacons['inner'].distance_from_threshold_nm:.1f} NM, "
                f"expected altitude {self.runway_beacons['inner'].expected_altitude_agl:.0f} ft")
```

### Проверка в цикле захода

```python
def execute_approach(self):
    """Выполнение захода"""
    
    while self.running and self.phase != ApproachPhase.COMPLETED:
        # Получение телеметрии
        telemetry = self.telemetry.get_all_data()
        
        # Проверка дальнего привода
        if not self.runway_beacons['outer'].passed:
            outer_check = self.navigation.check_beacon_passage(
                current_lat=telemetry['position']['latitude'],
                current_lon=telemetry['position']['longitude'],
                current_altitude_agl=telemetry['position']['altitude_agl'],
                current_heading=telemetry['attitude']['heading_magnetic'],
                current_speed=telemetry['speed']['airspeed_indicated'],
                beacon=self.runway_beacons['outer'],
                expected_course=self.approach_config.final_approach_course
            )
            
            if outer_check.passed_beacon:
                self.runway_beacons['outer'].passed = True
                self.runway_beacons['outer'].pass_timestamp = outer_check.timestamp
                
                logger.info(f"OUTER BEACON PASSED: {outer_check.beacon_name}")
                logger.info(f"  Status: {outer_check.status}")
                logger.info(f"  Altitude: {outer_check.current_altitude_agl:.0f} ft "
                           f"(expected {outer_check.expected_altitude_agl:.0f} ft, "
                           f"error {outer_check.altitude_error_ft:+.0f} ft)")
                logger.info(f"  Course: {outer_check.current_course:.0f}° "
                           f"(expected {outer_check.expected_course:.0f}°, "
                           f"error {outer_check.course_error_deg:+.1f}°)")
                
                if outer_check.violations:
                    logger.warning(f"  Violations: {', '.join(outer_check.violations)}")
                
                for rec in outer_check.recommendations:
                    logger.info(f"  → {rec}")
                
                # Переход в фазу FINAL если всё OK
                if outer_check.status == 'OK' and self.phase == ApproachPhase.INTERMEDIATE:
                    self.phase = ApproachPhase.FINAL
                    logger.info("Transitioning to FINAL phase")
        
        # Проверка ближнего привода
        if not self.runway_beacons['inner'].passed and self.phase == ApproachPhase.FINAL:
            inner_check = self.navigation.check_beacon_passage(
                current_lat=telemetry['position']['latitude'],
                current_lon=telemetry['position']['longitude'],
                current_altitude_agl=telemetry['position']['altitude_agl'],
                current_heading=telemetry['attitude']['heading_magnetic'],
                current_speed=telemetry['speed']['airspeed_indicated'],
                beacon=self.runway_beacons['inner'],
                expected_course=self.approach_config.final_approach_course
            )
            
            if inner_check.passed_beacon:
                self.runway_beacons['inner'].passed = True
                self.runway_beacons['inner'].pass_timestamp = inner_check.timestamp
                
                logger.info(f"INNER BEACON PASSED: {inner_check.beacon_name}")
                logger.info(f"  Status: {inner_check.status}")
                logger.info(f"  Altitude: {inner_check.current_altitude_agl:.0f} ft")
                
                if inner_check.status == 'CRITICAL':
                    logger.critical("UNSTABILIZED APPROACH - GO AROUND RECOMMENDED")
                    # Можно автоматически инициировать уход на второй круг
                
                for rec in inner_check.recommendations:
                    logger.info(f"  → {rec}")
```

## Визуализация в GUI

```python
# В create_navigation_panel
ttk.Label(parent, text="Outer Beacon:").grid(row=row, column=0, sticky=tk.W)
self.outer_beacon_var = tk.StringVar(value="--")
self.outer_beacon_label = ttk.Label(parent, textvariable=self.outer_beacon_var)
self.outer_beacon_label.grid(row=row, column=1, sticky=tk.E)
row += 1

ttk.Label(parent, text="Inner Beacon:").grid(row=row, column=0, sticky=tk.W)
self.inner_beacon_var = tk.StringVar(value="--")
self.inner_beacon_label = ttk.Label(parent, textvariable=self.inner_beacon_var)
self.inner_beacon_label.grid(row=row, column=1, sticky=tk.E)
row += 1

# В update_display
if hasattr(self.system, 'runway_beacons'):
    # Дальний привод
    outer = self.system.runway_beacons['outer']
    if outer.passed:
        self.outer_beacon_var.set(f"✓ PASSED")
        self.outer_beacon_label.config(foreground='green')
    else:
        telemetry = self.system.telemetry.get_all_data()
        dist = self.system.navigation.calculate_distance(
            telemetry['position']['latitude'],
            telemetry['position']['longitude'],
            outer.latitude,
            outer.longitude
        )
        self.outer_beacon_var.set(f"{dist:.1f} NM")
        
        # Цветовая индикация по расстоянию
        if dist < 1.0:
            self.outer_beacon_label.config(foreground='yellow')
        else:
            self.outer_beacon_label.config(foreground='white')
    
    # Ближний привод
    inner = self.system.runway_beacons['inner']
    if inner.passed:
        self.inner_beacon_var.set(f"✓ PASSED")
        self.inner_beacon_label.config(foreground='green')
    else:
        dist = self.system.navigation.calculate_distance(
            telemetry['position']['latitude'],
            telemetry['position']['longitude'],
            inner.latitude,
            inner.longitude
        )
        self.inner_beacon_var.set(f"{dist:.1f} NM")
        
        if dist < 0.5:
            self.inner_beacon_label.config(foreground='yellow')
        else:
            self.inner_beacon_label.config(foreground='white')
```

## Примеры аэропортов с приводами

### UUEE (Шереметьево) RWY 24L

```python
runway_data = {
    'threshold_lat': 55.9728,
    'threshold_lon': 37.4106,
    'heading': 244,
    'elevation': 622,
    'glideslope_angle': 3.0,
    'outer_beacon_distance': 6.0,
    'outer_beacon_freq': 525,  # кГц
    'outer_beacon_name': 'ШР',  # Шереметьево
    'inner_beacon_distance': 1.0,
    'inner_beacon_freq': 490,
    'inner_beacon_name': 'ВН'  # Внутренний
}
```

### UUWW (Внуково) RWY 24

```python
runway_data = {
    'threshold_lat': 55.5914,
    'threshold_lon': 37.2615,
    'heading': 240,
    'elevation': 685,
    'glideslope_angle': 3.0,
    'outer_beacon_distance': 5.0,
    'outer_beacon_name': 'ВК',  # Внуково
    'inner_beacon_distance': 1.0
}
```

## Статусы проверки

| Статус | Условие | Действие |
|--------|---------|----------|
| **OK** | Все параметры в норме | Продолжить заход |
| **WARNING** | 1 нарушение, высота OK | Скорректировать параметр |
| **CRITICAL** | Множественные нарушения или высота не OK | Рассмотреть уход на второй круг |

## Рекомендации

### Для дальнего привода (OUTER):

✅ **При OK:**
- Начать снижение по глиссаде
- Настроить конфигурацию самолёта (закрылки)
- Стабилизировать скорость

⚠️ **При WARNING:**
- Скорректировать отклонившийся параметр
- Продолжить мониторинг

🔴 **При CRITICAL:**
- Если слишком низко → немедленно уменьшить снижение или уйти на второй круг
- Если множественные нарушения → рассмотреть уход на второй круг

### Для ближнего привода (INNER):

✅ **При OK:**
- Продолжить к посадке
- Подготовиться к выравниванию

🔴 **При CRITICAL:**
- **ОБЯЗАТЕЛЬНО** уход на второй круг
- Нестабилизированный заход опасен

## Тестирование

```python
# Тест 1: Расчёт приводов
beacons = navigation.calculate_runway_beacons(
    runway_threshold_lat=55.0,
    runway_threshold_lon=37.0,
    runway_heading=270,
    runway_elevation=500,
    glideslope_angle=3.0,
    outer_distance_nm=5.0,
    inner_distance_nm=1.0
)

assert beacons['outer'].distance_from_threshold_nm == 5.0
assert beacons['inner'].distance_from_threshold_nm == 1.0
assert beacons['outer'].expected_altitude_agl > 1500
assert beacons['inner'].expected_altitude_agl > 300

# Тест 2: Проверка пролёта (OK)
check = navigation.check_beacon_passage(
    current_lat=beacons['outer'].latitude,
    current_lon=beacons['outer'].longitude,
    current_altitude_agl=1600.0,
    current_heading=270.0,
    current_speed=120.0,
    beacon=beacons['outer'],
    expected_course=270.0
)

assert check.passed_beacon == True
assert check.status == 'OK'
assert len(check.violations) == 0

# Тест 3: Проверка нарушений (слишком низко)
check = navigation.check_beacon_passage(
    current_lat=beacons['outer'].latitude,
    current_lon=beacons['outer'].longitude,
    current_altitude_agl=1000.0,  # Слишком низко!
    current_heading=270.0,
    current_speed=120.0,
    beacon=beacons['outer'],
    expected_course=270.0
)

assert check.status == 'CRITICAL'
assert 'Too low' in check.violations[0]
assert 'go around' in check.recommendations[0].lower()
```

---

**Создано:** 2026-04-17  
**Автор:** Claude (Sonnet 4)  
**Проект:** MSFS AutoLand System
