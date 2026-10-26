from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class MCPToolResponse(BaseModel):
    success: bool
    status: str = Field(description="Outcome status, e.g. SUCCESS or ERROR")
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, str]] = None
    disclaimer: Optional[str] = None

class ParcelSummaryResponse(BaseModel):
    parcel_id: str
    bhumi_id: str
    administrative_hierarchy: Dict[str, str]
    khata_number: str
    plot_khesra_number: str
    recorded_area_acres: float
    land_nature: str
    revenue_records_available: bool
    cadastral_geometry_available: bool
    document_evidence_count: int
    field_verification_status: Optional[str]
    open_discrepancies_count: int
    disclaimer: str

class RevenueSummaryResponse(BaseModel):
    parcel_id: str
    khata_number: str
    plot_khesra_number: str
    jamabandi_number: Optional[str]
    recorded_area_original: Optional[str]
    recorded_area_acres: float
    recorded_raiyat: Optional[str]
    source_provenance: str
    retrieval_timestamp: Optional[str]
    verification_status: str
    disclaimer: str

class SpatialSummaryResponse(BaseModel):
    parcel_id: str
    geometry_available: bool
    crs: str
    geometry_validation_status: str
    recorded_area_acres: float
    calculated_area_acres: Optional[float]
    area_delta_acres: Optional[float]
    variance_percentage: Optional[float]
    comparison_outcome: str
    spatial_provenance: str
    disclaimer: str

class DocumentSummaryResponse(BaseModel):
    case_id: str
    documents_count: int
    documents: List[Dict[str, Any]]
    disclaimer: str

class EvidenceRegisterResponse(BaseModel):
    case_id: str
    evidence_count: int
    evidence_items: List[Dict[str, Any]]

class ConsistencyFindingsResponse(BaseModel):
    case_id: str
    findings_count: int
    findings: List[Dict[str, Any]]
    disclaimer: str

class FieldVerificationStatusResponse(BaseModel):
    task_id: Optional[str]
    tasks_count: int
    tasks: List[Dict[str, Any]]
    disclaimer: str

class FieldVerificationCreateResponse(BaseModel):
    task_id: str
    task_number: str
    status: str
    priority: str
    case_id: str
    parcel_id: Optional[str]
    created_at: str
    message: str

class ReportMetadataResponse(BaseModel):
    report_id: str
    report_number: str
    version_number: int
    status: str
    sha256_hash: str
    page_count: int
    file_size_bytes: int
    created_at: str
    verification_url: str
    summary_counts: Dict[str, Any]

class ReportGenerateResponse(BaseModel):
    report_id: str
    report_number: str
    version_number: int
    status: str
    sha256_hash: str
    verification_url: str
    page_count: int
    file_size_bytes: int
    message: str
    disclaimer: str

class ReportIntegrityResponse(BaseModel):
    is_valid: bool
    is_authentic: Optional[bool] = None
    status: str
    report_number: Optional[str] = None
    version_number: Optional[int] = None
    issued_at: Optional[Any] = None
    sha256_hash: Optional[str] = None
    hash_matches_stored_file: bool = False
    scope: Optional[str] = None
    scope_summary: Optional[Dict[str, Any]] = None
    disclaimer: str
