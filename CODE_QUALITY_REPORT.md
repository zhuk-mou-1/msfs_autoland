# Code Quality Report - MSFS AutoLand

**Дата:** 2026-04-21 02:13 UTC+3  
**Проект:** msfs_autoland  
**Строк кода:** 14,878 (Python)

---

## Сводка

| Метрика | Значение | Статус |
|---------|----------|--------|
| **Средняя сложность (Radon)** | A (3.7) | ✅ Отлично |
| **Тесты (pytest)** | 0 тестов | ⚠️ Отсутствуют |
| **Безопасность (Bandit)** | 4 Low issues | ✅ Безопасно |
| **Линтинг (Ruff)** | 8 ошибок | ⚠️ Требует исправления |

---

## 1. Цикломатическая сложность (Radon)

**Всего блоков:** 617 (классы, функции, методы)  
**Средняя сложность:** A (3.7) - отлично

### Критическая сложность (E):
1. **modules/telemetry.py:229** - get_aircraft_info - E (38)
2. **modules/msfs_airport_reader.py:255** - auto_configure_approach - E (34)
3. **modules/aircraft_config_reader.py:208** - _detect_from_manifest - E (33)

### Высокая сложность (C):
1. modules/connection_monitor.py:346 - should_switch_method - C (19)
2. modules/navigation.py:658 - check_beacon_passage - C (18)
3. gui.py:1954 - _update_autopilot_modes_panel - C (17)
4. modules/autopilot_takeover.py:70 - should_initiate_takeover - C (17)
5. modules/telemetry.py:446 - get_approach_info - C (16)

---

## 2. Линтинг (Ruff) - 8 ошибок

### modules/approach_dialog.py (5 ошибок):
- F821: Undefined name logger (строки 198, 270, 279, 284, 472)
- **Исправление:** Добавить import logging

### modules/navigraph_parser.py (3 ошибки):
- F401: Неиспользуемые импорты lru_cache, wraps
- F541: f-string без placeholders
- **Исправление:** ruff check . --fix

---

## 3. Безопасность (Bandit)

✅ **Безопасно** - 0 критичных проблем, 4 Low issues

---

## 4. Приоритеты

### Критично:
1. Исправить 8 ошибок Ruff
2. Рефакторинг 3 методов E-сложности

### Важно:
3. Рефакторинг 8 методов C-сложности
4. Создать unit-тесты

---

## Команды

```bash
cd C:/BAT/msfs_autoland
python -m ruff check . --fix
python -m radon cc . -a -s
```

---

## Заключение

**Оценка:** ⭐⭐⭐⭐☆ (4/5)

✅ Отличная средняя сложность  
✅ Безопасный код  
❌ Отсутствие тестов  
⚠️ 3 метода критической сложности

---

## Обновление: Полный отчет Prospector

**Дата:** 2026-04-21 02:20 UTC+3  
**Время проверки:** 11.71 секунд  
**Найдено проблем:** 245

### Категории проблем:

1. **logging-fstring-interpolation** - использование f-string в logging (должно быть lazy %)
2. **too-many-locals** - слишком много локальных переменных (>15)
3. **too-many-statements** - слишком много операторов (>60)
4. **too-many-branches** - слишком много ветвлений (>15)
5. **too-many-arguments** - слишком много аргументов (>5)
6. **unused-argument** - неиспользуемые аргументы
7. **unused-variable** - неиспользуемые переменные
8. **no-else-return** - лишний else после return
9. **import-outside-toplevel** - импорты внутри функций
10. **line-too-long** - строки >120 символов

### Рекомендации:

**Приоритет 1 (Критично):**
- Рефакторинг методов E-сложности (3 метода)
- Создание unit-тестов

**Приоритет 2 (Важно):**
- Рефакторинг методов C-сложности (8 методов)
- Исправление logging f-string → lazy %

**Приоритет 3 (Желательно):**
- Уменьшение количества локальных переменных
- Удаление неиспользуемых аргументов
- Перемещение импортов в начало файлов

**Статус:** Код функционален и безопасен, но требует рефакторинга для улучшения поддерживаемости.
