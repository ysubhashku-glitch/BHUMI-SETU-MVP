"""
Property Passport Synthesis and Land Risk Intelligence API Router (TASK-P2-06).

Provides REST endpoints for:
- Generating explainable parcel assessments across all 8 intelligence dimensions
- Retrieving versioned assessments and assessment history
- Inspecting observed facts, derived inferences, review findings, and evidence gaps
- Submitting findings for human review and recording authorized reviewer decisions
- Recomputing assessments when new evidence is available
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.core.dependencies import get_current_user, require_roles
from app.schemas.passport_synthesis import (
    PassportAssessmentResponse,
    PassportAssessmentDetailResponse,
    FindingResponse,
    EvidenceGapResponse,
    GenerateAssessmentRequest,
    FindingReviewRequest,
    AssessmentRecomputeRequest,
)
from app.services.passport.synthesis_service import PassportSynthesisService

router = APIRouter(prefix="/passport", tags=["Property Passport Synthesis"])


@router.post(
    "/parcels/{parcel_id}/assess",
    response_model=PassportAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate explainable Property Passport synthesis assessment for a parcel",
)
def generate_parcel_assessment(
    parcel_id: uuid.UUID,
    request: GenerateAssessmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.CASE_OPERATOR, UserRole.REVIEWER])),
):
    """
    Consolidates evidence from revenue records, cadastral overlay, OCR/Kaithi,
    field survey, judicial dockets, MVR valuation, and mutation history.
    Produces a versioned, explainable assessment with dimension scores and audit hashes.
    """
    service = PassportSynthesisService(db)
    try:
        return service.generate_assessment(
            parcel_id=parcel_id,
            org_id=current_user.org_id,
            request=request,
            generated_by_user_id=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/assessments/{assessment_id}",
    response_model=PassportAssessmentDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve detailed Property Passport assessment by ID",
)
def get_assessment_detail(
    assessment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PassportSynthesisService(db)
    assessment = service.get_assessment(assessment_id=assessment_id, org_id=current_user.org_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment '{assessment_id}' not found.",
        )
    return assessment


@router.get(
    "/parcels/{parcel_id}/assessments",
    response_model=List[PassportAssessmentResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve assessment version history for a parcel",
)
def list_assessments_for_parcel(
    parcel_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PassportSynthesisService(db)
    return service.list_assessments_for_parcel(parcel_id=parcel_id, org_id=current_user.org_id)


@router.get(
    "/assessments/{assessment_id}/findings",
    response_model=List[FindingResponse],
    status_code=status.HTTP_200_OK,
    summary="List review findings for an assessment",
)
def list_assessment_findings(
    assessment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PassportSynthesisService(db)
    try:
        return service.list_findings(assessment_id=assessment_id, org_id=current_user.org_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/assessments/{assessment_id}/gaps",
    response_model=List[EvidenceGapResponse],
    status_code=status.HTTP_200_OK,
    summary="List unresolved evidence gaps for an assessment",
)
def list_assessment_evidence_gaps(
    assessment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PassportSynthesisService(db)
    try:
        return service.list_evidence_gaps(assessment_id=assessment_id, org_id=current_user.org_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/findings/{finding_id}/submit-review",
    response_model=FindingResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit a finding for human reviewer inspection",
)
def submit_finding_for_review(
    finding_id: uuid.UUID,
    notes: str = Query(..., description="Reason for requesting human review"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.CASE_OPERATOR, UserRole.REVIEWER])),
):
    service = PassportSynthesisService(db)
    try:
        return service.submit_finding_for_review(
            finding_id=finding_id,
            org_id=current_user.org_id,
            user_id=current_user.user_id,
            notes=notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/findings/{finding_id}/review",
    response_model=FindingResponse,
    status_code=status.HTTP_200_OK,
    summary="Record authorized reviewer decision on an assessment finding",
)
def record_finding_review(
    finding_id: uuid.UUID,
    request: FindingReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.LEGAL_REVIEWER, UserRole.REVIEWER])),
):
    service = PassportSynthesisService(db)
    try:
        return service.record_finding_review(
            finding_id=finding_id,
            org_id=current_user.org_id,
            user_id=current_user.user_id,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/assessments/{assessment_id}/recompute",
    response_model=PassportAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Recompute an assessment after new evidence arrives (creates new version, supersedes old)",
)
def recompute_assessment(
    assessment_id: uuid.UUID,
    request: AssessmentRecomputeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.REVIEWER])),
):
    service = PassportSynthesisService(db)
    try:
        return service.recompute_assessment(
            assessment_id=assessment_id,
            org_id=current_user.org_id,
            user_id=current_user.user_id,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
