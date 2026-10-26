"""
Bihar Minimum Valuation Register (MVR) and Stamp Duty Domain Models.

Persists official government circle rate schedules, historical rate versions,
and deterministic property valuation and statutory charge assessments.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import sqlalchemy as sa
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import GUID, JSONCompatible, utc_now


class PropertyCategory(str):
    AGRICULTURAL = "AGRICULTURAL"
    RESIDENTIAL = "RESIDENTIAL"
    COMMERCIAL = "COMMERCIAL"
    INDUSTRIAL = "INDUSTRIAL"
    OTHER = "OTHER"


class RoadCategory(str):
    MAIN_ROAD_NH_SH = "MAIN_ROAD_NH_SH"
    PWD_ROAD = "PWD_ROAD"
    BRANCH_ROAD_MUNICIPAL = "BRANCH_ROAD_MUNICIPAL"
    RURAL_ROAD_OR_NO_ROAD = "RURAL_ROAD_OR_NO_ROAD"


class JurisdictionType(str):
    RURAL = "RURAL"
    URBAN_MUNICIPAL = "URBAN_MUNICIPAL"
    URBAN_CORPORATION = "URBAN_CORPORATION"


class AreaUnit(str):
    DECIMAL = "DECIMAL"
    KATHA = "KATHA"
    ACRE = "ACRE"
    BIGHA = "BIGHA"
    SQFT = "SQFT"
    SQMETER = "SQMETER"


class ScheduleVerificationStatus(str):
    VERIFIED_OFFICIAL = "VERIFIED_OFFICIAL"
    PROVISIONAL = "PROVISIONAL"
    UNVERIFIED = "UNVERIFIED"
    SUPERSEDED = "SUPERSEDED"


class DiscrepancyStatus(str):
    NO_DISCREPANCY_DETECTED = "NO_DISCREPANCY_DETECTED"
    POTENTIAL_UNDERVALUE = "POTENTIAL_UNDERVALUE"
    POTENTIAL_OVERVALUATION = "POTENTIAL_OVERVALUATION"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    REQUIRES_MANUAL_REVIEW = "REQUIRES_MANUAL_REVIEW"


class BuyerGenderCategory(str):
    MALE = "MALE"
    FEMALE = "FEMALE"
    JOINT_MALE_FEMALE = "JOINT_MALE_FEMALE"
    ORGANIZATION_OR_TRUST = "ORGANIZATION_OR_TRUST"


class MVRSchedule(Base):
    """
    Persists official Minimum Valuation Register (MVR) / Circle Rate schedules
    published by Bihar District Collectorates and Registration Offices.
    """
    __tablename__ = "mvr_schedules"

    schedule_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="SET NULL"), nullable=True, index=True)
    schedule_code = sa.Column(sa.String(64), unique=True, nullable=False, index=True)
    
    district = sa.Column(sa.String(64), nullable=False, index=True)
    registration_office = sa.Column(sa.String(128), nullable=False)
    anchal_circle = sa.Column(sa.String(128), nullable=False, index=True)
    mauza = sa.Column(sa.String(128), nullable=False, index=True)
    thana_number = sa.Column(sa.String(32), nullable=True)
    
    jurisdiction_type = sa.Column(sa.String(32), nullable=False, default=JurisdictionType.RURAL)
    property_category = sa.Column(sa.String(64), nullable=False, default=PropertyCategory.AGRICULTURAL)
    land_classification = sa.Column(sa.String(64), nullable=False, default="DHANHAR_I")
    road_category = sa.Column(sa.String(64), nullable=False, default=RoadCategory.RURAL_ROAD_OR_NO_ROAD)
    
    # Valuation rates
    rate_per_decimal = sa.Column(sa.Numeric(12, 2), nullable=False)
    rate_per_sqft = sa.Column(sa.Numeric(12, 2), nullable=True)
    rate_per_katha = sa.Column(sa.Numeric(12, 2), nullable=True)
    unit_basis = sa.Column(sa.String(32), nullable=False, default=AreaUnit.DECIMAL)
    
    # Schedule validity and provenance
    effective_from = sa.Column(sa.DateTime(timezone=True), nullable=False, default=utc_now)
    effective_to = sa.Column(sa.DateTime(timezone=True), nullable=True)
    version_number = sa.Column(sa.Integer, nullable=False, default=1)
    is_active = sa.Column(sa.Boolean, nullable=False, default=True)
    verification_status = sa.Column(sa.String(32), nullable=False, default=ScheduleVerificationStatus.VERIFIED_OFFICIAL)
    
    source_gazette_reference = sa.Column(sa.String(256), nullable=True)
    source_url = sa.Column(sa.String(512), nullable=True)
    source_provider = sa.Column(sa.String(64), nullable=False, default="OFFICIAL_GAZETTE")
    raw_source_payload = sa.Column(JSONCompatible, nullable=False, default=dict)
    
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    valuations = relationship("PropertyValuation", back_populates="schedule")


class PropertyValuation(Base):
    """
    Audit-ready record of a calculated government property valuation,
    associated statutory charges (Stamp Duty & Registration Fee),
    and discrepancy analysis against declared consideration.
    """
    __tablename__ = "property_valuations"

    valuation_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="SET NULL"), nullable=True, index=True)
    case_id = sa.Column(GUID, sa.ForeignKey("cases.case_id", ondelete="SET NULL"), nullable=True, index=True)
    parcel_id = sa.Column(GUID, sa.ForeignKey("parcels.parcel_id", ondelete="SET NULL"), nullable=True, index=True)
    schedule_id = sa.Column(GUID, sa.ForeignKey("mvr_schedules.schedule_id", ondelete="SET NULL"), nullable=True, index=True)
    
    valuation_date = sa.Column(sa.DateTime(timezone=True), nullable=False, default=utc_now)
    
    # Area inputs and normalization
    total_area_decimal = sa.Column(sa.Numeric(12, 4), nullable=False)
    input_area_value = sa.Column(sa.Numeric(12, 4), nullable=False)
    input_area_unit = sa.Column(sa.String(32), nullable=False, default=AreaUnit.DECIMAL)
    unit_circle_rate = sa.Column(sa.Numeric(12, 2), nullable=False)
    
    # Calculated valuation values
    calculated_land_value = sa.Column(sa.Numeric(14, 2), nullable=False)
    built_up_area_sqft = sa.Column(sa.Numeric(10, 2), nullable=True, default=0.0)
    construction_rate_sqft = sa.Column(sa.Numeric(10, 2), nullable=True, default=0.0)
    calculated_structure_value = sa.Column(sa.Numeric(14, 2), nullable=False, default=0.0)
    total_government_valuation = sa.Column(sa.Numeric(14, 2), nullable=False)
    
    # Financial assessment & statutory charges
    declared_transaction_consideration = sa.Column(sa.Numeric(14, 2), nullable=True)
    assessment_base = sa.Column(sa.Numeric(14, 2), nullable=False)
    buyer_category = sa.Column(sa.String(32), nullable=False, default=BuyerGenderCategory.MALE)
    
    stamp_duty_rate_percent = sa.Column(sa.Numeric(5, 2), nullable=False, default=6.0)
    stamp_duty_amount = sa.Column(sa.Numeric(14, 2), nullable=False)
    registration_fee_rate_percent = sa.Column(sa.Numeric(5, 2), nullable=False, default=2.0)
    registration_fee_amount = sa.Column(sa.Numeric(14, 2), nullable=False)
    municipal_surcharge_percent = sa.Column(sa.Numeric(5, 2), nullable=False, default=0.0)
    municipal_surcharge_amount = sa.Column(sa.Numeric(14, 2), nullable=False, default=0.0)
    total_statutory_charges = sa.Column(sa.Numeric(14, 2), nullable=False)
    concession_applied = sa.Column(sa.String(128), nullable=True)
    
    # Discrepancy analysis
    discrepancy_status = sa.Column(sa.String(64), nullable=False, default=DiscrepancyStatus.NO_DISCREPANCY_DETECTED)
    discrepancy_amount = sa.Column(sa.Numeric(14, 2), nullable=False, default=0.0)
    discrepancy_percentage = sa.Column(sa.Numeric(6, 2), nullable=False, default=0.0)
    discrepancy_explanation = sa.Column(sa.Text, nullable=False)
    
    rule_version = sa.Column(sa.String(64), nullable=False, default="BIHAR_STAMP_RULES_v2026.1")
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)
    created_by_user_id = sa.Column(GUID, sa.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)

    schedule = relationship("MVRSchedule", back_populates="valuations")
    case = relationship("Case", back_populates="valuations")
    parcel = relationship("Parcel", back_populates="valuations")
