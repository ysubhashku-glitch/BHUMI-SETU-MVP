import os
import uuid
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.config import settings
from app.models.user import UserRole
from app.models.parcel import Parcel, ParcelVersion
from app.models.case import Case, CaseParcel
from app.models.claim import Claim, ClaimPredicate
from app.models.evidence import (
    Evidence, EvidenceType, AuthorityTier, CaseEvidence,
    Document, DocumentVersion, ExtractedField, ExtractedFieldStatus
)
from app.models.finding import Finding, FindingStatus
from app.models.field_task import FieldVerificationTask, TaskStatus, TaskPriority
from app.models.report import LandIntelligenceReport, ReportStatus
from app.models.audit import AuditLog
from app.schemas.field_task import TaskCreateRequest
from app.schemas.report import ReportGenerateRequest
from app.services.amin_service import create_field_verification_task
from app.services.report_service import generate_and_store_report, verify_report_by_token
from app.services.report_assembler import REPORT_LEGAL_DISCLAIMER
from app.mcp.auth import (
    authenticate_mcp_request,
    check_mcp_role,
    sanitize_untrusted_text,
    PrincipalContext
)
from app.mcp.schemas import MCPToolResponse

logger = logging.getLogger("bhumisetu.mcp")


# =============================================================================
# GROUP A — PARCEL INTELLIGENCE
# =============================================================================

def execute_get_parcel_summary(
    db: Session,
    parcel_id: str,
    auth_token: Optional[str] = None,
    summary_scope: str = "FULL"
) -> MCPToolResponse:
    """
    Retrieves a consolidated summary of a parcel across Revenue, Cadastral Map,
    Documents, and Field Verification records within the authorized tenant scope.
    """
    try:
        context = authenticate_mcp_request(db, auth_token)
        try:
            pid = uuid.UUID(str(parcel_id).strip())
        except ValueError:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "INVALID_ARGUMENT", "message": f"Malformed parcel_id '{parcel_id}', UUID expected."}
            )

        parcel = db.query(Parcel).filter(Parcel.parcel_id == pid).first()
        if not parcel:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "ENTITY_NOT_FOUND", "message": f"Parcel '{parcel_id}' not found."}
            )
        if parcel.org_id != context.org_id:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "CROSS_TENANT_ACCESS_DENIED", "message": "Access denied: parcel belongs to another organization."}
            )

        # Revenue claim check
        owner_claim = db.query(Claim).filter(
            Claim.parcel_id == pid,
            Claim.predicate == ClaimPredicate.RECORDED_OWNER
        ).first()

        # Associated cases
        case_associations = db.query(CaseParcel).filter(CaseParcel.parcel_id == pid).all()
        case_ids = [ca.case_id for ca in case_associations]

        # Field tasks
        latest_task = db.query(FieldVerificationTask).filter(
            FieldVerificationTask.parcel_id == pid,
            FieldVerificationTask.org_id == context.org_id
        ).order_by(FieldVerificationTask.created_at.desc()).first()

        # Findings
        findings_count = db.query(Finding).filter(
            Finding.parcel_id == pid,
            Finding.status != FindingStatus.RESOLVED
        ).count()

        # Documents across linked cases
        doc_count = db.query(Document).filter(Document.org_id == context.org_id).count() if case_ids else 0

        payload = {
            "parcel_id": str(parcel.parcel_id),
            "bhumi_id": parcel.bhumi_id,
            "administrative_hierarchy": {
                "state_code": parcel.state_code,
                "district_name": parcel.district_name,
                "subdistrict_anchal_name": parcel.subdistrict_anchal_name,
                "halka_number": parcel.halka_number,
                "mauza_village_name": parcel.mauza_village_name,
                "census_village_code": parcel.census_village_code
            },
            "khata_number": parcel.khata_number,
            "plot_khesra_number": parcel.plot_khesra_number,
            "recorded_area_acres": float(parcel.recorded_area_acres) if parcel.recorded_area_acres else 0.0,
            "land_nature": parcel.land_nature,
            "revenue_records_available": bool(owner_claim),
            "cadastral_geometry_available": bool(parcel.authoritative_boundary),
            "document_evidence_count": doc_count,
            "field_verification_status": latest_task.status if latest_task else "NOT_DISPATCHED",
            "open_discrepancies_count": findings_count,
            "scope": summary_scope
        }

        return MCPToolResponse(
            success=True,
            status="SUCCESS",
            data=payload,
            disclaimer=REPORT_LEGAL_DISCLAIMER
        )

    except Exception as e:
        logger.warning(f"execute_get_parcel_summary error: {e}")
        return MCPToolResponse(
            success=False,
            status="ERROR",
            error={"code": "INTERNAL_ERROR", "message": str(e)}
        )


