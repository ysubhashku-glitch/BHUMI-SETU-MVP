"""
Judicial Risk Intelligence API Router.

Provides endpoints for searching public judicial records (District Courts and Patna High Court),
correlating candidate proceedings with land parcels, operator-assisted case ingestion,
and advocate review workflows.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.core.dependencies import get_current_user, require_roles
from app.schemas.judicial import (
    JudicialSearchQuery,
    JudicialSearchResponse,
    JudicialCaseRecord,
    ParcelJudicialMatchResponse,
    JudicialManualIngestRequest,
    JudicialMatchReviewRequest,
)
from app.services.judicial.service import JudicialService

router = APIRouter(tags=["Judicial Risk Intelligence"])
judicial_service = JudicialService()


@router.post(
    "/cases/{case_id}/judicial-search",
    response_model=JudicialSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger authorized judicial search and parcel entity resolution",
)
async def search_judicial_cases(
    case_id: uuid.UUID,
    query: JudicialSearchQuery,
    parcel_id: Optional[uuid.UUID] = Query(None, description="Optional target parcel ID to correlate"),
    provider_type: Optional[str] = Query(None, description="Provider override (MOCK, ECOURTS, OPERATOR)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Searches official court dockets (eCourts / Patna High Court) and resolves entity matches
    against the case parcel(s). All matches are explainable and never automatically asserted as title encumbrances.
    """
    return await judicial_service.search_and_correlate(
        db=db,
        case_id=case_id,
        parcel_id=parcel_id,
        query=query,
        current_user=current_user,
        provider_type=provider_type,
    )


@router.get(
    "/cases/{case_id}/judicial-cases",
    status_code=status.HTTP_200_OK,
    summary="Retrieve judicial risk summary and detected cases for a case",
)
def get_case_judicial_summary(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return judicial_service.get_case_judicial_summary(
        db=db,
        case_id=case_id,
        current_user=current_user,
    )


@router.get(
    "/parcels/{parcel_id}/judicial-cases",
    response_model=List[ParcelJudicialMatchResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve all candidate judicial matches for a specific parcel",
)
def get_parcel_judicial_matches(
    parcel_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return judicial_service.get_parcel_judicial_matches(
        db=db,
        parcel_id=parcel_id,
        current_user=current_user,
    )


@router.post(
    "/judicial-cases/import",
    response_model=JudicialCaseRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Operator-assisted manual ingestion of certified judicial records",
)
def import_judicial_case(
    request: JudicialManualIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.OPERATOR])),
):
    """
    Compliant operator ingestion path when automated public portal access is blocked by CAPTCHA
    or when certified advocate copies/judgments are uploaded.
    """
    return judicial_service.manual_ingest_case(
        db=db,
        request=request,
        current_user=current_user,
    )


@router.post(
    "/judicial-matches/{match_id}/review",
    response_model=ParcelJudicialMatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Record advocate or operator review decision on candidate judicial match",
)
def review_judicial_match(
    match_id: uuid.UUID,
    review_request: JudicialMatchReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.ANALYST])),
):
    """
    Records an advocate's review decision (VERIFIED_ASSOCIATED, DISMISSED_UNRELATED, INSUFFICIENT_EVIDENCE)
    with audit timestamps without modifying the underlying raw source docket.
    """
    return judicial_service.review_match(
        db=db,
        match_id=match_id,
        review_request=review_request,
        current_user=current_user,
    )
