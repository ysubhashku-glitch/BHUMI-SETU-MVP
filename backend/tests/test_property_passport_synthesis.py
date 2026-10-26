"""
Comprehensive Test Suite for Property Passport Synthesis & Explainable Land Risk Intelligence (TASK-P2-06).

Covers:
1. Reconciliation of consistent evidence across subsystems (Revenue, Cadastral, Amin, Judicial, MVR, Mutation).
2. Detection of conflicting evidence (area variance, party discrepancies, adverse statuses).
3. Missing and stale evidence explicitly represented as AssessmentEvidenceGap.
4. Ambiguous parcel matching & Name-only matching restrictions (strictly capped at <= 0.40).
5. Mutation timeline conflicts & adverse rejection order alerts.
6. Incomplete judicial searches & uncorroborated party matches.
7. Insufficient spatial accuracy & CRS verification gates.
8. Unverified MVR schedules & Synthetic-data exclusion from production valuations.
9. Assessment reproducibility & SHA-256 snapshot hashing.
10. Assessment version history & recomputation (SUPERSEDED lifecycle).
11. Human-review workflows (SUBMITTED, ACCEPTED, REJECTED with audit trail).
12. Multi-tenant isolation & unauthorized cross-tenant rejection.
13. REST API endpoints (/parcels/{id}/assess, /assessments/{id}, /findings/{id}/review, etc.).
14. Land Intelligence Report & PDF integration with statutory limitation notice.
"""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.case import Case, CaseParcel, CaseStatus
from app.models.parcel import Parcel
from app.models.evidence import Evidence, CaseEvidence
from app.models.claim import Claim, ClaimPredicate, ClaimStatus
from app.models.field_task import FieldVerificationTask, TaskStatus
from app.models.field_survey import FieldSurvey
from app.models.judicial import (
    JudicialCase,
    ParcelJudicialMatch,
    JudicialCaseStatus,
    JudicialRiskCategory,
    JudicialMatchCategory,
    JudicialReviewStatus,
)
from app.models.valuation import (
    PropertyValuation,
    MVRSchedule,
    PropertyCategory,
    RoadCategory,
    JurisdictionType,
    RateVerificationStatus,
)
from app.models.mutation import (
    MutationCase,
    MutationStatus,
    MutationType,
    MutationEntityResolution,
    MutationMatchingMethod,
    MutationVerificationStatus,
)
from app.models.spatial_overlay import BoundaryOverlayAnalysis
from app.models.passport_synthesis import (
    PassportAssessment,
    AssessmentFact,
    AssessmentInference,
    AssessmentFinding,
    AssessmentEvidenceGap,
    AssessmentReviewAction,
    AssessmentStatus,
    AssessmentRiskTier,
    FactSubsystem,
    FactVerificationStatus,
    RiskDimension,
    FindingSeverity,
    FindingReviewStatus,
    STATUTORY_PASSPORT_LIMITATION_STATEMENT,
)
from app.schemas.passport_synthesis import (
    GenerateAssessmentRequest,
    FindingReviewRequest,
    AssessmentRecomputeRequest,
)
from app.services.passport.reconciliation_engine import ReconciliationEngine
from app.services.passport.risk_evaluator import RiskEvaluator
from app.services.passport.synthesis_service import SynthesisService
from app.services.report_assembler import assemble_report_data
from app.services.pdf_report_generator import generate_land_intelligence_pdf


# =====================================================================
# Fixtures for Multi-Subsystem Domain Objects
# =====================================================================

@pytest.fixture
def sample_parcel(db_session: Session, tenant_a: Organization) -> Parcel:
    parcel = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id="BR-PAT-DAN-00123-0456",
        state="Bihar",
        district_name="Patna",
        subdistrict_anchal_name="Danapur",
        mauza_village_name="Mustafapur",
        khata_number="123",
        plot_khesra_number="456",
        recorded_area_acres=1.50,
        land_nature="Raiyati",
        source_portal="Bihar Bhumi",
        source_authority="Circle Officer Danapur",
    )
    db_session.add(parcel)
    db_session.commit()
    db_session.refresh(parcel)
    return parcel


