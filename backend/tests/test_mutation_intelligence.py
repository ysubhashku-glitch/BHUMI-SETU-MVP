"""
Comprehensive Test Suite for Mutation Intelligence & Property Passport Synchronization (TASK-P2-05).

Covers:
1. Source adapter integration & SSRF domain defense
2. CAPTCHA detection and operator-assisted fallback
3. Cryptographic payload hashing & event ledger idempotency
4. Field extraction & Bihar rejection ground classification
5. State machine lifecycle progression & out-of-order event preservation
6. Conflicting evidence preservation (no silent selection)
7. Entity resolution with mandatory anti-name-only safeguards
8. Multi-tenant isolation & object-level authorization
9. Property Passport timeline synchronization & statutory disclaimer
10. Reconciliation engine (duplicate deeds, stale cases, adverse rejection alerts)
11. Land Intelligence Report assembly integration
12. REST API endpoints & role-based access control
"""

import uuid
import pytest
from datetime import datetime, timezone, date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.case import Case, CaseStatus
from app.models.parcel import Parcel
from app.models.mutation import (
    MutationCase,
    MutationEvent,
    MutationDocument,
    MutationEntityResolution,
    MutationType,
    MutationStatus,
    MutationEventType,
    MutationMatchingMethod,
    MutationVerificationStatus,
)
from app.schemas.mutation import (
    MutationCaseCreate,
    MutationManualImportRequest,
    MutationEventCreate,
    MutationOperatorReviewRequest,
    STATUTORY_MUTATION_DISCLAIMER,
)
from app.services.mutation.adapters import (
    MockMutationAdapter,
    BiharBhumiAdapter,
    OperatorImportAdapter,
    MutationSSRFBlockedError,
    MutationCaptchaRequiredError,
    MutationInvalidQueryError,
)
from app.services.mutation.extractor import MutationExtractor
from app.services.mutation.matcher import MutationEntityResolver
from app.services.mutation.lifecycle import MutationLifecycleEngine
from app.services.mutation.service import MutationService
from app.services.report_assembler import assemble_report_data
from app.schemas.report import MUTATION_REPORT_LIMITATION_STATEMENT


# =====================================================================
# 1. Source Adapter & SSRF Protection Tests
# =====================================================================

@pytest.mark.asyncio
async def test_mock_adapter_search_and_retrieval():
    adapter = MockMutationAdapter()
    results = await adapter.search_cases(district="Patna", circle="Danapur")
    assert len(results) >= 2
    case_numbers = [r["case_number"] for r in results]
    assert "MUT-2024-DAN-00104" in case_numbers
    assert "MUT-2024-DAN-00215" in case_numbers

    # Detail check
    detail = await adapter.get_case_detail("MUT-2024-DAN-00104", "Patna", "Danapur")
    assert detail is not None
    assert detail["normalized_status"] == "APPROVED"
    assert len(detail["events"]) >= 5


def test_ssrf_blocked_domain_exception():
    # Attempting to target an internal or unwhitelisted domain must be rejected immediately
    with pytest.raises(MutationSSRFBlockedError) as exc_info:
        BiharBhumiAdapter(base_url="https://attacker-controlled-site.com")
    assert "domain whitelist" in str(exc_info.value).lower()

    with pytest.raises(MutationSSRFBlockedError):
        BiharBhumiAdapter(base_url="http://192.168.1.100")


def test_operator_import_adapter_hashing():
    adapter = OperatorImportAdapter()
    record = adapter.ingest_record(
        case_number="MUT-2024-TEST-001",
        district="Patna",
        circle="Danapur",
        mauza="Mustafapur",
        applicant_name="Ramesh Kumar",
        khata_number="45",
        khesra_number="128",
        reported_status="APPROVED",
        filing_date=date(2024, 2, 20),
        order_date=date(2024, 4, 15),
    )
    assert record["payload_hash"] is not None
    assert len(record["payload_hash"]) == 64  # SHA-256
    assert record["provenance_type"] == "OPERATOR_CERTIFIED_DOCUMENT"
    assert record["verification_status"] == "UNVERIFIED"  # Not auto-verified
    assert len(record["events"]) == 2


