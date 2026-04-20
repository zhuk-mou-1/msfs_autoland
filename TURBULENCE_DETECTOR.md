# Детектор турбулентности (Turbulence Detector)

## Обзор

**TurbulenceDetector** - система обнаружения турбулентности любого типа, включая CAT (Clear Air Turbulence - турбулентность в ясном небе). Работает параллельно с детектором сдвига ветра и анализирует ускорения, колебания и изменения параметров полёта.

**Файл:** `modules/turbulence_detector.py`  
**Дата создания:** 2026-04-17

## Возможности

### Типы обнаруживаемой турбулентности

1. **CAT (Clear Air Turbulence)** - турбулентность в ясном небе
   - Колебания G-force без явных изменений ветра
   - Обычно на высоте, вдали от облаков
   - Связана со струйными течениями и температурными инверсиями

2. **CONVECTIVE** - конвективная турбулентность
   - Высокая изменчивость ветра
   - Связана с грозами и кучево-дождевыми облаками
   - Резкие порывы ветра

3. **MECHANICAL** - механическая турбулентность
   - На малых высотах (< 1000 футов)
   - Вызвана рельефом местности и препятствиями
   - Характерна для захода на посадку

4. **UNKNOWN** - неопределённый тип
   - Когда невозможно точно классифицировать

### Уровни интенсивности

Основаны на стандартах авиации:

| Интенсивность | G-force std | Описание | Цвет |
|---------------|-------------|----------|------|
| **SMOOTH** | < 0.05 | Спокойный полёт | Зелёный |
| **LIGHT** | 0.05 - 0.15 | Лёгкая турбулентность, небольшие колебания | Жёлтый |
| **MODERATE** | 0.15 - 0.30 | Умеренная турбулентность, заметные колебания | Оранжевый |
| **SEVERE** | > 0.30 | Сильная турбулентность, резкие броски | Красный |

## Принцип работы

### Анализируемые параметры

1. **G-force (вертикальная перегрузка)** - главный индикатор (вес 60%)
   - Стандартное отклонение за последние 5 секунд
   - Чем выше разброс, тем сильнее турбулентность

2. **Колебания крена (Bank oscillation)** - вес 30%
   - Амплитуда колебаний крена (размах)
   - Пороги: 3° (light), 8° (moderate), 15° (severe)

3. **Колебания тангажа (Pitch oscillation)** - вес 10%
   - Амплитуда колебаний тангажа
   - Дополнительный индикатор

4. **Изменчивость ветра (Wind variability)**
   - Максимальное изменение скорости ветра
   - Помогает определить тип турбулентности

### Алгоритм обнаружения

```python
# 1. Сбор данных (история 100 измерений = 10 секунд при 10Hz)
g_force_history
bank_angle_history
pitch_angle_history
wind_velocity_history
temperature_history

# 2. Расчёт метрик
g_force_std = std(g_force_history[-50:])  # Последние 5 секунд
bank_oscillation = max(bank_history[-50:]) - min(bank_history[-50:])
pitch_oscillation = max(pitch_history[-50:]) - min(pitch_history[-50:])
wind_variability = max(abs(diff(wind_history[-50:])))

# 3. Комбинированная оценка
combined_score = (
    g_force_std * 0.6 +
    (bank_oscillation / 20.0) * 0.3 +
    (pitch_oscillation / 15.0) * 0.1
)

# 4. Определение интенсивности
if combined_score >= 0.30: intensity = 'SEVERE'
elif combined_score >= 0.15: intensity = 'MODERATE'
elif combined_score >= 0.05: intensity = 'LIGHT'
else: intensity = 'SMOOTH'

# 5. Определение типа
if wind_variability > 5.0: type = 'CONVECTIVE'
elif altitude < 1000 ft: type = 'MECHANICAL'
elif g_force_std > 0.05 and wind_variability < 2.0: type = 'CAT'
else: type = 'UNKNOWN'
```

## Использование

### Инициализация

```python
from modules.turbulence_detector import TurbulenceDetector

# Создание детектора
turbulence_detector = TurbulenceDetector(history_size=100)
```

### Обновление данных

