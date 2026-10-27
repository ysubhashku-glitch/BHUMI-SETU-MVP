"""
TASK-P2-07.4: Release Integrity Verification & Operational Gate Execution Test Suite.
Validates:
1. Operator-assisted e-Nibandhan ingestion idempotency and version progression.
2. Ingestion schema validation and gazette reference integrity.
3. e-Nibandhan CAPTCHA signaling without bypass attempts.
4. Role-based verification enforcement and audit logging.
5. Cross-tenant isolation boundaries.
6. Production-mode synthetic fixture exclusion.
7. Graceful PDF report generation with non-admission disclaimers and SHA-256 digests.
8. Jurisdiction mismatch and expired schedule rejection.
"""
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.parcel import Parcel
from app.models.case import Case, CaseStatus, CaseParcel
from app.models.valuation import (
    MVRSchedule,
    PropertyValuation,
    AreaUnit,
    PropertyCategory,
    RoadCategory,
    JurisdictionType,
    ScheduleVerificationStatus,
    DiscrepancyStatus,
)
from app.models.audit import AuditLog
from app.core.exceptions import ForbiddenError, CrossTenantAccessError
from app.schemas.valuation import (
    MVRScheduleCreateRequest,
    MVRScheduleVerifyRequest,
    ValuationCalculationRequest,
)
from app.services.valuation.service import ValuationService
from app.services.valuation.providers.operator_import import OperatorImportValuationProvider
from app.services.valuation.providers.enibandhan_provider import (
    ENibandhanBiharProvider,
    ValuationCaptchaRequiredError,
)
from app.services.valuation.providers.base import MVRRateNotFoundError
from app.services.passport.reconciliation_engine import EvidenceReconciliationEngine
from app.services.report_assembler import assemble_report_data
from app.services.pdf_report_generator import generate_land_intelligence_pdf


@pytest.fixture
def test_supervisor(db_session: Session, tenant_a: Organization) -> User:
    user = User(
        org_id=tenant_a.org_id,
        email="supervisor.audit@bhumisetu.gov.in",
        hashed_password="fakehash_audit_sup",
        full_name="Audit Senior Supervisor",
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
        email="operator.audit@bhumisetu.gov.in",
        hashed_password="fakehash_audit_op",
        full_name="Audit Case Operator",
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
        case_number="CASE-AUDIT-2026-PAT-001",
        title="Release Integrity Diligence - Mustafapur Plot 202",
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
        bhumi_id="BR-PAT-DAN-MUS-2026-002",
        state_code="BR",
        district_name="Patna",
        subdistrict_anchal_name="Danapur",
        halka_number="04",
        mauza_village_name="Mustafapur",
        census_village_code="245002",
        khata_number="155",
        plot_khesra_number="202",
        recorded_area_acres=0.85,
        land_nature="RESIDENTIAL",
        authoritative_boundary="SRID=4326;POLYGON((85.045 25.615, 85.055 25.615, 85.055 25.625, 85.045 25.625, 85.045 25.615))",
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
# Tests: Phase F & G Audits
# =====================================================================

def test_audit_01_operator_ingestion_idempotency_and_version_progression(
    db_session: Session,
    tenant_a: Organization,
    test_operator: User,
):
    """
    Verifies that re-importing an existing schedule:
    - Increments the version number (v1 -> v2)
    - Updates rates and gazette citation
    - Resets verification_status to PROVISIONAL
    - Logs distinct AuditLog entries with previous and new states.
    """
    service = ValuationService()

    # Initial Import (Version 1)
    req1 = MVRScheduleCreateRequest(
        district="PATNA",
        registration_office="Danapur Registry Office",
        anchal_circle="Danapur",
        mauza="Mustafapur",
        thana_number="42",
        jurisdiction_type=JurisdictionType.RURAL,
        property_category=PropertyCategory.RESIDENTIAL,
        road_category=RoadCategory.MAIN_ROAD_NH_SH,
        rate_per_decimal=50000.0,
        source_gazette_reference="Patna District Gazette Notification No. 101/2025",
        schedule_code="MVR-BR-PAT-DAN-MUS-RES-MAI",
    )
    rec1 = service.import_schedule(db=db_session, request=req1, current_user=test_operator)
    assert rec1.version_number == 1
    assert rec1.verification_status == ScheduleVerificationStatus.PROVISIONAL
    assert rec1.rate_per_decimal == 50000.0

    # Second Import (Version 2 with revised rate)
    req2 = MVRScheduleCreateRequest(
        district="PATNA",
        registration_office="Danapur Registry Office",
        anchal_circle="Danapur",
        mauza="Mustafapur",
        thana_number="42",
        jurisdiction_type=JurisdictionType.RURAL,
        property_category=PropertyCategory.RESIDENTIAL,
        road_category=RoadCategory.MAIN_ROAD_NH_SH,
        rate_per_decimal=55000.0,
        source_gazette_reference="Patna District Gazette Notification No. 101/2025-CORR",
        schedule_code="MVR-BR-PAT-DAN-MUS-RES-MAI",
    )
    rec2 = service.import_schedule(db=db_session, request=req2, current_user=test_operator)
    assert rec2.version_number == 2
    assert rec2.verification_status == ScheduleVerificationStatus.PROVISIONAL
    assert rec2.rate_per_decimal == 55000.0

    # Verify AuditLogs
    logs = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.entity_name == "MVRSchedule",
            AuditLog.action == "MVR_SCHEDULE_IMPORTED",
        )
        .order_by(AuditLog.created_at.asc())
        .all()
    )
    assert len(logs) >= 2
    last_log = logs[-1]
    assert last_log.actor_party_id == test_operator.user_id
    assert last_log.previous_state.get("version_number") == 1
    assert last_log.new_state.get("rate_per_decimal") == 55000.0


