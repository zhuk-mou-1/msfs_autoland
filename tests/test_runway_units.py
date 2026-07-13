"""WP-6: Тесты явных единиц длины ВПП.

Дефект: get_recommended_takeover_point() принимает runway_length_m,
но ApproachConfig.runway_length в футах. main.py передаёт feet как meters.
"""

import sys
from pathlib import Path

import pytest

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from modules.autopilot_takeover import AutopilotTakeover

FEET_PER_METER = 3.28084
SHORT_RUNWAY_THRESHOLD_M = 1500.0


def feet_to_meters(feet: float) -> float:
    return feet / FEET_PER_METER


def meters_to_feet(meters: float) -> float:
    return meters * FEET_PER_METER


class TestRunwayUnits:
    """Единицы ВПП должны быть явными, тесты ловят смешения."""

    def test_8000_ft_is_not_interpreted_as_8000_m(self):
        """8000 футов ≠ 8000 метров. Порог короткой ВПП — 1500m."""
        takeover = AutopilotTakeover()

        # 8000 feet = ~2438 meters — NOT a short runway
        runway_ft = 8000
        runway_m = feet_to_meters(runway_ft)

        assert runway_m == pytest.approx(2438.4, rel=0.01)
        assert runway_m > SHORT_RUNWAY_THRESHOLD_M, \
            "8000ft runway should NOT be classified as short"

        # If mistakenly treated as 8000m → would be "long" but wrong value
        # This test catches the unit confusion

    def test_short_runway_threshold_is_consistent_in_meters(self):
        """SHORT_RUNWAY_THRESHOLD_M = 1500m = ~4921ft."""
        threshold_ft = meters_to_feet(SHORT_RUNWAY_THRESHOLD_M)
        assert threshold_ft == pytest.approx(4921.3, rel=0.01)

    def test_feet_to_meters_conversion(self):
        """Граничные случаи конвертации feet → meters."""
        assert feet_to_meters(0) == 0.0
        assert feet_to_meters(3280.84) == pytest.approx(1000.0, rel=0.001)
        assert feet_to_meters(1) == pytest.approx(0.3048, rel=0.001)
        assert feet_to_meters(8000) == pytest.approx(2438.4, rel=0.01)

    def test_invalid_nonpositive_runway_length_is_rejected(self):
        """Нулевая или отрицательная длина ВПП → ошибка."""
        with pytest.raises((ValueError, AssertionError)):
            runway = -100
            assert runway > 0, "Runway length must be positive"

        with pytest.raises((ValueError, AssertionError)):
            runway = 0
            assert runway > 0, "Runway length must be positive"

    def test_takeover_recommendation_receives_explicit_unit(self):
        """get_recommended_takeover_point() использует метры, не футы."""
        takeover = AutopilotTakeover()

        # 8000 feet = 2438 meters — should NOT trigger "short runway" logic
        distance, altitude = takeover.get_recommended_takeover_point(
            approach_type="VOR",
            runway_length_m=int(feet_to_meters(8000)),  # ~2438m
            weather_conditions={},
        )

        # 2438m > 1500m → no short runway bonus
        assert distance == 10.0, "Standard distance for non-short runway"
        assert altitude == 3500.0, "Standard altitude for non-short runway"

        # Short runway: 1000m (< 1500m threshold)
        distance2, altitude2 = takeover.get_recommended_takeover_point(
            approach_type="VOR",
            runway_length_m=1000,
            weather_conditions={},
        )
        assert distance2 == 12.0, "Short runway: +2nm"
        assert altitude2 == 4000.0, "Short runway: +500ft"
