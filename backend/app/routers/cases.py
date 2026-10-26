import uuid
import random
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.case import Case, CaseStatus, TransactionReadinessState, CaseParcel
from app.models.parcel import Parcel
from app.models.evidence import Evidence, CaseEvidence
from app.models.claim import Claim
from app.models.finding import Finding
from app.core.dependencies import get_current_user, require_roles
from app.core.exceptions import EntityNotFoundError, CrossTenantAccessError
from app.schemas.case import CaseCreateRequest, CaseUpdateRequest, CaseTransitionRequest, CaseParcelAddRequest, CaseResponse
from app.schemas.evidence import CaseEvidenceAddRequest, EvidenceResponse
from app.schemas.claim import ClaimResponse
from app.schemas.finding import FindingResponse
from app.services.case_service import transition_case_status, associate_parcel_to_case

router = APIRouter(prefix="/cases", tags=["Cases"])

def _build_case_response(case: Case, db: Session) -> CaseResponse:
    parcels = db.query(CaseParcel).filter(CaseParcel.case_id == case.case_id).all()
    parcel_ids = [str(cp.parcel_id) for cp in parcels]
    return CaseResponse(
        case_id=str(case.case_id),
        org_id=str(case.org_id),
        case_number=case.case_number,
        primary_client_party_id=str(case.primary_client_party_id),
        assigned_amin_id=str(case.assigned_amin_id) if case.assigned_amin_id else None,
        assigned_advocate_id=str(case.assigned_advocate_id) if case.assigned_advocate_id else None,
        status=case.status,
        transaction_readiness_state=case.transaction_readiness_state,
        target_transaction_id=str(case.target_transaction_id) if case.target_transaction_id else None,
        linked_parcel_ids=parcel_ids
    )

@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    request: CaseCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case_number = f"BS-JH-2026-{random.randint(10000, 99999)}"
    new_case = Case(
        org_id=current_user.org_id,
        case_number=case_number,
        primary_client_party_id=uuid.UUID(request.primary_client_party_id),
        status=CaseStatus.DRAFT,
        transaction_readiness_state=TransactionReadinessState.NOT_READY
    )
    db.add(new_case)
    db.flush()

    if request.initial_parcel_id:
        associate_parcel_to_case(db, new_case, uuid.UUID(request.initial_parcel_id), is_primary=True)

    db.commit()
    db.refresh(new_case)
    return _build_case_response(new_case, db)

@router.get("", response_model=List[CaseResponse])
def list_cases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cases = db.query(Case).filter(Case.org_id == current_user.org_id).all()
    return [_build_case_response(c, db) for c in cases]

@router.get("/{case_id}", response_model=CaseResponse)
def get_case(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise EntityNotFoundError("Case", case_id)
    
    if case.org_id != current_user.org_id:
        raise CrossTenantAccessError("Access to case belonging to another tenant is denied.")

    return _build_case_response(case, db)

@router.patch("/{case_id}", response_model=CaseResponse)
def update_case(
    case_id: uuid.UUID,
    request: CaseUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise EntityNotFoundError("Case", case_id)
    if case.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    if request.assigned_amin_id is not None:
        case.assigned_amin_id = uuid.UUID(request.assigned_amin_id) if request.assigned_amin_id else None
    if request.assigned_advocate_id is not None:
        case.assigned_advocate_id = uuid.UUID(request.assigned_advocate_id) if request.assigned_advocate_id else None

    db.commit()
    db.refresh(case)
    return _build_case_response(case, db)

@router.post("/{case_id}/transition", response_model=CaseResponse)
def transition_case(
    case_id: uuid.UUID,
    request: CaseTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise EntityNotFoundError("Case", case_id)
    if case.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    updated = transition_case_status(
        db=db,
        case=case,
        next_status=request.next_status,
        actor_party_id=current_user.party_id if hasattr(current_user, 'party_id') else None,
        reason=request.transition_reason
    )
    return _build_case_response(updated, db)

@router.post("/{case_id}/parcels", status_code=status.HTTP_201_CREATED)
def add_parcel_to_case(
    case_id: uuid.UUID,
    request: CaseParcelAddRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise EntityNotFoundError("Case", case_id)
    if case.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    associate_parcel_to_case(db, case, uuid.UUID(request.parcel_id), is_primary=request.is_primary)
    return {"message": "Parcel associated to case successfully.", "case_id": str(case_id), "parcel_id": request.parcel_id}

@router.post("/{case_id}/evidence", status_code=status.HTTP_201_CREATED)
def attach_evidence_to_case(
    case_id: uuid.UUID,
    request: CaseEvidenceAddRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise EntityNotFoundError("Case", case_id)
    if case.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    ev_uuid = uuid.UUID(request.evidence_id)
    evidence = db.query(Evidence).filter(Evidence.evidence_id == ev_uuid).first()
    if not evidence:
        raise EntityNotFoundError("Evidence", ev_uuid)

    existing = db.query(CaseEvidence).filter(
        CaseEvidence.case_id == case_id,
        CaseEvidence.evidence_id == ev_uuid
    ).first()

    if not existing:
        assoc = CaseEvidence(case_id=case_id, evidence_id=ev_uuid)
        db.add(assoc)
        db.commit()

    return {"message": "Evidence attached to case successfully.", "case_id": str(case_id), "evidence_id": str(ev_uuid)}

@router.get("/{case_id}/claims", response_model=List[ClaimResponse])
def get_case_claims(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise EntityNotFoundError("Case", case_id)
    if case.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    claims = db.query(Claim).filter(Claim.case_id == case_id).all()
    return [
        ClaimResponse(
            claim_id=str(c.claim_id),
            case_id=str(c.case_id),
            parcel_id=str(c.parcel_id),
            evidence_id=str(c.evidence_id),
            subject_entity_type=c.subject_entity_type,
            subject_id=str(c.subject_id),
            predicate=c.predicate,
            object_value=c.object_value,
            authority_tier=c.authority_tier,
            confidence_score=c.confidence_score,
            observed_at=c.observed_at,
            recorded_at=c.recorded_at,
            effective_from=c.effective_from,
            effective_to=c.effective_to,
            status=c.status
        )
        for c in claims
    ]

@router.get("/{case_id}/findings", response_model=List[FindingResponse])
def get_case_findings(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise EntityNotFoundError("Case", case_id)
    if case.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    findings = db.query(Finding).filter(Finding.case_id == case_id).all()
    return [
        FindingResponse(
            finding_id=str(f.finding_id),
            case_id=str(f.case_id),
            parcel_id=str(f.parcel_id),
            rule_id=f.rule_id,
            severity=f.severity,
            status=f.status,
            observed_values=f.observed_values,
            explanation=f.explanation,
            recommended_action=f.recommended_action
        )
        for f in findings
    ]