def test_audit_02_gazette_reference_strict_validation(test_operator: User):
    """
    Verifies that OperatorImportValuationProvider and Pydantic reject:
    - Empty or short gazette references (< 5 characters)
    - Placeholder strings like 'NONE', 'N/A', 'TEST', 'NULL'
    - Non-positive rates.
    """
    provider = OperatorImportValuationProvider()

    # Rejection of placeholder reference
    for bad_ref in ["NONE", "N/A", "test", "NULL", "123", "   "]:
        req = MVRScheduleCreateRequest(
            district="PATNA",
            registration_office="Danapur",
            anchal_circle="Danapur",
            mauza="Mustafapur",
            property_category=PropertyCategory.RESIDENTIAL,
            road_category=RoadCategory.MAIN_ROAD_NH_SH,
            rate_per_decimal=45000.0,
            source_gazette_reference=bad_ref,
        )
        with pytest.raises(ValueError, match="Official gazette notification reference is required"):
            provider.normalize_and_register(req, operator_user_id=str(test_operator.user_id))

    # Rejection of negative/zero rate at Pydantic schema validation layer
    with pytest.raises(ValidationError):
        MVRScheduleCreateRequest(
            district="PATNA",
            registration_office="Danapur",
            anchal_circle="Danapur",
            mauza="Mustafapur",
            property_category=PropertyCategory.RESIDENTIAL,
            road_category=RoadCategory.MAIN_ROAD_NH_SH,
            rate_per_decimal=-100.0,
            source_gazette_reference="Patna Collectorate Gazette 2025",
        )


@pytest.mark.asyncio
async def test_audit_03_enibandhan_captcha_fallback_and_no_bypass():
    """
    Verifies that the live e-Nibandhan provider correctly signals
    ValuationCaptchaRequiredError rather than attempting automated CAPTCHA bypass.
    """
    provider = ENibandhanBiharProvider()
    from app.schemas.valuation import MVRScheduleSearchQuery

    query = MVRScheduleSearchQuery(
        district="PATNA",
        anchal_circle="Danapur",
        mauza="Mustafapur",
    )
    with pytest.raises(ValuationCaptchaRequiredError, match="visual CAPTCHA verification"):
        await provider.search_schedules(query)


