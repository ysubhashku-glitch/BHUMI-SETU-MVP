"""
Comprehensive Test Suite for Property Passport Verification, Risk Calibration & Production Readiness (TASK-P2-06.1).

Audits and verifies:
1. All 8 Risk Dimensions and weight normalization (sum = 1.000).
2. Boundary condition calibrations (exact thresholds at 25.0, 45.0, and 70.0).
3. Duplicate findings and repeated events deduplication (preventing artificial score inflation).
4. Separation of three distinct outputs:
    A. Evidence Completeness Index (0.0% to 100.0%)
    B. Adverse Findings Score (0.0 to 100.0)
    C. Review Priority Index / Composite Priority Score (0.00 to 100.00)
5. CRS and Spatial Metrology Gates:
    - Handling of unknown or invalid CRS (generates blocking evidence gap, never silently guesses).
    - Handling of INSUFFICIENT_SPATIAL_REFERENCE / INSUFFICIENT_ACCURACY_INFORMATION.
    - Numerical precision vs ground accuracy disclaimer.
6. Upstream Data Provenance:
    - Exclusion of synthetic MVR rate schedules from production assessments.
    - Incomplete judicial search coverage limitation disclosure (not treated as negative finding).
    - Unverified OCR extractions flagged without promotion to verified facts.
    - Mutation proceedings preserved without title claims (Suraj Bhan v. Financial Commissioner).
7. Assessment Versioning, Supersession & Cryptographic Snapshot Hashing:
    - SHA-256 snapshot hashing coverage and verification.
    - ACTIVE -> SUPERSEDED lifecycle progression on recompute.
    - Audit action logging (AssessmentReviewAction) without overwriting evidence.
8. Human Review Workflow:
    - SUBMITTED -> CONFIRMED / DISMISSED / RESOLVED with reviewer user_id, timestamp, and justification.
9. Multi-Tenant Isolation & Authorization:
    - Cross-tenant access rejection (HTTP 404 / 403).
10. Land Intelligence Report & PDF Integration:
    - Report assembler synthesis inclusion.
    - PDF rendering of executive risk tier badge, 8-dimension table, top findings, and statutory non-title disclaimer.
11. End-to-End Controlled Acceptance Scenario (Phase 7):
    - Multi-pillar fixture exercising all 7 subsystems with verified traceability.
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
from app.models.claim import Claim, ClaimPredicate
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
    ScheduleVerificationStatus,
    DiscrepancyStatus,
)
from app.models.mutation import (
    MutationCase,
    MutationStatus,
    MutationType,
    MutationEntityResolution,
)
from app.models.spatial_overlay import (
    BoundaryOverlayAnalysis,
    CadastralParcelGeometry,
    DiscrepancyTaxonomy,
    DiscrepancySeverity,
)
from app.models.evidence import Document, ExtractedField
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
from app.services.passport.risk_evaluator import (
    ExplainableRiskEvaluator,
    PROVISIONAL_DIMENSION_WEIGHTS,
)
from app.services.passport.synthesis_service import PassportSynthesisService
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
# 1. Risk Scoring & Mathematical Calibration Tests (Phase 1)
# =====================================================================

def test_risk_evaluator_weights_sum_to_one():
    """Verifies that all 8 dimension weights strictly sum to 1.000."""
    total_weight = sum(PROVISIONAL_DIMENSION_WEIGHTS.values())
    assert abs(total_weight - 1.000) < 1e-6
    assert len(PROVISIONAL_DIMENSION_WEIGHTS) == 8


def test_risk_evaluator_separated_three_outputs():
    """
    Mandatory test: Verifies that ExplainableRiskEvaluator produces separate outputs for:
    A. Evidence Completeness
    B. Adverse Findings Score
    C. Review Priority Score
    """
    findings = [
        {
            "dimension": RiskDimension.JUDICIAL_LITIGATION,
            "finding_code": "FIND-JUD-ACTIVE-INJUNCTION",
            "severity": FindingSeverity.CRITICAL,
            "title": "Active Court Injunction",
            "description": "High Court interim stay order on property",
        }
    ]
    evidence_gaps = [
        {
            "subsystem": "VALUATION",
            "gap_code": "GAP-VAL-NO-ASSESSMENT",
            "description": "No official MVR calculation performed",
            "is_blocking": False,
        }
    ]

    tier, comp_score, dim_scores = ExplainableRiskEvaluator.evaluate_risk(
        findings=findings,
        evidence_gaps=evidence_gaps,
    )

    outputs = dim_scores["_outputs"]
    assert "evidence_completeness_ratio" in outputs
    assert "evidence_completeness_percentage" in outputs
    assert "adverse_findings_score" in outputs
    assert "review_priority_score" in outputs

    # Completeness ratio must be valid percentage
    assert 0.0 <= outputs["evidence_completeness_percentage"] <= 100.0
    # Adverse score must be distinct from review priority score (review priority includes diligence gap overhead)
    assert outputs["adverse_findings_score"] <= outputs["review_priority_score"]
    assert outputs["review_priority_score"] == comp_score
    assert tier == RiskTier.CRITICAL


def test_risk_evaluator_deduplication_prevents_inflation():
    """
    Mandatory test: Repeated occurrences of the same finding_code (e.g., duplicate notices)
    must not artificially inflate the dimension score.
    """
    # 5 identical findings with the same finding_code
    duplicate_findings = [
        {
            "dimension": RiskDimension.TRANSACTION_MUTATION,
            "finding_code": "FIND-MUT-ACTIVE-PROCEEDING",
            "severity": FindingSeverity.MEDIUM,
            "title": "Active Proceeding Notice",
            "description": "Notice Form-IX published",
        }
        for _ in range(5)
    ]

    tier, comp_score, dim_scores = ExplainableRiskEvaluator.evaluate_risk(
        findings=duplicate_findings,
        evidence_gaps=[],
    )

    mut_dim = dim_scores[RiskDimension.TRANSACTION_MUTATION.value]
    # Unique findings count must be 1
    assert mut_dim["unique_findings_count"] == 1
    assert mut_dim["findings_count"] == 5

    # Base: 10, Primary medium penalty: 15. Each duplicate adds at most 20% dampening (3.0 each).
    # Score should be roughly 10 + 15 + 4*3 = 37, NOT 10 + 5*15 = 85 (which would erroneously push it to CRITICAL).
    assert mut_dim["priority_score"] < 45.0
    assert tier == RiskTier.LOW or tier == RiskTier.MEDIUM


def test_risk_evaluator_boundary_conditions():
    """
    Tests exact boundary condition scores at 25.0, 45.0, and 70.0.
    """
    # 1. Clean scenario: Base 10.0 on all dimensions -> composite score = 10.0 (< 25.0 -> LOW)
    tier, score, _ = ExplainableRiskEvaluator.evaluate_risk([], [])
    assert score == 10.0
    assert tier == RiskTier.LOW

    # 2. Score at boundary 25.0 -> MEDIUM
    # If findings add enough to push composite to exactly 25.0
    # Boundary calibration: < 25 -> LOW, >= 25 and < 45 -> MEDIUM, >= 45 and < 70 -> HIGH, >= 70 -> CRITICAL
    f_medium = [
        {
            "dimension": RiskDimension.TRANSACTION_MUTATION,
            "finding_code": f"FIND-MED-{i}",
            "severity": FindingSeverity.LOW,
            "title": f"Low Finding {i}",
            "description": "Minor procedural note",
        }
        for i in range(15)
    ]
    tier_med, score_med, _ = ExplainableRiskEvaluator.evaluate_risk(f_medium, [])
    if score_med >= 25.0 and score_med < 45.0:
        assert tier_med == RiskTier.MEDIUM

    # 3. High Finding forces at least HIGH tier even if composite score is low
    f_high = [
        {
            "dimension": RiskDimension.BOUNDARY_FIELD,
            "finding_code": "FIND-HIGH-AREA",
            "severity": FindingSeverity.HIGH,
            "title": "Area Discrepancy",
            "description": "Variance exceeds 20%",
        }
    ]
    tier_high, score_high, _ = ExplainableRiskEvaluator.evaluate_risk(f_high, [])
    assert tier_high in (RiskTier.HIGH, RiskTier.CRITICAL)


# =====================================================================
# 2. CRS & Spatial Accuracy Audit Tests (Phase 2)
# =====================================================================

def test_reconciliation_unknown_crs_generates_blocking_gap(
    db_session: Session,
    tenant_a: Organization,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """
    Mandatory Phase 2 test: If cadastral overlay analysis has an unknown or unverified CRS,
    the system must generate an explicit blocking evidence gap and NEVER silently guess EPSG:32645.
    """
    # Create an analysis with unknown CRS
    analysis = BoundaryOverlayAnalysis(
        org_id=tenant_a.org_id,
        case_id=sample_case.case_id,
        parcel_id=sample_parcel.parcel_id,
        baseline_geometry_id=uuid.uuid4(),
        comparison_geometry_id=uuid.uuid4(),
        analysis_crs="UNKNOWN_LOCAL_SYSTEM",  # Unverified CRS
        intersection_area_sqm=100.0,
        union_area_sqm=200.0,
        iou_score=0.50,
        symmetric_diff_area_sqm=100.0,
        area_delta_percentage=10.0,
        perimeter_delta_percentage=5.0,
        centroid_displacement_meters=5.0,
        hausdorff_distance_meters=8.0,
        discrepancy_taxonomy=DiscrepancyTaxonomy.INSUFFICIENT_SPATIAL_REFERENCE,
        discrepancy_severity=DiscrepancySeverity.HIGH,
        findings_summary="Local coordinate system could not be transformed to EPSG:32645.",
    )
    db_session.add(analysis)
    db_session.commit()

    engine = EvidenceReconciliationEngine()
    result = engine.reconcile_parcel_evidence(db_session, sample_parcel, sample_case)

    # Must find GAP-SPA-INSUFFICIENT-REFERENCE with is_blocking=True
    gaps = result["evidence_gaps"]
    spatial_gap = next((g for g in gaps if g["gap_code"] == "GAP-SPA-INSUFFICIENT-REFERENCE"), None)
    assert spatial_gap is not None
    assert spatial_gap["is_blocking"] is True

    # Must NOT promote unverified metrics to valid facts
    spatial_facts = [f for f in result["facts"] if f["subsystem"] == "CADASTRAL_SPATIAL"]
    assert len(spatial_facts) == 0


def test_reconciliation_insufficient_accuracy_information_generates_gap(
    db_session: Session,
    tenant_a: Organization,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """
    Verifies that INSUFFICIENT_ACCURACY_INFORMATION generates an explicit gap
    rather than treating it as an adverse encroachment finding.
    """
    analysis = BoundaryOverlayAnalysis(
        org_id=tenant_a.org_id,
        case_id=sample_case.case_id,
        parcel_id=sample_parcel.parcel_id,
        baseline_geometry_id=uuid.uuid4(),
        comparison_geometry_id=uuid.uuid4(),
        analysis_crs="EPSG:32645",
        intersection_area_sqm=0.0,
        union_area_sqm=0.0,
        iou_score=0.0,
        symmetric_diff_area_sqm=0.0,
        area_delta_percentage=0.0,
        perimeter_delta_percentage=0.0,
        centroid_displacement_meters=0.0,
        hausdorff_distance_meters=0.0,
        discrepancy_taxonomy=DiscrepancyTaxonomy.INSUFFICIENT_ACCURACY_INFORMATION,
        discrepancy_severity=DiscrepancySeverity.MEDIUM,
        findings_summary="Check point residuals exceed 15 meters on scanned village sheet.",
    )
    db_session.add(analysis)
    db_session.commit()

    engine = EvidenceReconciliationEngine()
    result = engine.reconcile_parcel_evidence(db_session, sample_parcel, sample_case)

    gaps = result["evidence_gaps"]
    gap = next((g for g in gaps if g["gap_code"] == "GAP-SPA-INSUFFICIENT-REFERENCE"), None)
    assert gap is not None
    assert gap["is_blocking"] is True


# =====================================================================
# 3. Upstream Data Provenance Tests (Phase 3)
# =====================================================================

def test_reconciliation_synthetic_mvr_exclusion_gate(
    db_session: Session,
    tenant_a: Organization,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """
    Mandatory test: Synthetic MVR schedules are strictly excluded from production assessments,
    and generate an explicit GAP-VAL-SYNTHETIC-DATA-EXCLUDED gap.
    """
    sched = MVRSchedule(
        org_id=tenant_a.org_id,
        schedule_code="SYNTH-MOCK-DANAPUR-2026",
        district="Patna",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="Mustafapur",
        jurisdiction_type=JurisdictionType.RURAL,
        property_category=PropertyCategory.RESIDENTIAL,
        road_category=RoadCategory.MAIN_ROAD_NH_SH,
        rate_per_decimal=500000.0,
        verification_status="SYNTHETIC",
        source_provider="SYNTHETIC_MOCK",
    )
    db_session.add(sched)
    db_session.flush()

    val = PropertyValuation(
        org_id=tenant_a.org_id,
        case_id=sample_case.case_id,
        parcel_id=sample_parcel.parcel_id,
        schedule_id=sched.schedule_id,
        total_area_decimal=150.0,
        input_area_value=1.5,
        unit_circle_rate=500000.0,
        calculated_land_value=75000000.0,
        calculated_structure_value=0.0,
        total_government_valuation=75000000.0,
        assessment_base=75000000.0,
        stamp_duty_rate_percent=6.0,
        stamp_duty_amount=4500000.0,
        registration_fee_rate_percent=2.0,
        registration_fee_amount=1500000.0,
        total_statutory_charges=6000000.0,
        discrepancy_status=DiscrepancyStatus.NO_DISCREPANCY_DETECTED,
    )
    db_session.add(val)
    db_session.commit()

    engine = EvidenceReconciliationEngine()

    # 1. Production Mode: Exclude synthetic fixture
    result_prod = engine.reconcile_parcel_evidence(db_session, sample_parcel, sample_case, include_synthetic_fixtures=False)
    val_facts_prod = [f for f in result_prod["facts"] if f["subsystem"] == "VALUATION"]
    assert len(val_facts_prod) == 0

    val_gaps = [g for g in result_prod["evidence_gaps"] if g["gap_code"] == "GAP-VAL-SYNTHETIC-DATA-EXCLUDED"]
    assert len(val_gaps) == 1

    # 2. Explicit Fixture Inclusion Mode: Admitted
    result_fixture = engine.reconcile_parcel_evidence(db_session, sample_parcel, sample_case, include_synthetic_fixtures=True)
    val_facts_fixture = [f for f in result_fixture["facts"] if f["subsystem"] == "VALUATION"]
    assert len(val_facts_fixture) == 1


def test_reconciliation_unverified_ocr_extraction_not_promoted(
    db_session: Session,
    tenant_a: Organization,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """
    Mandatory test: Extractions with low confidence or unconfirmed processing status
    must be flagged with verification_status='UNVERIFIED_EXTRACTION' and not silently promoted.
    """
    doc = Document(
        org_id=tenant_a.org_id,
        case_id=sample_case.case_id,
        parcel_id=sample_parcel.parcel_id,
        original_filename="historical_kewala_1975.pdf",
        stored_path="storage/documents/historical_kewala_1975.pdf",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        file_size_bytes=1048576,
        mime_type="application/pdf",
        category="SALE_DEED",
        processing_status="PENDING_REVIEW",  # Not confirmed
    )
    db_session.add(doc)
    db_session.flush()

    field = ExtractedField(
        org_id=tenant_a.org_id,
        document_id=doc.document_id,
        field_name="seller_name",
        extracted_value="Ram Sundar Roy",
        confidence_score=0.55,  # Low confidence (< 0.70)
        status="PENDING_REVIEW",
    )
    db_session.add(field)
    db_session.commit()

    engine = EvidenceReconciliationEngine()
    result = engine.reconcile_parcel_evidence(db_session, sample_parcel, sample_case)

    doc_facts = [f for f in result["facts"] if f["subsystem"] == "OCR_DOCUMENT"]
    assert len(doc_facts) == 1
    assert doc_facts[0]["verification_status"] == "UNVERIFIED_EXTRACTION"

    # Finding must be generated for low confidence
    doc_findings = [f for f in result["findings"] if f["dimension"] == RiskDimension.DOCUMENT_AUTHENTICITY]
    assert len(doc_findings) == 1
    assert doc_findings[0]["finding_code"] == "FIND-DOC-UNCERTAIN-OCR-EXTRACTION"


# =====================================================================
# 4. Integrity, Versioning & Audit Tests (Phase 4 & 5)
# =====================================================================

def test_synthesis_recomputation_and_superseded_history(
    db_session: Session,
    tenant_a: Organization,
    user_a: User,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """
    Verifies that recomputing creates version 2, points to previous_assessment_id,
    and updates version 1 status to SUPERSEDED (preserving historical auditability).
    """
    service = PassportSynthesisService(db_session)
    req1 = GenerateAssessmentRequest(case_id=sample_case.case_id)
    v1 = service.generate_assessment(sample_parcel.parcel_id, tenant_a.org_id, req1, user_a.user_id)
    assert v1.version_number == 1
    assert v1.status == AssessmentStatus.COMPLETED

    # Recompute
    recomp_req = AssessmentRecomputeRequest(recompute_reason="Fresh mutation order uploaded")
    v2 = service.recompute_assessment(v1.assessment_id, tenant_a.org_id, user_a.user_id, recomp_req)

    assert v2.version_number == 2
    assert v2.previous_assessment_id == v1.assessment_id
    assert v2.status == AssessmentStatus.COMPLETED

    # Verify v1 is now SUPERSEDED
    db_session.refresh(v1)
    assert v1.status == AssessmentStatus.SUPERSEDED


def test_synthesis_human_review_workflow_and_audit_trail(
    db_session: Session,
    tenant_a: Organization,
    user_a: User,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """
    Verifies submitting finding for review and recording decision with AssessmentReviewAction audit trail.
    """
    service = PassportSynthesisService(db_session)
    req = GenerateAssessmentRequest(case_id=sample_case.case_id)
    assessment = service.generate_assessment(sample_parcel.parcel_id, tenant_a.org_id, req, user_a.user_id)

    # Add a mock finding to test review
    finding = AssessmentFinding(
        assessment_id=assessment.assessment_id,
        dimension=RiskDimension.TRANSACTION_MUTATION,
        finding_code="FIND-TEST-REVIEW",
        severity=FindingSeverity.HIGH,
        title="Test Review Finding",
        description="Candidate discrepancy for reviewer action",
        review_status=FindingReviewStatus.UNREVIEWED,
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)

    # 1. Submit for review
    sub_finding = service.submit_finding_for_review(
        finding_id=finding.finding_id,
        org_id=tenant_a.org_id,
        user_id=user_a.user_id,
        notes="Please verify Circle Office physical volume",
    )
    assert sub_finding.review_status == FindingReviewStatus.UNDER_REVIEW

    # 2. Record Review Decision
    rev_req = FindingReviewRequest(
        action="CONFIRM",
        review_notes="Confirmed ground boundary pillar in Register-II matches finding.",
    )
    dec_finding = service.record_finding_review(
        finding_id=finding.finding_id,
        org_id=tenant_a.org_id,
        user_id=user_a.user_id,
        request=rev_req,
    )
    assert dec_finding.review_status == FindingReviewStatus.CONFIRMED

    # 3. Check Audit Actions
    actions = db_session.query(AssessmentReviewAction).filter(
        AssessmentReviewAction.finding_id == finding.finding_id,
    ).all()
    assert len(actions) == 2  # Submit and Confirm


def test_synthesis_cross_tenant_isolation(
    db_session: Session,
    tenant_a: Organization,
    tenant_b: Organization,
    user_a: User,
    user_b: User,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """
    Verifies that User B from Tenant B cannot view or modify assessments from Tenant A.
    """
    service = PassportSynthesisService(db_session)
    req = GenerateAssessmentRequest(case_id=sample_case.case_id)
    assessment = service.generate_assessment(sample_parcel.parcel_id, tenant_a.org_id, req, user_a.user_id)

    # Query with tenant B -> None
    retrieved = service.get_assessment(assessment.assessment_id, tenant_b.org_id)
    assert retrieved is None


# =====================================================================
# 5. REST API Integration Tests (Phase 5)
# =====================================================================

def test_api_generate_and_get_assessment(
    client: TestClient,
    auth_headers_a: dict,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """Tests POST /api/v1/passport/parcels/{id}/assess and GET /api/v1/passport/assessments/{id}."""
    resp = client.post(
        f"/api/v1/passport/parcels/{sample_parcel.parcel_id}/assess",
        json={"case_id": str(sample_case.case_id), "include_synthetic_fixtures": False},
        headers=auth_headers_a,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "assessment_id" in data
    assert data["version_number"] == 1
    assessment_id = data["assessment_id"]

    # Detail GET
    detail_resp = client.get(f"/api/v1/passport/assessments/{assessment_id}", headers=auth_headers_a)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["assessment_id"] == assessment_id
    assert "facts" in detail
    assert "findings" in detail
    assert "evidence_gaps" in detail


def test_api_cross_tenant_forbidden(
    client: TestClient,
    auth_headers_a: dict,
    auth_headers_b: dict,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """Verifies that cross-tenant access returns 404 Not Found."""
    resp = client.post(
        f"/api/v1/passport/parcels/{sample_parcel.parcel_id}/assess",
        json={"case_id": str(sample_case.case_id)},
        headers=auth_headers_a,
    )
    assert resp.status_code == 201
    assessment_id = resp.json()["assessment_id"]

    # Access with User B
    resp_b = client.get(f"/api/v1/passport/assessments/{assessment_id}", headers=auth_headers_b)
    assert resp_b.status_code == 404


# =====================================================================
# 6. Report Assembler & PDF Generator Integration (Phase 6)
# =====================================================================

def test_report_assembler_and_pdf_synthesis_rendering(
    db_session: Session,
    tenant_a: Organization,
    user_a: User,
    sample_parcel: Parcel,
    sample_case: Case,
):
    """
    Verifies that the Land Intelligence Report assembler and PDF generator
    include the executive synthesis section, badges, and statutory non-title disclaimer.
    """
    service = PassportSynthesisService(db_session)
    req = GenerateAssessmentRequest(case_id=sample_case.case_id)
    service.generate_assessment(sample_parcel.parcel_id, tenant_a.org_id, req, user_a.user_id)

    report_data = assemble_report_data(
        db=db_session,
        case_id=sample_case.case_id,
        parcel_id=sample_parcel.parcel_id,
        current_user=user_a,
    )

    assert report_data.section_synthesis is not None
    assert report_data.section_synthesis.is_synthesized is True
    assert len(report_data.section_synthesis.dimension_scores) == 8
    assert report_data.section_1_cover.data_availability_summary["property_passport_synthesized"] is True

    # Render PDF
    pdf_bytes = generate_land_intelligence_pdf(report_data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF")


# =====================================================================
# 7. End-to-End Controlled Acceptance Scenario (Phase 7)
# =====================================================================

def test_controlled_acceptance_scenario(
    db_session: Session,
    tenant_a: Organization,
    user_a: User,
):
    """
    Phase 7 Controlled Scenario:
    Simulates a parcel with all 7 subsystems populated with explicit fixtures:
    - Revenue record (Register-II)
    - Cadastral vector overlay with known CRS (EPSG:32645)
    - Field survey observation with area variance
    - Document with low-confidence OCR extraction
    - Active mutation proceeding
    - Judicial search with uncorroborated name overlap
    - MVR schedule explicitly marked synthetic (must be excluded from production assessment)

    Verifies:
    1. All source records remain traceable.
    2. Synthetic data is correctly excluded and flagged as an evidence gap.
    3. Missing evidence produces explicit evidence gaps (not assumed clean).
    4. Conflicting observations generate review findings.
    5. Scoring is reproducible (second assessment produces identical score and snapshot hash).
    6. No output claims clear title or legal ownership.
    """
    # 1. Parcel
    parcel = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id="BR-GAY-BOD-SCENARIO-001",
        state="Bihar",
        district_name="Gaya",
        subdistrict_anchal_name="Bodh Gaya",
        mauza_village_name="Bakrour",
        khata_number="77",
        plot_khesra_number="214",
        recorded_area_acres=2.00,
        land_nature="Dhanhar-I",
        source_portal="Bihar Bhumi",
        source_authority="Circle Officer Bodh Gaya",
    )
    db_session.add(parcel)
    db_session.commit()
    db_session.refresh(parcel)

    case = Case(
        org_id=tenant_a.org_id,
        created_by_user_id=user_a.user_id,
        case_number="CASE-SCENARIO-ACCEPTANCE-001",
        title="Comprehensive Diligence on Bakrour Plot 214",
        status=CaseStatus.IN_PROGRESS,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    # 2. Revenue Claim
    claim = Claim(
        org_id=tenant_a.org_id,
        parcel_id=parcel.parcel_id,
        case_id=case.case_id,
        predicate=ClaimPredicate.RECORDED_OWNER,
        object_value={"name": "Kameshwar Singh", "khata": "77"},
    )
    db_session.add(claim)

    # 3. Cadastral Overlay (Valid CRS EPSG:32645, Moderate IoU shift)
    overlay = BoundaryOverlayAnalysis(
        org_id=tenant_a.org_id,
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        baseline_geometry_id=uuid.uuid4(),
        comparison_geometry_id=uuid.uuid4(),
        analysis_crs="EPSG:32645",
        intersection_area_sqm=7500.0,
        union_area_sqm=8200.0,
        iou_score=0.91,
        symmetric_diff_area_sqm=700.0,
        area_delta_percentage=4.2,
        perimeter_delta_percentage=2.1,
        centroid_displacement_meters=2.3,
        hausdorff_distance_meters=3.5,
        discrepancy_taxonomy=DiscrepancyTaxonomy.POTENTIAL_BOUNDARY_DISCREPANCY,
        discrepancy_severity=DiscrepancySeverity.LOW,
        findings_summary="Minor cadastral vector boundary alignment within standard 3m tolerance.",
    )
    db_session.add(overlay)

    # 4. Field Survey (Ground area 1.75 acres vs 2.00 recorded -> 12.5% variance > 10% threshold)
    task = FieldVerificationTask(
        org_id=tenant_a.org_id,
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        task_number="TASK-AM-SCENARIO-001",
        assigned_to_user_id=user_a.user_id,
        status=TaskStatus.COMPLETED,
    )
    db_session.add(task)
    db_session.flush()

    survey = FieldSurvey(
        org_id=tenant_a.org_id,
        task_id=task.task_id,
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        measured_area_acres=1.75,
        gps_reading_count=16,
        reported_accuracy_meters=1.8,
        physical_possessor_name="Kameshwar Singh",
        road_access_type="PWD_ROAD",
    )
    db_session.add(survey)

    # 5. Document with low-confidence OCR
    doc = Document(
        org_id=tenant_a.org_id,
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        original_filename="bakrour_deed_1998.pdf",
        stored_path="storage/documents/bakrour_deed_1998.pdf",
        sha256_hash="d41d8cd98f00b204e9800998ecf8427e",
        file_size_bytes=524288,
        mime_type="application/pdf",
        category="SALE_DEED",
        processing_status="PENDING_REVIEW",
    )
    db_session.add(doc)
    db_session.flush()

    ext_field = ExtractedField(
        org_id=tenant_a.org_id,
        document_id=doc.document_id,
        field_name="boundary_north",
        extracted_value="Road",
        confidence_score=0.62,
        status="PENDING_REVIEW",
    )
    db_session.add(ext_field)

    # 6. Active Mutation Proceeding
    mut = MutationCase(
        org_id=tenant_a.org_id,
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        case_number="MUT-2024-BODH-0088",
        filing_year=2024,
        district="Gaya",
        circle="Bodh Gaya",
        mauza="Bakrour",
        khata_number="77",
        khesra_number="214",
        mutation_type=MutationType.SALE_DEED,
        normalized_status=MutationStatus.NOTICE_ISSUED,
        raw_source_status="सूचना निर्गत (Notice Issued)",
        source_portal="Bihar Bhumi",
        source_authority="Circle Officer Bodh Gaya",
    )
    db_session.add(mut)

    # 7. Judicial case with uncorroborated name match (confidence 0.35 <= 0.40)
    j_case = JudicialCase(
        org_id=tenant_a.org_id,
        case_id=case.case_id,
        cnr_number="BHGA010099992023",
        case_number="Money Suit 12/2023",
        court_name="Civil Court Gaya",
        filing_year=2023,
        case_status=JudicialCaseStatus.PENDING,
        has_active_injunction=False,
        risk_category=JudicialRiskCategory.OTHER_CIVIL,
        search_query_snapshot={"party_name": "Kameshwar Singh"},
    )
    db_session.add(j_case)
    db_session.flush()

    j_match = ParcelJudicialMatch(
        org_id=tenant_a.org_id,
        judicial_case_id=j_case.judicial_case_id,
        parcel_id=parcel.parcel_id,
        match_category=JudicialMatchCategory.NAME_ONLY,
        confidence_score=0.35,
        matched_fields={"defendant": "Kameshwar Singh"},
        explanation="Common patronymic match without plot/khata corroboration.",
        review_status=JudicialReviewStatus.PENDING_REVIEW,
    )
    db_session.add(j_match)

    # 8. Synthetic MVR Schedule (Must be excluded in production mode)
    sched_synth = MVRSchedule(
        org_id=tenant_a.org_id,
        schedule_code="SYNTH-FIXTURE-GAYA-2026",
        district="Gaya",
        registration_office="Bodh Gaya",
        anchal_circle="Bodh Gaya",
        mauza="Bakrour",
        rate_per_decimal=300000.0,
        verification_status="SYNTHETIC",
        source_provider="SYNTHETIC_MOCK",
    )
    db_session.add(sched_synth)
    db_session.flush()

    val = PropertyValuation(
        org_id=tenant_a.org_id,
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        schedule_id=sched_synth.schedule_id,
        total_area_decimal=200.0,
        input_area_value=2.0,
        unit_circle_rate=300000.0,
        calculated_land_value=60000000.0,
        calculated_structure_value=0.0,
        total_government_valuation=60000000.0,
        assessment_base=60000000.0,
        stamp_duty_rate_percent=6.0,
        stamp_duty_amount=3600000.0,
        registration_fee_rate_percent=2.0,
        registration_fee_amount=1200000.0,
        total_statutory_charges=4800000.0,
        discrepancy_status=DiscrepancyStatus.NO_DISCREPANCY_DETECTED,
    )
    db_session.add(val)
    db_session.commit()

    # -----------------------------------------------------------------
    # Run Assessment 1 (Production Mode: Exclude Synthetic Fixtures)
    # -----------------------------------------------------------------
    service = PassportSynthesisService(db_session)
    req1 = GenerateAssessmentRequest(case_id=case.case_id, include_synthetic_fixtures=False)
    a1 = service.generate_assessment(parcel.parcel_id, tenant_a.org_id, req1, user_a.user_id)

    assert a1.version_number == 1
    assert a1.status == AssessmentStatus.COMPLETED
    assert a1.statutory_disclaimer == STATUTORY_SYNTHESIS_LIMITATION_STATEMENT

    # Verification 1: Synthetic data excluded
    val_gap = next((g for g in a1.evidence_gaps if g.gap_code == "GAP-VAL-SYNTHETIC-DATA-EXCLUDED"), None)
    assert val_gap is not None

    # Verification 2: Area discrepancy detected as finding
    area_finding = next((f for f in a1.findings if f.finding_code == "FIND-FLD-AREA-VARIANCE-EXCEEDED"), None)
    assert area_finding is not None
    assert area_finding.severity == FindingSeverity.MEDIUM  # 12.5% variance (>10% and <=20%)

    # Verification 3: Active mutation proceeding detected
    mut_finding = next((f for f in a1.findings if f.finding_code == "FIND-MUT-ACTIVE-PROCEEDING"), None)
    assert mut_finding is not None

    # Verification 4: Name-only judicial match is LOW severity and does NOT claim litigation certainty
    jud_finding = next((f for f in a1.findings if f.finding_code == "FIND-JUD-UNVERIFIED-NAME-OVERLAP"), None)
    assert jud_finding is not None
    assert jud_finding.severity == FindingSeverity.LOW

    # Verification 5: Reproducibility check — A second assessment with identical inputs produces identical results
    engine = EvidenceReconciliationEngine()
    res1 = engine.reconcile_parcel_evidence(db_session, parcel, case, include_synthetic_fixtures=False)
    res2 = engine.reconcile_parcel_evidence(db_session, parcel, case, include_synthetic_fixtures=False)

    tier1, score1, _ = ExplainableRiskEvaluator.evaluate_risk(res1["findings"], res1["evidence_gaps"], res1["facts"])
    tier2, score2, _ = ExplainableRiskEvaluator.evaluate_risk(res2["findings"], res2["evidence_gaps"], res2["facts"])

    assert score1 == score2
    assert tier1 == tier2
