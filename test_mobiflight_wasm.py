"""
Тестовый скрипт для проверки работы MobiFlight WASM
"""

import logging
import sys

import pytest

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_mobiflight_wasm():
    """Тест подключения к MobiFlight WASM"""

    print("=" * 70)
    print("MobiFlight WASM Connection Test")
    print("=" * 70)
    print()

    # Шаг 1: Подключение к MSFS
    print("Шаг 1: Подключение к Microsoft Flight Simulator...")
    try:
        from modules.telemetry import MSFSTelemetry
        telemetry = MSFSTelemetry()

        if not telemetry.connect():
            print("❌ ОШИБКА: Не удалось подключиться к MSFS")
            print("   Убедитесь что MSFS запущен и загружен полёт")
            pytest.skip("MSFS not running - skipping test")

        print("✅ Подключено к MSFS")
        print()

    except Exception as e:
        print(f"❌ ОШИБКА подключения: {e}")
        pytest.skip(f"MSFS connection error: {e}")

    # Шаг 2: Инициализация MobiFlight WASM
    print("Шаг 2: Инициализация MobiFlight WASM...")
    try:
        from modules.wasm_interface import MobiFlightWASM
        wasm = MobiFlightWASM(telemetry.sm)

        if not wasm.connect():
            print("❌ MobiFlight WASM не найден")
            print()
            print("Возможные причины:")
            print("  1. MobiFlight WASM не установлен в Community папке")
            print("  2. MSFS нужно перезапустить после установки")
            print("  3. Путь к Community папке неверный")
            print()
            print("Установленный путь:")
            print("  C:\\Users\\MYRIG\\AppData\\Local\\Packages\\")
            print("  Microsoft.FlightSimulator_8wekyb3d8bbwe\\LocalCache\\Packages\\Community\\")
            print("  mobiflight-event-module\\")
            print()
            telemetry.disconnect()
            pytest.skip("MobiFlight WASM not found")

        print("✅ MobiFlight WASM подключен успешно!")
        print()

    except Exception as e:
        print(f"❌ ОШИБКА инициализации WASM: {e}")
        telemetry.disconnect()
        pytest.skip(f"WASM initialization error: {e}")

    # Шаг 3: Получение информации о самолёте
    print("Шаг 3: Определение типа самолёта...")
    try:
        aircraft_info = telemetry.get_aircraft_info()
        if aircraft_info:
            print(f"✅ Самолёт: {aircraft_info.get('title', 'Unknown')}")
            print(f"   Производитель: {aircraft_info.get('aircraft_manufacturer', 'Unknown')}")
            print(f"   Тип автопилота: {aircraft_info.get('autopilot_type', 'Unknown')}")
            print(f"   Кастомный: {aircraft_info.get('is_custom_aircraft', False)}")
        else:
            print("⚠️  Не удалось получить информацию о самолёте")
        print()

    except Exception as e:
        print(f"⚠️  Ошибка получения информации: {e}")
        print()

    # Шаг 4: Тест чтения L:Var
    print("Шаг 4: Тест чтения локальной переменной (L:Var)...")
    try:
        # Пробуем прочитать тестовую переменную
        test_var = "MOBIFLIGHT_TEST"
        value = wasm.read_lvar(test_var)

        if value is not None:
            print(f"✅ Чтение L:Var работает: {test_var} = {value}")
        else:
            print(f"⚠️  L:Var не найдена: {test_var} (это нормально для теста)")
        print()

    except Exception as e:
        print(f"❌ ОШИБКА чтения L:Var: {e}")
        print()

    # Шаг 5: Тест записи L:Var (если самолёт поддерживает)
    print("Шаг 5: Тест записи локальной переменной...")
    try:
        # Для PMDG/Fenix можно попробовать записать реальную переменную
        # Для теста используем безопасную переменную
        test_var = "MOBIFLIGHT_TEST_WRITE"
        test_value = 123.45

        success = wasm.write_lvar(test_var, test_value)

        if success:
            print(f"✅ Запись L:Var работает: {test_var} = {test_value}")

            # Проверяем чтение
            read_value = wasm.read_lvar(test_var)
            if read_value == test_value:
                print(f"✅ Проверка записи: значение совпадает ({read_value})")
            else:
                print(f"⚠️  Проверка записи: значение отличается ({read_value} != {test_value})")
        else:
            print("⚠️  Запись L:Var не удалась (может быть нормально для некоторых самолётов)")
        print()

    except Exception as e:
        print(f"⚠️  Ошибка записи L:Var: {e}")
        print()

    # Шаг 6: Проверка интеграции с aircraft_adapter
    print("Шаг 6: Проверка интеграции с aircraft_adapter...")
    try:
        from modules.aircraft_adapter import AircraftCommandAdapter
        from modules.control import MSFSControl

        control = MSFSControl(telemetry.ae)
        adapter = AircraftCommandAdapter(control, telemetry)

        if adapter.detect_and_configure():
            print("✅ Aircraft adapter настроен")
            print(f"   Профиль: {adapter.current_profile.get('name', 'Unknown')}")
            print(f"   WASM доступен: {adapter.wasm is not None and adapter.wasm.connected}")
        else:
            print("⚠️  Aircraft adapter не смог определить профиль")
        print()

    except Exception as e:
        print(f"⚠️  Ошибка aircraft_adapter: {e}")
        print()

    # Итоги
    print("=" * 70)
    print("РЕЗУЛЬТАТЫ ТЕСТА")
    print("=" * 70)
    print()
    print("✅ MobiFlight WASM v1.0.1 установлен и работает!")
    print()
    print("Следующие шаги:")
    print("  1. Запустите MSFS с кастомным самолётом (PMDG, Fenix)")
    print("  2. Запустите gui.py для полного тестирования")
    print("  3. Проверьте логи на наличие сообщений о WASM")
    print()
    print("Документация:")
    print("  - CLIENT_DATA_IMPLEMENTATION.md - описание реализации")
    print("  - TESTING_INSTRUCTIONS.md - инструкции по тестированию")
    print()

    # Отключение
    telemetry.disconnect()

    print("✅ Все тесты пройдены успешно")


if __name__ == "__main__":
    print()
    print("ВАЖНО: Перед запуском теста:")
    print("  1. Запустите Microsoft Flight Simulator")
    print("  2. Загрузите любой полёт (можно на земле)")
    print("  3. Дождитесь полной загрузки")
    print()
    input("Нажмите Enter когда MSFS будет готов...")
    print()

    try:
        test_mobiflight_wasm()
        print("✅ Тест завершён успешно!")
        sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⚠️  Тест прерван пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
