"""
Valuation Discrepancy Analyzer.

Compares declared transaction consideration against government guideline valuation
to identify potential undervaluation risks, revenue deficit liabilities under Section 47-A,
and overvaluation premiums.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional

from app.models.valuation import DiscrepancyStatus
from app.schemas.valuation import STATUTORY_VALUATION_DISCLAIMER

logger = logging.getLogger("bhumisetu.valuation.discrepancy_analyzer")


class ValuationDiscrepancyAnalyzer:
    """
    Evaluates financial discrepancy between declared consideration and guideline valuation.
    """

    def analyze_discrepancy(
        self,
        government_valuation: float,
        declared_consideration: Optional[float],
        assessment_base: float,
    ) -> Dict[str, Any]:
        """
        Produces an auditable discrepancy evaluation with explicit rationale.
        """
        govt_val = round(float(government_valuation), 2)

        # Handle missing or zero consideration
        if declared_consideration is None or declared_consideration <= 0:
            return {
                "discrepancy_status": DiscrepancyStatus.INSUFFICIENT_DATA,
                "declared_consideration": 0.0,
                "government_valuation": govt_val,
                "assessment_base": assessment_base,
                "variance_amount": 0.0,
                "variance_percentage": 0.0,
                "is_undervalued": False,
                "is_overvalued": False,
                "explanation": (
                    "Declared transaction consideration was not provided. Government valuation serves as "
                    "the statutory minimum guideline base."
                ),
                "recommended_action": "Enter declared deed sale price to evaluate Section 47-A undervaluation risk.",
                "disclaimer": STATUTORY_VALUATION_DISCLAIMER,
            }

        decl_val = round(float(declared_consideration), 2)
        variance = round(decl_val - govt_val, 2)
        pct = round((abs(variance) / govt_val) * 100.0, 2) if govt_val > 0 else 0.0

        # Scenario 1: Potential Undervaluation (Consideration < Government Valuation)
        if decl_val < govt_val:
            deficit = round(govt_val - decl_val, 2)
            return {
                "discrepancy_status": DiscrepancyStatus.POTENTIAL_UNDERVALUE,
                "declared_consideration": decl_val,
                "government_valuation": govt_val,
                "assessment_base": assessment_base,
                "variance_amount": deficit,
                "variance_percentage": pct,
                "is_undervalued": True,
                "is_overvalued": False,
                "explanation": (
                    f"Declared consideration (₹{decl_val:,.2f}) is lower than the official government "
                    f"guideline valuation (₹{govt_val:,.2f}) by ₹{deficit:,.2f} ({pct:.2f}% deficit). "
                    f"Under Section 47-A of the Indian Stamp Act (Bihar Amendment), statutory stamp duty "
                    f"and registration fees must be assessed on the government valuation (₹{assessment_base:,.2f}). "
                    f"This does not establish fraudulent intent, but requires statutory minimum compliance."
                ),
                "recommended_action": (
                    "Prepare deed consideration or adjust duty deposit to meet government guideline value "
                    "to prevent impounding or reference under Section 47-A."
                ),
                "disclaimer": STATUTORY_VALUATION_DISCLAIMER,
            }

        # Scenario 2: Potential Overvaluation / Commercial Premium (Consideration > 1.5 * Govt Valuation)
        if decl_val > (1.5 * govt_val):
            premium = round(decl_val - govt_val, 2)
            return {
                "discrepancy_status": DiscrepancyStatus.POTENTIAL_OVERVALUATION,
                "declared_consideration": decl_val,
                "government_valuation": govt_val,
                "assessment_base": assessment_base,
                "variance_amount": premium,
                "variance_percentage": pct,
                "is_undervalued": False,
                "is_overvalued": True,
                "explanation": (
                    f"Declared consideration (₹{decl_val:,.2f}) exceeds the official government circle rate "
                    f"(₹{govt_val:,.2f}) by ₹{premium:,.2f} ({pct:.2f}% premium). Stamp duty will be assessed "
                    f"on the higher declared consideration (₹{assessment_base:,.2f}) as required by law."
                ),
                "recommended_action": "Verify that declared consideration reflects legitimate market appreciation.",
                "disclaimer": STATUTORY_VALUATION_DISCLAIMER,
            }

        # Scenario 3: No Discrepancy (Consideration >= Govt Valuation and within normal commercial range)
        return {
            "discrepancy_status": DiscrepancyStatus.NO_DISCREPANCY_DETECTED,
            "declared_consideration": decl_val,
            "government_valuation": govt_val,
            "assessment_base": assessment_base,
            "variance_amount": variance,
            "variance_percentage": pct,
            "is_undervalued": False,
            "is_overvalued": False,
            "explanation": (
                f"Declared consideration (₹{decl_val:,.2f}) meets or exceeds the government guideline "
                f"valuation (₹{govt_val:,.2f}). Assessment base matches statutory requirements."
            ),
            "recommended_action": "Proceed with standard registration deed preparation.",
            "disclaimer": STATUTORY_VALUATION_DISCLAIMER,
        }
