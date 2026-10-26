"""
Pydantic Schemas for Property Passport Synthesis & Explainable Land Risk Intelligence (TASK-P2-06).

Defines request, response, dimension breakdown, finding review,
and audit history models.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from app.models.passport_synthesis import (
    AssessmentStatus,
    RiskTier,
    RiskDimension,
    ReconciliationOutcome,
    FindingSeverity,
    FindingReviewStatus,
    InferenceReviewStatus,
    STATUTORY_SYNTHESIS_LIMITATION_STATEMENT,
)


class FactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fact_id: uuid.UUID
    assessment_id: uuid.UUID
    subsystem: str
    fact_category: str
    source_reference: str
    source_retrieval_date: Optional[datetime] = None
    applicable_date: Optional[datetime] = None
    raw_value: Dict[str, Any] = Field(default_factory=dict)
    normalized_value: Dict[str, Any] = Field(default_factory=dict)
    verification_status: str
    limitations: Optional[str] = None
    created_at: datetime


class InferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    inference_id: uuid.UUID
    assessment_id: uuid.UUID
    rule_id: str
    rule_version: str
    input_evidence_ids: List[str] = Field(default_factory=list)
    inference_category: str
    explanation: str
    assumptions: Optional[str] = None
    confidence_score: float
    uncertainty_representation: Dict[str, Any] = Field(default_factory=dict)
    review_status: InferenceReviewStatus
    created_at: datetime


class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    finding_id: uuid.UUID
    assessment_id: uuid.UUID
    dimension: RiskDimension
    finding_code: str
    severity: FindingSeverity
    title: str
    description: str
    supporting_evidence: Dict[str, Any] = Field(default_factory=dict)
    recommended_action: Optional[str] = None
    requires_human_review: bool
    review_status: FindingReviewStatus
    reviewed_by_user_id: Optional[uuid.UUID] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: datetime


class EvidenceGapResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    gap_id: uuid.UUID
    assessment_id: uuid.UUID
    subsystem: str
    gap_code: str
    description: str
    impact_on_assessment: str
    remedy_action: Optional[str] = None
    is_blocking: bool
    created_at: datetime


class ReviewActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action_id: uuid.UUID
    assessment_id: uuid.UUID
    finding_id: Optional[uuid.UUID] = None
    user_id: uuid.UUID
    action_type: str
    previous_state: Dict[str, Any] = Field(default_factory=dict)
    new_state: Dict[str, Any] = Field(default_factory=dict)
    justification: str
    created_at: datetime


class DimensionRiskAssessment(BaseModel):
    dimension: RiskDimension
    status: str
    severity: FindingSeverity
    dimension_priority_score: float  # 0.0 to 100.0 rule-based priority score
    findings_count: int
    evidence_gaps_count: int
    data_freshness: Optional[str] = None
    coverage_limitations: Optional[str] = None
    uncertainty_statement: Optional[str] = None
    recommended_action: Optional[str] = None
    requires_human_review: bool
    findings: List[FindingResponse] = Field(default_factory=list)
    evidence_gaps: List[EvidenceGapResponse] = Field(default_factory=list)


class PassportAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assessment_id: uuid.UUID
    org_id: uuid.UUID
    parcel_id: uuid.UUID
    case_id: Optional[uuid.UUID] = None
    assessment_number: str
    version_number: int
    status: AssessmentStatus
    overall_risk_tier: RiskTier
    composite_priority_score: float
    scoring_formula_version: str
    dimension_scores: Dict[str, Any] = Field(default_factory=dict)
    reconciliation_summary: Dict[str, Any] = Field(default_factory=dict)
    facts_count: int
    inferences_count: int
    findings_count: int
    evidence_gaps_count: int
    previous_assessment_id: Optional[uuid.UUID] = None
    sha256_snapshot_hash: str
    statutory_disclaimer: str = STATUTORY_SYNTHESIS_LIMITATION_STATEMENT
    created_at: datetime
    updated_at: datetime


class PassportAssessmentDetailResponse(PassportAssessmentResponse):
    dimension_assessments: Dict[str, DimensionRiskAssessment] = Field(default_factory=dict)
    facts: List[FactResponse] = Field(default_factory=list)
    inferences: List[InferenceResponse] = Field(default_factory=list)
    findings: List[FindingResponse] = Field(default_factory=list)
    evidence_gaps: List[EvidenceGapResponse] = Field(default_factory=list)
    review_actions: List[ReviewActionResponse] = Field(default_factory=list)


class GenerateAssessmentRequest(BaseModel):
    case_id: Optional[uuid.UUID] = None
    include_synthetic_fixtures: bool = Field(
        default=False,
        description="Whether to include synthetic rate fixtures/test data. Default False enforces production validation gate.",
    )
    notes: Optional[str] = None


class FindingReviewRequest(BaseModel):
    action: str = Field(..., description="'CONFIRM', 'DISMISS', 'RESOLVE', or 'MARK_UNDER_REVIEW'")
    review_notes: str


class AssessmentRecomputeRequest(BaseModel):
    include_synthetic_fixtures: bool = False
    recompute_reason: str = Field(..., description="Justification for recomputing assessment")