```python
# В основном цикле (каждые 100мс)
telemetry = self.telemetry.get_all_data()

turbulence_alert = self.turbulence_detector.update(telemetry)

if turbulence_alert and turbulence_alert.intensity != 'SMOOTH':
    logger.warning(f"TURBULENCE {turbulence_alert.intensity} ({turbulence_alert.type}): "
                   f"G-std: {turbulence_alert.g_force_std:.3f}, "
                   f"Bank osc: {turbulence_alert.bank_oscillation:.1f}° - "
                   f"{turbulence_alert.recommendation}")
```

### Получение текущего статуса

```python
# Получить текущее предупреждение
alert = turbulence_detector.get_current_alert()

if alert:
    print(f"Intensity: {alert.intensity}")
    print(f"Type: {alert.type}")
    print(f"G-force std: {alert.g_force_std:.3f}")
    print(f"Recommendation: {alert.recommendation}")
```

### Статистика

```python
stats = turbulence_detector.get_statistics()

print(f"Samples: {stats['samples']}")
print(f"Current G-force std: {stats['current_g_force_std']:.3f}")
print(f"Max G-force std: {stats['max_g_force_std']:.3f}")
print(f"Turbulence events: {stats['turbulence_events_count']}")
print(f"Current intensity: {stats['current_intensity']}")
```

## Интеграция в систему

### main.py

```python
# Инициализация (в __init__)
self.turbulence_detector = TurbulenceDetector()

# В execute_approach() после получения телеметрии
turbulence_alert = self.turbulence_detector.update(telemetry)
if turbulence_alert and turbulence_alert.intensity != 'SMOOTH':
    logger.warning(f"TURBULENCE {turbulence_alert.intensity} ({turbulence_alert.type})")
```

### gui.py

```python
# Создание UI элементов (в create_telemetry_panel)
ttk.Label(parent, text="Turbulence:", font=('Arial', 9, 'bold'))
self.turbulence_var = tk.StringVar(value="SMOOTH")
self.turbulence_label = ttk.Label(parent, textvariable=self.turbulence_var)

# Обновление (в update_display)
turbulence_alert = self.system.turbulence_detector.get_current_alert()
if turbulence_alert and turbulence_alert.intensity != 'SMOOTH':
    turb_text = f"{turbulence_alert.intensity} {turbulence_alert.type}"
    self.turbulence_var.set(turb_text)
    
    # Цветовая индикация
    if turbulence_alert.intensity == 'SEVERE':
        self.turbulence_label.config(foreground='red', font=('Arial', 9, 'bold'))
    elif turbulence_alert.intensity == 'MODERATE':
        self.turbulence_label.config(foreground='orange', font=('Arial', 9, 'bold'))
    else:  # LIGHT
        self.turbulence_label.config(foreground='yellow', font=('Arial', 9))
else:
    self.turbulence_var.set("SMOOTH")
    self.turbulence_label.config(foreground='green', font=('Arial', 9))
```

## Рекомендации по действиям

Детектор автоматически генерирует рекомендации:

| Интенсивность | Рекомендация |
|---------------|--------------|
| **SEVERE** | REDUCE SPEED - FASTEN SEATBELTS - CONSIDER DIVERSION |
| **MODERATE (CAT)** | REDUCE SPEED - REQUEST ALTITUDE CHANGE |
| **MODERATE (другие)** | REDUCE SPEED - MAINTAIN CONTROL |
| **LIGHT** | MONITOR CONDITIONS - FASTEN SEATBELTS |
| **SMOOTH** | NORMAL OPERATIONS |

## Настройка порогов

Пороги можно настроить при инициализации:

```python
detector = TurbulenceDetector()

# Изменение порогов интенсивности
detector.light_turbulence_threshold = 0.05  # G-force std
detector.moderate_turbulence_threshold = 0.15
detector.severe_turbulence_threshold = 0.30

# Изменение порогов колебаний
detector.light_bank_oscillation = 3.0  # градусы
detector.moderate_bank_oscillation = 8.0
detector.severe_bank_oscillation = 15.0

# Cooldown между предупреждениями
detector.alert_cooldown = 3.0  # секунды
```

