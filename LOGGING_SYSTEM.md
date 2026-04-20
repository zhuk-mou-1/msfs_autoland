# Документация системы логирования и автоанализа

## Обзор

Система структурированного логирования и автоматического анализа для MSFS AutoLand позволяет:
- Записывать детальные логи в JSON формате
- Автоматически анализировать ошибки и проблемы производительности
- Генерировать отчёты с рекомендациями
- Предлагать исправления кода

## Компоненты

### 1. Структурированный логгер (`modules/structured_logger.py`)

**Класс `StructuredLogger`:**
- Записывает логи в JSON формат (JSONL)
- Создаёт отдельные файлы для ошибок
- Сохраняет метрики производительности
- Поддерживает категории событий

**Категории логов:**
- `SYSTEM` - системные события
- `TELEMETRY` - данные телеметрии
- `NAVIGATION` - навигация
- `AUTOPILOT` - автопилот
- `CONTROL` - управление
- `WIND_SHEAR` - сдвиг ветра
- `AUDIO` - звуковые предупреждения
- `GUI` - интерфейс
- `PERFORMANCE` - производительность
- `ERROR` - ошибки

**Использование:**

```python
from modules.structured_logger import init_logger, get_logger, LogCategory

# Инициализация (один раз при старте)
logger = init_logger()

# Логирование
logger.info(LogCategory.SYSTEM, "System started")
logger.error(LogCategory.TELEMETRY, "Failed to read data", 
             data={'variable': 'altitude'}, 
             exception=e)
logger.log_performance("telemetry_read", duration=0.015)
```

**Файлы логов:**
- `logs/session_YYYYMMDD_HHMMSS.jsonl` - все логи в JSON
- `logs/session_YYYYMMDD_HHMMSS.log` - текстовые логи
- `logs/errors_YYYYMMDD_HHMMSS.jsonl` - только ошибки

### 2. Анализатор логов (`modules/log_analyzer.py`)

**Класс `LogAnalyzer`:**
- Загружает и парсит JSONL логи
- Группирует ошибки по паттернам
- Анализирует производительность
- Генерирует рекомендации

**Использование:**

```python
from modules.log_analyzer import LogAnalyzer, analyze_latest_session

# Анализ конкретной сессии
analyzer = LogAnalyzer("logs")
report = analyzer.analyze_session("20260417_001530")

# Анализ последней сессии
report = analyze_latest_session("logs")

# Генерация отчёта
analyzer.generate_report_file(report)
```

**Отчёт содержит:**
- Сводку (общее количество логов, ошибок, предупреждений)
- Паттерны ошибок (группировка похожих ошибок)
- Проблемы производительности
- Рекомендации по исправлению
- Предложения по изменению кода

### 3. Автоматическое исправление (`modules/auto_fixer.py`)

**Класс `AutoFixer`:**
- Генерирует исправления на основе анализа
- Создаёт отчёты с примерами кода
- Предлагает конкретные изменения

**Поддерживаемые типы ошибок:**
- `AttributeError` - добавление проверки атрибутов
- `KeyError` - использование .get() вместо []
- `IndexError` - проверка длины списка
- `TypeError` - проверка типов
- `ValueError` - обработка ошибок конвертации
- `SimConnect errors` - переподключение
- `WASM errors` - fallback на SimConnect

**Использование:**

```python
from modules.auto_fixer import AutoFixer, auto_analyze_and_fix

# Автоматический анализ и генерация исправлений
report, fixes = auto_analyze_and_fix("logs", ".")

# Ручная генерация исправлений
fixer = AutoFixer()
fixes = fixer.generate_fixes(report)
fixer.generate_fix_report(fixes, "logs/fixes.md")
```

### 4. Скрипт анализа (`analyze_logs.py`)

Консольный инструмент для анализа логов.

**Использование:**

```bash
# Анализ последней сессии
python analyze_logs.py --latest

# Анализ конкретной сессии
python analyze_logs.py --session 20260417_001530

# С генерацией исправлений
python analyze_logs.py --latest --generate-fixes

# Указать директорию логов
python analyze_logs.py --latest --log-dir logs --generate-fixes
```

**Вывод:**
- Сводка анализа в консоль
- Отчёт в Markdown: `logs/analysis_SESSIONID.md`
- Исправления в Markdown: `logs/fixes_SESSIONID.md`

## Интеграция в проект

### В main.py:

```python
from modules.structured_logger import init_logger, get_logger, LogCategory

class AutoLandSystem:
    def __init__(self):
        # Инициализация логгера
        self.structured_logger = init_logger()
        self.structured_logger.info(LogCategory.SYSTEM, "System initializing")
        
    def connect(self):
        try:
            # ... код подключения ...
            self.structured_logger.info(LogCategory.SYSTEM, "Connected to MSFS")
        except Exception as e:
            self.structured_logger.error(LogCategory.SYSTEM, "Connection failed", 
                                        exception=e)
```

### В других модулях:

```python
from modules.structured_logger import get_logger, LogCategory

logger = get_logger()

def some_function():
    logger.debug(LogCategory.NAVIGATION, "Calculating course")
    
    try:
        result = calculate()
        logger.info(LogCategory.NAVIGATION, "Course calculated", 
                   data={'course': result})
    except Exception as e:
        logger.error(LogCategory.NAVIGATION, "Calculation failed", 
                    exception=e)
```

## Формат JSON логов

```json
{
  "timestamp": 1713388530.123,
  "datetime_str": "2026-04-17T00:15:30.123456",
  "level": "ERROR",
  "category": "TELEMETRY",
  "message": "Failed to read altitude",
  "module": "modules.telemetry",
  "function": "get_data",
  "line": 145,
  "data": {
    "variable": "altitude",
    "attempt": 3
  },
  "exception": {
    "type": "KeyError",
    "message": "'altitude'",
    "args": ["altitude"]
  },
  "stack_trace": "Traceback...",
  "session_id": "20260417_001530"
}
```

## Примеры отчётов

### Анализ логов (`analysis_SESSIONID.md`):

```markdown
# Анализ логов сессии 20260417_001530

**Время анализа:** 2026-04-17T00:20:15

## Сводка

Проанализировано 1523 записей логов. Обнаружено 12 ошибок (0.8% от всех записей).
Система работает стабильно.

## Обнаруженные ошибки

### 1. KeyError [HIGH]

**Сообщение:** Failed to read altitude from telemetry data

**Количество:** 8

**Затронутые модули:** modules.telemetry

**Затронутые функции:** get_data, read_altitude

## Рекомендации

- [HIGH] KeyError (8x): Использовать .get() для безопасного доступа к ключу 'altitude'
- [PERFORMANCE] telemetry_read: Оптимизировать операцию, среднее время 125.3ms
```

### Исправления (`fixes_SESSIONID.md`):

```markdown
# Предложения по исправлению кода

## modules/telemetry.py

### Исправление 1: KeyError

**Функция:** `get_data`

**Описание:** Использовать .get() для безопасного доступа к ключу 'altitude'

**Было:**
```python
value = data['altitude']
```

**Стало:**
```python
value = data.get('altitude')
if value is None:
    logger.warning(f"Key 'altitude' not found in data")
    value = default_value
```
```

## Рабочий процесс

1. **Во время работы:** Система автоматически логирует все события
2. **После сессии:** Запустить анализ: `python analyze_logs.py --latest --generate-fixes`
3. **Просмотр отчётов:** Открыть `logs/analysis_*.md` и `logs/fixes_*.md`
4. **Применение исправлений:** Вручную применить предложенные изменения кода
5. **Повторное тестирование:** Запустить систему и проверить что ошибки исправлены

## Автоматизация

Можно добавить автоматический анализ при завершении программы:

```python
import atexit
from modules.auto_fixer import auto_analyze_and_fix

def on_exit():
    print("Analyzing logs...")
    report, fixes = auto_analyze_and_fix()
    if report:
        print(f"Analysis complete. Errors: {report.error_count}")
        if fixes:
            print(f"Generated {len(fixes)} fix suggestions")

atexit.register(on_exit)
```

## Преимущества

1. **Структурированные данные:** JSON формат легко парсится и анализируется
2. **Автоматический анализ:** Не нужно вручную искать ошибки в логах
3. **Группировка ошибок:** Похожие ошибки объединяются в паттерны
4. **Конкретные рекомендации:** Система предлагает конкретные исправления
5. **Метрики производительности:** Автоматическое выявление узких мест
6. **История сессий:** Каждая сессия сохраняется отдельно

## Ограничения

- Исправления генерируются автоматически и требуют ручной проверки
- Не все типы ошибок могут быть автоматически исправлены
- Анализ производительности требует достаточного количества измерений
- Большие логи (>10000 записей) могут замедлить анализ

## Требования

Все модули используют только стандартную библиотеку Python, дополнительные зависимости не требуются.
