"""
Pydantic Schemas for Bihar MVR Circle Rate and Stamp Duty Valuation Subsystem.

Defines schedule models, valuation requests, statutory charge breakdowns,
discrepancy analysis responses, and statutory disclaimers.
"""

from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, ConfigDict


STATUTORY_VALUATION_DISCLAIMER = (
    "STATUTORY VALUATION & STAMP DUTY NOTICE: Minimum Valuation Register (MVR) rates, "
    "government guideline values, stamp duty estimates, and undervaluation discrepancy analyses "
    "are informational indicators derived from published District Collectorate schedules. "
    "Calculations do not constitute a final binding adjudication under Section 47-A of the Indian "
    "Stamp Act (Bihar Amendment) or an official endorsement of declared consideration. Final statutory "
    "liabilities and registration fees must be assessed and accepted by the competent registering officer "
    "(Sub-Registrar) at the time of deed presentation."
)


class MVRScheduleRecord(BaseModel):
    schedule_id: Union[str, uuid.UUID]
    schedule_code: str
    district: str
    registration_office: str
    anchal_circle: str
    mauza: str
    thana_number: Optional[str] = None
    jurisdiction_type: str = "RURAL"
    property_category: str = "AGRICULTURAL"
    land_classification: str = "DHANHAR_I"
    road_category: str = "RURAL_ROAD_OR_NO_ROAD"
    rate_per_decimal: float
    rate_per_sqft: Optional[float] = None
    rate_per_katha: Optional[float] = None
    unit_basis: str = "DECIMAL"
    effective_from: Union[datetime, date]
    effective_to: Optional[Union[datetime, date]] = None
    version_number: int = 1
    is_active: bool = True
    verification_status: str = "VERIFIED_OFFICIAL"
    source_gazette_reference: Optional[str] = None
    source_url: Optional[str] = None
    source_provider: str = "OFFICIAL_GAZETTE"

    model_config = ConfigDict(from_attributes=True)


class MVRScheduleCreateRequest(BaseModel):
    schedule_code: Optional[str] = None
    district: str
    registration_office: str
    anchal_circle: str
    mauza: str
    thana_number: Optional[str] = None
    jurisdiction_type: str = "RURAL"  # "RURAL", "URBAN_MUNICIPAL", "URBAN_CORPORATION"
    property_category: str = "AGRICULTURAL"  # "AGRICULTURAL", "RESIDENTIAL", "COMMERCIAL", "INDUSTRIAL"
    land_classification: str = "DHANHAR_I"
    road_category: str = "RURAL_ROAD_OR_NO_ROAD"
    rate_per_decimal: float = Field(..., gt=0, description="MVR circle rate per decimal in INR")
    rate_per_sqft: Optional[float] = None
    rate_per_katha: Optional[float] = None
    unit_basis: str = "DECIMAL"
    effective_from: Optional[datetime] = None
    source_gazette_reference: Optional[str] = None
    source_url: Optional[str] = None


class MVRScheduleSearchQuery(BaseModel):
    district: Optional[str] = None
    registration_office: Optional[str] = None
    anchal_circle: Optional[str] = None
    mauza: Optional[str] = None
    property_category: Optional[str] = None
    road_category: Optional[str] = None
    effective_date: Optional[datetime] = None


class ValuationCalculationRequest(BaseModel):
    case_id: Optional[uuid.UUID] = None
    parcel_id: Optional[uuid.UUID] = None
    
    district: str
    registration_office: Optional[str] = None
    anchal_circle: str
    mauza: str
    thana_number: Optional[str] = None
    
    property_category: str = "AGRICULTURAL"
    land_classification: Optional[str] = None
    road_category: str = "RURAL_ROAD_OR_NO_ROAD"
    jurisdiction_type: Optional[str] = None
    
    area_value: float = Field(..., gt=0, description="Land area quantity")
    area_unit: str = Field("DECIMAL", description="Unit: DECIMAL, KATHA, ACRE, BIGHA, SQFT, SQMETER")
    
    built_up_area_sqft: Optional[float] = Field(0.0, ge=0, description="Plinth area of structure if present")
    construction_rate_sqft: Optional[float] = Field(0.0, ge=0, description="Construction rate per sqft")
    
    declared_consideration: Optional[float] = Field(None, ge=0, description="Declared sale deed consideration")
    buyer_category: str = Field("MALE", description="MALE, FEMALE, JOINT_MALE_FEMALE, ORGANIZATION_OR_TRUST")
    valuation_date: Optional[datetime] = None


class ValuationCalculationResponse(BaseModel):
    valuation_id: Optional[str] = None
    schedule_code: Optional[str] = None
    district: str
    anchal_circle: str
    mauza: str
    property_category: str
    road_category: str
    jurisdiction_type: str
    
    total_area_decimal: float
    input_area_value: float
    input_area_unit: str
    applied_unit_rate: float
    rate_basis: str
    
    calculated_land_value: float
    calculated_structure_value: float
    total_government_valuation: float
    declared_consideration: Optional[float] = None
    assessment_base: float
    
    # Statutory charge breakdown
    stamp_duty_rate_percent: float
    stamp_duty_amount: float
    registration_fee_rate_percent: float
    registration_fee_amount: float
    municipal_surcharge_percent: float
    municipal_surcharge_amount: float
    total_statutory_charges: float
    concession_applied: Optional[str] = None
    
    # Discrepancy analysis
    discrepancy_status: str
    discrepancy_amount: float
    discrepancy_percentage: float
    discrepancy_explanation: str
    
    verification_status: str
    rule_version: str
    valuation_date: datetime
    disclaimer: str = STATUTORY_VALUATION_DISCLAIMER

    model_config = ConfigDict(from_attributes=True)


class DiscrepancyAnalysisResult(BaseModel):
    discrepancy_status: str
    declared_consideration: float
    government_valuation: float
    assessment_base: float
    variance_amount: float
    variance_percentage: float
    is_undervalued: bool
    is_overvalued: bool
    explanation: str
    recommended_action: Optional[str] = None
    disclaimer: str = STATUTORY_VALUATION_DISCLAIMER


class MVRDistrictCoverageSummary(BaseModel):
    district: str
    total_schedules: int
    verified_schedules: int
    unverified_schedules: int
    anchals_covered: List[str]
    property_categories_available: List[str]
    coverage_status: str  # "VERIFIED_ACTIVE", "PARTIAL_COVERAGE", "UNAVAILABLE"
    data_freshness_timestamp: Optional[datetime] = None


class MVRScheduleVerifyRequest(BaseModel):
    verification_status: str = "VERIFIED_OFFICIAL"  # "VERIFIED_OFFICIAL", "SUPERSEDED", "UNVERIFIED"
    verification_notes: str
