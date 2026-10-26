"""
Bhumi Setu - Document Intelligence Cross-Reference Service.

Cross-references OCR-extracted land document fields (Sale Deeds, Khatiyans, Jamabandis)
against existing database parcels, Bihar Bhumi Jamabandi revenue records, and Bhu-Naksha cadastral maps.

Epistemic Safety Rule:
    Never declare an automated cross-reference or heuristic match as an authoritative
    or independently verified legal fact. Matches are candidate hypotheses to guide
    human review and field demarcation. Authoritative records are never overwritten.
"""

from __future__ import annotations

import uuid
import re
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.parcel import Parcel
from app.models.evidence import Document, ExtractedField
from app.services.consistency_service import check_area_delta, ConsistencyCheckResult
from app.models.finding import FindingSeverity
from app.schemas.document_pipeline import (
    CrossReferenceMatchCandidate,
    DocumentCrossReferenceResponse
)

class CrossReferenceStatus(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    PROBABLE_MATCH = "PROBABLE_MATCH"
    MULTIPLE_CANDIDATE_MATCHES = "MULTIPLE_CANDIDATE_MATCHES"
    IDENTIFIER_CONFLICT = "IDENTIFIER_CONFLICT"
    AREA_DISCREPANCY = "AREA_DISCREPANCY"
    NO_MATCH = "NO_MATCH"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class DocumentCrossReferenceService:
    """
    Service responsible for deterministic and fuzzy cross-referencing of extracted
    document fields against registered parcels, Jamabandi records, and cadastral maps.
    """

    @classmethod
    def cross_reference_document(
        cls,
        document_id: uuid.UUID,
        org_id: uuid.UUID,
        db: Session,
        jamabandi_records: Optional[List[Dict[str, Any]]] = None,
        cadastral_records: Optional[List[Dict[str, Any]]] = None
    ) -> DocumentCrossReferenceResponse:
        """
        Executes cross-referencing for an uploaded document against tenant parcels and external records.
        """
        # 1. Fetch extracted fields for this document
        fields = db.query(ExtractedField).filter(ExtractedField.document_id == document_id).all()
        field_map: Dict[str, ExtractedField] = {f.field_name: f for f in fields}

        # Extract normalized identifiers
        khata_val = cls._get_normalized_string(field_map.get("khata_number"))
        plot_val = cls._get_normalized_string(field_map.get("plot_number"))
        district_val = cls._get_normalized_string(field_map.get("district"))
        circle_val = cls._get_normalized_string(field_map.get("circle"))
        village_val = cls._get_normalized_string(field_map.get("village"))
        
        extracted_area_acres, extracted_area_sqm = cls._extract_area_metric(field_map.get("recorded_area"))

        party_name = None
        for p_field in ["seller_name", "recorded_raiyat", "buyer_name"]:
            if p_field in field_map and field_map[p_field].raw_value:
                party_name = field_map[p_field].raw_value
                break

        extracted_identifiers = {
            "khata_number": khata_val,
            "plot_number": plot_val,
            "district": district_val,
            "circle": circle_val,
            "village": village_val,
            "recorded_area_acres": extracted_area_acres,
            "recorded_area_sqm": extracted_area_sqm,
            "party_name": party_name
        }

        # Rule: Insufficient identifiers
        if not khata_val and not plot_val:
            return DocumentCrossReferenceResponse(
                document_id=str(document_id),
                status=CrossReferenceStatus.INSUFFICIENT_DATA.value,
                confidence=0.0,
                extracted_identifiers=extracted_identifiers,
                matched_parcel=None,
                candidate_matches=[],
                discrepancies=[],
                explanations=["Document lacks critical Khata and Plot/Khesra number identifiers for cross-referencing."],
                review_required=True
            )

        # 2. Query Candidate Parcels in Tenant Org
        query = db.query(Parcel).filter(Parcel.org_id == org_id)

        # Match by plot number if available
        matched_parcels: List[Parcel] = []
        if plot_val and plot_val != "UNKNOWN":
            clean_plot = re.sub(r"[^A-Za-z0-9]", "", plot_val).lower()
            all_org_parcels = query.all()
            for p in all_org_parcels:
                p_clean = re.sub(r"[^A-Za-z0-9]", "", p.plot_khesra_number or "").lower()
                if clean_plot == p_clean or clean_plot in p_clean:
                    matched_parcels.append(p)
        elif khata_val and khata_val != "UNKNOWN":
            clean_khata = re.sub(r"[^A-Za-z0-9]", "", khata_val).lower()
            all_org_parcels = query.all()
            for p in all_org_parcels:
                p_khata = re.sub(r"[^A-Za-z0-9]", "", p.khata_number or "").lower()
                if clean_khata == p_khata:
                    matched_parcels.append(p)

        # 3. Evaluate Match Outcomes
        if not matched_parcels:
            # Check external Jamabandi records if provided
            if jamabandi_records:
                ext_match = cls._match_external_jamabandi(extracted_identifiers, jamabandi_records)
                if ext_match:
                    return ext_match

            return DocumentCrossReferenceResponse(
                document_id=str(document_id),
                status=CrossReferenceStatus.NO_MATCH.value,
                confidence=0.10,
                extracted_identifiers=extracted_identifiers,
                matched_parcel=None,
                candidate_matches=[],
                discrepancies=[],
                explanations=["No matching registered parcel found in the organization repository."],
                review_required=True
            )

        if len(matched_parcels) > 1:
            candidates = [cls._build_candidate(p, 0.65, ["Multiple plots with matching identifier"]) for p in matched_parcels]
            return DocumentCrossReferenceResponse(
                document_id=str(document_id),
                status=CrossReferenceStatus.MULTIPLE_CANDIDATE_MATCHES.value,
                confidence=0.60,
                extracted_identifiers=extracted_identifiers,
                matched_parcel=None,
                candidate_matches=candidates,
                discrepancies=[],
                explanations=[f"Found {len(matched_parcels)} candidate parcels matching plot number '{plot_val}'."],
                review_required=True
            )

        # Single Candidate Parcel Found
        target_parcel = matched_parcels[0]
        reasons: List[str] = ["Plot/Khesra number match"]
        discrepancies: List[Dict[str, Any]] = []
        is_exact = True
        status = CrossReferenceStatus.EXACT_MATCH
        confidence = 0.95

        # Check Khata consistency
        p_khata_clean = re.sub(r"[^A-Za-z0-9]", "", target_parcel.khata_number or "").lower()
        doc_khata_clean = re.sub(r"[^A-Za-z0-9]", "", khata_val or "").lower()

        if doc_khata_clean and p_khata_clean and doc_khata_clean != p_khata_clean:
            is_exact = False
            status = CrossReferenceStatus.IDENTIFIER_CONFLICT
            confidence = 0.50
            reasons.append(f"Khata number mismatch: Document states '{khata_val}', parcel has '{target_parcel.khata_number}'")
            discrepancies.append({
                "field": "khata_number",
                "document_value": khata_val,
                "parcel_value": target_parcel.khata_number,
                "type": "IDENTIFIER_CONFLICT"
            })

        # Check Mauza / Village consistency if present
        if village_val and village_val != "UNKNOWN":
            p_mauza = (target_parcel.mauza_village_name or "").lower()
            doc_mauza = village_val.lower()
            if doc_mauza not in p_mauza and p_mauza not in doc_mauza:
                reasons.append(f"Village name variance: Document states '{village_val}', parcel has '{target_parcel.mauza_village_name}'")

        # Check Area Consistency
        if extracted_area_acres is not None and float(target_parcel.recorded_area_acres or 0) > 0:
            parcel_acres = float(target_parcel.recorded_area_acres)
            doc_sqm = extracted_area_sqm if extracted_area_sqm else (extracted_area_acres * 4046.8564)
            parcel_sqm = parcel_acres * 4046.8564

            area_check = check_area_delta(
                deed_area_sqm=doc_sqm,
                survey_area_sqm=parcel_sqm,
                tolerance_pct=5.0
            )

            if not area_check.passed:
                is_exact = False
                status = CrossReferenceStatus.AREA_DISCREPANCY
                confidence = 0.70
                reasons.append(area_check.explanation)
                discrepancies.append({
                    "field": "recorded_area",
                    "document_area_acres": extracted_area_acres,
                    "parcel_area_acres": parcel_acres,
                    "document_area_sqm": doc_sqm,
                    "parcel_area_sqm": parcel_sqm,
                    "delta_percentage": abs(doc_sqm - parcel_sqm) / max(doc_sqm, parcel_sqm) * 100.0,
                    "severity": area_check.severity,
                    "type": "AREA_DISCREPANCY"
                })
            else:
                reasons.append(f"Recorded area matches within 5% tolerance (Doc: {extracted_area_acres} ac, Parcel: {parcel_acres} ac)")

        # External Jamabandi consistency check if provided
        if jamabandi_records:
            j_match = cls._match_external_jamabandi(extracted_identifiers, jamabandi_records)
            if j_match and j_match.discrepancies:
                discrepancies.extend(j_match.discrepancies)

        # Build candidate object
        candidate = cls._build_candidate(target_parcel, confidence, reasons)

        review_required = (status != CrossReferenceStatus.EXACT_MATCH)

        return DocumentCrossReferenceResponse(
            document_id=str(document_id),
            status=status.value,
            confidence=confidence,
            extracted_identifiers=extracted_identifiers,
            matched_parcel=candidate,
            candidate_matches=[candidate],
            discrepancies=discrepancies,
            explanations=reasons,
            review_required=review_required
        )

    @classmethod
    def _get_normalized_string(cls, field: Optional[ExtractedField]) -> Optional[str]:
        if not field:
            return None
        if isinstance(field.normalized_value, str) and field.normalized_value != "UNKNOWN":
            return field.normalized_value
        return field.raw_value

    @classmethod
    def _extract_area_metric(cls, field: Optional[ExtractedField]) -> Tuple[Optional[float], Optional[float]]:
        if not field:
            return None, None
        norm = field.normalized_value
        if isinstance(norm, dict):
            acres = norm.get("normalized_acres") or norm.get("total_acres") or norm.get("standard_acres")
            sqm = norm.get("normalized_sqm") or norm.get("square_meters")
            return (float(acres) if acres else None, float(sqm) if sqm else None)
        return None, None

    @classmethod
    def _build_candidate(cls, parcel: Parcel, conf: float, reasons: List[str]) -> CrossReferenceMatchCandidate:
        return CrossReferenceMatchCandidate(
            parcel_id=str(parcel.parcel_id),
            bhumi_id=parcel.bhumi_id,
            khata_number=parcel.khata_number,
            plot_number=parcel.plot_khesra_number,
            mauza=parcel.mauza_village_name,
            recorded_area_acres=float(parcel.recorded_area_acres) if parcel.recorded_area_acres else None,
            match_confidence=conf,
            match_reasons=reasons
        )

    @classmethod
    def _match_external_jamabandi(
        cls,
        extracted_identifiers: Dict[str, Any],
        jamabandi_records: List[Dict[str, Any]]
    ) -> Optional[DocumentCrossReferenceResponse]:
        doc_plot = extracted_identifiers.get("plot_number")
        doc_khata = extracted_identifiers.get("khata_number")
        doc_raiyat = extracted_identifiers.get("party_name")

        matches = []
        for rec in jamabandi_records:
            r_plot = rec.get("khesra_plot_no") or rec.get("plot")
            r_khata = rec.get("khata_no") or rec.get("khata")
            r_tenant = rec.get("raiyat_name") or rec.get("tenant")

            plot_match = (doc_plot and r_plot and str(doc_plot).strip() == str(r_plot).strip())
            khata_match = (doc_khata and r_khata and str(doc_khata).strip() == str(r_khata).strip())

            if plot_match or khata_match:
                matches.append((rec, plot_match, khata_match, r_tenant))

        if not matches:
            return None

        first_rec, p_match, k_match, tenant = matches[0]
        reasons = []
        discrepancies = []
        conf = 0.80

        if p_match and k_match:
            status = CrossReferenceStatus.EXACT_MATCH
            reasons.append("Exact match on Khata and Plot in Bihar Jamabandi Register-II")
            conf = 0.95
        elif p_match:
            status = CrossReferenceStatus.PROBABLE_MATCH
            reasons.append("Plot matches Bihar Jamabandi Register-II record")
            conf = 0.75
        else:
            status = CrossReferenceStatus.PROBABLE_MATCH
            reasons.append("Khata matches Bihar Jamabandi Register-II record")
            conf = 0.70

        if doc_raiyat and tenant:
            if doc_raiyat.lower() not in tenant.lower() and tenant.lower() not in doc_raiyat.lower():
                discrepancies.append({
                    "field": "raiyat_name",
                    "document_party": doc_raiyat,
                    "jamabandi_tenant": tenant,
                    "type": "TENANT_NAME_VARIANCE"
                })
                reasons.append(f"Recorded Jamabandi tenant ('{tenant}') differs from document party ('{doc_raiyat}')")
                status = CrossReferenceStatus.PROBABLE_MATCH

        return DocumentCrossReferenceResponse(
            document_id=str(uuid.uuid4()),
            status=status.value,
            confidence=conf,
            extracted_identifiers=extracted_identifiers,
            matched_parcel=None,
            candidate_matches=[],
            discrepancies=discrepancies,
            explanations=reasons,
            review_required=(status != CrossReferenceStatus.EXACT_MATCH)
        )
