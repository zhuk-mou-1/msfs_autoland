# VS Code Setup Guide - MSFS AutoLand

## Быстрый старт

### 1. Открыть проект

```bash
cd C:\BAT\msfs_autoland
code .
```

Или: **File → Open Folder** → `C:\BAT\msfs_autoland`

### 2. Установить рекомендуемые расширения

При первом открытии VS Code предложит установить расширения.
Нажмите **"Install All"** или установите вручную:

- **Python** (Microsoft) - обязательно
- **Pylance** (Microsoft) - обязательно
- **Markdown All in One** - для документации
- **GitLens** - для Git (опционально)

### 3. Выбрать интерпретатор Python

1. **Ctrl+Shift+P** → "Python: Select Interpreter"
2. Выберите Python 3.7+ (тот же что используете в командной строке)

## Конфигурационные файлы

Созданы автоматически в `.vscode/`:

### ✅ settings.json
- Настройки Python (linting, formatting)
- Исключения файлов (__pycache__, *.pyc)
- Настройки редактора (rulers, tabs)
- Auto-save через 1 секунду

### ✅ launch.json
- **F5** → Запуск с отладкой
- 6 конфигураций:
  - AutoLand GUI (gui.py)
  - AutoLand Main (main.py)
  - Current File (текущий файл)
  - Analyze Logs
  - Claude Read Logs
  - Debug with Arguments

### ✅ tasks.json
- **Ctrl+Shift+B** → Run AutoLand GUI (по умолчанию)
- **Ctrl+Shift+P** → "Tasks: Run Task" → выбрать:
  - Run AutoLand GUI
  - Run AutoLand Main
  - Analyze Logs
  - Install Dependencies
  - Clean Python Cache

### ✅ extensions.json
- Рекомендуемые расширения
- VS Code предложит установить автоматически

## Горячие клавиши

### Навигация
- **Ctrl+P** - Быстрый поиск файлов
- **Ctrl+Shift+F** - Поиск по проекту
- **Ctrl+T** - Поиск символов (классы, функции)
- **F12** - Перейти к определению
- **Alt+F12** - Peek определение
- **Ctrl+Shift+O** - Символы в текущем файле

