import uuid
from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.evidence import Evidence
from app.core.dependencies import get_current_user
from app.core.exceptions import EntityNotFoundError
from app.schemas.evidence import EvidenceCreateRequest, EvidenceResponse

router = APIRouter(prefix="/evidence", tags=["Evidence"])

def _build_evidence_response(ev: Evidence) -> EvidenceResponse:
    return EvidenceResponse(
        evidence_id=str(ev.evidence_id),
        evidence_type=ev.evidence_type,
        authority_tier=ev.authority_tier,
        source_name=ev.source_name,
        storage_uri=ev.storage_uri,
        sha256_hash=ev.sha256_hash,
        captured_by_party_id=str(ev.captured_by_party_id) if ev.captured_by_party_id else None,
        captured_at=ev.captured_at,
        evidence_metadata=ev.evidence_metadata or {}
    )

@router.post("", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
def create_evidence(
    request: EvidenceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ev = Evidence(
        evidence_type=request.evidence_type,
        authority_tier=request.authority_tier,
        source_name=request.source_name,
        storage_uri=request.storage_uri,
        sha256_hash=request.sha256_hash,
        captured_by_party_id=uuid.UUID(request.captured_by_party_id) if request.captured_by_party_id else None,
        evidence_metadata=request.metadata
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return _build_evidence_response(ev)

@router.get("/{evidence_id}", response_model=EvidenceResponse)
def get_evidence(
    evidence_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ev = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if not ev:
        raise EntityNotFoundError("Evidence", evidence_id)
    return _build_evidence_response(ev)
