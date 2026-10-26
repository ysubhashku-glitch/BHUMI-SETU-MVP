from typing import Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class FindingCreateRequest(BaseModel):
    case_id: str
    parcel_id: str
    rule_id: str
    severity: str = "MEDIUM"
    status: str = "OPEN"
    observed_values: Dict[str, Any]
    explanation: str
    recommended_action: Optional[str] = None

class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    finding_id: str
    case_id: str
    parcel_id: str
    rule_id: str
    severity: str
    status: str
    observed_values: Dict[str, Any]
    explanation: str
    recommended_action: Optional[str] = None

class ActionCreateRequest(BaseModel):
    action_type: str
    assigned_role: str = "FIELD_AMIN"
    assigned_to_party_id: Optional[str] = None

class ActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action_id: str
    finding_id: str
    case_id: str
    action_type: str
    assigned_role: str
    assigned_to_party_id: Optional[str] = None
    status: str
    resolution_notes: Optional[str] = None
    resolved_by_party_id: Optional[str] = None
    resolving_evidence_id: Optional[str] = None
    resolved_at: Optional[datetime] = None

class ResolutionCreateRequest(BaseModel):
    action_id: str
    resolving_evidence_id: str
    reviewer_party_id: str
    resolution_outcome: str
    notes: Optional[str] = None

class ResolutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    resolution_id: str
    finding_id: str
    action_id: str
    resolving_evidence_id: str
    reviewer_party_id: str
    resolution_outcome: str
    notes: Optional[str] = None
    resolved_at: datetime

