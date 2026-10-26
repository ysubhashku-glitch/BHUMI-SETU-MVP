from typing import Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class EvidenceCreateRequest(BaseModel):
    evidence_type: str
    authority_tier: str = "USER_SUBMISSION"
    source_name: str
    storage_uri: str
    sha256_hash: str
    captured_by_party_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class CaseEvidenceAddRequest(BaseModel):
    evidence_id: str

class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evidence_id: str
    evidence_type: str
    authority_tier: str
    source_name: str
    storage_uri: str
    sha256_hash: str
    captured_by_party_id: Optional[str] = None
    captured_at: datetime
    evidence_metadata: Dict[str, Any]

class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    storage_uri: str
    sha256_hash: str
    processing_status: str

