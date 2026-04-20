# Исследование альтернатив MobiFlight WASM

**Дата:** 2026-04-17  
**Проблема:** Python-SimConnect 0.4.26 не поддерживает CLIENT_DATA API

## Текущая ситуация

### Используемая библиотека
- **Название:** Python-SimConnect
- **Версия:** 0.4.26
- **Автор:** Anthony Pray (odwdinc)
- **GitHub:** https://github.com/odwdinc/Python-SimConnect
- **Лицензия:** AGPL 3.0

### Проблема
Библиотека не реализует CLIENT_DATA API, необходимый для работы с MobiFlight WASM:
- Отсутствует метод `map_client_data_name_to_id`
- Отсутствует метод `add_to_client_data_definition`
- Отсутствует метод `request_client_data`
- Отсутствует метод `set_client_data`

**Доступные методы:** только `get_data`, `request_data`, `set_data` (базовый SimConnect)

### Текущее решение
Проект использует **fallback механизм**:
1. Попытка подключения к MobiFlight WASM
2. При ошибке автоматическое переключение на SimConnect
3. Работа с ограниченной функциональностью (только стандартные SimVars)

## Альтернативы

### 1. Обновление Python-SimConnect (рекомендуется)

**Вариант A: Проверить новые версии**
- Проверить GitHub репозиторий на наличие обновлений
- Возможно CLIENT_DATA API добавлен в более новых коммитах
- Установить из GitHub: `pip install git+https://github.com/odwdinc/Python-SimConnect.git`

**Вариант B: Создать Pull Request**
- Реализовать CLIENT_DATA API самостоятельно
- Добавить методы в библиотеку
- Отправить PR в основной репозиторий

**Вариант C: Форк библиотеки**
- Создать форк Python-SimConnect
- Добавить CLIENT_DATA API
- Использовать свою версию

### 2. Альтернативные библиотеки

**FSUIPC (коммерческое решение)**
- Требует покупки лицензии FSUIPC7 для MSFS
- Python библиотека: pyuipc
- Поддерживает L:Vars через Offset API
- **Минусы:** платное, дополнительный софт

**SimConnect.dll напрямую через ctypes**
- Использовать SimConnect.dll напрямую
- Реализовать CLIENT_DATA API вручную
- Полный контроль над функциональностью
- **Минусы:** сложная реализация, много низкоуровневого кода

**WASM модуль с HTTP API**
- Создать собственный WASM модуль
- Использовать HTTP/WebSocket для коммуникации
- Обход SimConnect CLIENT_DATA
- **Минусы:** требует разработки WASM модуля

### 3. Работа без WASM (текущий подход)

**Преимущества:**
- Работает прямо сейчас
- Не требует дополнительных зависимостей
- Поддерживает стандартные самолёты MSFS

**Ограничения:**
- Нет доступа к L:Vars (локальные переменные)
- Ограниченная поддержка кастомных автопилотов (PMDG, Fenix)
- Нет возможности отправки кастомных событий

**Поддерживаемые самолёты:**
- ✅ Все стандартные самолёты MSFS (Asobo)
- ✅ Самолёты с SimConnect-совместимым автопилотом
- ❌ PMDG 737/777 (требуют L:Vars для полной функциональности)
- ❌ Fenix A320 (требует L:Vars)
- ❌ FlyByWire A32NX (частичная поддержка)

## Рекомендации

### Краткосрочные (сейчас)
1. ✅ **Продолжать использовать fallback** - система работает со стандартными самолётами
2. ✅ **Документировать ограничения** - пользователи должны знать о них
3. ✅ **Тестировать с доступными самолётами** - TBM 930, Cessna, Airbus A320neo (стандартный)

### Среднесрочные (1-2 недели)
1. 🔍 **Проверить GitHub Python-SimConnect** - возможно есть обновления
2. 🔍 **Изучить исходный код библиотеки** - оценить сложность добавления CLIENT_DATA
3. 🔍 **Связаться с автором** - создать issue на GitHub с запросом функциональности

### Долгосрочные (1-2 месяца)
1. 🛠️ **Реализовать CLIENT_DATA API** - форк или PR в основной репозиторий
2. 🛠️ **Альтернативная библиотека** - рассмотреть создание собственной обёртки
3. 🛠️ **WASM модуль с HTTP** - если CLIENT_DATA не получится

## Технические детали

### Необходимые методы CLIENT_DATA API

```python
# Регистрация CLIENT_DATA области
sm.map_client_data_name_to_id(name: str, client_data_id: int)

# Определение структуры данных
sm.add_to_client_data_definition(
    define_id: int,
    offset: int,
    size: int,
    epsilon: float = 0.0,
    datum_id: int = 0
)

# Запрос данных
sm.request_client_data(
    client_data_id: int,
    request_id: int,
    define_id: int,
    period: int = 0,
    flags: int = 0
)

# Установка данных
sm.set_client_data(
    client_data_id: int,
    define_id: int,
    flags: int,
    reserved: int,
    data_size: int,
    data: bytes
)
```

### Пример использования (если бы работало)

```python
# Регистрация MobiFlight CLIENT_DATA
sm.map_client_data_name_to_id("MobiFlight.Command", 100)
sm.map_client_data_name_to_id("MobiFlight.Response", 101)

# Определение структуры команды
sm.add_to_client_data_definition(1000, 0, 256)

# Отправка команды на чтение L:Var
command = struct.pack("I256s", CMD_GET_LVAR, b"L:AUTOPILOT_MASTER")
sm.set_client_data(100, 1000, 0, 0, len(command), command)

# Чтение ответа
sm.request_client_data(101, 1001, 1001)
```

## Статус

**Текущий статус:** ❌ MobiFlight WASM не работает  
**Fallback статус:** ✅ SimConnect работает  
**Влияние на проект:** ⚠️ Ограниченная поддержка кастомных самолётов  
**Приоритет исправления:** Средний (не блокирует основную функциональность)

## Ссылки

- Python-SimConnect: https://github.com/odwdinc/Python-SimConnect
- MobiFlight WASM: https://github.com/MobiFlight/MobiFlight-WASM-Module
- SimConnect SDK Documentation: Microsoft Flight Simulator SDK
- FSUIPC: http://www.fsuipc.com/

## История изменений

- **2026-04-17:** Первоначальное исследование, документирование проблемы
- **2026-04-17:** Подтверждено отсутствие CLIENT_DATA API в версии 0.4.26
- **2026-04-17:** Fallback механизм работает корректно