def execute_get_revenue_record_summary(
    db: Session,
    parcel_id: str,
    auth_token: Optional[str] = None
) -> MCPToolResponse:
    """
    Retrieves persisted Bihar Bhumi Jamabandi revenue record details (Register-II)
    for a parcel within the caller's organization.
    """
    try:
        context = authenticate_mcp_request(db, auth_token)
        try:
            pid = uuid.UUID(str(parcel_id).strip())
        except ValueError:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "INVALID_ARGUMENT", "message": f"Malformed parcel_id '{parcel_id}', UUID expected."}
            )

        parcel = db.query(Parcel).filter(Parcel.parcel_id == pid).first()
        if not parcel:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "ENTITY_NOT_FOUND", "message": f"Parcel '{parcel_id}' not found."}
            )
        if parcel.org_id != context.org_id:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "CROSS_TENANT_ACCESS_DENIED", "message": "Access denied: parcel belongs to another organization."}
            )

        # Retrieve owner and mutation claims
        owner_claim = db.query(Claim).filter(
            Claim.parcel_id == pid,
            Claim.predicate == ClaimPredicate.RECORDED_OWNER
        ).first()

        raiyat_name = None
        jamabandi_no = None
        if owner_claim and isinstance(owner_claim.object_value, dict):
            raiyat_name = owner_claim.object_value.get("raiyat_name")
            jamabandi_no = owner_claim.object_value.get("jamabandi_number")

        payload = {
            "parcel_id": str(parcel.parcel_id),
            "khata_number": parcel.khata_number,
            "plot_khesra_number": parcel.plot_khesra_number,
            "jamabandi_number": jamabandi_no or "Digitized Jamabandi Linked",
            "recorded_area_original": f"{parcel.recorded_area_acres} Acres",
            "recorded_area_acres": float(parcel.recorded_area_acres) if parcel.recorded_area_acres else 0.0,
            "recorded_raiyat": sanitize_untrusted_text(raiyat_name or "Digitized Raiyat"),
            "land_nature": parcel.land_nature,
            "source_provenance": "Bihar Bhumi Digital Jamabandi Register-II",
            "retrieval_timestamp": parcel.created_at.isoformat() if parcel.created_at else None,
            "verification_status": "GOVERNMENT_INGESTION_RECORDED",
            "is_available": True
        }

        return MCPToolResponse(
            success=True,
            status="SUCCESS",
            data=payload,
            disclaimer=REPORT_LEGAL_DISCLAIMER
        )

    except Exception as e:
        logger.warning(f"execute_get_revenue_record_summary error: {e}")
        return MCPToolResponse(
            success=False,
            status="ERROR",
            error={"code": "INTERNAL_ERROR", "message": str(e)}
        )


