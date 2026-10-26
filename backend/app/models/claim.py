import uuid
import sqlalchemy as sa
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import GUID, JSONCompatible, utc_now
from app.models.evidence import AuthorityTier

class ClaimStatus(str):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    DISPUTED = "DISPUTED"
    REJECTED = "REJECTED"
    UNVERIFIED = "UNVERIFIED"
    CONFLICTING = "CONFLICTING"

class CandidateClaimStatus(str):
    CANDIDATE = "CANDIDATE"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CONFLICTING = "CONFLICTING"

class ClaimPredicate(str):
    RECORDED_OWNER = "RECORDED_OWNER"
    BUYER = "BUYER"
    SELLER = "SELLER"
    WITNESS = "WITNESS"
    PROPERTY_IDENTIFIER = "PROPERTY_IDENTIFIER"
    RECORDED_AREA = "RECORDED_AREA"
    MEASURED_AREA = "MEASURED_AREA"
    BOUNDARY_NORTH = "BOUNDARY_NORTH"
    BOUNDARY_SOUTH = "BOUNDARY_SOUTH"
    BOUNDARY_EAST = "BOUNDARY_EAST"
    BOUNDARY_WEST = "BOUNDARY_WEST"
    REGISTRATION_NUMBER = "REGISTRATION_NUMBER"
    REGISTRATION_DATE = "REGISTRATION_DATE"
    DEED_DATE = "DEED_DATE"
    DEED_VALUE = "DEED_VALUE"
    MUTATION_STATUS = "MUTATION_STATUS"
    DOCUMENT_REFERENCE = "DOCUMENT_REFERENCE"
    ENCUMBRANCE_REFERENCE = "ENCUMBRANCE_REFERENCE"
    LIEN_STATUS = "LIEN_STATUS"
    POSSESSION_HOLDER = "POSSESSION_HOLDER"
    CADASTRAL_GEOMETRY = "CADASTRAL_GEOMETRY"

class Claim(Base):
    __tablename__ = "claims"

    claim_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    case_id = sa.Column(GUID, sa.ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False, index=True)
    parcel_id = sa.Column(GUID, sa.ForeignKey("parcels.parcel_id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_id = sa.Column(GUID, sa.ForeignKey("evidence.evidence_id", ondelete="CASCADE"), nullable=False, index=True)
    
    subject_entity_type = sa.Column(sa.String(32), nullable=False) # 'PARCEL', 'PARTY'
    subject_id = sa.Column(GUID, nullable=False, index=True)
    predicate = sa.Column(sa.String(64), nullable=False, index=True)
    object_value = sa.Column(JSONCompatible, nullable=False)
    
    # Epistemic Metrics
    authority_tier = sa.Column(sa.String(32), nullable=False, default=AuthorityTier.USER_SUBMISSION)
    confidence_score = sa.Column(sa.Numeric(5, 2), nullable=False, default=1.0)
    
    # Temporal Dimensions (Mandatory Red-Team Fix)
    observed_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=utc_now)
    recorded_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    effective_from = sa.Column(sa.Date, nullable=True)
    effective_to = sa.Column(sa.Date, nullable=True)
    
    status = sa.Column(sa.String(32), nullable=False, default=ClaimStatus.ACTIVE, index=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    case = relationship("Case", back_populates="claims")
    parcel = relationship("Parcel", back_populates="claims")
    evidence = relationship("Evidence", back_populates="claims")
    candidate_claim = relationship("CandidateClaim", back_populates="materialized_claim", uselist=False)

class CandidateClaim(Base):
    """
    Epistemic staging claim extracted by OCR/parser/AI.
    Requires human review or validation before promotion to canonical Claim.
    """
    __tablename__ = "candidate_claims"

    candidate_claim_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    case_id = sa.Column(GUID, sa.ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = sa.Column(GUID, sa.ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False, index=True)
    version_id = sa.Column(GUID, sa.ForeignKey("document_versions.version_id", ondelete="CASCADE"), nullable=False, index=True)
    extracted_field_id = sa.Column(GUID, sa.ForeignKey("extracted_fields.field_id", ondelete="SET NULL"), nullable=True)
    evidence_span_id = sa.Column(GUID, sa.ForeignKey("evidence_spans.span_id", ondelete="SET NULL"), nullable=True)
    
    subject_entity_type = sa.Column(sa.String(32), nullable=False, default="PARCEL") # 'PARCEL', 'PARTY'
    subject_hint = sa.Column(JSONCompatible, nullable=True) # {"name": "...", "khata": "..."}
    predicate = sa.Column(sa.String(64), nullable=False, index=True)
    object_value = sa.Column(JSONCompatible, nullable=False)
    
    authority_tier = sa.Column(sa.String(32), nullable=False, default=AuthorityTier.USER_SUBMISSION)
    confidence_score = sa.Column(sa.Numeric(5, 2), nullable=False, default=1.0)
    
    # Temporal timestamps
    document_date = sa.Column(sa.Date, nullable=True)
    execution_date = sa.Column(sa.Date, nullable=True)
    registration_date = sa.Column(sa.Date, nullable=True)
    
    status = sa.Column(sa.String(32), nullable=False, default=CandidateClaimStatus.CANDIDATE, index=True)
    materialized_claim_id = sa.Column(GUID, sa.ForeignKey("claims.claim_id", ondelete="SET NULL"), nullable=True)
    
    review_notes = sa.Column(sa.Text, nullable=True)
    reviewed_by_user_id = sa.Column(GUID, sa.ForeignKey("users.user_id"), nullable=True)
    reviewed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    case = relationship("Case")
    document = relationship("Document")
    version = relationship("DocumentVersion")
    extracted_field = relationship("ExtractedField", back_populates="candidate_claims")
    evidence_span = relationship("EvidenceSpan")
    materialized_claim = relationship("Claim", back_populates="candidate_claim")
