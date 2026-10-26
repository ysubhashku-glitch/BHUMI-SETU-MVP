"""
Judicial Risk Classification and Proceeding Categorizer.

Classifies legal proceedings into standard risk domains based on case types,
statutory sections, and reported orders.
Separates:
1. Procedural detection (case detected in docket)
2. Potential parcel association (probabilistic / schedule candidate)
3. Reviewer verification status (advocate review)
4. Official procedural status (Pending, Disposed, Stayed)
5. Legal effect (requires qualified professional adjudication)
"""

from __future__ import annotations

import re
from typing import Dict, Any, List, Optional, Tuple

from app.models.judicial import JudicialRiskCategory, JudicialCaseStatus


# Case type keywords mapping to risk categories
TITLE_KEYWORDS = {"TITLE SUIT", "T.S.", "TITLE DECLARATION", "SPECIFIC RELIEF", "DECLARATORY SUIT", "EVICTION"}
PARTITION_KEYWORDS = {"PARTITION", "T.P.S.", "BATWARA", "SEPARATION OF SHARE", "CO-SHARER"}
REVENUE_KEYWORDS = {"MUTATION", "JAMABANDI", "DCLR", "BLT", "LAND TRIBUNAL", "REVENUE APPEAL", "REVENUE REVISION"}
WRIT_KEYWORDS = {"CWJC", "CIVIL WRIT", "MJC", "LPA", "LETTER PATENT APPEAL", "SPECIAL LEAVE PETITION", "SLP"}
INJUNCTION_KEYWORDS = {
    "INJUNCTION", "STATUS QUO", "RESTRAINED", "STAY ORDER", "ORDER 39",
    "NO ALIENATION", "MAINTAIN STATUS QUO", "INTERIM RELIEF", "PROHIBITORY"
}


class JudicialRiskClassifier:
    """
    Categorizes judicial proceedings and evaluates active injunction indicators.
    """

    def classify_case(
        self,
        case_type: Optional[str],
        acts_sections: Optional[List[str]] = None,
        orders_summary: Optional[List[Dict[str, Any]]] = None,
        stage_of_case: Optional[str] = None,
    ) -> Tuple[str, bool]:
        """
        Determines the risk category and whether an active injunction/stay is indicated.
        
        Returns:
            Tuple of (risk_category: str, has_active_injunction: bool)
        """
        c_type = (case_type or "").upper()
        acts_text = " ".join(acts_sections or []).upper()
        orders_text = " ".join([str(o.get("summary", "")) for o in (orders_summary or [])]).upper()
        stage_text = (stage_of_case or "").upper()

        combined_text = f"{c_type} {acts_text} {orders_text} {stage_text}"

        # 1. Detect Active Injunction / Stay Status
        has_active_injunction = False
        for kw in INJUNCTION_KEYWORDS:
            if kw in orders_text or kw in stage_text:
                has_active_injunction = True
                break

        # 2. Resolve Category
        # Check Writ / High Court
        if any(kw in c_type for kw in WRIT_KEYWORDS) or "ART 226" in combined_text:
            return JudicialRiskCategory.WRIT_LITIGATION, has_active_injunction

        # Check Partition
        if any(kw in c_type for kw in PARTITION_KEYWORDS) or "PARTITION ACT" in combined_text:
            return JudicialRiskCategory.PARTITION_PROCEEDING, has_active_injunction

        # Check Revenue / Mutation Dispute
        if any(kw in c_type for kw in REVENUE_KEYWORDS) or any(kw in combined_text for kw in REVENUE_KEYWORDS):
            return JudicialRiskCategory.REVENUE_MUTATION_DISPUTE, has_active_injunction

        # Check Injunction Specific Proceeding
        if has_active_injunction and ("INJUNCTION SUIT" in c_type or "MISC CASE" in c_type):
            return JudicialRiskCategory.INJUNCTION_RISK, has_active_injunction

        # Check Title Dispute
        if any(kw in c_type for kw in TITLE_KEYWORDS) or "SPECIFIC RELIEF" in combined_text:
            return JudicialRiskCategory.TITLE_DISPUTE, has_active_injunction

        # Fallback
        return JudicialRiskCategory.OTHER, has_active_injunction
