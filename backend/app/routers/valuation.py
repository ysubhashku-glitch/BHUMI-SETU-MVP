"""
Valuation & Stamp Duty Intelligence API Router.

Exposes endpoints for calculating government MVR guideline values,
estimating statutory stamp duty and registration fees, analyzing undervaluation risks,
and managing official circle rate schedules.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.core.dependencies import get_current_user, require_roles
from app.schemas.valuation import (
    MVRScheduleRecord,
    MVRScheduleCreateRequest,
    MVRScheduleSearchQuery,
    ValuationCalculationRequest,
    ValuationCalculationResponse,
    DiscrepancyAnalysisResult,
    MVRDistrictCoverageSummary,
    MVRScheduleVerifyRequest,
)
from app.services.valuation.service import ValuationService
from app.services.valuation.discrepancy_analyzer import ValuationDiscrepancyAnalyzer

router = APIRouter(prefix="/valuation", tags=["Valuation & Stamp Duty Intelligence"])
valuation_service = ValuationService()
discrepancy_analyzer = ValuationDiscrepancyAnalyzer()


@router.post(
    "/calculate",
    response_model=ValuationCalculationResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate government valuation, statutory stamp duty, and discrepancy analysis",
)
async def calculate_property_valuation(
    request: ValuationCalculationRequest,
    provider_type: Optional[str] = Query(None, description="Provider override (MOCK, ENIBANDHAN, OPERATOR)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Computes official MVR guideline valuation, Section 47-A assessment base,
    applicable stamp duty (with female/joint buyer concessions), registration fees,
    municipal surcharges, and undervaluation discrepancy status.
    """
    return await valuation_service.calculate_and_assess_property(
        db=db,
        request=request,
        current_user=current_user,
        provider_type=provider_type,
    )


@router.get(
    "/schedules",
    response_model=List[MVRScheduleRecord],
    status_code=status.HTTP_200_OK,
    summary="Search official MVR circle rate schedules",
)
def search_mvr_schedules(
    district: Optional[str] = Query(None, description="Bihar district name (e.g. PATNA, GAYA)"),
    anchal_circle: Optional[str] = Query(None, description="Anchal / Circle name (e.g. Danapur)"),
    mauza: Optional[str] = Query(None, description="Mauza / Village name"),
    property_category: Optional[str] = Query(None, description="AGRICULTURAL, RESIDENTIAL, COMMERCIAL, INDUSTRIAL"),
    road_category: Optional[str] = Query(None, description="MAIN_ROAD_NH_SH, PWD_ROAD, RURAL_ROAD_OR_NO_ROAD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = MVRScheduleSearchQuery(
        district=district,
        anchal_circle=anchal_circle,
        mauza=mauza,
        property_category=property_category,
        road_category=road_category,
    )
    return valuation_service.search_schedules(db=db, query=query, current_user=current_user)


@router.get(
    "/coverage",
    response_model=List[MVRDistrictCoverageSummary],
    status_code=status.HTTP_200_OK,
    summary="Retrieve Bihar district MVR coverage and data freshness status",
)
def get_district_coverage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns coverage statistics indicating which districts and anchals have
    verified circle rate schedules vs provisional or unavailable areas.
    """
    return valuation_service.get_district_coverage(db=db, current_user=current_user)


@router.post(
    "/discrepancy-analysis",
    response_model=DiscrepancyAnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Analyze undervaluation discrepancy between declared consideration and guideline valuation",
)
def analyze_valuation_discrepancy(
    government_valuation: float = Query(..., gt=0, description="Government MVR valuation in INR"),
    declared_consideration: Optional[float] = Query(None, ge=0, description="Declared sale price in deed"),
    current_user: User = Depends(get_current_user),
):
    assessment_base = max(government_valuation, declared_consideration or 0.0)
    return discrepancy_analyzer.analyze_discrepancy(
        government_valuation=government_valuation,
        declared_consideration=declared_consideration,
        assessment_base=assessment_base,
    )


@router.post(
    "/schedules/import",
    response_model=MVRScheduleRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Operator-assisted manual ingestion of official circle rate schedules",
)
def import_mvr_schedule(
    request: MVRScheduleCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.OPERATOR])),
):
    """
    Ingests and normalizes an official circle rate notification or district gazette schedule.
    """
    return valuation_service.import_schedule(db=db, request=request, current_user=current_user)


@router.post(
    "/schedules/{schedule_id}/verify",
    response_model=MVRScheduleRecord,
    status_code=status.HTTP_200_OK,
    summary="Verify or update official verification status of an MVR schedule",
)
def verify_mvr_schedule(
    schedule_id: uuid.UUID,
    verify_request: MVRScheduleVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPERVISOR])),
):
    """
    Sets schedule verification status (VERIFIED_OFFICIAL, SUPERSEDED, UNVERIFIED).
    """
    return valuation_service.verify_schedule(
        db=db,
        schedule_id=schedule_id,
        verify_request=verify_request,
        current_user=current_user,
    )
