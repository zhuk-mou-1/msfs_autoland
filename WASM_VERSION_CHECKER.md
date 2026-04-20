# MobiFlight WASM - Автоматическая проверка версий

**Дата:** 2026-04-18  
**Версия:** 1.0  
**Статус:** ✅ Реализовано

---

## Описание

Система автоматической проверки версии MobiFlight WASM Module с уведомлениями об обновлениях в GUI.

---

## Возможности

### 1. Автоматическая проверка при подключении

При подключении к MSFS система автоматически:
- Определяет установленную версию MobiFlight WASM
- Проверяет последнюю доступную версию на GitHub
- Сравнивает версии
- Отображает результат в GUI
- Показывает уведомление если доступно обновление

### 2. Ручная проверка обновлений

Кнопка "Check for Updates" в панели Aircraft Info позволяет:
- Проверить наличие обновлений в любой момент
- Получить информацию о последней версии
- Получить ссылку для скачивания

### 3. Визуальная индикация

**Цветовая кодировка версии:**
- 🟢 **Зелёный** - установлена последняя версия
- 🟠 **Оранжевый** - доступно обновление
- 🔴 **Красный** - MobiFlight WASM не установлен
- ⚪ **Серый** - ошибка проверки или не проверено

---

## Использование

### В GUI

1. **Запустите gui.py**
   ```bash
   python gui.py
   ```

2. **Подключитесь к MSFS**
   - Нажмите кнопку "Connect"
   - Система автоматически проверит версию WASM

3. **Просмотр версии**
   - Перейдите на вкладку "Aircraft Info (Ctrl+1)"
   - Найдите секцию "MobiFlight WASM"
   - Версия отображается рядом с "Version:"

4. **Ручная проверка**
   - Нажмите кнопку "Check for Updates"
   - Дождитесь результата проверки

### Программно

```python
from modules.wasm_version_checker import MobiFlightVersionChecker

# Создание экземпляра
checker = MobiFlightVersionChecker()

# Проверка обновлений
result = checker.check_for_updates()

# Результат содержит:
print(f"Installed: {result['installed_version']}")
print(f"Latest: {result['latest_version']}")
print(f"Update available: {result['update_available']}")
print(f"Download URL: {result['download_url']}")

# Получить сообщение для пользователя
if result['update_available']:
    message = checker.get_update_message()
    print(message)
```

### Консольный режим

```bash
# Запуск тестового скрипта
python -m modules.wasm_version_checker

# Вывод:
# ======================================================================
# MobiFlight WASM Version Checker
# ======================================================================
# 
# Результаты проверки:
#   Установленная версия: 1.0.1
#   Последняя версия: 1.0.1
#   Обновление доступно: Нет
```

---

## Архитектура

### Модуль: `modules/wasm_version_checker.py`

**Класс `MobiFlightVersionChecker`:**

```python
class MobiFlightVersionChecker:
    """Проверка версии MobiFlight WASM Module"""
    
    # Константы
    GITHUB_API_URL = "https://api.github.com/repos/MobiFlight/MobiFlight-WASM-Module/releases/latest"
    COMMUNITY_FOLDER = "C:\\Users\\MYRIG\\AppData\\Local\\Packages\\..."
    WASM_FOLDER_NAME = "mobiflight-event-module"
    
    # Методы
    def get_installed_version() -> Optional[str]
    def get_latest_version() -> Optional[Tuple[str, str]]
    def compare_versions(version1: str, version2: str) -> int
    def check_for_updates() -> Dict
    def get_update_message() -> Optional[str]
```

**Функция `check_mobiflight_version()`:**
```python
def check_mobiflight_version(show_message: bool = True) -> Dict
```

### Интеграция в GUI: `gui.py`

**Новые методы:**
1. `check_wasm_version_on_connect()` - автоматическая проверка при подключении
2. `check_wasm_updates()` - ручная проверка по кнопке

**Новые элементы интерфейса:**
1. `wasm_version_var` - StringVar для отображения версии
2. `wasm_version_label` - Label с цветовой индикацией
3. `wasm_check_btn` - Button для ручной проверки

---

## Алгоритм работы

### 1. Определение установленной версии

```
1. Открыть manifest.json в папке MobiFlight WASM
2. Прочитать поле "package_version"
3. Вернуть версию (например "1.0.1")
```

**Путь к manifest.json:**
```
C:\Users\MYRIG\AppData\Local\Packages\
Microsoft.FlightSimulator_8wekyb3d8bbwe\LocalCache\Packages\Community\
mobiflight-event-module\manifest.json
```

### 2. Получение последней версии

```
1. Запрос к GitHub API:
   GET https://api.github.com/repos/MobiFlight/MobiFlight-WASM-Module/releases/latest
   
2. Извлечь "tag_name" (например "v1.0.1")
3. Убрать префикс "v" -> "1.0.1"
4. Найти .zip файл в "assets"
5. Получить "browser_download_url"
```

### 3. Сравнение версий

```python
def compare_versions(v1, v2):
    # Разбить на числа: "1.0.1" -> [1, 0, 1]
    parts1 = [int(x) for x in v1.split('.')]
    parts2 = [int(x) for x in v2.split('.')]
    
    # Дополнить нулями до одинаковой длины
    # Сравнить поэлементно
    
    # Вернуть: -1 (v1 < v2), 0 (равны), 1 (v1 > v2)
```

