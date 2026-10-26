"""
Pydantic Schemas for Mutation Intelligence & Property Passport Synchronization (TASK-P2-05).
Defines request, response, timeline, import, entity resolution, and reconciliation models.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from app.models.mutation import (
    MutationType,
    MutationStatus,
    MutationEventType,
    MutationDocumentType,
    MutationMatchingMethod,
    MutationVerificationStatus,
)

STATUTORY_MUTATION_DISCLAIMER = (
    "STATUTORY NOTICE & LEGAL DISCLAIMER (MUTATION INTELLIGENCE):\n"
    "1. Mutation (Dakhil-Kharij / दाखिल-खारिज) entries under the Bihar Land Reforms / Mutation Act "
    "are fiscal and administrative records for land-revenue payment liability.\n"
    "2. As established by the Supreme Court of India in Suraj Bhan v. Financial Commissioner (2007) 6 SCC 186 "
    "and consistent precedent, mutation entries do NOT create, confer, extinguish, or determine legal title "
    "or ownership of immovable property.\n"
    "3. A reported mutation approval or issuance of Shuddhi Patra (शुद्धि पत्र) does NOT certify conclusive "
    "clear title, physical possession, or absence of encumbrances.\n"
    "4. The absence of a detected mutation proceeding does NOT imply unencumbered title or non-existence of competing transactions.\n"
    "5. Rejection orders (खारिज) specify procedural or prima facie grounds (e.g. area deficit, disputed ownership, "
    "insufficient deed) and must be independently verified by legal counsel."
)


# =====================================================================
# Document Schemas
# =====================================================================

class MutationDocumentCreate(BaseModel):
    document_type: MutationDocumentType
    file_name: str
    storage_path: str
    sha256_hash: str
    file_size_bytes: int
    mime_type: str = "application/pdf"
    source_reference: Optional[str] = None
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)
    ocr_confidence: Optional[float] = None
    ocr_engine: Optional[str] = None


class MutationDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mutation_document_id: uuid.UUID
    mutation_case_id: uuid.UUID
    document_type: MutationDocumentType
    file_name: str
    storage_path: str
    sha256_hash: str
    file_size_bytes: int
    mime_type: str
    source_reference: Optional[str] = None
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)
    ocr_confidence: Optional[float] = None
    ocr_engine: Optional[str] = None
    created_at: datetime


# =====================================================================
# Event Schemas
# =====================================================================

class MutationEventCreate(BaseModel):
    event_type: MutationEventType
    source_event_id: Optional[str] = None
    reported_event_timestamp: Optional[datetime] = None
    source_authority: str = "Circle Office (CO)"
    source_document_reference: Optional[str] = None
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)
    action_taken: Optional[str] = None
    remarks: Optional[str] = None
    provenance_type: str = "OFFICIAL_GOVERNMENT_PORTAL"


class MutationEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mutation_event_id: uuid.UUID
    mutation_case_id: uuid.UUID
    event_type: MutationEventType
    source_event_id: Optional[str] = None
    reported_event_timestamp: Optional[datetime] = None
    ingested_timestamp: datetime
    source_authority: str
    source_document_reference: Optional[str] = None
    payload_hash: str
    raw_payload: Dict[str, Any]
    extracted_fields: Dict[str, Any]
    action_taken: Optional[str] = None
    remarks: Optional[str] = None
    provenance_type: str
    created_at: datetime


# =====================================================================
# Case Schemas
# =====================================================================

class MutationCaseCreate(BaseModel):
    case_number: str
    filing_year: int
    district: str
    circle: str
    mauza: str
    mutation_type: MutationType = MutationType.SALE_DEED
    khata_number: Optional[str] = None
    khesra_number: Optional[str] = None
    jamabandi_number: Optional[str] = None
    deed_number: Optional[str] = None
    deed_date: Optional[date] = None
    deed_registered_office: Optional[str] = None
    applicant_names: List[str] = Field(default_factory=list)
    buyer_names: List[str] = Field(default_factory=list)
    seller_names: List[str] = Field(default_factory=list)
    parcel_id: Optional[uuid.UUID] = None
    case_id: Optional[uuid.UUID] = None
    filing_date: Optional[date] = None
    normalized_status: MutationStatus = MutationStatus.RECEIVED
    raw_source_status: Optional[str] = None
    rejection_reason_code: Optional[str] = None
    rejection_reason_details: Optional[str] = None
    source_portal: str = "biharbhumi.bihar.gov.in"
    source_authority: str = "Circle Officer (CO)"
    notes: Optional[str] = None


class MutationCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mutation_case_id: uuid.UUID
    org_id: uuid.UUID
    parcel_id: Optional[uuid.UUID] = None
    case_id: Optional[uuid.UUID] = None
    case_number: str
    filing_year: int
    district: str
    circle: str
    mauza: str
    mutation_type: MutationType
    khata_number: Optional[str] = None
    khesra_number: Optional[str] = None
    jamabandi_number: Optional[str] = None
    deed_number: Optional[str] = None
    deed_date: Optional[date] = None
    deed_registered_office: Optional[str] = None
    applicant_names: List[str] = Field(default_factory=list)
    buyer_names: List[str] = Field(default_factory=list)
    seller_names: List[str] = Field(default_factory=list)
    filing_date: Optional[date] = None
    disposal_date: Optional[date] = None
    normalized_status: MutationStatus
    raw_source_status: Optional[str] = None
    rejection_reason_code: Optional[str] = None
    rejection_reason_details: Optional[str] = None
    source_portal: str
    source_authority: str
    verification_status: MutationVerificationStatus
    last_source_observation: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class MutationCaseDetailResponse(MutationCaseResponse):
    events: List[MutationEventResponse] = Field(default_factory=list)
    documents: List[MutationDocumentResponse] = Field(default_factory=list)
    statutory_disclaimer: str = STATUTORY_MUTATION_DISCLAIMER


# =====================================================================
# Entity Resolution Schemas
# =====================================================================

class MutationEntityResolutionRequest(BaseModel):
    mutation_case_id: uuid.UUID
    parcel_id: Optional[uuid.UUID] = None
    case_id: Optional[uuid.UUID] = None


class MutationEntityResolutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    resolution_id: uuid.UUID
    org_id: uuid.UUID
    mutation_case_id: uuid.UUID
    parcel_id: Optional[uuid.UUID] = None
    case_id: Optional[uuid.UUID] = None
    matching_method: MutationMatchingMethod
    identifiers_compared: Dict[str, Any]
    confidence_score: float
    match_outcome: str
    explanation: str
    review_status: str
    reviewer_user_id: Optional[uuid.UUID] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: datetime


class MutationOperatorReviewRequest(BaseModel):
    action: str = Field(..., description="'CONFIRM_ASSOCIATION', 'REJECT_ASSOCIATION', or 'FLAG_AMBIGUOUS'")
    review_notes: str


# =====================================================================
# Operator Import & Manual Ingestion
# =====================================================================

class MutationManualImportRequest(BaseModel):
    case_number: str
    filing_year: int
    district: str
    circle: str
    mauza: str
    mutation_type: MutationType = MutationType.SALE_DEED
    khata_number: Optional[str] = None
    khesra_number: Optional[str] = None
    jamabandi_number: Optional[str] = None
    deed_number: Optional[str] = None
    deed_date: Optional[date] = None
    deed_registered_office: Optional[str] = None
    applicant_name: str
    seller_name: Optional[str] = None
    filing_date: Optional[date] = None
    reported_status: str = "RECEIVED"
    order_date: Optional[date] = None
    rejection_reason_code: Optional[str] = None
    rejection_reason_details: Optional[str] = None
    parcel_id: Optional[uuid.UUID] = None
    case_id: Optional[uuid.UUID] = None
    operator_notes: Optional[str] = None
    certified_document_reference: Optional[str] = None


# =====================================================================
# Property Passport Timeline Schemas
# =====================================================================

class MutationTimelineEntry(BaseModel):
    entry_id: str
    timestamp: datetime
    stage: str
    event_type: str
    case_number: str
    authority: str
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)
    provenance_type: str  # OFFICIAL_GOVERNMENT_PORTAL, OPERATOR_CERTIFIED_DOCUMENT, OCR_EXTRACTED_FIELD, SYSTEM_INFERRED, HUMAN_REVIEWED
    confidence: float
    document_reference: Optional[str] = None
    is_conflict: bool = False
    conflict_details: Optional[str] = None


class PropertyPassportMutationTimelineResponse(BaseModel):
    parcel_id: str
    case_id: Optional[str] = None
    total_cases_tracked: int
    active_proceedings_count: int
    rejection_orders_count: int
    approved_shuddhi_patras_count: int
    active_conflicts_count: int
    timeline: List[MutationTimelineEntry] = Field(default_factory=list)
    active_conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    last_synced_at: Optional[datetime] = None
    statutory_disclaimer: str = STATUTORY_MUTATION_DISCLAIMER


# =====================================================================
# Reconciliation Schemas
# =====================================================================

class MutationReconcileRequest(BaseModel):
    parcel_id: Optional[uuid.UUID] = None
    district: Optional[str] = None
    circle: Optional[str] = None
    lookback_days: int = 365


class MutationReconciliationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: uuid.UUID
    org_id: uuid.UUID
    adapter_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    records_observed: int
    records_new: int
    records_updated: int
    records_duplicate: int
    records_rejected: int
    records_unresolved: int
    records_conflicting: int
    status: str
    error_summary: Optional[Dict[str, Any]] = None
    created_at: datetime


# =====================================================================
# Search & Filter
# =====================================================================

class MutationSearchQuery(BaseModel):
    case_number: Optional[str] = None
    district: Optional[str] = None
    circle: Optional[str] = None
    mauza: Optional[str] = None
    khata_number: Optional[str] = None
    khesra_number: Optional[str] = None
    deed_number: Optional[str] = None
    party_name: Optional[str] = None
    status: Optional[MutationStatus] = None
    parcel_id: Optional[uuid.UUID] = None
    case_id: Optional[uuid.UUID] = None