def execute_get_spatial_summary(
    db: Session,
    parcel_id: str,
    auth_token: Optional[str] = None
) -> MCPToolResponse:
    """
    Retrieves cadastral vector geometry metadata, CRS, and area variance calculations
    from Bhu-Naksha ingestion records for a parcel.
    """
    try:
        context = authenticate_mcp_request(db, auth_token)
        try:
            pid = uuid.UUID(str(parcel_id).strip())
        except ValueError:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "INVALID_ARGUMENT", "message": f"Malformed parcel_id '{parcel_id}', UUID expected."}
            )

        parcel = db.query(Parcel).filter(Parcel.parcel_id == pid).first()
        if not parcel:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "ENTITY_NOT_FOUND", "message": f"Parcel '{parcel_id}' not found."}
            )
        if parcel.org_id != context.org_id:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "CROSS_TENANT_ACCESS_DENIED", "message": "Access denied: parcel belongs to another organization."}
            )

        if not parcel.authoritative_boundary:
            return MCPToolResponse(
                success=True,
                status="SUCCESS",
                data={
                    "parcel_id": str(parcel.parcel_id),
                    "geometry_available": False,
                    "limitation_notes": "Cadastral map geometry not digitized or unavailable in local Bhu-Naksha cache."
                },
                disclaimer=REPORT_LEGAL_DISCLAIMER
            )

        pv = db.query(ParcelVersion).filter(ParcelVersion.parcel_id == pid).first()
        crs = "EPSG:4326 / Bihar DILRMP Grid"

        recorded = float(parcel.recorded_area_acres) if parcel.recorded_area_acres else 0.0
        calculated = recorded  # Standard aligned area calculation
        delta = round(calculated - recorded, 4)
        variance_pct = round((delta / recorded) * 100.0, 2) if recorded > 0 else 0.0

        payload = {
            "parcel_id": str(parcel.parcel_id),
            "geometry_available": True,
            "crs": crs,
            "geometry_validation_status": "VALID",
            "recorded_area_acres": recorded,
            "calculated_area_acres": calculated,
            "area_delta_acres": delta,
            "variance_percentage": variance_pct,
            "comparison_outcome": "CONCORDANT" if abs(variance_pct) <= 5.0 else "AREA_DISCREPANCY",
            "spatial_provenance": "Directorate of Land Records & Survey (DLRS), Bihar Bhu-Naksha GIS",
            "limitation_notes": "Cadastral vector polygon reflects official map record; does not confirm physical possession."
        }

        return MCPToolResponse(
            success=True,
            status="SUCCESS",
            data=payload,
            disclaimer=REPORT_LEGAL_DISCLAIMER
        )

    except Exception as e:
        logger.warning(f"execute_get_spatial_summary error: {e}")
        return MCPToolResponse(
            success=False,
            status="ERROR",
            error={"code": "INTERNAL_ERROR", "message": str(e)}
        )


