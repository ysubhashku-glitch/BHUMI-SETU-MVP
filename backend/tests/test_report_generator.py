import io
import uuid
import hashlib
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.case import Case, CaseStatus, TransactionReadinessState
from app.models.parcel import Parcel
from app.models.evidence import (
    Evidence,
    EvidenceType,
    AuthorityTier,
    CaseEvidence,
    Document,
    DocumentVersion,
    ExtractedField,
    ExtractedFieldStatus
)
from app.models.claim import Claim, ClaimPredicate
from app.models.field_task import FieldVerificationTask, TaskStatus, ReviewOutcome
from app.models.finding import Finding, FindingSeverity, FindingStatus
from app.models.report import LandIntelligenceReport, ReportStatus
from app.core.security import hash_password, create_access_token
from app.services.report_assembler import assemble_report_data
from app.services.pdf_report_generator import generate_land_intelligence_pdf

@pytest.fixture
def operator_a(db_session: Session, tenant_a: Organization) -> User:
    user = User(
        org_id=tenant_a.org_id,
        email="operator_report_a@bhumisetu.local",
        hashed_password=hash_password("Password123!"),
        full_name="DEMO_DATA: Case Operator A",
        phone_number="9800000070",
        role=UserRole.CASE_OPERATOR,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def operator_b(db_session: Session, tenant_b: Organization) -> User:
    user = User(
        org_id=tenant_b.org_id,
        email="operator_report_b@bhumisetu.local",
        hashed_password=hash_password("Password123!"),
        full_name="DEMO_DATA: Case Operator B",
        phone_number="9800000080",
        role=UserRole.CASE_OPERATOR,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def field_worker_a(db_session: Session, tenant_a: Organization) -> User:
    worker = User(
        org_id=tenant_a.org_id,
        email="amin_report_a@bhumisetu.local",
        hashed_password=hash_password("Password123!"),
        full_name="DEMO_DATA: Field Amin Ramesh",
        phone_number="9800000090",
        role=UserRole.FIELD_EXPERT,
        is_active=True
    )
    db_session.add(worker)
    db_session.commit()
    db_session.refresh(worker)
    return worker

@pytest.fixture
def headers_op_a(operator_a: User) -> dict:
    token = create_access_token(data={"sub": str(operator_a.user_id), "tenant_id": str(operator_a.org_id), "role": operator_a.role})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def headers_op_b(operator_b: User) -> dict:
    token = create_access_token(data={"sub": str(operator_b.user_id), "tenant_id": str(operator_b.org_id), "role": operator_b.role})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def headers_worker_a(field_worker_a: User) -> dict:
    token = create_access_token(data={"sub": str(field_worker_a.user_id), "tenant_id": str(field_worker_a.org_id), "role": field_worker_a.role})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def comprehensive_case(
    db_session: Session,
    tenant_a: Organization,
    client_party,
    field_worker_a: User
) -> tuple[Case, Parcel]:
    # 1. Case
    case = Case(
        org_id=tenant_a.org_id,
        case_number=f"BS-JH-2026-{uuid.uuid4().hex[:5].upper()}",
        primary_client_party_id=client_party.party_id,
        status=CaseStatus.PROCESSING,
        transaction_readiness_state=TransactionReadinessState.NOT_READY
    )
    db_session.add(case)
    db_session.flush()

    # 2. Parcel (P1-01 & P1-02)
    parcel = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id=f"JH-DEO-{uuid.uuid4().hex[:6]}",
        state_code="JH",
        district_name="Deoghar",
        subdistrict_anchal_name="Deoghar Sadar",
        mauza_village_name="Jasidih",
        census_village_code="256789",
        khata_number="48",
        plot_khesra_number="112",
        recorded_area_acres=2.5000,
        land_nature="Raiyati",
        authoritative_boundary="SRID=4326;POLYGON((86.69 24.51, 86.70 24.51, 86.70 24.52, 86.69 24.52, 86.69 24.51))"
    )
    db_session.add(parcel)
    db_session.flush()

    # Link CaseParcel
    from app.models.case import CaseParcel
    cp = CaseParcel(case_id=case.case_id, parcel_id=parcel.parcel_id, is_primary=True)
    db_session.add(cp)

    # 3. Evidence: Jamabandi record (P1-01)
    ev_jamabandi = Evidence(
        evidence_type=EvidenceType.GOVERNMENT_RECORD,
        authority_tier=AuthorityTier.REVENUE_RECORD,
        source_name="Bihar Bhumi Digital Jamabandi Register-II",
        storage_uri="mock://storage/jamabandi_sample.html",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    db_session.add(ev_jamabandi)
    db_session.flush()
    db_session.add(CaseEvidence(case_id=case.case_id, evidence_id=ev_jamabandi.evidence_id))

    # Claim for owner (P1-01)
    owner_claim = Claim(
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        evidence_id=ev_jamabandi.evidence_id,
        subject_entity_type="PARCEL",
        subject_id=parcel.parcel_id,
        predicate=ClaimPredicate.RECORDED_OWNER,
        object_value={"raiyat_name": "Ramchandra Mahto", "father_name": "Late Sitaram Mahto"},
        authority_tier=AuthorityTier.REVENUE_RECORD
    )
    db_session.add(owner_claim)

    # 4. Document & OCR fields (P1-03)
    doc = Document(
        org_id=tenant_a.org_id,
        document_category="SALE_DEED",
        original_filename="Registered_Kewala_1984_Plot112.pdf",
        mime_type="application/pdf",
        file_size_bytes=102400,
        storage_uri="mock://storage/deed.pdf",
        sha256_hash="01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b"
    )
    db_session.add(doc)
    db_session.flush()

    doc_version = DocumentVersion(
        document_id=doc.document_id,
        version_number=1,
        content_hash=doc.sha256_hash,
        storage_reference=doc.storage_uri,
        mime_type="application/pdf",
        file_size_bytes=102400,
        page_count=3,
        ocr_engine="Tesseract OCR 5.3"
    )
    db_session.add(doc_version)
    db_session.flush()

    # Extracted fields
    f_deed_no = ExtractedField(
        document_id=doc.document_id,
        version_id=doc_version.version_id,
        field_name="deed_number",
        raw_value="4812/1984",
        status=ExtractedFieldStatus.VALIDATED,
        confidence=0.98
    )
    f_plot = ExtractedField(
        document_id=doc.document_id,
        version_id=doc_version.version_id,
        field_name="plot_number",
        raw_value="112",
        status=ExtractedFieldStatus.VALIDATED,
        confidence=0.95
    )
    f_north = ExtractedField(
        document_id=doc.document_id,
        version_id=doc_version.version_id,
        field_name="boundary_north",
        raw_value="Shri Ramlal Sah",
        status=ExtractedFieldStatus.CANDIDATE,
        confidence=0.91
    )
    f_south = ExtractedField(
        document_id=doc.document_id,
        version_id=doc_version.version_id,
        field_name="boundary_south",
        raw_value="Irrigation Canal",
        status=ExtractedFieldStatus.VALIDATED,
        confidence=0.94
    )
    db_session.add_all([f_deed_no, f_plot, f_north, f_south])

    # 5. Field Task & Survey (P1-04)
    task = FieldVerificationTask(
        org_id=tenant_a.org_id,
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        task_number="FT-20261024-TEST01",
        title="Boundary & Possession Verification",
        reason="Field inspection",
        status=TaskStatus.REVIEW_ACCEPTED,
        priority="HIGH",
        assigned_amin_id=field_worker_a.user_id,
        visit_started_at=datetime.now(timezone.utc),
        visit_completed_at=datetime.now(timezone.utc),
        review_status=ReviewOutcome.ACCEPT,
        review_notes="Ground pillars verified. Possessor in active peaceful possession.",
        field_observations={
            "narrative_report": "Field boundary points surveyed along stone pillars. North neighbor Ramlal Sah confirmed boundary.",
            "measured_area_acres": 2.4800,
            "gps_points": [
                {"latitude": 24.5100, "longitude": 86.6900, "accuracy_meters": 2.8},
                {"latitude": 24.5107, "longitude": 86.6900, "accuracy_meters": 3.1}
            ],
            "ground_neighbors": {
                "north": "Shri Ramlal Sah",
                "south": "Irrigation Canal",
                "east": "Village Road",
                "west": "Devendra Yadav"
            },
            "road_access": {"road_type": "PUCCA_ROAD", "frontage_feet": 60.0},
            "physical_possessor": {"name": "Ramchandra Mahto"}
        },
        evidence_ids=[]
    )
    db_session.add(task)

    # 6. Finding
    finding = Finding(
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        rule_id="RULE_SPATIAL_AREA_CHECK",
        severity=FindingSeverity.INFORMATIONAL,
        status=FindingStatus.RESOLVED,
        observed_values={"recorded_acres": 2.50, "field_acres": 2.48, "delta_pct": -0.8},
        explanation="Area variance between revenue records and field survey is 0.8% (well within 5.0% threshold).",
        recommended_action="Title diligence verified."
    )
    db_session.add(finding)

    db_session.commit()
    db_session.refresh(case)
    db_session.refresh(parcel)
    return case, parcel


# =========================================================================
# A. Report Data Assembly Tests
# =========================================================================

def test_assemble_report_data_comprehensive(
    db_session: Session,
    comprehensive_case: tuple[Case, Parcel],
    operator_a: User
):
    case, parcel = comprehensive_case
    data = assemble_report_data(
        db=db_session,
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        current_user=operator_a
    )

    # Section 1
    assert data.section_1_cover.case_number == case.case_number
    assert data.section_1_cover.district == "Deoghar"
    assert data.section_1_cover.data_availability_summary["revenue_record_available"] is True
    assert data.section_1_cover.data_availability_summary["field_survey_available"] is True

    # Section 2
    assert data.section_2_revenue.is_available is True
    assert data.section_2_revenue.khata_number == "48"
    assert data.section_2_revenue.khesra_number == "112"
    assert data.section_2_revenue.recorded_area_acres == 2.5000
    assert "Ramchandra" in str(data.section_2_revenue.recorded_raiyat)

    # Section 3
    assert data.section_3_cadastral.is_available is True
    assert data.section_3_cadastral.geometry_validation_status == "VALID"

    # Section 4
    assert len(data.section_4_documents) >= 1
    doc_item = data.section_4_documents[0]
    assert doc_item.document_category == "SALE_DEED"
    assert doc_item.review_status == "UNREVIEWED_OCR"  # Had one CANDIDATE field
    assert doc_item.chauhaddi["south"] == "Irrigation Canal"

    # Section 5
    assert data.section_5_field.is_available is True
    assert data.section_5_field.measured_area_acres == 2.4800
    assert data.section_5_field.ground_chauhaddi["north"] == "Shri Ramlal Sah"
    assert data.section_5_field.physical_possessor_name == "Ramchandra Mahto"

    # Section 6
    assert len(data.section_6_consistency) >= 2
    categories = [c.category for c in data.section_6_consistency]
    assert "PLOT_IDENTIFIER" in categories
    assert "AREA_DIMENSION" in categories

    # Section 7
    assert len(data.section_7_evidence) >= 1

    # Section 8
    assert len(data.section_8_findings_actions) >= 1
    assert data.verification_url.startswith("https://")


def test_assemble_report_data_sparse_case(
    db_session: Session,
    tenant_a: Organization,
    client_party,
    operator_a: User
):
    # Case with no parcel, no documents, no field survey
    bare_case = Case(
        org_id=tenant_a.org_id,
        case_number=f"BS-BARE-{uuid.uuid4().hex[:4].upper()}",
        primary_client_party_id=client_party.party_id,
        status=CaseStatus.DRAFT
    )
    db_session.add(bare_case)
    db_session.commit()
    db_session.refresh(bare_case)

    data = assemble_report_data(
        db=db_session,
        case_id=bare_case.case_id,
        parcel_id=None,
        current_user=operator_a
    )

    assert data.section_1_cover.case_number == bare_case.case_number
    assert data.section_2_revenue.is_available is False
    assert data.section_3_cadastral.is_available is False
    assert len(data.section_4_documents) == 0
    assert data.section_5_field.is_available is False
    assert len(data.section_7_evidence) == 0


# =========================================================================
# B. PDF Rendering Tests
# =========================================================================

def test_generate_pdf_bytes_output(
    db_session: Session,
    comprehensive_case: tuple[Case, Parcel],
    operator_a: User
):
    case, parcel = comprehensive_case
    data = assemble_report_data(
        db=db_session,
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        current_user=operator_a
    )

    pdf_bytes = generate_land_intelligence_pdf(data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")  # Valid PDF Magic bytes header


def test_generate_pdf_with_property_passport_synthesis(
    db_session: Session,
    comprehensive_case: tuple[Case, Parcel],
    operator_a: User
):
    from app.schemas.report import (
        SectionSynthesisData,
        SectionDimensionScoreItem,
        SectionEvidenceGapItem,
        SectionFindingSummaryItem,
    )
    case, parcel = comprehensive_case
    data = assemble_report_data(
        db=db_session,
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        current_user=operator_a
    )

    # Attach synthesis data
    data.section_synthesis = SectionSynthesisData(
        is_synthesized=True,
        assessment_number="PASSPORT-2026-PAT-001",
        version_number=1,
        assessment_date="2026-10-27 12:00:00 UTC",
        overall_risk_tier="MEDIUM",
        composite_priority_score=36.50,
        dimension_scores=[
            SectionDimensionScoreItem(
                dimension="REVENUE_RECORD",
                dimension_name="Revenue Records & Jamabandi",
                score=10.0,
                weight=0.15,
                status="CONSISTENT",
                findings_count=0
            ),
            SectionDimensionScoreItem(
                dimension="CADASTRAL_SPATIAL",
                dimension_name="Cadastral Map & Boundary",
                score=45.0,
                weight=0.15,
                status="REQUIRES_REVIEW",
                findings_count=1
            ),
        ],
        top_findings=[
            SectionFindingSummaryItem(
                finding_id=str(uuid.uuid4()),
                dimension="CADASTRAL_SPATIAL",
                severity="MEDIUM",
                title="Boundary Displacement 1.8m",
                description="Minor discrepancy between historical CS map and modern survey",
                supporting_evidence=["Map Sheet 1910", "DILRMP Vector 2022"],
                review_status="PENDING_REVIEW"
            )
        ],
        evidence_gaps=[
            SectionEvidenceGapItem(
                gap_id=str(uuid.uuid4()),
                dimension="VALUATION_STATUTORY",
                gap_code="GAP-VAL-NO-ASSESSMENT",
                title="MVR Schedule Unavailable",
                description="No verified official circle rate schedule found for mauza",
                remedy_action="Upload verified Collectorate gazette notification"
            )
        ],
        facts_count=12,
        inferences_count=4,
        findings_count=1,
        gaps_count=1,
        sha256_snapshot_hash="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2"
    )

    pdf_bytes = generate_land_intelligence_pdf(data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1500
    assert pdf_bytes.startswith(b"%PDF-")


# =========================================================================
# C. End-to-End API Generation, Verification & Download Tests
# =========================================================================

def test_api_generate_report_success(
    client: TestClient,
    headers_op_a: dict,
    comprehensive_case: tuple[Case, Parcel]
):
    case, parcel = comprehensive_case
    payload = {
        "case_id": str(case.case_id),
        "parcel_id": str(parcel.parcel_id)
    }
    resp = client.post("/api/v1/reports/generate", json=payload, headers=headers_op_a)
    assert resp.status_code == 201
    data = resp.json()

    assert data["report_number"].startswith("LIR-")
    assert data["version_number"] == 1
    assert data["status"] == ReportStatus.GENERATED
    assert len(data["sha256_hash"]) == 64
    assert data["file_size_bytes"] > 0
    assert "download_url" in data
    assert "verification_url" in data


def test_api_report_versioning_increments(
    client: TestClient,
    headers_op_a: dict,
    comprehensive_case: tuple[Case, Parcel]
):
    case, parcel = comprehensive_case
    payload = {"case_id": str(case.case_id), "parcel_id": str(parcel.parcel_id)}

    # Version 1
    r1 = client.post("/api/v1/reports/generate", json=payload, headers=headers_op_a)
    assert r1.status_code == 201
    assert r1.json()["version_number"] == 1

    # Version 2
    r2 = client.post("/api/v1/reports/generate", json=payload, headers=headers_op_a)
    assert r2.status_code == 201
    assert r2.json()["version_number"] == 2

    # Check that previous report is marked SUPERSEDED
    old_id = r1.json()["report_id"]
    old_rep = client.get(f"/api/v1/reports/{old_id}", headers=headers_op_a)
    assert old_rep.status_code == 200
    assert old_rep.json()["status"] == ReportStatus.SUPERSEDED


def test_api_download_report_authorized(
    client: TestClient,
    headers_op_a: dict,
    comprehensive_case: tuple[Case, Parcel]
):
    case, parcel = comprehensive_case
    r = client.post("/api/v1/reports/generate", json={"case_id": str(case.case_id)}, headers=headers_op_a)
    report_id = r.json()["report_id"]

    download_resp = client.get(f"/api/v1/reports/{report_id}/download", headers=headers_op_a)
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == "application/pdf"
    assert "attachment" in download_resp.headers["content-disposition"]
    assert download_resp.content.startswith(b"%PDF-")


def test_api_public_qr_verification_endpoint(
    client: TestClient,
    headers_op_a: dict,
    db_session: Session,
    comprehensive_case: tuple[Case, Parcel]
):
    case, parcel = comprehensive_case
    r = client.post("/api/v1/reports/generate", json={"case_id": str(case.case_id)}, headers=headers_op_a)
    report_id = r.json()["report_id"]

    report_obj = db_session.query(LandIntelligenceReport).filter(LandIntelligenceReport.report_id == uuid.UUID(report_id)).first()
    token = report_obj.verification_token

    # Public unauthenticated request to verification endpoint
    verify_resp = client.get(f"/api/v1/reports/verify/{token}")
    assert verify_resp.status_code == 200
    v_data = verify_resp.json()

    assert v_data["is_authentic"] is True
    assert v_data["report_number"] == report_obj.report_number
    assert v_data["status"] == ReportStatus.GENERATED
    assert v_data["hash_matches_stored_file"] is True
    assert v_data["sha256_hash"] == report_obj.sha256_hash
    # Confirm private owner name is NOT leaked in public verification endpoint
    assert "Ramchandra Mahto" not in str(v_data)


def test_api_verification_invalid_token_returns_404(client: TestClient):
    resp = client.get(f"/api/v1/reports/verify/NON_EXISTENT_SECURITY_TOKEN")
    assert resp.status_code == 404


# =========================================================================
# D. Security & Tenant Isolation Tests
# =========================================================================

def test_cross_tenant_report_generation_denied(
    client: TestClient,
    headers_op_b: dict,
    comprehensive_case: tuple[Case, Parcel]
):
    case, parcel = comprehensive_case
    # Operator B (Tenant B) attempts to generate report for Tenant A's case
    payload = {"case_id": str(case.case_id)}
    resp = client.post("/api/v1/reports/generate", json=payload, headers=headers_op_b)
    assert resp.status_code == 403


def test_cross_tenant_report_download_denied(
    client: TestClient,
    headers_op_a: dict,
    headers_op_b: dict,
    comprehensive_case: tuple[Case, Parcel]
):
    case, parcel = comprehensive_case
    # Operator A generates report
    r = client.post("/api/v1/reports/generate", json={"case_id": str(case.case_id)}, headers=headers_op_a)
    report_id = r.json()["report_id"]

    # Operator B attempts to download report
    resp = client.get(f"/api/v1/reports/{report_id}/download", headers=headers_op_b)
    assert resp.status_code == 403


def test_unauthorized_role_cannot_generate_report(
    client: TestClient,
    headers_worker_a: dict,
    comprehensive_case: tuple[Case, Parcel]
):
    case, parcel = comprehensive_case
    # Field worker cannot generate final Land Intelligence Reports
    resp = client.post("/api/v1/reports/generate", json={"case_id": str(case.case_id)}, headers=headers_worker_a)
    assert resp.status_code == 403
