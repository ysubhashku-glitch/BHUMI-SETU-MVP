import uuid
import sqlalchemy as sa
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import GUID, utc_now

class CaseStatus(str):
    DRAFT = "DRAFT"
    PROPERTY_IDENTIFIED = "PROPERTY_IDENTIFIED"
    DATA_COLLECTION = "DATA_COLLECTION"
    DOCUMENT_COLLECTION = "DOCUMENT_COLLECTION"
    PROCESSING = "PROCESSING"
    ANALYSIS = "ANALYSIS"
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"
    FIELD_VERIFICATION = "FIELD_VERIFICATION"
    LEGAL_REVIEW = "LEGAL_REVIEW"
    REPORT_DRAFT = "REPORT_DRAFT"
    REPORT_REVIEW = "REPORT_REVIEW"
    FINAL = "FINAL"
    # Exceptional States
    BLOCKED = "BLOCKED"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    CONFLICTING_DATA = "CONFLICTING_DATA"
    CANCELLED = "CANCELLED"

class TransactionReadinessState(str):
    NOT_READY = "NOT_READY"
    REQUIRES_CONDITIONAL_RESOLUTION = "REQUIRES_CONDITIONAL_RESOLUTION"
    BLOCKED_STATUTORY_HAZARD = "BLOCKED_STATUTORY_HAZARD"
    READY_FOR_LEGAL_CLOSING = "READY_FOR_LEGAL_CLOSING"

class Case(Base):
    __tablename__ = "cases"

    case_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False, index=True)
    case_number = sa.Column(sa.String(32), unique=True, nullable=False, index=True)
    primary_client_party_id = sa.Column(GUID, sa.ForeignKey("parties.party_id"), nullable=False)
    assigned_amin_id = sa.Column(GUID, sa.ForeignKey("users.user_id"), nullable=True)
    assigned_advocate_id = sa.Column(GUID, sa.ForeignKey("users.user_id"), nullable=True)
    
    status = sa.Column(sa.String(32), nullable=False, default=CaseStatus.DRAFT, index=True)
    transaction_readiness_state = sa.Column(sa.String(32), nullable=False, default=TransactionReadinessState.NOT_READY)
    target_transaction_id = sa.Column(GUID, sa.ForeignKey("transactions.transaction_id"), nullable=True)
    
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    organization = relationship("Organization", back_populates="cases")
    client_party = relationship("Party", back_populates="cases")
    target_transaction = relationship("Transaction", back_populates="cases")
    assigned_amin = relationship("User", foreign_keys=[assigned_amin_id])
    assigned_advocate = relationship("User", foreign_keys=[assigned_advocate_id])
    
    parcel_associations = relationship("CaseParcel", back_populates="case", cascade="all, delete-orphan")
    evidence_associations = relationship("CaseEvidence", back_populates="case", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="case", cascade="all, delete-orphan")
    findings = relationship("Finding", back_populates="case", cascade="all, delete-orphan")
    surveys = relationship("FieldSurvey", back_populates="case", cascade="all, delete-orphan")
    field_tasks = relationship("FieldVerificationTask", back_populates="case", cascade="all, delete-orphan")
    passport = relationship("LandPassport", back_populates="case", uselist=False, cascade="all, delete-orphan")
    reports = relationship("LandIntelligenceReport", back_populates="case", cascade="all, delete-orphan")

class CaseParcel(Base):
    __tablename__ = "case_parcels"

    case_id = sa.Column(GUID, sa.ForeignKey("cases.case_id", ondelete="CASCADE"), primary_key=True)
    parcel_id = sa.Column(GUID, sa.ForeignKey("parcels.parcel_id", ondelete="CASCADE"), primary_key=True)
    is_primary = sa.Column(sa.Boolean, default=True, nullable=False)

    case = relationship("Case", back_populates="parcel_associations")
    parcel = relationship("Parcel", back_populates="case_associations")
