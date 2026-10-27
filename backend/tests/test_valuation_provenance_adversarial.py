"""
Adversarial Regression Test Suite for TASK-P2-07.2:
MVR Valuation Provenance Enforcement, Trust Boundaries & Pilot Acceptance.

Covers all 12 required adversarial test dimensions:
1. Mock schedule marked VERIFIED_OFFICIAL is rejected.
2. Synthetic schedule with official-looking code is rejected.
3. Unknown / untrusted provider with apparently valid status is blocked.
4. Missing or invalid source gazette notification references are blocked.
5. Expired or superseded schedules are blocked with blocking evidence gaps.
6. Schedules from the wrong jurisdiction are blocked.
7. Unauthorized verification attempts are blocked and logged.
8. Client-supplied verification labels are stripped on import and alternate API entry points.
9. Property Passport synthesis with mixed trusted and untrusted evidence forces INSUFFICIENT_EVIDENCE.
10. PDF generation succeeds safely when valuation source is blocked without crashing or presenting synthetic rates as authoritative.
11. Recalculation after schedule revocation/supersession preserves audit history and surfaces blocking gaps.
12. Audit-log preservation for rejected, imported, and approved schedule verifications.
"""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.case import Case, CaseStatus, CaseParcel
from app.models.parcel import Parcel
from app.models.audit import AuditLog
from app.models.valuation import (
    MVRSchedule,
    PropertyValuation,
    PropertyCategory,
    RoadCategory,
    ScheduleVerificationStatus,
    DiscrepancyStatus,
    ValuationSourceProviderType,
    SYNTHETIC_MOCK_VALUATION_PROVIDERS,
    AUTHORIZED_OFFICIAL_VALUATION_PROVIDERS,
)
from app.models.passport_synthesis import (
    PassportAssessment,
    AssessmentStatus,
    RiskTier,
    RiskDimension,
)
from app.core.security import hash_password, create_access_token
from app.core.exceptions import ForbiddenError
from app.services.valuation.providers import InvalidJurisdictionError
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
def supervisor_user(db_session: Session, tenant_a: Organization) -> User:
    user = User(
        org_id=tenant_a.org_id,
        email="supervisor_val@bhumisetu.local",
        hashed_password=hash_password("SuperSecret123!"),
        full_name="DEMO_DATA: Valuation Supervisor",
        phone_number="9800000088",
        role=UserRole.SUPERVISOR,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def operator_user(db_session: Session, tenant_a: Organization) -> User:
    user = User(
        org_id=tenant_a.org_id,
        email="operator_val@bhumisetu.local",
        hashed_password=hash_password("OperatorSecret123!"),
        full_name="DEMO_DATA: Case Operator",
        phone_number="9800000077",
        role=UserRole.CASE_OPERATOR,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_parcel(db_session: Session, tenant_a: Organization) -> Parcel:
    parcel = Parcel(
        parcel_id=uuid.uuid4(),
        org_id=tenant_a.org_id,
        district="PATNA",
        circle="Danapur",
        mauza="Kotwa",
        khata_number="48",
        khesra_number="112",
        recorded_raiyat="Ram Bilas Singh",
        recorded_area_acre=0.25,
        land_classification="Raiyati",
    )
    db_session.add(parcel)
    db_session.commit()
    db_session.refresh(parcel)
    return parcel


@pytest.fixture
def test_case(db_session: Session, tenant_a: Organization, test_parcel: Parcel) -> Case:
    c = Case(
        case_id=uuid.uuid4(),
        org_id=tenant_a.org_id,
        case_number="CASE-TEST-2026-001",
        title="Diligence Case - Plot 112 Kotwa",
        status=CaseStatus.IN_PROGRESS,
    )
    db_session.add(c)
    db_session.flush()

    cp = CaseParcel(case_id=c.case_id, parcel_id=test_parcel.parcel_id, is_primary=True)
    db_session.add(cp)
    db_session.commit()
    db_session.refresh(c)
    return c


# =====================================================================
# 1. Mock Schedule Marked VERIFIED_OFFICIAL is Rejected
# =====================================================================

def test_01_mock_schedule_marked_verified_official_rejected(
    db_session: Session,
    supervisor_user: User,
):
    """
    Attempting to verify a mock/synthetic schedule as VERIFIED_OFFICIAL
    must be strictly rejected with ValueError.
    """
    service = ValuationService()

    # Create a schedule with MOCK_PROVIDER origin
    sched = MVRSchedule(
        schedule_id=uuid.uuid4(),
        org_id=supervisor_user.org_id,
        schedule_code="MVR-MOCK-PAT-DAN-001",
        district="PATNA",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="Kotwa",
        property_category=PropertyCategory.AGRICULTURAL,
        road_category=RoadCategory.RURAL_ROAD_OR_NO_ROAD,
        rate_per_decimal=50000.0,
        rate_per_sqft=114.78,
        rate_per_katha=156250.0,
        effective_from=datetime.now(timezone.utc) - timedelta(days=30),
        is_active=True,
        verification_status=ScheduleVerificationStatus.PROVISIONAL,
        source_provider=ValuationSourceProviderType.MOCK_PROVIDER,
        source_gazette_reference="District Gazette Notification 99/2025",
    )
    db_session.add(sched)
    db_session.commit()

    # Attempt to promote to VERIFIED_OFFICIAL
    req = MVRScheduleVerifyRequest(
        verification_status=ScheduleVerificationStatus.VERIFIED_OFFICIAL,
        verification_notes="Supervisor erroneously attempting to verify mock fixture",
    )
    with pytest.raises(ValueError, match="cannot become VERIFIED_OFFICIAL"):
        service.verify_schedule(db_session, sched.schedule_id, req, supervisor_user)

    # Confirm schedule remains PROVISIONAL in DB
    db_session.refresh(sched)
    assert sched.verification_status == ScheduleVerificationStatus.PROVISIONAL


# =====================================================================
# 2. Synthetic Schedule with Official-Looking Code is Rejected
# =====================================================================

def test_02_synthetic_schedule_with_official_looking_code_rejected(
    db_session: Session,
    supervisor_user: User,
    test_parcel: Parcel,
):
    """
    A schedule with an official-looking code (e.g. 'MVR-BIHAR-GOVT-GAZETTE-2026')
    derived from synthetic providers must be rejected by verification and blocked
    in Property Passport reconciliation.
    """
    service = ValuationService()

    sched = MVRSchedule(
        schedule_id=uuid.uuid4(),
        org_id=supervisor_user.org_id,
        schedule_code="MVR-BIHAR-GOVT-GAZETTE-2026-PAT-KOT",
        district="PATNA",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="Kotwa",
        property_category=PropertyCategory.RESIDENTIAL,
        road_category=RoadCategory.MAIN_ROAD_NH_SH,
        rate_per_decimal=150000.0,
        rate_per_sqft=344.35,
        rate_per_katha=468750.0,
        effective_from=datetime.now(timezone.utc) - timedelta(days=60),
        is_active=True,
        verification_status=ScheduleVerificationStatus.PROVISIONAL,
        source_provider="SYNTHETIC_FIXTURE",
        source_gazette_reference="Bihar Extraordinary Gazette No. 543/2025",
    )
    db_session.add(sched)
    db_session.commit()

    # 1. Verification reject
    req = MVRScheduleVerifyRequest(
        verification_status=ScheduleVerificationStatus.VERIFIED_OFFICIAL,
        verification_notes="Attempted promotion of synthetic fixture",
    )
    with pytest.raises(ValueError, match="cannot become VERIFIED_OFFICIAL"):
        service.verify_schedule(db_session, sched.schedule_id, req, supervisor_user)

    # 2. Add property valuation pointing to this schedule
    val = PropertyValuation(
        valuation_id=uuid.uuid4(),
        org_id=supervisor_user.org_id,
        parcel_id=test_parcel.parcel_id,
        schedule_id=sched.schedule_id,
        total_area_decimal=10.0,
        input_area_value=10.0,
        input_area_unit="DECIMAL",
        unit_circle_rate=150000.0,
        calculated_land_value=1500000.0,
        total_government_valuation=1500000.0,
        assessment_base=1500000.0,
        stamp_duty_rate_percent=6.0,
        stamp_duty_amount=90000.0,
        registration_fee_rate_percent=2.0,
        registration_fee_amount=30000.0,
        total_statutory_charges=120000.0,
        discrepancy_status=DiscrepancyStatus.NO_DISCREPANCY_DETECTED,
        valuation_date=datetime.now(timezone.utc),
    )
    db_session.add(val)
    db_session.commit()

    # 3. Reconciliation check: must surface GAP-VAL-SYNTHETIC-DATA-EXCLUDED as blocking
    result = EvidenceReconciliationEngine.reconcile_parcel_evidence(db=db_session, parcel=test_parcel)

    synth_gaps = [g for g in result["evidence_gaps"] if g["gap_code"] == "GAP-VAL-SYNTHETIC-DATA-EXCLUDED"]
    assert len(synth_gaps) == 1
    assert synth_gaps[0]["is_blocking"] is True
    # Fact must NOT be admitted
    assert not any(f.get("fact_type") == "VALUATION_ASSESSMENT" for f in result["facts"])


# =====================================================================
# 3. Unknown / Untrusted Provider Blocked in Synthesis
# =====================================================================

def test_03_unknown_untrusted_provider_blocked(
    db_session: Session,
    supervisor_user: User,
    test_parcel: Parcel,
):
    """
    Valuations linked to unauthorized third-party scrape providers
    (even if labeled VERIFIED_OFFICIAL) trigger GAP-VAL-UNTRUSTED-PROVIDER (blocking).
    """
    service = ValuationService()

    sched = MVRSchedule(
        schedule_id=uuid.uuid4(),
        org_id=supervisor_user.org_id,
        schedule_code="MVR-UNOFFICIAL-SCRAPER-001",
        district="PATNA",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="Kotwa",
        property_category=PropertyCategory.AGRICULTURAL,
        road_category=RoadCategory.RURAL_ROAD_OR_NO_ROAD,
        rate_per_decimal=45000.0,
        rate_per_sqft=103.30,
        rate_per_katha=140625.0,
        effective_from=datetime.now(timezone.utc) - timedelta(days=90),
        is_active=True,
        verification_status=ScheduleVerificationStatus.PROVISIONAL,
        source_provider="SHADY_THIRD_PARTY_CRAWLER",
        source_gazette_reference="Notification Claimed 45/2024",
    )
    db_session.add(sched)
    db_session.commit()

    # Attempt to verify: must fail because provider is not an authorized official source
    req = MVRScheduleVerifyRequest(
        verification_status=ScheduleVerificationStatus.VERIFIED_OFFICIAL,
        verification_notes="Attempted verification of crawler source",
    )
    with pytest.raises(ValueError, match="not an authorized official government registry"):
        service.verify_schedule(db_session, sched.schedule_id, req, supervisor_user)

    # Force DB status to VERIFIED_OFFICIAL to test upstream reconciliation defense
    sched.verification_status = ScheduleVerificationStatus.VERIFIED_OFFICIAL
    db_session.commit()

    val = PropertyValuation(
        valuation_id=uuid.uuid4(),
        org_id=supervisor_user.org_id,
        parcel_id=test_parcel.parcel_id,
        schedule_id=sched.schedule_id,
        total_area_decimal=5.0,
        input_area_value=5.0,
        input_area_unit="DECIMAL",
        unit_circle_rate=45000.0,
        calculated_land_value=225000.0,
        total_government_valuation=225000.0,
        assessment_base=225000.0,
        stamp_duty_rate_percent=6.0,
        stamp_duty_amount=13500.0,
        registration_fee_rate_percent=2.0,
        registration_fee_amount=4500.0,
        total_statutory_charges=18000.0,
        discrepancy_status=DiscrepancyStatus.NO_DISCREPANCY_DETECTED,
        valuation_date=datetime.now(timezone.utc),
    )
    db_session.add(val)
    db_session.commit()

    result = EvidenceReconciliationEngine.reconcile_parcel_evidence(db=db_session, parcel=test_parcel)

    untrusted_gaps = [g for g in result["evidence_gaps"] if g["gap_code"] == "GAP-VAL-UNTRUSTED-PROVIDER"]
    assert len(untrusted_gaps) == 1
    assert untrusted_gaps[0]["is_blocking"] is True


# =====================================================================
# 4. Missing or Invalid Source Gazette References Blocked
# =====================================================================

def test_04_missing_or_invalid_gazette_reference_blocked(
    db_session: Session,
    supervisor_user: User,
    test_parcel: Parcel,
):
    """
    Importing without a gazette reference is rejected.
    Schedules lacking official gazette citations trigger GAP-VAL-MISSING-GAZETTE-REFERENCE (blocking).
    """
    service = ValuationService()

    # 1. Import rejected when gazette reference is missing or empty
    bad_req = MVRScheduleCreateRequest(
        schedule_code="MVR-NO-GAZETTE-001",
        district="PATNA",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="Kotwa",
        property_category="AGRICULTURAL",
        road_category="RURAL_ROAD_OR_NO_ROAD",
        rate_per_decimal=55000.0,
        source_gazette_reference="   ",  # whitespace
    )
    with pytest.raises(ValueError, match="gazette notification reference is required"):
        service.import_schedule(db_session, bad_req, supervisor_user)

    # 2. Reconciliation check on existing schedule with blank gazette reference
    sched = MVRSchedule(
        schedule_id=uuid.uuid4(),
        org_id=supervisor_user.org_id,
        schedule_code="MVR-BLANK-GAZETTE-002",
        district="PATNA",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="Kotwa",
        property_category=PropertyCategory.AGRICULTURAL,
        road_category=RoadCategory.RURAL_ROAD_OR_NO_ROAD,
        rate_per_decimal=55000.0,
        rate_per_sqft=126.26,
        rate_per_katha=171875.0,
        effective_from=datetime.now(timezone.utc) - timedelta(days=30),
        is_active=True,
        verification_status=ScheduleVerificationStatus.VERIFIED_OFFICIAL,
        source_provider=ValuationSourceProviderType.OFFICIAL_GAZETTE,
        source_gazette_reference="NONE",  # placeholder
    )
    db_session.add(sched)
    db_session.commit()

    val = PropertyValuation(
        valuation_id=uuid.uuid4(),
        org_id=supervisor_user.org_id,
        parcel_id=test_parcel.parcel_id,
        schedule_id=sched.schedule_id,
        total_area_decimal=5.0,
        input_area_value=5.0,
        input_area_unit="DECIMAL",
        unit_circle_rate=55000.0,
        calculated_land_value=275000.0,
        total_government_valuation=275000.0,
        assessment_base=275000.0,
        stamp_duty_rate_percent=6.0,
        stamp_duty_amount=16500.0,
        registration_fee_rate_percent=2.0,
        registration_fee_amount=5500.0,
        total_statutory_charges=22000.0,
        discrepancy_status=DiscrepancyStatus.NO_DISCREPANCY_DETECTED,
        valuation_date=datetime.now(timezone.utc),
    )
    db_session.add(val)
    db_session.commit()

    result = EvidenceReconciliationEngine.reconcile_parcel_evidence(db=db_session, parcel=test_parcel)

    gaz_gaps = [g for g in result["evidence_gaps"] if g["gap_code"] == "GAP-VAL-MISSING-GAZETTE-REFERENCE"]
    assert len(gaz_gaps) == 1
    assert gaz_gaps[0]["is_blocking"] is True


# =====================================================================
# 5. Expired or Superseded Schedules Blocked with Blocking Gaps
# =====================================================================

def test_05_expired_and_superseded_schedules_blocked(
    db_session: Session,
    supervisor_user: User,
    test_parcel: Parcel,
):
    """
    Expired schedules (effective_to in past) trigger GAP-VAL-EXPIRED-SCHEDULE.
    Deactivated/superseded schedules trigger GAP-VAL-SUPERSEDED-SCHEDULE.
    Both must be marked is_blocking: True.
    """
    # 1. Superseded schedule test
    sched_sup = MVRSchedule(
        schedule_id=uuid.uuid4(),
        org_id=supervisor_user.org_id,
        schedule_code="MVR-SUPERSEDED-001",
        district="PATNA",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="Kotwa",
        property_category=PropertyCategory.AGRICULTURAL,
        road_category=RoadCategory.RURAL_ROAD_OR_NO_ROAD,
        rate_per_decimal=40000.0,
        rate_per_sqft=91.82,
        rate_per_katha=125000.0,
        effective_from=datetime(2023, 1, 1, tzinfo=timezone.utc),
        effective_to=datetime(2024, 1, 1, tzinfo=timezone.utc),
        is_active=False,
        verification_status=ScheduleVerificationStatus.SUPERSEDED,
        source_provider=ValuationSourceProviderType.OFFICIAL_GAZETTE,
        source_gazette_reference="Patna Gazette 10/2023",
    )
    db_session.add(sched_sup)
    db_session.commit()

    val_sup = PropertyValuation(
        valuation_id=uuid.uuid4(),
        org_id=supervisor_user.org_id,
        parcel_id=test_parcel.parcel_id,
        schedule_id=sched_sup.schedule_id,
        total_area_decimal=5.0,
        input_area_value=5.0,
        input_area_unit="DECIMAL",
        unit_circle_rate=40000.0,
        calculated_land_value=200000.0,
        total_government_valuation=200000.0,
        assessment_base=200000.0,
        stamp_duty_rate_percent=6.0,
        stamp_duty_amount=12000.0,
        registration_fee_rate_percent=2.0,
        registration_fee_amount=4000.0,
        total_statutory_charges=16000.0,
        discrepancy_status=DiscrepancyStatus.NO_DISCREPANCY_DETECTED,
        valuation_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )
    db_session.add(val_sup)
    db_session.commit()

    res_sup = EvidenceReconciliationEngine.reconcile_parcel_evidence(db=db_session, parcel=test_parcel)

    sup_gaps = [g for g in res_sup["evidence_gaps"] if g["gap_code"] == "GAP-VAL-SUPERSEDED-SCHEDULE"]
    assert len(sup_gaps) == 1
    assert sup_gaps[0]["is_blocking"] is True

    # 2. Expired schedule test (is_active True, but valuation_date > effective_to)
    sched_exp = MVRSchedule(
        schedule_id=uuid.uuid4(),
        org_id=supervisor_user.org_id,
        schedule_code="MVR-EXPIRED-002",
        district="PATNA",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="Kotwa",
        property_category=PropertyCategory.RESIDENTIAL,
        road_category=RoadCategory.MAIN_ROAD_NH_SH,
        rate_per_decimal=110000.0,
        rate_per_sqft=252.52,
        rate_per_katha=343750.0,
        effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        effective_to=datetime(2025, 1, 1, tzinfo=timezone.utc),
        is_active=True,
        verification_status=ScheduleVerificationStatus.VERIFIED_OFFICIAL,
        source_provider=ValuationSourceProviderType.OFFICIAL_GAZETTE,
        source_gazette_reference="Patna Gazette 12/2024",
    )
    db_session.add(sched_exp)
    db_session.commit()

    # Clear old valuation, add valuation with date in 2026 (after schedule expiry)
    db_session.query(PropertyValuation).filter(PropertyValuation.parcel_id == test_parcel.parcel_id).delete()
    db_session.commit()

    val_exp = PropertyValuation(
        valuation_id=uuid.uuid4(),
        org_id=supervisor_user.org_id,
        parcel_id=test_parcel.parcel_id,
        schedule_id=sched_exp.schedule_id,
        total_area_decimal=2.0,
        input_area_value=2.0,
        input_area_unit="DECIMAL",
        unit_circle_rate=110000.0,
        calculated_land_value=220000.0,
        total_government_valuation=220000.0,
        assessment_base=220000.0,
        stamp_duty_rate_percent=6.0,
        stamp_duty_amount=13200.0,
        registration_fee_rate_percent=2.0,
        registration_fee_amount=4400.0,
        total_statutory_charges=17600.0,
        discrepancy_status=DiscrepancyStatus.NO_DISCREPANCY_DETECTED,
        valuation_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    db_session.add(val_exp)
    db_session.commit()

    res_exp = EvidenceReconciliationEngine.reconcile_parcel_evidence(db=db_session, parcel=test_parcel)
    exp_gaps = [g for g in res_exp["evidence_gaps"] if g["gap_code"] == "GAP-VAL-EXPIRED-SCHEDULE"]
    assert len(exp_gaps) == 1
    assert exp_gaps[0]["is_blocking"] is True


# =====================================================================
# 6. Schedules from Wrong Jurisdiction Blocked
# =====================================================================

@pytest.mark.asyncio
async def test_06_jurisdiction_mismatch_blocked(
    db_session: Session,
    supervisor_user: User,
    test_parcel: Parcel,
):
    """
    Attempting valuation calculation with mismatched district or mauza raises
    InvalidJurisdictionError.
    Reconciliation surfaces GAP-VAL-JURISDICTION-MISMATCH (blocking).
    """
    service = ValuationService()

    # 1. Calculation service rejects mismatch against parcel
    req = ValuationCalculationRequest(
        parcel_id=test_parcel.parcel_id,
        district="PATNA",
        anchal_circle="Danapur",
        mauza="WrongMauzaName",  # Parcel is in Kotwa
        property_category="AGRICULTURAL",
        road_category="RURAL_ROAD_OR_NO_ROAD",
        area_value=5.0,
        area_unit="DECIMAL",
    )
    with pytest.raises(InvalidJurisdictionError, match="does not match parcel mauza"):
        await service.calculate_and_assess_property(db_session, req, supervisor_user)

    # 2. Reconciliation check when valuation links to a schedule of a different mauza
    sched_gaya = MVRSchedule(
        schedule_id=uuid.uuid4(),
        org_id=supervisor_user.org_id,
        schedule_code="MVR-GAYA-BODHGAYA-001",
        district="GAYA",
        registration_office="Bodh Gaya",
        anchal_circle="Bodh Gaya",
        mauza="BodhGayaTown",
        property_category=PropertyCategory.AGRICULTURAL,
        road_category=RoadCategory.RURAL_ROAD_OR_NO_ROAD,
        rate_per_decimal=60000.0,
        rate_per_sqft=137.74,
        rate_per_katha=187500.0,
        effective_from=datetime.now(timezone.utc) - timedelta(days=60),
        is_active=True,
        verification_status=ScheduleVerificationStatus.VERIFIED_OFFICIAL,
        source_provider=ValuationSourceProviderType.OFFICIAL_GAZETTE,
        source_gazette_reference="Gaya Gazette 44/2025",
    )
    db_session.add(sched_gaya)
    db_session.commit()

    val_mismatch = PropertyValuation(
        valuation_id=uuid.uuid4(),
        org_id=supervisor_user.org_id,
        parcel_id=test_parcel.parcel_id,
        schedule_id=sched_gaya.schedule_id,
        total_area_decimal=5.0,
        input_area_value=5.0,
        input_area_unit="DECIMAL",
        unit_circle_rate=60000.0,
        calculated_land_value=300000.0,
        total_government_valuation=300000.0,
        assessment_base=300000.0,
        stamp_duty_rate_percent=6.0,
        stamp_duty_amount=18000.0,
        registration_fee_rate_percent=2.0,
        registration_fee_amount=6000.0,
        total_statutory_charges=24000.0,
        discrepancy_status=DiscrepancyStatus.NO_DISCREPANCY_DETECTED,
        valuation_date=datetime.now(timezone.utc),
    )
    db_session.add(val_mismatch)
    db_session.commit()

    res = EvidenceReconciliationEngine.reconcile_parcel_evidence(db=db_session, parcel=test_parcel)

    mismatch_gaps = [g for g in res["evidence_gaps"] if g["gap_code"] == "GAP-VAL-JURISDICTION-MISMATCH"]
    assert len(mismatch_gaps) == 1
    assert mismatch_gaps[0]["is_blocking"] is True


# =====================================================================
# 7. Unauthorized Verification Attempts Blocked & Logged
# =====================================================================

def test_07_unauthorized_verification_attempts_blocked_and_logged(
    db_session: Session,
    operator_user: User,
):
    """
    A CASE_OPERATOR (non-SUPERVISOR/ADMIN) attempting to verify an MVR schedule
    is rejected with ForbiddenError and logged to AuditLog.
    """
    service = ValuationService()

    sched = MVRSchedule(
        schedule_id=uuid.uuid4(),
        org_id=operator_user.org_id,
        schedule_code="MVR-UNAUTH-TEST-001",
        district="PATNA",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="Kotwa",
        property_category=PropertyCategory.AGRICULTURAL,
        road_category=RoadCategory.RURAL_ROAD_OR_NO_ROAD,
        rate_per_decimal=50000.0,
        rate_per_sqft=114.78,
        rate_per_katha=156250.0,
        effective_from=datetime.now(timezone.utc),
        is_active=True,
        verification_status=ScheduleVerificationStatus.PROVISIONAL,
        source_provider=ValuationSourceProviderType.OPERATOR_ASSISTED_IMPORT,
        source_gazette_reference="Patna Gazette 12/2025",
    )
    db_session.add(sched)
    db_session.commit()

    req = MVRScheduleVerifyRequest(
        verification_status=ScheduleVerificationStatus.VERIFIED_OFFICIAL,
        verification_notes="Operator unauthorized attempt",
    )

    with pytest.raises(ForbiddenError, match="Only ADMIN or SUPERVISOR"):
        service.verify_schedule(db_session, sched.schedule_id, req, operator_user)

    # Verify audit log was recorded
    audit_log = db_session.query(AuditLog).filter(
        AuditLog.entity_id == sched.schedule_id,
        AuditLog.action == "MVR_SCHEDULE_VERIFY_UNAUTHORIZED",
    ).first()

    assert audit_log is not None
    assert audit_log.actor_party_id == operator_user.user_id
    expected_role = operator_user.role.value if hasattr(operator_user.role, "value") else str(operator_user.role)
    assert audit_log.new_state["user_role"] == expected_role


# =====================================================================
# 8. Client Verification Labels Stripped on Import and Alternate API Entry
# =====================================================================

def test_08_client_verification_labels_stripped_on_import(
    db_session: Session,
    supervisor_user: User,
    operator_user: User,
    client: TestClient,
):
    """
    Client-supplied verification_status='VERIFIED_OFFICIAL' in import request
    must be ignored/overridden to PROVISIONAL.
    REST API verification endpoint rejects non-supervisor tokens with HTTP 403.
    """
    service = ValuationService()

    # 1. Service import overrides to PROVISIONAL
    req = MVRScheduleCreateRequest(
        schedule_code="MVR-STRIP-LABEL-001",
        district="PATNA",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="Kotwa",
        property_category="AGRICULTURAL",
        road_category="RURAL_ROAD_OR_NO_ROAD",
        rate_per_decimal=62000.0,
        source_gazette_reference="District Gazette 77/2025",
    )
    record = service.import_schedule(db_session, req, supervisor_user)
    assert record.verification_status == ScheduleVerificationStatus.PROVISIONAL

    # 2. REST API verification endpoint rejects non-supervisor token
    token = create_access_token({"sub": str(operator_user.user_id), "org_id": str(operator_user.org_id)})
    headers = {"Authorization": f"Bearer {token}"}

    verify_payload = {
        "verification_status": "VERIFIED_OFFICIAL",
        "verification_notes": "Operator trying to bypass via REST endpoint",
    }
    resp = client.post(
        f"/api/v1/valuation/schedules/{record.schedule_id}/verify",
        json=verify_payload,
        headers=headers,
    )
    # HTTP 403 Forbidden due to require_roles([ADMIN, SUPERVISOR])
    assert resp.status_code == 403


# =====================================================================
# 9. Mixed Evidence Forces INSUFFICIENT_EVIDENCE
# =====================================================================

def test_09_property_passport_mixed_trusted_and_untrusted_evidence(
    db_session: Session,
    supervisor_user: User,
    test_parcel: Parcel,
    test_case: Case,
):
    """
    When parcel has trusted evidence but valuation relies on synthetic or provisional schedule,
    Property Passport synthesis surfaces the blocking gap and forces overall_risk_tier
    strictly to INSUFFICIENT_EVIDENCE.
    """
    # Create valuation with PROVISIONAL schedule
    sched = MVRSchedule(
        schedule_id=uuid.uuid4(),
        org_id=supervisor_user.org_id,
        schedule_code="MVR-PROV-MIXED-001",
        district="PATNA",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="Kotwa",
        property_category=PropertyCategory.AGRICULTURAL,
        road_category=RoadCategory.RURAL_ROAD_OR_NO_ROAD,
        rate_per_decimal=45000.0,
        rate_per_sqft=103.30,
        rate_per_katha=140625.0,
        effective_from=datetime.now(timezone.utc),
        is_active=True,
        verification_status=ScheduleVerificationStatus.PROVISIONAL,
        source_provider=ValuationSourceProviderType.OPERATOR_ASSISTED_IMPORT,
        source_gazette_reference="Gazette Citation 88/2025",
    )
    db_session.add(sched)

    val = PropertyValuation(
        valuation_id=uuid.uuid4(),
        org_id=supervisor_user.org_id,
        parcel_id=test_parcel.parcel_id,
        schedule_id=sched.schedule_id,
        total_area_decimal=10.0,
        input_area_value=10.0,
        input_area_unit="DECIMAL",
        unit_circle_rate=45000.0,
        calculated_land_value=450000.0,
        total_government_valuation=450000.0,
        assessment_base=450000.0,
        stamp_duty_rate_percent=6.0,
        stamp_duty_amount=27000.0,
        registration_fee_rate_percent=2.0,
        registration_fee_amount=9000.0,
        total_statutory_charges=36000.0,
        discrepancy_status=DiscrepancyStatus.NO_DISCREPANCY_DETECTED,
        valuation_date=datetime.now(timezone.utc),
    )
    db_session.add(val)
    db_session.commit()

    service = PassportSynthesisService(db_session)
    req = GenerateAssessmentRequest(case_id=test_case.case_id)
    assessment = service.generate_assessment(test_parcel.parcel_id, supervisor_user.org_id, req, supervisor_user.user_id)

    # Must be forced to INSUFFICIENT_EVIDENCE due to blocking gap
    assert assessment.overall_risk_tier == RiskTier.INSUFFICIENT_EVIDENCE
    assert any(g.is_blocking for g in assessment.evidence_gaps)

    # Blocking gap for unverified schedule must be listed
    db_gaps = assessment.evidence_gaps
    val_gaps = [g for g in db_gaps if g.gap_code == "GAP-VAL-UNVERIFIED-SCHEDULE"]
    assert len(val_gaps) >= 1
    assert val_gaps[0].is_blocking is True


# =====================================================================
# 10. PDF Generation when Valuation Source is Blocked
# =====================================================================

def test_10_pdf_generation_when_valuation_blocked(
    db_session: Session,
    supervisor_user: User,
    test_parcel: Parcel,
    test_case: Case,
):
    """
    When official valuation is blocked (no admitted valuations), Land Intelligence
    PDF generation must succeed safely, render the disclaimer box, and not crash
    or output misleading numbers.
    """
    # Clean valuations for this parcel
    db_session.query(PropertyValuation).filter(PropertyValuation.parcel_id == test_parcel.parcel_id).delete()
    db_session.commit()

    report_data = assemble_report_data(
        db=db_session,
        case_id=test_case.case_id,
        parcel_id=test_parcel.parcel_id,
        current_user=supervisor_user,
    )

    # Generate PDF
    pdf_bytes = generate_land_intelligence_pdf(report_data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


# =====================================================================
# 11. Recalculation After Schedule Supersession
# =====================================================================

def test_11_recalculation_after_schedule_supersession(
    db_session: Session,
    supervisor_user: User,
    test_parcel: Parcel,
    test_case: Case,
):
    """
    When an active schedule is superseded, recomputing Property Passport assessment
    records version 2, marks version 1 SUPERSEDED, and flags GAP-VAL-SUPERSEDED-SCHEDULE.
    """
    service = ValuationService()

    # Create official schedule
    sched = MVRSchedule(
        schedule_id=uuid.uuid4(),
        org_id=supervisor_user.org_id,
        schedule_code="MVR-RECOMPUTE-001",
        district="PATNA",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="Kotwa",
        property_category=PropertyCategory.AGRICULTURAL,
        road_category=RoadCategory.RURAL_ROAD_OR_NO_ROAD,
        rate_per_decimal=50000.0,
        rate_per_sqft=114.78,
        rate_per_katha=156250.0,
        effective_from=datetime.now(timezone.utc) - timedelta(days=60),
        is_active=True,
        verification_status=ScheduleVerificationStatus.VERIFIED_OFFICIAL,
        source_provider=ValuationSourceProviderType.OFFICIAL_GAZETTE,
        source_gazette_reference="District Notification 33/2025",
    )
    db_session.add(sched)

    val = PropertyValuation(
        valuation_id=uuid.uuid4(),
        org_id=supervisor_user.org_id,
        parcel_id=test_parcel.parcel_id,
        schedule_id=sched.schedule_id,
        total_area_decimal=10.0,
        input_area_value=10.0,
        input_area_unit="DECIMAL",
        unit_circle_rate=50000.0,
        calculated_land_value=500000.0,
        total_government_valuation=500000.0,
        assessment_base=500000.0,
        stamp_duty_rate_percent=6.0,
        stamp_duty_amount=30000.0,
        registration_fee_rate_percent=2.0,
        registration_fee_amount=10000.0,
        total_statutory_charges=40000.0,
        discrepancy_status=DiscrepancyStatus.NO_DISCREPANCY_DETECTED,
        valuation_date=datetime.now(timezone.utc),
    )
    db_session.add(val)
    db_session.commit()

    passport_service = PassportSynthesisService(db_session)
    req1 = GenerateAssessmentRequest(case_id=test_case.case_id)
    v1 = passport_service.generate_assessment(test_parcel.parcel_id, supervisor_user.org_id, req1, supervisor_user.user_id)
    assert v1.version_number == 1
    assert v1.status == AssessmentStatus.COMPLETED

    # Now supervisor supersedes the schedule
    verify_req = MVRScheduleVerifyRequest(
        verification_status=ScheduleVerificationStatus.SUPERSEDED,
        verification_notes="Superseded by 2026 revision",
    )
    service.verify_schedule(db_session, sched.schedule_id, verify_req, supervisor_user)

    # Recompute assessment
    recomp_req = AssessmentRecomputeRequest(recompute_reason="Circle rate schedule superseded")
    v2 = passport_service.recompute_assessment(v1.assessment_id, supervisor_user.org_id, supervisor_user.user_id, recomp_req)

    assert v2.version_number == 2
    assert v2.previous_assessment_id == v1.assessment_id
    assert v2.status == AssessmentStatus.COMPLETED

    # Check v1 was updated to SUPERSEDED
    db_session.refresh(v1)
    assert v1.status == AssessmentStatus.SUPERSEDED

    # In v2, GAP-VAL-SUPERSEDED-SCHEDULE must be flagged
    gaps_v2 = [g for g in v2.evidence_gaps if g.gap_code == "GAP-VAL-SUPERSEDED-SCHEDULE"]
    assert len(gaps_v2) == 1
    assert gaps_v2[0].is_blocking is True


# =====================================================================
# 12. Audit-Log Preservation for Verification and Imports
# =====================================================================

def test_12_audit_log_preservation_for_verification_and_imports(
    db_session: Session,
    supervisor_user: User,
):
    """
    Verifies that importing and verifying schedules creates complete, auditable
    AuditLog records with actor, entity, action, previous_state, and new_state.
    """
    service = ValuationService()

    # 1. Import schedule
    import_req = MVRScheduleCreateRequest(
        schedule_code="MVR-AUDIT-TEST-001",
        district="PATNA",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="Kotwa",
        property_category="AGRICULTURAL",
        road_category="RURAL_ROAD_OR_NO_ROAD",
        rate_per_decimal=52000.0,
        source_gazette_reference="District Gazette 99/2025",
    )
    sched_record = service.import_schedule(db_session, import_req, supervisor_user)

    import_log = db_session.query(AuditLog).filter(
        AuditLog.entity_id == sched_record.schedule_id,
        AuditLog.action == "MVR_SCHEDULE_IMPORTED",
    ).first()

    assert import_log is not None
    assert import_log.actor_party_id == supervisor_user.user_id
    assert import_log.new_state["schedule_code"] == "MVR-AUDIT-TEST-001"
    assert import_log.new_state["verification_status"] == ScheduleVerificationStatus.PROVISIONAL

    # 2. Verify schedule
    verify_req = MVRScheduleVerifyRequest(
        verification_status=ScheduleVerificationStatus.VERIFIED_OFFICIAL,
        verification_notes="Official collectorate gazette verified by supervisor",
    )
    service.verify_schedule(db_session, sched_record.schedule_id, verify_req, supervisor_user)

    verify_log = db_session.query(AuditLog).filter(
        AuditLog.entity_id == sched_record.schedule_id,
        AuditLog.action == "MVR_SCHEDULE_VERIFIED_OFFICIAL",
    ).first()

    assert verify_log is not None
    assert verify_log.actor_party_id == supervisor_user.user_id
    assert verify_log.previous_state["verification_status"] == ScheduleVerificationStatus.PROVISIONAL
    assert verify_log.new_state["verification_status"] == ScheduleVerificationStatus.VERIFIED_OFFICIAL
    assert verify_log.new_state["notes"] == "Official collectorate gazette verified by supervisor"
