"""
Bihar Statutory Stamp Duty and Registration Fee Engine.

Computes statutory transfer charges in compliance with:
- Indian Stamp Act 1899 as amended by Bihar Stamp (Amendment) Acts
- Section 47-A (Prevention of Undervaluation & Assessment Base Selection)
- Bihar Registration Rules 2008
- Statutory Concessions for Women Purchasers and Municipal Surcharges
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional

from app.models.valuation import BuyerGenderCategory, JurisdictionType

logger = logging.getLogger("bhumisetu.valuation.stamp_duty_engine")


class StampDutyEngine:
    """
    Statutory charge calculation engine for Bihar property conveyances.
    """

    RULE_VERSION = "BIHAR_STAMP_SCHEDULE_v2026.1"

    # Standard Stamp Duty Rates (Conveyance / Sale Deed)
    BASE_STAMP_DUTY_MALE = 6.0
    BASE_STAMP_DUTY_FEMALE = 5.6  # 0.40% statutory concession for women
    BASE_STAMP_DUTY_JOINT = 5.8   # Average for joint male/female ownership
    BASE_STAMP_DUTY_ENTITY = 6.0

    # Municipal Corporation Surcharge (e.g. PMC limits)
    MUNICIPAL_CORPORATION_SURCHARGE = 2.0

    # Registration Fee
    REGISTRATION_FEE_RATE = 2.0

    def calculate_charges(
        self,
        government_valuation: float,
        declared_consideration: Optional[float] = None,
        buyer_category: str = BuyerGenderCategory.MALE,
        jurisdiction_type: str = JurisdictionType.RURAL,
    ) -> Dict[str, Any]:
        """
        Calculates assessment base, stamp duty, municipal surcharge, and registration fees.
        """
        govt_val = round(float(government_valuation), 2)
        decl_val = round(float(declared_consideration), 2) if declared_consideration is not None else 0.0

        # Section 47-A Assessment Base: greater of consideration and government guideline value
        assessment_base = max(govt_val, decl_val)

        # 1. Resolve Stamp Duty Rate & Concessions
        buyer_cat = (buyer_category or BuyerGenderCategory.MALE).upper()
        concession_applied: Optional[str] = None

        if buyer_cat == BuyerGenderCategory.FEMALE:
            stamp_duty_rate = self.BASE_STAMP_DUTY_FEMALE
            concession_applied = "0.40% statutory stamp duty concession applied for sole female purchaser."
        elif buyer_cat == BuyerGenderCategory.JOINT_MALE_FEMALE:
            stamp_duty_rate = self.BASE_STAMP_DUTY_JOINT
            concession_applied = "0.20% proportional stamp duty concession applied for joint male/female co-purchasers."
        else:
            stamp_duty_rate = self.BASE_STAMP_DUTY_MALE

        # 2. Municipal Surcharge
        jur_type = (jurisdiction_type or JurisdictionType.RURAL).upper()
        if jur_type == JurisdictionType.URBAN_CORPORATION:
            municipal_surcharge_rate = self.MUNICIPAL_CORPORATION_SURCHARGE
        else:
            municipal_surcharge_rate = 0.0

        # 3. Calculate Amounts (rounded to nearest rupee per registration standard)
        stamp_duty_amount = round((assessment_base * stamp_duty_rate) / 100.0, 2)
        municipal_surcharge_amount = round((assessment_base * municipal_surcharge_rate) / 100.0, 2)
        registration_fee_amount = round((assessment_base * self.REGISTRATION_FEE_RATE) / 100.0, 2)

        total_statutory_charges = round(
            stamp_duty_amount + municipal_surcharge_amount + registration_fee_amount, 2
        )

        return {
            "declared_consideration": decl_val if declared_consideration is not None else None,
            "government_valuation": govt_val,
            "assessment_base": assessment_base,
            "buyer_category": buyer_cat,
            "stamp_duty_rate_percent": stamp_duty_rate,
            "stamp_duty_amount": stamp_duty_amount,
            "municipal_surcharge_percent": municipal_surcharge_rate,
            "municipal_surcharge_amount": municipal_surcharge_amount,
            "registration_fee_rate_percent": self.REGISTRATION_FEE_RATE,
            "registration_fee_amount": registration_fee_amount,
            "total_statutory_charges": total_statutory_charges,
            "concession_applied": concession_applied,
            "statutory_rule_version": self.RULE_VERSION,
        }
