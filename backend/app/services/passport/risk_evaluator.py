"""
Explainable Multi-Dimensional Land Risk Evaluator (TASK-P2-06).

Evaluates the 8 separate Land Intelligence risk dimensions:
1. REVENUE_RECORD
2. TRANSACTION_MUTATION
3. JUDICIAL_LITIGATION
4. CADASTRAL_SPATIAL
5. BOUNDARY_FIELD
6. DOCUMENT_AUTHENTICITY
7. VALUATION_STATUTORY
8. EVIDENCE_COMPLETENESS

Scoring Formula and Rationale:
- The Composite Priority Score is a deterministic rule-based diligence priority index (0.00 to 100.00)
  calibrated to rank the density and severity of legal, cadastral, and physical discrepancies.
- It is NOT a statistical probability of title defect or litigation outcome.
- Never outputs a "CLEAR_TITLE", "TITLE_CONFIRMED", or equivalent certificate.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional, Tuple
from app.models.passport_synthesis import (
    RiskDimension,
    RiskTier,
    FindingSeverity,
    STATUTORY_SYNTHESIS_LIMITATION_STATEMENT,
)

# Relative dimension weights in composite diligence score (sum = 1.00)
DIMENSION_WEIGHTS: Dict[RiskDimension, float] = {
    RiskDimension.JUDICIAL_LITIGATION: 0.20,
    RiskDimension.TRANSACTION_MUTATION: 0.20,
    RiskDimension.CADASTRAL_SPATIAL: 0.15,
    RiskDimension.BOUNDARY_FIELD: 0.15,
    RiskDimension.REVENUE_RECORD: 0.15,
    RiskDimension.DOCUMENT_AUTHENTICITY: 0.05,
    RiskDimension.EVIDENCE_COMPLETENESS: 0.05,
    RiskDimension.VALUATION_STATUTORY: 0.05,
}

# Penalty weights per severity tier
SEVERITY_PENALTIES: Dict[FindingSeverity, float] = {
    FindingSeverity.CRITICAL: 50.0,
    FindingSeverity.HIGH: 30.0,
    FindingSeverity.MEDIUM: 15.0,
    FindingSeverity.LOW: 5.0,
    FindingSeverity.INFO: 0.0,
}


class ExplainableRiskEvaluator:
    """
    Computes explainable, multi-dimensional diligence priority scores
    and assigns risk tiers with explicit audit explanations.
    """

    @classmethod
    def evaluate_risk(
        cls,
        findings: List[Dict[str, Any]],
        evidence_gaps: List[Dict[str, Any]],
    ) -> Tuple[RiskTier, float, Dict[str, Any]]:
        """
        Calculates dimension-level assessments and overall composite priority score.
        Returns:
            (overall_risk_tier, composite_score, dimension_breakdown)
        """
        dimension_findings: Dict[RiskDimension, List[Dict[str, Any]]] = {d: [] for d in RiskDimension}
        for f in findings:
            dim = f["dimension"]
            if isinstance(dim, str):
                dim = RiskDimension(dim)
            dimension_findings[dim].append(f)

        dimension_gaps: Dict[RiskDimension, List[Dict[str, Any]]] = {d: [] for d in RiskDimension}
        subsystem_to_dimension = {
            "REVENUE": RiskDimension.REVENUE_RECORD,
            "MUTATION": RiskDimension.TRANSACTION_MUTATION,
            "JUDICIAL": RiskDimension.JUDICIAL_LITIGATION,
            "CADASTRAL_SPATIAL": RiskDimension.CADASTRAL_SPATIAL,
            "FIELD_SURVEY": RiskDimension.BOUNDARY_FIELD,
            "OCR_DOCUMENT": RiskDimension.DOCUMENT_AUTHENTICITY,
            "VALUATION": RiskDimension.VALUATION_STATUTORY,
        }

        for g in evidence_gaps:
            sub = g["subsystem"]
            target_dim = subsystem_to_dimension.get(sub, RiskDimension.EVIDENCE_COMPLETENESS)
            dimension_gaps[target_dim].append(g)

        dimension_scores: Dict[str, Any] = {}
        weighted_sum = 0.0
        has_critical_finding = False
        has_high_finding = False
        has_blocking_gap = any(g.get("is_blocking", False) for g in evidence_gaps)

        for dim in RiskDimension:
            d_findings = dimension_findings[dim]
            d_gaps = dimension_gaps[dim]

            # Base score of 10.0 representing baseline diligence overhead
            dim_score = 10.0
            highest_sev = FindingSeverity.INFO

            for f in d_findings:
                sev = f["severity"]
                if isinstance(sev, str):
                    sev = FindingSeverity(sev)
                if sev == FindingSeverity.CRITICAL:
                    has_critical_finding = True
                    highest_sev = FindingSeverity.CRITICAL
                elif sev == FindingSeverity.HIGH:
                    has_high_finding = True
                    if highest_sev != FindingSeverity.CRITICAL:
                        highest_sev = FindingSeverity.HIGH
                elif sev == FindingSeverity.MEDIUM:
                    if highest_sev not in (FindingSeverity.CRITICAL, FindingSeverity.HIGH):
                        highest_sev = FindingSeverity.MEDIUM
                elif sev == FindingSeverity.LOW:
                    if highest_sev == FindingSeverity.INFO:
                        highest_sev = FindingSeverity.LOW

                dim_score += SEVERITY_PENALTIES.get(sev, 0.0)

            # Evidence gaps add diligence priority
            for g in d_gaps:
                if g.get("is_blocking", False):
                    dim_score += 20.0
                else:
                    dim_score += 8.0

            dim_score = min(100.0, max(0.0, round(dim_score, 2)))
            weight = DIMENSION_WEIGHTS.get(dim, 0.10)
            weighted_sum += (dim_score * weight)

            status_label = "CONSISTENT"
            if highest_sev in (FindingSeverity.CRITICAL, FindingSeverity.HIGH):
                status_label = "DISCREPANCY_DETECTED"
            elif highest_sev == FindingSeverity.MEDIUM:
                status_label = "REQUIRES_REVIEW"
            elif len(d_gaps) > 0 and len(d_findings) == 0:
                status_label = "INSUFFICIENT_EVIDENCE"

            dimension_scores[dim.value] = {
                "dimension": dim.value,
                "status": status_label,
                "severity": highest_sev.value,
                "priority_score": dim_score,
                "findings_count": len(d_findings),
                "evidence_gaps_count": len(d_gaps),
                "weight_in_composite": weight,
                "requires_human_review": any(f.get("requires_human_review", False) for f in d_findings),
            }

        composite_score = min(100.0, max(0.0, round(weighted_sum, 2)))

        # Assign overall risk tier
        if has_blocking_gap:
            overall_tier = RiskTier.INSUFFICIENT_EVIDENCE
        elif composite_score >= 70.0 or has_critical_finding:
            overall_tier = RiskTier.CRITICAL
        elif composite_score >= 50.0 or has_high_finding:
            overall_tier = RiskTier.HIGH
        elif composite_score >= 30.0:
            overall_tier = RiskTier.MEDIUM
        else:
            overall_tier = RiskTier.LOW

        return overall_tier, composite_score, dimension_scores
