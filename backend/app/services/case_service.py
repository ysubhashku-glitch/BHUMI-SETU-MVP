import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.case import Case, CaseStatus, TransactionReadinessState, CaseParcel
from app.models.parcel import Parcel
from app.models.audit import AuditLog
from app.core.exceptions import StateTransitionError, EntityNotFoundError

# Allowed State Machine Transitions
VALID_TRANSITIONS = {
    CaseStatus.DRAFT: [CaseStatus.PROPERTY_IDENTIFIED, CaseStatus.CANCELLED],
    CaseStatus.PROPERTY_IDENTIFIED: [CaseStatus.DATA_COLLECTION, CaseStatus.BLOCKED, CaseStatus.CANCELLED],
    CaseStatus.DATA_COLLECTION: [CaseStatus.DOCUMENT_COLLECTION, CaseStatus.DATA_UNAVAILABLE, CaseStatus.CANCELLED],
    CaseStatus.DOCUMENT_COLLECTION: [CaseStatus.PROCESSING, CaseStatus.DATA_UNAVAILABLE, CaseStatus.CANCELLED],
    CaseStatus.PROCESSING: [CaseStatus.ANALYSIS, CaseStatus.CONFLICTING_DATA, CaseStatus.CANCELLED],
    CaseStatus.ANALYSIS: [CaseStatus.VERIFICATION_REQUIRED, CaseStatus.LEGAL_REVIEW, CaseStatus.CONFLICTING_DATA, CaseStatus.CANCELLED],
    CaseStatus.VERIFICATION_REQUIRED: [CaseStatus.FIELD_VERIFICATION, CaseStatus.BLOCKED, CaseStatus.CANCELLED],
    CaseStatus.FIELD_VERIFICATION: [CaseStatus.LEGAL_REVIEW, CaseStatus.BLOCKED, CaseStatus.CANCELLED],
    CaseStatus.LEGAL_REVIEW: [CaseStatus.REPORT_DRAFT, CaseStatus.BLOCKED, CaseStatus.CANCELLED],
    CaseStatus.REPORT_DRAFT: [CaseStatus.REPORT_REVIEW, CaseStatus.CANCELLED],
    CaseStatus.REPORT_REVIEW: [CaseStatus.FINAL, CaseStatus.LEGAL_REVIEW, CaseStatus.CANCELLED],
    CaseStatus.FINAL: [],  # Terminal
    CaseStatus.BLOCKED: [CaseStatus.LEGAL_REVIEW, CaseStatus.CANCELLED],
    CaseStatus.DATA_UNAVAILABLE: [CaseStatus.DATA_COLLECTION, CaseStatus.CANCELLED],
    CaseStatus.CONFLICTING_DATA: [CaseStatus.ANALYSIS, CaseStatus.CANCELLED],
    CaseStatus.CANCELLED: []  # Terminal
}

def transition_case_status(
    db: Session,
    case: Case,
    next_status: str,
    actor_party_id: Optional[uuid.UUID] = None,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None
) -> Case:
    current_status = case.status
    allowed_next_states = VALID_TRANSITIONS.get(current_status, [])
    
    if next_status not in allowed_next_states:
        raise StateTransitionError(
            current_state=current_status,
            attempted_state=next_status,
            reason=f"Valid next states from '{current_status}' are: {', '.join(allowed_next_states) if allowed_next_states else 'None (Terminal state)'}"
        )
    
    # Specific Domain Pre-condition Checks
    if next_status == CaseStatus.PROPERTY_IDENTIFIED:
        # Must have at least one parcel associated
        parcel_count = db.query(CaseParcel).filter(CaseParcel.case_id == case.case_id).count()
        if parcel_count == 0:
            raise StateTransitionError(
                current_state=current_status,
                attempted_state=next_status,
                reason="Cannot transition to PROPERTY_IDENTIFIED without at least one associated parcel."
            )

    previous_state = {"status": current_status, "transaction_readiness_state": case.transaction_readiness_state}
    case.status = next_status
    
    if next_status == CaseStatus.BLOCKED:
        case.transaction_readiness_state = TransactionReadinessState.BLOCKED_STATUTORY_HAZARD
    
    new_state = {"status": next_status, "transaction_readiness_state": case.transaction_readiness_state, "reason": reason}
    
    # Audit trail logging
    audit = AuditLog(
        org_id=case.org_id,
        actor_party_id=actor_party_id,
        action="CASE_STATUS_TRANSITION",
        entity_name="CASE",
        entity_id=case.case_id,
        previous_state=previous_state,
        new_state=new_state,
        ip_address=ip_address
    )
    db.add(audit)
    db.commit()
    db.refresh(case)
    return case

def associate_parcel_to_case(
    db: Session,
    case: Case,
    parcel_id: uuid.UUID,
    is_primary: bool = True
) -> CaseParcel:
    parcel = db.query(Parcel).filter(Parcel.parcel_id == parcel_id).first()
    if not parcel:
        raise EntityNotFoundError("Parcel", parcel_id)
    
    existing = db.query(CaseParcel).filter(
        CaseParcel.case_id == case.case_id,
        CaseParcel.parcel_id == parcel_id
    ).first()
    
    if existing:
        return existing
    
    case_parcel = CaseParcel(case_id=case.case_id, parcel_id=parcel_id, is_primary=is_primary)
    db.add(case_parcel)
    db.commit()
    db.refresh(case_parcel)
    return case_parcel
