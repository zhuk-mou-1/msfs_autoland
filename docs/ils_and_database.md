# ILS Заходы и База Данных Аэропортов

## Обзор новых возможностей

Система теперь поддерживает:
1. **ILS заходы** с автоматическим чтением глиссады из MSFS
2. **База данных аэропортов** с популярными заходами
3. **Графический диалог** для настройки захода

---

## 1. ILS Заходы (Instrument Landing System)

### Что такое ILS?

ILS - это система точного захода, которая передаёт:
- **Localizer** - курсовой маяк (горизонтальное наведение)
- **Glideslope** - глиссадный маяк (вертикальное наведение)

### Преимущества ILS

- Автоматическое определение угла глиссады (обычно 3.0°)
- Точное наведение по курсу и высоте
- Работает в любых погодных условиях (IMC)
- Минимальная высота принятия решения: 200 футов

### Как работает ILS в программе

**Чтение данных из MSFS:**
```python
ils_data = telemetry.get_ils_data()

# Localizer (курс)
has_localizer = ils_data['nav1_has_localizer']
cdi = ils_data['nav1_cdi']  # -127 (влево) до +127 (вправо)

# Glideslope (глиссада)
has_glideslope = ils_data['nav1_has_glideslope']
gsi = ils_data['nav1_gsi']  # -127 (ниже) до +127 (выше)
```

**Интерпретация отклонений:**
- **CDI (Course Deviation Indicator)**: ±2.5° полное отклонение
- **GSI (Glideslope Indicator)**: ±0.7° полное отклонение
- **5 точек** на индикаторе (как в реальном самолёте)

**Пример:**
```
CDI = +64 → 1.25° вправо от курса → 2.5 точки вправо
GSI = -32 → 0.175° ниже глиссады → 1.25 точки ниже
```

### Автоматическое управление

Система автоматически:
1. Перехватывает localizer (курс)
2. Следует по глиссаде
3. Корректирует отклонения
4. Выполняет выравнивание и посадку

---

## 2. База Данных Аэропортов

### Структура базы данных

Файл: `config/airports_database.json`

```json
{
  "airports": {
    "UUEE": {
      "name": "Sheremetyevo International Airport",
      "city": "Moscow",
      "elevation": 622,
      "runways": {
        "07C": {
          "heading": 70,
          "length": 12139,
          "width": 197,
          "threshold_lat": 55.9728,
          "threshold_lon": 37.4106,
          "approaches": {
            "ILS": {
              "frequency": 110300000,
              "course": 70,
              "glideslope": 3.0,
              "decision_height": 200
            }
          }
        }
      }
    }
  }
}
```

### Включённые аэропорты

1. **UUEE** - Шереметьево (Москва)
2. **KJFK** - JFK (Нью-Йорк)
3. **EGLL** - Heathrow (Лондон)
4. **EGLC** - London City (крутая глиссада 5.5°!)
5. **LFPG** - Charles de Gaulle (Париж)
6. **EDDF** - Frankfurt (Франкфурт)
7. **RJTT** - Haneda (Токио)
8. **KLAX** - LAX (Лос-Анджелес)

### Использование базы данных

**В коде:**
```python
from modules.airports_database import AirportsDatabase

db = AirportsDatabase()

# Поиск аэропорта
results = db.search_airports("Moscow")
# [{'icao': 'UUEE', 'name': 'Sheremetyevo...', ...}]

# Получение конфигурации захода
config = db.get_approach_config('UUEE', '07C', 'ILS')
system.configure_approach(config)
```

**В GUI:**
- Просто выберите аэропорт, ВПП и тип захода из списка!

---

## 3. Графический Диалог Настройки

### Как использовать

1. Запустите GUI: `python gui.py`
2. Нажмите "Connect" для подключения к MSFS
3. Нажмите "Start Approach"
4. Откроется диалог настройки

### Вкладка "From Database"

**Выбор из базы данных:**
1. Найдите аэропорт (поиск по ICAO, названию, городу)
2. Выберите ВПП
3. Выберите тип захода (ILS, VOR, NDB)
4. Просмотрите информацию о заходе
5. Нажмите OK

**Пример:**
```
Search: "Moscow"
Airport: UUEE - Sheremetyevo International Airport (Moscow)
Runway: 07C
Approach: ILS

Info:
Type: ILS
Frequency: 110.30 MHz
Course: 70°
Glideslope: 3.0°
Decision Height: 200 ft
Approach Speed: 140 kt
Runway: 12139 x 197 ft
Elevation: 622 ft
```

### Вкладка "Manual Entry"

**Ручной ввод параметров:**
- Тип захода (ILS/VOR/NDB)
- Частота (MHz)
- Курс посадки (градусы)
- Угол глиссады (градусы)
- Высота принятия решения (футы)
- Скорость захода (узлы)
- Параметры ВПП

**Когда использовать:**
- Аэропорта нет в базе данных
- Нестандартные параметры
- Тестирование

---

## 4. Откуда берётся угол глиссады

### Для ILS заходов

