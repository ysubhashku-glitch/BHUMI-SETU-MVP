"""
Bihar Government Land Valuation Engine.

Deterministically computes land and structural guideline values using verified
Minimum Valuation Register (MVR) / Circle Rate schedules and standardized area units.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone

from app.models.valuation import (
    AreaUnit,
    PropertyCategory,
    RoadCategory,
    ScheduleVerificationStatus,
)
from app.schemas.valuation import (
    MVRScheduleRecord,
    ValuationCalculationRequest,
)
from app.services.valuation.unit_converter import convert_to_decimal
from app.services.valuation.providers.base import MVRRateNotFoundError

logger = logging.getLogger("bhumisetu.valuation.engine")


class ValuationEngine:
    """
    Deterministic calculation engine for Bihar government land valuation.
    """

    RULE_VERSION = "BIHAR_MVR_VALUATION_v2026.1"

    def calculate_valuation(
        self,
        request: ValuationCalculationRequest,
        schedule: MVRScheduleRecord,
    ) -> Dict[str, Any]:
        """
        Calculates land valuation, building structure valuation, and total government valuation.
        """
        # 1. Normalize area into Decimals
        area_decimals = convert_to_decimal(request.area_value, request.area_unit)

        # 2. Select matching circle rate
        unit_rate = schedule.rate_per_decimal
        rate_basis = "INR_PER_DECIMAL"

        # 3. Compute land value
        calculated_land_value = round(area_decimals * unit_rate, 2)

        # 4. Compute structural value if building plinth area is provided
        built_up_sqft = float(request.built_up_area_sqft or 0.0)
        construction_rate = float(request.construction_rate_sqft or 0.0)
        calculated_structure_value = 0.0
        if built_up_sqft > 0 and construction_rate > 0:
            calculated_structure_value = round(built_up_sqft * construction_rate, 2)

        # 5. Total Government Valuation
        total_govt_valuation = round(calculated_land_value + calculated_structure_value, 2)

        return {
            "schedule_code": schedule.schedule_code,
            "district": schedule.district,
            "anchal_circle": schedule.anchal_circle,
            "mauza": schedule.mauza,
            "property_category": schedule.property_category,
            "road_category": schedule.road_category,
            "jurisdiction_type": schedule.jurisdiction_type,
            "total_area_decimal": area_decimals,
            "input_area_value": request.area_value,
            "input_area_unit": request.area_unit.upper(),
            "applied_unit_rate": unit_rate,
            "rate_basis": rate_basis,
            "calculated_land_value": calculated_land_value,
            "built_up_area_sqft": built_up_sqft,
            "construction_rate_sqft": construction_rate,
            "calculated_structure_value": calculated_structure_value,
            "total_government_valuation": total_govt_valuation,
            "verification_status": schedule.verification_status,
            "rule_version": self.RULE_VERSION,
        }
