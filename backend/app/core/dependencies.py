import uuid
from typing import Callable, List, Optional
from fastapi import Depends, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.core.security import decode_access_token
from app.core.exceptions import UnauthorizedError, ForbiddenError

security_scheme = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    if not credentials:
        raise UnauthorizedError("Authentication token is missing.")
    
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise UnauthorizedError("Token payload missing subject.")
        user_id = uuid.UUID(user_id_str)
    except Exception as e:
        raise UnauthorizedError(f"Could not validate credentials: {str(e)}")
    
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise UnauthorizedError("User associated with this token does not exist.")
    if not user.is_active:
        raise ForbiddenError("User account is inactive.")
    
    return user

def require_roles(*allowed_roles) -> Callable[[User], User]:
    flattened = set()
    for item in allowed_roles:
        if isinstance(item, (list, tuple, set)):
            flattened.update(item)
        else:
            flattened.add(item)

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        authorized = set(flattened)
        if UserRole.CASE_OPERATOR in authorized or "OPERATOR" in authorized:
            authorized.add(UserRole.CASE_OPERATOR)
            authorized.add("OPERATOR")

        if current_user.role not in authorized:
            raise ForbiddenError(
                f"Role '{current_user.role}' is not authorized. Required: {', '.join(str(r) for r in flattened)}"
            )
        return current_user
    return role_checker

def get_current_tenant(current_user: User = Depends(get_current_user)) -> uuid.UUID:
    return current_user.org_id
