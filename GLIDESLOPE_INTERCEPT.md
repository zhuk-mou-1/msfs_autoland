# Расчёт точки входа в глиссаду (Glideslope Intercept Point)

## Обзор

Система расчёта точки входа в глиссаду позволяет определить:
- Где на посадочной прямой начинать снижение
- Идеальную высоту для текущей позиции
- Момент перехода в фазу FINAL (снижение по глиссаде)

**Поддержка нестандартных углов глиссады:** от 2.5° до 10°+

**Файл:** `modules/navigation.py` (новые методы)  
**Дата создания:** 2026-04-17

## Углы глиссады

### Стандартные углы

| Угол | Категория | Применение | Футов/миля |
|------|-----------|------------|------------|
| **3.0°** | STANDARD | Большинство аэропортов (ICAO стандарт) | 318 |
| **3.2°** | STANDARD | Некоторые аэропорты | 340 |

### Нестандартные углы

| Угол | Категория | Применение | Футов/миля | Примеры |
|------|-----------|------------|------------|---------|
| **3.5°** | STEEP | Препятствия, шумоподавление | 371 | Многие европейские аэропорты |
| **4.0°** | STEEP | Горные аэропорты | 424 | Innsbruck (LOWI) |
| **4.5°** | VERY_STEEP | Сложный рельеф | 477 | Некоторые альпийские аэропорты |
| **5.0°** | VERY_STEEP | Экстремальные условия | 531 | Paro (VQPR), Bhutan |
| **5.5°** | EXTREME | Требует спец. сертификации | 585 | London City (EGLC) |
| **6.0°+** | EXTREME | Очень редко | 638+ | Lugano (LSZA), Courchevel |

### Требуемая вертикальная скорость

Зависит от путевой скорости и угла глиссады:

**Формула:** VS = GS × tan(angle) × 101.3

| Угол | 90 узлов | 120 узлов | 150 узлов |
|------|----------|-----------|-----------|
| 3.0° | 475 fpm | 634 fpm | 792 fpm |
| 3.5° | 554 fpm | 739 fpm | 924 fpm |
| 4.0° | 633 fpm | 844 fpm | 1055 fpm |
| 5.0° | 792 fpm | 1056 fpm | 1320 fpm |
| 5.5° | 871 fpm | 1162 fpm | 1452 fpm |

## Методы

### 1. calculate_glideslope_distance()

Расчёт расстояния по глиссаде для заданной высоты.

```python
distance_nm = navigation.calculate_glideslope_distance(
    altitude_above_threshold=2000.0,  # футы
    glideslope_angle=3.0  # градусы
)
# Результат: 6.29 NM для 3°
# Результат: 5.39 NM для 3.5°
# Результат: 4.72 NM для 4°
```

**Формула:**
```python
distance_feet = altitude / tan(angle)
distance_nm = distance_feet / 6076.12
```

### 2. calculate_glideslope_intercept_point()

Вычисление координат точки входа в глиссаду.

```python
intercept = navigation.calculate_glideslope_intercept_point(
    runway_threshold_lat=55.9728,
    runway_threshold_lon=37.4106,
    runway_heading=244,
    runway_elevation=622,
    glideslope_angle=3.5,  # Нестандартный угол!
    intercept_altitude_agl=2000.0
)

# Результат:
{
    'latitude': 55.9891,
    'longitude': 37.5198,
    'distance_from_threshold_nm': 5.39,
    'altitude_agl': 2000.0,
    'altitude_msl': 2622.0,
    'glideslope_angle': 3.5,
    'runway_heading': 244,
    'feet_per_nm': 371.0
}
```

### 3. should_start_descent()

Определение момента начала снижения.

```python
descent_check = navigation.should_start_descent(
    current_lat=55.9850,
    current_lon=37.5150,
    current_altitude_agl=2100.0,
    intercept_point=intercept,
    tolerance_nm=0.5
)

# Результат:
{
    'should_descend': True,
    'distance_to_intercept_nm': 0.3,
    'ideal_altitude_agl': 2000.0,
    'altitude_error_ft': 100.0,
    'vertical_deviation_dots': 0.8,
    'reason': 'Reached glideslope intercept point (0.3 NM)',
    'status': 'INTERCEPT',
    'glideslope_angle': 3.5
}
```

**Статусы:**
- `INTERCEPT` - достигли точки входа
- `ON_PROFILE` - на правильной высоте
- `HIGH` - слишком высоко (>300 футов)
- `LOW` - слишком низко (<-300 футов) - ОПАСНО!
- `DEVIATION` - небольшое отклонение

### 4. get_glideslope_info()

Получение информации о параметрах глиссады.

