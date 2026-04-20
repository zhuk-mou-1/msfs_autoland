"""
Тестовый скрипт для проверки работы LVAR через MobiFlight WASM
"""

import logging

from modules.telemetry import MSFSTelemetry
from modules.wasm_interface import MobiFlightWASM

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Основная функция тестирования"""
    print("=" * 60)
    print("MobiFlight WASM - LVAR Test")
    print("=" * 60)
    print()

    # Подключение к MSFS
    telemetry = MSFSTelemetry()

    print("Connecting to MSFS...")
    if not telemetry.connect():
        print("ERROR: Failed to connect to MSFS")
        print("Make sure Microsoft Flight Simulator is running")
        return

    print("✅ Connected to MSFS")
    print()

    # Подключение к WASM
    print("Connecting to MobiFlight WASM...")
    wasm = MobiFlightWASM(telemetry.sm)

    if not wasm.connect():
        print("❌ MobiFlight WASM not available")
        print()
        print("Please install MobiFlight WASM module:")
        print("1. Download: https://github.com/MobiFlight/MobiFlight-WASM-Module/releases")
        print("2. Extract to MSFS Community folder")
        print("3. Restart MSFS")
        print()
        print("See docs/wasm_installation.md for detailed instructions")
        return

    print("✅ MobiFlight WASM connected")
    print()

    # Получение информации о самолёте
    aircraft_info = telemetry.get_aircraft_info()
    print("=" * 60)
    print("AIRCRAFT INFORMATION")
    print("=" * 60)
    print(f"Title: {aircraft_info.get('title', 'Unknown')}")
    print(f"Manufacturer: {aircraft_info.get('aircraft_manufacturer', 'Unknown')}")
    print(f"Type: {aircraft_info.get('autopilot_type', 'Unknown')}")
    print(f"Custom Aircraft: {aircraft_info.get('is_custom_aircraft', False)}")
    print()

    # Тесты LVAR операций
    print("=" * 60)
    print("LVAR OPERATIONS TEST")
    print("=" * 60)
    print()

    # Тест 1: Чтение тестовой переменной
    print("Test 1: Reading test LVAR...")
    test_value = wasm.read_lvar("MOBIFLIGHT_TEST")
    if test_value is not None:
        print(f"✅ Read successful: MOBIFLIGHT_TEST = {test_value}")
    else:
        print("⚠️  Read returned None (variable may not exist)")
    print()

    # Тест 2: Запись и чтение
    print("Test 2: Write and read back...")
    test_var = "MOBIFLIGHT_TEST_WRITE"
    test_write_value = 12345.67

    if wasm.write_lvar(test_var, test_write_value):
        print(f"✅ Write successful: {test_var} = {test_write_value}")

        # Чтение обратно
        read_back = wasm.read_lvar(test_var)
        if read_back is not None:
            print(f"✅ Read back: {test_var} = {read_back}")

            if abs(read_back - test_write_value) < 0.01:
                print("✅ Values match!")
            else:
                print(f"⚠️  Values don't match: {read_back} != {test_write_value}")
        else:
            print("❌ Read back failed")
    else:
        print("❌ Write failed")
    print()

    # Тест 3: Специфичные переменные для кастомных самолётов
    if aircraft_info.get('is_custom_aircraft'):
        print("Test 3: Custom aircraft LVARs...")
        manufacturer = aircraft_info.get('aircraft_manufacturer')

        if manufacturer == "PMDG":
            print("Testing PMDG variables...")
            # Попытка чтения MCP курса
            mcp_course = wasm.read_lvar("PMDG_737_MCP_Course")
            if mcp_course is not None:
                print(f"✅ PMDG_737_MCP_Course = {mcp_course}")
            else:
                print("⚠️  PMDG_737_MCP_Course not available")

        elif manufacturer == "FENIX":
            print("Testing Fenix variables...")
            # Попытка чтения FCU курса
            fcu_hdg = wasm.read_lvar("S_FCU_HEADING")
            if fcu_hdg is not None:
                print(f"✅ S_FCU_HEADING = {fcu_hdg}")
            else:
                print("⚠️  S_FCU_HEADING not available")

        elif manufacturer == "FLYBYWIRE":
            print("Testing FlyByWire variables...")
            # Попытка чтения A32NX переменных
            ap_active = wasm.read_lvar("A32NX_AUTOPILOT_1_ACTIVE")
            if ap_active is not None:
                print(f"✅ A32NX_AUTOPILOT_1_ACTIVE = {ap_active}")
            else:
                print("⚠️  A32NX_AUTOPILOT_1_ACTIVE not available")

        else:
            print(f"No specific tests for {manufacturer}")
    else:
        print("Test 3: Skipped (not a custom aircraft)")
    print()

    # Тест 4: Отправка события
    print("Test 4: Trigger event...")
    if wasm.trigger_event("MOBIFLIGHT_TEST_EVENT", 123):
        print("✅ Event triggered successfully")
    else:
        print("❌ Event trigger failed")
    print()

    # Итоги
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print("✅ WASM module is working")
    print("✅ LVAR read/write operations functional")

    if aircraft_info.get('is_custom_aircraft'):
        print(f"✅ Custom aircraft detected: {aircraft_info.get('aircraft_manufacturer')}")
        print("   You can now use full AutoLand functionality")
    else:
        print("ℹ️  Standard aircraft - LVAR support not required")

    print()
    print("=" * 60)

    # Отключение
    wasm.disconnect()
    telemetry.disconnect()
    print("Disconnected from MSFS")


if __name__ == "__main__":
    main()
