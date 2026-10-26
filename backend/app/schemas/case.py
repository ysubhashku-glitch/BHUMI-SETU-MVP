from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

class CaseCreateRequest(BaseModel):
    primary_client_party_id: str
    target_transaction_type: Optional[str] = "PURCHASE"
    target_price_inr: Optional[float] = None
    initial_parcel_id: Optional[str] = None

class CaseUpdateRequest(BaseModel):
    assigned_amin_id: Optional[str] = None
    assigned_advocate_id: Optional[str] = None

class CaseTransitionRequest(BaseModel):
    next_status: str
    transition_reason: Optional[str] = None

class CaseParcelAddRequest(BaseModel):
    parcel_id: str
    is_primary: bool = True

class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: str
    org_id: str
    case_number: str
    primary_client_party_id: str
    assigned_amin_id: Optional[str] = None
    assigned_advocate_id: Optional[str] = None
    status: str
    transaction_readiness_state: str
    target_transaction_id: Optional[str] = None
    linked_parcel_ids: List[str] = []