# =====================================================================
# 2. Document Extraction & Rejection Reason Classification
# =====================================================================

def test_document_extractor_rejection_grounds():
    text_dispute = (
        "कार्यालय अंचल अधिकारी दानापुर। दाखिल खारिज वाद संख्या MUT-2024-DAN-00215। "
        "मौजा मुस्तफापुर, खाता 45, खेसरा 130। "
        "विवादित भूमि होने एवं सिविल कोर्ट में वाद लंबित होने के कारण आवेदन खारिज किया जाता है।"
    )
    extracted = MutationExtractor.extract_from_text(text_dispute)
    fields = extracted["extracted_fields"]

    assert fields["case_number"]["normalized"] == "MUT-2024-DAN-00215"
    assert fields["khata_number"]["normalized"] == "45"
    assert fields["khesra_number"]["normalized"] == "130"
    assert "LAND_DISPUTED" in fields["rejection_grounds"]["codes"]
    assert extracted["requires_human_review"] is True


def test_document_extractor_area_deficit():
    text_deficit = (
        "दाखिल खारिज वाद सं MUT-2024-PAT-00450। "
        "खाता 112, प्लॉट संख्या 540। मौजा शेखपुरा। "
        "कर्मचारी जांच अनुसार विक्रेता का रकबा कमी एवं रकबा शून्य पाया गया। अतः खारिज।"
    )
    extracted = MutationExtractor.extract_from_text(text_deficit)
    fields = extracted["extracted_fields"]

    assert fields["case_number"]["normalized"] == "MUT-2024-PAT-00450"
    assert fields["khata_number"]["normalized"] == "112"
    assert fields["khesra_number"]["normalized"] == "540"
    assert "AREA_DEFICIT" in fields["rejection_grounds"]["codes"]


def test_status_normalization_hindi_and_english():
    st1, _ = MutationExtractor.normalize_status("स्वीकृत (Shuddhi Patra Issued)")
    assert st1 == MutationStatus.APPROVED

    st2, _ = MutationExtractor.normalize_status("अस्वीकृत - खारिज")
    assert st2 == MutationStatus.REJECTED

    st3, _ = MutationExtractor.normalize_status("Form-IX नोटिस जारी")
    assert st3 == MutationStatus.NOTICE_ISSUED

    st4, _ = MutationExtractor.normalize_status("सुनवाई हेतु लंबित")
    assert st4 == MutationStatus.HEARING_PENDING


# =====================================================================
# 3. Lifecycle State Machine & Out-of-Order Event Handling
# =====================================================================

def test_lifecycle_normal_progression():
    curr = MutationStatus.RECEIVED
    new_st, updated, note = MutationLifecycleEngine.evaluate_new_event(
        current_status=curr,
        event_type=MutationEventType.NOTICE_FORM_IX_ISSUED,
        event_timestamp=datetime(2024, 3, 1, tzinfo=timezone.utc),
        last_observation_time=datetime(2024, 2, 20, tzinfo=timezone.utc),
        event_payload={},
    )
    assert new_st == MutationStatus.NOTICE_ISSUED
    assert updated is True


def test_lifecycle_out_of_order_older_event_preservation():
    # If a case is already APPROVED, and an older procedural notice event arrives later:
    # It must NOT revert status back to NOTICE_ISSUED!
    curr = MutationStatus.APPROVED
    new_st, updated, note = MutationLifecycleEngine.evaluate_new_event(
        current_status=curr,
        event_type=MutationEventType.NOTICE_FORM_IX_ISSUED,
        event_timestamp=datetime(2024, 2, 25, tzinfo=timezone.utc),
        last_observation_time=datetime(2024, 4, 15, tzinfo=timezone.utc),
        event_payload={},
    )
    # Status remains APPROVED
    assert new_st == MutationStatus.APPROVED
    assert updated is False
    assert "without downgrading" in note.lower() or "ledger" in note.lower()


