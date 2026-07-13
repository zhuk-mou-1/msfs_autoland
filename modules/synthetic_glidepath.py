"""
Synthetic glidepath controller for non-precision approaches (VOR/NDB).

Computes target vertical speed to track a computed glideslope based on
aircraft position relative to runway threshold.  Integrates with the
existing Navigation helpers and wind-correction pipeline.

Pipeline (per frame):
    glideslope tracking  →  wind correction (input)  →  MDA floor clamp  →  final VS

MDA source (COMPATIBILITY — temporary):
    ``decision_height`` in ApproachConfig historically carries AGL values
    (consistent with the DH guard in FinalPhaseState which compares it
    against radio_height).  For non-precision VOR/NDB approaches this
    value is reinterpreted as minimum altitude above runway (AGL), and
    the effective MDA in MSL is derived as:

        effective_mda_msl = decision_height + runway_elevation

    This is NOT a substitute for a published MDA field.  When a dedicated
    ``minimum_descent_altitude_msl`` field is added to ApproachConfig it
    should be preferred over this conversion.

The floor is hard: the module never commands descent below effective_mda_msl.
All altitude comparisons in this module use MSL unless noted otherwise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.navigation import Navigation
    from modules.types import ApproachConfig


class SyntheticGlidepath:
    """Continuous glideslope tracker for non-precision approaches.

    MDA is derived from ``decision_height`` (AGL, compatibility) plus
    ``runway_elevation`` → MSL.  When a real MDA field is added to
    ApproachConfig, use it instead of this conversion.

    Args:
        navigation: Navigation instance (distance / altitude helpers).
        config: ApproachConfig with glideslope_angle, decision_height,
                runway_threshold_lat/lon, runway_elevation.
        mda_hysteresis_ft: Band above MDA where level-off begins (ft).
        gain: Proportional gain converting altitude error to VS correction
              (fpm per ft of error).  Default 2.0 → 100 ft error ≈ 200 fpm
              correction.
    """

    def __init__(
        self,
        navigation: "Navigation",
        config: "ApproachConfig",
        mda_hysteresis_ft: float = 15.0,
        gain: float = 2.0,
    ) -> None:
        self._nav = navigation
        self._config = config
        # MDA in MSL: decision_height is AGL (consistent with DH guard),
        # so convert to MSL by adding runway elevation.
        self._mda_msl: float = float(config.decision_height) + float(config.runway_elevation)
        self._mda_hysteresis: float = mda_hysteresis_ft
        self._gain: float = gain

        # Pre-compute glideslope intercept point (used by should_start_descent)
        self._intercept_point = self._nav.calculate_glideslope_intercept_point(
            config.runway_threshold_lat,
            config.runway_threshold_lon,
            config.final_approach_course,
            config.runway_elevation,
            config.glideslope_angle,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_target_vs(
        self,
        telemetry: dict,
        wind_correction_vs: float,
    ) -> float:
        """Return target vertical speed for the current telemetry frame.

        Pipeline:
            1. Compute ideal altitude from distance-to-threshold (MSL).
            2. Derive altitude error in MSL → proportional VS correction.
            3. Combine with wind-corrected base VS.
            4. Clamp to MDA floor in MSL (last stage, after wind correction).

        Args:
            telemetry: Standard telemetry dict (position, speed, …).
            wind_correction_vs: VS already adjusted for wind
                (``wind_data['corrected_vs']``).

        Returns:
            Target VS in fpm (**positive = descend**).
            Guaranteed ≤ 0 when altitude_msl ≤ MDA_MSL + hysteresis.
        """
        # FIX-P1-5: defensive telemetry access - the rest of the codebase
        # treats missing telemetry keys as a fail-safe "hold / do not
        # command further descent" signal rather than raising KeyError.
        position = telemetry.get("position", {})
        altitude_msl = position.get("altitude")
        altitude_agl = position.get("altitude_agl")
        latitude = position.get("latitude")
        longitude = position.get("longitude")

        if altitude_msl is None or altitude_agl is None or latitude is None or longitude is None:
            return 0.0

        # ── MDA hard floor (MSL comparison) ─────────────────────────
        # _mda_msl = decision_height (AGL) + runway_elevation
        if altitude_msl <= self._mda_msl:
            return 0.0

        # ── Descent status via existing helper ──────────────────────
        descent_info = self._nav.should_start_descent(
            current_lat=latitude,
            current_lon=longitude,
            current_altitude_agl=altitude_agl,
            intercept_point=self._intercept_point,
        )

        # Too low on the profile → do not descend further
        if descent_info["status"] == "LOW":
            return 0.0

        # Not yet past intercept point and not high → hold altitude
        if not descent_info["should_descend"] and descent_info["status"] != "HIGH":
            return 0.0

        # ── Position-based ideal altitude (MSL) ────────────────────
        distance_nm = self._nav.calculate_distance_to_threshold(
            latitude,
            longitude,
            self._config,
        )

        ideal_alt_msl = self._nav.calculate_required_altitude(
            distance_nm,
            self._config.glideslope_angle,
            self._config.runway_elevation,
        )

        # Positive error = aircraft is above glideslope (both MSL)
        altitude_error = altitude_msl - ideal_alt_msl

        # ── Proportional VS correction ──────────────────────────────
        vs_correction = altitude_error * self._gain

        # Combine wind-corrected base VS with position error correction
        raw_vs = wind_correction_vs + vs_correction

        # ── MDA floor clamp (MSL, last stage after wind correction) ─
        # Within hysteresis band: hold altitude exactly.
        # Must be exactly 0.0 — not min(raw_vs, 0) which would allow
        # negative VS (climb command) when the aircraft is below the
        # glideslope but within the MDA band.
        if altitude_msl <= self._mda_msl + self._mda_hysteresis:
            raw_vs = 0.0

        return raw_vs
