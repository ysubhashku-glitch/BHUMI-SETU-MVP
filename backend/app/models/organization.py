import uuid
import sqlalchemy as sa
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import GUID, utc_now

class Organization(Base):
    __tablename__ = "organizations"

    org_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    name = sa.Column(sa.String(128), nullable=False)
    slug = sa.Column(sa.String(64), unique=True, nullable=False, index=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    parcels = relationship("Parcel", back_populates="organization")
    cases = relationship("Case", back_populates="organization")
