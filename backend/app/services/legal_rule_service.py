import uuid
from typing import Dict, Any, Optional
from app.models.finding import FindingSeverity

SANTHAL_PARGANAS_DISTRICTS = ["deoghar", "dumka", "godda", "jamtara", "pakur", "sahibganj"]

class LegalRuleEvaluationResult:
    def __init__(
        self,
        rule_id: str,
        rule_version: str,
        statutory_hazard: bool,
        severity: str,
        observed_values: Dict[str, Any],
        legal_citation: str,
        explanation: str,
        recommended_action: Optional[str] = None
    ):
        self.rule_id = rule_id
        self.rule_version = rule_version
        self.statutory_hazard = statutory_hazard
        self.severity = severity
        self.observed_values = observed_values
        self.legal_citation = legal_citation
        self.explanation = explanation
        self.recommended_action = recommended_action

def evaluate_spt_act_section_20(
    state: str,
    district: str,
    vendor_community_category: Optional[str],
    is_raiyati_holding: bool = True
) -> LegalRuleEvaluationResult:
    """
    Evaluates Section 20 of the Santhal Parganas Tenancy (Supplementary Provisions) Act, 1949.
    Section 20 prohibits transfer, by sale, gift, mortgage or will, of Raiyati rights in Santhal Parganas.
    """
    rule_id = "LEGAL_RULE_JH_SPT_SEC_20"
    rule_version = "v1.0-1949-statutory"
    legal_citation = "Santhal Parganas Tenancy (Supplementary Provisions) Act, 1949, Section 20"

    norm_state = state.strip().lower()
    norm_district = district.strip().lower()

    if norm_state != "jharkhand" or norm_district not in SANTHAL_PARGANAS_DISTRICTS:
        return LegalRuleEvaluationResult(
            rule_id=rule_id,
            rule_version=rule_version,
            statutory_hazard=False,
            severity=FindingSeverity.INFORMATIONAL,
            observed_values={"state": state, "district": district, "jurisdiction_match": False},
            legal_citation=legal_citation,
            explanation=f"Parcel jurisdiction ({district}, {state}) is outside Santhal Parganas division. SPT Act Section 20 does not apply."
        )

    # Santhal Parganas jurisdiction match
    is_tribal = (vendor_community_category == "SCHEDULED_TRIBE")
    
    if is_raiyati_holding and is_tribal:
        return LegalRuleEvaluationResult(
            rule_id=rule_id,
            rule_version=rule_version,
            statutory_hazard=True,
            severity=FindingSeverity.CRITICAL,
            observed_values={
                "state": state,
                "district": district,
                "vendor_community_category": vendor_community_category,
                "is_raiyati_holding": is_raiyati_holding,
                "jurisdiction_match": True
            },
            legal_citation=legal_citation,
            explanation=(
                f"Absolute statutory hazard: Property is situated in {district.capitalize()} (Santhal Parganas) and vendor/record holder belongs to "
                f"a Scheduled Tribe under Raiyati holding. Any transfer by sale, gift, or deed is void ab initio under Section 20 of SPT Act, 1949."
            ),
            recommended_action=(
                "Mandatory Legal Stop: Obtain certified extract from Deputy Commissioner's revenue office. Transaction cannot proceed without statutory clearance."
            )
        )

    return LegalRuleEvaluationResult(
        rule_id=rule_id,
        rule_version=rule_version,
        statutory_hazard=False,
        severity=FindingSeverity.LOW,
        observed_values={
            "state": state,
            "district": district,
            "vendor_community_category": vendor_community_category,
            "is_raiyati_holding": is_raiyati_holding,
            "jurisdiction_match": True
        },
        legal_citation=legal_citation,
        explanation="Parcel is in Santhal Parganas, but record does not indicate a protected Scheduled Tribe Raiyati transfer prohibition under Section 20.",
        recommended_action="Conduct standard 30-year chain-of-title verification and revenue rent receipt verification."
    )
