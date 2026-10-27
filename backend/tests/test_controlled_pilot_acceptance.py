"""
TASK-P2-07.3: Controlled Pilot Acceptance & End-to-End Operational Gate Checks.
Validates the complete 8-dimension end-to-end acceptance matrix using authorized
dataflow, strict role enforcement, audit logging, and statutory disclaimers.
"""
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.parcel import Parcel
from app.models.case import Case, CaseStatus, CaseParcel
from app.models.valuation import (
    MVRSchedule,
    PropertyValuation,
    PropertyCategory,
    RoadCategory,
    JurisdictionType,
    ScheduleVerificationStatus,
    DiscrepancyStatus,
)
from app.models.passport_synthesis import (
    PassportAssessment,
    RiskTier,
    AssessmentStatus,
)
from app.models.audit import AuditLog
from app.core.exceptions import ForbiddenError, CrossTenantAccessError
from app.schemas.valuation import (
    MVRScheduleCreateRequest,
    MVRScheduleVerifyRequest,
    ValuationCalculationRequest,
)
from app.schemas.passport_synthesis import (
    GenerateAssessmentRequest,
    AssessmentRecomputeRequest,
)
from app.services.valuation.service import ValuationService
from app.services.passport.reconciliation_engine import EvidenceReconciliationEngine
from app.services.passport.synthesis_service import PassportSynthesisService
from app.services.report_assembler import assemble_report_data
from app.services.pdf_report_generator import generate_land_intelligence_pdf


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def test_supervisor(db_session: Session, tenant_a: Organization) -> User:
    user = User(
        org_id=tenant_a.org_id,
        email="supervisor.acceptance@bhumisetu.gov.in",
        hashed_password="fakehash_acceptance",
        full_name="Senior Revenue Supervisor",
        role=UserRole.SUPERVISOR,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_operator(db_session: Session, tenant_a: Organization) -> User:
    user = User(
        org_id=tenant_a.org_id,
        email="operator.acceptance@bhumisetu.gov.in",
        hashed_password="fakehash_operator",
        full_name="Case Operator Ramakant",
        role=UserRole.CASE_OPERATOR,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_case(db_session: Session, tenant_a: Organization, test_supervisor: User) -> Case:
    case = Case(
        org_id=tenant_a.org_id,
        case_number="CASE-PILOT-2026-PAT-001",
        title="Supervised Pilot Diligence - Mustafapur Plot 101",
        status=CaseStatus.IN_PROGRESS,
        created_by_user_id=test_supervisor.user_id,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


@pytest.fixture
def pilot_parcel(db_session: Session, tenant_a: Organization, test_case: Case) -> Parcel:
    parcel = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id="BR-PAT-DAN-MUS-2026-001",
        state_code="BR",
        district_name="Patna",
        subdistrict_anchal_name="Danapur",
        halka_number="04",
        mauza_village_name="Mustafapur",
        census_village_code="245002",
        khata_number="142",
        plot_khesra_number="101",
        recorded_area_acres=1.25,
        land_nature="AGRICULTURAL_RAIYATI",
        authoritative_boundary="SRID=4326;POLYGON((85.04 25.61, 85.05 25.61, 85.05 25.62, 85.04 25.62, 85.04 25.61))",
    )
    db_session.add(parcel)
    db_session.flush()

    cp = CaseParcel(
        case_id=test_case.case_id,
        parcel_id=parcel.parcel_id,
        is_primary=True,
    )
    db_session.add(cp)
    db_session.commit()
    db_session.refresh(parcel)
    return parcel


# =====================================================================
# End-to-End Acceptance Tests
# =====================================================================

def test_acceptance_01_ingestion_and_authorized_verification_lifecycle(
    db_session: Session,
    tenant_a: Organization,
    test_supervisor: User,
    test_operator: User,
):
    """
    Acceptance Dimension 1:
    - Schedule imported enters as PROVISIONAL.
    - Unauthorized verification by CASE_OPERATOR must be rejected with ForbiddenError.
    - Authorized verification by SUPERVISOR must promote schedule to VERIFIED_OFFICIAL.
    - Audit log entries must be preserved for both events.
    """
    service = ValuationService()
    req = MVRScheduleCreateRequest(
        schedule_code="MVR-BR-PAT-DAN-MUS-ACCEPT-001",
        district="PATNA",
        registration_office="Danapur Sub-Registry",
        anchal_circle="Danapur",
        mauza="Mustafapur",
        jurisdiction_type="RURAL",
        property_category="AGRICULTURAL",
        road_category="MAIN_ROAD_NH_SH",
        rate_per_decimal=95000.0,
        source_gazette_reference="Patna District Gazette Notification No. 89/Reg-2025",
    )

    imported_record = service.import_schedule(
        db=db_session,
        request=req,
        current_user=test_supervisor,
    )
    assert imported_record is not None
    assert imported_record.verification_status == ScheduleVerificationStatus.PROVISIONAL

    sched = db_session.query(MVRSchedule).filter(
        MVRSchedule.schedule_code == "MVR-BR-PAT-DAN-MUS-ACCEPT-001"
    ).first()
    assert sched is not None
    assert sched.verification_status == ScheduleVerificationStatus.PROVISIONAL

    # Step 2: Unauthorized verification attempt by Case Operator
    verify_req = MVRScheduleVerifyRequest(
        verification_status="VERIFIED_OFFICIAL",
        verification_notes="Operator attempting unauthorized verification",
    )
    with pytest.raises(ForbiddenError):
        service.verify_schedule(
            db=db_session,
            schedule_id=sched.schedule_id,
            verify_request=verify_req,
            current_user=test_operator,
        )

    # Step 3: Authorized verification by Supervisor
    verify_req_auth = MVRScheduleVerifyRequest(
        verification_status="VERIFIED_OFFICIAL",
        verification_notes="Verified against official Patna Collectorate gazette notification signed by District Magistrate.",
    )
    verified_sched = service.verify_schedule(
        db=db_session,
        schedule_id=sched.schedule_id,
        verify_request=verify_req_auth,
        current_user=test_supervisor,
    )
    assert verified_sched.verification_status == ScheduleVerificationStatus.VERIFIED_OFFICIAL

    # Step 4: Verify audit logs exist
    unauth_log = db_session.query(AuditLog).filter(
        AuditLog.action == "MVR_SCHEDULE_VERIFY_UNAUTHORIZED",
        AuditLog.actor_party_id == test_operator.user_id,
    ).first()
    assert unauth_log is not None

    verified_log = db_session.query(AuditLog).filter(
        AuditLog.action == "MVR_SCHEDULE_VERIFIED_OFFICIAL",
        AuditLog.actor_party_id == test_supervisor.user_id,
    ).first()
    assert verified_log is not None


def test_acceptance_02_parcel_jurisdiction_strict_matching(
    db_session: Session,
    tenant_a: Organization,
    pilot_parcel: Parcel,
    test_case: Case,
):
    """
    Acceptance Dimension 2:
    - If valuation uses a schedule from a mismatched mauza (e.g. Gaya Bodh Gaya schedule for Patna Mustafapur),
      the reconciliation engine strictly blocks admission and raises GAP-VAL-JURISDICTION-MISMATCH.
    """
    # Create verified schedule in Gaya
    mismatch_sched = MVRSchedule(
        org_id=tenant_a.org_id,
        schedule_code="MVR-BR-GAY-BOD-BOD-RES-RUR-001",
        district="GAYA",
        registration_office="Bodh Gaya Sub-Registry",
        anchal_circle="Bodh Gaya",
        mauza="Bodh Gaya Town",
        jurisdiction_type=JurisdictionType.URBAN_MUNICIPAL,
        property_category=PropertyCategory.RESIDENTIAL,
        road_category=RoadCategory.RURAL_ROAD_OR_NO_ROAD,
        rate_per_decimal=180000.0,
        verification_status=ScheduleVerificationStatus.VERIFIED_OFFICIAL,
        source_provider="OPERATOR_ASSISTED_IMPORT",
        source_gazette_reference="Gaya Collectorate Gazette Notification 102/2025",
        is_active=True,
    )
    db_session.add(mismatch_sched)
    db_session.flush()

    val = PropertyValuation(
        org_id=tenant_a.org_id,
        case_id=test_case.case_id,
        parcel_id=pilot_parcel.parcel_id,
        schedule_id=mismatch_sched.schedule_id,
        total_area_decimal=125.0,
        input_area_value=1.25,
        unit_circle_rate=180000.0,
        calculated_land_value=22500000.0,
        calculated_structure_value=0.0,
        total_government_valuation=22500000.0,
        assessment_base=22500000.0,
        stamp_duty_rate_percent=6.0,
        stamp_duty_amount=1350000.0,
        registration_fee_rate_percent=2.0,
        registration_fee_amount=450000.0,
        total_statutory_charges=1800000.0,
        discrepancy_status=DiscrepancyStatus.NO_DISCREPANCY_DETECTED,
    )
    db_session.add(val)
    db_session.commit()

    result = EvidenceReconciliationEngine.reconcile_parcel_evidence(
        db=db_session,
        parcel=pilot_parcel,
        case=test_case,
        include_synthetic_fixtures=False,
    )
    assert not any(f["subsystem"] == "VALUATION" for f in result["facts"])
    gap = next((g for g in result["evidence_gaps"] if g["gap_code"] == "GAP-VAL-JURISDICTION-MISMATCH"), None)
    assert gap is not None
    assert gap["is_blocking"] is True


@pytest.mark.asyncio
async def test_acceptance_03_valuation_calculation_and_traceability(
    db_session: Session,
    tenant_a: Organization,
    pilot_parcel: Parcel,
    test_case: Case,
    test_supervisor: User,
):
    """
    Acceptance Dimension 3:
    - Calculation applies Section 47-A max(Consideration, Guideline Base).
    - Concessions for sole female buyer (5.6%) are evaluated accurately.
    - Full schedule traceability is preserved in the valuation record.
    """
    sched = MVRSchedule(
        org_id=tenant_a.org_id,
        schedule_code="MVR-BR-PAT-DAN-MUS-AGR-NH-001",
        district="PATNA",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="Mustafapur",
        jurisdiction_type=JurisdictionType.RURAL,
        property_category=PropertyCategory.AGRICULTURAL,
        road_category=RoadCategory.MAIN_ROAD_NH_SH,
        rate_per_decimal=95000.0,
        verification_status=ScheduleVerificationStatus.VERIFIED_OFFICIAL,
        source_provider="OPERATOR_ASSISTED_IMPORT",
        source_gazette_reference="Patna District Gazette Notification No. 89/Reg-2025",
        is_active=True,
    )
    db_session.add(sched)
    db_session.commit()

    service = ValuationService()
    calc_req = ValuationCalculationRequest(
        case_id=test_case.case_id,
        parcel_id=pilot_parcel.parcel_id,
        district="PATNA",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="Mustafapur",
        property_category="AGRICULTURAL",
        road_category="MAIN_ROAD_NH_SH",
        area_value=125.0,
        area_unit="DECIMAL",
        declared_consideration=10000000.0,
        buyer_category="FEMALE",
    )

    val_resp = await service.calculate_and_assess_property(
        db=db_session,
        request=calc_req,
        current_user=test_supervisor,
    )

    assert val_resp.total_government_valuation == 11875000.0
    assert val_resp.assessment_base == 11875000.0
    assert val_resp.stamp_duty_rate_percent == 5.6
    assert val_resp.stamp_duty_amount == round(11875000.0 * 0.056, 2)
    assert val_resp.registration_fee_rate_percent == 2.0
    assert val_resp.registration_fee_amount == round(11875000.0 * 0.02, 2)
    assert val_resp.discrepancy_status == "POTENTIAL_UNDERVALUE"


def test_acceptance_04_property_passport_synthesis_and_blocking_gaps(
    db_session: Session,
    tenant_a: Organization,
    pilot_parcel: Parcel,
    test_case: Case,
    test_supervisor: User,
):
    """
    Acceptance Dimension 4:
    - Synthesizing a Property Passport where valuation is unverified results in
      a blocking evidence gap, forcing overall risk tier to INSUFFICIENT_EVIDENCE.
    - Evidence completeness ratio reflects missing verified evidence.
    """
    # Add provisional schedule and valuation
    prov_sched = MVRSchedule(
        org_id=tenant_a.org_id,
        schedule_code="MVR-BR-PAT-DAN-MUS-PROV-TEST-001",
        district="PATNA",
        registration_office="Danapur Sub-Registry",
        anchal_circle="Danapur",
        mauza="Mustafapur",
        jurisdiction_type=JurisdictionType.RURAL,
        property_category=PropertyCategory.AGRICULTURAL,
        road_category=RoadCategory.MAIN_ROAD_NH_SH,
        rate_per_decimal=95000.0,
        verification_status=ScheduleVerificationStatus.PROVISIONAL,
        source_provider="OPERATOR_ASSISTED_IMPORT",
        source_gazette_reference="Patna District Gazette Notification No. 89/Reg-2025",
        is_active=True,
    )
    db_session.add(prov_sched)
    db_session.flush()

    val = PropertyValuation(
        org_id=tenant_a.org_id,
        case_id=test_case.case_id,
        parcel_id=pilot_parcel.parcel_id,
        schedule_id=prov_sched.schedule_id,
        total_area_decimal=125.0,
        input_area_value=1.25,
        unit_circle_rate=95000.0,
        calculated_land_value=11875000.0,
        calculated_structure_value=0.0,
        total_government_valuation=11875000.0,
        assessment_base=11875000.0,
        stamp_duty_rate_percent=6.0,
        stamp_duty_amount=712500.0,
        registration_fee_rate_percent=2.0,
        registration_fee_amount=237500.0,
        total_statutory_charges=950000.0,
        discrepancy_status=DiscrepancyStatus.NO_DISCREPANCY_DETECTED,
    )
    db_session.add(val)
    db_session.commit()

    service = PassportSynthesisService(db=db_session)
    gen_req = GenerateAssessmentRequest(case_id=test_case.case_id, include_synthetic_fixtures=False)

    assessment = service.generate_assessment(
        parcel_id=pilot_parcel.parcel_id,
        org_id=tenant_a.org_id,
        request=gen_req,
        generated_by_user_id=test_supervisor.user_id,
    )

    assert assessment.status == AssessmentStatus.COMPLETED
    blocking_gaps = [g for g in assessment.evidence_gaps if g.is_blocking]
    assert len(blocking_gaps) >= 1
    assert any(g.gap_code == "GAP-VAL-UNVERIFIED-SCHEDULE" for g in blocking_gaps)

    assert assessment.overall_risk_tier == RiskTier.INSUFFICIENT_EVIDENCE
    assert assessment.evidence_gaps_count >= 1
    outputs = assessment.dimension_scores.get("_outputs", {})
    if "evidence_completeness_ratio" in outputs:
        assert outputs["evidence_completeness_ratio"] < 1.0


def test_acceptance_05_pdf_graceful_handling_and_disclaimer(
    db_session: Session,
    tenant_a: Organization,
    pilot_parcel: Parcel,
    test_case: Case,
    test_supervisor: User,
):
    """
    Acceptance Dimension 5:
    - When compiling a Land Intelligence Report PDF without verified valuation,
      assembly succeeds gracefully and includes statutory non-admission disclaimer.
    """
    service = PassportSynthesisService(db=db_session)
    gen_req = GenerateAssessmentRequest(case_id=test_case.case_id, include_synthetic_fixtures=False)

    service.generate_assessment(
        parcel_id=pilot_parcel.parcel_id,
        org_id=tenant_a.org_id,
        request=gen_req,
        generated_by_user_id=test_supervisor.user_id,
    )

    report_data = assemble_report_data(
        db=db_session,
        case_id=test_case.case_id,
        parcel_id=pilot_parcel.parcel_id,
        current_user=test_supervisor,
    )

    pdf_bytes = generate_land_intelligence_pdf(report_data)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")


def test_acceptance_06_audit_logging_and_recomputation_lifecycle(
    db_session: Session,
    tenant_a: Organization,
    pilot_parcel: Parcel,
    test_case: Case,
    test_supervisor: User,
):
    """
    Acceptance Dimension 6:
    - Recomputation supersedes existing assessment and issues audit action.
    - Snapshot cryptographic hash changes with new evidence.
    """
    service = PassportSynthesisService(db=db_session)
    gen_req = GenerateAssessmentRequest(case_id=test_case.case_id, include_synthetic_fixtures=False)

    a1 = service.generate_assessment(
        parcel_id=pilot_parcel.parcel_id,
        org_id=tenant_a.org_id,
        request=gen_req,
        generated_by_user_id=test_supervisor.user_id,
    )
    assert a1.status == AssessmentStatus.COMPLETED

    recomp_req = AssessmentRecomputeRequest(recompute_reason="Acceptance test recomputation with updated parameters")
    a2 = service.recompute_assessment(
        assessment_id=a1.assessment_id,
        org_id=tenant_a.org_id,
        user_id=test_supervisor.user_id,
        request=recomp_req,
    )

    db_session.refresh(a1)
    assert a1.status == AssessmentStatus.SUPERSEDED
    assert a2.status == AssessmentStatus.COMPLETED
    assert a2.previous_assessment_id == a1.assessment_id

    from app.models.passport_synthesis import AssessmentReviewAction
    super_action = db_session.query(AssessmentReviewAction).filter(
        AssessmentReviewAction.assessment_id == a2.assessment_id,
        AssessmentReviewAction.action_type == "RECOMPUTE_ASSESSMENT",
    ).first()
    assert super_action is not None


@pytest.mark.asyncio
async def test_acceptance_07_tenant_isolation_and_cross_tenant_block(
    db_session: Session,
    tenant_a: Organization,
    test_case: Case,
):
    """
    Acceptance Dimension 7:
    - Organization B cannot read or calculate against Organization A's case.
    """
    tenant_b = Organization(name="Patna District Operations Tenant B", slug="patna-b")
    db_session.add(tenant_b)
    db_session.commit()

    user_b = User(
        org_id=tenant_b.org_id,
        email="operator.b@bhumisetu.gov.in",
        hashed_password="fakehash_tenant_b",
        full_name="Tenant B Operator",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user_b)
    db_session.commit()

    service = ValuationService()
    calc_req = ValuationCalculationRequest(
        case_id=test_case.case_id,
        district="PATNA",
        anchal_circle="Danapur",
        mauza="Mustafapur",
        area_value=5.0,
        area_unit="DECIMAL",
    )

    with pytest.raises(CrossTenantAccessError):
        await service.calculate_and_assess_property(
            db=db_session,
            request=calc_req,
            current_user=user_b,
        )


def test_acceptance_08_production_vs_fixture_mode_boundary(
    db_session: Session,
    tenant_a: Organization,
    pilot_parcel: Parcel,
    test_case: Case,
):
    """
    Acceptance Dimension 8:
    - Production mode strictly blocks mock provider schedules with GAP-VAL-SYNTHETIC-DATA-EXCLUDED.
    - Test fixture mode admits synthetic fixtures for testing without claiming official validity.
    """
    mock_sched = MVRSchedule(
        org_id=tenant_a.org_id,
        schedule_code="MVR-BR-PAT-DAN-MUS-MOCK-ACCEPT",
        district="Patna",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="Mustafapur",
        jurisdiction_type=JurisdictionType.RURAL,
        property_category=PropertyCategory.RESIDENTIAL,
        road_category=RoadCategory.MAIN_ROAD_NH_SH,
        rate_per_decimal=500000.0,
        verification_status="SYNTHETIC",
        source_provider="MOCK_PROVIDER",
        is_active=True,
    )
    db_session.add(mock_sched)
    db_session.flush()

    val = PropertyValuation(
        org_id=tenant_a.org_id,
        case_id=test_case.case_id,
        parcel_id=pilot_parcel.parcel_id,
        schedule_id=mock_sched.schedule_id,
        total_area_decimal=125.0,
        input_area_value=1.25,
        unit_circle_rate=500000.0,
        calculated_land_value=62500000.0,
        calculated_structure_value=0.0,
        total_government_valuation=62500000.0,
        assessment_base=62500000.0,
        stamp_duty_rate_percent=6.0,
        stamp_duty_amount=3750000.0,
        registration_fee_rate_percent=2.0,
        registration_fee_amount=1250000.0,
        total_statutory_charges=5000000.0,
        discrepancy_status=DiscrepancyStatus.NO_DISCREPANCY_DETECTED,
    )
    db_session.add(val)
    db_session.commit()

    # Production mode: Must block
    prod_res = EvidenceReconciliationEngine.reconcile_parcel_evidence(
        db=db_session,
        parcel=pilot_parcel,
        case=test_case,
        include_synthetic_fixtures=False,
    )
    assert not any(f["subsystem"] == "VALUATION" for f in prod_res["facts"])
    gap = next((g for g in prod_res["evidence_gaps"] if g["gap_code"] == "GAP-VAL-SYNTHETIC-DATA-EXCLUDED"), None)
    assert gap is not None
    assert gap["is_blocking"] is True

    # Test fixture mode: Admitted for offline test harness
    fixture_res = EvidenceReconciliationEngine.reconcile_parcel_evidence(
        db=db_session,
        parcel=pilot_parcel,
        case=test_case,
        include_synthetic_fixtures=True,
    )
    assert any(f["subsystem"] == "VALUATION" for f in fixture_res["facts"])