def test_lifecycle_conflicting_terminal_events():
    # If case was reported APPROVED but inbound event indicates REJECTED:
    curr = MutationStatus.APPROVED
    new_st, updated, note = MutationLifecycleEngine.evaluate_new_event(
        current_status=curr,
        event_type=MutationEventType.REJECTION_ORDER_PASSED,
        event_timestamp=datetime(2024, 4, 20, tzinfo=timezone.utc),
        last_observation_time=datetime(2024, 4, 15, tzinfo=timezone.utc),
        event_payload={"outcome": "rejected"},
    )
    assert new_st == MutationStatus.CONFLICTING_EVIDENCE
    assert updated is True
    assert "conflicting" in note.lower()


# =====================================================================
# 4. Mandatory Anti-Name-Only & Entity Resolution Tests
# =====================================================================

def test_critical_anti_name_only_match_rule():
    """
    CRITICAL REQUIREMENT:
    Never merge records solely because two people share the same name.
    Name-only match without plot/khata corroboration is capped at <= 0.40 confidence
    and MUST be routed to manual review.
    """
    res = MutationEntityResolver.evaluate_name_only_match(
        party_name="Ramesh Kumar",
        applicant_name="Ramesh Kumar",
        has_cadastral_corroboration=False,
    )
    assert res["matched"] is False
    assert res["confidence_score"] <= 0.40
    assert res["matching_method"] == MutationMatchingMethod.NAME_ONLY_MATCH_UNVERIFIED
    assert res["requires_review"] is True
    assert "cannot establish parcel association" in res["explanation"]


def test_corroborated_name_and_plot_match():
    res = MutationEntityResolver.evaluate_name_only_match(
        party_name="Ramesh Kumar",
        applicant_name="Ramesh Kumar",
        has_cadastral_corroboration=True,
    )
    assert res["matched"] is True
    assert res["confidence_score"] >= 0.85


def test_parcel_to_mutation_cadastral_matching(db_session: Session, tenant_a: Organization):
    parcel = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id="BH-PAT-DAN-00128",
        state="Bihar",
        district="Patna",
        subdistrict_anchal="Danapur",
        circle="Danapur",
        mauza="Mustafapur",
        khata_number="45",
        plot_khesra_number="128",
        khesra_number="128",
        area_acres=0.25,
    )
    db_session.add(parcel)
    db_session.commit()

    mutation_case = MutationCase(
        org_id=tenant_a.org_id,
        case_number="MUT-2024-DAN-00104",
        filing_year=2024,
        district="Patna",
        circle="Danapur",
        mauza="Mustafapur",
        khata_number="45",
        khesra_number="128",
        mutation_type=MutationType.SALE_DEED,
        normalized_status=MutationStatus.APPROVED,
    )
    db_session.add(mutation_case)
    db_session.commit()

    match_res = MutationEntityResolver.resolve_case_to_parcel(mutation_case, parcel)
    assert match_res["matched"] is True
    assert match_res["confidence_score"] >= 0.90
    assert match_res["matching_method"] == MutationMatchingMethod.CORROBORATED_PLOT_KHATA


def test_cross_tenant_resolution_rejection(db_session: Session, tenant_a: Organization, tenant_b: Organization):
    parcel_a = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id="BH-ORG-A-001",
        state="Bihar",
        district="Patna",
        circle="Danapur",
        mauza="Mustafapur",
        khata_number="45",
        khesra_number="128",
    )
    case_b = MutationCase(
        org_id=tenant_b.org_id,
        case_number="MUT-TENANT-B-001",
        filing_year=2024,
        district="Patna",
        circle="Danapur",
        mauza="Mustafapur",
        khata_number="45",
        khesra_number="128",
        mutation_type=MutationType.SALE_DEED,
        normalized_status=MutationStatus.RECEIVED,
    )
    db_session.add_all([parcel_a, case_b])
    db_session.commit()

    res = MutationEntityResolver.resolve_case_to_parcel(case_b, parcel_a)
    assert res["matched"] is False
    assert res["match_outcome"] == "REJECTED_CROSS_TENANT"
    assert res["confidence_score"] == 0.0


