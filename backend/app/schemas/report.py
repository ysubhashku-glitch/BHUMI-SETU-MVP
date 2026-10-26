import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.models.report import ReportStatus

class ReportGenerateRequest(BaseModel):
    case_id: uuid.UUID
    parcel_id: Optional[uuid.UUID] = None
    report_title: Optional[str] = Field("Land Intelligence Diligence Dossier", description="Custom report title if needed")
    notes: Optional[str] = None

class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_id: uuid.UUID
    org_id: uuid.UUID
    case_id: uuid.UUID
    parcel_id: Optional[uuid.UUID] = None
    report_number: str
    version_number: int
    status: str
    sha256_hash: str
    file_size_bytes: int
    page_count: int
    created_at: datetime
    download_url: str
    verification_url: str
    summary_counts: Dict[str, Any] = Field(default_factory=dict)

class ReportVerificationResponse(BaseModel):
    """
    Data-minimized public verification response for QR code scans.
    Reveals authenticity and tamper-evidence status without leaking private owner dossier.
    """
    is_authentic: bool
    report_number: str
    version_number: int
    status: str
    issued_at: datetime
    sha256_hash: str
    hash_matches_stored_file: bool
    scope: str
    disclaimer: str

class Section1CoverData(BaseModel):
    report_number: str
    report_version: int
    generated_at: str
    case_number: str
    case_id: str
    case_status: str
    parcel_bhumi_id: Optional[str] = None
    district: Optional[str] = None
    circle: Optional[str] = None
    mauza: Optional[str] = None
    khata: Optional[str] = None
    khesra: Optional[str] = None
    data_availability_summary: Dict[str, bool]
    disclaimer: str

class Section2RevenueData(BaseModel):
    parcel_bhumi_id: Optional[str] = None
    khata_number: Optional[str] = None
    khesra_number: Optional[str] = None
    jamabandi_number: Optional[str] = None
    recorded_area_original: Optional[str] = None
    recorded_area_acres: Optional[float] = None
    land_nature: Optional[str] = None
    recorded_raiyat: Optional[str] = None
    retrieval_timestamp: Optional[str] = None
    source_name: Optional[str] = None
    evidence_id: Optional[str] = None
    is_available: bool

class Section3CadastralData(BaseModel):
    is_available: bool
    crs: Optional[str] = None
    geometry_validation_status: Optional[str] = None
    recorded_area_acres: Optional[float] = None
    calculated_area_acres: Optional[float] = None
    area_delta_acres: Optional[float] = None
    variance_percentage: Optional[float] = None
    map_image_available: bool = False
    spatial_provenance: Optional[str] = None
    limitation_notes: Optional[str] = None

class Section4DocumentItem(BaseModel):
    document_id: str
    document_category: str
    original_filename: str
    upload_date: Optional[str] = None
    page_count: int
    ocr_engine: Optional[str] = None
    extracted_fields: Dict[str, Any]
    chauhaddi: Dict[str, Optional[str]]
    extraction_confidence: float
    review_status: str
    cross_reference_status: Optional[str] = None

class Section5FieldData(BaseModel):
    is_available: bool
    task_number: Optional[str] = None
    task_status: Optional[str] = None
    assigned_worker: Optional[str] = None
    visit_started_at: Optional[str] = None
    visit_completed_at: Optional[str] = None
    gps_reading_count: int = 0
    reported_accuracy_meters: Optional[float] = None
    measured_area_acres: Optional[float] = None
    ground_chauhaddi: Dict[str, Optional[str]]
    road_access_type: Optional[str] = None
    road_frontage_feet: Optional[float] = None
    physical_possessor_name: Optional[str] = None
    photograph_evidence_ids: List[str] = Field(default_factory=list)
    narrative_summary: Optional[str] = None
    reviewer_notes: Optional[str] = None
    review_outcome: Optional[str] = None

class Section6ConsistencyItem(BaseModel):
    category: str
    values_compared: str
    source_a: str
    source_b: str
    outcome: str
    difference_explanation: str
    recommended_action: Optional[str] = None

class Section7EvidenceItem(BaseModel):
    evidence_id: str
    evidence_type: str
    authority_tier: str
    source_name: str
    captured_at: Optional[str] = None
    sha256_hash: str
    limitations: Optional[str] = None