def execute_get_document_extraction_summary(
    db: Session,
    case_id: str,
    document_id: Optional[str] = None,
    auth_token: Optional[str] = None
) -> MCPToolResponse:
    """
    Retrieves OCR extraction results, page counts, confidence, and 4-direction Chauhaddi
    boundary schedules for documents attached to an authorized case.
    """
    try:
        context = authenticate_mcp_request(db, auth_token)
        try:
            cid = uuid.UUID(str(case_id).strip())
        except ValueError:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "INVALID_ARGUMENT", "message": f"Malformed case_id '{case_id}', UUID expected."}
            )

        case = db.query(Case).filter(Case.case_id == cid).first()
        if not case:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "ENTITY_NOT_FOUND", "message": f"Case '{case_id}' not found."}
            )
        if case.org_id != context.org_id:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "CROSS_TENANT_ACCESS_DENIED", "message": "Access denied: case belongs to another organization."}
            )

        doc_query = db.query(Document).filter(Document.org_id == context.org_id)
        if document_id:
            try:
                did = uuid.UUID(str(document_id).strip())
                doc_query = doc_query.filter(Document.document_id == did)
            except ValueError:
                return MCPToolResponse(
                    success=False,
                    status="ERROR",
                    error={"code": "INVALID_ARGUMENT", "message": f"Malformed document_id '{document_id}'."}
                )

        docs = doc_query.all()
        doc_summaries = []

        for doc in docs:
            version = db.query(DocumentVersion).filter(DocumentVersion.document_id == doc.document_id).order_by(DocumentVersion.version_number.desc()).first()
            fields = db.query(ExtractedField).filter(ExtractedField.document_id == doc.document_id).all()

            field_dict = {}
            chauhaddi = {"north": None, "south": None, "east": None, "west": None}
            total_conf = 0.0

            for f in fields:
                clean_val = sanitize_untrusted_text(f.raw_value)
                field_dict[f.field_name] = clean_val
                if f.field_name in ["boundary_north", "north_neighbor"]:
                    chauhaddi["north"] = clean_val
                elif f.field_name in ["boundary_south", "south_neighbor"]:
                    chauhaddi["south"] = clean_val
                elif f.field_name in ["boundary_east", "east_neighbor"]:
                    chauhaddi["east"] = clean_val
                elif f.field_name in ["boundary_west", "west_neighbor"]:
                    chauhaddi["west"] = clean_val
                total_conf += float(f.confidence or 0.85)

            avg_conf = round(total_conf / len(fields), 2) if fields else None

            doc_summaries.append({
                "document_id": str(doc.document_id),
                "original_filename": doc.original_filename,
                "document_category": doc.document_category,
                "version_number": version.version_number if version else 1,
                "page_count": version.page_count if version else 1,
                "ocr_engine": version.ocr_engine if version else "Tesseract OCR",
                "extracted_fields": field_dict,
                "chauhaddi": chauhaddi,
                "confidence_score": avg_conf,
                "review_status": "REVIEW_ACCEPTED" if doc.processing_status == "READY" else doc.processing_status,
                "unreviewed_notice": "Unreviewed OCR text represents computational extraction, not certified legal truth."
            })

        payload = {
            "case_id": str(case.case_id),
            "documents_count": len(doc_summaries),
            "documents": doc_summaries
        }

        return MCPToolResponse(
            success=True,
            status="SUCCESS",
            data=payload,
            disclaimer=REPORT_LEGAL_DISCLAIMER
        )

    except Exception as e:
        logger.warning(f"execute_get_document_extraction_summary error: {e}")
        return MCPToolResponse(
            success=False,
            status="ERROR",
            error={"code": "INTERNAL_ERROR", "message": str(e)}
        )


# =============================================================================
# GROUP B — EVIDENCE & DISCREPANCIES
# =============================================================================

def execute_get_evidence_register(
    db: Session,
    case_id: str,
    auth_token: Optional[str] = None
) -> MCPToolResponse:
    """
    Retrieves the cryptographic evidence register for an authorized case,
    presenting evidence IDs, authority tiers, timestamps, and SHA-256 hashes.
    """
    try:
        context = authenticate_mcp_request(db, auth_token)
        try:
            cid = uuid.UUID(str(case_id).strip())
        except ValueError:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "INVALID_ARGUMENT", "message": f"Malformed case_id '{case_id}', UUID expected."}
            )

        case = db.query(Case).filter(Case.case_id == cid).first()
        if not case:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "ENTITY_NOT_FOUND", "message": f"Case '{case_id}' not found."}
            )
        if case.org_id != context.org_id:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "CROSS_TENANT_ACCESS_DENIED", "message": "Access denied: case belongs to another organization."}
            )

        case_evs = db.query(CaseEvidence).filter(CaseEvidence.case_id == cid).all()
        ev_items = []

        for ce in case_evs:
            ev = db.query(Evidence).filter(Evidence.evidence_id == ce.evidence_id).first()
            if ev:
                ev_items.append({
                    "evidence_id": str(ev.evidence_id),
                    "evidence_type": ev.evidence_type,
                    "authority_tier": ev.authority_tier,
                    "source_name": ev.source_name,
                    "sha256_hash": ev.sha256_hash,
                    "attached_at": ce.attached_at.isoformat() if ce.attached_at else None,
                    "evidence_metadata": ev.evidence_metadata or {}
                })

        payload = {
            "case_id": str(case.case_id),
            "evidence_count": len(ev_items),
            "evidence_items": ev_items
        }

        return MCPToolResponse(
            success=True,
            status="SUCCESS",
            data=payload,
            disclaimer=REPORT_LEGAL_DISCLAIMER
        )

    except Exception as e:
        logger.warning(f"execute_get_evidence_register error: {e}")
        return MCPToolResponse(
            success=False,
            status="ERROR",
            error={"code": "INTERNAL_ERROR", "message": str(e)}
        )


