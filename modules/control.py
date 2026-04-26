"""
Модуль управления самолётом через SimConnect API
"""

import logging
from typing import Optional

from SimConnect import AircraftEvents

logger = logging.getLogger(__name__)


class MSFSControl:
    """Класс для управления самолётом через SimConnect"""

    def __init__(self, aircraft_events: AircraftEvents):
        self.ae = aircraft_events

    def set_autopilot_master(self, state: bool):
        """Включить/выключить автопилот"""
        try:
            if state:
                self.ae.event("AUTOPILOT_ON")
            else:
                self.ae.event("AUTOPILOT_OFF")
            logger.info("Autopilot master: %s", state)
        except Exception as e:
            logger.error("Error setting autopilot master: %s", e)

    def set_heading_hold(self, heading: Optional[int] = None):
        """Установить режим удержания курса"""
        try:
            self.ae.event("AP_HDG_HOLD_ON")
            if heading is not None:
                self.ae.event("HEADING_BUG_SET", int(heading))
            logger.info("Heading hold ON, heading: %s", heading)
        except Exception as e:
            logger.error("Error setting heading hold: %s", e)

    def set_altitude_hold(self, altitude: Optional[int] = None):
        """Установить режим удержания высоты"""
        try:
            self.ae.event("AP_ALT_HOLD_ON")
            if altitude is not None:
                self.ae.event("AP_ALT_VAR_SET_ENGLISH", int(altitude))
            logger.info("Altitude hold ON, altitude: %s", altitude)
        except Exception as e:
            logger.error("Error setting altitude hold: %s", e)

    def set_nav_hold(self, state: bool):
        """Включить/выключить режим NAV (следование по VOR)"""
        try:
            if state:
                self.ae.event("AP_NAV1_HOLD_ON")
            else:
                self.ae.event("AP_NAV1_HOLD_OFF")
            logger.info("NAV hold: %s", state)
        except Exception as e:
            logger.error("Error setting NAV hold: %s", e)

    def set_approach_mode(self, state: bool):
        """Включить/выключить режим захода на посадку"""
        try:
            if state:
                self.ae.event("AP_APR_HOLD_ON")
            else:
                self.ae.event("AP_APR_HOLD_OFF")
            logger.info("Approach mode: %s", state)
        except Exception as e:
            logger.error("Error setting approach mode: %s", e)

    def set_airspeed_hold(self, speed: Optional[int] = None):
        """Установить режим удержания скорости"""
        try:
            self.ae.event("AP_AIRSPEED_ON")
            if speed is not None:
                self.ae.event("AP_SPD_VAR_SET", int(speed))
            logger.info("Airspeed hold ON, speed: %s", speed)
        except Exception as e:
            logger.error("Error setting airspeed hold: %s", e)

    def set_vertical_speed(self, vs: int):
        """Установить вертикальную скорость (футы/мин)"""
        try:
            self.ae.event("AP_VS_HOLD")
            self.ae.event("AP_VS_VAR_SET_ENGLISH", int(vs))
            logger.info("Vertical speed set: %s fpm", vs)
        except Exception as e:
            logger.error("Error setting vertical speed: %s", e)

    def set_nav_frequency(self, nav_index: int, frequency: int):
        """Установить частоту NAV радио (в Hz)"""
        try:
            if nav_index == 1:
                self.ae.event("NAV1_RADIO_SET_HZ", frequency)
            elif nav_index == 2:
                self.ae.event("NAV2_RADIO_SET_HZ", frequency)
            logger.info("NAV%s frequency set: %s Hz", nav_index, frequency)
        except Exception as e:
            logger.error("Error setting NAV frequency: %s", e)

    def set_adf_frequency(self, frequency: int):
        """Установить частоту ADF (в Hz)"""
        try:
            self.ae.event("ADF_COMPLETE_SET", frequency)
            logger.info("ADF frequency set: %s Hz", frequency)
        except Exception as e:
            logger.error("Error setting ADF frequency: %s", e)

    def set_obs(self, nav_index: int, course: int):
        """Установить OBS (курс на VOR)"""
        try:
            if nav_index == 1:
                self.ae.event("VOR1_SET", int(course))
            elif nav_index == 2:
                self.ae.event("VOR2_SET", int(course))
            logger.info("NAV%s OBS set: %s°", nav_index, course)
        except Exception as e:
            logger.error("Error setting OBS: %s", e)

    def set_flaps(self, position: int):
        """Установить закрылки (0-3)"""
        try:
            self.ae.event("FLAPS_SET", position)
            logger.info("Flaps set: %s", position)
        except Exception as e:
            logger.error("Error setting flaps: %s", e)

    def set_gear(self, state: bool):
        """Выпустить/убрать шасси"""
        try:
            if state:
                self.ae.event("GEAR_DOWN")
            else:
                self.ae.event("GEAR_UP")
            logger.info("Gear: %s", 'DOWN' if state else 'UP')
        except Exception as e:
            logger.error("Error setting gear: %s", e)

    def set_throttle(self, percent: float):
        """
        Установить газ на всех двигателях (0.0 - 1.0)

        Args:
            percent: Процент тяги (0.0 - 1.0)
        """
        try:
            value = int(percent * 16384)
            self.ae.event("THROTTLE_SET", value)
            logger.info("Throttle set: %.1f%%", percent*100)
        except Exception as e:
            logger.error("Error setting throttle: %s", e)

    def set_throttle_engine(self, engine_index: int, percent: float):
        """
        Установить газ на конкретном двигателе (0.0 - 1.0)

        Args:
            engine_index: Номер двигателя (1-4)
            percent: Процент тяги (0.0 - 1.0)
        """
        try:
            value = int(percent * 16384)

            # SimConnect события для индивидуальных двигателей
            event_map = {
                1: "THROTTLE1_SET",
                2: "THROTTLE2_SET",
                3: "THROTTLE3_SET",
                4: "THROTTLE4_SET"
            }

            if engine_index not in event_map:
                logger.error(f"Invalid engine index: {engine_index} (must be 1-4)")
                return

            self.ae.event(event_map[engine_index], value)
            logger.info(f"Engine {engine_index} throttle set: {percent*100:.1f}%")

        except Exception as e:
            logger.error(f"Error setting engine {engine_index} throttle: {e}")

    def set_throttle_asymmetric(self, throttle_values: dict):
        """
        Установить асимметричную тягу (разные значения для каждого двигателя)

        Args:
            throttle_values: Словарь {engine_index: percent}
                            Например: {1: 0.8, 2: 0.0, 3: 0.8, 4: 0.0}
        """
        try:
            for engine_idx, percent in throttle_values.items():
                self.set_throttle_engine(engine_idx, percent)

            logger.info(f"Asymmetric throttle set: {throttle_values}")

        except Exception as e:
            logger.error(f"Error setting asymmetric throttle: {e}")

    def set_rudder(self, percent: float):
        """
        Установить руль направления (-1.0 до +1.0)

        Args:
            percent: Положение руля
                    -1.0 = полностью вправо
                     0.0 = нейтраль
                    +1.0 = полностью влево
        """
        try:
            # SimConnect использует диапазон -16384 до +16384
            value = int(percent * 16384)
            self.ae.event("RUDDER_SET", value)
            logger.debug(f"Rudder set: {percent:+.2f} ({value})")

        except Exception as e:
            logger.error(f"Error setting rudder: {e}")

    def set_aileron(self, percent: float):
        """
        Установить элероны (-1.0 до +1.0)

        Args:
            percent: Положение элеронов
                    -1.0 = полностью влево (левый крен)
                     0.0 = нейтраль
                    +1.0 = полностью вправо (правый крен)
        """
        try:
            # SimConnect использует диапазон -16384 до +16384
            value = int(percent * 16384)
            self.ae.event("AILERON_SET", value)
            logger.debug(f"Aileron set: {percent:+.2f} ({value})")

        except Exception as e:
            logger.error(f"Error setting aileron: {e}")
