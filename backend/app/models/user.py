import uuid
import sqlalchemy as sa
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import GUID, utc_now

class UserRole(str):
    ADMIN = "ADMIN"
    SUPERVISOR = "SUPERVISOR"
    CASE_OPERATOR = "CASE_OPERATOR"
    OPERATOR = "CASE_OPERATOR"
    ANALYST = "ANALYST"
    FIELD_EXPERT = "FIELD_EXPERT"
    LEGAL_REVIEWER = "LEGAL_REVIEWER"
    REVIEWER = "REVIEWER"

class User(Base):
    __tablename__ = "users"

    user_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False, index=True)
    full_name = sa.Column(sa.String(128), nullable=False)
    email = sa.Column(sa.String(128), unique=True, nullable=False, index=True)
    hashed_password = sa.Column(sa.String(256), nullable=False)
    phone_number = sa.Column(sa.String(20), nullable=False)
    role = sa.Column(sa.String(32), nullable=False, default=UserRole.CASE_OPERATOR)
    is_active = sa.Column(sa.Boolean, default=True, nullable=False)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    organization = relationship("Organization", back_populates="users")

    def __init__(self, **kwargs):
        if "phone_number" not in kwargs or not kwargs["phone_number"]:
            kwargs["phone_number"] = "+919000000000"
        super().__init__(**kwargs)
