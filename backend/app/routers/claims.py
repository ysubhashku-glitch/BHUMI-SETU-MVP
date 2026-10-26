import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.claim import Claim, ClaimStatus
from app.models.case import Case
from app.models.parcel import Parcel
from app.models.evidence import Evidence
from app.core.dependencies import get_current_user
from app.core.exceptions import EntityNotFoundError, CrossTenantAccessError
from app.schemas.claim import ClaimCreateRequest, ClaimResponse

router = APIRouter(prefix="/claims", tags=["Claims"])

def _build_claim_response(c: Claim) -> ClaimResponse:
    return ClaimResponse(
        claim_id=str(c.claim_id),
        case_id=str(c.case_id),
        parcel_id=str(c.parcel_id),
        evidence_id=str(c.evidence_id),
        subject_entity_type=c.subject_entity_type,
        subject_id=str(c.subject_id),
        predicate=c.predicate,
        object_value=c.object_value,
        authority_tier=c.authority_tier,
        confidence_score=float(c.confidence_score),
        observed_at=c.observed_at,
        recorded_at=c.recorded_at,
        effective_from=c.effective_from,
        effective_to=c.effective_to,
        status=c.status
    )

@router.post("", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
def create_claim(
    request: ClaimCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case_uuid = uuid.UUID(request.case_id)
    parcel_uuid = uuid.UUID(request.parcel_id)
    evidence_uuid = uuid.UUID(request.evidence_id)
    subject_uuid = uuid.UUID(request.subject_id)

    case = db.query(Case).filter(Case.case_id == case_uuid).first()
    if not case:
        raise EntityNotFoundError("Case", case_uuid)
    if case.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    parcel = db.query(Parcel).filter(Parcel.parcel_id == parcel_uuid).first()
    if not parcel:
        raise EntityNotFoundError("Parcel", parcel_uuid)

    evidence = db.query(Evidence).filter(Evidence.evidence_id == evidence_uuid).first()
    if not evidence:
        raise EntityNotFoundError("Evidence", evidence_uuid)

    claim = Claim(
        case_id=case_uuid,
        parcel_id=parcel_uuid,
        evidence_id=evidence_uuid,
        subject_entity_type=request.subject_entity_type,
        subject_id=subject_uuid,
        predicate=request.predicate,
        object_value=request.object_value,
        authority_tier=request.authority_tier,
        confidence_score=request.confidence_score,
        recorded_at=request.recorded_at,
        effective_from=request.effective_from,
        effective_to=request.effective_to,
        status=request.status
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return _build_claim_response(claim)
