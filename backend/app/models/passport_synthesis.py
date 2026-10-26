"""
Property Passport Synthesis and Land Risk Intelligence Models (TASK-P2-06).

Defines the core data model for evidence-first synthesis:
- PassportAssessment: Top-level versioned parcel intelligence assessment
- AssessmentFact: Ground observed facts with immutable source attribution
- AssessmentInference: Deterministic inferences with rule versioning and uncertainty
- AssessmentFinding: Review findings categorized across 8 risk dimensions
- AssessmentEvidenceGap: Explicit representation of missing, stale, or unavailable evidence
- AssessmentReviewAction: Auditable human review trail for findings and assessments

Enforces strict epistemic rules:
1. Never certifies legal title, clear ownership, or legally authoritative boundaries.
2. Distinguishes observed facts from derived inferences and system inferences.
3. Explicitly surfaces evidence gaps rather than assuming missing records mean zero risk.
"""

from __future__ import annotations

import enum
import uuid
import sqlalchemy as sa
from sqlalchemy.orm import relationship, synonym
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base
from app.models.base import GUID, utc_now

# SQLite compatibility fallback for JSONB
JSONType = JSONB().with_variant(sa.JSON, "sqlite")

STATUTORY_SYNTHESIS_LIMITATION_STATEMENT = (
    "Bhumi Setu provides evidence-based land intelligence and due-diligence assistance. "
    "Its findings do not establish legal title, guarantee possession, certify boundaries, "
    "or replace review of authoritative records and qualified legal advice."
)


class AssessmentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    COMPLETED = "COMPLETED"
    SUPERSEDED = "SUPERSEDED"
    REQUIRES_HUMAN_REVIEW = "REQUIRES_HUMAN_REVIEW"


