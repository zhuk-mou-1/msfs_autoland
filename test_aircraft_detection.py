"""
Тестовый скрипт для определения типа самолёта и автопилота
"""

import logging

from modules.telemetry import MSFSTelemetry

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Основная функция"""
    print("=" * 60)
    print("MSFS Aircraft & Autopilot Detection")
    print("=" * 60)
    print()

    # Подключение к MSFS
    telemetry = MSFSTelemetry()

    print("Connecting to MSFS...")
    if not telemetry.connect():
        print("ERROR: Failed to connect to MSFS")
        print("Make sure Microsoft Flight Simulator is running")
        return

    print("Connected successfully!")
    print()

    try:
        # Получение информации о самолёте
        aircraft_info = telemetry.get_aircraft_info()

        if not aircraft_info:
            print("ERROR: Could not retrieve aircraft information")
            return

        # Вывод информации
        print("=" * 60)
        print("AIRCRAFT INFORMATION")
        print("=" * 60)
        print(f"Title:              {aircraft_info.get('title', 'Unknown')}")
        print(f"ATC Type:           {aircraft_info.get('atc_type', 'Unknown')}")
        print(f"ATC Model:          {aircraft_info.get('atc_model', 'Unknown')}")
        print(f"Category:           {aircraft_info.get('category', 'Unknown')}")
        print()

        print("=" * 60)
        print("ENGINE INFORMATION")
        print("=" * 60)
        print(f"Engine Type:        {aircraft_info.get('engine_type_name', 'Unknown')} ({aircraft_info.get('engine_type', 'N/A')})")
        print(f"Number of Engines:  {aircraft_info.get('number_of_engines', 'Unknown')}")
        print()

        print("=" * 60)
        print("AUTOPILOT INFORMATION")
        print("=" * 60)
        print(f"Autopilot Available: {aircraft_info.get('autopilot_available', False)}")
        print(f"Autopilot Type:      {aircraft_info.get('autopilot_type', 'NONE')}")
        print(f"Max Bank Angle:      {aircraft_info.get('autopilot_max_bank', 'N/A')}°")
        print()

        # Интерпретация типа автопилота
        autopilot_type = aircraft_info.get('autopilot_type', 'NONE')
        print("=" * 60)
        print("AUTOPILOT TYPE INTERPRETATION")
        print("=" * 60)

        if autopilot_type == "NONE":
            print("❌ No autopilot available")
            print("   This aircraft does not have autopilot systems")
        elif autopilot_type == "LIMITED":
            print("⚠️  Limited autopilot")
            print("   Basic autopilot with limited functionality")
        elif autopilot_type == "BASIC":
            print("✅ Basic autopilot")
            print("   Standard autopilot with heading and altitude hold")
        elif autopilot_type == "STANDARD":
            print("✅ Standard autopilot")
            print("   Full-featured standard MSFS autopilot")
            print("   Supports: Heading, Altitude, NAV, Approach modes")
        elif autopilot_type == "ADVANCED":
            print("🚀 Advanced autopilot")
            print("   Possibly custom or study-level autopilot")
            print("   Higher bank angle limits suggest advanced features")

        print()

        # Дополнительная информация
        print("=" * 60)
        print("ADDITIONAL FEATURES")
        print("=" * 60)
        print(f"Retractable Gear:   {aircraft_info.get('is_gear_retractable', False)}")
        print(f"Tail Dragger:       {aircraft_info.get('is_tail_dragger', False)}")
        print()

        # Получение текущего состояния автопилота
        autopilot_state = telemetry.get_autopilot_state()

        print("=" * 60)
        print("CURRENT AUTOPILOT STATE")
        print("=" * 60)
        print(f"Master:             {'ON' if autopilot_state.get('master') else 'OFF'}")
        print(f"Heading Hold:       {'ON' if autopilot_state.get('heading_hold') else 'OFF'}")
        print(f"Altitude Hold:      {'ON' if autopilot_state.get('altitude_hold') else 'OFF'}")
        print(f"NAV Hold:           {'ON' if autopilot_state.get('nav_hold') else 'OFF'}")
        print(f"Approach Hold:      {'ON' if autopilot_state.get('approach_hold') else 'OFF'}")
        print(f"Airspeed Hold:      {'ON' if autopilot_state.get('airspeed_hold') else 'OFF'}")
        print()

        # Рекомендации для нашей системы
        print("=" * 60)
        print("RECOMMENDATIONS FOR AUTOLAND SYSTEM")
        print("=" * 60)

        if autopilot_type in ["STANDARD", "ADVANCED"]:
            print("✅ This aircraft is COMPATIBLE with AutoLand system")
            print("   Full autopilot functionality available")
        elif autopilot_type == "BASIC":
            print("⚠️  This aircraft has LIMITED compatibility")
            print("   Some features may not work (NAV/Approach modes)")
        else:
            print("❌ This aircraft may NOT be compatible")
            print("   Consider using vJoy for direct control")

        print()
        print("=" * 60)

    except Exception as e:
        logger.error("Error: %s", e)
        print(f"ERROR: {e}")

    finally:
        telemetry.disconnect()
        print("Disconnected from MSFS")


if __name__ == "__main__":
    main()
