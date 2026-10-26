"""
Explainable Multi-Dimensional Land Risk Evaluator (TASK-P2-06.1).

Evaluates the 8 separate Land Intelligence risk dimensions:
1. REVENUE_RECORD
2. TRANSACTION_MUTATION
3. JUDICIAL_LITIGATION
4. CADASTRAL_SPATIAL
5. BOUNDARY_FIELD
6. DOCUMENT_AUTHENTICITY
7. VALUATION_STATUTORY
8. EVIDENCE_COMPLETENESS

Mathematical Implementation & Epistemic Principles:
- Weight Normalization: All 8 dimension weights sum strictly to 1.000.
- Provisional Nature: Weights and thresholds are deterministic diligence-priority rules,
  marked as PROVISIONAL until calibrated against empirical pilot ground-truth.
- Deduplication: Identical or correlated findings sharing the same finding_code are deduplicated
  within each dimension to prevent artificial score inflation from repeated notifications.
- Separation of Three Outputs:
    A. Evidence Completeness (0.0% to 100.0%): Measures availability of verified records.
       Missing evidence reduces completeness, but is NEVER treated as proof of an adverse defect.
    B. Adverse Findings Score (0.0 to 100.0): Measures severity of detected conflicts, stays, and deficits.
       Absence of detected problems is NEVER treated as proof of safety.
    C. Review Priority Index (0.00 to 100.00): Composite diligence priority index ranking the need
       for professional manual scrutiny. It is NOT a statistical probability of title defect.
- Strict Boundary Calibration:
    * Score < 25.0: LOW (provided no High/Critical finding)
    * 25.0 <= Score < 45.0: MEDIUM
    * 45.0 <= Score < 70.0: HIGH
    * Score >= 70.0: CRITICAL
    * Any CRITICAL finding forces CRITICAL tier.
    * Any HIGH finding forces at least HIGH tier.
    * Any blocking evidence gap forces INSUFFICIENT_EVIDENCE tier.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from app.models.passport_synthesis import (
    RiskDimension,
    RiskTier,
    FindingSeverity,
    STATUTORY_SYNTHESIS_LIMITATION_STATEMENT,
)

logger = logging.getLogger(__name__)

# Relative dimension weights in composite diligence score (Strictly sum = 1.00)
# NOTE: Marked PROVISIONAL until statistically calibrated against verified pilot dockets.
PROVISIONAL_DIMENSION_WEIGHTS: Dict[RiskDimension, float] = {
    RiskDimension.JUDICIAL_LITIGATION: 0.20,
    RiskDimension.TRANSACTION_MUTATION: 0.20,
    RiskDimension.CADASTRAL_SPATIAL: 0.15,
    RiskDimension.BOUNDARY_FIELD: 0.15,
    RiskDimension.REVENUE_RECORD: 0.15,
    RiskDimension.DOCUMENT_AUTHENTICITY: 0.05,
    RiskDimension.EVIDENCE_COMPLETENESS: 0.05,
    RiskDimension.VALUATION_STATUTORY: 0.05,
}

# Penalty weights per severity tier for primary findings
SEVERITY_PENALTIES: Dict[FindingSeverity, float] = {
    FindingSeverity.CRITICAL: 50.0,
    FindingSeverity.HIGH: 30.0,
    FindingSeverity.MEDIUM: 15.0,
    FindingSeverity.LOW: 5.0,
    FindingSeverity.INFO: 0.0,
}

# Subsystems tracked for evidence completeness measurement
CORE_SUBSYSTEMS: List[str] = [
    "REVENUE",
    "MUTATION",
    "JUDICIAL",
    "CADASTRAL_SPATIAL",
    "FIELD_SURVEY",
    "OCR_DOCUMENT",
    "VALUATION",
]


class ExplainableRiskEvaluator:
    """
    Computes explainable, multi-dimensional diligence priority scores,
    enforcing deduplication, output separation, and strict boundary conditions.
    """

    @classmethod
    def evaluate_risk(
        cls,
        findings: List[Dict[str, Any]],
        evidence_gaps: List[Dict[str, Any]],
        facts: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[RiskTier, float, Dict[str, Any]]:
        """
        Calculates dimension-level assessments and overall composite priority score.

        Separates three distinct outputs:
          A. Evidence Completeness
          B. Adverse Findings Score
          C. Review Priority Score (Composite Priority Index)

        Returns:
            (overall_risk_tier, composite_score, dimension_breakdown)
        """
        # 1. Map findings by dimension with source-aware deduplication
        dimension_findings: Dict[RiskDimension, List[Dict[str, Any]]] = {d: [] for d in RiskDimension}
        seen_finding_codes: Dict[RiskDimension, Set[str]] = {d: set() for d in RiskDimension}
        seen_origins: Dict[RiskDimension, Set[Tuple[str, str]]] = {d: set() for d in RiskDimension}

        for f in findings:
            dim = f["dimension"]
            if isinstance(dim, str):
                dim = RiskDimension(dim)

            code = f.get("finding_code", "")
            # Origin identifier: preserves distinct material events from different sources
            supp = f.get("supporting_evidence") or {}
            origin_id = (
                f.get("source_record_id")
                or supp.get("cnr_number")
                or supp.get("case_number")
                or supp.get("mutation_case_no")
                or f.get("title")
                or ""
            )
            origin_key = (code, str(origin_id))

            # If exact same finding code AND same source origin is already seen, apply dampening
            is_duplicate = False
            if origin_key in seen_origins[dim] and origin_id:
                is_duplicate = True
            else:
                if origin_id:
                    seen_origins[dim].add(origin_key)

            if code:
                seen_finding_codes[dim].add(code)

            f_copy = dict(f)
            f_copy["is_correlated_duplicate"] = is_duplicate
            dimension_findings[dim].append(f_copy)

        # 2. Map evidence gaps by dimension
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

        seen_gap_codes: Set[str] = set()
        deduped_gaps: List[Dict[str, Any]] = []

        for g in evidence_gaps:
            g_code = g.get("gap_code", "")
            if g_code and g_code in seen_gap_codes:
                continue  # Deduplicate identical gap codes
            if g_code:
                seen_gap_codes.add(g_code)
            deduped_gaps.append(g)

            sub = g.get("subsystem", "")
            target_dim = subsystem_to_dimension.get(sub, RiskDimension.EVIDENCE_COMPLETENESS)
            dimension_gaps[target_dim].append(g)

        # -------------------------------------------------------------
        # Output A: Evidence Completeness Index
        # -------------------------------------------------------------
        subsystems_with_gaps = {g.get("subsystem") for g in deduped_gaps if g.get("subsystem")}
        available_subsystems_count = 0
        for s in CORE_SUBSYSTEMS:
            if s not in subsystems_with_gaps:
                available_subsystems_count += 1

        evidence_completeness_ratio = round(available_subsystems_count / len(CORE_SUBSYSTEMS), 4)
        evidence_completeness_pct = round(evidence_completeness_ratio * 100.0, 2)

        # -------------------------------------------------------------
        # Evaluate Each Dimension
        # -------------------------------------------------------------
        dimension_scores: Dict[str, Any] = {}
        weighted_priority_sum = 0.0
        weighted_adverse_sum = 0.0
        has_critical_finding = False
        has_high_finding = False
        has_blocking_gap = any(g.get("is_blocking", False) for g in deduped_gaps)

        for dim in RiskDimension:
            d_findings = dimension_findings[dim]
            d_gaps = dimension_gaps[dim]

            # Base score: 10.0 baseline diligence inspection effort
            base_score = 10.0
            adverse_penalty = 0.0
            gap_penalty = 0.0
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

                # If duplicate finding, apply dampening (at most 20% penalty) to prevent inflation
                if f.get("is_correlated_duplicate", False):
                    adverse_penalty += (SEVERITY_PENALTIES.get(sev, 0.0) * 0.20)
                else:
                    adverse_penalty += SEVERITY_PENALTIES.get(sev, 0.0)

            # Evidence gaps add diligence priority, NOT adverse defect penalties
            for g in d_gaps:
                if g.get("is_blocking", False):
                    gap_penalty += 15.0
                else:
                    gap_penalty += 5.0

            # Cap individual dimension penalties at 100.0
            dim_adverse_score = min(100.0, max(0.0, round(base_score + adverse_penalty, 2)))
            dim_priority_score = min(100.0, max(0.0, round(base_score + adverse_penalty + gap_penalty, 2)))

            weight = PROVISIONAL_DIMENSION_WEIGHTS.get(dim, 0.10)
            weighted_priority_sum += (dim_priority_score * weight)
            weighted_adverse_sum += (dim_adverse_score * weight)

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
                "priority_score": dim_priority_score,
                "adverse_score": dim_adverse_score,
                "findings_count": len(d_findings),
                "unique_findings_count": len(seen_finding_codes[dim]),
                "evidence_gaps_count": len(d_gaps),
                "weight_in_composite": weight,
                "requires_human_review": any(f.get("requires_human_review", False) for f in d_findings),
            }

        # -------------------------------------------------------------
        # Output B & C: Adverse Score and Composite Diligence Priority Score
        # -------------------------------------------------------------
        adverse_findings_score = min(100.0, max(0.0, round(weighted_adverse_sum, 2)))
        composite_score = min(100.0, max(0.0, round(weighted_priority_sum, 2)))

        # -------------------------------------------------------------
        # Calibrate Overall Risk Tier against Strict Boundary Conditions
        # -------------------------------------------------------------
        if composite_score >= 70.0 or has_critical_finding:
            underlying_adverse_tier = RiskTier.CRITICAL
        elif composite_score >= 45.0 or has_high_finding:
            underlying_adverse_tier = RiskTier.HIGH
        elif composite_score >= 25.0:
            underlying_adverse_tier = RiskTier.MEDIUM
        else:
            underlying_adverse_tier = RiskTier.LOW

        if has_blocking_gap:
            overall_tier = RiskTier.INSUFFICIENT_EVIDENCE
            tier_explanation = (
                f"Assessment tier is INSUFFICIENT_EVIDENCE due to blocking evidence gaps. "
                f"Underlying adverse findings evaluated at {underlying_adverse_tier.value} "
                f"(Adverse Score: {adverse_findings_score:.2f}). Both missing evidence and adverse findings require resolution."
            )
            precedence_rule = "BLOCKING_EVIDENCE_GAP_PRECEDENCE_OVER_ADVERSE_TIER"
        else:
            overall_tier = underlying_adverse_tier
            tier_explanation = f"Assessment tier determined by adverse findings and diligence priority score ({composite_score:.2f})."
            precedence_rule = "DILIGENCE_SCORE_AND_SEVERITY_OVERRIDE"

        # Attach overall separated outputs in dimension_scores metadata
        dimension_scores["_outputs"] = {
            "evidence_completeness_ratio": evidence_completeness_ratio,
            "evidence_completeness_percentage": evidence_completeness_pct,
            "adverse_findings_score": adverse_findings_score,
            "review_priority_score": composite_score,
            "overall_risk_tier": overall_tier.value,
            "underlying_adverse_tier": underlying_adverse_tier.value,
            "tier_explanation": tier_explanation,
            "precedence_rule": precedence_rule,
            "has_blocking_gap": has_blocking_gap,
            "formula_version": "v1.2-calibrated-separated-outputs",
            "weights_status": "PROVISIONAL_PENDING_EMPIRICAL_PILOT",
            "statutory_limitation": STATUTORY_SYNTHESIS_LIMITATION_STATEMENT,
        }

        return overall_tier, composite_score, dimension_scores
