import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class DocumentVersionResponse(BaseModel):
    version_id: str
    document_id: str
    version_number: int
    content_hash: str
    storage_reference: str
    mime_type: str
    file_size_bytes: int
    page_count: int
    processing_status: str
    parser_version: Optional[str] = None
    ocr_engine: Optional[str] = None
    ocr_engine_version: Optional[str] = None
    failure_reason: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DocumentPageResponse(BaseModel):
    page_id: str
    document_id: Optional[str] = None
    version_id: Optional[str] = None
    page_number: int
    page_image_uri: Optional[str] = None
    ocr_text: Optional[str] = None
    ocr_confidence: Optional[float] = None
    width_px: Optional[int] = None
    height_px: Optional[int] = None
    rotation_deg: int = 0
    resolution_dpi: Optional[int] = None
    has_selectable_text: bool = False
    is_blank: bool = False
    page_hash: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class EvidenceSpanResponse(BaseModel):
    span_id: str
    document_id: str
    version_id: Optional[str] = None
    page_id: str
    x_min: Optional[float] = None
    y_min: Optional[float] = None
    x_max: Optional[float] = None
    y_max: Optional[float] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    extracted_text: str
    source_type: str
    extraction_method: str
    confidence: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ExtractedFieldResponse(BaseModel):
    field_id: str
    document_id: str
    version_id: str
    page_id: Optional[str] = None
    evidence_span_id: Optional[str] = None
    field_name: str
    raw_value: Optional[str] = None
    normalized_value: Optional[Any] = None
    unit: Optional[str] = None
    data_type: str
    extraction_method: str
    confidence: float
    status: str
    review_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ExtractionReviewRequest(BaseModel):
    action: str  # "ACCEPT", "EDIT", "REJECT", "MARK_UNKNOWN", "MARK_CONFLICTING"
    reviewed_value: Optional[Any] = None
    review_notes: Optional[str] = None

class CandidateClaimResponse(BaseModel):
    candidate_claim_id: str
    case_id: str
    document_id: str
    version_id: str
    extracted_field_id: Optional[str] = None
    evidence_span_id: Optional[str] = None
    subject_entity_type: str
    subject_hint: Optional[Dict[str, Any]] = None
    predicate: str
    object_value: Dict[str, Any]
    authority_tier: str
    confidence_score: float
    status: str
    materialized_claim_id: Optional[str] = None
    review_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CandidateClaimAcceptRequest(BaseModel):
    parcel_id: str
    review_notes: Optional[str] = None

class CandidateClaimRejectRequest(BaseModel):
    rejection_reason: str

class DocumentProcessingStatusResponse(BaseModel):
    document_id: str
    active_version_id: Optional[str] = None
    document_category: str
    processing_status: str
    page_count: int
    ocr_engine: Optional[str] = None
    failure_reason: Optional[str] = None
    extracted_field_count: int = 0
    candidate_claim_count: int = 0

class DocumentClassificationResponse(BaseModel):
    document_id: str
    document_category: str
    confidence: float
    method: str
    model_version: str
    matched_signals: Dict[str, Any]
    alternative_classifications: List[Dict[str, Any]] = []
    review_required: bool = False
    processing_status: str = "CLASSIFIED"

class CrossReferenceMatchCandidate(BaseModel):
    parcel_id: Optional[str] = None
    bhumi_id: Optional[str] = None
    khata_number: Optional[str] = None
    plot_number: Optional[str] = None
    mauza: Optional[str] = None
    recorded_area_acres: Optional[float] = None
    match_confidence: float = 0.0
    match_reasons: List[str] = []

class CrossReferenceRequest(BaseModel):
    case_id: Optional[str] = None
    compare_with_jamabandi: bool = True
    compare_with_cadastral: bool = True

class DocumentCrossReferenceResponse(BaseModel):
    document_id: str
    status: str  # EXACT_MATCH, PROBABLE_MATCH, MULTIPLE_CANDIDATE_MATCHES, IDENTIFIER_CONFLICT, AREA_DISCREPANCY, NO_MATCH, INSUFFICIENT_DATA
    confidence: float
    extracted_identifiers: Dict[str, Any]
    matched_parcel: Optional[CrossReferenceMatchCandidate] = None
    candidate_matches: List[CrossReferenceMatchCandidate] = []
    discrepancies: List[Dict[str, Any]] = []
    explanations: List[str] = []
    review_required: bool = False
    epistemic_notice: str = (
        "Automated cross-reference results are derived heuristics and do NOT "
        "constitute verified legal title, judicial adjudication, or field survey confirmation."
    )

