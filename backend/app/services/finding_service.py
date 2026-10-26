import uuid
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.finding import Finding, RequiredAction, Resolution, FindingStatus, ActionStatus, FindingSeverity
from app.models.evidence import Evidence
from app.models.audit import AuditLog
from app.models.case import Case
from app.core.exceptions import EntityNotFoundError, DomainValidationError

def create_finding(
    db: Session,
    case_id: uuid.UUID,
    parcel_id: uuid.UUID,
    rule_id: str,
    severity: str,
    observed_values: Dict[str, Any],
    explanation: str,
    recommended_action: Optional[str] = None,
    actor_party_id: Optional[uuid.UUID] = None,
    org_id: Optional[uuid.UUID] = None
) -> Finding:
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise EntityNotFoundError("Case", case_id)
    
    resolved_org_id = org_id or case.org_id

    finding = Finding(
        case_id=case_id,
        parcel_id=parcel_id,
        rule_id=rule_id,
        severity=severity,
        status=FindingStatus.OPEN,
        observed_values=observed_values,
        explanation=explanation,
        recommended_action=recommended_action
    )
    db.add(finding)
    db.flush()

    audit = AuditLog(
        org_id=resolved_org_id,
        actor_party_id=actor_party_id,
        action="CREATE_FINDING",
        entity_name="FINDING",
        entity_id=finding.finding_id,
        previous_state=None,
        new_state={
            "rule_id": rule_id,
            "severity": severity,
            "status": FindingStatus.OPEN,
            "case_id": str(case_id),
            "parcel_id": str(parcel_id)
        }
    )
    db.add(audit)
    db.commit()
    db.refresh(finding)
    return finding

def create_required_action(
    db: Session,
    finding_id: uuid.UUID,
    action_type: str,
    assigned_role: str,
    assigned_to_party_id: Optional[uuid.UUID] = None,
    actor_party_id: Optional[uuid.UUID] = None,
    org_id: Optional[uuid.UUID] = None
) -> RequiredAction:
    finding = db.query(Finding).filter(Finding.finding_id == finding_id).first()
    if not finding:
        raise EntityNotFoundError("Finding", finding_id)
    
    case = db.query(Case).filter(Case.case_id == finding.case_id).first()
    resolved_org_id = org_id or (case.org_id if case else None)

    action = RequiredAction(
        finding_id=finding_id,
        case_id=finding.case_id,
        action_type=action_type,
        assigned_role=assigned_role,
        assigned_to_party_id=assigned_to_party_id,
        status=ActionStatus.OPEN
    )
    db.add(action)
    db.flush()

    if resolved_org_id:
        audit = AuditLog(
            org_id=resolved_org_id,
            actor_party_id=actor_party_id,
            action="CREATE_REQUIRED_ACTION",
            entity_name="REQUIRED_ACTION",
            entity_id=action.action_id,
            previous_state=None,
            new_state={
                "finding_id": str(finding_id),
                "action_type": action_type,
                "assigned_role": assigned_role,
                "status": ActionStatus.OPEN
            }
        )
        db.add(audit)

    db.commit()
    db.refresh(action)
    return action

def resolve_finding(
    db: Session,
    finding_id: uuid.UUID,
    action_id: uuid.UUID,
    resolving_evidence_id: uuid.UUID,
    reviewer_party_id: uuid.UUID,
    resolution_outcome: str,
    notes: Optional[str] = None,
    org_id: Optional[uuid.UUID] = None
) -> Resolution:
    finding = db.query(Finding).filter(Finding.finding_id == finding_id).first()
    if not finding:
        raise EntityNotFoundError("Finding", finding_id)

    action = db.query(RequiredAction).filter(
        RequiredAction.action_id == action_id,
        RequiredAction.finding_id == finding_id
    ).first()
    if not action:
        raise DomainValidationError(f"Action {action_id} not found or does not belong to Finding {finding_id}")

    # Ensure evidence exists
    evidence = db.query(Evidence).filter(Evidence.evidence_id == resolving_evidence_id).first()
    if not evidence:
        raise EntityNotFoundError("Evidence", resolving_evidence_id)

    # Update Action state
    action.status = ActionStatus.COMPLETED
    action.resolved_by_party_id = reviewer_party_id
    action.resolving_evidence_id = resolving_evidence_id
    action.resolution_notes = notes
    action.resolved_at = sa_func_now()

    # Create Resolution
    res_uuid = uuid.uuid4()
    resolution = Resolution(
        resolution_id=res_uuid,
        finding_id=finding_id,
        action_id=action_id,
        resolving_evidence_id=resolving_evidence_id,
        reviewer_party_id=reviewer_party_id,
        resolution_outcome=resolution_outcome,
        notes=notes
    )
    db.add(resolution)
    db.flush()

    # Check remaining open actions on finding
    open_actions = db.query(RequiredAction).filter(
        RequiredAction.finding_id == finding_id,
        RequiredAction.action_id != action_id,
        RequiredAction.status != ActionStatus.COMPLETED
    ).count()

    if open_actions == 0:
        finding.status = FindingStatus.RESOLVED

    case = db.query(Case).filter(Case.case_id == finding.case_id).first()
    resolved_org_id = org_id or (case.org_id if case else None)

    if resolved_org_id:
        audit = AuditLog(
            org_id=resolved_org_id,
            actor_party_id=reviewer_party_id,
            action="RESOLVE_FINDING",
            entity_name="RESOLUTION",
            entity_id=resolution.resolution_id,
            previous_state={"finding_status": finding.status},
            new_state={
                "finding_id": str(finding_id),
                "action_id": str(action_id),
                "resolving_evidence_id": str(resolving_evidence_id),
                "resolution_outcome": resolution_outcome
            }
        )
        db.add(audit)

    db.commit()
    db.refresh(resolution)
    db.refresh(finding)
    return resolution

def sa_func_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)