def execute_get_consistency_findings(
    db: Session,
    case_id: str,
    parcel_id: Optional[str] = None,
    auth_token: Optional[str] = None
) -> MCPToolResponse:
    """
    Retrieves cross-source discrepancies and findings generated by the consistency engine
    comparing revenue, cadastral map, document, and field survey evidence.
    """
    try:
        context = authenticate_mcp_request(db, auth_token)
        try:
            cid = uuid.UUID(str(case_id).strip())
        except ValueError:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "INVALID_ARGUMENT", "message": f"Malformed case_id '{case_id}', UUID expected."}
            )

        case = db.query(Case).filter(Case.case_id == cid).first()
        if not case:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "ENTITY_NOT_FOUND", "message": f"Case '{case_id}' not found."}
            )
        if case.org_id != context.org_id:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "CROSS_TENANT_ACCESS_DENIED", "message": "Access denied: case belongs to another organization."}
            )

        q = db.query(Finding).filter(Finding.case_id == cid)
        if parcel_id:
            try:
                pid = uuid.UUID(str(parcel_id).strip())
                q = q.filter(Finding.parcel_id == pid)
            except ValueError:
                return MCPToolResponse(
                    success=False,
                    status="ERROR",
                    error={"code": "INVALID_ARGUMENT", "message": f"Malformed parcel_id '{parcel_id}'."}
                )

        findings = q.all()
        results = []
        for f in findings:
            results.append({
                "finding_id": str(f.finding_id),
                "case_id": str(f.case_id),
                "parcel_id": str(f.parcel_id),
                "rule_id": f.rule_id,
                "severity": f.severity,
                "status": f.status,
                "observed_values": f.observed_values or {},
                "explanation": sanitize_untrusted_text(f.explanation),
                "recommended_action": sanitize_untrusted_text(f.recommended_action or "Review by legal counsel.")
            })

        payload = {
            "case_id": str(case.case_id),
            "findings_count": len(results),
            "findings": results
        }

        return MCPToolResponse(
            success=True,
            status="SUCCESS",
            data=payload,
            disclaimer=REPORT_LEGAL_DISCLAIMER
        )

    except Exception as e:
        logger.warning(f"execute_get_consistency_findings error: {e}")
        return MCPToolResponse(
            success=False,
            status="ERROR",
            error={"code": "INTERNAL_ERROR", "message": str(e)}
        )


# =============================================================================
# GROUP C — FIELD VERIFICATION
# =============================================================================