```python
info = navigation.get_glideslope_info(glideslope_angle=5.5)

# Результат:
{
    'angle': 5.5,
    'category': 'EXTREME',
    'description': 'Экстремально крутая глиссада (требует сертификации)',
    'feet_per_nm': 585.0,
    'required_vs_90kts': 871.0,
    'required_vs_120kts': 1162.0,
    'required_vs_150kts': 1452.0,
    'distance_for_2000ft': 3.42,
    'distance_for_3000ft': 5.13
}
```

## Примеры использования

### Пример 1: Стандартная глиссада 3°

```python
# UUEE (Шереметьево) RWY 24L - стандартная глиссада
intercept = navigation.calculate_glideslope_intercept_point(
    runway_threshold_lat=55.9728,
    runway_threshold_lon=37.4106,
    runway_heading=244,
    runway_elevation=622,
    glideslope_angle=3.0,
    intercept_altitude_agl=2000.0
)

print(f"Точка входа: {intercept['distance_from_threshold_nm']:.1f} NM")
# Результат: 6.3 NM

print(f"Координаты: {intercept['latitude']:.4f}, {intercept['longitude']:.4f}")
```

### Пример 2: Крутая глиссада 5.5° (London City)

```python
# EGLC (London City) RWY 27 - крутая глиссада 5.5°
intercept = navigation.calculate_glideslope_intercept_point(
    runway_threshold_lat=51.5053,
    runway_threshold_lon=0.0553,
    runway_heading=267,
    runway_elevation=19,
    glideslope_angle=5.5,  # Экстремально крутая!
    intercept_altitude_agl=1500.0
)

print(f"Точка входа: {intercept['distance_from_threshold_nm']:.1f} NM")
# Результат: 2.6 NM (намного ближе!)

# Требуемая VS при 120 узлах
info = navigation.get_glideslope_info(5.5)
print(f"Требуемая VS: {info['required_vs_120kts']:.0f} fpm")
# Результат: 1162 fpm (почти в 2 раза больше чем для 3°!)
```

### Пример 3: Мониторинг в полёте

```python
# В основном цикле execute_approach()
while self.running:
    # Получение телеметрии
    telemetry = self.telemetry.get_all_data()
    current_lat = telemetry['position']['latitude']
    current_lon = telemetry['position']['longitude']
    current_alt_agl = telemetry['position']['altitude_agl']
    
    # Проверка момента начала снижения
    descent_check = self.navigation.should_start_descent(
        current_lat=current_lat,
        current_lon=current_lon,
        current_altitude_agl=current_alt_agl,
        intercept_point=self.glideslope_intercept,
        tolerance_nm=0.5
    )
    
    # Логирование
    logger.info(f"Distance to intercept: {descent_check['distance_to_intercept_nm']:.1f} NM, "
                f"Altitude error: {descent_check['altitude_error_ft']:+.0f} ft, "
                f"Status: {descent_check['status']}")
    
    # Переход в фазу FINAL
    if descent_check['should_descend'] and self.phase == ApproachPhase.INTERMEDIATE:
        logger.info(f"Starting descent: {descent_check['reason']}")
        self.phase = ApproachPhase.FINAL
        # Начать снижение по глиссаде
```

## Интеграция в main.py

### Настройка захода

```python
def configure_approach(self, runway_data: dict):
    """Настройка параметров захода"""
    
    # Получение угла глиссады (может быть нестандартным!)
    glideslope_angle = runway_data.get('glideslope_angle', 3.0)
    
    # Получение информации о глиссаде
    gs_info = self.navigation.get_glideslope_info(glideslope_angle)
    
    if gs_info['category'] in ['VERY_STEEP', 'EXTREME']:
        logger.warning(f"STEEP GLIDESLOPE: {glideslope_angle}° - {gs_info['description']}")
        logger.warning(f"Required VS at 120kts: {gs_info['required_vs_120kts']:.0f} fpm")
    
    # Вычисление точки входа
    self.glideslope_intercept = self.navigation.calculate_glideslope_intercept_point(
        runway_threshold_lat=runway_data['threshold_lat'],
        runway_threshold_lon=runway_data['threshold_lon'],
        runway_heading=runway_data['heading'],
        runway_elevation=runway_data['elevation'],
        glideslope_angle=glideslope_angle,
        intercept_altitude_agl=2000.0
    )
    
    logger.info(f"Glideslope intercept: "
                f"{self.glideslope_intercept['distance_from_threshold_nm']:.1f} NM, "
                f"Angle: {glideslope_angle}°")
```

## Визуализация в GUI

