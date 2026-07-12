"""Fail-closed ownership gateway for SimConnect actuator commands."""
from __future__ import annotations
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from enum import Enum
from modules.control_ownership import ControlOwner

logger = logging.getLogger(__name__)

class CommandSource(Enum):
    AIRCRAFT_AP = "aircraft_ap"
    EXTERNAL = "external"
    SAFETY = "safety"

_SOURCE = ContextVar("autoland_command_source", default=CommandSource.AIRCRAFT_AP)

class CommandRejected(RuntimeError):
    pass

class CommandGateway:
    _CHANNELS = {
        "set_aileron": "roll", "set_rudder": "roll", "set_heading_hold": "roll",
        "set_vertical_speed": "pitch", "set_altitude_hold": "pitch",
        "set_throttle": "throttle", "set_throttle_engine": "throttle",
        "set_throttle_asymmetric": "throttle", "set_flaps": "configuration",
        "set_gear": "configuration", "set_nav_frequency": "navigation",
        "set_adf_frequency": "navigation", "set_obs": "navigation",
        "set_autopilot_master": "autopilot", "set_nav_hold": "autopilot",
        "set_approach_mode": "autopilot", "set_airspeed_hold": "autopilot",
    }

    def __init__(self, control, ownership_provider):
        self._control = control
        self._ownership_provider = ownership_provider

    @contextmanager
    def source_scope(self, source: CommandSource):
        token = _SOURCE.set(source)
        try:
            yield self
        finally:
            _SOURCE.reset(token)

    def _expected_owner(self, channel: str):
        ownership = self._ownership_provider()
        if channel == "roll": return ownership.roll
        if channel == "pitch": return ownership.pitch
        if channel == "throttle": return ownership.throttle
        return ControlOwner.AIRCRAFT_AP

    def _authorize(self, name: str):
        source = _SOURCE.get()
        if source == CommandSource.SAFETY:
            return
        actual = ControlOwner.AIRCRAFT_AP if source == CommandSource.AIRCRAFT_AP else ControlOwner.EXTERNAL
        expected = self._expected_owner(self._CHANNELS[name])
        if actual != expected:
            message = f"Rejected {name}: source={source.value}, owner={expected.value}"
            logger.critical(message)
            raise CommandRejected(message)

    def __getattr__(self, name):
        target = getattr(self._control, name)
        if name not in self._CHANNELS or not callable(target):
            return target
        def guarded(*args, **kwargs):
            self._authorize(name)
            return target(*args, **kwargs)
        return guarded

    @property
    def raw_control(self):
        return self._control
