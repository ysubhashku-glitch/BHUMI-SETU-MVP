import uuid
import sqlalchemy as sa
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import GUID, JSONCompatible, utc_now

class PropertyEventType(str):
    SALE = "SALE"
    TRANSFER = "TRANSFER"
    REGISTRATION = "REGISTRATION"
    MUTATION = "MUTATION"
    PARTITION = "PARTITION"
    INHERITANCE = "INHERITANCE"
    MORTGAGE = "MORTGAGE"
    RELEASE = "RELEASE"
    SUBDIVISION = "SUBDIVISION"
    CONSOLIDATION = "CONSOLIDATION"
    SURVEY = "SURVEY"
    LEGAL_EVENT = "LEGAL_EVENT"
    OTHER = "OTHER"

class PropertyEvent(Base):
    __tablename__ = "property_events"

    event_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    parcel_id = sa.Column(GUID, sa.ForeignKey("parcels.parcel_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = sa.Column(sa.String(32), nullable=False)
    
    event_date = sa.Column(sa.Date, nullable=True)
    recorded_date = sa.Column(sa.Date, nullable=True)
    effective_date = sa.Column(sa.Date, nullable=True)
    
    source_authority = sa.Column(sa.String(128), nullable=False)
    evidence_id = sa.Column(GUID, sa.ForeignKey("evidence.evidence_id", ondelete="SET NULL"), nullable=True)
    event_metadata = sa.Column(JSONCompatible, nullable=False, default=dict)
    
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)