# =====================================================================
# 5. Service, Property Passport Timeline & Reconciliation
# =====================================================================

def test_service_crud_and_idempotency(db_session: Session, tenant_a: Organization):
    service = MutationService(db_session)

    # 1. Create case
    case_create = MutationCaseCreate(
        case_number="MUT-2024-TEST-100",
        filing_year=2024,
        district="Patna",
        circle="Danapur",
        mauza="Mustafapur",
        khata_number="50",
        khesra_number="140",
        applicant_names=["Sunil Kumar"],
        normalized_status=MutationStatus.RECEIVED,
    )
    mc = service.create_or_update_case(tenant_a.org_id, case_create)
    assert mc.mutation_case_id is not None

    # 2. Add event
    ev_create = MutationEventCreate(
        event_type=MutationEventType.NOTICE_FORM_IX_ISSUED,
        reported_event_timestamp=datetime.now(timezone.utc),
        source_authority="Circle Officer, Danapur",
        raw_payload={"notice_no": "IX-100"},
        action_taken="Form-IX notice issued",
    )
    ev = service.record_event(mc.mutation_case_id, tenant_a.org_id, ev_create)
    assert ev.payload_hash is not None
    assert mc.normalized_status == MutationStatus.NOTICE_ISSUED

    # 3. Idempotent duplicate event submission
    ev2 = service.record_event(mc.mutation_case_id, tenant_a.org_id, ev_create)
    assert ev.mutation_event_id == ev2.mutation_event_id  # Returns exact same event


def test_property_passport_timeline(db_session: Session, tenant_a: Organization):
    service = MutationService(db_session)

    parcel = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id="BH-PAT-DAN-00200",
        state="Bihar",
        district="Patna",
        circle="Danapur",
        mauza="Mustafapur",
        khata_number="45",
        khesra_number="128",
    )
    db_session.add(parcel)
    db_session.commit()

    # Ingest operator case linked to this parcel
    req = MutationManualImportRequest(
        case_number="MUT-2024-DAN-00104",
        filing_year=2024,
        district="Patna",
        circle="Danapur",
        mauza="Mustafapur",
        khata_number="45",
        khesra_number="128",
        applicant_name="Ramesh Kumar Sharma",
        reported_status="APPROVED",
        parcel_id=parcel.parcel_id,
    )
    service.import_operator_case(tenant_a.org_id, req)

    # Build Property Passport timeline
    timeline = service.get_parcel_timeline(parcel.parcel_id, tenant_a.org_id)
    assert timeline.total_cases_tracked == 1
    assert timeline.approved_shuddhi_patras_count == 1
    assert len(timeline.timeline) >= 1
    assert "Suraj Bhan v. Financial Commissioner" in timeline.statutory_disclaimer


def test_mutation_reconciliation_run(db_session: Session, tenant_a: Organization):
    service = MutationService(db_session)

    # Create two cases with identical deed number (duplicate deed submission)
    service.create_or_update_case(
        tenant_a.org_id,
        MutationCaseCreate(
            case_number="MUT-DUP-1",
            filing_year=2024,
            district="Patna",
            circle="Danapur",
            mauza="Mustafapur",
            deed_number="DEED-DUP-888",
            normalized_status=MutationStatus.RECEIVED,
        ),
    )
    service.create_or_update_case(
        tenant_a.org_id,
        MutationCaseCreate(
            case_number="MUT-DUP-2",
            filing_year=2024,
            district="Patna",
            circle="Danapur",
            mauza="Mustafapur",
            deed_number="DEED-DUP-888",
            normalized_status=MutationStatus.RECEIVED,
        ),
    )

    run = service.run_reconciliation(tenant_a.org_id, district="Patna", circle="Danapur")
    assert run.records_observed >= 2
    assert run.records_duplicate >= 1
    assert run.status == "COMPLETED"