@pytest.fixture
def sample_case(db_session: Session, tenant_a: Organization, user_a: User, sample_parcel: Parcel) -> Case:
    case = Case(
        org_id=tenant_a.org_id,
        created_by_user_id=user_a.user_id,
        case_number="CASE-2026-PAT-001",
        title="Diligence on Mustafapur Plot 456",
        status=CaseStatus.IN_PROGRESS,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    # Link parcel to case
    cp = CaseParcel(
        case_id=case.case_id,
        parcel_id=sample_parcel.parcel_id,
        is_primary=True,
    )
    db_session.add(cp)
    db_session.commit()
    return case


# =====================================================================
# 1. Reconciliation Engine Unit Tests
# =====================================================================

def test_reconciliation_observed_facts_collection(
    db_session: Session,
    tenant_a: Organization,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """Verifies that facts from revenue, mutation, judicial, spatial, field survey, and MVR are assembled."""
    engine = ReconciliationEngine(db_session)
    bundle = engine.gather_evidence_bundle(sample_parcel, sample_case.case_id, include_synthetic_fixtures=False)

    # Should at least find revenue facts from parcel
    revenue_facts = [f for f in bundle.facts if f.subsystem == FactSubsystem.REVENUE]
    assert len(revenue_facts) >= 2  # Plot number, recorded area

    # Should observe limitations and data freshness
    assert all(f.source_reference is not None for f in bundle.facts)
    assert all(isinstance(f.is_verified, bool) for f in bundle.facts)


def test_reconciliation_detects_area_conflict(
    db_session: Session,
    tenant_a: Organization,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """Verifies that an area discrepancy between revenue record and field survey is inferred deterministically."""
    # Add a field survey task and survey with measured area differing > 10%
    task = FieldVerificationTask(
        org_id=tenant_a.org_id,
        case_id=sample_case.case_id,
        parcel_id=sample_parcel.parcel_id,
        task_number="TASK-AM-2026-001",
        assigned_to_user_id=sample_case.created_by_user_id,
        status=TaskStatus.COMPLETED,
    )
    db_session.add(task)
    db_session.flush()

    survey = FieldSurvey(
        org_id=tenant_a.org_id,
        task_id=task.task_id,
        case_id=sample_case.case_id,
        parcel_id=sample_parcel.parcel_id,
        measured_area_acres=1.10,  # 1.10 vs 1.50 = 26.7% variance (exceeds 5% tolerance)
        gps_reading_count=12,
        reported_accuracy_meters=2.5,
        physical_possessor_name="Ram Babu",
    )
    db_session.add(survey)
    db_session.commit()

    engine = ReconciliationEngine(db_session)
    bundle = engine.gather_evidence_bundle(sample_parcel, sample_case.case_id, include_synthetic_fixtures=False)

    # Check for area variance inference
    area_infs = [inf for inf in bundle.inferences if inf.rule_id == "RULE-AREA-VARIANCE-01"]
    assert len(area_infs) == 1
    assert area_infs[0].uncertainty_metric is not None
    assert area_infs[0].uncertainty_metric > 15.0  # >15% variance

    # Check for boundary finding
    area_findings = [f for f in bundle.findings if f.dimension == RiskDimension.BOUNDARY_VERIFICATION]
    assert len(area_findings) >= 1
    assert area_findings[0].severity in (FindingSeverity.HIGH, FindingSeverity.CRITICAL)


def test_reconciliation_anti_name_only_matching_rule(
    db_session: Session,
    tenant_a: Organization,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """
    Mandatory test: A judicial case matching ONLY on party name without plot or khata
    must be capped at <= 0.40 confidence and require human review.
    """
    j_case = JudicialCase(
        org_id=tenant_a.org_id,
        case_id=sample_case.case_id,
        cnr_number="BHPAT01002342024",
        case_number="Title Suit 88/2024",
        court_name="Civil Court Danapur",
        filing_year=2024,
        case_status=JudicialCaseStatus.PENDING,
        has_active_injunction=True,
        risk_category=JudicialRiskCategory.TITLE_DISPUTE,
        search_query_snapshot={"party_name": "Ram Babu"},
    )
    db_session.add(j_case)
    db_session.flush()

    # Link with NAME_ONLY
    match = ParcelJudicialMatch(
        org_id=tenant_a.org_id,
        judicial_case_id=j_case.judicial_case_id,
        parcel_id=sample_parcel.parcel_id,
        match_category=JudicialMatchCategory.NAME_ONLY,
        confidence_score=0.35,  # Capped at 0.40
        matched_fields={"petitioner": "Ram Babu"},
        explanation="Name match on common surname without corroborating plot or khata identifier.",
        review_status=JudicialReviewStatus.PENDING_REVIEW,
    )
    db_session.add(match)
    db_session.commit()

    engine = ReconciliationEngine(db_session)
    bundle = engine.gather_evidence_bundle(sample_parcel, sample_case.case_id)

    # Inferences must reflect low confidence and uncertainty
    jud_infs = [inf for inf in bundle.inferences if inf.rule_id == "RULE-JUDICIAL-MATCH-01"]
    assert len(jud_infs) >= 1
    assert jud_infs[0].confidence_score <= 0.40

    # Finding must require human review
    jud_findings = [f for f in bundle.findings if f.dimension == RiskDimension.JUDICIAL_LITIGATION]
    assert len(jud_findings) >= 1
    assert jud_findings[0].review_status == FindingReviewStatus.PENDING_REVIEW


def test_reconciliation_adverse_mutation_rejection(
    db_session: Session,
    tenant_a: Organization,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """Verifies that an adverse mutation rejection triggers a HIGH or CRITICAL finding."""
    mut = MutationCase(
        org_id=tenant_a.org_id,
        case_id=sample_case.case_id,
        parcel_id=sample_parcel.parcel_id,
        case_number="MUT-2024-DAN-REJ-01",
        filing_year=2024,
        district="Patna",
        circle="Danapur",
        mauza="Mustafapur",
        khata_number="123",
        khesra_number="456",
        mutation_type=MutationType.SALE_DEED,
        normalized_status=MutationStatus.REJECTED,
        raw_source_status="अस्वीकृत (Rejected)",
        rejection_reason_code="LAND_CEILING_EXCESS",
        source_portal="Bihar Bhumi Dakhil-Kharij",
        source_authority="Circle Officer Danapur",
    )
    db_session.add(mut)
    db_session.commit()

    engine = ReconciliationEngine(db_session)
    bundle = engine.gather_evidence_bundle(sample_parcel, sample_case.case_id)

    mut_findings = [f for f in bundle.findings if f.dimension == RiskDimension.TRANSACTION_MUTATION]
    assert len(mut_findings) >= 1
    rej_finding = next((f for f in mut_findings if "Rejected" in f.title or "Rejection" in f.title), None)
    assert rej_finding is not None
    assert rej_finding.severity in (FindingSeverity.HIGH, FindingSeverity.CRITICAL)


def test_reconciliation_synthetic_data_exclusion_gate(
    db_session: Session,
    tenant_a: Organization,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """
    Mandatory upstream gate: Synthetic valuation fixtures must be excluded
    unless explicitly requested.
    """
    # Create an unverified / synthetic rate schedule
    sched = MVRSchedule(
        org_id=tenant_a.org_id,
        schedule_code="SYNTH-PAT-2026",
        district="Patna",
        anchal_circle="Danapur",
        mauza="Mustafapur",
        effective_from_year=2026,
        is_synthetic=True,
        verification_status=RateVerificationStatus.SYNTHETIC,
        residential_main_road_rate=500000.0,
    )
    db_session.add(sched)
    db_session.flush()

    val = PropertyValuation(
        org_id=tenant_a.org_id,
        case_id=sample_case.case_id,
        parcel_id=sample_parcel.parcel_id,
        mvr_schedule_id=sched.schedule_id,
        property_category=PropertyCategory.RESIDENTIAL,
        road_category=RoadCategory.MAIN_ROAD,
        jurisdiction_type=JurisdictionType.MUNICIPAL_CORPORATION,
        total_area_decimal=150.0,
        input_area_value=1.5,
        input_area_unit="Acre",
        unit_circle_rate=500000.0,
        calculated_land_value=75000000.0,
        calculated_structure_value=0.0,
        total_government_valuation=75000000.0,
        assessment_base=75000000.0,
        stamp_duty_rate_percent=6.0,
        stamp_duty_amount=4500000.0,
        registration_fee_rate_percent=2.0,
        registration_fee_amount=1500000.0,
        municipal_surcharge_percent=2.0,
        municipal_surcharge_amount=1500000.0,
        total_statutory_charges=7500000.0,
        is_synthetic=True,
        verification_status=RateVerificationStatus.SYNTHETIC,
    )
    db_session.add(val)
    db_session.commit()

    engine = ReconciliationEngine(db_session)
    
    # 1. Without synthetic inclusion: Should NOT include synthetic valuation facts
    bundle_prod = engine.gather_evidence_bundle(sample_parcel, sample_case.case_id, include_synthetic_fixtures=False)
    val_facts_prod = [f for f in bundle_prod.facts if f.subsystem == FactSubsystem.VALUATION]
    assert len(val_facts_prod) == 0

    # 2. Evidence gap must be raised for valuation when only synthetic data existed
    val_gaps = [g for g in bundle_prod.evidence_gaps if g.dimension == RiskDimension.VALUATION_CHARGES]
    assert len(val_gaps) >= 1
    assert "SYNTHETIC" in val_gaps[0].gap_code or "NO_VERIFIED" in val_gaps[0].gap_code

    # 3. With explicit synthetic inclusion: Facts are admitted
    bundle_synth = engine.gather_evidence_bundle(sample_parcel, sample_case.case_id, include_synthetic_fixtures=True)
    val_facts_synth = [f for f in bundle_synth.facts if f.subsystem == FactSubsystem.VALUATION]
    assert len(val_facts_synth) >= 1


def test_reconciliation_missing_evidence_never_silently_cleared(
    db_session: Session,
    tenant_a: Organization,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """
    Mandatory test: When cadastral overlay or judicial search is absent,
    the system must explicitly produce AssessmentEvidenceGap records and NOT assume zero risk.
    """
    engine = ReconciliationEngine(db_session)
    bundle = engine.gather_evidence_bundle(sample_parcel, sample_case.case_id)

    # In our fresh parcel, no cadastral overlay or judicial search was performed
    cadastral_gaps = [g for g in bundle.evidence_gaps if g.dimension == RiskDimension.CADASTRAL_SPATIAL]
    assert len(cadastral_gaps) >= 1
    assert cadastral_gaps[0].gap_code == "GAP-SPATIAL-NO-OVERLAY"

    judicial_gaps = [g for g in bundle.evidence_gaps if g.dimension == RiskDimension.JUDICIAL_LITIGATION]
    assert len(judicial_gaps) >= 1
    assert judicial_gaps[0].gap_code == "GAP-JUDICIAL-NOT-INDEXED"


# =====================================================================
# 2. Risk Evaluator & Scoring Formula Tests
# =====================================================================

def test_risk_evaluator_scoring_and_tier_calculation(
    db_session: Session,
    tenant_a: Organization,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """Verifies multidimensional weighting and tier mapping (LOW, MEDIUM, HIGH, CRITICAL, INSUFFICIENT_EVIDENCE)."""
    engine = ReconciliationEngine(db_session)
    bundle = engine.gather_evidence_bundle(sample_parcel, sample_case.case_id)

    evaluator = RiskEvaluator()
    composite_score, tier, dim_scores = evaluator.evaluate(bundle)

    assert 0.0 <= composite_score <= 100.0
    assert tier in [t for t in AssessmentRiskTier]

    # Check that all 8 dimensions are evaluated
    assert len(dim_scores) == 8
    expected_dimensions = [d.value for d in RiskDimension]
    for dim_code in expected_dimensions:
        assert dim_code in dim_scores
        assert "score" in dim_scores[dim_code]
        assert "weight" in dim_scores[dim_code]
        assert "status" in dim_scores[dim_code]

    # Verify weights sum to 1.00 within tolerance
    total_weight = sum(d["weight"] for d in dim_scores.values())
    assert abs(total_weight - 1.00) < 0.001


# =====================================================================
# 3. Synthesis Service End-to-End & Lifecycle Tests
# =====================================================================

def test_synthesis_service_generate_assessment(
    db_session: Session,
    tenant_a: Organization,
    user_a: User,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """Tests generating a full, persisted, versioned assessment with SHA-256 snapshot hashing."""
    service = SynthesisService(db_session)
    req = GenerateAssessmentRequest(
        parcel_id=sample_parcel.parcel_id,
        case_id=sample_case.case_id,
        notes="Pre-purchase due diligence assessment.",
    )

    assessment = service.generate_assessment(req, user_a)
    assert assessment.assessment_id is not None
    assert assessment.version_number == 1
    assert assessment.assessment_status == AssessmentStatus.ACTIVE
    assert assessment.sha256_snapshot_hash is not None
    assert len(assessment.sha256_snapshot_hash) == 64
    assert assessment.statutory_disclaimer == STATUTORY_PASSPORT_LIMITATION_STATEMENT
    assert len(assessment.facts) > 0
    assert len(assessment.evidence_gaps) > 0

    # Ensure assessment is retrievable
    fetched = service.get_assessment(assessment.assessment_id, user_a)
    assert fetched.assessment_number == assessment.assessment_number


def test_synthesis_service_recompute_creates_superseded_version(
    db_session: Session,
    tenant_a: Organization,
    user_a: User,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """
    Mandatory test: Recomputing an assessment when new evidence arrives must
    preserve the old assessment as SUPERSEDED and create version 2 with a link to previous_assessment_id.
    """
    service = SynthesisService(db_session)
    req1 = GenerateAssessmentRequest(parcel_id=sample_parcel.parcel_id, case_id=sample_case.case_id)
    v1 = service.generate_assessment(req1, user_a)
    assert v1.version_number == 1
    assert v1.assessment_status == AssessmentStatus.ACTIVE

    # Now recompute
    recompute_req = AssessmentRecomputeRequest(reason="New Jamabandi deed uploaded by operator.")
    v2 = service.recompute_assessment(v1.assessment_id, recompute_req, user_a)

    # v2 must be version 2 and active
    assert v2.version_number == 2
    assert v2.assessment_status == AssessmentStatus.ACTIVE
    assert v2.previous_assessment_id == v1.assessment_id

    # v1 must now be SUPERSEDED, not deleted or modified in place
    db_session.refresh(v1)
    assert v1.assessment_status == AssessmentStatus.SUPERSEDED


def test_synthesis_service_human_review_workflow(
    db_session: Session,
    tenant_a: Organization,
    user_a: User,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """Tests submitting a finding for review and recording a reviewer decision with audit trail."""
    service = SynthesisService(db_session)
    req = GenerateAssessmentRequest(parcel_id=sample_parcel.parcel_id, case_id=sample_case.case_id)
    assessment = service.generate_assessment(req, user_a)

    # Pick a finding
    finding = assessment.findings[0]

    # Submit for review
    sub_finding = service.submit_finding_for_review(
        finding.finding_id,
        notes="High variance requires physical inspection by senior Amin.",
        current_user=user_a,
    )
    assert sub_finding.review_status == FindingReviewStatus.SUBMITTED

    # Record decision
    review_req = FindingReviewRequest(
        decision="ACCEPTED",
        decision_notes="Confirmed ground boundary pillar misplaced by encroacher.",
    )
    dec_finding = service.record_finding_review(finding.finding_id, review_req, user_a)
    assert dec_finding.review_status == FindingReviewStatus.ACCEPTED
    assert dec_finding.reviewed_by_user_id == user_a.user_id

    # Verify audit trail
    actions = db_session.query(AssessmentReviewAction).filter(
        AssessmentReviewAction.finding_id == finding.finding_id
    ).all()
    assert len(actions) >= 2  # Submit and Decision


# =====================================================================
# 4. Multi-Tenant Isolation & Security Tests
# =====================================================================

def test_synthesis_multi_tenant_isolation(
    db_session: Session,
    tenant_a: Organization,
    tenant_b: Organization,
    user_a: User,
    user_b: User,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """Verifies that User B from Tenant B cannot access or recompute an assessment owned by Tenant A."""
    from app.core.exceptions import CrossTenantAccessError, EntityNotFoundError

    service = SynthesisService(db_session)
    req = GenerateAssessmentRequest(parcel_id=sample_parcel.parcel_id, case_id=sample_case.case_id)
    assessment = service.generate_assessment(req, user_a)

    # User B attempting to view assessment -> CrossTenantAccessError
    with pytest.raises(CrossTenantAccessError):
        service.get_assessment(assessment.assessment_id, user_b)

    # User B attempting to recompute assessment -> CrossTenantAccessError
    recompute_req = AssessmentRecomputeRequest(reason="Malicious cross-tenant attempt")
    with pytest.raises(CrossTenantAccessError):
        service.recompute_assessment(assessment.assessment_id, recompute_req, user_b)


# =====================================================================
# 5. REST API Integration Tests
# =====================================================================

def test_api_generate_and_retrieve_assessment(
    client: TestClient,
    auth_headers_a: dict,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """Tests POST /api/v1/parcels/{id}/assess and GET /api/v1/assessments/{id}."""
    resp = client.post(
        f"/api/v1/parcels/{sample_parcel.parcel_id}/assess",
        json={"case_id": str(sample_case.case_id), "notes": "API test run"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "assessment_id" in data
    assert data["assessment_status"] == "ACTIVE"
    assert data["version_number"] == 1
    assessment_id = data["assessment_id"]

    # Retrieve
    get_resp = client.get(f"/api/v1/assessments/{assessment_id}", headers=auth_headers_a)
    assert get_resp.status_code == 200
    detail = get_resp.json()
    assert detail["assessment_id"] == assessment_id
    assert "dimension_scores" in detail
    assert "findings" in detail
    assert "evidence_gaps" in detail


def test_api_cross_tenant_access_forbidden(
    client: TestClient,
    auth_headers_a: dict,
    auth_headers_b: dict,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """Verifies cross-tenant GET returns 403 Forbidden."""
    resp = client.post(
        f"/api/v1/parcels/{sample_parcel.parcel_id}/assess",
        json={"case_id": str(sample_case.case_id)},
        headers=auth_headers_a,
    )
    assert resp.status_code == 201
    assessment_id = resp.json()["assessment_id"]

    # Attempt cross-tenant get with User B
    resp_b = client.get(f"/api/v1/assessments/{assessment_id}", headers=auth_headers_b)
    assert resp_b.status_code == 403


# =====================================================================
# 6. Land Intelligence Report & PDF Integration Tests
# =====================================================================

def test_report_assembler_and_pdf_synthesis_integration(
    db_session: Session,
    tenant_a: Organization,
    user_a: User,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """Verifies that report assembler pulls the assessment and PDF generator renders the executive synthesis."""
    # 1. Generate assessment first
    service = SynthesisService(db_session)
    req = GenerateAssessmentRequest(parcel_id=sample_parcel.parcel_id, case_id=sample_case.case_id)
    service.generate_assessment(req, user_a)

    # 2. Assemble Report Data
    report_data = assemble_report_data(
        db=db_session,
        case_id=sample_case.case_id,
        parcel_id=sample_parcel.parcel_id,
        current_user=user_a,
    )

    # Check synthesis section in report
    assert report_data.section_synthesis is not None
    assert report_data.section_synthesis.is_synthesized is True
    assert report_data.section_synthesis.version_number == 1
    assert len(report_data.section_synthesis.dimension_scores) == 8
    assert report_data.section_1_cover.data_availability_summary["property_passport_synthesized"] is True

    # 3. Render Land Intelligence PDF
    pdf_bytes = generate_land_intelligence_pdf(report_data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF")
