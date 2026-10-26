"""
Property Passport Synthesis Service Orchestrator (TASK-P2-06).

Consolidates all upstream intelligence subsystems into a reproducible,
versioned parcel assessment with multi-tenant isolation and auditable review trails.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.parcel import Parcel
from app.models.case import Case
from app.models.land_passport import LandPassport
from app.models.passport_synthesis import (
    PassportAssessment,
    AssessmentFact,
    AssessmentInference,
    AssessmentFinding,
    AssessmentEvidenceGap,
    AssessmentReviewAction,
    AssessmentStatus,
    RiskTier,
    RiskDimension,
    FindingSeverity,
    FindingReviewStatus,
    InferenceReviewStatus,
    STATUTORY_SYNTHESIS_LIMITATION_STATEMENT,
)
from app.schemas.passport_synthesis import (
    GenerateAssessmentRequest,
    FindingReviewRequest,
    AssessmentRecomputeRequest,
)
from app.services.passport.reconciliation_engine import EvidenceReconciliationEngine
from app.services.passport.risk_evaluator import ExplainableRiskEvaluator

logger = logging.getLogger(__name__)


class PassportSynthesisService:
    """
    Orchestrates evidence-first Property Passport synthesis and risk assessment.
    """

    def __init__(self, db: Session):
        self.db = db

    def generate_assessment(
        self,
        parcel_id: uuid.UUID,
        org_id: uuid.UUID,
        request: GenerateAssessmentRequest,
        generated_by_user_id: Optional[uuid.UUID] = None,
    ) -> PassportAssessment:
        """
        Gathers evidence across all subsystems, executes reconciliation,
        computes explainable risk dimensions, and persists versioned assessment.
        """
        parcel = self.db.query(Parcel).filter(Parcel.parcel_id == parcel_id, Parcel.org_id == org_id).first()
        if not parcel:
            raise ValueError(f"Parcel {parcel_id} not found for organization {org_id}.")

        case = None
        if request.case_id:
            case = self.db.query(Case).filter(Case.case_id == request.case_id, Case.org_id == org_id).first()

        # 1. Reconcile evidence across all subsystems
        rec_result = EvidenceReconciliationEngine.reconcile_parcel_evidence(
            db=self.db,
            parcel=parcel,
            case=case,
            include_synthetic_fixtures=request.include_synthetic_fixtures,
        )

        facts_data = rec_result["facts"]
        inferences_data = rec_result["inferences"]
        findings_data = rec_result["findings"]
        gaps_data = rec_result["evidence_gaps"]
        summary_data = rec_result["reconciliation_summary"]

        # 2. Evaluate multidimensional risk & priority score
        overall_tier, composite_score, dimension_scores = ExplainableRiskEvaluator.evaluate_risk(
            findings=findings_data,
            evidence_gaps=gaps_data,
            facts=facts_data,
        )

        # 3. Determine assessment number and version
        existing_latest = (
            self.db.query(PassportAssessment)
            .filter(PassportAssessment.parcel_id == parcel_id, PassportAssessment.org_id == org_id)
            .order_by(PassportAssessment.version_number.desc())
            .first()
        )

        version_num = (existing_latest.version_number + 1) if existing_latest else 1
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        short_id = uuid.uuid4().hex[:6].upper()
        assessment_num = f"PPA-{today_str}-{short_id}-V{version_num}"

        # 4. Generate SHA-256 snapshot hash of inputs
        snapshot_payload = {
            "parcel_id": str(parcel_id),
            "version": version_num,
            "facts": facts_data,
            "inferences": inferences_data,
            "findings": findings_data,
            "gaps": gaps_data,
            "composite_score": composite_score,
            "tier": overall_tier.value,
        }
        snapshot_bytes = json.dumps(snapshot_payload, sort_keys=True, default=str).encode("utf-8")
        snapshot_hash = hashlib.sha256(snapshot_bytes).hexdigest()

        # 5. Create PassportAssessment record
        assessment = PassportAssessment(
            org_id=org_id,
            parcel_id=parcel_id,
            case_id=case.case_id if case else None,
            assessment_number=assessment_num,
            version_number=version_num,
            status=AssessmentStatus.COMPLETED,
            overall_risk_tier=overall_tier,
            composite_priority_score=composite_score,
            scoring_formula_version="v1.1-calibrated-separated-outputs",
            dimension_scores=dimension_scores,
            reconciliation_summary=summary_data,
            facts_count=len(facts_data),
            inferences_count=len(inferences_data),
            findings_count=len(findings_data),
            evidence_gaps_count=len(gaps_data),
            previous_assessment_id=existing_latest.assessment_id if existing_latest else None,
            sha256_snapshot_hash=snapshot_hash,
            statutory_disclaimer=STATUTORY_SYNTHESIS_LIMITATION_STATEMENT,
        )
        self.db.add(assessment)
        self.db.flush()

        # 6. Persist Facts
        for f in facts_data:
            fact_rec = AssessmentFact(
                assessment_id=assessment.assessment_id,
                subsystem=f["subsystem"],
                fact_category=f["fact_category"],
                source_reference=f["source_reference"],
                source_retrieval_date=f.get("source_retrieval_date"),
                applicable_date=f.get("applicable_date"),
                raw_value=f.get("raw_value", {}),
                normalized_value=f.get("normalized_value", {}),
                verification_status=f.get("verification_status", "UNVERIFIED"),
                limitations=f.get("limitations"),
            )
            self.db.add(fact_rec)

        # 7. Persist Inferences
        for inf in inferences_data:
            inf_rec = AssessmentInference(
                assessment_id=assessment.assessment_id,
                rule_id=inf["rule_id"],
                rule_version=inf.get("rule_version", "v1.0"),
                input_evidence_ids=inf.get("input_evidence_ids", []),
                inference_category=inf["inference_category"],
                explanation=inf["explanation"],
                assumptions=inf.get("assumptions"),
                confidence_score=inf.get("confidence_score", 0.50),
                uncertainty_representation=inf.get("uncertainty_representation", {}),
                review_status=inf.get("review_status", InferenceReviewStatus.AUTOMATED_VALIDATED),
            )
            self.db.add(inf_rec)

        # 8. Persist Findings
        for fd in findings_data:
            dim_val = fd["dimension"]
            if isinstance(dim_val, str):
                dim_val = RiskDimension(dim_val)
            sev_val = fd["severity"]
            if isinstance(sev_val, str):
                sev_val = FindingSeverity(sev_val)

            finding_rec = AssessmentFinding(
                assessment_id=assessment.assessment_id,
                dimension=dim_val,
                finding_code=fd["finding_code"],
                severity=sev_val,
                title=fd["title"],
                description=fd["description"],
                supporting_evidence=fd.get("supporting_evidence", {}),
                recommended_action=fd.get("recommended_action"),
                requires_human_review=fd.get("requires_human_review", False),
                review_status=FindingReviewStatus.UNREVIEWED,
            )
            self.db.add(finding_rec)

        # 9. Persist Evidence Gaps
        for g in gaps_data:
            gap_rec = AssessmentEvidenceGap(
                assessment_id=assessment.assessment_id,
                subsystem=g["subsystem"],
                gap_code=g["gap_code"],
                description=g["description"],
                impact_on_assessment=g["impact_on_assessment"],
                remedy_action=g.get("remedy_action"),
                is_blocking=g.get("is_blocking", False),
            )
            self.db.add(gap_rec)

        # 10. Update existing LandPassport if present
        if case:
            existing_passport = self.db.query(LandPassport).filter(LandPassport.case_id == case.case_id).first()
            if existing_passport:
                # Update transaction readiness state according to synthesis risk tier
                readiness_map = {
                    RiskTier.LOW: "TRANSACTION_READY",
                    RiskTier.MEDIUM: "CAUTION_REQUIRED",
                    RiskTier.HIGH: "HIGH_RISK_ACTION_REQUIRED",
                    RiskTier.CRITICAL: "CRITICAL_DEFECTS_DETECTED",
                    RiskTier.INSUFFICIENT_EVIDENCE: "INSUFFICIENT_EVIDENCE",
                }
                existing_passport.transaction_readiness_state = readiness_map.get(overall_tier, "CAUTION_REQUIRED")
                existing_passport.sha256_sealed_hash = snapshot_hash

        self.db.commit()
        self.db.refresh(assessment)
        return assessment

    def get_assessment(self, assessment_id: uuid.UUID, org_id: uuid.UUID) -> Optional[PassportAssessment]:
        return (
            self.db.query(PassportAssessment)
            .filter(PassportAssessment.assessment_id == assessment_id, PassportAssessment.org_id == org_id)
            .first()
        )

    def list_assessments_for_parcel(self, parcel_id: uuid.UUID, org_id: uuid.UUID) -> List[PassportAssessment]:
        return (
            self.db.query(PassportAssessment)
            .filter(PassportAssessment.parcel_id == parcel_id, PassportAssessment.org_id == org_id)
            .order_by(PassportAssessment.version_number.desc())
            .all()
        )

    def list_findings(self, assessment_id: uuid.UUID, org_id: uuid.UUID) -> List[AssessmentFinding]:
        assessment = self.get_assessment(assessment_id, org_id)
        if not assessment:
            raise ValueError(f"Assessment {assessment_id} not found.")
        return assessment.findings

    def list_evidence_gaps(self, assessment_id: uuid.UUID, org_id: uuid.UUID) -> List[AssessmentEvidenceGap]:
        assessment = self.get_assessment(assessment_id, org_id)
        if not assessment:
            raise ValueError(f"Assessment {assessment_id} not found.")
        return assessment.evidence_gaps

    def submit_finding_for_review(
        self,
        finding_id: uuid.UUID,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        notes: str,
    ) -> AssessmentFinding:
        finding = (
            self.db.query(AssessmentFinding)
            .join(PassportAssessment)
            .filter(AssessmentFinding.finding_id == finding_id, PassportAssessment.org_id == org_id)
            .first()
        )
        if not finding:
            raise ValueError(f"Finding {finding_id} not found for organization {org_id}.")

        prev_state = {"status": finding.review_status.value}
        finding.review_status = FindingReviewStatus.UNDER_REVIEW
        finding.review_notes = notes

        action = AssessmentReviewAction(
            assessment_id=finding.assessment_id,
            finding_id=finding.finding_id,
            user_id=user_id,
            action_type="SUBMIT_FOR_REVIEW",
            previous_state=prev_state,
            new_state={"status": finding.review_status.value},
            justification=notes,
        )
        self.db.add(action)
        self.db.commit()
        self.db.refresh(finding)
        return finding

    def record_finding_review(
        self,
        finding_id: uuid.UUID,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        request: FindingReviewRequest,
    ) -> AssessmentFinding:
        finding = (
            self.db.query(AssessmentFinding)
            .join(PassportAssessment)
            .filter(AssessmentFinding.finding_id == finding_id, PassportAssessment.org_id == org_id)
            .first()
        )
        if not finding:
            raise ValueError(f"Finding {finding_id} not found for organization {org_id}.")

        prev_state = {"status": finding.review_status.value}

        status_map = {
            "CONFIRM": FindingReviewStatus.CONFIRMED,
            "DISMISS": FindingReviewStatus.DISMISSED,
            "RESOLVE": FindingReviewStatus.RESOLVED,
            "MARK_UNDER_REVIEW": FindingReviewStatus.UNDER_REVIEW,
        }
        finding.review_status = status_map.get(request.action.upper(), FindingReviewStatus.CONFIRMED)
        finding.reviewed_by_user_id = user_id
        finding.reviewed_at = datetime.now(timezone.utc)
        finding.review_notes = request.review_notes

        action = AssessmentReviewAction(
            assessment_id=finding.assessment_id,
            finding_id=finding.finding_id,
            user_id=user_id,
            action_type=f"REVIEW_{request.action.upper()}",
            previous_state=prev_state,
            new_state={"status": finding.review_status.value},
            justification=request.review_notes,
        )
        self.db.add(action)
        self.db.commit()
        self.db.refresh(finding)
        return finding

    def recompute_assessment(
        self,
        assessment_id: uuid.UUID,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        request: AssessmentRecomputeRequest,
    ) -> PassportAssessment:
        """
        Recomputes an assessment after new evidence arrives.
        Marks earlier assessment as SUPERSEDED and produces a new versioned assessment.
        """
        old_assessment = self.get_assessment(assessment_id, org_id)
        if not old_assessment:
            raise ValueError(f"Assessment {assessment_id} not found.")

        # Mark old assessment as SUPERSEDED
        old_assessment.status = AssessmentStatus.SUPERSEDED

        # Generate new assessment version
        gen_req = GenerateAssessmentRequest(
            case_id=old_assessment.case_id,
            include_synthetic_fixtures=request.include_synthetic_fixtures,
            notes=f"Recomputed from {old_assessment.assessment_number}: {request.recompute_reason}",
        )
        new_assessment = self.generate_assessment(
            parcel_id=old_assessment.parcel_id,
            org_id=org_id,
            request=gen_req,
            generated_by_user_id=user_id,
        )

        # Log audit action
        action = AssessmentReviewAction(
            assessment_id=new_assessment.assessment_id,
            user_id=user_id,
            action_type="RECOMPUTE_ASSESSMENT",
            previous_state={"previous_assessment_id": str(old_assessment.assessment_id), "version": old_assessment.version_number},
            new_state={"new_assessment_id": str(new_assessment.assessment_id), "version": new_assessment.version_number},
            justification=request.recompute_reason,
        )
        self.db.add(action)
        self.db.commit()
        self.db.refresh(new_assessment)
        return new_assessment
