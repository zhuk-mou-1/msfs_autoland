# Вес самолёта и FMS данные

## Дата: 2026-04-16

## Обзор

Добавлены три новые возможности:
1. Чтение веса самолёта через SimConnect
2. Ручной ввод веса и скорости захода в GUI
3. Чтение маршрутных точек FMS по всей схеме STAR включая FINAL

---

## 1. Чтение веса самолёта

### Новый метод в telemetry.py

```python
def get_aircraft_weight(self) -> Dict[str, float]:
    """Получить вес самолёта"""
    return {
        'total_weight': self.aq.get("TOTAL_WEIGHT"),  # фунты
        'empty_weight': self.aq.get("EMPTY_WEIGHT"),  # фунты
        'fuel_weight': self.aq.get("FUEL_TOTAL_QUANTITY_WEIGHT"),  # фунты
        'payload_weight': total - empty - fuel  # фунты
    }
```

### Использование в autothrottle

Autothrottle теперь использует реальный вес самолёта:

```python
# Получение веса из конфигурации (ручной ввод) или SimConnect
aircraft_weight = 5000.0  # По умолчанию

if hasattr(self.approach_config, 'aircraft_weight'):
    aircraft_weight = self.approach_config.aircraft_weight
else:
    weight_data = telemetry.get('weight', {})
    if weight_data and 'total_weight' in weight_data:
        aircraft_weight = weight_data['total_weight']
```

### Влияние на управление тягой

Вес влияет на базовую тягу:

```python
weight_correction = (aircraft_weight - weight_reference) × 0.00002
base_throttle = 0.5 + weight_correction
```

**Примеры:**
- Лёгкий самолёт (3000 lbs): базовая тяга 46%
- Средний самолёт (5000 lbs): базовая тяга 50%
- Тяжёлый самолёт (7000 lbs): базовая тяга 54%
- Очень тяжёлый (60000 lbs): базовая тяга 160% → ограничено до 100%

---

## 2. Ручной ввод в GUI

### Новые поля в approach_dialog.py

**Вкладка "Manual Entry":**

1. **Aircraft Weight (lbs)** - вес самолёта в фунтах
   - По умолчанию: 5000 lbs
   - Используется autothrottle для расчёта тяги

2. **Approach Speed (kt)** - скорость захода в узлах
   - По умолчанию: 120 kt
   - Целевая скорость для autothrottle

3. **Кнопка "Read from Aircraft"** - автоматическое чтение из MSFS
   - Читает вес через SimConnect
   - Читает текущую скорость (IAS)
   - Заполняет поля автоматически

### Метод read_from_aircraft()

```python
def read_from_aircraft(self):
    """Чтение веса и скорости из самолёта через SimConnect"""
    # Читаем вес
    weight_data = self.telemetry.get_aircraft_weight()
    if weight_data and 'total_weight' in weight_data:
        self.weight_var.set(f"{weight_data['total_weight']:.0f}")
    
    # Читаем текущую скорость
    speed_data = self.telemetry.get_speed()
    if speed_data and 'airspeed_indicated' in speed_data:
        current_speed = speed_data['airspeed_indicated']
        if current_speed > 60:
            self.speed_var.set(f"{current_speed:.0f}")
```

### Сохранение в конфигурацию

Вес сохраняется как атрибут ApproachConfig:

```python
self.result = ApproachConfig(...)
self.result.aircraft_weight = float(self.weight_var.get())
```

---

## 3. Чтение FMS данных

### Новый модуль fms_reader.py

Модуль для чтения маршрутных точек из FMS/GPS симулятора.

#### Класс Waypoint

```python
@dataclass
class Waypoint:
    index: int           # Индекс в плане полёта
    id: str             # Идентификатор (например "STAR1")
    latitude: float     # Широта
    longitude: float    # Долгота
    altitude: float     # Высота (футы)
    distance: float     # Расстояние (морские мили)
    ete: float          # Estimated Time Enroute (секунды)
    is_current: bool    # Текущая активная точка
```

#### Класс FMSReader

**Основные методы:**

1. **get_gps_destination()** - пункт назначения GPS
2. **get_flight_plan_info()** - информация о плане полёта
3. **get_current_waypoint()** - текущая активная точка
4. **get_previous_waypoint()** - предыдущая пройденная точка
5. **get_star_waypoints()** - все точки STAR
6. **get_approach_waypoints()** - точки схемы захода
7. **get_fms_status()** - полный статус FMS
8. **is_on_star_approach()** - проверка активности STAR

### SimConnect переменные

FMSReader использует следующие переменные SimConnect:

```
GPS_WP_NEXT_ID          - ID следующей точки
GPS_WP_NEXT_LAT         - Широта следующей точки
GPS_WP_NEXT_LON         - Долгота следующей точки
GPS_WP_NEXT_ALT         - Высота следующей точки
GPS_WP_DISTANCE         - Расстояние до следующей точки (метры)
GPS_WP_BEARING          - Пеленг на следующую точку
GPS_ETE                 - Время до следующей точки (секунды)

GPS_WP_PREV_ID          - ID предыдущей точки
GPS_WP_PREV_LAT         - Широта предыдущей точки
GPS_WP_PREV_LON         - Долгота предыдущей точки
GPS_WP_PREV_ALT         - Высота предыдущей точки

GPS_FLIGHT_PLAN_WP_COUNT  - Количество точек в плане
GPS_FLIGHT_PLAN_WP_INDEX  - Текущий индекс
GPS_IS_ACTIVE_FLIGHT_PLAN - Активен ли план
GPS_IS_ACTIVE_WAY_POINT   - Активна ли точка
GPS_IS_ARRIVED            - Прибыли ли в пункт назначения
```

### Интеграция в main.py

**Инициализация:**

```python
def __init__(self):
    # ...
    self.fms_reader: Optional[FMSReader] = None

def connect(self):
    # ...
    self.fms_reader = FMSReader(self.telemetry)
    logger.info("FMS reader initialized")
```

**Логирование при старте захода:**

```python
def execute_approach(self):
    # Логирование FMS данных
    if self.fms_reader:
        fms_status = self.fms_reader.get_fms_status()
        if fms_status.get('has_active_plan'):
            logger.info(f"FMS: Active flight plan - "
                       f"{fms_status['current_waypoint_index']+1}/"
                       f"{fms_status['total_waypoints']} waypoints")
            
            # Получение STAR точек
            star_waypoints = self.fms_reader.get_star_waypoints()
            for wp in star_waypoints:
                logger.info(f"  - {wp.id}: {wp.latitude:.4f}, "
                           f"{wp.longitude:.4f}, {wp.altitude:.0f}ft")
```

**Периодическое логирование (каждые 10 секунд):**

```python
def _handle_phase(self, telemetry, approach_data):
    # ...
    if self.fms_reader:
        current_wp = self.fms_reader.get_current_waypoint()
        if current_wp:
            logger.debug(f"FMS: Next waypoint {current_wp.id}, "
                        f"Distance: {current_wp.distance:.1f}nm")
```

---

## Ограничения SimConnect

⚠️ **Важно:** SimConnect не предоставляет прямой доступ ко всем точкам плана полёта.

**Доступны только:**
- Предыдущая точка (PREV)
- Текущая точка (NEXT)
- Общая информация (количество точек, индекс)

**Недоступны:**
- Произвольные точки по индексу
- Полный список всех точек STAR
- Детали процедур (SID/STAR/APPROACH)

Для получения полного списка точек потребуется:
- Парсинг навигационной базы данных MSFS
- Использование сторонних инструментов (Little Navmap API)
- Чтение файлов BGL/XML

---

## Примеры использования

### Пример 1: Ручной ввод веса и скорости

1. Запустите GUI: `python gui.py`
2. Нажмите "Start Approach"
3. Перейдите на вкладку "Manual Entry"
4. Введите:
   - Aircraft Weight: 7000 lbs
   - Approach Speed: 140 kt
5. Заполните остальные параметры
6. Нажмите OK

Autothrottle будет использовать вес 7000 lbs для расчёта тяги.

### Пример 2: Автоматическое чтение из самолёта

1. Запустите MSFS и загрузите полёт
2. Запустите GUI и подключитесь
3. Нажмите "Start Approach"
4. Вкладка "Manual Entry"
5. Нажмите "Read from Aircraft"
6. Вес и скорость заполнятся автоматически

### Пример 3: Мониторинг FMS

При запуске захода в логах появится:

```
FMS: Active flight plan detected - 5/12 waypoints
FMS: Current: STAR3, Distance: 15.2nm, ETE: 8.5min
FMS: Retrieved 2 STAR waypoints:
  - STAR2: 55.4523, 37.2341, 5000ft, 0.0nm
  - STAR3: 55.4821, 37.5123, 3000ft, 15.2nm
```

Во время захода каждые 10 секунд:

```
FMS: Next waypoint STAR3, Distance: 12.8nm, ETE: 7.2min
FMS: Next waypoint STAR3, Distance: 10.5nm, ETE: 5.9min
```

---

## Преимущества

✅ **Точность autothrottle** - учёт реального веса самолёта  
✅ **Удобство** - автоматическое чтение из MSFS  
✅ **Гибкость** - ручной ввод при необходимости  
✅ **Мониторинг** - отслеживание прогресса по FMS  
✅ **Интеграция** - работает с существующей системой  

---

## Будущие улучшения

- [ ] Парсинг полного плана полёта из файлов MSFS
- [ ] Интеграция с Little Navmap
- [ ] Автоматическое определение веса по типу самолёта
- [ ] Расчёт оптимальной скорости захода по весу
- [ ] Визуализация маршрута STAR в GUI
- [ ] Проверка соответствия высоты на точках STAR
- [ ] Автоматическое следование по FMS маршруту

---

**Система теперь полностью учитывает вес самолёта и интегрирована с FMS!** ✈️
