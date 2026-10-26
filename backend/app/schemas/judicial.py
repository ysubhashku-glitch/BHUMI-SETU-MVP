"""
Pydantic Schemas for Judicial Risk Intelligence Subsystem.
Defines case records, search requests/responses, manual ingestion models,
parcel-to-case matches, and operator review structures.
"""

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

EPISTEMIC_JUDICIAL_DISCLAIMER = (
    "NOTICE: Court case search results and entity-resolution matches are probabilistic "
    "informational indicators derived from publicly accessible judicial portals. "
    "A matching name does NOT confirm parcel-level litigation without certified court schedule review. "
    "Neither a detected case nor absence of records constitutes a legal title opinion, "
    "guarantee of non-encumbrance, or judicial adjudication of ownership."
)

class JudicialCaseRecord(BaseModel):
    case_id: Optional[str] = None
    cnr_number: str
    court_name: str
    court_type: str = "DISTRICT_COURT"
    district: str
    state: str = "Bihar"
    case_type: str
    case_number: str
    filing_year: int
    filing_date: Optional[datetime] = None
    registration_date: Optional[datetime] = None
    case_status: str = "PENDING"
    stage_of_case: Optional[str] = None
    petitioner_names: List[str] = Field(default_factory=list)
    respondent_names: List[str] = Field(default_factory=list)
    advocate_petitioner: Optional[str] = None
    advocate_respondent: Optional[str] = None
    acts_sections: List[str] = Field(default_factory=list)
    property_schedule_raw: Optional[str] = None
    extracted_land_identifiers: Dict[str, Any] = Field(default_factory=dict)
    orders_summary: List[Dict[str, Any]] = Field(default_factory=list)
    has_active_injunction: bool = False
    risk_category: str = "OTHER"
    source_url: Optional[str] = None
    source_provider: str = "MANUAL_IMPORT"
    retrieval_timestamp: Optional[datetime] = None
    evidence_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ParcelJudicialMatchResponse(BaseModel):
    match_id: str
    case_id: str
    parcel_id: str
    judicial_case_id: str
    cnr_number: str
    court_name: str
    case_type: str
    case_number: str
    case_status: str
    has_active_injunction: bool
    risk_category: str
    match_category: str
    confidence_score: float
    matched_fields: Dict[str, Any]
    matching_method: str
    explanation: str
    review_status: str
    reviewed_by_user_id: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: datetime
    epistemic_notice: str = EPISTEMIC_JUDICIAL_DISCLAIMER

    model_config = ConfigDict(from_attributes=True)


class JudicialSearchQuery(BaseModel):
    cnr_number: Optional[str] = None
    party_name: Optional[str] = None
    district: Optional[str] = None
    filing_year: Optional[int] = None
    case_type: Optional[str] = None
    case_number: Optional[str] = None
    parcel_id: Optional[uuid.UUID] = None


class JudicialSearchResponse(BaseModel):
    query: JudicialSearchQuery
    total_cases_found: int
    cases: List[JudicialCaseRecord] = []
    matches: List[ParcelJudicialMatchResponse] = []
    provider_used: str
    retrieval_timestamp: datetime
    epistemic_notice: str = EPISTEMIC_JUDICIAL_DISCLAIMER


class JudicialManualIngestRequest(BaseModel):
    cnr_number: str
    court_name: str
    court_type: str = "DISTRICT_COURT"
    district: str
    case_type: str
    case_number: str
    filing_year: int
    case_status: str = "PENDING"
    stage_of_case: Optional[str] = None
    petitioner_names: List[str]
    respondent_names: List[str]
    advocate_petitioner: Optional[str] = None
    advocate_respondent: Optional[str] = None
    property_schedule_raw: Optional[str] = None
    extracted_land_identifiers: Optional[Dict[str, Any]] = None
    orders_summary: Optional[List[Dict[str, Any]]] = None
    has_active_injunction: bool = False
    risk_category: str = "TITLE_DISPUTE"
    source_url: Optional[str] = None
    certified_document_id: Optional[uuid.UUID] = None


class JudicialMatchReviewRequest(BaseModel):
    action: str  # "CONFIRM_ASSOCIATED", "DISMISS_UNRELATED", "MARK_INSUFFICIENT"
    review_notes: str