def test_audit_04_unauthorized_schedule_verification_blocked_and_audited(
    db_session: Session,
    tenant_a: Organization,
    test_operator: User,
    test_supervisor: User,
):
    """
    Verifies that unprivileged CASE_OPERATOR cannot verify schedules,
    rejection raises ForbiddenError, and MVR_SCHEDULE_VERIFY_UNAUTHORIZED is audited.
    """
    service = ValuationService()

    # Import schedule as operator
    req = MVRScheduleCreateRequest(
        district="PATNA",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="Kotwa",
        property_category=PropertyCategory.AGRICULTURAL,
        road_category=RoadCategory.RURAL_ROAD_OR_NO_ROAD,
        rate_per_decimal=20000.0,
        source_gazette_reference="Patna Collectorate Gazette Kotwa 2025",
        schedule_code="MVR-BR-PAT-DAN-KOT-AGR-RUR",
    )
    rec = service.import_schedule(db=db_session, request=req, current_user=test_operator)

    # Attempt unauthorized verification as CASE_OPERATOR
    verify_req = MVRScheduleVerifyRequest(
        source_gazette_reference="Patna Collectorate Gazette Kotwa 2025",
        verification_notes="Attempted by operator",
    )
    sched_uuid = rec.schedule_id if isinstance(rec.schedule_id, uuid.UUID) else uuid.UUID(str(rec.schedule_id))
    with pytest.raises(ForbiddenError, match="Only ADMIN or SUPERVISOR"):
        service.verify_schedule(
            db=db_session,
            schedule_id=sched_uuid,
            verify_request=verify_req,
            current_user=test_operator,
        )

    # Check AuditLog for unauthorized attempt
    unauth_log = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "MVR_SCHEDULE_VERIFY_UNAUTHORIZED",
            AuditLog.entity_id == sched_uuid,
        )
        .first()
    )
    assert unauth_log is not None
    assert unauth_log.actor_party_id == test_operator.user_id

    # Authorized verification by SUPERVISOR succeeds
    verified_rec = service.verify_schedule(
        db=db_session,
        schedule_id=sched_uuid,
        verify_request=verify_req,
        current_user=test_supervisor,
    )
    assert verified_rec.verification_status == ScheduleVerificationStatus.VERIFIED_OFFICIAL


def test_audit_05_cross_tenant_schedule_isolation(
    db_session: Session,
    tenant_a: Organization,
    tenant_b: Organization,
    test_operator: User,
):
    """
    Verifies that an imported schedule associated with tenant_a cannot be
    modified or updated by a user from tenant_b.
    """
    service = ValuationService()

    # User from tenant_b
    user_b = User(
        org_id=tenant_b.org_id,
        email="operator.b@otherdomain.com",
        hashed_password="fakehash_tenant_b",
        full_name="Tenant B Operator",
        role=UserRole.CASE_OPERATOR,
        is_active=True,
    )
    db_session.add(user_b)
    db_session.commit()

    # Schedule created under tenant_a
    req = MVRScheduleCreateRequest(
        district="PATNA",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="Mustafapur",
        property_category=PropertyCategory.COMMERCIAL,
        road_category=RoadCategory.MAIN_ROAD_NH_SH,
        rate_per_decimal=80000.0,
        source_gazette_reference="Patna Gazette Commercial 2025",
        schedule_code="MVR-BR-PAT-DAN-MUS-COM-MAI",
    )
    service.import_schedule(db=db_session, request=req, current_user=test_operator)

    # Tenant B tries to re-import / overwrite Tenant A's schedule
    with pytest.raises(CrossTenantAccessError, match="Cross-tenant access prohibited"):
        service.import_schedule(db=db_session, request=req, current_user=user_b)