### Редактирование
- **Ctrl+D** - Выделить следующее вхождение
- **Ctrl+Shift+L** - Выделить все вхождения
- **Alt+Click** - Множественные курсоры
- **Ctrl+/** - Закомментировать/раскомментировать
- **Shift+Alt+F** - Форматировать документ
- **F2** - Переименовать символ (везде)

### Отладка
- **F5** - Запустить отладку
- **F9** - Установить/убрать breakpoint
- **F10** - Step over (следующая строка)
- **F11** - Step into (войти в функцию)
- **Shift+F11** - Step out (выйти из функции)
- **Ctrl+Shift+F5** - Перезапустить отладку

### Терминал
- **Ctrl+`** - Открыть/закрыть терминал
- **Ctrl+Shift+`** - Новый терминал

### Панели
- **Ctrl+B** - Показать/скрыть боковую панель
- **Ctrl+Shift+E** - Explorer
- **Ctrl+Shift+G** - Source Control (Git)
- **Ctrl+Shift+D** - Debug
- **Ctrl+Shift+X** - Extensions

### Markdown
- **Ctrl+Shift+V** - Предварительный просмотр
- **Ctrl+K V** - Открыть preview сбоку

## Быстрые команды (Tasks)

### Запуск GUI (по умолчанию)
```
Ctrl+Shift+B
```

### Другие задачи
```
Ctrl+Shift+P → Tasks: Run Task → выбрать
```

Доступные задачи:
- **Run AutoLand GUI** - запуск GUI
- **Run AutoLand Main** - запуск main.py
- **Analyze Logs** - анализ логов
- **Claude Read Logs** - чтение логов для Claude
- **Install Dependencies** - установка зависимостей
- **Check Python Version** - проверка версии Python
- **List Installed Packages** - список установленных пакетов
- **Clean Python Cache** - очистка кэша Python

## Отладка

### Запуск с отладкой

1. **Откройте файл** (например, gui.py)
2. **Установите breakpoint** (F9 на нужной строке)
3. **Нажмите F5** → выберите "Python: AutoLand GUI"
4. **Программа остановится** на breakpoint
5. **Смотрите переменные** в панели Debug (слева)
6. **Используйте F10/F11** для пошагового выполнения

### Панель Debug

Когда программа остановлена на breakpoint, вы видите:
- **Variables** - все переменные в текущей области
- **Watch** - отслеживаемые выражения
- **Call Stack** - стек вызовов
- **Breakpoints** - список всех breakpoints

### Debug Console

Внизу появится **Debug Console**, где можно:
```python
# Выполнить любой Python код
print(self.connection_monitor.current_method)
self.telemetry.get_all_data()
```

## Работа с проектом

### Структура проекта в Explorer

```
📁 msfs_autoland/
├── 📁 .vscode/          ← Конфигурация VS Code
├── 📁 modules/          ← Модули проекта
├── 📁 config/           ← Конфигурационные файлы
├── 📁 logs/             ← Логи
├── 📄 main.py           ← Главный файл
├── 📄 gui.py            ← GUI
└── 📄 *.md              ← Документация
```

### Поиск в проекте

**Найти файл:**
```
Ctrl+P → введите имя файла
Например: "connection_monitor"
```

**Найти текст:**
```
Ctrl+Shift+F → введите текст
Например: "def get_status"
```

**Найти символ:**
```
Ctrl+T → введите имя класса/функции
Например: "ConnectionMonitor"
```

### Просмотр документации

1. **Ctrl+P** → введите имя .md файла
2. **Ctrl+Shift+V** → предварительный просмотр
3. Или **Ctrl+K V** → preview сбоку

Документация:
- `CONNECTION_OPTIMIZER.md`
- `CONNECTION_MONITOR.md`
- `VJOY_MONITOR.md`
- `CURRENT_STATE.md`
- `CLAUDE.md`

### IntelliSense (автодополнение)

При вводе кода VS Code показывает:
- Доступные методы и свойства
- Документацию (docstrings)
- Типы параметров
- Примеры использования

```python
self.connection_monitor.  # ← автодополнение покажет все методы
```

### Переход к определению

**Способ 1:** Ctrl+Click на имени класса/функции
**Способ 2:** F12 на имени
**Способ 3:** Правый клик → "Go to Definition"

```python
from modules.connection_monitor import ConnectionMonitor
#                                      ↑ Ctrl+Click здесь
```

### Поиск использований

**Правый клик** на методе/классе → **"Find All References"**

Покажет все места где используется:
```python
def get_status(self):  # ← Find All References
    # Найдёт все вызовы get_status() в проекте
```

## Терминал

### Встроенный терминал (Ctrl+`)

```bash
# Запуск GUI
python gui.py

# Запуск main
python main.py

# Установка зависимостей
pip install -r requirements.txt

# Анализ логов
python claude_read_logs.py

# Проверка версии
python --version
```

### Несколько терминалов

- **Ctrl+Shift+`** - новый терминал
- **Dropdown** справа - переключение между терминалами
- **Split Terminal** - разделить терминал

## Git интеграция (опционально)

### Инициализация Git

```bash
git init
git add .
git commit -m "Initial commit with Connection Monitor and vJoy Monitor"
```

### Source Control (Ctrl+Shift+G)

- Видите все изменённые файлы
- Можете делать commit прямо из VS Code
- GitLens показывает историю изменений

## Полезные советы

### 1. Быстрое открытие файлов

```
Ctrl+P → connection  → Enter
# Откроет connection_monitor.py
```

### 2. Множественное редактирование

```
Ctrl+D несколько раз → выделит все вхождения
Alt+Click → множественные курсоры
```

### 3. Форматирование кода

```
Shift+Alt+F → форматирует весь файл
```

### 4. Комментирование блоков

```
Выделить блок → Ctrl+/ → закомментировать/раскомментировать
```

### 5. Сворачивание кода

```
Ctrl+Shift+[ → свернуть блок
Ctrl+Shift+] → развернуть блок
```

### 6. Переход между ошибками

```
F8 → следующая ошибка/предупреждение
Shift+F8 → предыдущая ошибка
```

## Проблемы и решения

### Python не найден

**Проблема:** "Python was not found"

**Решение:**
1. Ctrl+Shift+P → "Python: Select Interpreter"
2. Выберите установленный Python
3. Или укажите путь вручную в settings.json

### Нет автодополнения

**Проблема:** IntelliSense не работает

**Решение:**
1. Установите расширение **Pylance**
2. Перезапустите VS Code
3. Ctrl+Shift+P → "Python: Restart Language Server"

### Ошибки импорта

**Проблема:** "Import could not be resolved"

**Решение:**
1. Убедитесь что PYTHONPATH правильный
2. Проверьте что все зависимости установлены
3. Перезапустите VS Code

## Рекомендуемый workflow

### Ежедневная работа

1. **Открыть VS Code** → `C:\BAT\msfs_autoland`
2. **Ctrl+P** → Найти нужный файл
3. **Редактировать** с автодополнением
4. **Ctrl+Shift+B** → Запустить GUI для тестирования
5. **Ctrl+`** → Проверить вывод в терминале

### Отладка проблем

1. **Ctrl+Shift+F** → Найти где используется метод
2. **F9** → Установить breakpoint
3. **F5** → Запустить с отладкой
4. **Посмотреть переменные** в Debug панели
5. **F10/F11** → Пошаговое выполнение

### Работа с документацией

1. **Ctrl+P** → `CONNECTION_MONITOR.md`
2. **Ctrl+K V** → Preview сбоку
3. **Редактировать** с live preview
4. **Ctrl+S** → Сохранить

---

**Готово!** Проект полностью настроен для работы в VS Code. 🚀

**Следующий шаг:** Откройте проект в VS Code и попробуйте:
1. `code C:\BAT\msfs_autoland`
2. Установите рекомендуемые расширения
3. Нажмите **Ctrl+Shift+B** для запуска GUI