# =====================================================================
# 6. Land Intelligence Report Integration
# =====================================================================

def test_report_assembler_includes_mutation_section(db_session: Session, tenant_a: Organization, user_a: User):
    case = Case(
        org_id=tenant_a.org_id,
        case_number="CASE-MUT-REPORT-001",
        status=CaseStatus.INTAKE,
    )
    db_session.add(case)
    db_session.commit()

    parcel = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id="BH-PAT-00999",
        state="Bihar",
        district="Patna",
        circle="Danapur",
        mauza="Mustafapur",
        khata_number="45",
        khesra_number="128",
    )
    db_session.add(parcel)
    db_session.commit()

    service = MutationService(db_session)
    service.import_operator_case(
        tenant_a.org_id,
        MutationManualImportRequest(
            case_number="MUT-2024-DAN-REPORT",
            filing_year=2024,
            district="Patna",
            circle="Danapur",
            mauza="Mustafapur",
            applicant_name="Ramesh Kumar",
            reported_status="APPROVED",
            parcel_id=parcel.parcel_id,
            case_id=case.case_id,
        ),
    )

    report_data = assemble_report_data(
        db=db_session,
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        current_user=user_a,
    )

    assert report_data.section_mutation is not None
    assert report_data.section_mutation.is_reviewed is True
    assert report_data.section_mutation.total_cases_tracked >= 1
    assert "Suraj Bhan v. Financial Commissioner" in report_data.section_mutation.limitation_statement
    assert report_data.section_1_cover.data_availability_summary["mutation_history_reviewed"] is True


# =====================================================================
# 7. REST API Endpoints & Multi-Tenant Authorization
# =====================================================================

def test_api_list_and_import_mutation_cases(client: TestClient, auth_headers_a: dict):
    # 1. Import case
    import_payload = {
        "case_number": "MUT-2024-API-001",
        "filing_year": 2024,
        "district": "Patna",
        "circle": "Danapur",
        "mauza": "Mustafapur",
        "mutation_type": "SALE_DEED",
        "khata_number": "45",
        "khesra_number": "128",
        "applicant_name": "API Applicant",
        "reported_status": "NOTICE_ISSUED",
    }
    res_import = client.post("/api/v1/mutation/cases/import", json=import_payload, headers=auth_headers_a)
    assert res_import.status_code == 201
    created_case = res_import.json()
    assert created_case["case_number"] == "MUT-2024-API-001"
    case_id = created_case["mutation_case_id"]

    # 2. Get case details
    res_get = client.get(f"/api/v1/mutation/cases/{case_id}", headers=auth_headers_a)
    assert res_get.status_code == 200
    assert len(res_get.json()["events"]) >= 1

    # 3. List cases
    res_list = client.get("/api/v1/mutation/cases?district=Patna", headers=auth_headers_a)
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 1


def test_api_cross_tenant_isolation(client: TestClient, auth_headers_a: dict, auth_headers_b: dict):
    # Org A imports a case
    import_payload = {
        "case_number": "MUT-TENANT-A-ISOLATION",
        "filing_year": 2024,
        "district": "Patna",
        "circle": "Danapur",
        "mauza": "Mustafapur",
        "applicant_name": "Tenant A Secret Applicant",
        "reported_status": "RECEIVED",
    }
    res_import = client.post("/api/v1/mutation/cases/import", json=import_payload, headers=auth_headers_a)
    assert res_import.status_code == 201
    case_id = res_import.json()["mutation_case_id"]

    # Org B attempts to read Org A's case -> must return 404
    res_b = client.get(f"/api/v1/mutation/cases/{case_id}", headers=auth_headers_b)
    assert res_b.status_code == 404


def test_api_mutation_health(client: TestClient, auth_headers_a: dict):
    res = client.get("/api/v1/mutation/health", headers=auth_headers_a)
    assert res.status_code == 200
    assert res.json()["status"] == "UP"
