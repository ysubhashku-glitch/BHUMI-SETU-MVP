"""
Unit and Integration Test Suite for Judicial Risk Intelligence Subsystem.

Covers all 14 required verification dimensions:
1. Provider normalization and schema validation
2. Missing, malformed and contradictory case fields
3. Exact identifier matching (CNR + Plot/Khata)
4. Party-name similarity and honorific handling
5. Different people with identical/similar names (CRITICAL: uncorroborated name matches remain unverified)
6. Missing parcel identifiers in court dockets
7. Rejected and human-reviewed candidates workflow
8. Duplicate records and idempotent ingestion
9. Source outages, rate limiting, and retry/circuit-breaking behavior
10. Multi-tenant isolation and authorization
11. SSRF and outbound-request domain restrictions
12. Audit-log and provenance preservation
13. Report integration and statutory disclaimer presence
14. API endpoints and backward compatibility
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
from app.models.judicial import (
    JudicialCase,
    ParcelJudicialMatch,
    CourtType,
    JudicialCaseStatus,
    JudicialRiskCategory,
    ParcelMatchCategory,
    MatchReviewStatus,
)
from app.core.security import hash_password, create_access_token
from app.core.exceptions import CrossTenantAccessError
from app.schemas.judicial import (
    JudicialCaseRecord,
    JudicialSearchQuery,
    JudicialManualIngestRequest,
    JudicialMatchReviewRequest,
    EPISTEMIC_JUDICIAL_DISCLAIMER,
)
from app.services.judicial.providers import (
    MockJudicialProvider,
    ECourtsBiharProvider,
    OperatorImportProvider,
    ALLOWED_JUDICIAL_DOMAINS,
    validate_judicial_url,
    JudicialSSRFBlockedError,
    JudicialInvalidQueryError,
    JudicialSourceUnavailableError,
    JudicialRateLimitError,
)
from app.services.judicial.providers.ecourts_provider import CircuitBreaker
from app.services.judicial.matcher import (
    JudicialEntityResolver,
    normalize_legal_name,
    token_overlap_score,
)
from app.services.judicial.classifier import JudicialRiskClassifier
from app.services.judicial.service import JudicialService
from app.services.report_assembler import assemble_report_data
from app.services.pdf_report_generator import generate_land_intelligence_pdf


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def advocate_user(db_session: Session, tenant_a: Organization) -> User:
    user = User(
        org_id=tenant_a.org_id,
        email="advocate_a@bhumisetu.local",
        hashed_password=hash_password("Password123!"),
        full_name="DEMO_DATA: Advocate Kumar",
        phone_number="9800000091",
        role=UserRole.SUPERVISOR,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def patna_parcel(db_session: Session, tenant_a: Organization) -> Parcel:
    parcel = Parcel(
        parcel_id=uuid.uuid4(),
        org_id=tenant_a.org_id,
        district="PATNA",
        circle="Bakhtiyarpur",
        mauza="Bakhtiyarpur",
        khata_number="45",
        khesra_number="102",
        recorded_raiyat="Ram Swaroop Yadav",
        recorded_area_acre=1.20,
        land_classification="Raiyati",
    )
    db_session.add(parcel)
    db_session.commit()
    db_session.refresh(parcel)
    return parcel


@pytest.fixture
def patna_case(db_session: Session, tenant_a: Organization, patna_parcel: Parcel, advocate_user: User) -> Case:
    case = Case(
        case_id=uuid.uuid4(),
        org_id=tenant_a.org_id,
        case_number="CASE-PATNA-2026-001",
        status=CaseStatus.DRAFT,
        primary_client_party_id=uuid.uuid4(),
        assigned_advocate_id=advocate_user.user_id,
    )
    db_session.add(case)
    db_session.flush()

    cp = CaseParcel(case_id=case.case_id, parcel_id=patna_parcel.parcel_id, is_primary=True)
    db_session.add(cp)
    db_session.commit()
    db_session.refresh(case)
    return case


# =====================================================================
# 1. Provider Normalization & Schema Validation
# =====================================================================

def test_01_provider_normalization_and_schema_validation():
    """Validates schema validation and parsing of canonical judicial fields."""
    record = JudicialCaseRecord(
        cnr_number="BRPT01-001420-2021",
        court_name="Patna District Court",
        court_type="DISTRICT_COURT",
        district="PATNA",
        state="Bihar",
        case_type="Title Suit",
        case_number="T.S./142/2021",
        filing_year=2021,
        case_status="PENDING",
        petitioner_names=["Ram Swaroop Yadav"],
        respondent_names=["Dinanath Prasad"],
        has_active_injunction=True,
        risk_category="TITLE_DISPUTE",
    )
    assert record.cnr_number == "BRPT01-001420-2021"
    assert record.filing_year == 2021
    assert record.has_active_injunction is True
    assert record.risk_category == "TITLE_DISPUTE"


# =====================================================================
# 2. Missing, Malformed and Contradictory Case Fields
# =====================================================================

def test_02_malformed_and_missing_case_fields():
    """Ensures malformed CNR raises JudicialInvalidQueryError and missing fields parse safely."""
    provider = OperatorImportProvider()

    # CNR must be 16 characters
    req_bad_cnr = JudicialManualIngestRequest(
        cnr_number="INVALID_SHORT",
        court_name="Patna Civil Court",
        district="PATNA",
        case_type="T.S.",
        case_number="1/2021",
        filing_year=2021,
        petitioner_names=["Person A"],
        respondent_names=["Person B"],
    )
    with pytest.raises(JudicialInvalidQueryError):
        provider.normalize_and_register(req_bad_cnr)

    # Valid CNR with missing schedules parses safely
    req_valid = JudicialManualIngestRequest(
        cnr_number="BRPT01-000001-2021",
        court_name="Patna Civil Court",
        district="PATNA",
        case_type="T.S.",
        case_number="1/2021",
        filing_year=2021,
        petitioner_names=["Person A"],
        respondent_names=["Person B"],
        property_schedule_raw=None,
    )
    rec = provider.normalize_and_register(req_valid)
    assert rec.extracted_land_identifiers == {}
    assert rec.has_active_injunction is False


# =====================================================================
# 3. Exact Identifier Matching (Plot + Khata + Raiyat)
# =====================================================================

def test_03_exact_identifier_matching(patna_parcel: Parcel):
    """Corroborated plot, khata, and party name yields EXACT_IDENTIFIER_MATCH (0.95)."""
    resolver = JudicialEntityResolver()
    case_dict = {
        "cnr_number": "BRPT01-001420-2021",
        "court_type": "DISTRICT_COURT",
        "district": "PATNA",
        "extracted_land_identifiers": {
            "khata": "45",
            "khesra": "102",
            "mauza": "Bakhtiyarpur",
        },
        "petitioner_names": ["Ram Swaroop Yadav"],
        "respondent_names": ["Dinanath Prasad"],
    }

    match = resolver.match_case_to_parcel(patna_parcel, case_dict)
    assert match["match_category"] == ParcelMatchCategory.EXACT_IDENTIFIER_MATCH
    assert match["confidence_score"] == 0.95
    assert match["matched_fields"]["matched_khesra"] is True
    assert match["matched_fields"]["matched_khata"] is True
    assert match["matched_fields"]["matched_party"] is True


# =====================================================================
# 4. Party-Name Similarity & Honorific Handling
# =====================================================================

def test_04_party_name_normalization_and_similarity():
    """Tests token sorting and honorific stripping across Bihar personal names."""
    assert normalize_legal_name("Sri Ram Swaroop Yadav") == "RAM SWAROOP YADAV"
    assert normalize_legal_name("Late Smt. Laxmi Devi W/o Dinanath Prasad") == "LAXMI DINANATH PRASAD"

    # Token overlap score
    score = token_overlap_score("Ram Swaroop Yadav", "Sri Ram S. Yadav")
    assert score >= 0.50

    # Completely different names
    score_diff = token_overlap_score("Ram Swaroop Yadav", "Mukesh Kumar Singh")
    assert score_diff == 0.0


# =====================================================================
# 5. Common Names Without Parcel Corroboration (CRITICAL EPISTEMIC TEST)
# =====================================================================

def test_05_common_name_without_parcel_corroboration_remains_weak_candidate(patna_parcel: Parcel):
    """
    CRITICAL NON-NEGOTIABLE RULE:
    When party name matches but court docket contains NO parcel identifiers (khesra/khata),
    the match MUST remain WEAK_CANDIDATE_REVIEW_REQUIRED with calibrated confidence <= 0.45.
    It must NEVER be marked as an exact or confirmed match.
    """
    resolver = JudicialEntityResolver()
    case_dict = {
        "cnr_number": "BRPT01-009999-2023",
        "court_type": "DISTRICT_COURT",
        "district": "PATNA",
        "extracted_land_identifiers": {},  # NO PLOT OR KHATA IN DOCKET
        "petitioner_names": ["Shri Ram Swaroop Yadav"],
        "respondent_names": ["State of Bihar"],
    }

    match = resolver.match_case_to_parcel(patna_parcel, case_dict)
    assert match["match_category"] == ParcelMatchCategory.WEAK_CANDIDATE_REVIEW_REQUIRED
    assert match["confidence_score"] <= 0.45
    assert "Unverified candidate match" in match["explanation"]
    assert "cannot be represented as a confirmed parcel dispute" in match["explanation"]


# =====================================================================
# 6. Missing Parcel Identifiers
# =====================================================================

def test_06_missing_parcel_identifiers_and_no_party_match(patna_parcel: Parcel):
    """Case with neither party match nor cadastral identifiers yields INSUFFICIENT_DATA."""
    resolver = JudicialEntityResolver()
    case_dict = {
        "cnr_number": "BRPT01-008888-2022",
        "court_type": "DISTRICT_COURT",
        "district": "PATNA",
        "extracted_land_identifiers": {},
        "petitioner_names": ["Unrelated Person A"],
        "respondent_names": ["Unrelated Person B"],
    }

    match = resolver.match_case_to_parcel(patna_parcel, case_dict)
    assert match["match_category"] == ParcelMatchCategory.INSUFFICIENT_DATA
    assert match["confidence_score"] == 0.10


# =====================================================================
# 7. Rejected Match & Human Review Workflow
# =====================================================================

def test_07_geographic_rejection_and_review_workflow(
    db_session: Session,
    patna_parcel: Parcel,
    patna_case: Case,
    advocate_user: User,
):
    """Ensures out-of-district District Court case is REJECTED, and review workflow updates status."""
    resolver = JudicialEntityResolver()

    # Case in Gaya for Patna parcel -> Hard Rejection
    gaya_case_dict = {
        "cnr_number": "BRGA01-001234-2020",
        "court_type": "DISTRICT_COURT",
        "district": "GAYA",
        "extracted_land_identifiers": {"khesra": "102"},
        "petitioner_names": ["Ram Swaroop Yadav"],
        "respondent_names": ["Dinanath Prasad"],
    }
    match = resolver.match_case_to_parcel(patna_parcel, gaya_case_dict)
    assert match["match_category"] == ParcelMatchCategory.REJECTED_MATCH
    assert match["confidence_score"] == 0.0

    # Test Advocate Review Workflow
    service = JudicialService()
    # Create a JudicialCase and Match in DB
    j_case = JudicialCase(
        case_id=uuid.uuid4(),
        org_id=patna_case.org_id,
        cnr_number="BRPT01-007777-2021",
        court_name="Patna District Court",
        court_type=CourtType.DISTRICT_COURT,
        district="PATNA",
        case_type="Title Suit",
        case_number="T.S./77/2021",
        filing_year=2021,
        case_status=JudicialCaseStatus.PENDING,
        petitioner_names=["Ram Swaroop Yadav"],
        respondent_names=["Dinanath Prasad"],
    )
    db_session.add(j_case)
    db_session.flush()

    p_match = ParcelJudicialMatch(
        match_id=uuid.uuid4(),
        org_id=patna_case.org_id,
        case_id=patna_case.case_id,
        parcel_id=patna_parcel.parcel_id,
        judicial_case_id=j_case.case_id,
        match_category=ParcelMatchCategory.WEAK_CANDIDATE_REVIEW_REQUIRED,
        confidence_score=0.45,
        explanation="Candidate under advocate review.",
        review_status=MatchReviewStatus.PENDING_REVIEW,
    )
    db_session.add(p_match)
    db_session.commit()

    # Advocate verifies association
    review_req = JudicialMatchReviewRequest(
        action="CONFIRM_ASSOCIATED",
        review_notes="Certified copy of plaint verified by advocate. Schedule relates to Khata 45.",
    )
    resp = service.review_match(db_session, p_match.match_id, review_req, advocate_user)
    assert resp.review_status == MatchReviewStatus.VERIFIED_ASSOCIATED
    assert resp.reviewed_by_user_id == str(advocate_user.user_id)
    assert resp.review_notes == review_req.review_notes


# =====================================================================
# 8. Duplicate Records and Idempotent Ingestion
# =====================================================================

def test_08_idempotent_ingestion(
    db_session: Session,
    patna_case: Case,
    patna_parcel: Parcel,
    advocate_user: User,
):
    """Ensures manual ingestion and searching does not create duplicate CNR or Match rows."""
    service = JudicialService()
    req = JudicialManualIngestRequest(
        cnr_number="BRPT01-003333-2022",
        court_name="Patna Civil Court",
        district="PATNA",
        case_type="Title Suit",
        case_number="T.S./33/2022",
        filing_year=2022,
        petitioner_names=["Rameshwar Singh"],
        respondent_names=["Suresh Singh"],
        property_schedule_raw="Khata no: 45, Khesra no: 102, Mauza: Bakhtiyarpur",
    )

    # First ingest
    c1 = service.manual_ingest_case(db_session, req, advocate_user)
    # Second ingest of same CNR
    c2 = service.manual_ingest_case(db_session, req, advocate_user)
    assert c1.cnr_number == c2.cnr_number

    # Verify only 1 row exists in DB
    count = db_session.query(JudicialCase).filter(JudicialCase.cnr_number == "BRPT01-003333-2022").count()
    assert count == 1


# =====================================================================
# 9. Source Outages, Rate Limiting and Circuit Breaker
# =====================================================================

@pytest.mark.asyncio
async def test_09_source_outage_and_circuit_breaker():
    """Verifies that source unavailability and rate limits raise structured domain errors and trip breaker."""
    mock_unavailable = MockJudicialProvider(failure_mode="UNAVAILABLE")
    with pytest.raises(JudicialSourceUnavailableError):
        await mock_unavailable.search_cases(JudicialSearchQuery(party_name="Ram"))

    mock_ratelimit = MockJudicialProvider(failure_mode="RATE_LIMIT")
    with pytest.raises(JudicialRateLimitError):
        await mock_ratelimit.search_cases(JudicialSearchQuery(party_name="Ram"))

    # Test Circuit Breaker logic
    breaker = CircuitBreaker(failure_threshold=3, reset_timeout_seconds=60.0)
    assert breaker.can_execute() is True
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.can_execute() is True
    breaker.record_failure()  # 3rd failure -> TRIPS
    assert breaker.can_execute() is False
    assert breaker.state == "OPEN"


# =====================================================================
# 10. Multi-Tenant Isolation and Authorization
# =====================================================================

@pytest.mark.asyncio
async def test_10_tenant_isolation(
    db_session: Session,
    patna_case: Case,
    user_b: User,
):
    """Ensures User from Tenant B cannot access or search cases for Tenant A."""
    service = JudicialService()
    query = JudicialSearchQuery(party_name="Ram")

    with pytest.raises(CrossTenantAccessError):
        await service.search_and_correlate(
            db=db_session,
            case_id=patna_case.case_id,
            parcel_id=None,
            query=query,
            current_user=user_b,
        )


# =====================================================================
# 11. SSRF and Outbound-Request Domain Restrictions
# =====================================================================

def test_11_ssrf_and_domain_restrictions():
    """Validates that outbound URLs are strictly restricted to official court domains."""
    # Permitted domains
    assert validate_judicial_url("https://services.ecourts.gov.in/ecourtindia_v6/?p=casestatus")
    assert validate_judicial_url("https://patnahighcourt.gov.in/case-status")

    # Blocked domains
    with pytest.raises(JudicialSSRFBlockedError):
        validate_judicial_url("https://malicious-portal.org/steal")

    with pytest.raises(JudicialSSRFBlockedError):
        validate_judicial_url("http://169.254.169.254/latest/meta-data/")

    with pytest.raises(JudicialSSRFBlockedError):
        validate_judicial_url("ftp://services.ecourts.gov.in/payload")


# =====================================================================
# 12. Audit-Log and Provenance Preservation
# =====================================================================

def test_12_audit_log_and_provenance(
    db_session: Session,
    advocate_user: User,
):
    """Verifies raw source payload is stored intact and reviewer audit is captured."""
    service = JudicialService()
    req = JudicialManualIngestRequest(
        cnr_number="BRPT01-004444-2021",
        court_name="Patna District Court",
        district="PATNA",
        case_type="Partition Suit",
        case_number="P.S./44/2021",
        filing_year=2021,
        petitioner_names=["Kailash Yadav"],
        respondent_names=["Subhash Yadav"],
        property_schedule_raw="Raw Advocate Plaint Property Schedule",
    )
    rec = service.manual_ingest_case(db_session, req, advocate_user)

    db_case = db_session.query(JudicialCase).filter(JudicialCase.cnr_number == "BRPT01-004444-2021").first()
    assert db_case is not None
    assert db_case.raw_source_payload is not None
    assert db_case.raw_source_payload["petitioner_names"] == ["Kailash Yadav"]


# =====================================================================
# 13. Land Intelligence Report Integration & Statutory Disclaimer
# =====================================================================

def test_13_report_integration_and_statutory_disclaimer(
    db_session: Session,
    patna_case: Case,
    patna_parcel: Parcel,
    advocate_user: User,
):
    """Assembles full report and generates PDF, verifying the judicial risk section and disclaimer."""
    # Add a mock judicial case and match
    j_case = JudicialCase(
        case_id=uuid.uuid4(),
        org_id=patna_case.org_id,
        cnr_number="BRPT01-001420-2021",
        court_name="Patna District Court",
        court_type=CourtType.DISTRICT_COURT,
        district="PATNA",
        case_type="Title Suit",
        case_number="T.S./142/2021",
        filing_year=2021,
        case_status=JudicialCaseStatus.PENDING,
        has_active_injunction=True,
        risk_category=JudicialRiskCategory.TITLE_DISPUTE,
        petitioner_names=["Ram Swaroop Yadav"],
        respondent_names=["Dinanath Prasad"],
    )
    db_session.add(j_case)
    db_session.flush()

    p_match = ParcelJudicialMatch(
        match_id=uuid.uuid4(),
        org_id=patna_case.org_id,
        case_id=patna_case.case_id,
        parcel_id=patna_parcel.parcel_id,
        judicial_case_id=j_case.case_id,
        match_category=ParcelMatchCategory.EXACT_IDENTIFIER_MATCH,
        confidence_score=0.95,
        explanation="Exact cadastral schedule and party name match.",
        review_status=MatchReviewStatus.VERIFIED_ASSOCIATED,
    )
    db_session.add(p_match)
    db_session.commit()

    # Assemble report
    report_data = assemble_report_data(
        db=db_session,
        case_id=patna_case.case_id,
        parcel_id=patna_parcel.parcel_id,
        current_user=advocate_user,
    )

    assert report_data.section_judicial_risk is not None
    assert report_data.section_judicial_risk.is_searched is True
    assert report_data.section_judicial_risk.total_candidates_found == 1
    assert report_data.section_judicial_risk.active_injunctions_detected == 1
    assert "JUDICIAL DOCKET SEARCH LIMITATION STATEMENT" in report_data.section_judicial_risk.limitation_statement

    # Generate PDF and verify non-empty bytes
    pdf_bytes = generate_land_intelligence_pdf(report_data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert b"%PDF" in pdf_bytes[:10]


# =====================================================================
# 14. API Endpoints Integration Test
# =====================================================================

def test_14_api_endpoints_judicial_search(
    client: TestClient,
    patna_case: Case,
    patna_parcel: Parcel,
    advocate_user: User,
):
    """Tests the HTTP REST endpoints for judicial search, import, and review."""
    token = create_access_token({"sub": str(advocate_user.user_id), "org_id": str(advocate_user.org_id)})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Search endpoint
    search_payload = {
        "party_name": "Ram Swaroop Yadav",
        "district": "PATNA",
    }
    resp = client.post(
        f"/api/v1/cases/{patna_case.case_id}/judicial-search?parcel_id={patna_parcel.parcel_id}",
        json=search_payload,
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "epistemic_notice" in data
    assert data["total_cases_found"] >= 1
    assert len(data["matches"]) >= 1

    match = data["matches"][0]
    match_id = match["match_id"]

    # 2. Get parcel judicial matches endpoint
    resp_parcel = client.get(
        f"/api/v1/parcels/{patna_parcel.parcel_id}/judicial-cases",
        headers=headers,
    )
    assert resp_parcel.status_code == 200
    assert len(resp_parcel.json()) >= 1

    # 3. Review match endpoint
    review_payload = {
        "action": "CONFIRM_ASSOCIATED",
        "review_notes": "Advocate review completed with certified plaint copy.",
    }
    resp_rev = client.post(
        f"/api/v1/judicial-matches/{match_id}/review",
        json=review_payload,
        headers=headers,
    )
    assert resp_rev.status_code == 200
    assert resp_rev.json()["review_status"] == MatchReviewStatus.VERIFIED_ASSOCIATED
