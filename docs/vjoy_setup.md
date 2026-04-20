# Установка и настройка vJoy

## Что такое vJoy?

vJoy (Virtual Joystick) - это драйвер виртуального джойстика для Windows, который позволяет программам эмулировать физический джойстик.

## Установка vJoy драйвера

### Шаг 1: Скачать vJoy

Скачайте последнюю версию vJoy с официального сайта:
- **Ссылка:** https://sourceforge.net/projects/vjoystick/
- **Файл:** vJoySetup.exe

### Шаг 2: Установить драйвер

1. Запустите `vJoySetup.exe` от имени администратора
2. Следуйте инструкциям установщика
3. Перезагрузите компьютер после установки

### Шаг 3: Настроить vJoy устройство

1. Откройте **vJoy Configure** (Start Menu → vJoy → Configure vJoy)
2. Выберите **Device 1**
3. Настройте оси:
   - ✅ Enable Device
   - ✅ X Axis (Aileron - элероны)
   - ✅ Y Axis (Elevator - руль высоты)
   - ✅ Z Axis (Rudder - руль направления)
   - ✅ Rz Axis (Throttle - газ)
4. Нажмите **Apply**

### Шаг 4: Проверить устройство

1. Откройте **Windows Game Controllers** (Win+R → `joy.cpl`)
2. Вы должны увидеть **vJoy Device**
3. Нажмите **Properties** для проверки осей

---

## Установка Python библиотеки

Установите pyvjoy:

```bash
pip install pyvjoy
```

Если возникают проблемы, попробуйте:

```bash
pip install git+https://github.com/tidzo/pyvjoy.git
```

---

## Настройка MSFS

### Шаг 1: Включить vJoy в MSFS

1. Запустите Microsoft Flight Simulator
2. Откройте **Options → Controls**
3. В списке устройств найдите **vJoy Device**
4. Убедитесь, что устройство активно

### Шаг 2: Настроить оси (опционально)

Если MSFS не распознаёт оси автоматически:

1. **Controls → Control Options**
2. Выберите **vJoy Device**
3. Назначьте оси:
   - X Axis → Ailerons
   - Y Axis → Elevator
   - Z Axis → Rudder
   - Rz Axis → Throttle

---

## Использование в программе

### Базовое использование:

```python
from modules.virtual_joystick import VirtualJoystick

# Создание и подключение
joystick = VirtualJoystick(device_id=1)
if joystick.connect():
    print("vJoy connected!")
    
    # Установка элеронов (крен)
    joystick.set_aileron(0.5)  # Правый крен
    
    # Установка руля высоты (тангаж)
    joystick.set_elevator(0.2)  # Вверх
    
    # Установка руля направления
    joystick.set_rudder(-0.3)  # Влево
    
    # Установка газа
    joystick.set_throttle(0.75)  # 75%
    
    # Центрирование
    joystick.center_all_axes()
    
    # Отключение
    joystick.disconnect()
```

### Автоматическая коррекция:

```python
# Коррекция крена
current_bank = 5.0  # градусы
target_bank = 0.0   # градусы
aileron_input = joystick.calculate_bank_correction(current_bank, target_bank)
joystick.set_aileron(aileron_input)

# Коррекция курса
current_heading = 270
target_heading = 280
target_bank = joystick.calculate_heading_correction(current_heading, target_heading, current_bank)
aileron_input = joystick.calculate_bank_correction(current_bank, target_bank)
joystick.set_aileron(aileron_input)
```

---

## Интеграция с AutoLand

Система автоматически определит наличие vJoy и использует его для точного управления:

```python
system = AutoLandSystem()
system.connect()

# Если vJoy доступен, система будет использовать его
# для прямого управления рулями
```

---

## Режимы управления

### Режим 1: Только автопилот (SimConnect)
- Используется по умолчанию
- Управление через автопилот MSFS
- Менее точное, но стабильное

### Режим 2: Прямое управление (vJoy)
- Требует установки vJoy
- Прямое управление рулями
- Более точное и плавное

### Режим 3: Гибридный (рекомендуется)
- SimConnect для автопилота и систем
- vJoy для коррекции крена/тангажа
- Лучшая точность и стабильность

---

## Устранение проблем

### vJoy не обнаруживается

1. Проверьте, что драйвер установлен:
   ```
   C:\Program Files\vJoy\x64\vJoyConfig.exe
   ```

2. Убедитесь, что Device 1 включён в vJoy Configure

3. Перезагрузите компьютер

### MSFS не видит vJoy

1. Перезапустите MSFS
2. Проверьте в Windows Game Controllers (joy.cpl)
3. Переназначьте оси в MSFS Controls

### pyvjoy не устанавливается

1. Обновите pip:
   ```bash
   python -m pip install --upgrade pip
   ```

2. Установите из GitHub:
   ```bash
   pip install git+https://github.com/tidzo/pyvjoy.git
   ```

### Оси не работают

1. Откройте vJoy Configure
2. Убедитесь, что все нужные оси включены
3. Нажмите Apply и перезапустите программу

---

## Ограничения

- vJoy работает только на Windows
- Требует прав администратора для установки
- Может конфликтовать с другими виртуальными устройствами
- Максимум 16 виртуальных устройств

---

## Альтернативы

Если vJoy не работает, можно использовать:

1. **SimConnect только** - управление через автопилот
2. **FreePIE** - альтернативный виртуальный джойстик
3. **UCR (Universal Control Remapper)** - маппинг устройств

---

## Полезные ссылки

- vJoy официальный сайт: https://sourceforge.net/projects/vjoystick/
- pyvjoy GitHub: https://github.com/tidzo/pyvjoy
- Документация vJoy: http://vjoystick.sourceforge.net/site/
- MSFS SDK: https://docs.flightsimulator.com/

---

## Проверка установки

Запустите тестовый скрипт:

```python
from modules.virtual_joystick import VirtualJoystick

joystick = VirtualJoystick()
if joystick.connect():
    print("✅ vJoy работает!")
    joystick.center_all_axes()
    joystick.disconnect()
else:
    print("❌ vJoy не найден. Установите драйвер.")
```
