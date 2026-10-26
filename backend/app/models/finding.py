import uuid
import sqlalchemy as sa
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import GUID, JSONCompatible, utc_now

class FindingSeverity(str):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFORMATIONAL = "INFORMATIONAL"

class FindingStatus(str):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    RESOLVED = "RESOLVED"
    ACCEPTED_WITH_REVIEW = "ACCEPTED_WITH_REVIEW"
    WONT_RESOLVE = "WONT_RESOLVE"
    SUPERSEDED = "SUPERSEDED"

class ActionStatus(str):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class Finding(Base):
    __tablename__ = "findings"

    finding_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    case_id = sa.Column(GUID, sa.ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False, index=True)
    parcel_id = sa.Column(GUID, sa.ForeignKey("parcels.parcel_id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id = sa.Column(sa.String(64), nullable=False, index=True)
    severity = sa.Column(sa.String(16), nullable=False, default=FindingSeverity.MEDIUM)
    status = sa.Column(sa.String(32), nullable=False, default=FindingStatus.OPEN, index=True)
    
    observed_values = sa.Column(JSONCompatible, nullable=False)
    explanation = sa.Column(sa.Text, nullable=False)
    recommended_action = sa.Column(sa.Text, nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    case = relationship("Case", back_populates="findings")
    parcel = relationship("Parcel", back_populates="findings")
    actions = relationship("RequiredAction", back_populates="finding", cascade="all, delete-orphan")
    resolutions = relationship("Resolution", back_populates="finding", cascade="all, delete-orphan")

class RequiredAction(Base):
    __tablename__ = "required_actions"

    action_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    finding_id = sa.Column(GUID, sa.ForeignKey("findings.finding_id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = sa.Column(GUID, sa.ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = sa.Column(sa.String(64), nullable=False)
    assigned_role = sa.Column(sa.String(32), nullable=False) # 'FIELD_AMIN', 'LEGAL_ADVOCATE', 'OPERATIONS_DESK'
    assigned_to_party_id = sa.Column(GUID, sa.ForeignKey("parties.party_id"), nullable=True)
    
    status = sa.Column(sa.String(32), nullable=False, default=ActionStatus.OPEN, index=True)
    resolution_notes = sa.Column(sa.Text, nullable=True)
    resolved_by_party_id = sa.Column(GUID, sa.ForeignKey("parties.party_id"), nullable=True)
    resolving_evidence_id = sa.Column(GUID, sa.ForeignKey("evidence.evidence_id"), nullable=True)
    resolved_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    finding = relationship("Finding", back_populates="actions")
    resolutions = relationship("Resolution", back_populates="action")

class Resolution(Base):
    __tablename__ = "resolutions"

    resolution_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    finding_id = sa.Column(GUID, sa.ForeignKey("findings.finding_id", ondelete="CASCADE"), nullable=False, index=True)
    action_id = sa.Column(GUID, sa.ForeignKey("required_actions.action_id", ondelete="CASCADE"), nullable=False, index=True)
    resolving_evidence_id = sa.Column(GUID, sa.ForeignKey("evidence.evidence_id"), nullable=False)
    reviewer_party_id = sa.Column(GUID, sa.ForeignKey("parties.party_id"), nullable=False)
    resolution_outcome = sa.Column(sa.String(64), nullable=False) # 'RESOLVED_VALID', 'RESOLVED_ENCROACHMENT_REMEDIED'
    notes = sa.Column(sa.Text, nullable=True)
    resolved_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    finding = relationship("Finding", back_populates="resolutions")
    action = relationship("RequiredAction", back_populates="resolutions")