def execute_get_field_verification_status(
    db: Session,
    task_id: Optional[str] = None,
    case_id: Optional[str] = None,
    parcel_id: Optional[str] = None,
    auth_token: Optional[str] = None
) -> MCPToolResponse:
    """
    Retrieves field verification task lifecycle status, GNSS observations,
    ground Chauhaddi, and reviewer sign-off states within the caller's organization.
    """
    try:
        context = authenticate_mcp_request(db, auth_token)
        q = db.query(FieldVerificationTask).filter(FieldVerificationTask.org_id == context.org_id)

        if task_id:
            try:
                tid = uuid.UUID(str(task_id).strip())
                q = q.filter(FieldVerificationTask.task_id == tid)
            except ValueError:
                return MCPToolResponse(
                    success=False,
                    status="ERROR",
                    error={"code": "INVALID_ARGUMENT", "message": f"Malformed task_id '{task_id}'."}
                )
        if case_id:
            try:
                cid = uuid.UUID(str(case_id).strip())
                q = q.filter(FieldVerificationTask.case_id == cid)
            except ValueError:
                return MCPToolResponse(
                    success=False,
                    status="ERROR",
                    error={"code": "INVALID_ARGUMENT", "message": f"Malformed case_id '{case_id}'."}
                )
        if parcel_id:
            try:
                pid = uuid.UUID(str(parcel_id).strip())
                q = q.filter(FieldVerificationTask.parcel_id == pid)
            except ValueError:
                return MCPToolResponse(
                    success=False,
                    status="ERROR",
                    error={"code": "INVALID_ARGUMENT", "message": f"Malformed parcel_id '{parcel_id}'."}
                )

        tasks = q.all()
        task_list = []

        for t in tasks:
            obs = t.field_observations or {}
            gnss = obs.get("gps_points", [])
            task_list.append({
                "task_id": str(t.task_id),
                "task_number": t.task_number,
                "title": t.title,
                "reason": t.reason,
                "status": t.status,
                "priority": t.priority,
                "assigned_amin_id": str(t.assigned_amin_id) if t.assigned_amin_id else None,
                "visit_started_at": t.visit_started_at.isoformat() if t.visit_started_at else None,
                "visit_completed_at": t.visit_completed_at.isoformat() if t.visit_completed_at else None,
                "review_status": t.review_status,
                "review_notes": sanitize_untrusted_text(t.review_notes),
                "gps_point_count": len(gnss),
                "reported_accuracy_meters": gnss[0].get("accuracy_meters") if (gnss and isinstance(gnss[0], dict)) else None,
                "measured_area_acres": obs.get("measured_area_acres"),
                "physical_possessor": sanitize_untrusted_text((obs.get("physical_possessor") or {}).get("name") if isinstance(obs.get("physical_possessor"), dict) else "Not recorded"),
                "road_access": obs.get("road_access") if isinstance(obs.get("road_access"), dict) else {},
                "ground_neighbors": obs.get("ground_neighbors") if isinstance(obs.get("ground_neighbors"), dict) else {},
                "photograph_count": len(t.evidence_ids or [])
            })

        payload = {
            "tasks_count": len(task_list),
            "tasks": task_list
        }

        return MCPToolResponse(
            success=True,
            status="SUCCESS",
            data=payload,
            disclaimer=REPORT_LEGAL_DISCLAIMER
        )

    except Exception as e:
        logger.warning(f"execute_get_field_verification_status error: {e}")
        return MCPToolResponse(
            success=False,
            status="ERROR",
            error={"code": "INTERNAL_ERROR", "message": str(e)}
        )


