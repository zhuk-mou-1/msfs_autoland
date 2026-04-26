# Тестирование AutoFixer

## Способ 1: Быстрый тест (создание тестовых логов)

### Шаг 1: Создать тестовый лог с ошибками

```bash
cd C:/BAT/msfs_autoland

# Создать директорию для тестовых логов
mkdir -p logs/test_session

# Создать тестовый лог с ошибками
cat > logs/test_session/autoland.jsonl << 'EOF'
{"timestamp": "2026-04-21T02:30:00", "level": "ERROR", "category": "SYSTEM", "message": "AttributeError: 'NoneType' object has no attribute 'altitude'", "module": "telemetry", "function": "get_position", "data": {}}
{"timestamp": "2026-04-21T02:30:01", "level": "ERROR", "category": "NAVIGATION", "message": "KeyError: 'runway_heading'", "module": "navigation", "function": "calculate_approach", "data": {}}
{"timestamp": "2026-04-21T02:30:02", "level": "ERROR", "category": "CONTROL", "message": "IndexError: list index out of range", "module": "control", "function": "set_autopilot", "data": {}}
{"timestamp": "2026-04-21T02:30:03", "level": "WARNING", "category": "SYSTEM", "message": "Connection timeout", "module": "telemetry", "function": "connect", "data": {}}
EOF
```

### Шаг 2: Запустить анализ с генерацией исправлений

```bash
python analyze_logs.py --log-dir logs/test_session --generate-fixes --output logs/test_report.md
```

### Ожидаемый результат:

```
================================================================================
АНАЛИЗ ЛОГОВ
================================================================================

Сессия: test_session
Всего логов: 4
Ошибок: 3
Предупреждений: 1

================================================================================
ГЕНЕРАЦИЯ ИСПРАВЛЕНИЙ
================================================================================

Сгенерировано исправлений: 3
Отчёт с исправлениями: logs/fixes_test_session.md

Предлагаемые исправления:
  1. telemetry.py:XX -> get_position
     AttributeError: 'NoneType' object has no attribute 'altitude'
  2. navigation.py:XX -> calculate_approach
     KeyError: 'runway_heading'
  3. control.py:XX -> set_autopilot
     IndexError: list index out of range
```

---

## Способ 2: Использовать реальные логи (если есть)

### Проверить наличие логов:

```bash
ls -la logs/
```

### Если есть логи, запустить анализ:

```bash
# Анализ последней сессии
python analyze_logs.py --latest --generate-fixes

# Или конкретной сессии
python analyze_logs.py --session <session_id> --generate-fixes
```

---

## Способ 3: Прямой тест AutoFixer (Python)

### Создать тестовый скрипт:

```python
# test_autofixer.py
from modules.auto_fixer import AutoFixer, CodeFix
from modules.log_analyzer import AnalysisReport, ErrorPattern

# Создать тестовый отчёт
error_pattern = ErrorPattern(
    error_type='AttributeError',
    message_pattern="'NoneType' object has no attribute 'altitude'",
    count=5,
    first_occurrence='2026-04-21T02:30:00',
    last_occurrence='2026-04-21T02:35:00',
    affected_modules=['telemetry'],
    affected_functions=['get_position'],
    sample_data=[],
    severity='HIGH'
)

report = AnalysisReport(
    session_id='test',
    analysis_time='2026-04-21T02:40:00',
    total_logs=10,
    error_count=5,
    warning_count=2,
    error_patterns=[error_pattern],
    performance_issues=[],
    recommendations=[],
    code_fixes=[{
        'error_type': 'AttributeError',
        'severity': 'HIGH',
        'affected_files': ['modules/telemetry.py'],
        'affected_functions': ['get_position'],
        'description': "'NoneType' object has no attribute 'altitude'",
        'suggested_fix': 'Добавить проверку на None перед обращением к атрибуту'
    }],
    summary='Test report'
)

# Запустить AutoFixer
fixer = AutoFixer()
fixes = fixer.generate_fixes(report)

print(f"Сгенерировано исправлений: {len(fixes)}")

for fix in fixes:
    print(f"\nИсправление:")
    print(f"  Файл: {fix.file_path}:{fix.line_number}")
    print(f"  Функция: {fix.function_name}")
    print(f"  Ошибка: {fix.error_type}")
    print(f"  Описание: {fix.description}")
    print(f"\nТекущий код:")
    print(fix.current_code)
    print(f"\nПредложенное исправление:")
    print(fix.suggested_code)
    
    # Генерация diff
    diff = fixer.generate_diff(fix)
    print(f"\nDiff:")
    print(diff)
```

### Запустить тест:

```bash
python test_autofixer.py
```

---

## Что проверить:

### 1. Анализ кода через AST
- ✅ AutoFixer находит функции в файлах
- ✅ Извлекает код функции с контекстом
- ✅ Не падает на синтаксических ошибках

### 2. Генерация исправлений
- ✅ Создаёт CodeFix для каждой ошибки
- ✅ Генерирует предложенный код с комментариями
- ✅ Добавляет объяснения

### 3. Генерация отчётов
- ✅ Создаёт Markdown отчёт
- ✅ Форматирует код в блоках ```python
- ✅ Включает diff для каждого исправления

### 4. Безопасность
- ✅ НЕ модифицирует исходные файлы
- ✅ Только читает и анализирует
- ✅ Генерирует предложения, не применяет их

---

## Ожидаемые файлы после теста:

```
logs/
├── test_session/
│   └── autoland.jsonl          # Тестовые логи
├── test_report.md              # Отчёт анализа
└── fixes_test_session.md       # Отчёт с исправлениями
```

---

## Пример отчёта fixes_*.md:

```markdown
# Отчёт автоматических исправлений

**Дата:** 2026-04-21
**Всего исправлений:** 3

---

## 1. modules/telemetry.py:45 - get_position

**Тип ошибки:** AttributeError
**Критичность:** HIGH
**Описание:** 'NoneType' object has no attribute 'altitude'

### Текущий код:

\```python
def get_position(self):
    data = self.telemetry.get_data()
    return data.altitude
\```

### Предложенное исправление:

\```python
# Добавить проверку на None перед обращением к атрибуту
# Добавить проверку:
# if obj is not None:
#     obj.attribute

def get_position(self):
    data = self.telemetry.get_data()
    if data is not None:
        return data.altitude
    return None
\```

**Объяснение:** Добавить проверку на None перед обращением к атрибуту

---
```

---

## Быстрая команда для полного теста:

```bash
cd C:/BAT/msfs_autoland

# Создать тестовые логи
mkdir -p logs/test_session
echo '{"timestamp": "2026-04-21T02:30:00", "level": "ERROR", "category": "SYSTEM", "message": "AttributeError: NoneType", "module": "telemetry", "function": "get_position", "data": {}}' > logs/test_session/autoland.jsonl

# Запустить анализ
python analyze_logs.py --log-dir logs/test_session --generate-fixes

# Проверить результат
cat logs/fixes_test_session.md
```
