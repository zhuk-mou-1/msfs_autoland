# Changelog - ILS Support and Airport Database

## Дата: 2026-04-16

## Добавлено

### 1. Поддержка ILS заходов

**Новые файлы:**
- `modules/ils_navigation.py` - модуль навигации по ILS
- `docs/ils_and_database.md` - документация по ILS и базе данных

**Изменённые файлы:**
- `modules/telemetry.py` - добавлен метод `get_ils_data()`
- `main.py` - интеграция ILS навигации

**Возможности:**
- Чтение localizer (курсовой маяк) из MSFS
- Чтение glideslope (глиссадный маяк) из MSFS
- Автоматическое определение угла глиссады
- Отклонения в градусах и точках индикатора
- Точное наведение по курсу и высоте
- Поддержка стандартных (3.0°) и крутых (5.5°) глиссад

### 2. База данных аэропортов

**Новые файлы:**
- `config/airports_database.json` - JSON база с аэропортами
- `modules/airports_database.py` - модуль работы с базой

**Включённые аэропорты:**
1. UUEE - Sheremetyevo (Moscow)
2. KJFK - JFK (New York)
3. EGLL - Heathrow (London)
4. EGLC - London City (steep 5.5° glideslope!)
5. LFPG - Charles de Gaulle (Paris)
6. EDDF - Frankfurt
7. RJTT - Haneda (Tokyo)
8. KLAX - LAX (Los Angeles)

**Возможности:**
- Готовые конфигурации ILS/VOR/NDB заходов
- Поиск по ICAO, названию, городу
- Автоматическая загрузка параметров
- Легко расширяемая структура

### 3. Графический диалог настройки

**Новые файлы:**
- `modules/approach_dialog.py` - диалог настройки захода

**Изменённые файлы:**
- `gui.py` - интеграция диалога

**Возможности:**
- Две вкладки: "From Database" и "Manual Entry"
- Выбор аэропорта, ВПП, типа захода
- Поиск аэропортов
- Предпросмотр информации о заходе
- Ручной ввод всех параметров

### 4. Документация

**Обновлённые файлы:**
- `README.md` - добавлена информация о новых возможностях
- `docs/ils_and_database.md` - полная документация

## Откуда берётся угол глиссады

### ILS заходы
- Из базы данных аэропортов (`airports_database.json`)
- Обычно 3.0° (стандарт ICAO)
- Специальные аэропорты: 5.5° (London City)

### VOR/NDB заходы
- Из базы данных аэропортов
- Или ручной ввод пользователем
- VOR/NDB не передают информацию о глиссаде

### Автоматический расчёт
Система автоматически:
1. Использует угол из конфигурации
2. Рассчитывает требуемую высоту: `h = distance × tan(angle)`
3. Рассчитывает вертикальную скорость: `VS = GS × tan(angle) × 101.3`

## Использование

### GUI (рекомендуется)
```bash
python gui.py
```
1. Connect
2. Start Approach
3. Выбрать из базы или ввести вручную
4. OK

### Из кода
```python
from modules.airports_database import AirportsDatabase

db = AirportsDatabase()
config = db.get_approach_config('UUEE', '07C', 'ILS')
ils_config = db.get_ils_config('UUEE', '07C')

system.configure_approach(config)
system.ils_navigation.configure(ils_config)
system.start_approach()
```

## Технические детали

### ILS отклонения
- **CDI (Course Deviation Indicator)**: ±127 = ±2.5° = ±5 точек
- **GSI (Glideslope Indicator)**: ±127 = ±0.7° = ±5 точек

### Структура базы данных
```json
{
  "airports": {
    "ICAO": {
      "name": "...",
      "elevation": 500,
      "runways": {
        "09": {
          "heading": 90,
          "length": 8000,
          "approaches": {
            "ILS": {
              "frequency": 110300000,
              "glideslope": 3.0,
              ...
            }
          }
        }
      }
    }
  }
}
```

## Совместимость

- Все существующие функции работают без изменений
- VOR/NDB заходы полностью совместимы
- ILS - дополнительная опция
- База данных - опциональная (можно использовать ручной ввод)

## Что дальше?

Возможные улучшения:
- Добавить больше аэропортов в базу
- Импорт из LittleNavMap/Navigraph
- RNAV/GPS заходы
- Визуальные индикаторы ILS в GUI
- Запись/воспроизведение заходов

---

**Все задачи выполнены!** ✅

Система теперь полностью поддерживает ILS заходы с автоматическим определением угла глиссады из базы данных или ручного ввода.
