"""
Configuration loader for MSFS AutoLand System

Loads centralized thresholds from config/thresholds.json
Provides type-safe access to all system limits and constants
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class StabilizedApproachConfig:
    """Stabilized approach criteria"""
    speed_tolerance_high: float
    speed_tolerance_low: float
    max_vertical_speed: int
    max_glideslope_deviation: float
    max_localizer_deviation: float
    max_bank_angle: float
    min_throttle_percent: float


@dataclass
class WindShearConfig:
    """Wind shear detection thresholds"""
    headwind_loss_threshold: float
    crosswind_change_threshold: float
    vertical_speed_change_threshold: float
    airspeed_loss_threshold: float
    monitoring_window_seconds: float


@dataclass
class TurbulenceConfig:
    """Turbulence severity thresholds"""
    light_threshold: float
    moderate_threshold: float
    severe_threshold: float
    wind_variance_calm: float


@dataclass
class FlareConfig:
    """Flare controller parameters"""
    start_height: float
    end_height: float
    initial_pitch: float
    target_pitch: float
    max_pitch_rate: float
    throttle_reduction_start: float
    height_adjustment_headwind: float
    height_adjustment_tailwind: float


@dataclass
class AutopilotTakeoverConfig:
    """Autopilot takeover conditions"""
    distance_nm: float
    altitude_min_agl: float
    altitude_max_agl: float
    ils_cat1_dh: float
    ils_cat2_dh: float
    initialization_timeout: float
    stabilization_timeout: float
    speed_tolerance: float
    altitude_tolerance: float
    default_distance_nm: float
    default_altitude_agl: float
    cat1_default_altitude: float
    vor_distance_nm: float
    vor_altitude_agl: float


@dataclass
class PIDConfig:
    """PID controller coefficients"""
    kp: float
    ki: float
    kd: float


@dataclass
class ThrottleConfig:
    """Throttle limits"""
    max: float
    min: float
    max_rate: float
    initial: float
    base: float


@dataclass
class DragFactorsConfig:
    """Drag factors"""
    flaps: float
    gear: float


@dataclass
class WeightConfig:
    """Weight parameters"""
    reference: float
    factor: float


@dataclass
class AutothrottleConfig:
    """Autothrottle configuration"""
    pid: PIDConfig
    throttle: ThrottleConfig
    speed_tolerance: float
    drag_factors: DragFactorsConfig
    weight: WeightConfig


@dataclass
class ApproachPhasesConfig:
    """Approach phase transition thresholds"""
    ils_intercept_distance_nm: float
    cat2_decision_height: float
    final_approach_pitch: float
    flare_throttle_factor: float
    flare_height_reference: float


@dataclass
class NavigationConfig:
    """Navigation tolerances"""
    course_tolerance: float
    altitude_tolerance: float
    distance_tolerance_nm: float


@dataclass
class TimeoutsConfig:
    """System timeouts"""
    initialization: float
    stabilization: float
    connection_retry: float
    telemetry_update: float


@dataclass
class SafetyLimitsConfig:
    """Hard safety limits"""
    max_bank_angle: float
    max_pitch_up: float
    max_pitch_down: float
    min_decision_height: float
    max_crosswind_landing: float
    max_tailwind_landing: float
    min_runway_length_m: int


class ThresholdsConfig:
    """Centralized thresholds configuration"""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "thresholds.json"

        self.config_path = config_path
        self._data: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load configuration from JSON file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Thresholds config not found: {self.config_path}")

        with open(self.config_path, encoding='utf-8') as f:
            self._data = json.load(f)

    @property
    def stabilized_approach(self) -> StabilizedApproachConfig:
        """Get stabilized approach config"""
        data = self._data['stabilized_approach']
        return StabilizedApproachConfig(**data)

    @property
    def wind_shear(self) -> WindShearConfig:
        """Get wind shear config"""
        data = self._data['wind_shear']
        return WindShearConfig(**data)

    @property
    def turbulence(self) -> TurbulenceConfig:
        """Get turbulence config"""
        data = self._data['turbulence']
        return TurbulenceConfig(**data)

    @property
    def flare(self) -> FlareConfig:
        """Get flare config"""
        data = self._data['flare']
        return FlareConfig(**data)

    @property
    def autopilot_takeover(self) -> AutopilotTakeoverConfig:
        """Get autopilot takeover config"""
        data = self._data['autopilot_takeover']
        return AutopilotTakeoverConfig(**data)

    @property
    def autothrottle(self) -> AutothrottleConfig:
        """Get autothrottle config"""
        data = self._data['autothrottle']
        return AutothrottleConfig(
            pid=PIDConfig(**data['pid']),
            throttle=ThrottleConfig(**data['throttle']),
            speed_tolerance=data['speed_tolerance'],
            drag_factors=DragFactorsConfig(**data['drag_factors']),
            weight=WeightConfig(**data['weight'])
        )

    @property
    def approach_phases(self) -> ApproachPhasesConfig:
        """Get approach phases config"""
        data = self._data['approach_phases']
        return ApproachPhasesConfig(**data)

    @property
    def navigation(self) -> NavigationConfig:
        """Get navigation config"""
        data = self._data['navigation']
        return NavigationConfig(**data)

    @property
    def timeouts(self) -> TimeoutsConfig:
        """Get timeouts config"""
        data = self._data['timeouts']
        return TimeoutsConfig(**data)

    @property
    def safety_limits(self) -> SafetyLimitsConfig:
        """Get safety limits config"""
        data = self._data['safety_limits']
        return SafetyLimitsConfig(**data)

    def validate(self) -> bool:
        """Validate configuration values"""
        validation = self._data.get('validation', {})

        # Validate speed ranges
        for key in ['stabilized_approach', 'autopilot_takeover', 'autothrottle']:
            if key in self._data:
                config = self._data[key]
                if 'speed_tolerance' in config:
                    if not (validation['speed_min'] <= config['speed_tolerance'] <= validation['speed_max']):
                        return False

        # Validate throttle ranges
        throttle = self._data['autothrottle']['throttle']
        if not (validation['throttle_min'] <= throttle['min'] <= throttle['max'] <= validation['throttle_max']):
            return False

        return True


# Global singleton instance
_thresholds_config: Optional[ThresholdsConfig] = None


def get_thresholds() -> ThresholdsConfig:
    """Get global thresholds configuration instance"""
    global _thresholds_config
    if _thresholds_config is None:
        _thresholds_config = ThresholdsConfig()
    return _thresholds_config


def reload_thresholds() -> None:
    """Reload thresholds from disk"""
    global _thresholds_config
    if _thresholds_config is not None:
        _thresholds_config.load()
