"""
Area Unit Normalization and Conversion Utility for Bihar Land Records.

Standardizes area units across Decimal, Katha, Acre, Bigha, SqFt, and SqMeters
using authentic Bihar revenue department conversion standards:
- 1 Decimal = 435.60 SqFt = 40.4686 SqMeters
- 1 Acre = 100 Decimals = 43,560 SqFt = 4,046.86 SqMeters
- 1 Katha (Standard Bihar) = 3.125 Decimals = 1,361.25 SqFt
- 1 Bigha (20 Kathas) = 62.50 Decimals = 27,225 SqFt
- 1 Hectare = 247.105 Decimals = 10,000 SqMeters
"""

from __future__ import annotations

from typing import Dict
from app.models.valuation import AreaUnit


# Canonical conversion factors: number of Decimals per 1 unit
DECIMAL_FACTORS: Dict[str, float] = {
    AreaUnit.DECIMAL: 1.0,
    AreaUnit.ACRE: 100.0,
    AreaUnit.KATHA: 3.125,
    AreaUnit.BIGHA: 62.50,
    AreaUnit.SQFT: 1.0 / 435.60,
    AreaUnit.SQMETER: 1.0 / 40.4686,
    "HECTARE": 247.105,
    "DISMIL": 1.0,
    "KATTHA": 3.125,
}

# Number of SqFt per 1 unit
SQFT_FACTORS: Dict[str, float] = {
    AreaUnit.DECIMAL: 435.60,
    AreaUnit.ACRE: 43560.0,
    AreaUnit.KATHA: 1361.25,
    AreaUnit.BIGHA: 27225.0,
    AreaUnit.SQFT: 1.0,
    AreaUnit.SQMETER: 10.7639,
    "HECTARE": 107639.0,
    "DISMIL": 435.60,
    "KATTHA": 1361.25,
}


def normalize_area_unit_name(unit: str) -> str:
    """Normalizes colloquial or regional unit names to standard AreaUnit enum."""
    u = (unit or "").strip().upper()
    if u in ("DECIMAL", "DISMIL", "DECIMALS", "डिसमिल", "डीसमिल"):
        return AreaUnit.DECIMAL
    if u in ("KATHA", "KATTHA", "कट्ठा", "कठ्ठा"):
        return AreaUnit.KATHA
    if u in ("ACRE", "ACRES", "एकड़"):
        return AreaUnit.ACRE
    if u in ("BIGHA", "BIGHAS", "बीघा"):
        return AreaUnit.BIGHA
    if u in ("SQFT", "SQ_FT", "SQUARE_FEET", "वर्ग फीट", "वर्गफीट"):
        return AreaUnit.SQFT
    if u in ("SQMETER", "SQ_METER", "SQM", "SQUARE_METER", "वर्ग मीटर"):
        return AreaUnit.SQMETER
    return u


def convert_to_decimal(value: float, from_unit: str) -> float:
    """
    Converts any supported area quantity into Decimals with precision.
    """
    if value < 0:
        raise ValueError(f"Area value cannot be negative: {value}")
    norm_unit = normalize_area_unit_name(from_unit)
    factor = DECIMAL_FACTORS.get(norm_unit)
    if factor is None:
        raise ValueError(f"Unsupported area unit '{from_unit}'. Supported: DECIMAL, KATHA, ACRE, BIGHA, SQFT, SQMETER")
    return round(value * factor, 6)


def convert_area(value: float, from_unit: str, to_unit: str) -> float:
    """
    Converts area from any supported unit to any target unit.
    """
    if value < 0:
        raise ValueError(f"Area value cannot be negative: {value}")
    norm_from = normalize_area_unit_name(from_unit)
    norm_to = normalize_area_unit_name(to_unit)
    
    # Convert from -> Decimal -> to
    in_decimal = convert_to_decimal(value, norm_from)
    target_factor = DECIMAL_FACTORS.get(norm_to)
    if target_factor is None:
        raise ValueError(f"Unsupported target unit '{to_unit}'")
    
    return round(in_decimal / target_factor, 6)
