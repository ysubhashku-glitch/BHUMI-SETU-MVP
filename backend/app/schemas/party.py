from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class PartyCreateRequest(BaseModel):
    party_type: str = "PERSON"
    primary_name: str
    canonical_transliterated_name: Optional[str] = None
    father_or_husband_name: Optional[str] = None
    relationship_type: Optional[str] = "SON_OF"
    community_caste_category: str = "GENERAL"  # Lawful purpose: SPT/CNT statutory checks
    is_tribal: bool = False
    phone_number: Optional[str] = None
    residence_village_lgd: Optional[str] = None

class PartyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    party_id: str
    org_id: str
    party_type: str
    primary_name: str
    canonical_transliterated_name: Optional[str] = None
    father_or_husband_name: Optional[str] = None
    relationship_type: Optional[str] = None
    community_caste_category: str
    is_tribal: bool
    phone_number: Optional[str] = None
    residence_village_lgd: Optional[str] = None

