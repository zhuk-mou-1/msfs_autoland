"""Shared unit conversion helpers for safety-critical flight calculations."""

FEET_PER_METER = 3.28084
POUNDS_PER_KILOGRAM = 2.20462
METERS_PER_NAUTICAL_MILE = 1852.0


def feet_to_meters(feet: float) -> float:
    return feet / FEET_PER_METER


def meters_to_feet(meters: float) -> float:
    return meters * FEET_PER_METER


def kg_to_lbs(kg: float) -> float:
    return kg * POUNDS_PER_KILOGRAM


def lbs_to_kg(lbs: float) -> float:
    return lbs / POUNDS_PER_KILOGRAM


def meters_to_nm(meters: float) -> float:
    return meters / METERS_PER_NAUTICAL_MILE


def nm_to_meters(nm: float) -> float:
    return nm * METERS_PER_NAUTICAL_MILE
