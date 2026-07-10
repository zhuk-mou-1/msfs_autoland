"""
WP-5: Владение каналами управления.

Гарантирует, что в каждый момент один канал (roll, pitch, throttle)
имеет ровно одного владельца. Внешнее vJoy-управление не смешивается
с AP-командами того же канала.
"""

from dataclasses import dataclass
from enum import Enum


class ControlOwner(Enum):
    NONE = "none"
    AIRCRAFT_AP = "aircraft_ap"
    EXTERNAL = "external"


@dataclass(frozen=True)
class ControlOwnership:
    roll: ControlOwner
    pitch: ControlOwner
    throttle: ControlOwner


def compute_ownership(
    *,
    phase: str,
    confirmed_takeover: bool,
    use_vjoy: bool,
    vjoy_ready: bool,
    use_autothrottle: bool,
    external_at_active: bool = False,
) -> ControlOwnership:
    """Вычислить разрешённого владельца для каждого канала.

    Policy (Stage 0):
    ┌─────────────────────────────────┬───────────┬──────────┬───────────┐
    │ Condition                       │ Roll      │ Pitch    │ Throttle  │
    ├─────────────────────────────────┼───────────┼──────────┼───────────┤
    │ Before confirmed takeover       │ AP        │ AP       │ AP or ext │
    │ FINAL, no confirmed takeover    │ AP        │ AP       │ one owner│
    │ External flare + vJoy ready     │ EXTERNAL  │ EXTERNAL │ one owner│
    │ External mode, no vJoy          │ NONE      │ NONE     │ one owner│
    │ Go-around / abort               │ NONE      │ NONE     │ AP        │
    └─────────────────────────────────┴───────────┴──────────┴───────────┘
    """
    if phase == "GO_AROUND":
        return ControlOwnership(
            roll=ControlOwner.NONE,
            pitch=ControlOwner.NONE,
            throttle=ControlOwner.AIRCRAFT_AP,
        )

    if not confirmed_takeover:
        return ControlOwnership(
            roll=ControlOwner.AIRCRAFT_AP,
            pitch=ControlOwner.AIRCRAFT_AP,
            throttle=ControlOwner.AIRCRAFT_AP,
        )

    # Confirmed takeover
    # Throttle: autothrottle takes priority if active
    if use_autothrottle and not external_at_active:
        throttle_owner = ControlOwner.AIRCRAFT_AP
    elif use_vjoy and vjoy_ready:
        throttle_owner = ControlOwner.EXTERNAL
    else:
        throttle_owner = ControlOwner.AIRCRAFT_AP

    if use_vjoy and vjoy_ready:
        return ControlOwnership(
            roll=ControlOwner.EXTERNAL,
            pitch=ControlOwner.EXTERNAL,
            throttle=throttle_owner,
        )
    else:
        return ControlOwnership(
            roll=ControlOwner.AIRCRAFT_AP,
            pitch=ControlOwner.AIRCRAFT_AP,
            throttle=throttle_owner,
        )
