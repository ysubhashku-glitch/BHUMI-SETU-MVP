import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.finding import Finding, RequiredAction, Resolution
from app.core.dependencies import get_current_user
from app.core.exceptions import EntityNotFoundError
from app.schemas.finding import (
    FindingCreateRequest, FindingResponse,
    ActionCreateRequest, ActionResponse,
    ResolutionCreateRequest, ResolutionResponse
)
from app.services.finding_service import create_finding, create_required_action, resolve_finding

router = APIRouter(prefix="/findings", tags=["Findings"])

@router.post("", response_model=FindingResponse, status_code=status.HTTP_201_CREATED)
def create_new_finding(
    request: FindingCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case_uuid = uuid.UUID(request.case_id)
    parcel_uuid = uuid.UUID(request.parcel_id)
    
    finding = create_finding(
        db=db,
        case_id=case_uuid,
        parcel_id=parcel_uuid,
        rule_id=request.rule_id,
        severity=request.severity,
        observed_values=request.observed_values,
        explanation=request.explanation,
        recommended_action=request.recommended_action,
        org_id=current_user.org_id
    )

    return FindingResponse(
        finding_id=str(finding.finding_id),
        case_id=str(finding.case_id),
        parcel_id=str(finding.parcel_id),
        rule_id=finding.rule_id,
        severity=finding.severity,
        status=finding.status,
        observed_values=finding.observed_values,
        explanation=finding.explanation,
        recommended_action=finding.recommended_action
    )

@router.post("/{finding_id}/actions", response_model=ActionResponse, status_code=status.HTTP_201_CREATED)
def add_action_to_finding(
    finding_id: uuid.UUID,
    request: ActionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    assigned_party_uuid = uuid.UUID(request.assigned_to_party_id) if request.assigned_to_party_id else None

    action = create_required_action(
        db=db,
        finding_id=finding_id,
        action_type=request.action_type,
        assigned_role=request.assigned_role,
        assigned_to_party_id=assigned_party_uuid,
        org_id=current_user.org_id
    )

    return ActionResponse(
        action_id=str(action.action_id),
        finding_id=str(action.finding_id),
        case_id=str(action.case_id),
        action_type=action.action_type,
        assigned_role=action.assigned_role,
        assigned_to_party_id=str(action.assigned_to_party_id) if action.assigned_to_party_id else None,
        status=action.status,
        resolution_notes=action.resolution_notes,
        resolved_by_party_id=str(action.resolved_by_party_id) if action.resolved_by_party_id else None,
        resolving_evidence_id=str(action.resolving_evidence_id) if action.resolving_evidence_id else None,
        resolved_at=action.resolved_at
    )

@router.post("/{finding_id}/resolve", response_model=ResolutionResponse, status_code=status.HTTP_201_CREATED)
def resolve_finding_endpoint(
    finding_id: uuid.UUID,
    request: ResolutionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    action_uuid = uuid.UUID(request.action_id)
    evidence_uuid = uuid.UUID(request.resolving_evidence_id)
    reviewer_uuid = uuid.UUID(request.reviewer_party_id)

    resolution = resolve_finding(
        db=db,
        finding_id=finding_id,
        action_id=action_uuid,
        resolving_evidence_id=evidence_uuid,
        reviewer_party_id=reviewer_uuid,
        resolution_outcome=request.resolution_outcome,
        notes=request.notes,
        org_id=current_user.org_id
    )

    return ResolutionResponse(
        resolution_id=str(resolution.resolution_id),
        finding_id=str(resolution.finding_id),
        action_id=str(resolution.action_id),
        resolving_evidence_id=str(resolution.resolving_evidence_id),
        reviewer_party_id=str(resolution.reviewer_party_id),
        resolution_outcome=resolution.resolution_outcome,
        notes=resolution.notes,
        resolved_at=resolution.resolved_at
    )
