import uuid
import sqlalchemy as sa
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import GUID, utc_now

class LandPassport(Base):
    __tablename__ = "land_passports"

    passport_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    case_id = sa.Column(GUID, sa.ForeignKey("cases.case_id", ondelete="CASCADE"), unique=True, nullable=False)
    parcel_id = sa.Column(GUID, sa.ForeignKey("parcels.parcel_id", ondelete="CASCADE"), nullable=False)
    passport_number = sa.Column(sa.String(32), unique=True, nullable=False, index=True)
    
    transaction_readiness_state = sa.Column(sa.String(32), nullable=False)
    statutory_tenancy_status = sa.Column(sa.String(32), nullable=False)
    area_variance_percentage = sa.Column(sa.Numeric(6, 2), nullable=True)
    
    sha256_sealed_hash = sa.Column(sa.String(64), nullable=False)
    pdf_storage_uri = sa.Column(sa.String(512), nullable=False)
    issued_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    case = relationship("Case", back_populates="passport")
    parcel = relationship("Parcel")
