# FSUIPC / MobiFlight WASM - Интеграция (TODO)

## Статус: Не реализовано

Для полной поддержки кастомных самолётов (PMDG, Fenix, FSLabs, iniBuilds) требуется доступ к локальным переменным (LVARs).

---

## Варианты реализации

### Вариант 1: FSUIPC (Рекомендуется)

**Преимущества:**
- ✅ Стабильная работа
- ✅ Полная документация
- ✅ Поддержка всех типов переменных
- ✅ Python библиотека `pyuipc`

**Недостатки:**
- ❌ Платный ($30 USD)
- ❌ Требует установки драйвера

**Установка:**
```bash
# 1. Купить и установить FSUIPC 7
# https://fsuipc.com/

# 2. Установить Python библиотеку
pip install pyuipc
```

**Пример использования:**
```python
import pyuipc

# Подключение
fsuipc = pyuipc.open(0)

# Чтение LVAR
value = fsuipc.read_lvar("PMDG_737_MCP_Course")

# Запись LVAR
fsuipc.write_lvar("PMDG_737_MCP_Course", 270)

# Отправка события
fsuipc.send_event("PMDG_737_MCP_COURSE_SELECTOR")
```

---

### Вариант 2: MobiFlight WASM (Бесплатный)

**Преимущества:**
- ✅ Бесплатный
- ✅ Open source
- ✅ Активная разработка
- ✅ Поддержка MSFS 2020/2024

**Недостатки:**
- ❌ Требует установки WASM модуля
- ❌ Менее стабильный чем FSUIPC
- ❌ Нет готовой Python библиотеки

**Установка:**
```bash
# 1. Скачать WASM модуль
# https://github.com/MobiFlight/MobiFlight-WASM-Module/releases

# 2. Распаковать в папку Community MSFS
# C:\Users\<User>\AppData\Local\Packages\Microsoft.FlightSimulator_...\LocalCache\Packages\Community\

# 3. Перезапустить MSFS
```

**Пример использования (через SimConnect):**
```python
# MobiFlight использует специальные SimConnect события
# Требуется реализация протокола

# Чтение LVAR
# CLIENT_DATA_ID = 1
# REQUEST_ID = 1
sm.map_client_data_name_to_id("MobiFlight.LVars", CLIENT_DATA_ID)
sm.request_client_data(CLIENT_DATA_ID, REQUEST_ID, ...)

# Запись LVAR
# Аналогично через CLIENT_DATA
```

---

## План реализации

### Этап 1: FSUIPC интеграция (приоритет)

**Файл:** `modules/fsuipc_interface.py`

```python
class FSUIPCInterface:
    """Интерфейс для работы с FSUIPC"""
    
    def __init__(self):
        self.connected = False
        self.fsuipc = None
    
    def connect(self) -> bool:
        """Подключение к FSUIPC"""
        try:
            import pyuipc
            self.fsuipc = pyuipc.open(0)
            self.connected = True
            return True
        except ImportError:
            logger.error("pyuipc not installed")
            return False
        except Exception as e:
            logger.error(f"FSUIPC connection failed: {e}")
            return False
    
    def read_lvar(self, name: str) -> Optional[float]:
        """Чтение локальной переменной"""
        if not self.connected:
            return None
        try:
            return self.fsuipc.read_lvar(name)
        except Exception as e:
            logger.error(f"Error reading LVAR {name}: {e}")
            return None
    
    def write_lvar(self, name: str, value: float) -> bool:
        """Запись локальной переменной"""
        if not self.connected:
            return False
        try:
            self.fsuipc.write_lvar(name, value)
            return True
        except Exception as e:
            logger.error(f"Error writing LVAR {name}: {e}")
            return False
    
    def send_event(self, event: str, param: int = 0) -> bool:
        """Отправка события"""
        if not self.connected:
            return False
        try:
            self.fsuipc.send_event(event, param)
            return True
        except Exception as e:
            logger.error(f"Error sending event {event}: {e}")
            return False
```

