# Установка MobiFlight WASM модуля

## Что такое MobiFlight WASM?

MobiFlight WASM - это бесплатный модуль для Microsoft Flight Simulator, который позволяет читать и записывать локальные переменные (LVARs) кастомных самолётов через SimConnect.

**Необходим для работы с:**
- PMDG 737/777/747
- Fenix A320
- FSLabs A320/A319/A321
- iniBuilds A300/A310
- FlyByWire A32NX

---

## Пошаговая установка

### Шаг 1: Скачать модуль

1. Перейдите на GitHub: https://github.com/MobiFlight/MobiFlight-WASM-Module/releases
2. Скачайте последнюю версию (файл `mobiflight-event-module.zip`)

### Шаг 2: Найти папку Community

**Для Microsoft Store версии:**
```
C:\Users\<ИМЯ_ПОЛЬЗОВАТЕЛЯ>\AppData\Local\Packages\Microsoft.FlightSimulator_8wekyb3d8bbwe\LocalCache\Packages\Community\
```

**Для Steam версии:**
```
C:\Users\<ИМЯ_ПОЛЬЗОВАТЕЛЯ>\AppData\Roaming\Microsoft Flight Simulator\Packages\Community\
```

**Для Boxed версии:**
```
C:\Users\<ИМЯ_ПОЛЬЗОВАТЕЛЯ>\AppData\Local\MSFSPackages\Community\
```

### Шаг 3: Установить модуль

1. Распакуйте скачанный `mobiflight-event-module.zip`
2. Скопируйте папку `mobiflight-event-module` в папку `Community`
3. Структура должна быть:
   ```
   Community\
   └── mobiflight-event-module\
       ├── manifest.json
       ├── layout.json
       └── ...
   ```

### Шаг 4: Перезапустить MSFS

1. Полностью закройте Microsoft Flight Simulator
2. Запустите снова
3. Модуль загрузится автоматически

---

## Проверка установки

### Способ 1: Через наш тестовый скрипт

```bash
cd C:/BAT/msfs_autoland
python test_lvar.py
```

**Ожидаемый результат:**
```
MobiFlight WASM connected successfully
✅ WASM module is working
```

### Способ 2: Через логи MSFS

1. Запустите MSFS
2. Откройте Developer Mode (Alt + Z)
3. Console → Filter: "MobiFlight"
4. Должны увидеть сообщения о загрузке модуля

### Способ 3: Через наш AutoLand

```bash
cd C:/BAT/msfs_autoland
python test_aircraft_detection.py
```

**В выводе должно быть:**
```
MobiFlight WASM connected - LVAR support enabled
✅ Full functionality available
```

---

## Устранение проблем

### Модуль не загружается

**Проблема:** MSFS не видит модуль

**Решение:**
1. Проверьте путь к папке Community
2. Убедитесь что папка называется `mobiflight-event-module`
3. Проверьте наличие файла `manifest.json` внутри
4. Перезапустите MSFS

### WASM not connected

**Проблема:** Наша программа не видит WASM

**Решение:**
1. Убедитесь что MSFS запущен
2. Загрузите любой полёт (самолёт должен быть в воздухе)
3. Подождите 10-15 секунд после загрузки
4. Запустите нашу программу

### Permission denied

**Проблема:** Нет доступа к папке Community

**Решение:**
1. Запустите проводник от имени администратора
2. Или измените права доступа к папке Community

---

## Альтернатива: FSUIPC (платный)

Если MobiFlight WASM не работает, можно использовать FSUIPC:

### Преимущества FSUIPC:
- ✅ Более стабильный
- ✅ Больше возможностей
- ✅ Официальная поддержка

### Недостатки:
- ❌ Платный ($30 USD)
- ❌ Требует установки драйвера

### Установка FSUIPC:

1. Купить: https://fsuipc.com/
2. Скачать FSUIPC 7 для MSFS
3. Установить
4. Установить Python библиотеку:
   ```bash
   pip install pyuipc
   ```

**Примечание:** Наша программа автоматически определит FSUIPC если он установлен.

---

## Проверка работы с кастомными самолётами

### PMDG 737

1. Загрузите PMDG 737 в MSFS
2. Запустите наш тест:
   ```bash
   python test_aircraft_detection.py
   ```

**Ожидаемый результат:**
```
Detected aircraft: PMDG 737-800
Manufacturer: PMDG, Type: PMDG_737
Using custom profile: PMDG 737
MobiFlight WASM connected - LVAR support enabled

✅ This aircraft is COMPATIBLE with AutoLand system
   Full functionality available
   WASM: Available
```

### Fenix A320

```
Detected aircraft: Fenix A320
Manufacturer: FENIX, Type: FENIX_A320
Using custom profile: Fenix A320
MobiFlight WASM connected - LVAR support enabled

✅ This aircraft is COMPATIBLE with AutoLand system
   Full functionality available
   WASM: Available
```

---

## Что дальше?

После установки MobiFlight WASM:

1. ✅ Все команды автопилота будут работать напрямую
2. ✅ Чтение статуса кастомных систем
3. ✅ Полная поддержка PMDG/Fenix/FSLabs
4. ✅ Автоматическая тяга через кастомные системы

**Наша программа автоматически:**
- Определит наличие WASM
- Переключится на LVAR команды
- Использует кастомные события
- Fallback на SimConnect если что-то не работает

---

## Дополнительная информация

**Официальная документация:**
- MobiFlight: https://www.mobiflight.com/
- GitHub: https://github.com/MobiFlight/MobiFlight-WASM-Module
- Wiki: https://github.com/MobiFlight/MobiFlight-WASM-Module/wiki

**Поддержка:**
- Discord: https://discord.gg/S5sjCC9
- Forum: https://www.mobiflight.com/forum/

---

## Часто задаваемые вопросы

**Q: Нужно ли устанавливать MobiFlight Connector?**
A: Нет, для нашей программы нужен только WASM модуль.

**Q: Работает ли с MSFS 2024?**
A: Да, MobiFlight WASM поддерживает MSFS 2020 и 2024.

**Q: Можно ли использовать без WASM?**
A: Да, программа будет работать через SimConnect fallback, но с ограниченной функциональностью для кастомных самолётов.

**Q: Безопасно ли это?**
A: Да, MobiFlight WASM - это open source проект с активным сообществом.

**Q: Влияет ли на производительность?**
A: Минимально, модуль очень легковесный.

---

**Готово! Теперь ваша система AutoLand полностью поддерживает кастомные самолёты!** ✈️
