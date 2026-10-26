"""
Deterministic Judicial Entity Resolution Engine.

Correlates land parcels with court proceedings using traceable, explainable evidence:
- Distinguishes exact identifier matches, strong corroborated candidates,
  unverified candidates requiring human review, rejected matches, and insufficient data.
- Enforces the core domain rule: A party-name match WITHOUT parcel-specific corroboration
  (plot/khesra, khata, mauza) MUST REMAIN an unverified candidate (WEAK_CANDIDATE_REVIEW_REQUIRED)
  and must NEVER be automatically represented as a confirmed parcel dispute.
"""

from __future__ import annotations

import re
from typing import Dict, Any, List, Optional, Tuple, Set

from app.models.judicial import ParcelMatchCategory
from app.models.parcel import Parcel


# Bihar honorifics, titles, and common relation tokens for name normalization
HONORIFICS_REGEX = re.compile(
    r"\b(SRI|SHRI|SHREE|SMT|SHRIMATI|LATE|SWARGIYA|MD|MOHAMMAD|DEVI|W\/O|S\/O|D\/O|C\/O|ALIAS|URPH|URF)\b",
    re.IGNORECASE,
)

PUNCTUATION_REGEX = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_legal_name(name: Optional[str]) -> str:
    """
    Normalizes a personal or party name:
    - Strips honorifics (Sri, Smt, Late, etc.)
    - Removes punctuation
    - Collapses whitespace
    - Uppercases for case-insensitive matching
    """
    if not name:
        return ""
    cleaned = HONORIFICS_REGEX.sub(" ", name)
    cleaned = PUNCTUATION_REGEX.sub(" ", cleaned)
    tokens = [t.strip().upper() for t in cleaned.split() if len(t.strip()) > 1]
    return " ".join(tokens)


def token_overlap_score(name_a: str, name_b: str) -> float:
    """
    Calculates Jaccard token overlap similarity between two normalized names.
    Returns float in range [0.0, 1.0].
    """
    norm_a = normalize_legal_name(name_a)
    norm_b = normalize_legal_name(name_b)
    if not norm_a or not norm_b:
        return 0.0

    tokens_a = set(norm_a.split())
    tokens_b = set(norm_b.split())

    if not tokens_a or not tokens_b:
        return 0.0

    intersection = tokens_a.intersection(tokens_b)
    union = tokens_a.union(tokens_b)
    return len(intersection) / len(union)


