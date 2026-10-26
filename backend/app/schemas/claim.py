from typing import Optional, Any, Dict
from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict

class ClaimCreateRequest(BaseModel):
    case_id: str
    parcel_id: str
    evidence_id: str
    subject_entity_type: str = "PARCEL"
    subject_id: str
    predicate: str
    object_value: Dict[str, Any]
    authority_tier: str = "USER_SUBMISSION"
    confidence_score: float = 1.0
    recorded_at: Optional[datetime] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    status: str = "ACTIVE"

class ClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    claim_id: str
    case_id: str
    parcel_id: str
    evidence_id: str
    subject_entity_type: str
    subject_id: str
    predicate: str
    object_value: Dict[str, Any]
    authority_tier: str
    confidence_score: float
    observed_at: datetime
    recorded_at: Optional[datetime] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    status: str

