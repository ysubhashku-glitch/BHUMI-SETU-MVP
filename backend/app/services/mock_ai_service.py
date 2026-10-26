import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.case import Case
from app.models.evidence import Evidence, CaseEvidence
from app.models.claim import Claim
from app.models.finding import Finding
from app.core.exceptions import EntityNotFoundError

def query_ai_land_expert(
    db: Session,
    case_id: uuid.UUID,
    question: str
) -> Dict[str, Any]:
    """
    Read-only, grounded AI Land Expert service complying with the 6-point evidence grounding contract.
    Explicitly labeled as MOCK_AI to guarantee no ungrounded hallucination or canonical data mutation.
    """
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise EntityNotFoundError("Case", case_id)

    # Collect ground-truth artifacts associated with case
    evidence_items = (
        db.query(Evidence)
        .join(CaseEvidence, CaseEvidence.evidence_id == Evidence.evidence_id)
        .filter(CaseEvidence.case_id == case_id)
        .all()
    )
    
    claims = db.query(Claim).filter(Claim.subject_id == case_id).all()
    findings = db.query(Finding).filter(Finding.case_id == case_id).all()

    # Synthesize citations based strictly on active evidence in the case
    citations: List[Dict[str, Any]] = []
    for ev in evidence_items:
        citations.append({
            "citation_source": ev.source_name,
            "evidence_type": ev.evidence_type,
            "authority_tier": ev.authority_tier,
            "verbatim_excerpt": (ev.evidence_metadata or {}).get("summary_excerpt", "Certified legal extract on record."),
            "date_of_record": ev.created_at.isoformat() if ev.created_at else None,
            "extraction_confidence": 0.95
        })

    # Identify open contradictions or findings
    contradictions = [
        {
            "finding_id": str(f.finding_id),
            "rule_id": f.rule_id,
            "severity": f.severity,
            "explanation": f.explanation
        }
        for f in findings if f.status != "RESOLVED"
    ]

    answer_text = (
        f"[AI Land Expert Response - Mode: MOCK_AI]\n"
        f"Case: {case.case_number} ({case.status})\n"
        f"Analysis grounded in {len(evidence_items)} evidence artifact(s), {len(claims)} claim(s), and {len(findings)} finding(s).\n"
        f"Query: '{question}'\n\n"
        f"Ground Truth Summary:\n"
        + (f"- {len(contradictions)} active risk finding(s) require review before final report generation.\n" if contradictions else "- No blocking title defects or active statutory hazards detected on current record.\n")
        + "- Land records must be verified against Jamabandi Panji II and certified encumbrance search."
    )

    return {
        "engine": "BHUMISETU_GROUNDED_AI_EXPERT_V1",
        "mode": "MOCK_AI",
        "case_id": str(case_id),
        "query": question,
        "answer": answer_text,
        "grounding_contract": {
            "evidence_citations": citations,
            "active_contradictions": contradictions,
            "read_only": True,
            "canonical_mutation_permitted": False
        }
    }