class JudicialEntityResolver:
    """
    Deterministic Entity Resolution Engine for Court Cases vs Land Parcels.
    """

    MATCHING_VERSION = "DETERMINISTIC_ENTITY_RESOLUTION_v1.0"

    def match_case_to_parcel(
        self,
        parcel: Parcel,
        case_dict: Dict[str, Any],
        is_direct_cnr_lookup: bool = False,
    ) -> Dict[str, Any]:
        """
        Evaluates parcel against a judicial case docket.
        
        Returns:
            Dict containing:
                - match_category (str)
                - confidence_score (float)
                - matched_fields (dict)
                - matching_method (str)
                - explanation (str)
        """
        matched_fields: Dict[str, Any] = {
            "matched_khesra": False,
            "matched_khata": False,
            "matched_mauza": False,
            "matched_district": False,
            "matched_party": False,
            "parcel_khesra": parcel.khesra_number,
            "parcel_khata": parcel.khata_number,
            "parcel_mauza": parcel.mauza,
            "parcel_district": parcel.district,
            "parcel_recorded_raiyat": parcel.recorded_raiyat,
            "case_district": case_dict.get("district"),
            "extracted_land_identifiers": case_dict.get("extracted_land_identifiers") or {},
            "petitioner_names": case_dict.get("petitioner_names") or [],
            "respondent_names": case_dict.get("respondent_names") or [],
            "missing_corroboration": [],
        }

        # 1. Evaluate Geographic Alignment
        parcel_district = (parcel.district or "").strip().upper()
        case_district = (case_dict.get("district") or "").strip().upper()
        court_type = (case_dict.get("court_type") or "DISTRICT_COURT").upper()

        if parcel_district and case_district:
            if parcel_district == case_district:
                matched_fields["matched_district"] = True
            elif court_type == "DISTRICT_COURT":
                # District court in a completely different district: Hard Rejection
                return {
                    "match_category": ParcelMatchCategory.REJECTED_MATCH,
                    "confidence_score": 0.0,
                    "matched_fields": matched_fields,
                    "matching_method": self.MATCHING_VERSION,
                    "explanation": (
                        f"Geographic contradiction: Parcel is located in District '{parcel_district}', "
                        f"but proceeding is before District Court of '{case_district}'. Suit rejected as non-jurisdictional."
                    ),
                }

        # 2. Evaluate Plot and Khata Extracted Identifiers
        extracted_land = case_dict.get("extracted_land_identifiers") or {}
        extracted_khesra = str(extracted_land.get("khesra") or "").strip()
        extracted_khata = str(extracted_land.get("khata") or "").strip()
        extracted_mauza = str(extracted_land.get("mauza") or "").strip().upper()

        parcel_khesra = str(parcel.khesra_number or "").strip()
        parcel_khata = str(parcel.khata_number or "").strip()
        parcel_mauza = str(parcel.mauza or "").strip().upper()

        if extracted_khesra and parcel_khesra and extracted_khesra == parcel_khesra:
            matched_fields["matched_khesra"] = True

        if extracted_khata and parcel_khata and extracted_khata == parcel_khata:
            matched_fields["matched_khata"] = True

        if extracted_mauza and parcel_mauza and (extracted_mauza in parcel_mauza or parcel_mauza in extracted_mauza):
            matched_fields["matched_mauza"] = True

        # 3. Evaluate Party Name Overlap
        raiyat_name = parcel.recorded_raiyat or ""
        best_party_overlap = 0.0
        best_matched_party_name = None

        all_case_parties = case_dict.get("petitioner_names", []) + case_dict.get("respondent_names", [])
        for party in all_case_parties:
            score = token_overlap_score(raiyat_name, party)
            if score > best_party_overlap:
                best_party_overlap = score
                best_matched_party_name = party

        if best_party_overlap >= 0.50:
            matched_fields["matched_party"] = True
            matched_fields["matched_party_name"] = best_matched_party_name
            matched_fields["party_overlap_score"] = round(best_party_overlap, 2)

        # 4. Resolve Match Category & Calibrated Confidence

        # Scenario A: Direct CNR search linkage with corroboration
        if is_direct_cnr_lookup and (matched_fields["matched_khesra"] or matched_fields["matched_khata"] or matched_fields["matched_party"]):
            return {
                "match_category": ParcelMatchCategory.EXACT_IDENTIFIER_MATCH,
                "confidence_score": 0.95,
                "matched_fields": matched_fields,
                "matching_method": self.MATCHING_VERSION,
                "explanation": (
                    f"Exact judicial proceeding link: Proceeding CNR '{case_dict.get('cnr_number')}' "
                    f"was directly queried and corroborated with parcel identifiers."
                ),
            }

        # Scenario B: Explicit Plot (Khesra) + Khata Schedule Match in same district
        if matched_fields["matched_khesra"] and matched_fields["matched_khata"]:
            if matched_fields["matched_party"]:
                return {
                    "match_category": ParcelMatchCategory.EXACT_IDENTIFIER_MATCH,
                    "confidence_score": 0.95,
                    "matched_fields": matched_fields,
                    "matching_method": self.MATCHING_VERSION,
                    "explanation": (
                        f"Exact parcel schedule and party match: Court schedule explicitly lists Khesra {parcel_khesra} "
                        f"and Khata {parcel_khata} in {case_district}, matching recorded raiyat '{raiyat_name}'."
                    ),
                }
            else:
                matched_fields["missing_corroboration"].append("party_name_not_matched")
                return {
                    "match_category": ParcelMatchCategory.STRONG_CORROBORATED_MATCH,
                    "confidence_score": 0.85,
                    "matched_fields": matched_fields,
                    "matching_method": self.MATCHING_VERSION,
                    "explanation": (
                        f"Strong cadastral schedule match: Court schedule explicitly identifies Khesra {parcel_khesra} "
                        f"and Khata {parcel_khata} in {case_district}. Recorded raiyat name differs or represents co-sharer/assignee."
                    ),
                }

        # Scenario C: Plot (Khesra) Match with Mauza/District Match
        if matched_fields["matched_khesra"] and (matched_fields["matched_mauza"] or matched_fields["matched_district"]):
            if matched_fields["matched_party"]:
                return {
                    "match_category": ParcelMatchCategory.STRONG_CORROBORATED_MATCH,
                    "confidence_score": 0.80,
                    "matched_fields": matched_fields,
                    "matching_method": self.MATCHING_VERSION,
                    "explanation": (
                        f"Strong cadastral match: Court schedule specifies Khesra {parcel_khesra} and party '{best_matched_party_name}' "
                        f"in {case_district}. Khata schedule number unconfirmed in docket."
                    ),
                }
            else:
                matched_fields["missing_corroboration"].extend(["khata_unconfirmed", "party_unconfirmed"])
                return {
                    "match_category": ParcelMatchCategory.STRONG_CORROBORATED_MATCH,
                    "confidence_score": 0.70,
                    "matched_fields": matched_fields,
                    "matching_method": self.MATCHING_VERSION,
                    "explanation": (
                        f"Cadastral match on Khesra {parcel_khesra} in {case_district}. "
                        f"Requires advocate schedule verification for Khata and co-sharer identity."
                    ),
                }

        # Scenario D: Party Name Match WITHOUT Parcel-Specific Corroboration
        # CRITICAL DOMAIN RULE: Must remain WEAK_CANDIDATE_REVIEW_REQUIRED with calibrated confidence <= 0.45.
        if matched_fields["matched_party"]:
            matched_fields["missing_corroboration"].extend([
                "khesra_plot_not_in_docket",
                "khata_not_in_docket",
                "schedule_unverified",
            ])
            return {
                "match_category": ParcelMatchCategory.WEAK_CANDIDATE_REVIEW_REQUIRED,
                "confidence_score": 0.45,
                "matched_fields": matched_fields,
                "matching_method": self.MATCHING_VERSION,
                "explanation": (
                    f"Unverified candidate match: Party name '{best_matched_party_name}' matches recorded raiyat "
                    f"'{raiyat_name}', but the court docket contains NO parcel-specific plot (khesra) or khata identifiers. "
                    f"Similar names are common in Bihar civil dockets; this cannot be represented as a confirmed parcel dispute "
                    f"without certified plaint/schedule review by an advocate."
                ),
            }

        # Scenario E: Insufficient Data / No identifiable overlaps
        matched_fields["missing_corroboration"].extend([
            "no_plot_match",
            "no_khata_match",
            "no_party_overlap",
        ])
        return {
            "match_category": ParcelMatchCategory.INSUFFICIENT_DATA,
            "confidence_score": 0.10,
            "matched_fields": matched_fields,
            "matching_method": self.MATCHING_VERSION,
            "explanation": (
                "Insufficient source data: Court docket contains no matching cadastral identifiers (khesra/khata) "
                "or recognizable party name overlap for this parcel."
            ),
        }
