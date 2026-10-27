"""
Cross-Source Evidence Reconciliation Engine (TASK-P2-06).

Reconciles evidence across all six Bhumi Setu intelligence pillars:
1. Revenue & Jamabandi (P1-01)
2. Document OCR, Chauhaddi & Kaithi (P1-02, P2-01)
3. Cadastral Vector Overlay & Bhu-Naksha (P1-03, P2-04)
4. LandAmin Field Verification & GPS (P1-04)
5. Judicial Litigation & High Court Injunctions (P2-02)
6. MVR Valuation & Stamp Duty (P2-03)
7. Mutation Proceedings & Dakhil-Kharij (P2-05)

Enforces strict epistemic rules:
- Observed facts, derived inferences, review findings, and evidence gaps are kept separate.
- Missing values are explicitly recorded as Evidence Gaps, NEVER silently assumed to be clean or zero risk.
- Anti-name-only matching: Name-only similarity without plot/khata corroboration is never sufficient.
- Upstream validation gates: Inadequate georeferencing, unverified MVR schedules, or unindexed searches are flagged.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.parcel import Parcel
from app.models.case import Case
from app.models.claim import Claim, ClaimPredicate
from app.models.evidence import Evidence, CaseEvidence, Document, ExtractedField
from app.models.field_survey import FieldSurvey
from app.models.field_task import FieldVerificationTask
from app.models.judicial import JudicialCase, ParcelJudicialMatch
from app.models.valuation import PropertyValuation, MVRSchedule
from app.models.spatial_overlay import BoundaryOverlayAnalysis, CadastralParcelGeometry
from app.models.mutation import (
    MutationCase,
    MutationEvent,
    MutationStatus,
    MutationEntityResolution,
)
from app.models.passport_synthesis import (
    RiskDimension,
    ReconciliationOutcome,
    FindingSeverity,
    FindingReviewStatus,
    InferenceReviewStatus,
)

logger = logging.getLogger(__name__)

# Recognized valid geographic and projected CRS codes for Bihar and Indian subcontinent
RECOGNIZED_REGIONAL_CRSS = {
    "EPSG:32645",  # UTM Zone 45N (Central / North / South Bihar - Patna, Gaya, Muzaffarpur)
    "EPSG:32644",  # UTM Zone 44N (Western Bihar - Buxar, Kaimur, Rohtas)
    "EPSG:32646",  # UTM Zone 46N (Far Eastern Bihar - Kishanganj)
    "EPSG:4326",   # WGS 84 Geographic 2D (Standard GPS lat/lon)
    "EPSG:7755",   # Survey of India LCC (National Grid)
    "EPSG:7760",   # Survey of India Zone IIa (West Gangetic Plain)
    "EPSG:7761",   # Survey of India Zone IIb (East Gangetic Plain)
    "EPSG:24378",  # Kalianpur 1975 / India Zone IIa
    "EPSG:24379",  # Kalianpur 1975 / India Zone IIb
}

# Provisional independent check-point error tolerance (meters) for cadastral scale 1:3960 / 1:1980
PROVISIONAL_CHECKPOINT_RMSE_THRESHOLD_METERS = 2.50


class EvidenceReconciliationEngine:
    """
    Analyzes all persistent domain evidence for a parcel and generates
    structured facts, inferences, findings, and evidence gaps.
    """

    @classmethod
    def reconcile_parcel_evidence(
        cls,
        db: Session,
        parcel: Parcel,
        case: Optional[Case] = None,
        include_synthetic_fixtures: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes multi-pillar cross-source reconciliation.
        Returns a dictionary containing:
            - facts: List[Dict[str, Any]]
            - inferences: List[Dict[str, Any]]
            - findings: List[Dict[str, Any]]
            - evidence_gaps: List[Dict[str, Any]]
            - reconciliation_summary: Dict[str, Any]
        """
        facts: List[Dict[str, Any]] = []
        inferences: List[Dict[str, Any]] = []
        findings: List[Dict[str, Any]] = []
        evidence_gaps: List[Dict[str, Any]] = []
        summary: Dict[str, Any] = {}

        org_id = parcel.org_id
        now_utc = datetime.now(timezone.utc)

        # -----------------------------------------------------------------
        # 1. REVENUE RECORDS & IDENTIFIERS
        # -----------------------------------------------------------------
        facts.append({
            "subsystem": "REVENUE",
            "fact_category": "RECORDED_PARCEL_IDENTIFIERS",
            "source_reference": "Bhumi Setu Cadastral Registry (Register-II / Khatian)",
            "source_retrieval_date": parcel.created_at,
            "applicable_date": parcel.created_at,
            "raw_value": {
                "bhumi_id": parcel.bhumi_id,
                "district": parcel.district,
                "circle": parcel.circle,
                "mauza": parcel.mauza,
                "khata": parcel.khata_number,
                "khesra": parcel.plot_khesra_number,
                "recorded_area_acres": float(parcel.recorded_area_acres) if parcel.recorded_area_acres else None,
                "land_nature": parcel.land_nature,
            },
            "normalized_value": {
                "district": parcel.district.strip().title() if parcel.district else "Unknown",
                "circle": parcel.circle.strip().title() if parcel.circle else "Unknown",
                "mauza": parcel.mauza.strip().title() if parcel.mauza else "Unknown",
                "khata": str(parcel.khata_number).strip() if parcel.khata_number else None,
                "khesra": str(parcel.plot_khesra_number).strip() if parcel.plot_khesra_number else None,
                "area_acres": float(parcel.recorded_area_acres) if parcel.recorded_area_acres else 0.0,
            },
            "verification_status": "OFFICIAL_SOURCE",
            "limitations": "Subject to historical Jamabandi digitisation currency and circle records.",
        })

        # Check for recorded raiyat / owner claim
        owner_claim = db.query(Claim).filter(
            Claim.parcel_id == parcel.parcel_id,
            Claim.predicate == ClaimPredicate.RECORDED_OWNER,
        ).first()

        raiyat_name = None
        if owner_claim:
            if isinstance(owner_claim.object_value, dict):
                raiyat_name = owner_claim.object_value.get("name") or owner_claim.object_value.get("raiyat_name")
            elif isinstance(owner_claim.object_value, str):
                raiyat_name = owner_claim.object_value

            facts.append({
                "subsystem": "REVENUE",
                "fact_category": "RECORDED_RAIYAT_CLAIM",
                "source_reference": f"Claim {owner_claim.claim_id} (Jamabandi Register-II)",
                "source_retrieval_date": owner_claim.created_at,
                "raw_value": {"claim_id": str(owner_claim.claim_id), "raiyat": raiyat_name},
                "normalized_value": {"raiyat_name": raiyat_name},
                "verification_status": "OFFICIAL_SOURCE",
            })
        else:
            evidence_gaps.append({
                "subsystem": "REVENUE",
                "gap_code": "GAP-REV-NO-OWNER-CLAIM",
                "description": "No recorded raiyat / owner claim currently mapped to parcel in Register-II.",
                "impact_on_assessment": "Ownership lineage cannot be cross-referenced against seller/applicant.",
                "remedy_action": "Retrieve certified copy of Jamabandi extract from Circle Office.",
                "is_blocking": False,
            })

        # -----------------------------------------------------------------
        # 2. TRANSACTION & MUTATION INTELLIGENCE (P2-05)
        # -----------------------------------------------------------------
        mutation_cases = db.query(MutationCase).filter(
            MutationCase.org_id == org_id,
            or_(
                MutationCase.parcel_id == parcel.parcel_id,
                MutationCase.resolutions.any(MutationEntityResolution.parcel_id == parcel.parcel_id),
            ),
        ).all()

        if mutation_cases:
            has_adverse_rejection = False
            has_conflicting_mutation = False
            active_proceedings = 0

            for mc in mutation_cases:
                facts.append({
                    "subsystem": "MUTATION",
                    "fact_category": "MUTATION_PROCEEDING_STATUS",
                    "source_reference": f"{mc.source_portal} - Case {mc.case_number}",
                    "source_retrieval_date": mc.last_source_observation or mc.created_at,
                    "applicable_date": datetime.combine(mc.filing_date, datetime.min.time(), tzinfo=timezone.utc) if mc.filing_date else None,
                    "raw_value": {
                        "case_number": mc.case_number,
                        "raw_status": mc.raw_source_status,
                        "rejection_code": mc.rejection_reason_code,
                        "rejection_details": mc.rejection_reason_details,
                    },
                    "normalized_value": {
                        "case_number": mc.case_number,
                        "normalized_status": mc.normalized_status.value,
                        "applicant_names": mc.applicant_names,
                        "seller_names": mc.seller_names,
                    },
                    "verification_status": mc.verification_status.value,
                    "limitations": "Mutation records indicate revenue tax liability, not title (Suraj Bhan v. Financial Commissioner).",
                })

                if mc.normalized_status == MutationStatus.REJECTED:
                    has_adverse_rejection = True
                    findings.append({
                        "dimension": RiskDimension.TRANSACTION_MUTATION,
                        "finding_code": f"FIND-MUT-REJECTED-{mc.rejection_reason_code or 'ORDER'}",
                        "severity": FindingSeverity.HIGH,
                        "title": f"Adverse Mutation Rejection: {mc.case_number}",
                        "description": (
                            f"Mutation application was rejected by Circle Officer. "
                            f"Grounds: {mc.rejection_reason_code or 'Administrative rejection'}. "
                            f"Details: {mc.rejection_reason_details or 'See certified order sheet'}."
                        ),
                        "supporting_evidence": {"case_number": mc.case_number, "rejection_code": mc.rejection_reason_code},
                        "recommended_action": "Obtain certified copy of rejection order sheet and review legal defects before transaction.",
                        "requires_human_review": True,
                    })

                elif mc.normalized_status == MutationStatus.CONFLICTING_EVIDENCE:
                    has_conflicting_mutation = True
                    findings.append({
                        "dimension": RiskDimension.TRANSACTION_MUTATION,
                        "finding_code": "FIND-MUT-CONFLICTING-EVIDENCE",
                        "severity": FindingSeverity.CRITICAL,
                        "title": f"Conflicting Mutation Evidence: {mc.case_number}",
                        "description": f"Conflicting observations detected between official portals and submitted records: {mc.notes}",
                        "supporting_evidence": {"case_number": mc.case_number},
                        "recommended_action": "Conduct manual inspection of Circle Office docket Register-II to resolve contradiction.",
                        "requires_human_review": True,
                    })

                elif mc.normalized_status in (
                    MutationStatus.RECEIVED,
                    MutationStatus.SUBMITTED,
                    MutationStatus.UNDER_SCRUTINY,
                    MutationStatus.NOTICE_ISSUED,
                    MutationStatus.HEARING_PENDING,
                    MutationStatus.UNDER_REVIEW,
                ):
                    active_proceedings += 1

            if active_proceedings > 0:
                findings.append({
                    "dimension": RiskDimension.TRANSACTION_MUTATION,
                    "finding_code": "FIND-MUT-ACTIVE-PROCEEDING",
                    "severity": FindingSeverity.MEDIUM,
                    "title": f"Active Mutation Proceeding in Progress ({active_proceedings} case(s))",
                    "description": "One or more Dakhil-Kharij proceedings are pending before Circle Officer (CO). Form-IX notice or hearing pending.",
                    "supporting_evidence": {"active_cases_count": active_proceedings},
                    "recommended_action": "Verify whether public objections were filed during Form-IX window.",
                    "requires_human_review": False,
                })
        else:
            evidence_gaps.append({
                "subsystem": "MUTATION",
                "gap_code": "GAP-MUT-NO-PROCEEDINGS-FOUND",
                "description": "No mutation proceedings discovered for this parcel.",
                "impact_on_assessment": "Absence of mutation history does not confirm clear title; property may have unrecorded transfers.",
                "remedy_action": "Search Bihar Bhumi using historical deed registration numbers.",
                "is_blocking": False,
            })

        # -----------------------------------------------------------------
        # 3. JUDICIAL LITIGATION & INJUNCTIONS (P2-02)
        # -----------------------------------------------------------------
        judicial_matches = db.query(ParcelJudicialMatch).filter(
            ParcelJudicialMatch.parcel_id == parcel.parcel_id,
        ).all()

        if judicial_matches:
            for jm in judicial_matches:
                j_case = db.query(JudicialCase).filter(JudicialCase.case_id == jm.judicial_case_id).first()
                if not j_case:
                    continue

                facts.append({
                    "subsystem": "JUDICIAL",
                    "fact_category": "COURT_CASE_RECORD",
                    "source_reference": f"eCourts Services / Patna High Court - CNR {j_case.cnr_number}",
                    "source_retrieval_date": j_case.retrieval_timestamp,
                    "applicable_date": j_case.filing_date,
                    "raw_value": {
                        "cnr_number": j_case.cnr_number,
                        "court_name": j_case.court_name,
                        "case_number": j_case.case_number,
                        "case_status": j_case.case_status,
                        "has_injunction": j_case.has_active_injunction,
                    },
                    "normalized_value": {
                        "cnr": j_case.cnr_number,
                        "risk_category": j_case.risk_category,
                        "match_category": jm.match_category,
                        "confidence_score": float(jm.confidence_score),
                    },
                    "verification_status": "OFFICIAL_SOURCE",
                    "limitations": "Court records search is probabilistic; identical personal names frequently occur across Bihar.",
                })

                if j_case.has_active_injunction:
                    findings.append({
                        "dimension": RiskDimension.JUDICIAL_LITIGATION,
                        "finding_code": "FIND-JUD-ACTIVE-INJUNCTION",
                        "severity": FindingSeverity.CRITICAL,
                        "title": f"Active Judicial Stay / Injunction Detected: CNR {j_case.cnr_number}",
                        "description": (
                            f"Court docket in {j_case.court_name} ({j_case.case_number}) records an ACTIVE INJUNCTION or stay order. "
                            f"Risk category: {j_case.risk_category}. Match confidence: {jm.confidence_score}."
                        ),
                        "supporting_evidence": {"cnr_number": j_case.cnr_number, "court": j_case.court_name},
                        "recommended_action": "MANDATORY: Advocate due diligence on civil suit plaint and interim injunction schedule.",
                        "requires_human_review": True,
                    })
                elif jm.confidence_score >= 0.70:
                    findings.append({
                        "dimension": RiskDimension.JUDICIAL_LITIGATION,
                        "finding_code": "FIND-JUD-CORROBORATED-LITIGATION",
                        "severity": FindingSeverity.HIGH,
                        "title": f"Pending Litigation Candidate: {j_case.case_number}",
                        "description": (
                            f"Civil case in {j_case.court_name} correlates with parcel identifiers or parties. "
                            f"Status: {j_case.case_status}. Risk: {j_case.risk_category}."
                        ),
                        "supporting_evidence": {"cnr": j_case.cnr_number, "explanation": jm.explanation},
                        "recommended_action": "Inspect court case schedule to verify whether this specific parcel is subject matter of dispute.",
                        "requires_human_review": True,
                    })
                elif jm.matching_method == "NAME_ONLY_MATCH_UNVERIFIED" or jm.confidence_score <= 0.40:
                    findings.append({
                        "dimension": RiskDimension.JUDICIAL_LITIGATION,
                        "finding_code": "FIND-JUD-UNVERIFIED-NAME-OVERLAP",
                        "severity": FindingSeverity.LOW,
                        "title": "Uncorroborated Name Overlap in Judicial Registry",
                        "description": (
                            f"Party name similarity detected in {j_case.case_number}, but lacking plot/khata corroboration. "
                            "Per system rules, name-only overlap cannot confirm litigation. Informational only."
                        ),
                        "supporting_evidence": {"cnr": j_case.cnr_number},
                        "recommended_action": "Check party parentage and village in plaint schedule.",
                        "requires_human_review": False,
                    })
        else:
            evidence_gaps.append({
                "subsystem": "JUDICIAL",
                "gap_code": "GAP-JUD-INCOMPLETE-SEARCH",
                "description": "Judicial search depends on top-level eCourts indexes; many plaints do not expose plot numbers online.",
                "impact_on_assessment": "Absence of a matching case does NOT prove absence of pending or past litigation.",
                "remedy_action": "Conduct physical civil court index inspection at District Court / Sub-Divisional Court.",
                "is_blocking": False,
            })

        # -----------------------------------------------------------------
        # 4. CADASTRAL & SPATIAL CONSISTENCY (P1-03, P2-04)
        # -----------------------------------------------------------------
        overlay_analysis = db.query(BoundaryOverlayAnalysis).filter(
            BoundaryOverlayAnalysis.parcel_id == parcel.parcel_id,
        ).order_by(BoundaryOverlayAnalysis.created_at.desc()).first()

        if overlay_analysis:
            det = overlay_analysis.detailed_metrics or {}
            crs_declared = (overlay_analysis.analysis_crs or "").strip().upper()

            # Source-Aware Spatial Validation Gate
            if not crs_declared or crs_declared in ("UNKNOWN", "NONE", ""):
                evidence_gaps.append({
                    "subsystem": "CADASTRAL_SPATIAL",
                    "gap_code": "GAP-SPA-UNKNOWN-CRS",
                    "description": "Cadastral vector overlay is missing spatial reference system (CRS). Coordinates cannot be projected reliably.",
                    "impact_on_assessment": "Spatial overlay cannot be reliably verified without confirmed CRS.",
                    "remedy_action": "Specify declared source CRS (e.g. EPSG:32645, EPSG:32644, or EPSG:4326).",
                    "is_blocking": True,
                })
            elif (
                overlay_analysis.discrepancy_taxonomy == "CONTRADICTORY_METADATA"
                or det.get("contradictory_crs_metadata")
            ):
                evidence_gaps.append({
                    "subsystem": "CADASTRAL_SPATIAL",
                    "gap_code": "GAP-SPA-CONTRADICTORY-METADATA",
                    "description": f"Cadastral dataset coordinates contradict declared CRS metadata ('{crs_declared}').",
                    "impact_on_assessment": "Coordinate ranges or axis ordering conflict with declared projection.",
                    "remedy_action": "Verify coordinate units (degrees vs meters) and axis ordering (Easting/Northing vs Lat/Lon).",
                    "is_blocking": True,
                })
            elif (
                overlay_analysis.discrepancy_taxonomy == "INVALID_GEOMETRY"
                or det.get("geometry_invalid")
            ):
                evidence_gaps.append({
                    "subsystem": "CADASTRAL_SPATIAL",
                    "gap_code": "GAP-SPA-INVALID-GEOMETRY",
                    "description": "Boundary polygon is topologically invalid (self-intersecting or non-closed ring).",
                    "impact_on_assessment": "Geometric metrics (area, IoU, centroid shift) cannot be computed on invalid geometries.",
                    "remedy_action": "Repair polygon topology using ST_MakeValid or boundary clean-up.",
                    "is_blocking": True,
                })
            elif overlay_analysis.discrepancy_taxonomy in (
                "INSUFFICIENT_SPATIAL_REFERENCE",
                "INSUFFICIENT_ACCURACY_INFORMATION",
            ):
                evidence_gaps.append({
                    "subsystem": "CADASTRAL_SPATIAL",
                    "gap_code": "GAP-SPA-INSUFFICIENT-REFERENCE",
                    "description": f"Cadastral overlay has insufficient georeferencing accuracy: {overlay_analysis.discrepancy_taxonomy}.",
                    "impact_on_assessment": "Spatial overlay cannot be reliably verified without adequate reference information.",
                    "remedy_action": "Georeference cadastral sheet with ground control points and explicit CRS transformation.",
                    "is_blocking": True,
                })
            elif crs_declared not in RECOGNIZED_REGIONAL_CRSS:
                evidence_gaps.append({
                    "subsystem": "CADASTRAL_SPATIAL",
                    "gap_code": "GAP-SPA-UNKNOWN-CRS",
                    "description": f"Declared CRS '{crs_declared}' is not a recognized regional projection for Bihar / India.",
                    "impact_on_assessment": "Projection distortion or coordinate mismatch prevents safe cadastral overlay.",
                    "remedy_action": "Transform geometry to a recognized system (e.g. EPSG:32645, EPSG:32644, EPSG:4326, EPSG:7755).",
                    "is_blocking": True,
                })
            elif det.get("transformation_method") == "UNSUPPORTED":
                evidence_gaps.append({
                    "subsystem": "CADASTRAL_SPATIAL",
                    "gap_code": "GAP-SPA-UNSUPPORTED-TRANSFORMATION",
                    "description": "Requested georeferencing transformation method is unsupported for this cadastral sheet.",
                    "impact_on_assessment": "Transformation accuracy cannot be guaranteed.",
                    "remedy_action": "Use standard affine (6-parameter) or polynomial georeferencing transformation.",
                    "is_blocking": True,
                })
            elif det.get("gcp_count") is not None and det.get("gcp_count") < 4:
                evidence_gaps.append({
                    "subsystem": "CADASTRAL_SPATIAL",
                    "gap_code": "GAP-SPA-INSUFFICIENT-CONTROL-POINTS",
                    "description": f"Georeferencing has only {det.get('gcp_count')} ground control points (minimum 4 non-collinear GCPs required).",
                    "impact_on_assessment": "Transformation residuals cannot be verified with under-determined control points.",
                    "remedy_action": "Establish at least 4 well-distributed ground control points on village tri-junctions (sehadana).",
                    "is_blocking": True,
                })
            elif (
                det.get("checkpoint_rmse_meters") is not None
                and det.get("checkpoint_rmse_meters") > PROVISIONAL_CHECKPOINT_RMSE_THRESHOLD_METERS
            ):
                evidence_gaps.append({
                    "subsystem": "CADASTRAL_SPATIAL",
                    "gap_code": "GAP-SPA-EXCESSIVE-CHECKPOINT-ERROR",
                    "description": (
                        f"Independent check-point error ({det.get('checkpoint_rmse_meters'):.2f}m) "
                        f"exceeds provisional accuracy threshold ({PROVISIONAL_CHECKPOINT_RMSE_THRESHOLD_METERS:.2f}m)."
                    ),
                    "impact_on_assessment": "Spatial displacement exceeds acceptable cadastral boundary tolerance.",
                    "remedy_action": "Recalibrate georeferencing using verified ground survey control points.",
                    "is_blocking": True,
                })
            else:
                # Valid CRS & georeferencing
                facts.append({
                    "subsystem": "CADASTRAL_SPATIAL",
                    "fact_category": "VECTOR_OVERLAY_METROLOGY",
                    "source_reference": f"PostGIS Spatial Engine Analysis {overlay_analysis.analysis_id} (CRS: {crs_declared})",
                    "source_retrieval_date": overlay_analysis.created_at,
                    "raw_value": {
                        "crs": crs_declared,
                        "iou_score": float(overlay_analysis.iou_score) if overlay_analysis.iou_score else None,
                        "centroid_displacement_meters": float(overlay_analysis.centroid_displacement_meters) if overlay_analysis.centroid_displacement_meters else None,
                        "hausdorff_distance_meters": float(overlay_analysis.hausdorff_distance_meters) if overlay_analysis.hausdorff_distance_meters else None,
                        "discrepancy_taxonomy": overlay_analysis.discrepancy_taxonomy,
                        "severity": overlay_analysis.discrepancy_severity,
                        "transformation_method": det.get("transformation_method", "AFFINE_6_PARAM"),
                        "gcp_count": det.get("gcp_count"),
                        "checkpoint_rmse_meters": det.get("checkpoint_rmse_meters"),
                    },
                    "normalized_value": {
                        "crs": crs_declared,
                        "iou": float(overlay_analysis.iou_score) if overlay_analysis.iou_score else 0.0,
                        "centroid_shift_m": float(overlay_analysis.centroid_displacement_meters) if overlay_analysis.centroid_displacement_meters else 0.0,
                        "is_recognized_regional_crs": True,
                    },
                    "verification_status": "COMPUTED_METRIC",
                    "limitations": "Reported coordinates reflect analytical calculation precision (0.001m), which must not be conflated with physical ground accuracy (cadastral chain survey tolerance ±1-3m).",
                })

                # Spatial validation gate: check IoU and centroid displacement
                if overlay_analysis.discrepancy_severity in ("HIGH", "CRITICAL") or (overlay_analysis.iou_score and overlay_analysis.iou_score < 0.70):
                    findings.append({
                        "dimension": RiskDimension.CADASTRAL_SPATIAL,
                        "finding_code": f"FIND-SPA-{overlay_analysis.discrepancy_taxonomy or 'OVERLAY-SHIFT'}",
                        "severity": FindingSeverity.HIGH if overlay_analysis.discrepancy_severity == "HIGH" else FindingSeverity.CRITICAL,
                        "title": f"Cadastral Boundary Discrepancy: {overlay_analysis.discrepancy_taxonomy}",
                        "description": (
                            f"Spatial overlay between historical cadastral sheet and modern parcel shows significant variance. "
                            f"IoU: {overlay_analysis.iou_score:.2f}, Centroid displacement: {overlay_analysis.centroid_displacement_meters:.1f}m. "
                            f"{overlay_analysis.findings_summary or ''}"
                        ),
                        "supporting_evidence": {
                            "crs": crs_declared,
                            "iou": float(overlay_analysis.iou_score) if overlay_analysis.iou_score else None,
                            "shift_meters": float(overlay_analysis.centroid_displacement_meters) if overlay_analysis.centroid_displacement_meters else None,
                        },
                        "recommended_action": "Depute LandAmin for DGPS ground boundary demarcation.",
                        "requires_human_review": True,
                    })
        else:
            evidence_gaps.append({
                "subsystem": "CADASTRAL_SPATIAL",
                "gap_code": "GAP-SPA-NO-OVERLAY",
                "description": "Cadastral vector overlay analysis has not been performed for this parcel.",
                "impact_on_assessment": "Boundary encroachment or historical survey alignment risks cannot be evaluated.",
                "remedy_action": "Upload georeferenced cadastral survey sheet and trigger vector overlay analysis.",
                "is_blocking": False,
            })

        # -----------------------------------------------------------------
        # 5. FIELD AMIN VERIFICATION & POSSESSION (P1-04)
        # -----------------------------------------------------------------
        field_survey = db.query(FieldSurvey).filter(
            FieldSurvey.parcel_id == parcel.parcel_id,
        ).order_by(FieldSurvey.created_at.desc()).first()

        if field_survey:
            amin_ident = getattr(field_survey, "amin_user_id", None) or getattr(field_survey, "surveyor_party_id", "UNKNOWN")
            gps_count = getattr(field_survey, "gps_reading_count", None)
            facts.append({
                "subsystem": "FIELD_SURVEY",
                "fact_category": "GROUND_POSSESSION_OBSERVATION",
                "source_reference": f"Field Survey {field_survey.survey_id} by Amin {amin_ident}",
                "source_retrieval_date": field_survey.created_at,
                "applicable_date": field_survey.created_at,
                "raw_value": {
                    "measured_area": float(field_survey.measured_area_acres) if field_survey.measured_area_acres else None,
                    "possessor": field_survey.physical_possessor_name,
                    "road_access": field_survey.road_access_type,
                    "gps_points_count": gps_count,
                },
                "normalized_value": {
                    "possessor_name": field_survey.physical_possessor_name,
                    "measured_area_acres": float(field_survey.measured_area_acres) if field_survey.measured_area_acres else 0.0,
                },
                "verification_status": "FIELD_RECORDED",
                "limitations": "Field observations reflect on-ground inspection at visit time; does not adjudicate legal rights.",
            })

            # Check for area variance: Recorded area vs Ground measured area
            if parcel.recorded_area_acres and field_survey.measured_area_acres:
                rec_a = float(parcel.recorded_area_acres)
                meas_a = float(field_survey.measured_area_acres)
                delta = abs(meas_a - rec_a)
                pct = (delta / rec_a) * 100.0 if rec_a > 0 else 0.0

                inferences.append({
                    "rule_id": "RULE-SPA-AREA-VARIANCE",
                    "rule_version": "v1.0",
                    "input_evidence_ids": [str(parcel.parcel_id), str(field_survey.survey_id)],
                    "inference_category": "AREA_VARIANCE_CALCULATION",
                    "explanation": f"Recorded area ({rec_a:.3f} acres) vs Field measured area ({meas_a:.3f} acres). Variance: {pct:.1f}%.",
                    "confidence_score": 0.85,
                    "uncertainty_representation": {"variance_pct": pct, "delta_acres": delta},
                    "review_status": InferenceReviewStatus.AUTOMATED_VALIDATED,
                })

                if pct > 10.0:
                    findings.append({
                        "dimension": RiskDimension.BOUNDARY_FIELD,
                        "finding_code": "FIND-FLD-AREA-VARIANCE-EXCEEDED",
                        "severity": FindingSeverity.HIGH if pct > 20.0 else FindingSeverity.MEDIUM,
                        "title": f"Area Discrepancy Exceeds Tolerance ({pct:.1f}%)",
                        "description": (
                            f"Ground measured area ({meas_a:.3f} acres) deviates from revenue recorded area ({rec_a:.3f} acres) "
                            f"by {pct:.1f}% ({delta:.3f} acres difference)."
                        ),
                        "supporting_evidence": {"recorded_area": rec_a, "measured_area": meas_a, "variance_pct": pct},
                        "recommended_action": "Joint demarcation survey with boundary land owners.",
                        "requires_human_review": True,
                    })

            # Check physical possessor vs recorded raiyat
            if field_survey.physical_possessor_name and raiyat_name:
                possessor_clean = field_survey.physical_possessor_name.strip().lower()
                raiyat_clean = raiyat_name.strip().lower()
                if possessor_clean not in raiyat_clean and raiyat_clean not in possessor_clean:
                    findings.append({
                        "dimension": RiskDimension.BOUNDARY_FIELD,
                        "finding_code": "FIND-FLD-ADVERSE-POSSESSION-RISK",
                        "severity": FindingSeverity.HIGH,
                        "title": "Physical Possessor Differs from Recorded Raiyat",
                        "description": (
                            f"On-ground possessor reported by LandAmin is '{field_survey.physical_possessor_name}', "
                            f"which does not match recorded revenue owner '{raiyat_name}'."
                        ),
                        "supporting_evidence": {
                            "observed_possessor": field_survey.physical_possessor_name,
                            "recorded_raiyat": raiyat_name,
                        },
                        "recommended_action": "Investigate basis of possession (tenancy, unregistered sale, or adverse possession).",
                        "requires_human_review": True,
                    })
        else:
            evidence_gaps.append({
                "subsystem": "FIELD_SURVEY",
                "gap_code": "GAP-FLD-NO-SURVEY",
                "description": "No LandAmin ground survey or GPS verification has been conducted for this parcel.",
                "impact_on_assessment": "Physical possession, actual road access, and ground encroachment remain unverified.",
                "remedy_action": "Schedule LandAmin field verification task.",
                "is_blocking": False,
            })

        # -----------------------------------------------------------------
        # 6. VALUATION & APPLICABLE CHARGES (P2-03)
        # -----------------------------------------------------------------
        valuations = db.query(PropertyValuation).filter(
            PropertyValuation.parcel_id == parcel.parcel_id,
        ).all()

        if valuations:
            has_admitted_val = False
            for val in valuations:
                sched = db.query(MVRSchedule).filter(MVRSchedule.schedule_id == val.schedule_id).first()
                sched_ver = sched.verification_status if sched else "UNVERIFIED"

                # Upstream validation gate: Synthetic data handling
                source_prov = (getattr(sched, "source_provider", "") or "").upper() if sched else ""
                is_synthetic = (
                    (sched_ver in ("SYNTHETIC", "SYNTHETIC_MOCK", "SYNTHETIC_FIXTURE"))
                    or (sched and source_prov in ("MOCK_PROVIDER", "SYNTHETIC_MOCK", "SYNTHETIC_FIXTURE"))
                    or (sched and "MOCK" in source_prov)
                    or (sched and "SYNTH" in source_prov)
                    or ("mock" in (sched.schedule_code.lower() if sched else ""))
                    or ("synth" in (sched.schedule_code.lower() if sched else ""))
                )
                if is_synthetic and not include_synthetic_fixtures:
                    evidence_gaps.append({
                        "subsystem": "VALUATION",
                        "gap_code": "GAP-VAL-SYNTHETIC-DATA-EXCLUDED",
                        "description": f"MVR valuation schedule '{sched.schedule_code if sched else 'UNKNOWN'}' is synthetic and excluded from production assessment.",
                        "impact_on_assessment": "Valuation relies on synthetic fixtures; official published Collectorate schedule required.",
                        "remedy_action": "Import verified official MVR circle rate schedule for this mauza.",
                        "is_blocking": True,
                    })
                    continue  # Exclude synthetic fixture from production assessment per rule 6B

                has_admitted_val = True
                facts.append({
                    "subsystem": "VALUATION",
                    "fact_category": "MVR_VALUATION_RECORD",
                    "source_reference": f"District Collectorate MVR Schedule {sched.schedule_code if sched else 'UNKNOWN'}",
                    "source_retrieval_date": val.valuation_date,
                    "applicable_date": sched.effective_from if sched else None,
                    "raw_value": {
                        "circle_rate": float(val.unit_circle_rate),
                        "govt_valuation": float(val.total_government_valuation),
                        "assessment_base": float(val.assessment_base),
                        "total_statutory_charges": float(val.total_statutory_charges),
                        "discrepancy_status": val.discrepancy_status,
                    },
                    "normalized_value": {
                        "unit_rate_dec": float(val.unit_circle_rate),
                        "govt_value": float(val.total_government_valuation),
                        "duty_amount": float(val.stamp_duty_amount),
                    },
                    "verification_status": sched_ver,
                    "limitations": "Estimates based on published MVR schedules; final assessment by Sub-Registrar under Section 47-A.",
                })

                if val.discrepancy_status == "POTENTIAL_UNDERVALUE":
                    findings.append({
                        "dimension": RiskDimension.VALUATION_STATUTORY,
                        "finding_code": "FIND-VAL-STAMP-DUTY-UNDERVALUE",
                        "severity": FindingSeverity.MEDIUM,
                        "title": "Declared Consideration Below Minimum Government Valuation",
                        "description": (
                            f"Declared consideration is lower than guideline circle rate valuation by "
                            f"Rs. {val.discrepancy_amount:,.2f} ({val.discrepancy_percentage:.1f}%). "
                            "Triggers minimum assessment base rules under Section 47-A to prevent duty shortfall."
                        ),
                        "supporting_evidence": {
                            "declared": float(val.declared_transaction_consideration) if val.declared_transaction_consideration else 0.0,
                            "govt_valuation": float(val.total_government_valuation),
                        },
                        "recommended_action": "Structure deed consideration at or above government assessment base to avoid penalty.",
                        "requires_human_review": False,
                    })

            if not has_admitted_val and not any(g["gap_code"] == "GAP-VAL-SYNTHETIC-DATA-EXCLUDED" for g in evidence_gaps):
                evidence_gaps.append({
                    "subsystem": "VALUATION",
                    "gap_code": "GAP-VAL-NO-ASSESSMENT",
                    "description": "No official MVR circle rate valuation has been calculated for this parcel.",
                    "impact_on_assessment": "Statutory stamp duty, registration fee, and undervaluation risks cannot be estimated.",
                    "remedy_action": "Trigger MVR valuation calculation using property and road category.",
                    "is_blocking": False,
                })
        else:
            evidence_gaps.append({
                "subsystem": "VALUATION",
                "gap_code": "GAP-VAL-NO-ASSESSMENT",
                "description": "No official MVR circle rate valuation has been calculated for this parcel.",
                "impact_on_assessment": "Statutory stamp duty, registration fee, and undervaluation risks cannot be estimated.",
                "remedy_action": "Trigger MVR valuation calculation using property and road category.",
                "is_blocking": False,
            })

        # -----------------------------------------------------------------
        # 7. DOCUMENT AUTHENTICITY & EXTRACTION (P1-02, P2-01)
        # -----------------------------------------------------------------
        documents = db.query(Document).filter(
            Document.org_id == org_id,
        ).all()
        # Filter documents linked to this parcel or case
        relevant_docs = [d for d in documents if d.parcel_id == parcel.parcel_id or (case and d.case_id == case.case_id)]

        if relevant_docs:
            for doc in relevant_docs:
                fields = db.query(ExtractedField).filter(ExtractedField.document_id == doc.document_id).all()
                low_conf_fields = [f for f in fields if f.confidence_score is not None and f.confidence_score < 0.70]

                doc_verification = "OPERATOR_SUPPLIED"
                if doc.processing_status != "CONFIRMED":
                    doc_verification = "UNVERIFIED_EXTRACTION"

                facts.append({
                    "subsystem": "OCR_DOCUMENT",
                    "fact_category": "INGESTED_LEGAL_DOCUMENT",
                    "source_reference": f"Document {doc.document_id} ({doc.original_filename})",
                    "source_retrieval_date": doc.created_at,
                    "raw_value": {
                        "category": doc.category,
                        "filename": doc.original_filename,
                        "status": doc.processing_status,
                        "low_confidence_fields_count": len(low_conf_fields),
                    },
                    "normalized_value": {"doc_category": doc.category},
                    "verification_status": doc_verification,
                    "limitations": "Raw OCR extractions are unverified until human review confirms deed schedules."
                })

                if low_conf_fields:
                    findings.append({
                        "dimension": RiskDimension.DOCUMENT_AUTHENTICITY,
                        "finding_code": "FIND-DOC-UNCERTAIN-OCR-EXTRACTION",
                        "severity": FindingSeverity.MEDIUM,
                        "title": f"Uncertain OCR Extractions in {doc.original_filename}",
                        "description": f"{len(low_conf_fields)} extracted fields have confidence < 0.70 and require manual verification.",
                        "supporting_evidence": {"document_id": str(doc.document_id), "count": len(low_conf_fields)},
                        "recommended_action": "Verify deed party names and plot numbers in Document OCR viewer.",
                        "requires_human_review": True,
                    })
        else:
            evidence_gaps.append({
                "subsystem": "OCR_DOCUMENT",
                "gap_code": "GAP-DOC-NO-CERTIFIED-DEEDS",
                "description": "No certified registered deeds or Khatiyan documents uploaded for this parcel.",
                "impact_on_assessment": "Chauhaddi boundary recitals and deed encumbrance covenants remain unverified.",
                "remedy_action": "Upload certified registered deed or Khatiyan sheet.",
                "is_blocking": False,
            })

        # Summary of reconciliation
        summary = {
            "total_facts_extracted": len(facts),
            "total_inferences_derived": len(inferences),
            "total_findings_generated": len(findings),
            "total_evidence_gaps_identified": len(evidence_gaps),
            "reconciled_at": now_utc.isoformat(),
        }

        return {
            "facts": facts,
            "inferences": inferences,
            "findings": findings,
            "evidence_gaps": evidence_gaps,
            "reconciliation_summary": summary,
        }