class RiskTier(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class RiskDimension(str, enum.Enum):
    REVENUE_RECORD = "REVENUE_RECORD"
    TRANSACTION_MUTATION = "TRANSACTION_MUTATION"
    JUDICIAL_LITIGATION = "JUDICIAL_LITIGATION"
    CADASTRAL_SPATIAL = "CADASTRAL_SPATIAL"
    BOUNDARY_FIELD = "BOUNDARY_FIELD"
    DOCUMENT_AUTHENTICITY = "DOCUMENT_AUTHENTICITY"
    VALUATION_STATUTORY = "VALUATION_STATUTORY"
    EVIDENCE_COMPLETENESS = "EVIDENCE_COMPLETENESS"


class ReconciliationOutcome(str, enum.Enum):
    CONSISTENT_WITHIN_DEFINED_TOLERANCE = "CONSISTENT_WITHIN_DEFINED_TOLERANCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    POTENTIAL_MATCH_REQUIRES_REVIEW = "POTENTIAL_MATCH_REQUIRES_REVIEW"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FindingSeverity(str, enum.Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FindingReviewStatus(str, enum.Enum):
    UNREVIEWED = "UNREVIEWED"
    UNDER_REVIEW = "UNDER_REVIEW"
    CONFIRMED = "CONFIRMED"
    DISMISSED = "DISMISSED"
    RESOLVED = "RESOLVED"


class InferenceReviewStatus(str, enum.Enum):
    AUTOMATED_VALIDATED = "AUTOMATED_VALIDATED"
    PENDING_REVIEW = "PENDING_REVIEW"
    HUMAN_CONFIRMED = "HUMAN_CONFIRMED"
    HUMAN_REJECTED = "HUMAN_REJECTED"


class PassportAssessment(Base):
    """
    Versioned, reproducible parcel intelligence synthesis assessment.
    Consolidates revenue, cadastral, OCR, field survey, judicial, valuation,
    and mutation evidence without duplicating source records.
    """
    __tablename__ = "passport_assessments"

    assessment_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False, index=True)
    parcel_id = sa.Column(GUID, sa.ForeignKey("parcels.parcel_id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = sa.Column(GUID, sa.ForeignKey("cases.case_id", ondelete="SET NULL"), nullable=True, index=True)

    assessment_number = sa.Column(sa.String(64), unique=True, nullable=False, index=True)
    version_number = sa.Column(sa.Integer, default=1, nullable=False)
    status = sa.Column(sa.Enum(AssessmentStatus), default=AssessmentStatus.COMPLETED, nullable=False)

    overall_risk_tier = sa.Column(sa.Enum(RiskTier), default=RiskTier.MEDIUM, nullable=False)
    composite_priority_score = sa.Column(sa.Numeric(5, 2), nullable=False)  # 0.00 to 100.00 diligence priority score
    scoring_formula_version = sa.Column(sa.String(32), default="v1.0-deterministic-weighted", nullable=False)

    dimension_scores = sa.Column(JSONType, default=dict, nullable=False)
    reconciliation_summary = sa.Column(JSONType, default=dict, nullable=False)

    facts_count = sa.Column(sa.Integer, default=0, nullable=False)
    inferences_count = sa.Column(sa.Integer, default=0, nullable=False)
    findings_count = sa.Column(sa.Integer, default=0, nullable=False)
    evidence_gaps_count = sa.Column(sa.Integer, default=0, nullable=False)

    previous_assessment_id = sa.Column(GUID, sa.ForeignKey("passport_assessments.assessment_id", ondelete="SET NULL"), nullable=True)
    sha256_snapshot_hash = sa.Column(sa.String(64), nullable=False)
    statutory_disclaimer = sa.Column(sa.Text, default=STATUTORY_SYNTHESIS_LIMITATION_STATEMENT, nullable=False)

    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    parcel = relationship("Parcel", back_populates="passport_assessments")
    case = relationship("Case", back_populates="passport_assessments")
    facts = relationship("AssessmentFact", back_populates="assessment", cascade="all, delete-orphan", order_by="AssessmentFact.created_at")
    inferences = relationship("AssessmentInference", back_populates="assessment", cascade="all, delete-orphan", order_by="AssessmentInference.created_at")
    findings = relationship("AssessmentFinding", back_populates="assessment", cascade="all, delete-orphan", order_by="AssessmentFinding.created_at")
    evidence_gaps = relationship("AssessmentEvidenceGap", back_populates="assessment", cascade="all, delete-orphan", order_by="AssessmentEvidenceGap.created_at")
    review_actions = relationship("AssessmentReviewAction", back_populates="assessment", cascade="all, delete-orphan", order_by="AssessmentReviewAction.created_at")


class AssessmentFact(Base):
    """
    Information directly present in an identified source or explicitly recorded by a qualified field observer.
    """
    __tablename__ = "assessment_facts"

    fact_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    assessment_id = sa.Column(GUID, sa.ForeignKey("passport_assessments.assessment_id", ondelete="CASCADE"), nullable=False, index=True)

    subsystem = sa.Column(sa.String(32), nullable=False)  # REVENUE, CADASTRAL_SPATIAL, OCR_DOCUMENT, FIELD_SURVEY, JUDICIAL, VALUATION, MUTATION
    fact_category = sa.Column(sa.String(64), nullable=False)
    source_reference = sa.Column(sa.String(256), nullable=False)
    source_retrieval_date = sa.Column(sa.DateTime(timezone=True), nullable=True)
    applicable_date = sa.Column(sa.DateTime(timezone=True), nullable=True)

    raw_value = sa.Column(JSONType, default=dict, nullable=False)
    normalized_value = sa.Column(JSONType, default=dict, nullable=False)
    verification_status = sa.Column(sa.String(32), default="UNVERIFIED", nullable=False)
    limitations = sa.Column(sa.Text, nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    assessment = relationship("PassportAssessment", back_populates="facts")


class AssessmentInference(Base):
    """
    Conclusions produced by deterministic rules or documented analytical methods.
    """
    __tablename__ = "assessment_inferences"

    inference_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    assessment_id = sa.Column(GUID, sa.ForeignKey("passport_assessments.assessment_id", ondelete="CASCADE"), nullable=False, index=True)

    rule_id = sa.Column(sa.String(64), nullable=False, index=True)
    rule_version = sa.Column(sa.String(32), default="v1.0", nullable=False)
    input_evidence_ids = sa.Column(JSONType, default=list, nullable=False)
    inference_category = sa.Column(sa.String(64), nullable=False)
    explanation = sa.Column(sa.Text, nullable=False)
    assumptions = sa.Column(sa.Text, nullable=True)

    confidence_score = sa.Column(sa.Numeric(4, 2), default=0.50, nullable=False)
    uncertainty_representation = sa.Column(JSONType, default=dict, nullable=False)
    review_status = sa.Column(sa.Enum(InferenceReviewStatus), default=InferenceReviewStatus.AUTOMATED_VALIDATED, nullable=False)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    assessment = relationship("PassportAssessment", back_populates="inferences")


class AssessmentFinding(Base):
    """
    Issues that require an authorized human to inspect the underlying evidence,
    categorized across the 8 Land Intelligence Risk Dimensions.
    """
    __tablename__ = "assessment_findings"

    finding_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    assessment_id = sa.Column(GUID, sa.ForeignKey("passport_assessments.assessment_id", ondelete="CASCADE"), nullable=False, index=True)

    dimension = sa.Column(sa.Enum(RiskDimension), nullable=False, index=True)
    finding_code = sa.Column(sa.String(64), nullable=False, index=True)
    severity = sa.Column(sa.Enum(FindingSeverity), default=FindingSeverity.INFO, nullable=False)

    title = sa.Column(sa.String(256), nullable=False)
    description = sa.Column(sa.Text, nullable=False)
    supporting_evidence = sa.Column(JSONType, default=dict, nullable=False)
    recommended_action = sa.Column(sa.Text, nullable=True)

    requires_human_review = sa.Column(sa.Boolean, default=False, nullable=False)
    review_status = sa.Column(sa.Enum(FindingReviewStatus), default=FindingReviewStatus.UNREVIEWED, nullable=False)
    reviewed_by_user_id = sa.Column(GUID, sa.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    reviewed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    review_notes = sa.Column(sa.Text, nullable=True)

    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    assessment = relationship("PassportAssessment", back_populates="findings")
    reviewer = relationship("User")


class AssessmentEvidenceGap(Base):
    """
    Explicitly represents unavailable, stale, or insufficient evidence.
    Never silently converted into clean results or zero risk.
    """
    __tablename__ = "assessment_evidence_gaps"

    gap_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    assessment_id = sa.Column(GUID, sa.ForeignKey("passport_assessments.assessment_id", ondelete="CASCADE"), nullable=False, index=True)

    subsystem = sa.Column(sa.String(32), nullable=False)
    dimension = synonym("subsystem")
    gap_code = sa.Column(sa.String(64), nullable=False, index=True)
    description = sa.Column(sa.Text, nullable=False)
    impact_on_assessment = sa.Column(sa.Text, nullable=False)
    remedy_action = sa.Column(sa.Text, nullable=True)
    is_blocking = sa.Column(sa.Boolean, default=False, nullable=False)

    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    assessment = relationship("PassportAssessment", back_populates="evidence_gaps")

    @property
    def title(self) -> str:
        return self.gap_code

    def __init__(self, **kwargs):
        if "dimension" in kwargs and "subsystem" not in kwargs:
            val = kwargs.pop("dimension")
            kwargs["subsystem"] = val.value if hasattr(val, "value") else str(val)
        if "subsystem" in kwargs and hasattr(kwargs["subsystem"], "value"):
            kwargs["subsystem"] = kwargs["subsystem"].value
        super().__init__(**kwargs)


class AssessmentReviewAction(Base):
    """
    Auditable history of reviewer actions, score overrides, and manual confirmations.
    """
    __tablename__ = "assessment_review_actions"

    action_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    assessment_id = sa.Column(GUID, sa.ForeignKey("passport_assessments.assessment_id", ondelete="CASCADE"), nullable=False, index=True)
    finding_id = sa.Column(GUID, sa.ForeignKey("assessment_findings.finding_id", ondelete="SET NULL"), nullable=True)
    user_id = sa.Column(GUID, sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)

    action_type = sa.Column(sa.String(64), nullable=False)  # SUBMIT_REVIEW, CONFIRM_FINDING, DISMISS_FINDING, OVERRIDE_SCORE, RECOMPUTE
    previous_state = sa.Column(JSONType, default=dict, nullable=False)
    new_state = sa.Column(JSONType, default=dict, nullable=False)
    justification = sa.Column(sa.Text, nullable=False)

    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    assessment = relationship("PassportAssessment", back_populates="review_actions")
    user = relationship("User")
