import os
import uuid
import re
from dataclasses import dataclass
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.core.security import decode_access_token
from app.core.exceptions import UnauthorizedError, ForbiddenError

@dataclass
class PrincipalContext:
    user: User
    user_id: uuid.UUID
    org_id: uuid.UUID
    role: str
    email: str

def authenticate_mcp_request(
    db: Session,
    auth_token: Optional[str] = None
) -> PrincipalContext:
    """
    Resolves caller identity for an MCP request.
    Extracts JWT bearer token from tool argument or environment variable fallback.
    Enforces that an active User and Organization exist in the database.
    """
    token = auth_token or os.getenv("BHUMI_SETU_MCP_TOKEN") or os.getenv("BHUMI_SETU_MCP_API_KEY")
    if not token:
        raise UnauthorizedError(
            "Authentication token is missing. A valid JWT access token must be provided via the 'auth_token' argument "
            "or the BHUMI_SETU_MCP_TOKEN environment variable."
        )

    clean_token = token.strip()
    if clean_token.lower().startswith("bearer "):
        clean_token = clean_token[7:].strip()

    try:
        payload = decode_access_token(clean_token)
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise UnauthorizedError("Token payload missing 'sub' subject identifier.")
        user_id = uuid.UUID(user_id_str)
    except Exception as e:
        raise UnauthorizedError(f"Invalid or expired authentication token: {str(e)}")

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise UnauthorizedError("User associated with this token does not exist in the platform.")
    if not user.is_active:
        raise ForbiddenError("User account is inactive or disabled.")

    return PrincipalContext(
        user=user,
        user_id=user.user_id,
        org_id=user.org_id,
        role=user.role,
        email=user.email
    )

def check_mcp_role(context: PrincipalContext, *allowed_roles: str) -> None:
    """
    Enforces role-based permissions for MCP state-changing or privileged tools.
    """
    if context.role not in allowed_roles:
        raise ForbiddenError(
            f"Role '{context.role}' is not authorized for this operation. Required: {', '.join(allowed_roles)}"
        )

def sanitize_untrusted_text(text: Optional[str], max_length: int = 1000) -> str:
    """
    Sanitizes untrusted OCR or user narrative text before returning to the model,
    neutralizing common prompt-injection tokens and bounding size.
    """
    if not text:
        return "N/A"
    
    # Strip dangerous pseudo-system tokens
    s = str(text)
    s = re.sub(r"(?i)<\s*system\s*>", "[SYSTEM_TAG_STRIPPED]", s)
    s = re.sub(r"(?i)<\s*/\s*system\s*>", "[/SYSTEM_TAG_STRIPPED]", s)
    s = re.sub(r"(?i)ignore\s+previous\s+instructions", "[INSTRUCTION_OVERRIDE_PREVENTED]", s)
    s = re.sub(r"(?i)disregard\s+all\s+prior", "[INSTRUCTION_OVERRIDE_PREVENTED]", s)
    
    return s.strip()[:max_length]
