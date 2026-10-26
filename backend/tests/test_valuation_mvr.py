"""
Unit and Integration Test Suite for Bihar MVR Circle Rate and Stamp Duty Subsystem.

Covers all required verification dimensions:
1. Official schedule schema validation
2. Missing and contradictory valuation records
3. Jurisdiction and property-category matching
4. Effective-date selection and historical versions
5. Area-unit conversions (Decimal, Katha, Acre, Bigha, SqFt, SqM)
6. Numeric precision, rounding, and arithmetic integrity
7. Buyer categories & statutory concessions (Male 6%, Female 5.6%, Joint 5.8%)
8. Municipal surcharge in urban corporation areas (2%)
9. Registration fee calculation (2%)
10. Section 47-A assessment base rule (max(Consideration, Govt Valuation))
11. Undervaluation discrepancy detection (POTENTIAL_UNDERVALUE)
12. Overvaluation detection (POTENTIAL_OVERVALUATION)
13. No discrepancy status (NO_DISCREPANCY_DETECTED)
14. Insufficient data behavior
15. Duplicate imports and idempotency
16. Multi-tenant isolation and authorization
17. SSRF and outbound-host restrictions
18. Land Intelligence Report integration and statutory disclaimers
19. REST API endpoints integration
"""

import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.case import Case, CaseStatus, CaseParcel
from app.models.parcel import Parcel
from app.models.valuation import (
    MVRSchedule,
    PropertyValuation,
    PropertyCategory,
    RoadCategory,
    JurisdictionType,
    AreaUnit,
    ScheduleVerificationStatus,
    DiscrepancyStatus,
    BuyerGenderCategory,
)
from app.core.security import hash_password, create_access_token
from app.core.exceptions import CrossTenantAccessError
from app.schemas.valuation import (
    MVRScheduleRecord,
    MVRScheduleCreateRequest,
    MVRScheduleSearchQuery,
    ValuationCalculationRequest,
    STATUTORY_VALUATION_DISCLAIMER,
)
from app.services.valuation.unit_converter import (
    convert_to_decimal,
    convert_area,
    normalize_area_unit_name,
)
from app.services.valuation.providers import (
    MockValuationProvider,
    ENibandhanBiharProvider,
    OperatorImportValuationProvider,
    ALLOWED_VALUATION_DOMAINS,
    validate_valuation_url,
    ValuationSSRFBlockedError,
    MVRRateNotFoundError,
    ValuationSourceUnavailableError,
    ValuationRateLimitError,
)
from app.services.valuation.valuation_engine import ValuationEngine
from app.services.valuation.stamp_duty_engine import StampDutyEngine
from app.services.valuation.discrepancy_analyzer import ValuationDiscrepancyAnalyzer
from app.services.valuation.service import ValuationService
from app.services.report_assembler import assemble_report_data
from app.services.pdf_report_generator import generate_land_intelligence_pdf


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def valuation_operator(db_session: Session, tenant_a: Organization) -> User:
    user = User(
        org_id=tenant_a.org_id,
        email="val_operator_a@bhumisetu.local",
        hashed_password=hash_password("Password123!"),
        full_name="DEMO_DATA: Valuation Officer",
        phone_number="9800000095",
        role=UserRole.SUPERVISOR,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def danapur_parcel(db_session: Session, tenant_a: Organization) -> Parcel:
    parcel = Parcel(
        parcel_id=uuid.uuid4(),
        org_id=tenant_a.org_id,
        district="PATNA",
        circle="Danapur",
        mauza="Kotwa",
        khata_number="48",
        khesra_number="112",
        recorded_raiyat="Shambhu Nath Singh",
        recorded_area_acre=0.10,  # 10 Decimals
        land_classification="Raiyati Agricultural",
    )
    db_session.add(parcel)
    db_session.commit()
    db_session.refresh(parcel)
    return parcel


@pytest.fixture
def danapur_case(db_session: Session, tenant_a: Organization, danapur_parcel: Parcel, valuation_operator: User) -> Case:
    case = Case(
        case_id=uuid.uuid4(),
        org_id=tenant_a.org_id,
        case_number="CASE-DANAPUR-2026-002",
        status=CaseStatus.DRAFT,
        primary_client_party_id=uuid.uuid4(),
        assigned_advocate_id=valuation_operator.user_id,
    )
    db_session.add(case)
    db_session.flush()

    cp = CaseParcel(case_id=case.case_id, parcel_id=danapur_parcel.parcel_id, is_primary=True)
    db_session.add(cp)
    db_session.commit()
    db_session.refresh(case)
    return case


# =====================================================================
# 1. Official Schedule Schema Validation
# =====================================================================

def test_01_mvr_schedule_schema_validation():
    """Validates MVR schedule record schema validation and defaults."""
    record = MVRScheduleRecord(
        schedule_id="SCHED-001",
        schedule_code="MVR-BR-PAT-DAN-KOT-AGR-NH",
        district="PATNA",
        registration_office="Danapur Sub-Registry",
        anchal_circle="Danapur",
        mauza="Kotwa",
        thana_number="18",
        jurisdiction_type="RURAL",
        property_category="AGRICULTURAL",
        land_classification="DHANHAR_I",
        road_category="MAIN_ROAD_NH_SH",
        rate_per_decimal=85000.0,
        rate_per_sqft=195.13,
        rate_per_katha=265625.0,
        unit_basis="DECIMAL",
        effective_from=datetime(2025, 4, 1, 0, 0, tzinfo=timezone.utc),
        is_active=True,
        verification_status="VERIFIED_OFFICIAL",
    )
    assert record.district == "PATNA"
    assert record.rate_per_decimal == 85000.0
    assert record.unit_basis == "DECIMAL"


# =====================================================================
# 2. Missing and Contradictory Valuation Records
# =====================================================================

@pytest.mark.asyncio
async def test_02_missing_schedule_raises_mvr_rate_not_found(
    db_session: Session,
    valuation_operator: User,
):
    """Ensures query for unknown mauza / circle raises MVRRateNotFoundError."""
    service = ValuationService()
    req = ValuationCalculationRequest(
        district="PATNA",
        anchal_circle="NonExistentAnchal",
        mauza="UnknownVillage",
        property_category="AGRICULTURAL",
        road_category="RURAL_ROAD_OR_NO_ROAD",
        area_value=10.0,
        area_unit="DECIMAL",
    )
    with pytest.raises(MVRRateNotFoundError):
        await service.calculate_and_assess_property(db_session, req, valuation_operator)


# =====================================================================
# 3. Jurisdiction and Property-Category Matching
# =====================================================================

@pytest.mark.asyncio
async def test_03_property_category_and_road_matching(
    db_session: Session,
    valuation_operator: User,
):
    """Correctly distinguishes Agricultural vs Commercial rates and NH vs Rural road rates."""
    service = ValuationService()

    # Request 1: Agricultural on Rural Road (Rate = 45,000/dec)
    req_rural = ValuationCalculationRequest(
        district="PATNA",
        anchal_circle="Danapur",
        mauza="Kotwa",
        property_category="AGRICULTURAL",
        road_category="RURAL_ROAD_OR_NO_ROAD",
        area_value=1.0,
        area_unit="DECIMAL",
    )
    resp_rural = await service.calculate_and_assess_property(db_session, req_rural, valuation_operator)
    assert resp_rural.applied_unit_rate == 45000.0
    assert resp_rural.calculated_land_value == 45000.0

    # Request 2: Agricultural on Main NH/SH (Rate = 85,000/dec)
    req_nh = ValuationCalculationRequest(
        district="PATNA",
        anchal_circle="Danapur",
        mauza="Kotwa",
        property_category="AGRICULTURAL",
        road_category="MAIN_ROAD_NH_SH",
        area_value=1.0,
        area_unit="DECIMAL",
    )
    resp_nh = await service.calculate_and_assess_property(db_session, req_nh, valuation_operator)
    assert resp_nh.applied_unit_rate == 85000.0
    assert resp_nh.calculated_land_value == 85000.0

    # Request 3: Commercial on Main NH/SH (Rate = 250,000/dec)
    req_com = ValuationCalculationRequest(
        district="PATNA",
        anchal_circle="Danapur",
        mauza="Kotwa",
        property_category="COMMERCIAL",
        road_category="MAIN_ROAD_NH_SH",
        area_value=1.0,
        area_unit="DECIMAL",
    )
    resp_com = await service.calculate_and_assess_property(db_session, req_com, valuation_operator)
    assert resp_com.applied_unit_rate == 250000.0
    assert resp_com.calculated_land_value == 250000.0


# =====================================================================
# 4. Effective-Date Selection and Historical Versions
# =====================================================================

@pytest.mark.asyncio
async def test_04_effective_date_window():
    """Ensures search filters by effective_from and effective_to window."""
    provider = MockValuationProvider()
    query_2026 = MVRScheduleSearchQuery(
        district="PATNA",
        anchal_circle="Danapur",
        effective_date=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
    )
    results = await provider.search_schedules(query_2026)
    assert len(results) >= 1

    # Date before 2025 schedule -> empty
    query_old = MVRScheduleSearchQuery(
        district="PATNA",
        anchal_circle="Danapur",
        effective_date=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
    )
    results_old = await provider.search_schedules(query_old)
    assert len(results_old) == 0


# =====================================================================
# 5. Area-Unit Conversions (Decimal, Katha, Acre, Bigha, SqFt)
# =====================================================================

def test_05_area_unit_conversions():
    """Tests exact conversion ratios used across Bihar revenue circles."""
    # 1 Katha = 3.125 Decimals
    assert convert_to_decimal(1.0, "KATHA") == 3.125
    assert convert_to_decimal(2.0, "KATHA") == 6.25

    # 1 Acre = 100 Decimals
    assert convert_to_decimal(1.0, "ACRE") == 100.0

    # 1 Bigha = 20 Kathas = 62.5 Decimals
    assert convert_to_decimal(1.0, "BIGHA") == 62.50

    # 1 Decimal = 435.60 SqFt
    assert convert_to_decimal(435.60, "SQFT") == 1.0

    # Bi-directional conversion: 1 Acre -> 43,560 SqFt
    sqft_val = convert_area(1.0, "ACRE", "SQFT")
    assert sqft_val == 43560.0


# =====================================================================
# 6. Numeric Precision, Rounding, and Arithmetic Integrity
# =====================================================================

def test_06_arithmetic_precision_and_structure_addition():
    """Tests exact calculation of land value plus plinth structure value without float drift."""
    engine = ValuationEngine()
    sched = MVRScheduleRecord(
        schedule_id="TEST-001",
        schedule_code="MVR-TEST",
        district="PATNA",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="Kotwa",
        rate_per_decimal=50000.0,
        effective_from=datetime.now(timezone.utc),
    )

    req = ValuationCalculationRequest(
        district="PATNA",
        anchal_circle="Danapur",
        mauza="Kotwa",
        area_value=2.5,
        area_unit="DECIMAL",
        built_up_area_sqft=1000.0,
        construction_rate_sqft=1200.0,
    )

    res = engine.calculate_valuation(req, sched)
    # Land: 2.5 * 50,000 = 125,000.00
    assert res["calculated_land_value"] == 125000.00
    # Structure: 1,000 * 1,200 = 1,200,000.00
    assert res["calculated_structure_value"] == 1200000.00
    # Total: 1,325,000.00
    assert res["total_government_valuation"] == 1325000.00


# =====================================================================
# 7. Buyer Categories & Statutory Concessions
# =====================================================================

def test_07_buyer_categories_and_statutory_concessions():
    """
    Tests Bihar Stamp Duty Rates & Concessions:
    - Male: 6.0%
    - Female (sole purchaser): 5.6% (0.40% concession)
    - Joint (Male + Female): 5.8%
    - Corporate Entity: 6.0%
    """
    engine = StampDutyEngine()
    govt_val = 1000000.0  # Rs. 10 Lakhs

    # Male
    res_male = engine.calculate_charges(govt_val, buyer_category=BuyerGenderCategory.MALE)
    assert res_male["stamp_duty_rate_percent"] == 6.0
    assert res_male["stamp_duty_amount"] == 60000.0
    assert res_male["concession_applied"] is None

    # Female (sole buyer)
    res_female = engine.calculate_charges(govt_val, buyer_category=BuyerGenderCategory.FEMALE)
    assert res_female["stamp_duty_rate_percent"] == 5.6
    assert res_female["stamp_duty_amount"] == 56000.0
    assert "0.40% statutory stamp duty concession" in res_female["concession_applied"]

    # Joint Male + Female
    res_joint = engine.calculate_charges(govt_val, buyer_category=BuyerGenderCategory.JOINT_MALE_FEMALE)
    assert res_joint["stamp_duty_rate_percent"] == 5.8
    assert res_joint["stamp_duty_amount"] == 58000.0
    assert "0.20% proportional stamp duty concession" in res_joint["concession_applied"]


# =====================================================================
# 8. Municipal Surcharge in Urban Corporation Areas
# =====================================================================

def test_08_municipal_corporation_surcharge():
    """In URBAN_CORPORATION (e.g. PMC), +2.0% municipal surcharge applies."""
    engine = StampDutyEngine()
    govt_val = 1000000.0

    # Rural -> 0% surcharge
    res_rural = engine.calculate_charges(govt_val, jurisdiction_type=JurisdictionType.RURAL)
    assert res_rural["municipal_surcharge_percent"] == 0.0
    assert res_rural["municipal_surcharge_amount"] == 0.0

    # Urban Corporation -> 2.0% surcharge
    res_pmc = engine.calculate_charges(govt_val, jurisdiction_type=JurisdictionType.URBAN_CORPORATION)
    assert res_pmc["municipal_surcharge_percent"] == 2.0
    assert res_pmc["municipal_surcharge_amount"] == 20000.0
    # Total charges: 60,000 (duty) + 20,000 (surcharge) + 20,000 (reg fee) = 100,000
    assert res_pmc["total_statutory_charges"] == 100000.0


# =====================================================================
# 9. Registration Fee Calculation
# =====================================================================

def test_09_registration_fee_calculation():
    """Registration fee is flat 2.0% of the assessment base."""
    engine = StampDutyEngine()
    res = engine.calculate_charges(500000.0)
    assert res["registration_fee_rate_percent"] == 2.0
    assert res["registration_fee_amount"] == 10000.0


# =====================================================================
# 10. Section 47-A Assessment Base Rule
# =====================================================================

def test_10_section_47a_assessment_base():
    """
    Assessment base must equal max(Declared Consideration, Government Valuation).
    """
    engine = StampDutyEngine()

    # Consideration < Govt Valuation -> Base = Govt Valuation
    res_low = engine.calculate_charges(government_valuation=500000.0, declared_consideration=400000.0)
    assert res_low["assessment_base"] == 500000.0

    # Consideration > Govt Valuation -> Base = Declared Consideration
    res_high = engine.calculate_charges(government_valuation=500000.0, declared_consideration=750000.0)
    assert res_high["assessment_base"] == 750000.0


# =====================================================================
# 11. Undervaluation Discrepancy Detection (POTENTIAL_UNDERVALUE)
# =====================================================================

def test_11_undervaluation_discrepancy():
    """Tests Section 47-A undervaluation detection and explanation."""
    analyzer = ValuationDiscrepancyAnalyzer()
    res = analyzer.analyze_discrepancy(
        government_valuation=500000.0,
        declared_consideration=350000.0,
        assessment_base=500000.0,
    )
    assert res["discrepancy_status"] == DiscrepancyStatus.POTENTIAL_UNDERVALUE
    assert res["is_undervalued"] is True
    assert res["variance_amount"] == 150000.0
    assert res["variance_percentage"] == 30.0
    assert "Section 47-A" in res["explanation"]


# =====================================================================
# 12. Overvaluation Detection (POTENTIAL_OVERVALUATION)
# =====================================================================

def test_12_overvaluation_discrepancy():
    """Tests commercial premium detection when consideration > 1.5 * govt valuation."""
    analyzer = ValuationDiscrepancyAnalyzer()
    res = analyzer.analyze_discrepancy(
        government_valuation=500000.0,
        declared_consideration=850000.0,  # 1.7x
        assessment_base=850000.0,
    )
    assert res["discrepancy_status"] == DiscrepancyStatus.POTENTIAL_OVERVALUATION
    assert res["is_overvalued"] is True
    assert res["variance_amount"] == 350000.0


# =====================================================================
# 13. No Discrepancy Status
# =====================================================================

def test_13_no_discrepancy():
    """Declared consideration matches or slightly exceeds government valuation."""
    analyzer = ValuationDiscrepancyAnalyzer()
    res = analyzer.analyze_discrepancy(
        government_valuation=500000.0,
        declared_consideration=550000.0,
        assessment_base=550000.0,
    )
    assert res["discrepancy_status"] == DiscrepancyStatus.NO_DISCREPANCY_DETECTED
    assert res["is_undervalued"] is False
    assert res["is_overvalued"] is False


# =====================================================================
# 14. Insufficient Data Behavior
# =====================================================================

def test_14_insufficient_data_behavior():
    """When consideration is omitted, produces INSUFFICIENT_DATA status."""
    analyzer = ValuationDiscrepancyAnalyzer()
    res = analyzer.analyze_discrepancy(
        government_valuation=500000.0,
        declared_consideration=None,
        assessment_base=500000.0,
    )
    assert res["discrepancy_status"] == DiscrepancyStatus.INSUFFICIENT_DATA


# =====================================================================
# 15. Duplicate Imports and Idempotency
# =====================================================================

def test_15_duplicate_schedule_import_idempotency(
    db_session: Session,
    valuation_operator: User,
):
    """Importing the same schedule code twice updates rather than duplicates."""
    service = ValuationService()
    req = MVRScheduleCreateRequest(
        schedule_code="MVR-BR-PAT-DAN-TEST-001",
        district="PATNA",
        registration_office="Danapur",
        anchal_circle="Danapur",
        mauza="TestMauza",
        property_category="AGRICULTURAL",
        road_category="RURAL_ROAD_OR_NO_ROAD",
        rate_per_decimal=55000.0,
    )

    s1 = service.import_schedule(db_session, req, valuation_operator)
    s2 = service.import_schedule(db_session, req, valuation_operator)
    assert s1.schedule_code == s2.schedule_code

    count = db_session.query(MVRSchedule).filter(MVRSchedule.schedule_code == "MVR-BR-PAT-DAN-TEST-001").count()
    assert count == 1


# =====================================================================
# 16. Multi-Tenant Isolation and Authorization
# =====================================================================

@pytest.mark.asyncio
async def test_16_tenant_isolation(
    db_session: Session,
    danapur_case: Case,
    user_b: User,
):
    """User B from Tenant B cannot run case valuation calculation on Tenant A's case."""
    service = ValuationService()
    req = ValuationCalculationRequest(
        case_id=danapur_case.case_id,
        district="PATNA",
        anchal_circle="Danapur",
        mauza="Kotwa",
        area_value=5.0,
        area_unit="DECIMAL",
    )
    with pytest.raises(CrossTenantAccessError):
        await service.calculate_and_assess_property(db_session, req, user_b)


# =====================================================================
# 17. SSRF and Outbound-Host Restrictions
# =====================================================================

def test_17_ssrf_and_outbound_host_restrictions():
    """Outbound URLs are restricted strictly to authorized government registration portals."""
    assert validate_valuation_url("http://registration.bihar.gov.in/mvr")
    assert validate_valuation_url("http://bhumijankari.bihar.gov.in/MVR/")
    assert validate_valuation_url("https://enibandhan.bihar.gov.in/")

    with pytest.raises(ValuationSSRFBlockedError):
        validate_valuation_url("https://unauthorized-attacker-site.com/steal")

    with pytest.raises(ValuationSSRFBlockedError):
        validate_valuation_url("http://169.254.169.254/latest/meta-data/")


# =====================================================================
# 18. Land Intelligence Report Integration & Statutory Disclaimers
# =====================================================================

@pytest.mark.asyncio
async def test_18_report_integration_and_disclaimers(
    db_session: Session,
    danapur_case: Case,
    danapur_parcel: Parcel,
    valuation_operator: User,
):
    """Assembles report with valuation intelligence and generates compliant PDF."""
    service = ValuationService()
    req = ValuationCalculationRequest(
        case_id=danapur_case.case_id,
        parcel_id=danapur_parcel.parcel_id,
        district="PATNA",
        anchal_circle="Danapur",
        mauza="Kotwa",
        property_category="AGRICULTURAL",
        road_category="RURAL_ROAD_OR_NO_ROAD",
        area_value=10.0,
        area_unit="DECIMAL",
        declared_consideration=400000.0,  # Below govt val of 450,000
    )
    await service.calculate_and_assess_property(db_session, req, valuation_operator)

    report_data = assemble_report_data(
        db=db_session,
        case_id=danapur_case.case_id,
        parcel_id=danapur_parcel.parcel_id,
        current_user=valuation_operator,
    )

    assert report_data.section_valuation is not None
    assert report_data.section_valuation.is_assessed is True
    assert len(report_data.section_valuation.valuations) >= 1
    v_item = report_data.section_valuation.valuations[0]
    assert v_item.discrepancy_status == DiscrepancyStatus.POTENTIAL_UNDERVALUE
    assert "STATUTORY VALUATION & STAMP DUTY LIMITATION NOTICE" in report_data.section_valuation.limitation_statement

    # PDF generation
    pdf_bytes = generate_land_intelligence_pdf(report_data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert b"%PDF" in pdf_bytes[:10]


# =====================================================================
# 19. REST API Endpoints Integration
# =====================================================================

def test_19_api_endpoints(
    client: TestClient,
    valuation_operator: User,
):
    """Tests HTTP endpoints for calculate, schedules, and coverage."""
    token = create_access_token({"sub": str(valuation_operator.user_id), "org_id": str(valuation_operator.org_id)})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. POST /api/v1/valuation/calculate
    calc_payload = {
        "district": "PATNA",
        "anchal_circle": "Danapur",
        "mauza": "Kotwa",
        "property_category": "RESIDENTIAL",
        "road_category": "PWD_ROAD",
        "area_value": 5.0,
        "area_unit": "DECIMAL",
        "declared_consideration": 600000.0,
        "buyer_category": "FEMALE",
    }
    resp = client.post("/api/v1/valuation/calculate", json=calc_payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["applied_unit_rate"] == 120000.0
    assert data["calculated_land_value"] == 600000.0
    assert data["stamp_duty_rate_percent"] == 5.6
    assert data["discrepancy_status"] == DiscrepancyStatus.NO_DISCREPANCY_DETECTED

    # 2. GET /api/v1/valuation/schedules
    resp_sched = client.get("/api/v1/valuation/schedules?district=PATNA", headers=headers)
    assert resp_sched.status_code == 200
    assert len(resp_sched.json()) >= 1

    # 3. GET /api/v1/valuation/coverage
    resp_cov = client.get("/api/v1/valuation/coverage", headers=headers)
    assert resp_cov.status_code == 200
    assert len(resp_cov.json()) >= 1