```python
# В create_navigation_panel
ttk.Label(parent, text="Glideslope:").grid(row=row, column=0, sticky=tk.W)
self.glideslope_var = tk.StringVar(value="--")
ttk.Label(parent, textvariable=self.glideslope_var).grid(row=row, column=1, sticky=tk.E)
row += 1

ttk.Label(parent, text="Intercept Distance:").grid(row=row, column=0, sticky=tk.W)
self.intercept_dist_var = tk.StringVar(value="--")
ttk.Label(parent, textvariable=self.intercept_dist_var).grid(row=row, column=1, sticky=tk.E)
row += 1

ttk.Label(parent, text="Altitude Error:").grid(row=row, column=0, sticky=tk.W)
self.alt_error_var = tk.StringVar(value="--")
self.alt_error_label = ttk.Label(parent, textvariable=self.alt_error_var)
self.alt_error_label.grid(row=row, column=1, sticky=tk.E)
row += 1

# В update_display
if hasattr(self.system, 'glideslope_intercept'):
    intercept = self.system.glideslope_intercept
    
    # Отображение угла глиссады
    angle = intercept['glideslope_angle']
    self.glideslope_var.set(f"{angle:.1f}°")
    
    # Расстояние до точки входа
    self.intercept_dist_var.set(f"{intercept['distance_from_threshold_nm']:.1f} NM")
    
    # Проверка снижения
    telemetry = self.system.telemetry.get_all_data()
    descent_check = self.system.navigation.should_start_descent(
        current_lat=telemetry['position']['latitude'],
        current_lon=telemetry['position']['longitude'],
        current_altitude_agl=telemetry['position']['altitude_agl'],
        intercept_point=intercept,
        tolerance_nm=0.5
    )
    
    # Отображение ошибки высоты
    alt_error = descent_check['altitude_error_ft']
    self.alt_error_var.set(f"{alt_error:+.0f} ft")
    
    # Цветовая индикация
    if descent_check['status'] == 'LOW':
        self.alt_error_label.config(foreground='red', font=('Arial', 9, 'bold'))
    elif descent_check['status'] == 'HIGH':
        self.alt_error_label.config(foreground='orange')
    elif descent_check['status'] == 'ON_PROFILE':
        self.alt_error_label.config(foreground='green')
    else:
        self.alt_error_label.config(foreground='yellow')
```

## Известные аэропорты с нестандартными глиссадами

### 3.5° (Steep)

- Многие европейские аэропорты для шумоподавления
- Некоторые аэропорты с близкими препятствиями

### 4.0° - 4.5° (Very Steep)

- **LOWI** (Innsbruck) - 4.0° - горы
- **LSZS** (Samedan) - 4.5° - Альпы

### 5.0° - 5.5° (Extreme)

- **EGLC** (London City) - 5.5° - короткая ВПП в городе
- **VQPR** (Paro, Bhutan) - 5.0° - горная долина

### 6.0°+ (Extreme)

- **LSZA** (Lugano) - 6.1° - горы и озеро
- **LFLJ** (Courchevel) - 6.5° - горнолыжный курорт

## Важные замечания

### Для крутых глиссад (>4°):

1. **Требуется специальная сертификация экипажа**
2. **Увеличенная вертикальная скорость** - до 1200+ fpm
3. **Короткое время на исправление ошибок**
4. **Повышенная нагрузка на автопилот**
5. **Может потребоваться ручное управление**

### Рекомендации:

- Для углов >4° рекомендуется снижать скорость захода
- Мониторить вертикальную скорость постоянно
- Быть готовым к уходу на второй круг
- Проверять ограничения самолёта по VS

## Тестирование

### Тест 1: Стандартная глиссада

```python
# 3° глиссада, 2000 футов
intercept = navigation.calculate_glideslope_intercept_point(
    runway_threshold_lat=55.0,
    runway_threshold_lon=37.0,
    runway_heading=270,
    runway_elevation=500,
    glideslope_angle=3.0,
    intercept_altitude_agl=2000.0
)

assert abs(intercept['distance_from_threshold_nm'] - 6.29) < 0.1
assert intercept['feet_per_nm'] > 300 and intercept['feet_per_nm'] < 320
```

### Тест 2: Крутая глиссада

```python
# 5.5° глиссада (London City), 1500 футов
intercept = navigation.calculate_glideslope_intercept_point(
    runway_threshold_lat=51.5053,
    runway_threshold_lon=0.0553,
    runway_heading=267,
    runway_elevation=19,
    glideslope_angle=5.5,
    intercept_altitude_agl=1500.0
)

assert abs(intercept['distance_from_threshold_nm'] - 2.56) < 0.1
assert intercept['feet_per_nm'] > 580 and intercept['feet_per_nm'] < 590
```

### Тест 3: Определение момента снижения

```python
# Самолёт на 0.3 NM от точки входа, на правильной высоте
descent_check = navigation.should_start_descent(
    current_lat=intercept['latitude'] + 0.005,
    current_lon=intercept['longitude'],
    current_altitude_agl=2000.0,
    intercept_point=intercept,
    tolerance_nm=0.5
)

assert descent_check['should_descend'] == True
assert descent_check['status'] == 'INTERCEPT'
```

---

**Создано:** 2026-04-17  
**Автор:** Claude (Sonnet 4)  
**Проект:** MSFS AutoLand System
