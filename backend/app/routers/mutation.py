"""
Mutation Intelligence API Router (TASK-P2-05).

Provides REST endpoints for:
- Listing and querying Bihar Dakhil-Kharij mutation cases
- Operator-assisted ingestion of certified mutation dockets
- Appending cryptographic lifecycle events
- Parcel entity resolution with anti-name-only safeguards
- Operator review of candidate associations
- Property Passport chronological mutation timeline retrieval
- Mutation reconciliation runs and source health checks
"""

import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.core.dependencies import get_current_user, require_roles
from app.models.mutation import MutationStatus
from app.schemas.mutation import (
    MutationCaseResponse,
    MutationCaseDetailResponse,
    MutationManualImportRequest,
    MutationEventCreate,
    MutationEventResponse,
    MutationEntityResolutionRequest,
    MutationEntityResolutionResponse,
    MutationOperatorReviewRequest,
    PropertyPassportMutationTimelineResponse,
    MutationReconciliationRunResponse,
    MutationReconcileRequest,
)
from app.services.mutation.service import MutationService

router = APIRouter(prefix="/mutation", tags=["Mutation Intelligence"])


@router.get(
    "/cases",
    response_model=List[MutationCaseResponse],
    status_code=status.HTTP_200_OK,
    summary="List mutation cases with filtering",
)
def list_mutation_cases(
    district: Optional[str] = Query(None, description="Filter by Bihar district"),
    circle: Optional[str] = Query(None, description="Filter by Circle / Anchal"),
    mutation_status: Optional[MutationStatus] = Query(None, alias="status", description="Filter by normalized status"),
    parcel_id: Optional[uuid.UUID] = Query(None, description="Filter by linked parcel ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = MutationService(db)
    return service.list_cases(
        org_id=current_user.org_id,
        district=district,
        circle=circle,
        status=mutation_status,
        parcel_id=parcel_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/cases/{case_id}",
    response_model=MutationCaseDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get detailed mutation case with events and attached documents",
)
def get_mutation_case_detail(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = MutationService(db)
    case = service.get_case(case_id=case_id, org_id=current_user.org_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mutation case '{case_id}' not found.",
        )
    return case


@router.post(
    "/cases/import",
    response_model=MutationCaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Operator-assisted manual ingestion of certified mutation records",
)
def import_mutation_case(
    request: MutationManualImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.CASE_OPERATOR, UserRole.REVIEWER])),
):
    """
    Ingests an operator-submitted mutation record or certified order sheet.
    Preserves provenance as OPERATOR_CERTIFIED_DOCUMENT without fabricating verification.
    """
    service = MutationService(db)
    return service.import_operator_case(
        org_id=current_user.org_id,
        req=request,
        operator_user_id=current_user.user_id,
    )


@router.post(
    "/cases/{case_id}/events",
    response_model=MutationEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Append lifecycle event to mutation case ledger",
)
def add_mutation_event(
    case_id: uuid.UUID,
    event_data: MutationEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.CASE_OPERATOR, UserRole.REVIEWER])),
):
    """
    Records an immutable lifecycle event in the case ledger with SHA-256 payload hash
    and evaluates state machine transition without rolling back verified terminal states.
    """
    service = MutationService(db)
    try:
        return service.record_event(
            mutation_case_id=case_id,
            org_id=current_user.org_id,
            event_data=event_data,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/cases/{case_id}/resolve",
    response_model=MutationEntityResolutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Correlate mutation case with a cadastral parcel",
)
def resolve_mutation_entity(
    case_id: uuid.UUID,
    parcel_id: uuid.UUID = Query(..., description="Target parcel ID to correlate"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Evaluates correlation between mutation record and cadastral parcel.
    Enforces tenant isolation and anti-name-only rules.
    """
    service = MutationService(db)
    try:
        return service.resolve_parcel_association(
            mutation_case_id=case_id,
            parcel_id=parcel_id,
            org_id=current_user.org_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/resolutions/{resolution_id}/review",
    response_model=MutationEntityResolutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Record operator review on candidate mutation-parcel match",
)
def review_mutation_resolution(
    resolution_id: uuid.UUID,
    review_request: MutationOperatorReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.LEGAL_REVIEWER, UserRole.REVIEWER])),
):
    """
    Records an authorized human reviewer's confirmation or dismissal of an entity match.
    """
    service = MutationService(db)
    try:
        return service.review_resolution(
            resolution_id=resolution_id,
            org_id=current_user.org_id,
            req=review_request,
            reviewer_user_id=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/parcels/{parcel_id}/timeline",
    response_model=PropertyPassportMutationTimelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Property Passport mutation timeline for a parcel",
)
def get_property_passport_mutation_timeline(
    parcel_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the source-attributed chronological mutation timeline for the Property Passport.
    Includes statutory notice confirming mutation records do not independently prove title.
    """
    service = MutationService(db)
    return service.get_parcel_timeline(
        parcel_id=parcel_id,
        org_id=current_user.org_id,
    )


@router.post(
    "/reconcile",
    response_model=MutationReconciliationRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger mutation reconciliation run across records",
)
def trigger_mutation_reconciliation(
    request: MutationReconcileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.REVIEWER])),
):
    service = MutationService(db)
    return service.run_reconciliation(
        org_id=current_user.org_id,
        parcel_id=request.parcel_id,
        district=request.district,
        circle=request.circle,
    )


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Check mutation source adapter health",
)
async def get_mutation_source_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = MutationService(db)
    return await service.get_source_health()