**Автоматически из MSFS:**
- MSFS знает угол глиссады для каждого ILS
- Обычно 3.0° (стандарт ICAO)
- Специальные аэропорты: 5.5° (London City)

**В программе:**
```python
# Угол глиссады берётся из базы данных или ручного ввода
config = db.get_approach_config('EGLC', '09', 'ILS')
# glideslope_angle = 5.5° (из базы данных)

# Система автоматически использует этот угол
ils_navigation.configure(ils_config)
```

### Для VOR/NDB заходов

**Из базы данных или ручного ввода:**
- VOR/NDB не передают информацию о глиссаде
- Угол берётся из карт заходов (approach charts)
- Пилоты вводят вручную

**Стандартные значения:**
- 3.0° - стандарт (99% заходов)
- 3.5° - при препятствиях
- 4.5° - специальные аэропорты

---

## 5. Примеры использования

### Пример 1: ILS заход в Шереметьево

```python
from modules.airports_database import AirportsDatabase

db = AirportsDatabase()

# Загрузка конфигурации из базы
config = db.get_approach_config('UUEE', '07C', 'ILS')
ils_config = db.get_ils_config('UUEE', '07C')

# Настройка системы
system.configure_approach(config)
system.ils_navigation.configure(ils_config)

# Запуск захода
system.start_approach()
system.execute_approach()
```

**Результат:**
- Частота: 110.30 MHz (автоматически)
- Курс: 70° (автоматически)
- Глиссада: 3.0° (из базы данных)
- Точное наведение по ILS

### Пример 2: Крутой заход в London City

```python
# London City - крутая глиссада 5.5°!
config = db.get_approach_config('EGLC', '09', 'ILS')

# glideslope_angle = 5.5°
# Вертикальная скорость будет выше:
# VS = 130 kt × tan(5.5°) × 101.3 = 1250 fpm
```

### Пример 3: Ручной ввод

```python
# Создание конфигурации вручную
station = NavStation(
    name="Custom ILS",
    frequency=110300000,  # 110.30 MHz
    latitude=55.9728,
    longitude=37.4106,
    type='ILS'
)

config = ApproachConfig(
    station=station,
    final_approach_course=70,
    glideslope_angle=3.0,  # Указываем вручную
    decision_height=200,
    approach_speed=140,
    runway_elevation=622,
    runway_length=12139,
    runway_width=197,
    runway_threshold_lat=55.9728,
    runway_threshold_lon=37.4106
)
```

---

## 6. Сравнение ILS vs VOR/NDB

| Параметр | ILS | VOR/NDB |
|----------|-----|---------|
| Точность курса | ±2.5° | ±5° |
| Вертикальное наведение | Да (глиссада) | Нет (расчётная) |
| Минимумы | 200 ft | 400+ ft |
| Погодные условия | IMC/VMC | VMC обычно |
| Угол глиссады | Из MSFS/БД | Только из БД/ручной ввод |
| Сложность | Проще | Сложнее |

---

## 7. Добавление своих аэропортов

### Формат записи

```json
"XXXX": {
  "name": "Airport Name",
  "city": "City",
  "country": "Country",
  "elevation": 500,
  "runways": {
    "09": {
      "heading": 90,
      "length": 8000,
      "width": 150,
      "threshold_lat": 55.0,
      "threshold_lon": 37.0,
      "approaches": {
        "ILS": {
          "type": "ILS",
          "frequency": 110300000,
          "course": 90,
          "glideslope": 3.0,
          "decision_height": 200,
          "approach_speed": 120
        }
      }
    }
  }
}
```

### Где найти данные

1. **LittleNavMap** - бесплатная программа с базой данных
2. **Navigraph** - платная подписка (актуальные данные)
3. **SkyVector** - онлайн карты (skyvector.com)
4. **MSFS SDK** - документация симулятора

---

## 8. Устранение проблем

### ILS сигнал не обнаружен

**Проблема:** `ILS signal not available`

**Решения:**
1. Проверьте частоту (должна совпадать с MSFS)
2. Убедитесь что вы в зоне действия ILS (обычно 25nm)
3. Проверьте что NAV1 настроен на правильную частоту
4. Используйте VOR/NDB заход как альтернативу

### Неправильный угол глиссады

**Проблема:** Самолёт слишком высоко/низко

**Решения:**
1. Проверьте значение в базе данных
2. Сравните с картами заходов
3. Используйте ручной ввод для коррекции

### Аэропорта нет в базе

**Решение:**
1. Используйте вкладку "Manual Entry"
2. Добавьте аэропорт в `airports_database.json`
3. Или используйте похожий аэропорт как шаблон

---

## Заключение

Теперь система поддерживает:
- ✅ ILS заходы с автоматическим наведением
- ✅ База данных с 8 крупными аэропортами
- ✅ Графический диалог для удобной настройки
- ✅ Автоматическое определение угла глиссады для ILS
- ✅ Ручной ввод для любых аэропортов

Угол глиссады теперь берётся:
- **ILS**: из базы данных (обычно 3.0°)
- **VOR/NDB**: из базы данных или ручного ввода
- **MSFS**: система использует этот угол для расчёта глиссады

Приятных полётов! 🛬