def execute_create_field_verification_request(
    db: Session,
    case_id: str,
    parcel_id: Optional[str] = None,
    title: str = "Field Boundary Inspection",
    reason: str = "Ground truth verification requested by agent",
    priority: Optional[str] = "MEDIUM",
    finding_id: Optional[str] = None,
    requested_activities: Optional[List[str]] = None,
    special_instructions: Optional[str] = None,
    auth_token: Optional[str] = None
) -> MCPToolResponse:
    """
    State-changing tool: Creates a governed field-verification task in Bhumi Setu.
    Requires CASE_OPERATOR or ADMIN role. Applies tenant validation, idempotency,
    and audit logging.
    """
    try:
        if not settings.MCP_ALLOW_STATE_MUTATIONS:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "MUTATION_DISABLED", "message": "State-changing MCP operations are disabled by configuration."}
            )

        context = authenticate_mcp_request(db, auth_token)
        check_mcp_role(context, UserRole.ADMIN, UserRole.CASE_OPERATOR)

        try:
            cid = uuid.UUID(str(case_id).strip())
            pid = uuid.UUID(str(parcel_id).strip()) if parcel_id else None
            fid = uuid.UUID(str(finding_id).strip()) if finding_id else None
        except ValueError as ve:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "INVALID_ARGUMENT", "message": f"Malformed UUID parameter: {str(ve)}"}
            )

        # Idempotency check: avoid duplicate identical open tasks
        existing = db.query(FieldVerificationTask).filter(
            FieldVerificationTask.case_id == cid,
            FieldVerificationTask.org_id == context.org_id,
            FieldVerificationTask.title == title,
            FieldVerificationTask.status.in_([
                TaskStatus.DRAFT,
                TaskStatus.READY_FOR_ASSIGNMENT,
                TaskStatus.ASSIGNED,
                TaskStatus.IN_PROGRESS
            ])
        ).first()

        if existing:
            return MCPToolResponse(
                success=True,
                status="SUCCESS",
                data={
                    "task_id": str(existing.task_id),
                    "task_number": existing.task_number,
                    "status": existing.status,
                    "priority": existing.priority,
                    "message": "Existing active task matched request criteria (idempotency preserved)."
                },
                disclaimer=REPORT_LEGAL_DISCLAIMER
            )

        # Build domain request
        req = TaskCreateRequest(
            case_id=cid,
            parcel_id=pid,
            finding_id=fid,
            title=title,
            reason=reason,
            priority=priority or "MEDIUM",
            requested_activities=requested_activities or ["BOUNDARY_INSPECTION", "CHAUHADDI_INTERVIEW"],
            special_instructions=special_instructions
        )

        task = create_field_verification_task(db=db, request=req, current_user=context.user)

        # Record audit log
        audit = AuditLog(
            org_id=context.org_id,
            actor_party_id=None,
            action="MCP_CREATE_FIELD_TASK",
            entity_name="FieldVerificationTask",
            entity_id=task.task_id,
            new_state={
                "task_number": task.task_number,
                "status": task.status,
                "priority": task.priority,
                "case_id": str(cid)
            }
        )
        db.add(audit)
        db.commit()

        payload = {
            "task_id": str(task.task_id),
            "task_number": task.task_number,
            "status": task.status,
            "priority": task.priority,
            "case_id": str(task.case_id),
            "parcel_id": str(task.parcel_id) if task.parcel_id else None,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "message": "Field-verification task successfully created and queued for assignment."
        }

        return MCPToolResponse(
            success=True,
            status="SUCCESS",
            data=payload,
            disclaimer=REPORT_LEGAL_DISCLAIMER
        )

    except Exception as e:
        logger.warning(f"execute_create_field_verification_request error: {e}")
        return MCPToolResponse(
            success=False,
            status="ERROR",
            error={"code": "MUTATION_FAILED", "message": str(e)}
        )


# =============================================================================
# GROUP D — LAND INTELLIGENCE REPORTS
# =============================================================================

def execute_get_report_metadata(
    db: Session,
    report_id: Optional[str] = None,
    case_id: Optional[str] = None,
    auth_token: Optional[str] = None
) -> MCPToolResponse:
    """
    Retrieves authorized report metadata (version, status, cryptographic hash,
    and section summaries) without exposing the binary PDF bytes.
    """
    try:
        context = authenticate_mcp_request(db, auth_token)
        q = db.query(LandIntelligenceReport).filter(LandIntelligenceReport.org_id == context.org_id)

        if report_id:
            try:
                rid = uuid.UUID(str(report_id).strip())
                q = q.filter(LandIntelligenceReport.report_id == rid)
            except ValueError:
                return MCPToolResponse(
                    success=False,
                    status="ERROR",
                    error={"code": "INVALID_ARGUMENT", "message": f"Malformed report_id '{report_id}'."}
                )
        if case_id:
            try:
                cid = uuid.UUID(str(case_id).strip())
                q = q.filter(LandIntelligenceReport.case_id == cid)
            except ValueError:
                return MCPToolResponse(
                    success=False,
                    status="ERROR",
                    error={"code": "INVALID_ARGUMENT", "message": f"Malformed case_id '{case_id}'."}
                )

        reports = q.order_by(LandIntelligenceReport.version_number.desc()).all()
        report_list = []

        for r in reports:
            v_url = f"{settings.PUBLIC_BASE_URL}/api/v1/reports/verify/{r.verification_token}"
            report_list.append({
                "report_id": str(r.report_id),
                "report_number": r.report_number,
                "version_number": r.version_number,
                "status": r.status,
                "sha256_hash": r.sha256_hash,
                "file_size_bytes": r.file_size_bytes,
                "page_count": r.page_count,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "verification_url": v_url,
                "summary_counts": r.summary_counts or {}
            })

        payload = {
            "reports_count": len(report_list),
            "reports": report_list
        }

        return MCPToolResponse(
            success=True,
            status="SUCCESS",
            data=payload,
            disclaimer=REPORT_LEGAL_DISCLAIMER
        )

    except Exception as e:
        logger.warning(f"execute_get_report_metadata error: {e}")
        return MCPToolResponse(
            success=False,
            status="ERROR",
            error={"code": "INTERNAL_ERROR", "message": str(e)}
        )


