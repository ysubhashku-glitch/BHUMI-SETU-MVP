"""
Judicial Risk Intelligence Domain Models.
Persists official eCourts, District Court, and Patna High Court dockets,
proceedings, orders, and their deterministic entity-resolution links to land parcels.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import sqlalchemy as sa
from sqlalchemy.orm import relationship, synonym

from app.database import Base
from app.models.base import GUID, JSONCompatible, utc_now

class CourtType(str):
    HIGH_COURT = "HIGH_COURT"
    DISTRICT_COURT = "DISTRICT_COURT"
    SUB_DIVISIONAL_COURT = "SUB_DIVISIONAL_COURT"
    REVENUE_TRIBUNAL = "REVENUE_TRIBUNAL"
    OTHER = "OTHER"

class JudicialCaseStatus(str):
    PENDING = "PENDING"
    DISPOSED = "DISPOSED"
    STAYED_INJUNCTION_ACTIVE = "STAYED_INJUNCTION_ACTIVE"
    ADMITTED = "ADMITTED"
    DISMISSED = "DISMISSED"
    UNKNOWN = "UNKNOWN"

class JudicialRiskCategory(str):
    TITLE_DISPUTE = "TITLE_DISPUTE"
    PARTITION_PROCEEDING = "PARTITION_PROCEEDING"
    INJUNCTION_RISK = "INJUNCTION_RISK"
    REVENUE_MUTATION_DISPUTE = "REVENUE_MUTATION_DISPUTE"
    WRIT_LITIGATION = "WRIT_LITIGATION"
    OTHER_CIVIL = "OTHER_CIVIL"
    OTHER = "OTHER"

class ParcelMatchCategory(str):
    EXACT_IDENTIFIER_MATCH = "EXACT_IDENTIFIER_MATCH"
    STRONG_CORROBORATED_MATCH = "STRONG_CORROBORATED_MATCH"
    WEAK_CANDIDATE_REVIEW_REQUIRED = "WEAK_CANDIDATE_REVIEW_REQUIRED"
    NAME_ONLY = "NAME_ONLY"
    REJECTED_MATCH = "REJECTED_MATCH"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

# Alias for external synthesis and testing compatibility
JudicialMatchCategory = ParcelMatchCategory

class MatchReviewStatus(str):
    PENDING_REVIEW = "PENDING_REVIEW"
    VERIFIED_ASSOCIATED = "VERIFIED_ASSOCIATED"
    DISMISSED_UNRELATED = "DISMISSED_UNRELATED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

# Alias for external synthesis and testing compatibility
JudicialReviewStatus = MatchReviewStatus



class JudicialCase(Base):
    __tablename__ = "judicial_cases"

    case_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="SET NULL"), nullable=True, index=True)
    cnr_number = sa.Column(sa.String(32), unique=True, nullable=False, index=True)
    court_name = sa.Column(sa.String(128), nullable=False)
    court_type = sa.Column(sa.String(32), nullable=False, default=CourtType.DISTRICT_COURT)
    district = sa.Column(sa.String(64), nullable=False, index=True)
    state = sa.Column(sa.String(32), nullable=False, default="Bihar")
    case_type = sa.Column(sa.String(64), nullable=False, index=True)
    case_number = sa.Column(sa.String(64), nullable=False)
    filing_year = sa.Column(sa.Integer, nullable=False)
    filing_date = sa.Column(sa.DateTime(timezone=True), nullable=True)
    registration_date = sa.Column(sa.DateTime(timezone=True), nullable=True)
    
    case_status = sa.Column(sa.String(32), nullable=False, default=JudicialCaseStatus.PENDING, index=True)
    stage_of_case = sa.Column(sa.String(128), nullable=True)
    
    petitioner_names = sa.Column(JSONCompatible, nullable=False, default=list)
    respondent_names = sa.Column(JSONCompatible, nullable=False, default=list)
    advocate_petitioner = sa.Column(sa.String(128), nullable=True)
    advocate_respondent = sa.Column(sa.String(128), nullable=True)
    acts_sections = sa.Column(JSONCompatible, nullable=False, default=list)
    
    property_schedule_raw = sa.Column(sa.Text, nullable=True)
    extracted_land_identifiers = sa.Column(JSONCompatible, nullable=False, default=dict)
    orders_summary = sa.Column(JSONCompatible, nullable=False, default=list)
    has_active_injunction = sa.Column(sa.Boolean, nullable=False, default=False)
    risk_category = sa.Column(sa.String(64), nullable=False, default=JudicialRiskCategory.OTHER)
    
    source_url = sa.Column(sa.String(512), nullable=True)
    source_provider = sa.Column(sa.String(64), nullable=False, default="MANUAL_IMPORT")
    retrieval_timestamp = sa.Column(sa.DateTime(timezone=True), nullable=False, default=utc_now)
    evidence_id = sa.Column(GUID, sa.ForeignKey("evidence.evidence_id", ondelete="SET NULL"), nullable=True)
    raw_source_payload = sa.Column(JSONCompatible, nullable=False, default=dict)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    matches = relationship("ParcelJudicialMatch", back_populates="judicial_case", cascade="all, delete-orphan")

    judicial_case_id = synonym("case_id")

    def __init__(self, **kwargs):
        self.search_query_snapshot = kwargs.pop("search_query_snapshot", None)
        if "judicial_case_id" in kwargs and "case_id" not in kwargs:
            kwargs["case_id"] = kwargs.pop("judicial_case_id")
        if "district" not in kwargs:
            court = kwargs.get("court_name", "")
            kwargs["district"] = "Gaya" if "Gaya" in court else "Patna"
        if "case_type" not in kwargs:
            kwargs["case_type"] = "CIVIL_SUIT"
        super().__init__(**kwargs)


class ParcelJudicialMatch(Base):
    __tablename__ = "parcel_judicial_matches"

    match_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="SET NULL"), nullable=True, index=True)
    case_id = sa.Column(GUID, sa.ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=True, index=True)
    parcel_id = sa.Column(GUID, sa.ForeignKey("parcels.parcel_id", ondelete="CASCADE"), nullable=False, index=True)
    judicial_case_id = sa.Column(GUID, sa.ForeignKey("judicial_cases.case_id", ondelete="CASCADE"), nullable=False, index=True)
    
    match_category = sa.Column(sa.String(64), nullable=False, default=ParcelMatchCategory.WEAK_CANDIDATE_REVIEW_REQUIRED, index=True)
    confidence_score = sa.Column(sa.Numeric(5, 2), nullable=False, default=0.50)
    matched_fields = sa.Column(JSONCompatible, nullable=False, default=dict)
    matching_method = sa.Column(sa.String(64), nullable=False, default="DETERMINISTIC_ENTITY_RESOLUTION_v1.0")
    explanation = sa.Column(sa.Text, nullable=False)
    
    review_status = sa.Column(sa.String(32), nullable=False, default=MatchReviewStatus.PENDING_REVIEW, index=True)
    reviewed_by_user_id = sa.Column(GUID, sa.ForeignKey("users.user_id"), nullable=True)
    reviewed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    review_notes = sa.Column(sa.Text, nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    judicial_case = relationship("JudicialCase", back_populates="matches")
    case = relationship("Case", back_populates="judicial_matches")
    parcel = relationship("Parcel", back_populates="judicial_matches")

    def __init__(self, **kwargs):
        if "case_id" not in kwargs:
            kwargs["case_id"] = None
        super().__init__(**kwargs)
