import uuid
import sqlalchemy as sa
from app.database import Base
from app.models.base import GUID, JSONCompatible, utc_now

class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False, index=True)
    actor_party_id = sa.Column(GUID, sa.ForeignKey("parties.party_id", ondelete="SET NULL"), nullable=True, index=True)
    action = sa.Column(sa.String(64), nullable=False, index=True)
    entity_name = sa.Column(sa.String(32), nullable=False, index=True)
    entity_id = sa.Column(GUID, nullable=False, index=True)
    previous_state = sa.Column(JSONCompatible, nullable=True)
    new_state = sa.Column(JSONCompatible, nullable=True)
    ip_address = sa.Column(sa.String(45), nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False, index=True)
