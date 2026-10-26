import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.finding import Finding, FindingSeverity, FindingStatus, RequiredAction, ActionStatus
from app.models.claim import Claim, ClaimPredicate, ClaimStatus
from app.models.base import utc_now

class ConsistencyCheckResult:
    def __init__(
        self,
        rule_id: str,
        passed: bool,
        severity: str,
        observed_values: Dict[str, Any],
        explanation: str,
        recommended_action: Optional[str] = None
    ):
        self.rule_id = rule_id
        self.passed = passed
        self.severity = severity
        self.observed_values = observed_values
        self.explanation = explanation
        self.recommended_action = recommended_action

def check_area_delta(
    deed_area_sqm: float,
    survey_area_sqm: float,
    tolerance_pct: float = 5.0
) -> ConsistencyCheckResult:
    """
    Compares registered deed area vs field survey or cadastral GIS area.
    Flags high-severity discrepancy if delta exceeds tolerance threshold.
    """
    if max(deed_area_sqm, survey_area_sqm) <= 0:
        return ConsistencyCheckResult(
            rule_id="RULE_AREA_DELTA_CHECK",
            passed=False,
            severity=FindingSeverity.HIGH,
            observed_values={"deed_area_sqm": deed_area_sqm, "survey_area_sqm": survey_area_sqm},
            explanation="Invalid or zero parcel area reported in comparison documents.",
            recommended_action="Conduct physical ground demarcation and re-survey."
        )

    delta = abs(deed_area_sqm - survey_area_sqm)
    delta_pct = (delta / max(deed_area_sqm, survey_area_sqm)) * 100.0

    passed = delta_pct <= tolerance_pct
    severity = FindingSeverity.INFORMATIONAL if passed else (FindingSeverity.CRITICAL if delta_pct > 15.0 else FindingSeverity.HIGH)
    
    explanation = (
        f"Parcel area delta is within acceptable tolerance ({delta_pct:.2f}% <= {tolerance_pct}%)."
        if passed
        else f"Discrepancy of {delta_pct:.2f}% detected between Deed ({deed_area_sqm} sqm) and Ground Survey ({survey_area_sqm} sqm). Threshold is {tolerance_pct}%."
    )
    recommended_action = (
        None if passed else "Deploy Field Amin for boundary ETS demarcation and neighbor chauhadri verification."
    )

    return ConsistencyCheckResult(
        rule_id="RULE_AREA_DELTA_CHECK",
        passed=passed,
        severity=severity,
        observed_values={
            "deed_area_sqm": deed_area_sqm,
            "survey_area_sqm": survey_area_sqm,
            "delta_sqm": round(delta, 2),
            "delta_pct": round(delta_pct, 2),
            "tolerance_pct": tolerance_pct
        },
        explanation=explanation,
        recommended_action=recommended_action
    )

def check_mutation_gap(
    deed_date: datetime,
    mutation_date: Optional[datetime] = None
) -> ConsistencyCheckResult:
    """
    Detects unmutated deeds or excessive time gap between registered transfer and government revenue mutation.
    """
    if mutation_date is None:
        return ConsistencyCheckResult(
            rule_id="RULE_UNMUTATED_DEED_CHECK",
            passed=False,
            severity=FindingSeverity.CRITICAL,
            observed_values={"deed_date": deed_date.isoformat(), "mutation_date": None},
            explanation="Registered sale deed exists without corresponding circle office mutation (Dakhil Kharij). Title remains unperfected in revenue records.",
            recommended_action="Request Dakhil Kharij order slip or file for circle office mutation rectification."
        )

    # Calculate gap in days
    gap_days = (mutation_date - deed_date).days
    if gap_days < 0:
        return ConsistencyCheckResult(
            rule_id="RULE_MUTATION_CHRONOLOGY_ANOMALY",
            passed=False,
            severity=FindingSeverity.HIGH,
            observed_values={"deed_date": deed_date.isoformat(), "mutation_date": mutation_date.isoformat(), "gap_days": gap_days},
            explanation=f"Mutation date ({mutation_date.date()}) precedes Deed execution date ({deed_date.date()}), indicating data entry or procedural defect.",
            recommended_action="Review certified copies of both registered deed and mutation register volume."
        )

    passed = gap_days <= 180  # 6 months nominal threshold
    severity = FindingSeverity.INFORMATIONAL if passed else FindingSeverity.MEDIUM
    explanation = (
        f"Mutation completed within normal timeline ({gap_days} days after deed registration)."
        if passed
        else f"Prolonged mutation delay of {gap_days} days between registration and mutation."
    )

    return ConsistencyCheckResult(
        rule_id="RULE_MUTATION_GAP_CHECK",
        passed=passed,
        severity=severity,
        observed_values={"deed_date": deed_date.isoformat(), "mutation_date": mutation_date.isoformat(), "gap_days": gap_days},
        explanation=explanation,
        recommended_action=None if passed else "Verify whether interim litigation or objection caused the mutation delay."
    )

