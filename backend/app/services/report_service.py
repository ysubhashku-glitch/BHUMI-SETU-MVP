import uuid
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.config import settings
from app.models.case import Case
from app.models.parcel import Parcel
from app.models.report import LandIntelligenceReport, ReportStatus
from app.models.evidence import Evidence, EvidenceType, AuthorityTier, CaseEvidence
from app.models.audit import AuditLog
from app.models.user import User, UserRole
from app.core.exceptions import EntityNotFoundError, CrossTenantAccessError, ForbiddenError, DomainValidationError
from app.core.storage import get_document_storage
from app.schemas.report import ReportGenerateRequest, ReportVerificationResponse
from app.services.report_assembler import assemble_report_data, REPORT_LEGAL_DISCLAIMER
from app.services.pdf_report_generator import generate_land_intelligence_pdf

def generate_and_store_report(
    db: Session,
    request: ReportGenerateRequest,
    current_user: User
) -> LandIntelligenceReport:
    """
    Assembles normalized evidence, renders PDF, computes SHA-256, stores in vault,
    records cryptographic report metadata and links to audit trail.
    """
    # 1. Authorize
    if current_user.role not in [UserRole.ADMIN, UserRole.CASE_OPERATOR, UserRole.LEGAL_REVIEWER]:
        raise ForbiddenError("Only dispatchers, reviewers, and administrators can generate Land Intelligence Reports.")

    case = db.query(Case).filter(Case.case_id == request.case_id).first()
    if not case:
        raise EntityNotFoundError("Case", request.case_id)
    if case.org_id != current_user.org_id:
        raise CrossTenantAccessError("Cannot generate report for a case belonging to another organization.")

    # 2. Check previous reports for versioning
    existing_reports = db.query(LandIntelligenceReport).filter(
        LandIntelligenceReport.case_id == request.case_id
    ).order_by(LandIntelligenceReport.version_number.desc()).all()

    version_number = 1
    if existing_reports:
        version_number = existing_reports[0].version_number + 1

    # 3. Generate token & assemble report data
    verification_token = secrets.token_urlsafe(32)
    report_data = assemble_report_data(
        db=db,
        case_id=request.case_id,
        parcel_id=request.parcel_id,
        current_user=current_user,
        verification_token=verification_token
    )
    report_data.section_1_cover.report_version = version_number

    # 4. Render PDF
    pdf_bytes = generate_land_intelligence_pdf(report_data)
    if not pdf_bytes or len(pdf_bytes) == 0:
        raise DomainValidationError("Failed to generate PDF report bytes.")

    # 5. Compute SHA-256
    sha256 = hashlib.sha256(pdf_bytes).hexdigest()

    # 6. Store via DocumentStorage
    storage = get_document_storage()
    filename = f"{report_data.section_1_cover.report_number}_v{version_number}.pdf"
    storage_res = storage.put(
        content=pdf_bytes,
        destination_name=filename,
        mime_type="application/pdf",
        metadata={
            "case_id": str(request.case_id),
            "report_number": report_data.section_1_cover.report_number,
            "version": version_number
        }
    )
    storage_ref = storage_res["storage_reference"]

    # 7. Create Evidence record
    evidence = Evidence(
        evidence_type=EvidenceType.LEGAL_REVIEW,
        authority_tier=AuthorityTier.AI_DERIVED,
        source_name=f"Bhumi Setu Land Intelligence Report ({report_data.section_1_cover.report_number})",
        storage_uri=storage_ref,
        sha256_hash=sha256,
        evidence_metadata={
            "report_number": report_data.section_1_cover.report_number,
            "version_number": version_number,
            "verification_token": verification_token,
            "generator_user_id": str(current_user.user_id)
        }
    )
    db.add(evidence)
    db.flush()

    case_ev = CaseEvidence(case_id=case.case_id, evidence_id=evidence.evidence_id)
    db.add(case_ev)

    # 8. Persist LandIntelligenceReport
    report = LandIntelligenceReport(
        org_id=current_user.org_id,
        case_id=request.case_id,
        parcel_id=request.parcel_id or (uuid.UUID(report_data.section_1_cover.parcel_bhumi_id) if False else None),
        report_number=report_data.section_1_cover.report_number,
        version_number=version_number,
        verification_token=verification_token,
        status=ReportStatus.GENERATED,
        sha256_hash=sha256,
        pdf_storage_uri=storage_ref,
        file_size_bytes=len(pdf_bytes),
        page_count=2,  # Typical 2-page consolidated dossier
        source_snapshots={
            "revenue_available": report_data.section_2_revenue.is_available,
            "cadastral_available": report_data.section_3_cadastral.is_available,
            "document_count": len(report_data.section_4_documents),
            "field_survey_available": report_data.section_5_field.is_available,
            "consistency_checks": len(report_data.section_6_consistency),
            "evidence_count": len(report_data.section_7_evidence),
            "findings_count": len(report_data.section_8_findings_actions)
        },
        summary_counts={
            "findings_count": len(report_data.section_8_findings_actions),
            "evidence_count": len(report_data.section_7_evidence)
        },
        generated_by_user_id=current_user.user_id
    )

    # Mark prior reports as superseded
    for prev_rep in existing_reports:
        if prev_rep.status == ReportStatus.GENERATED:
            prev_rep.status = ReportStatus.SUPERSEDED
            prev_rep.superseded_by_id = report.report_id

    db.add(report)
    db.flush()

    # 9. Audit Log
    audit = AuditLog(
        org_id=current_user.org_id,
        action="GENERATE_LAND_REPORT",
        entity_name="REPORT",
        entity_id=report.report_id,
        new_state={
            "report_number": report.report_number,
            "version_number": version_number,
            "sha256_hash": sha256,
            "generated_by": current_user.email
        }
    )
    db.add(audit)
    db.commit()
    db.refresh(report)
    return report

