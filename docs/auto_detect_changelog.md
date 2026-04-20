# Auto-Detect Feature - Changelog

## Дата: 2026-04-16

## Добавлено

### Автоматическое определение захода из MSFS

**Новые файлы:**
- `modules/msfs_airport_reader.py` - модуль чтения данных из MSFS через SimConnect
- `docs/auto_detect.md` - полная документация по Auto-Detect

**Изменённые файлы:**
- `modules/approach_dialog.py` - добавлена вкладка "Auto-Detect"
- `gui.py` - передача телеметрии в диалог
- `README.md` - обновлена документация

## Возможности Auto-Detect

### Что определяется автоматически

1. **ILS заход:**
   - Частота из NAV1 радио
   - Курс localizer
   - Координаты порога ВПП
   - Превышение ВПП

2. **GPS заход:**
   - Координаты из GPS пункта назначения
   - Превышение ВПП

3. **Общие параметры:**
   - Угол глиссады (3.0° стандарт)
   - Высота принятия решения
   - Скорость захода

### Как использовать

**В MSFS:**
1. Настройте NAV1 на частоту ILS (например, 110.30 MHz)
   ИЛИ
2. Установите пункт назначения в GPS/FMC

**В программе:**
1. `python gui.py`
2. Connect
3. Start Approach
4. Вкладка "Auto-Detect"
5. Кнопка "Detect Approach"
6. OK

### Преимущества

✅ **Быстро** - один клик  
✅ **Точно** - данные из симулятора  
✅ **Актуально** - всегда соответствует MSFS  
✅ **Просто** - не нужно искать в базе  

## Технические детали

### SimConnect API

**Используемые переменные:**

```python
# ILS
NAV_HAS_LOCALIZER:1      # bool - наличие localizer
NAV_ACTIVE_FREQUENCY:1   # int - частота в Hz
NAV_LOCALIZER:1          # float - курс в градусах

# GPS
GPS_WP_NEXT_LAT          # float - широта
GPS_WP_NEXT_LON          # float - долгота
GPS_WP_NEXT_ALT          # float - высота в футах

# Позиция
PLANE_LATITUDE           # float
PLANE_LONGITUDE          # float
PLANE_ALTITUDE           # float
PLANE_HEADING_DEGREES_MAGNETIC  # float
```

### Класс MSFSAirportReader

**Основные методы:**

```python
class MSFSAirportReader:
    def get_ils_frequency_from_nav() -> Tuple[float, int]
        # Возвращает (frequency_mhz, course)
    
    def get_active_runway_info() -> Dict
        # Возвращает GPS данные о пункте назначения
    
    def detect_approach_from_position() -> Dict
        # Определяет тип захода и параметры
    
    def auto_configure_approach() -> Dict
        # Создаёт полную конфигурацию захода
```

### Алгоритм

```
1. Проверка ILS:
   - Есть ли localizer на NAV1?
   - Да → ILS заход (частота + курс)
   
2. Проверка GPS:
   - Установлен ли пункт назначения?
   - Да → GPS заход (координаты)
   
3. Если ничего не найдено:
   - Возврат None
   - Пользователь видит предупреждение
```

## Интеграция с GUI

### Новая вкладка в диалоге

**ApproachConfigDialog теперь имеет 3 вкладки:**

1. **Auto-Detect** (если подключён MSFS)
   - Инструкция
   - Кнопка "Detect Approach"
   - Результаты определения
   - Статус

2. **From Database**
   - Выбор из базы данных
   - 8 аэропортов

3. **Manual Entry**
   - Ручной ввод всех параметров

### Передача телеметрии

```python
# В gui.py
dialog = ApproachConfigDialog(
    self.root, 
    self.system.telemetry  # Передаём телеметрию
)
```

## Примеры использования

### Пример 1: ILS в Шереметьево

**MSFS:**
- NAV1: 110.30 MHz
- Курс: 070°

**Auto-Detect результат:**
```
Type: ILS
Frequency: 110.30 MHz
Course: 70°
Glideslope: 3.0°
Decision Height: 200 ft
Approach Speed: 140 kt
Runway Threshold: 55.9728, 37.4106
Elevation: 622 ft
```

### Пример 2: GPS заход

**MSFS:**
- GPS Direct To: UUEE
- Runway: 07C

**Auto-Detect результат:**
```
Type: GPS
Glideslope: 3.0°
Decision Height: 400 ft
Approach Speed: 120 kt
Runway Threshold: 55.9728, 37.4106
Elevation: 622 ft
```

## Сравнение с другими методами

| Параметр | Auto-Detect | From Database | Manual Entry |
|----------|-------------|---------------|--------------|
| Скорость | ⚡ 1 клик | 🔍 3-4 клика | ⏱️ 10+ полей |
| Точность | ✅ Высокая | ✅ Высокая | ⚠️ Зависит |
| Полнота | ⚠️ Базовая | ✅ Полная | ✅ Полная |
| Требования | MSFS настроен | База данных | Знание параметров |

## Ограничения

- Не определяет длину/ширину ВПП (используются значения по умолчанию)
- Не определяет название аэропорта/ВПП
- Требует предварительной настройки ILS или GPS в MSFS
- Работает только при активном подключении

## Устранение проблем

### "No approach data detected"

**Решение:**
1. Проверьте NAV1 частоту
2. Убедитесь что в зоне действия ILS
3. Установите GPS пункт назначения
4. Используйте другой метод (Database/Manual)

### Неправильные данные

**Решение:**
1. Перепроверьте настройки в MSFS
2. Повторите Auto-Detect
3. Сравните с базой данных

## Будущие улучшения

Возможные дополнения:
- Определение длины ВПП из scenery
- Чтение STAR/SID процедур
- Определение активной ВПП по ветру
- История определённых заходов

---

## Итог

**Auto-Detect** делает настройку захода максимально простой:
1. Настройте ILS/GPS в MSFS
2. Один клик в программе
3. Готово к заходу!

Это самый быстрый способ начать автоматический заход, особенно когда вы уже летите и настроили навигацию в симуляторе.

**Три способа настройки захода - выбирайте удобный:**
- 🚀 **Auto-Detect** - быстро из MSFS
- 📚 **From Database** - полные данные
- ✍️ **Manual Entry** - полный контроль
