import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models.user import User, UserRole
from app.models.report import LandIntelligenceReport
from app.core.dependencies import get_current_user, require_roles
from app.core.exceptions import EntityNotFoundError, CrossTenantAccessError
from app.schemas.report import (
    ReportGenerateRequest,
    ReportResponse,
    ReportVerificationResponse
)
from app.services.report_service import (
    generate_and_store_report,
    get_report_by_id,
    get_report_pdf_bytes,
    verify_report_by_token
)

router = APIRouter(prefix="/reports", tags=["Land Intelligence Reports"])

def _build_report_response(report: LandIntelligenceReport) -> ReportResponse:
    base_url = settings.PUBLIC_BASE_URL.rstrip("/")
    return ReportResponse(
        report_id=report.report_id,
        org_id=report.org_id,
        case_id=report.case_id,
        parcel_id=report.parcel_id,
        report_number=report.report_number,
        version_number=report.version_number,
        status=report.status,
        sha256_hash=report.sha256_hash,
        file_size_bytes=report.file_size_bytes,
        page_count=report.page_count,
        created_at=report.created_at,
        download_url=f"/api/v1/reports/{report.report_id}/download",
        verification_url=f"{base_url}/api/v1/reports/verify/{report.verification_token}",
        summary_counts=report.summary_counts or {}
    )

@router.post("/generate", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def generate_report(
    request: ReportGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.CASE_OPERATOR, UserRole.LEGAL_REVIEWER))
):
    """
    Generates a new, versioned Land Intelligence Report PDF consolidating P1-01 through P1-04 evidence.
    """
    report = generate_and_store_report(db, request, current_user)
    return _build_report_response(report)

@router.get("", response_model=List[ReportResponse])
def list_reports(
    case_id: Optional[uuid.UUID] = None,
    parcel_id: Optional[uuid.UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists Land Intelligence Reports generated within the caller's organization.
    """
    query = db.query(LandIntelligenceReport).filter(LandIntelligenceReport.org_id == current_user.org_id)
    if case_id:
        query = query.filter(LandIntelligenceReport.case_id == case_id)
    if parcel_id:
        query = query.filter(LandIntelligenceReport.parcel_id == parcel_id)
    if status_filter:
        query = query.filter(LandIntelligenceReport.status == status_filter.upper())

    reports = query.order_by(LandIntelligenceReport.created_at.desc()).offset(offset).limit(limit).all()
    return [_build_report_response(r) for r in reports]

@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves metadata for a specific Land Intelligence Report.
    """
    report = get_report_by_id(db, report_id, current_user)
    return _build_report_response(report)

@router.get("/{report_id}/download")
def download_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Securely downloads the generated PDF report. Enforces organization/tenant authorization.
    """
    pdf_bytes, filename = get_report_pdf_bytes(db, report_id, current_user)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/pdf"
        }
    )

@router.get("/verify/{verification_token}", response_model=ReportVerificationResponse)
def verify_report(
    verification_token: str,
    db: Session = Depends(get_db)
):
    """
    Public QR code verification endpoint.
    Confirms cryptographic report integrity and authenticity without leaking confidential owner dossier.
    """
    return verify_report_by_token(db, verification_token)