### 4. Отображение результата

```
IF installed_version < latest_version:
    - Показать "v1.0.1 (Update available!)"
    - Цвет: оранжевый
    - Показать messagebox с информацией
    
ELSE IF installed_version == latest_version:
    - Показать "v1.0.1 (Up to date)"
    - Цвет: зелёный
    
ELSE IF installed_version > latest_version:
    - Показать "v1.0.2 (Newer than release)"
    - Цвет: зелёный
    
ELSE IF not installed:
    - Показать "Not installed"
    - Цвет: красный
```

---

## Примеры уведомлений

### Обновление доступно

```
⚠️ MobiFlight WASM Update Available

Update available!

Installed: v1.0.0
Latest: v1.0.1

Download from:
https://github.com/MobiFlight/MobiFlight-WASM-Module/releases/download/v1.0.1/mobiflight-event-module.zip

See MOBIFLIGHT_SETUP.md for installation instructions.
```

### Последняя версия установлена

```
✅ MobiFlight WASM

You have the latest version: v1.0.1
```

### WASM не установлен

```
⚠️ MobiFlight WASM

MobiFlight WASM is not installed.

See MOBIFLIGHT_SETUP.md for installation instructions.
```

---

## Обработка ошибок

### Ошибка чтения manifest.json

```python
try:
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
except FileNotFoundError:
    logger.warning("MobiFlight WASM manifest not found")
    return None
except Exception as e:
    logger.error(f"Error reading manifest: {e}")
    return None
```

### Ошибка запроса к GitHub

```python
try:
    response = urlopen(request, timeout=10)
except HTTPError as e:
    logger.error(f"HTTP error: {e.code} {e.reason}")
    return None
except URLError as e:
    logger.error(f"URL error: {e.reason}")
    return None
```

### Отображение ошибок в GUI

```python
if result.get('error'):
    messagebox.showerror("Check Failed", result['error'])
    wasm_version_var.set("Check failed")
    wasm_version_label.config(foreground='gray')
```

---

## Требования

### Обязательные

- Python 3.7+
- Модули стандартной библиотеки:
  - `json` - парсинг JSON
  - `os` - работа с путями
  - `re` - регулярные выражения
  - `urllib.request` - HTTP запросы
  - `logging` - логирование

### Опциональные

- Интернет-соединение для проверки GitHub API
- MobiFlight WASM установлен (для определения версии)

---

## Ограничения

1. **GitHub API Rate Limit**
   - 60 запросов в час без авторизации
   - Достаточно для нормального использования

2. **Timeout**
   - Запрос к GitHub: 10 секунд
   - При отсутствии интернета - ошибка

3. **Формат версий**
   - Поддерживаются версии вида "X.Y.Z"
   - Префикс "v" автоматически убирается

4. **Путь к Community папке**
   - Жёстко закодирован для пользователя MYRIG
   - Для других пользователей нужно изменить константу

---

## Будущие улучшения

### Приоритет 1
- [ ] Автоматическое определение пути к Community папке
- [ ] Поддержка MSFS 2024 (другой путь)
- [ ] Кэширование результата проверки (5-10 минут)

### Приоритет 2
- [ ] Автоматическое скачивание обновления
- [ ] Автоматическая установка обновления
- [ ] История версий (changelog)

### Приоритет 3
- [ ] Проверка beta/pre-release версий
- [ ] Уведомления в системном трее
- [ ] Настройка частоты проверки

---

## Тестирование

### Ручное тестирование

1. **Тест с установленным WASM:**
   ```bash
   python -m modules.wasm_version_checker
   ```
   Ожидаемый результат: версия определена

2. **Тест без WASM:**
   - Переименовать папку mobiflight-event-module
   - Запустить тест
   Ожидаемый результат: "Not installed"

3. **Тест в GUI:**
   ```bash
   python gui.py
   ```
   - Подключиться к MSFS
   - Проверить отображение версии
   - Нажать "Check for Updates"

### Автоматическое тестирование

```python
import unittest
from modules.wasm_version_checker import MobiFlightVersionChecker

class TestVersionChecker(unittest.TestCase):
    def test_compare_versions(self):
        checker = MobiFlightVersionChecker()
        
        # v1 < v2
        self.assertEqual(checker.compare_versions("1.0.0", "1.0.1"), -1)
        
        # v1 == v2
        self.assertEqual(checker.compare_versions("1.0.1", "1.0.1"), 0)
        
        # v1 > v2
        self.assertEqual(checker.compare_versions("1.0.2", "1.0.1"), 1)
```

---

## Changelog

**2026-04-18:**
- ✅ Создан модуль wasm_version_checker.py
- ✅ Интегрирован в GUI
- ✅ Добавлена автоматическая проверка при подключении
- ✅ Добавлена кнопка ручной проверки
- ✅ Реализована цветовая индикация
- ✅ Добавлены уведомления об обновлениях
- ✅ Создана документация

---

## Связанные файлы

- `modules/wasm_version_checker.py` - основной модуль
- `gui.py` - интеграция в GUI
- `MOBIFLIGHT_SETUP.md` - инструкции по установке WASM
- `modules/wasm_interface.py` - интерфейс работы с WASM

---

**Автор:** Claude (Sonnet 4)  
**Дата:** 2026-04-18 01:11 UTC+3