def check_chauhadri_boundaries(
    deed_chauhadri: Dict[str, str],
    field_chauhadri: Dict[str, str]
) -> ConsistencyCheckResult:
    """
    Compares 4-sided boundary neighbors (North, South, East, West) recorded in Deed against field survey ground truth.
    """
    mismatches = []
    directions = ["north", "south", "east", "west"]
    for d in directions:
        deed_neighbor = deed_chauhadri.get(d, "").strip().lower()
        field_neighbor = field_chauhadri.get(d, "").strip().lower()
        if deed_neighbor and field_neighbor and deed_neighbor != field_neighbor:
            mismatches.append(f"{d.capitalize()}: Deed='{deed_chauhadri.get(d)}' vs Field='{field_chauhadri.get(d)}'")

    passed = len(mismatches) == 0
    severity = FindingSeverity.INFORMATIONAL if passed else FindingSeverity.HIGH
    explanation = (
        "All 4 recorded chauhadri boundaries correspond with field observation."
        if passed
        else f"Boundary neighbor discrepancies observed in: {'; '.join(mismatches)}."
    )
    recommended_action = (
        None if passed else "Interview adjacent landowners and verify chain of title transfers for bordering plots."
    )

    return ConsistencyCheckResult(
        rule_id="RULE_CHAUHADRI_BOUNDARY_CHECK",
        passed=passed,
        severity=severity,
        observed_values={
            "deed_chauhadri": deed_chauhadri,
            "field_chauhadri": field_chauhadri,
            "mismatch_count": len(mismatches)
        },
        explanation=explanation,
        recommended_action=recommended_action
    )

def check_document_identity_consistency(
    deed_plot: str,
    mutation_plot: str,
    khatiyan_plot: Optional[str] = None
) -> ConsistencyCheckResult:
    """Checks whether the plot/khesra identifier matches across registered deed and revenue records."""
    d_clean = deed_plot.strip().lower()
    m_clean = mutation_plot.strip().lower()
    
    mismatch = (d_clean != m_clean)
    if mismatch:
        return ConsistencyCheckResult(
            rule_id="RULE_PLOT_IDENTITY_MISMATCH",
            passed=False,
            severity=FindingSeverity.CRITICAL,
            observed_values={"deed_plot": deed_plot, "mutation_plot": mutation_plot, "khatiyan_plot": khatiyan_plot},
            explanation=f"Plot discrepancy: Registered deed references Plot '{deed_plot}' while Mutation record references Plot '{mutation_plot}'.",
            recommended_action="Conduct certified registry volume inspection and circle office plot map verification."
        )

    return ConsistencyCheckResult(
        rule_id="RULE_PLOT_IDENTITY_MISMATCH",
        passed=True,
        severity=FindingSeverity.INFORMATIONAL,
        observed_values={"deed_plot": deed_plot, "mutation_plot": mutation_plot},
        explanation="Plot identity is consistent across registered deed and revenue mutation records."
    )

def evaluate_claims_consistency(
    case_id: uuid.UUID,
    parcel_id: uuid.UUID,
    db: Session
) -> List[Finding]:
    """
    Evaluates cross-document claims for a case and parcel,
    generating formal Findings and RequiredActions for any discrepancies.
    """
    claims = db.query(Claim).filter(
        Claim.case_id == case_id,
        Claim.parcel_id == parcel_id,
        Claim.status == ClaimStatus.ACTIVE
    ).all()

    findings: List[Finding] = []

    # 1. Compare Area Claims
    area_claims = [c for c in claims if c.predicate == ClaimPredicate.RECORDED_AREA]
    if len(area_claims) >= 2:
        vals = []
        for ac in area_claims:
            obj = ac.object_value
            norm_val = obj.get("normalized_value") if isinstance(obj, dict) else None
            if isinstance(norm_val, dict) and "normalized_sqm" in norm_val:
                vals.append(norm_val["normalized_sqm"])
            elif isinstance(norm_val, (int, float)):
                vals.append(float(norm_val))
        
        if len(vals) >= 2:
            res = check_area_delta(vals[0], vals[1], tolerance_pct=5.0)
            if not res.passed:
                finding = Finding(
                    case_id=case_id,
                    parcel_id=parcel_id,
                    rule_id=res.rule_id,
                    severity=res.severity,
                    status=FindingStatus.OPEN,
                    observed_values=res.observed_values,
                    explanation=res.explanation,
                    recommended_action=res.recommended_action
                )
                db.add(finding)
                db.flush()
                # Create corresponding RequiredAction
                act = RequiredAction(
                    finding_id=finding.finding_id,
                    case_id=case_id,
                    action_type="FIELD_DEMARCATION",
                    assigned_role="FIELD_AMIN",
                    status=ActionStatus.OPEN
                )
                db.add(act)
                findings.append(finding)

    # 2. Check Chauhadri Boundaries
    north_claims = [c for c in claims if c.predicate == ClaimPredicate.BOUNDARY_NORTH]
    if len(north_claims) >= 2:
        # Check if they conflict
        v1 = str(north_claims[0].object_value.get("raw_value", "")).strip().lower()
        v2 = str(north_claims[1].object_value.get("raw_value", "")).strip().lower()
        if v1 and v2 and v1 != v2:
            res = check_chauhadri_boundaries({"north": v1}, {"north": v2})
            if not res.passed:
                finding = Finding(
                    case_id=case_id,
                    parcel_id=parcel_id,
                    rule_id=res.rule_id,
                    severity=res.severity,
                    status=FindingStatus.OPEN,
                    observed_values={"deed_chauhadri": {"north": v1}, "field_chauhadri": {"north": v2}},
                    explanation=res.explanation,
                    recommended_action=res.recommended_action
                )
                db.add(finding)
                db.flush()
                act = RequiredAction(
                    finding_id=finding.finding_id,
                    case_id=case_id,
                    action_type="NEIGHBOR_BOUNDARY_VERIFICATION",
                    assigned_role="FIELD_AMIN",
                    status=ActionStatus.OPEN
                )
                db.add(act)
                findings.append(finding)

    db.commit()
    return findings
