from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.core.security import verify_password, create_access_token
from app.core.dependencies import get_current_user
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.core.exceptions import AuthenticationError

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/token", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise AuthenticationError("Invalid email or password.")
    
    if not user.is_active:
        raise AuthenticationError("User account is inactive.")

    token = create_access_token(
        data={
            "sub": str(user.user_id),
            "tenant_id": str(user.org_id),
            "role": user.role
        }
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_minutes=1440,
        user_id=str(user.user_id),
        tenant_id=str(user.org_id),
        role=user.role
    )

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        user_id=str(current_user.user_id),
        org_id=str(current_user.org_id),
        full_name=current_user.full_name,
        email=current_user.email,
        phone_number=current_user.phone_number,
        role=current_user.role,
        is_active=current_user.is_active
    )
