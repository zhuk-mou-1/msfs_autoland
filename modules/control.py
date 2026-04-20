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
        """Установить газ (0.0 - 1.0)"""
        try:
            value = int(percent * 16384)
            self.ae.event("THROTTLE_SET", value)
            logger.info("Throttle set: %s%", percent*100)
        except Exception as e:
            logger.error("Error setting throttle: %s", e)