### Этап 2: Интеграция в адаптер

**Обновить:** `modules/aircraft_adapter.py`

```python
class AircraftCommandAdapter:
    def __init__(self, control, telemetry):
        self.control = control
        self.telemetry = telemetry
        self.fsuipc = None
        
        # Попытка подключения к FSUIPC
        try:
            from modules.fsuipc_interface import FSUIPCInterface
            self.fsuipc = FSUIPCInterface()
            if self.fsuipc.connect():
                logger.info("FSUIPC connected - LVAR support enabled")
            else:
                self.fsuipc = None
        except ImportError:
            logger.info("FSUIPC not available - using SimConnect only")
    
    def set_heading(self, heading: int) -> bool:
        cmd = self.current_profile['autopilot']['commands']['heading']
        method = cmd.get('method', 'simconnect')
        
        if method == 'lvar' and self.fsuipc:
            # Через FSUIPC
            variable = cmd.get('variable')
            event = cmd.get('event')
            
            if self.fsuipc.write_lvar(variable, heading):
                if event:
                    self.fsuipc.send_event(event)
                logger.debug(f"Set heading via LVAR: {variable} = {heading}")
                return True
        
        # Fallback на SimConnect
        self.control.set_heading_hold(heading)
        return True
```

### Этап 3: Тестирование

**Тестовые самолёты:**
1. PMDG 737-800
2. Fenix A320
3. FlyByWire A32NX

**Тестовые сценарии:**
- Установка курса
- Установка высоты
- Включение режима APP
- Чтение статуса автопилота

---

## Альтернативные решения

### SimConnect L:Vars (ограниченно)

MSFS 2020/2024 поддерживает некоторые L:Vars через SimConnect:

```python
# Чтение
value = aq.get("L:PMDG_737_MCP_Course")

# Запись (не всегда работает)
ae.trigger("L:PMDG_737_MCP_Course", value)
```

**Проблемы:**
- Не все переменные доступны
- Запись работает нестабильно
- Нет поддержки событий

---

## Текущий статус

**Реализовано:**
- ✅ Структура для LVAR поддержки
- ✅ Fallback на SimConnect
- ✅ Профили с LVAR командами

**Не реализовано:**
- ❌ FSUIPC интеграция
- ❌ MobiFlight WASM интеграция
- ❌ Чтение LVAR статусов
- ❌ Отправка кастомных событий

**Работает:**
- ✅ Определение кастомных самолётов
- ✅ Загрузка профилей
- ✅ Fallback команды через SimConnect

**Не работает:**
- ❌ Прямое управление PMDG системами
- ❌ Прямое управление Fenix системами
- ❌ Чтение статуса кастомных автопилотов

---

## Рекомендации

### Для пользователей

**Если у вас есть PMDG/Fenix/FSLabs:**

1. **Установите FSUIPC 7** ($30)
   - Полная функциональность
   - Стабильная работа
   - Официальная поддержка

2. **Или используйте MobiFlight WASM** (бесплатно)
   - Базовая функциональность
   - Требует дополнительной настройки

3. **Или используйте как есть**
   - Ограниченная функциональность
   - Fallback на SimConnect
   - Может не работать корректно

### Для разработчиков

**Приоритет реализации:**

1. **FSUIPC интеграция** - максимальная совместимость
2. **Тестирование на реальных аддонах**
3. **MobiFlight WASM** - бесплатная альтернатива
4. **Расширение профилей** - больше самолётов

---

## Ссылки

- FSUIPC: https://fsuipc.com/
- pyuipc: https://pypi.org/project/pyuipc/
- MobiFlight WASM: https://github.com/MobiFlight/MobiFlight-WASM-Module
- MobiFlight Hub: https://www.mobiflight.com/

---

**Статус:** Ожидает реализации FSUIPC/WASM интеграции