def get_report_by_id(db: Session, report_id: uuid.UUID, current_user: User) -> LandIntelligenceReport:
    report = db.query(LandIntelligenceReport).filter(LandIntelligenceReport.report_id == report_id).first()
    if not report:
        raise EntityNotFoundError("LandIntelligenceReport", report_id)
    if report.org_id != current_user.org_id:
        raise CrossTenantAccessError("Cannot view report belonging to another organization.")
    return report

def get_report_pdf_bytes(db: Session, report_id: uuid.UUID, current_user: User) -> Tuple[bytes, str]:
    report = get_report_by_id(db, report_id, current_user)
    storage = get_document_storage()
    content = storage.get(report.pdf_storage_uri)
    filename = f"{report.report_number}_v{report.version_number}.pdf"
    return content, filename

def verify_report_by_token(db: Session, token: str) -> ReportVerificationResponse:
    """
    Public verification endpoint logic.
    Validates token, computes cryptographic file hash from storage, and confirms tamper-evidence.
    Does NOT leak private parties or provide unrestricted PDF download.
    """
    report = db.query(LandIntelligenceReport).filter(
        LandIntelligenceReport.verification_token == token
    ).first()
    if not report:
        raise EntityNotFoundError("ReportVerificationToken", token)

    # Verify stored file against recorded SHA-256 hash
    storage = get_document_storage()
    hash_matches = False
    try:
        content = storage.get(report.pdf_storage_uri)
        current_hash = hashlib.sha256(content).hexdigest()
        hash_matches = (current_hash == report.sha256_hash)
    except Exception:
        hash_matches = False

    is_authentic = (report.status == ReportStatus.GENERATED) and hash_matches

    return ReportVerificationResponse(
        is_authentic=is_authentic,
        report_number=report.report_number,
        version_number=report.version_number,
        status=report.status,
        issued_at=report.created_at,
        sha256_hash=report.sha256_hash,
        hash_matches_stored_file=hash_matches,
        scope="Consolidated Multi-Source Land Intelligence Dossier",
        disclaimer=REPORT_LEGAL_DISCLAIMER
    )
