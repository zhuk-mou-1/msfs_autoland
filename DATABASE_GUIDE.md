# База данных логов - Руководство

## Обзор

Создана SQLite база данных для хранения всех логов работы программы с удобными методами для Claude.

## Структура базы данных

### Таблицы:

1. **sessions** - информация о сессиях работы программы
   - session_id (PRIMARY KEY)
   - start_time, end_time
   - total_logs, error_count, warning_count
   - status (active/completed)

2. **logs** - все записи логов
   - id, session_id, timestamp
   - level, category, message
   - module, function, line
   - data (JSON), exception_type, exception_message, stack_trace

3. **errors** - группированные ошибки
   - id, session_id, error_type, message
   - module, function, count
   - first_occurrence, last_occurrence

4. **performance** - метрики производительности
   - id, session_id, timestamp
   - operation, duration_ms, data

## Файлы

- `modules/log_database.py` - класс LogDatabase с методами работы с БД
- `claude_db.py` - скрипт для Claude для чтения логов из БД
- `logs/logs.db` - файл SQLite базы данных

## Команды для Claude

### 1. Чтение последней сессии

```bash
python claude_db.py read
```

**Показывает:**
- Статистику базы данных
- Информацию о сессии
- Все ошибки с деталями
- Метрики производительности
- Последние критические события

### 2. Чтение конкретной сессии

```bash
python claude_db.py read --session 20260417_001530
```

### 3. Поиск в логах

```bash
python claude_db.py search "KeyError"
python claude_db.py search "altitude" --session 20260417_001530
```

### 4. Список всех сессий

```bash
python claude_db.py list
```

## Методы LogDatabase

### Для чтения:

```python
from modules.log_database import LogDatabase

db = LogDatabase()

# Получить информацию о сессии
session_info = db.get_session_info("20260417_001530")

# Получить логи сессии
logs = db.get_session_logs("20260417_001530", level="ERROR")

# Получить ошибки
errors = db.get_session_errors("20260417_001530")

# Получить метрики производительности
perf = db.get_performance_stats("20260417_001530")

# Поиск в логах
results = db.search_logs("KeyError")

# Последняя сессия
latest = db.get_latest_session()

# Статистика БД
stats = db.get_database_stats()
```

### Для записи (автоматически):

```python
# Создаётся автоматически при инициализации StructuredLogger
logger = init_logger()

# Логи автоматически записываются в БД
logger.info(LogCategory.SYSTEM, "Message")
logger.error(LogCategory.TELEMETRY, "Error", exception=e)
logger.log_performance("operation", duration=0.015)
```

## Преимущества базы данных

1. **Быстрый поиск** - индексы для быстрого поиска по сессиям, уровням, категориям
2. **Группировка ошибок** - автоматическая группировка одинаковых ошибок
3. **Статистика** - мгновенная статистика по сессиям
4. **Поиск** - полнотекстовый поиск по всем логам
5. **Компактность** - SQLite эффективно сжимает данные
6. **SQL запросы** - можно делать сложные запросы

## Пример использования Claude

```
Пользователь: "Клауд, посмотри что в базе данных логов"

Claude:
1. Запускает: python claude_db.py read
2. Видит:
   - Всего сессий: 5
   - Всего логов: 7523
   - Всего ошибок: 23
   - Размер БД: 1.2 MB
   
   Сессия: 20260417_001530
   - Ошибок: 12
   - KeyError в modules.telemetry (8 раз)
   - AttributeError в modules.navigation (3 раза)

3. Сообщает: "Нашёл 12 ошибок в последней сессии. 
   Основная проблема: KeyError в telemetry.py при чтении altitude (8 повторений)"

Пользователь: "Исправь KeyError"

Claude:
1. Читает: Read("modules/telemetry.py")
2. Находит проблему
3. Применяет исправление
```

## Расположение

```
msfs_autoland/
├── logs/
│   ├── logs.db                    # SQLite база данных
│   ├── session_*.jsonl            # JSON логи (дублирование)
│   └── session_*.log              # Текстовые логи
├── modules/
│   ├── log_database.py            # Класс LogDatabase
│   └── structured_logger.py       # Интеграция с БД
└── claude_db.py                   # Скрипт для Claude
```

## Автоматическая работа

При запуске программы:
1. Создаётся новая сессия в БД
2. Все логи автоматически записываются в БД
3. Ошибки группируются
4. Метрики производительности сохраняются
5. При завершении сессия закрывается

Claude может в любой момент:
- Прочитать логи из БД
- Найти ошибки
- Посмотреть статистику
- Сделать поиск

## Размер базы данных

- ~1 KB на 10 записей логов
- ~100 KB на 1000 записей
- ~1 MB на 10000 записей

База данных автоматически оптимизируется SQLite.