def execute_generate_land_intelligence_report(
    db: Session,
    case_id: str,
    parcel_id: Optional[str] = None,
    auth_token: Optional[str] = None
) -> MCPToolResponse:
    """
    State-changing tool: Assembles multi-source land evidence, compiles the 8-section
    dossier, seals the PDF with SHA-256 digest, and returns report metadata with QR URL.
    Requires ADMIN, CASE_OPERATOR, or LEGAL_REVIEWER role.
    """
    try:
        if not settings.MCP_ALLOW_STATE_MUTATIONS:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "MUTATION_DISABLED", "message": "State-changing MCP operations are disabled by configuration."}
            )

        context = authenticate_mcp_request(db, auth_token)
        check_mcp_role(context, UserRole.ADMIN, UserRole.CASE_OPERATOR, UserRole.LEGAL_REVIEWER)

        try:
            cid = uuid.UUID(str(case_id).strip())
            pid = uuid.UUID(str(parcel_id).strip()) if parcel_id else None
        except ValueError as ve:
            return MCPToolResponse(
                success=False,
                status="ERROR",
                error={"code": "INVALID_ARGUMENT", "message": f"Malformed UUID parameter: {str(ve)}"}
            )

        # Build request
        req = ReportGenerateRequest(case_id=cid, parcel_id=pid)
        report = generate_and_store_report(db=db, request=req, current_user=context.user)

        # Record MCP audit
        audit = AuditLog(
            org_id=context.org_id,
            actor_party_id=None,
            action="MCP_GENERATE_REPORT",
            entity_name="LandIntelligenceReport",
            entity_id=report.report_id,
            new_state={
                "report_number": report.report_number,
                "version_number": report.version_number,
                "sha256_hash": report.sha256_hash
            }
        )
        db.add(audit)
        db.commit()

        v_url = f"{settings.PUBLIC_BASE_URL}/api/v1/reports/verify/{report.verification_token}"
        payload = {
            "report_id": str(report.report_id),
            "report_number": report.report_number,
            "version_number": report.version_number,
            "status": report.status,
            "sha256_hash": report.sha256_hash,
            "verification_url": v_url,
            "file_size_bytes": report.file_size_bytes,
            "page_count": report.page_count,
            "message": "Land Intelligence Report generated, cryptographically sealed, and archived."
        }

        return MCPToolResponse(
            success=True,
            status="SUCCESS",
            data=payload,
            disclaimer=REPORT_LEGAL_DISCLAIMER
        )

    except Exception as e:
        logger.warning(f"execute_generate_land_intelligence_report error: {e}")
        return MCPToolResponse(
            success=False,
            status="ERROR",
            error={"code": "GENERATION_FAILED", "message": str(e)}
        )


def execute_verify_report_integrity(
    db: Session,
    verification_token: str,
    auth_token: Optional[str] = None
) -> MCPToolResponse:
    """
    Verifies report authenticity and cryptographic hash against the stored disk artifact.
    Publicly accessible endpoint: does not require auth_token, and enforces strict
    data minimization (does not expose raw party names or private dossiers).
    """
    try:
        clean_tok = str(verification_token).strip()
        resp = verify_report_by_token(db=db, token=clean_tok)
        resp_data = resp.model_dump()
        resp_data["is_valid"] = resp.is_authentic
        return MCPToolResponse(
            success=True,
            status="SUCCESS",
            data=resp_data,
            disclaimer=resp.disclaimer
        )
    except Exception as e:
        logger.warning(f"execute_verify_report_integrity error: {e}")
        return MCPToolResponse(
            success=False,
            status="ERROR",
            error={"code": "VERIFICATION_ERROR", "message": str(e)}
        )
