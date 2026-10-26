"""
Mutation Entity Resolution Engine (TASK-P2-05).

Resolves associations between mutation dockets, Bhumi Setu Parcels, Cases, and Persons.
Enforces strict epistemic rules:
1. Exact identifier / deed matches yield high confidence (0.85 - 0.95).
2. Corroborated plot/khata matches require geographic alignment (mauza, circle).
3. CRITICAL: Never merge records solely because two people share the same name.
   Name-only matches without parcel corroboration are capped at <= 0.40 and routed to review.
4. Cross-tenant matches are strictly prohibited.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, Tuple
import uuid

from app.models.mutation import (
    MutationCase,
    MutationEntityResolution,
    MutationMatchingMethod,
)
from app.models.parcel import Parcel
from app.models.case import Case

logger = logging.getLogger(__name__)


class MutationEntityResolver:
    """
    Evaluates correlation between mutation records and cadastral parcels / legal cases.
    Produces auditable explanations and confidence scores.
    """

    @classmethod
    def resolve_case_to_parcel(
        cls,
        mutation_case: MutationCase,
        parcel: Parcel,
    ) -> Dict[str, Any]:
        """
        Calculates correlation between a mutation proceeding and a cadastral parcel.
        Returns match parameters, confidence score, method, and explanation.
        """
        # Strict tenant isolation
        if mutation_case.org_id != parcel.org_id:
            return {
                "matched": False,
                "confidence_score": 0.0,
                "matching_method": MutationMatchingMethod.MANUAL_OPERATOR_LINK,
                "match_outcome": "REJECTED_CROSS_TENANT",
                "explanation": "Tenant isolation violation: mutation case and parcel belong to different organizations.",
                "requires_review": False,
                "identifiers_compared": {"tenant_a": str(mutation_case.org_id), "tenant_b": str(parcel.org_id)},
            }

        identifiers_compared: Dict[str, Any] = {
            "mutation_district": mutation_case.district,
            "parcel_district": parcel.district,
            "mutation_circle": mutation_case.circle,
            "parcel_circle": parcel.circle,
            "mutation_mauza": mutation_case.mauza,
            "parcel_mauza": parcel.mauza,
            "mutation_khata": mutation_case.khata_number,
            "parcel_khata": parcel.khata_number,
            "mutation_khesra": mutation_case.khesra_number,
            "parcel_khesra": parcel.khesra_number,
        }

        # Check district and circle compatibility
        geo_compat = (
            mutation_case.district.strip().lower() == parcel.district.strip().lower()
            and mutation_case.circle.strip().lower() == parcel.circle.strip().lower()
        )

        if not geo_compat:
            return {
                "matched": False,
                "confidence_score": 0.0,
                "matching_method": MutationMatchingMethod.MANUAL_OPERATOR_LINK,
                "match_outcome": "DISTRICT_CIRCLE_MISMATCH",
                "explanation": f"Geographic boundary mismatch: Mutation ({mutation_case.district}/{mutation_case.circle}) vs Parcel ({parcel.district}/{parcel.circle}).",
                "requires_review": False,
                "identifiers_compared": identifiers_compared,
            }

        mauza_match = (
            bool(mutation_case.mauza)
            and bool(parcel.mauza)
            and mutation_case.mauza.strip().lower() == parcel.mauza.strip().lower()
        )

        khata_match = (
            bool(mutation_case.khata_number)
            and bool(parcel.khata_number)
            and mutation_case.khata_number.strip() == parcel.khata_number.strip()
        )

        khesra_match = (
            bool(mutation_case.khesra_number)
            and bool(parcel.khesra_number)
            and mutation_case.khesra_number.strip() == parcel.khesra_number.strip()
        )

        # 1. Exact plot and khata match within same mauza
        if mauza_match and khata_match and khesra_match:
            return {
                "matched": True,
                "confidence_score": 0.90,
                "matching_method": MutationMatchingMethod.CORROBORATED_PLOT_KHATA,
                "match_outcome": "MATCH_CONFIRMED_HIGH",
                "explanation": (
                    f"Corroborated cadastral match on Mauza '{mutation_case.mauza}', "
                    f"Khata {mutation_case.khata_number}, Khesra {mutation_case.khesra_number}."
                ),
                "requires_review": False,
                "identifiers_compared": identifiers_compared,
            }

        # 2. Mauza and Khesra match (khata different or missing)
        if mauza_match and khesra_match:
            return {
                "matched": True,
                "confidence_score": 0.75,
                "matching_method": MutationMatchingMethod.CORROBORATED_PLOT_KHATA,
                "match_outcome": "MATCH_PROBABLE",
                "explanation": f"Mauza and Khesra/Plot {mutation_case.khesra_number} match, but Khata is unverified or differs.",
                "requires_review": True,
                "identifiers_compared": identifiers_compared,
            }

        # 3. Mauza and Khata match only (khesra missing or differs)
        if mauza_match and khata_match:
            return {
                "matched": True,
                "confidence_score": 0.60,
                "matching_method": MutationMatchingMethod.CORROBORATED_PLOT_KHATA,
                "match_outcome": "MATCH_AMBIGUOUS_KHATA_ONLY",
                "explanation": f"Mauza and Khata {mutation_case.khata_number} match, but specific Khesra/Plot is unverified.",
                "requires_review": True,
                "identifiers_compared": identifiers_compared,
            }

        # No parcel cadastral match
        return {
            "matched": False,
            "confidence_score": 0.10,
            "matching_method": MutationMatchingMethod.CORROBORATED_PLOT_KHATA,
            "match_outcome": "NO_CADASTRAL_OVERLAP",
            "explanation": "No common Khata or Khesra identifiers found within the same mauza.",
            "requires_review": False,
            "identifiers_compared": identifiers_compared,
        }

    @classmethod
    def evaluate_name_only_match(
        cls,
        party_name: str,
        applicant_name: str,
        has_cadastral_corroboration: bool = False,
    ) -> Dict[str, Any]:
        """
        CRITICAL EPISTEMIC RULE:
        Never merge records solely because two people share the same name.
        Common names (e.g. Ramesh Kumar, Birendra Singh) occur in thousands of Bihar mouzas.
        Without cadastral corroboration, name-only matches are capped at <= 0.40 confidence
        and MUST be routed to manual review.
        """
        clean_party = party_name.strip().lower()
        clean_app = applicant_name.strip().lower()

        is_name_match = (clean_party == clean_app) or (clean_party in clean_app) or (clean_app in clean_party)

        if not is_name_match:
            return {
                "matched": False,
                "confidence_score": 0.0,
                "matching_method": MutationMatchingMethod.NAME_ONLY_MATCH_UNVERIFIED,
                "match_outcome": "NO_NAME_MATCH",
                "explanation": f"Party names do not correspond: '{party_name}' vs '{applicant_name}'.",
                "requires_review": False,
            }

        if has_cadastral_corroboration:
            return {
                "matched": True,
                "confidence_score": 0.85,
                "matching_method": MutationMatchingMethod.CORROBORATED_PLOT_KHATA,
                "match_outcome": "NAME_AND_PLOT_CORROBORATED",
                "explanation": f"Party name '{party_name}' matches and is corroborated by cadastral plot/khata data.",
                "requires_review": False,
            }

        # UNCORROBORATED NAME MATCH: Capped at 0.35 - 0.40, requires review
        return {
            "matched": False,
            "confidence_score": 0.35,
            "matching_method": MutationMatchingMethod.NAME_ONLY_MATCH_UNVERIFIED,
            "match_outcome": "NAME_ONLY_MATCH_UNVERIFIED",
            "explanation": (
                f"POTENTIAL NAME OVERLAP ('{party_name}'), but lacking cadastral plot/khata corroboration. "
                "Per system rules, name-only similarity cannot establish parcel association. Human review required."
            ),
            "requires_review": True,
        }