## Отличия от Wind Shear Detector

| Параметр | Turbulence Detector | Wind Shear Detector |
|----------|---------------------|---------------------|
| **Цель** | Обнаружение турбулентности | Обнаружение сдвига ветра |
| **Главный индикатор** | G-force колебания | Изменения ветра |
| **Типы событий** | CAT, Convective, Mechanical | Headwind loss, Crosswind change, Downdraft |
| **Фаза полёта** | Весь полёт | Заход на посадку |
| **История** | 100 измерений (10 сек) | 20 измерений (2 сек) |
| **Cooldown** | 3 секунды | 5 секунд |

## Ограничения

### Что детектор НЕ может:

1. **Предсказать турбулентность** - работает реактивно, обнаруживает постфактум
2. **Различить источник** - не знает точную причину (струйное течение, гроза, рельеф)
3. **Читать метеоданные** - не использует прогнозы погоды
4. **Обнаружить wake turbulence** - турбулентность в следе других самолётов

### Зависимость от MSFS:

- Качество симуляции турбулентности в MSFS
- Точность физической модели
- Доступность параметров через SimConnect

## Тестирование

### Создание условий турбулентности в MSFS:

1. **Light turbulence:**
   - Полёт в облаках
   - Скорость ветра 15-25 узлов
   - Высота 5000-10000 футов

2. **Moderate turbulence:**
   - Полёт вблизи гроз
   - Скорость ветра 25-40 узлов
   - Изменение направления ветра

3. **Severe turbulence:**
   - Полёт в грозе
   - Скорость ветра > 40 узлов
   - Сильные порывы

### Проверка работы:

```python
# Запустить GUI
python gui.py

# Подключиться к MSFS
# Начать полёт в условиях турбулентности
# Наблюдать за панелью Telemetry:
#   - Turbulence: LIGHT/MODERATE/SEVERE
#   - Цвет индикатора (зелёный/жёлтый/оранжевый/красный)
#   - Логи в консоли
```

## Логирование

Детектор логирует события:

```
WARNING - TURBULENCE DETECTED: MODERATE CAT - G-std: 0.182, Bank osc: 9.3°
WARNING - TURBULENCE MODERATE (CAT): G-std: 0.182, Bank osc: 9.3° - REDUCE SPEED - REQUEST ALTITUDE CHANGE
```

## Будущие улучшения

- [ ] Звуковые предупреждения для SEVERE турбулентности
- [ ] Адаптивные PID-коэффициенты автопилота при турбулентности
- [ ] Запись и анализ событий турбулентности
- [ ] Интеграция с метеоданными MSFS
- [ ] Предиктивный анализ на основе трендов
- [ ] Визуализация истории G-force в GUI
- [ ] Экспорт данных турбулентности в CSV/JSON

## Примеры сценариев

### Сценарий 1: CAT на эшелоне

```
Условия:
- Высота: 35000 футов
- Погода: ясно
- Ветер: 80 узлов (струйное течение)

Обнаружение:
- G-force std: 0.12 (LIGHT)
- Wind variability: 1.5 (низкая)
- Type: CAT
- Recommendation: MONITOR CONDITIONS - FASTEN SEATBELTS
```

### Сценарий 2: Конвективная турбулентность

```
Условия:
- Высота: 8000 футов
- Погода: грозы
- Ветер: резкие изменения 20-45 узлов

Обнаружение:
- G-force std: 0.22 (MODERATE)
- Wind variability: 8.5 (высокая)
- Type: CONVECTIVE
- Recommendation: REDUCE SPEED - MAINTAIN CONTROL
```

### Сценарий 3: Механическая турбулентность

```
Условия:
- Высота: 500 футов AGL
- Погода: ветер 25 узлов
- Местность: горы

Обнаружение:
- G-force std: 0.08 (LIGHT)
- Altitude: < 1000 футов
- Type: MECHANICAL
- Recommendation: MONITOR CONDITIONS - FASTEN SEATBELTS
```

---

**Создано:** 2026-04-17  
**Автор:** Claude (Sonnet 4)  
**Проект:** MSFS AutoLand System
