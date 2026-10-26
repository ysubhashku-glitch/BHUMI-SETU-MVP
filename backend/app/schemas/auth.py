from typing import Optional, Any
from pydantic import BaseModel, Field, ConfigDict

class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None
    request_id: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user_id: str
    tenant_id: str
    role: str

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    org_id: str
    full_name: str
    email: str
    phone_number: str
    role: str
    is_active: bool