class Section8ActionItem(BaseModel):
    finding_id: str
    rule_id: str
    severity: str
    status: str
    explanation: str
    recommended_action: Optional[str] = None

JUDICIAL_REPORT_LIMITATION_STATEMENT = (
    "JUDICIAL DOCKET SEARCH LIMITATION STATEMENT:\n"
    "1. Search coverage depends on publicly accessible eCourts and Patna High Court records and may be incomplete, delayed, or subject to portal availability.\n"
    "2. Many civil suits do not expose parcel-level identifiers (khesra/plot, khata, mauza) in searchable top-level docket fields.\n"
    "3. Identical or similar personal names frequently occur across Bihar revenue circles and may refer to completely different individuals.\n"
    "4. Reported procedural case status (e.g. Pending, Disposed, Stayed) does not independently determine final legal rights or ownership.\n"
    "5. The absence of a detected matching case does NOT prove the complete absence of pending or past litigation.\n"
    "6. This report is strictly informational and does NOT constitute a formal legal opinion, title certificate, or substitute for independent advocate due diligence."
)

class SectionJudicialRiskItem(BaseModel):
    match_id: str
    cnr_number: str
    court_name: str
    case_type: str
    case_number: str
    filing_year: int
    case_status: str
    has_active_injunction: bool
    risk_category: str
    match_category: str
    confidence_score: float
    matched_fields: Dict[str, Any] = Field(default_factory=dict)
    explanation: str
    review_status: str
    source_url: Optional[str] = None
    retrieval_date: Optional[str] = None

class SectionJudicialRiskData(BaseModel):
    is_searched: bool
    total_candidates_found: int
    active_injunctions_detected: int
    candidate_cases: List[SectionJudicialRiskItem] = Field(default_factory=list)
    limitation_statement: str = JUDICIAL_REPORT_LIMITATION_STATEMENT

VALUATION_REPORT_LIMITATION_STATEMENT = (
    "STATUTORY VALUATION & STAMP DUTY LIMITATION NOTICE:\n"
    "1. MVR guideline circle rates and statutory charge estimates are derived from District Collectorate published schedules.\n"
    "2. This assessment is strictly informational and does not constitute a final binding adjudication under Section 47-A of the Indian Stamp Act (Bihar Amendment).\n"
    "3. Final stamp duty and registration fees are assessed by the competent Sub-Registrar at the time of deed presentation.\n"
    "4. Declared consideration lower than government guideline valuation triggers minimum statutory assessment base rules to prevent duty shortfall."
)

class SectionValuationItem(BaseModel):
    valuation_id: str
    schedule_code: str
    district: str
    anchal_circle: str
    mauza: str
    property_category: str
    road_category: str
    jurisdiction_type: str
    total_area_decimal: float
    input_area_value: float
    input_area_unit: str
    unit_circle_rate: float
    calculated_land_value: float
    calculated_structure_value: float
    total_government_valuation: float
    declared_consideration: Optional[float] = None
    assessment_base: float
    stamp_duty_rate_percent: float
    stamp_duty_amount: float
    registration_fee_rate_percent: float
    registration_fee_amount: float
    municipal_surcharge_percent: float
    municipal_surcharge_amount: float
    total_statutory_charges: float
    concession_applied: Optional[str] = None
    discrepancy_status: str
    discrepancy_amount: float
    discrepancy_percentage: float
    discrepancy_explanation: str
    verification_status: str
    rule_version: str
    valuation_date: Optional[str] = None

class SectionValuationData(BaseModel):
    is_assessed: bool
    valuations: List[SectionValuationItem] = Field(default_factory=list)
    limitation_statement: str = VALUATION_REPORT_LIMITATION_STATEMENT

class ReportDataStructure(BaseModel):
    """
    Testable normalized data representation of all report sections including judicial risk and valuation.
    """
    section_1_cover: Section1CoverData
    section_2_revenue: Section2RevenueData
    section_3_cadastral: Section3CadastralData
    section_4_documents: List[Section4DocumentItem]
    section_5_field: Section5FieldData
    section_6_consistency: List[Section6ConsistencyItem]
    section_7_evidence: List[Section7EvidenceItem]
    section_8_findings_actions: List[Section8ActionItem]
    section_judicial_risk: Optional[SectionJudicialRiskData] = None
    section_valuation: Optional[SectionValuationData] = None
    verification_url: str
    verification_token: str