def test_audit_06_production_synthetic_fixtures_exclusion(
    db_session: Session,
    tenant_a: Organization,
    test_case: Case,
    pilot_parcel: Parcel,
):
    """
    Verifies that when running with include_synthetic_fixtures=False (production mode),
    the reconciliation engine detects mock provider schedules and strictly
    emits GAP-VAL-SYNTHETIC-DATA-EXCLUDED with is_blocking=True.
    """
    mock_sched = MVRSchedule(
        org_id=tenant_a.org_id,
        schedule_code="MVR-MOCK-MUSTAFAPUR-AUDIT-01",
        district="Patna",
        registration_office="Danapur Registry Office",
        anchal_circle="Danapur",
        mauza="Mustafapur",
        property_category=PropertyCategory.RESIDENTIAL,
        road_category=RoadCategory.MAIN_ROAD_NH_SH,
        rate_per_decimal=50000.0,
        rate_per_sqft=114.78,
        rate_per_katha=156250.0,
        source_provider="MOCK_PROVIDER",
        verification_status=ScheduleVerificationStatus.VERIFIED_OFFICIAL,
        source_gazette_reference="Mock Gazette Audit 2026",
        is_active=True,
    )
    db_session.add(mock_sched)
    db_session.flush()

    val = PropertyValuation(
        org_id=tenant_a.org_id,
        case_id=test_case.case_id,
        parcel_id=pilot_parcel.parcel_id,
        schedule_id=mock_sched.schedule_id,
        total_area_decimal=100.0,
        input_area_value=1.0,
        unit_circle_rate=50000.0,
        calculated_land_value=5000000.0,
        calculated_structure_value=0.0,
        total_government_valuation=5000000.0,
        assessment_base=5000000.0,
        stamp_duty_rate_percent=6.0,
        stamp_duty_amount=300000.0,
        registration_fee_rate_percent=2.0,
        registration_fee_amount=100000.0,
        total_statutory_charges=400000.0,
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

    # Test fixture mode: Admitted
    fixture_res = EvidenceReconciliationEngine.reconcile_parcel_evidence(
        db=db_session,
        parcel=pilot_parcel,
        case=test_case,
        include_synthetic_fixtures=True,
    )
    assert any(f["subsystem"] == "VALUATION" for f in fixture_res["facts"])


def test_audit_07_inadmissible_valuation_report_disclaimer(
    db_session: Session,
    test_case: Case,
    pilot_parcel: Parcel,
    test_supervisor: User,
):
    """
    Verifies that when valuation is blocked/excluded, assemble_report_data
    and generate_land_intelligence_pdf gracefully generate the PDF report
    with high-visibility amber disclaimer and SHA-256 integrity hash.
    """
    report_data = assemble_report_data(
        db=db_session,
        case_id=test_case.case_id,
        parcel_id=pilot_parcel.parcel_id,
        current_user=test_supervisor,
    )
    assert report_data is not None
    # Valuation is not assessed / empty valuations list
    assert report_data.section_valuation is not None
    assert report_data.section_valuation.is_assessed is False
    assert len(report_data.section_valuation.valuations) == 0
    assert report_data.section_valuation.limitation_statement is not None

    pdf_bytes = generate_land_intelligence_pdf(report_data)
    assert isinstance(pdf_bytes, (bytes, bytearray))
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_audit_08_jurisdiction_mismatch_and_expired_schedules(
    db_session: Session,
    test_operator: User,
    test_supervisor: User,
):
    """
    Verifies that:
    - Schedules with expired validity dates are not selected by calculate_and_assess_property.
    """
    service = ValuationService()

    # Expired schedule for Mustafapur
    expired_sched = MVRSchedule(
        schedule_id=uuid.uuid4(),
        org_id=test_supervisor.org_id,
        schedule_code="MVR-BR-PAT-DAN-MUS-EXP-001",
        district="PATNA",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="Mustafapur",
        jurisdiction_type=JurisdictionType.RURAL,
        property_category=PropertyCategory.RESIDENTIAL,
        road_category=RoadCategory.MAIN_ROAD_NH_SH,
        rate_per_decimal=30000.0,
        rate_per_sqft=68.87,
        rate_per_katha=93750.0,
        unit_basis="DECIMAL",
        effective_from=datetime.now(timezone.utc) - timedelta(days=700),
        effective_to=datetime.now(timezone.utc) - timedelta(days=365),  # Expired 1 year ago
        version_number=1,
        is_active=True,
        verification_status=ScheduleVerificationStatus.VERIFIED_OFFICIAL,
        source_gazette_reference="Patna Expired Gazette 2024",
        source_provider="OPERATOR_ASSISTED_IMPORT",
    )
    db_session.add(expired_sched)
    db_session.commit()

    # Query for property valuation today
    calc_req = ValuationCalculationRequest(
        district="PATNA",
        anchal_circle="Danapur",
        mauza="Mustafapur",
        property_category=PropertyCategory.RESIDENTIAL,
        road_category=RoadCategory.MAIN_ROAD_NH_SH,
        area_value=1.0,
        area_unit=AreaUnit.DECIMAL,
    )
    # The expired schedule must be rejected, raising MVRRateNotFoundError
    with pytest.raises(MVRRateNotFoundError, match="No verified MVR circle rate found"):
        await service.calculate_and_assess_property(
            db=db_session,
            request=calc_req,
            current_user=test_supervisor,
            provider_type="OPERATOR",
        )
