import io
import os
import uuid
import json
import hashlib
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.models.base import utc_now
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.party import Party, PartyType
from app.models.case import Case, CaseStatus, CaseParcel
from app.models.parcel import Parcel
from app.models.evidence import (
    Evidence,
    EvidenceType,
    AuthorityTier,
    CaseEvidence,
    Document,
    DocumentCategory,
    DocumentVersion,
    DocumentProcessingStatus,
    ExtractedField,
    ExtractedFieldStatus
)
from app.models.claim import Claim, ClaimPredicate, ClaimStatus
from app.models.finding import Finding, FindingStatus, FindingSeverity, RequiredAction, ActionStatus
from app.models.field_task import FieldVerificationTask, TaskStatus, TaskPriority, ReviewOutcome
from app.models.field_survey import FieldSurvey
from app.models.report import LandIntelligenceReport, ReportStatus
from app.models.audit import AuditLog
from app.core.security import create_access_token, hash_password
from app.core.storage import get_document_storage
from app.services.scrapers.bhunaksha import (
    validate_and_normalize_geometry,
    BiharBhuNakshaAdapter,
    RevenueMapComparisonRequest,
    BhuNakshaPlotRecord,
    GeometryValidationResult
)
from app.services.document_pipeline import DocumentPipelineService
from app.services.amin_service import (
    create_field_verification_task,
    assign_field_task,
    accept_field_task,
    start_field_visit,
    upload_field_photo_evidence,
    submit_field_report,
    review_field_report
)
from app.schemas.field_task import (
    TaskCreateRequest,
    TaskAssignRequest,
    FieldReportSubmitRequest,
    TaskReviewRequest
)
from app.schemas.report import ReportGenerateRequest
from app.services.report_service import (
    generate_and_store_report,
    verify_report_by_token
)
from app.mcp.tools import (
    execute_get_parcel_summary,
    execute_get_revenue_record_summary,
    execute_get_spatial_summary,
    execute_get_document_extraction_summary,
    execute_get_evidence_register,
    execute_get_consistency_findings,
    execute_get_field_verification_status,
    execute_create_field_verification_request,
    execute_get_report_metadata,
    execute_generate_land_intelligence_report,
    execute_verify_report_integrity
)
from app.mcp.auth import authenticate_mcp_request
from app.core.exceptions import ForbiddenError, CrossTenantAccessError


def test_p1_end_to_end_system_integration_audit(db_session: Session):
    """
    TASK-P1-07 End-to-End Vertical-Slice Integration Audit.
    Exercises the complete 16-step workflow connecting P1-01 through P1-06.
    Deliberately introduces a legitimate area discrepancy (Jamabandi 1.50 Ac vs Cadastral 1.20 Ac)
    and verifies that the entire system identifies, reports, verifies in the field,
    assembles into a report, and exposes via MCP without silently masking it.
    """
    storage = get_document_storage()

    # =========================================================================
    # Step 1: Create Isolated Test Organizations & Users
    # =========================================================================
    org_a = Organization(name="Audit Tenant Alpha", slug="audit-tenant-alpha")
    org_b = Organization(name="Audit Tenant Beta (Adversary)", slug="audit-tenant-beta")
    db_session.add_all([org_a, org_b])
    db_session.commit()

    # Tenant A Users
    user_op_a = User(
        org_id=org_a.org_id,
        email="operator.a@bhumisetu.audit",
        hashed_password=hash_password("AuditPass123!"),
        full_name="Alpha Case Operator",
        phone_number="9876543210",
        role=UserRole.CASE_OPERATOR,
        is_active=True
    )
    user_amin_a = User(
        org_id=org_a.org_id,
        email="amin.a@bhumisetu.audit",
        hashed_password=hash_password("AuditPass123!"),
        full_name="Ramesh Amin (Licensed Field Worker)",
        phone_number="9876543211",
        role=UserRole.FIELD_EXPERT,
        is_active=True
    )
    user_rev_a = User(
        org_id=org_a.org_id,
        email="reviewer.a@bhumisetu.audit",
        hashed_password=hash_password("AuditPass123!"),
        full_name="Suresh Advocate (Legal Reviewer)",
        phone_number="9876543212",
        role=UserRole.LEGAL_REVIEWER,
        is_active=True
    )
    user_view_a = User(
        org_id=org_a.org_id,
        email="viewer.a@bhumisetu.audit",
        hashed_password=hash_password("AuditPass123!"),
        full_name="Client Viewer",
        phone_number="9876543213",
        role="CLIENT_VIEWER",
        is_active=True
    )

    # Tenant B User (for cross-tenant tests)
    user_op_b = User(
        org_id=org_b.org_id,
        email="operator.b@bhumisetu.audit",
        hashed_password=hash_password("AuditPass123!"),
        full_name="Beta Adversary Operator",
        phone_number="9876543299",
        role=UserRole.CASE_OPERATOR,
        is_active=True
    )

    db_session.add_all([user_op_a, user_amin_a, user_rev_a, user_view_a, user_op_b])
    db_session.commit()

    # Generate Auth Tokens
    token_op_a = create_access_token(data={"sub": str(user_op_a.user_id), "tid": str(org_a.org_id), "role": user_op_a.role})
    token_amin_a = create_access_token(data={"sub": str(user_amin_a.user_id), "tid": str(org_a.org_id), "role": user_amin_a.role})
    token_rev_a = create_access_token(data={"sub": str(user_rev_a.user_id), "tid": str(org_a.org_id), "role": user_rev_a.role})
    token_view_a = create_access_token(data={"sub": str(user_view_a.user_id), "tid": str(org_a.org_id), "role": user_view_a.role})
    token_op_b = create_access_token(data={"sub": str(user_op_b.user_id), "tid": str(org_b.org_id), "role": user_op_b.role})

    # Client Party
    client_party = Party(
        org_id=org_a.org_id,
        primary_name="Anupama Devi",
        party_type=PartyType.PERSON,
        phone_number="9123456789"
    )
    db_session.add(client_party)
    db_session.commit()

    # Case & Parcel
    case = Case(
        org_id=org_a.org_id,
        case_number="CAS-AUDIT-2026-001",
        primary_client_party_id=client_party.party_id,
        status=CaseStatus.PROPERTY_IDENTIFIED
    )
    parcel = Parcel(
        org_id=org_a.org_id,
        bhumi_id="BR-PAT-DAN-KOT-KH42-PL112A",
        state_code="BR",
        district_name="Patna",
        subdistrict_anchal_name="Danapur",
        mauza_village_name="Kothawan",
        census_village_code="245000",
        khata_number="42",
        plot_khesra_number="112/A",
        recorded_area_acres=1.50,  # 1.50 Acres recorded in Jamabandi
        land_nature="AGRICULTURAL_RAIYATI"
    )
    db_session.add_all([case, parcel])
    db_session.commit()

    case_parcel = CaseParcel(case_id=case.case_id, parcel_id=parcel.parcel_id, is_primary=True)
    db_session.add(case_parcel)
    db_session.commit()

    # =========================================================================
    # Step 2: Ingest Synthetic Revenue Record (P1-01)
    # =========================================================================
    jamabandi_raw = {
        "state": "Bihar",
        "district": "Patna",
        "circle": "Danapur",
        "mauza": "Kothawan",
        "khata": "42",
        "plot": "112/A",
        "jamabandi_number": "JB-420",
        "raiyat_name": "Ram Kumar Verma",
        "father_husband_name": "Late Shyam Verma",
        "recorded_area_original": "1 Acre 50 Decimal",
        "recorded_area_acres": 1.50,
        "recorded_area_sqm": 6070.28,
        "lagan": "Rs. 24.50"
    }
    raw_payload_bytes = json.dumps(jamabandi_raw).encode("utf-8")
    jamabandi_sha256 = hashlib.sha256(raw_payload_bytes).hexdigest()

    ev_storage = storage.put(
        content=raw_payload_bytes,
        destination_name=f"revenue_{parcel.bhumi_id}.json",
        mime_type="application/json",
        metadata={"source": "emutation.bihar.gov.in", "parcel_id": str(parcel.parcel_id)}
    )

    revenue_evidence = Evidence(
        evidence_type=EvidenceType.GOVERNMENT_RECORD,
        authority_tier=AuthorityTier.REVENUE_RECORD,
        source_name="Bihar Bhumi Digital Jamabandi Register-II",
        storage_uri=ev_storage["storage_reference"],
        sha256_hash=jamabandi_sha256,
        evidence_metadata=jamabandi_raw
    )
    db_session.add(revenue_evidence)
    db_session.flush()

    db_session.add(CaseEvidence(case_id=case.case_id, evidence_id=revenue_evidence.evidence_id))
    
    claim_owner = Claim(
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        evidence_id=revenue_evidence.evidence_id,
        subject_entity_type="PARCEL",
        subject_id=parcel.parcel_id,
        predicate=ClaimPredicate.RECORDED_OWNER,
        object_value={"raiyat_name": "Ram Kumar Verma", "jamabandi_no": "JB-420"},
        authority_tier=AuthorityTier.REVENUE_RECORD,
        confidence_score=1.0,
        status=ClaimStatus.ACTIVE
    )
    db_session.add(claim_owner)
    db_session.commit()

    # =========================================================================
    # Step 3: Associate Cadastral Geometry with Explicit CRS (P1-02)
    # Deliberate Legitimate Discrepancy: Mapped geometry area is 1.20 Acres (~20% deficit vs 1.50 Ac)
    # =========================================================================
    # Construct a WGS84 polygon in Patna (around 85.04E, 25.61N) with area ~ 1.20 Acres (approx 4856 sqm)
    # 1 deg lat ~ 110800m, 1 deg lon ~ 100400m in Patna.
    # A box of delta_lat ~ 0.00062 deg and delta_lon ~ 0.00071 deg is ~ 68.7m x 71.3m ~ 4900 sqm ~ 1.21 Acres
    min_lon, min_lat = 85.0420, 25.6120
    max_lon, max_lat = 85.04271, 25.61262
    cadastral_wkt = f"POLYGON(({min_lon} {min_lat}, {max_lon} {min_lat}, {max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))"
    
    geom, validation = validate_and_normalize_geometry(
        raw_geom=cadastral_wkt,
        crs="EPSG:4326",
        allow_repair=True
    )
    assert validation.is_valid is True
    assert validation.crs == "EPSG:4326"
    assert 1.15 <= validation.calculated_area_acres <= 1.25

    parcel.authoritative_boundary = cadastral_wkt
    parcel.centroid_point = f"POINT({validation.centroid[0]} {validation.centroid[1]})"
    db_session.commit()

    # =========================================================================
    # Step 4 & 5: Upload Land Document & Execute OCR Pipeline (P1-03)
    # =========================================================================
    deed_text = (
        "%PDF-1.4\n"
        "REGISTERED SALE DEED / बैनामा\n"
        "District: Patna, Circle: Danapur, Mauza: Kothawan (Thana No: 245)\n"
        "Khata No: 42, Plot / Khesra No: 112/A, Area: 1.50 Acre (150 Decimal)\n"
        "Seller (विक्रेता): Ram Kumar Verma, S/o Late Shyam Verma\n"
        "Buyer (क्रेता): Anupama Devi, W/o Rajesh Sharma\n"
        "Deed No: 8842/2021, Registration Date: 12-10-2021, Consideration: Rs 35,00,000\n"
        "Chauhadri / Boundaries:\n"
        "North: Nij plot of seller (Plot 111)\n"
        "South: PWD 20ft Main Road\n"
        "East: Plot 113 of Binod Roy\n"
        "West: Irrigation Canal / Nala\n"
        "%%EOF\n"
    )
    deed_bytes = deed_text.encode("utf-8")
    deed_storage = storage.put(
        content=deed_bytes,
        destination_name="sale_deed_8842.pdf",
        mime_type="application/pdf",
        metadata={"case_id": str(case.case_id)}
    )

    deed_sha256 = hashlib.sha256(deed_bytes).hexdigest()
    doc = Document(
        org_id=org_a.org_id,
        document_category=DocumentCategory.SALE_DEED,
        original_filename="sale_deed_8842.pdf",
        mime_type="application/pdf",
        file_size_bytes=len(deed_bytes),
        storage_uri=deed_storage["storage_reference"],
        sha256_hash=deed_sha256
    )
    db_session.add(doc)
    db_session.flush()

    doc_version = DocumentVersion(
        document_id=doc.document_id,
        version_number=1,
        file_size_bytes=len(deed_bytes),
        mime_type="application/pdf",
        storage_reference=deed_storage["storage_reference"],
        content_hash=deed_sha256,
        processing_status=DocumentProcessingStatus.UPLOADED
    )
    db_session.add(doc_version)
    db_session.commit()

    # Execute Document Pipeline
    proc_version = DocumentPipelineService.execute_pipeline(
        document_id=doc.document_id,
        version_id=doc_version.version_id,
        db=db_session,
        case_id=case.case_id
    )
    assert proc_version.processing_status in (
        DocumentProcessingStatus.READY,
        DocumentProcessingStatus.VALIDATION_REQUIRED,
        DocumentProcessingStatus.EXTRACTION_COMPLETE
    )
    assert proc_version.page_count >= 1

    extracted_fields = db_session.query(ExtractedField).filter(
        ExtractedField.version_id == doc_version.version_id
    ).all()
    assert len(extracted_fields) > 0

    # =========================================================================
    # Step 6: Cross-Source Consistency Checks (Detect Legitimate Area Deficit)
    # =========================================================================
    plot_record = BhuNakshaPlotRecord(
        district_name="Patna",
        district_code="28",
        circle_name="Danapur",
        mauza_name="Kothawan",
        khesra_plot_number="112/A",
        khata_number="42",
        geometry_geojson={"type": "Polygon", "coordinates": [[[min_lon, min_lat], [max_lon, min_lat], [max_lon, max_lat], [min_lon, max_lat], [min_lon, min_lat]]]},
        geometry_wkt=cadastral_wkt,
        crs="EPSG:4326",
        validation=validation,
        sha256_hash=hashlib.sha256(cadastral_wkt.encode()).hexdigest()
    )

    bhunaksha_adapter = BiharBhuNakshaAdapter()
    comparison = bhunaksha_adapter.compare_cadastral_to_revenue(
        cadastral_record=plot_record,
        jamabandi_recorded_area_acres=1.50,
        jamabandi_khesra_number="112/A",
        jamabandi_khata_number="42"
    )
    assert comparison.identifiers_matched is True
    assert comparison.status == "AREA_DISCREPANCY"
    assert comparison.area_delta_pct is not None
    assert abs(comparison.area_delta_pct) > 15.0  # ~19.5% discrepancy

    # Create Discrepancy Finding and Action
    finding = Finding(
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        rule_id="RULE-AREA-DEFICIT",
        severity=FindingSeverity.HIGH,
        status=FindingStatus.OPEN,
        observed_values={
            "revenue_area_acres": 1.50,
            "cadastral_mapped_acres": round(validation.calculated_area_acres, 4),
            "delta_percentage": comparison.area_delta_pct
        },
        explanation=(
            f"Cadastral vector map shows {validation.calculated_area_acres:.2f} Acres, "
            f"representing a significant deficit against the 1.50 Acres recorded in Register-II Jamabandi."
        ),
        recommended_action="Dispatch field verification amin to measure ground physical possession boundary."
    )
    db_session.add(finding)
    db_session.flush()

    action = RequiredAction(
        finding_id=finding.finding_id,
        case_id=case.case_id,
        action_type="FIELD_SURVEY_VERIFICATION",
        assigned_role="FIELD_EXPERT",
        status=ActionStatus.OPEN
    )
    db_session.add(action)
    db_session.commit()

    # =========================================================================
    # Step 7 & 8: Create Field Task & Permitted State Transitions (P1-04)
    # =========================================================================
    task_req = TaskCreateRequest(
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        finding_id=finding.finding_id,
        action_id=action.action_id,
        title="Verify ground boundary and possessor for Plot 112/A area deficit",
        reason="Cadastral map area deficit vs Jamabandi revenue record",
        priority=TaskPriority.HIGH,
        required_activities=["MEASURE_GROUND_AREA", "VERIFY_CHAUHADDI", "INTERVIEW_POSSESSOR"]
    )
    field_task = create_field_verification_task(db_session, task_req, user_op_a)
    assert field_task.status == TaskStatus.READY_FOR_ASSIGNMENT

    # Assign -> Accepted -> In Progress
    field_task = assign_field_task(
        db_session,
        field_task.task_id,
        TaskAssignRequest(amin_user_id=user_amin_a.user_id),
        user_op_a
    )
    assert field_task.status == TaskStatus.ASSIGNED

    field_task = accept_field_task(db_session, field_task.task_id, user_amin_a)
    assert field_task.status == TaskStatus.ACCEPTED

    field_task = start_field_visit(db_session, field_task.task_id, user_amin_a)
    assert field_task.status == TaskStatus.IN_PROGRESS

    # =========================================================================
    # Step 9: Field Observations & Test Image Evidence
    # =========================================================================
    # Upload authentic JPEG photo
    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00" + b"\x00" * 80 + b"\xff\xc0\x00\x11\x08\x00\x10\x00\x10\x03\x01\x22\x00\xff\xda\x00\x0c\x03\x01\x00\x00\x3f\x00\xff\xd9"
    photo_ev = upload_field_photo_evidence(
        db=db_session,
        task_id=field_task.task_id,
        file_bytes=jpeg_bytes,
        filename="ground_corner_peg.jpg",
        declared_mime="image/jpeg",
        current_user=user_amin_a,
        latitude=25.6122,
        longitude=85.0423,
        accuracy_meters=1.5
    )
    assert photo_ev.sha256_hash is not None

    # Submit Field Report with GPS Polygon matching ~1.22 Acres
    gps_coords = [
        [min_lon, min_lat],
        [max_lon, min_lat],
        [max_lon, max_lat],
        [min_lon, max_lat],
        [min_lon, min_lat]
    ]
    report_submit_payload = FieldReportSubmitRequest(
        field_observations={
            "measured_area_acres": 1.21,
            "boundary_points": gps_coords,
            "average_gnss_accuracy_meters": 1.5,
            "ground_neighbors": {
                "north": "Plot 111 (Sugarcane field of Ram Kumar)",
                "south": "PWD 20ft road (matches deed)",
                "east": "Plot 113 of Binod Roy",
                "west": "Irrigation Nala (encroachment observed on western ridge)"
            },
            "road_access": {
                "has_road_access": True,
                "road_type": "TAR_PAVED",
                "frontage_width_feet": 45.0
            },
            "physical_possessor": {
                "name": "Ram Kumar Verma",
                "possession_type": "AGRICULTURAL_CULTIVATION",
                "years_in_possession": 25
            }
        },
        narrative_report=(
            "Completed boundary walk. Ground ridge (aal) measurements align with Cadastral map (~1.21 Acres). "
            "Western 0.29 Acre area appears occupied by government irrigation canal widening done in 1998, "
            "explaining the shortfall against the 1.50 Acres recorded in old Jamabandi."
        )
    )
    field_task = submit_field_report(db_session, field_task.task_id, report_submit_payload, user_amin_a)
    assert field_task.status == TaskStatus.SUBMITTED

    # =========================================================================
    # Step 10: Reviewer Evaluation (Conflict of Interest Check & Acceptance)
    # =========================================================================
    # Negative Test: Amin user cannot evaluate their own task
    with pytest.raises(ForbiddenError):
        review_field_report(
            db_session,
            field_task.task_id,
            TaskReviewRequest(outcome=ReviewOutcome.ACCEPT, review_notes="Self-approval attempt"),
            user_amin_a
        )

    # Positive Test: Legal Reviewer accepts report and auto-resolves finding action
    field_task = review_field_report(
        db_session,
        field_task.task_id,
        TaskReviewRequest(
            outcome=ReviewOutcome.ACCEPT,
            review_notes="Field investigation accepted. Canal widening confirmed as reason for area deficit.",
            create_field_survey_record=True
        ),
        user_rev_a
    )
    assert field_task.status == TaskStatus.REVIEW_ACCEPTED
    assert field_task.survey_id is not None

    db_session.refresh(action)
    assert action.status == ActionStatus.COMPLETED

    # =========================================================================
    # Step 11 & 12: Generate Land Intelligence Report & Verify Integrity (P1-05)
    # =========================================================================
    gen_report = generate_and_store_report(
        db=db_session,
        request=ReportGenerateRequest(case_id=case.case_id, parcel_id=parcel.parcel_id),
        current_user=user_rev_a
    )
    assert gen_report.report_number.startswith("LIR-")
    assert gen_report.status == ReportStatus.GENERATED
    assert len(gen_report.sha256_hash) == 64
    assert gen_report.verification_token is not None

    # Cryptographic Verification of untouched PDF
    v_result = verify_report_by_token(db=db_session, token=gen_report.verification_token)
    assert v_result.is_authentic is True
    assert v_result.hash_matches_stored_file is True
    assert v_result.report_number == gen_report.report_number

    # Tamper Simulation Test: Altering 1 byte in stored file causes cryptographic verification failure
    pdf_bytes = storage.get(gen_report.pdf_storage_uri)
    tampered_bytes = pdf_bytes + b"\x00TAMPERED"
    target_storage_path = storage._get_path_from_ref(gen_report.pdf_storage_uri)
    with open(target_storage_path, "wb") as f:
        f.write(tampered_bytes)

    v_tampered = verify_report_by_token(db=db_session, token=gen_report.verification_token)
    assert v_tampered.is_authentic is False
    assert v_tampered.hash_matches_stored_file is False

    # Restore original bytes
    with open(target_storage_path, "wb") as f:
        f.write(pdf_bytes)

    # =========================================================================
    # Step 13: Governed MCP Tool Retrieval (P1-06)
    # =========================================================================
    # 1. Parcel Summary
    p_sum = execute_get_parcel_summary(db=db_session, parcel_id=str(parcel.parcel_id), auth_token=token_op_a)
    assert p_sum.success is True
    assert p_sum.data["parcel_id"] == str(parcel.parcel_id)
    assert p_sum.data["open_discrepancies_count"] == 0  # Discrepancy finding was resolved by task review acceptance
    assert p_sum.data["field_verification_status"] == TaskStatus.REVIEW_ACCEPTED
    assert "clear title" not in p_sum.disclaimer.lower() or "does not" in p_sum.disclaimer.lower()

    # 2. Revenue Summary
    r_sum = execute_get_revenue_record_summary(db=db_session, parcel_id=str(parcel.parcel_id), auth_token=token_op_a)
    assert r_sum.success is True
    assert r_sum.data["khata_number"] == "42"
    assert r_sum.data["plot_khesra_number"] == "112/A"
    assert r_sum.data["recorded_area_acres"] == 1.50

    # 3. Spatial Summary
    s_sum = execute_get_spatial_summary(db=db_session, parcel_id=str(parcel.parcel_id), auth_token=token_op_a)
    assert s_sum.success is True
    assert s_sum.data["geometry_available"] is True
    assert "EPSG:4326" in s_sum.data["crs"]

    # 4. Document Extraction Summary
    d_sum = execute_get_document_extraction_summary(db=db_session, case_id=str(case.case_id), auth_token=token_op_a)
    assert d_sum.success is True
    assert d_sum.data["documents_count"] >= 1

    # 5. Evidence Register
    e_sum = execute_get_evidence_register(db=db_session, case_id=str(case.case_id), auth_token=token_op_a)
    assert e_sum.success is True
    assert e_sum.data["evidence_count"] >= 2
    # Ensure raw private storage paths are omitted
    for ev in e_sum.data["evidence_items"]:
        assert "storage_uri" not in ev

    # 6. Consistency Findings
    f_sum = execute_get_consistency_findings(db=db_session, case_id=str(case.case_id), auth_token=token_op_a)
    assert f_sum.success is True
    assert f_sum.data["findings_count"] >= 1
    assert any("AREA" in item["rule_id"] for item in f_sum.data["findings"])

    # 7. Field Verification Status
    fv_sum = execute_get_field_verification_status(db=db_session, case_id=str(case.case_id), auth_token=token_op_a)
    assert fv_sum.success is True
    assert fv_sum.data["tasks_count"] >= 1
    assert fv_sum.data["tasks"][0]["status"] == TaskStatus.REVIEW_ACCEPTED

    # 8. Report Metadata
    rm_sum = execute_get_report_metadata(db=db_session, report_id=str(gen_report.report_id), auth_token=token_op_a)
    assert rm_sum.success is True
    assert rm_sum.data["reports_count"] == 1
    assert rm_sum.data["reports"][0]["sha256_hash"] == gen_report.sha256_hash

    # 9. Verify Report Integrity (Public Tool)
    vi_sum = execute_verify_report_integrity(db=db_session, verification_token=gen_report.verification_token)
    assert vi_sum.success is True
    assert vi_sum.data["is_valid"] is True
    assert vi_sum.data["hash_matches_stored_file"] is True

    # =========================================================================
    # Step 14: Attempt Unauthorized Cross-Tenant Access
    # =========================================================================
    # Tenant B tries to query Tenant A's parcel
    cross_p = execute_get_parcel_summary(db=db_session, parcel_id=str(parcel.parcel_id), auth_token=token_op_b)
    assert cross_p.success is False
    assert cross_p.error["code"] in ("CROSS_TENANT_ACCESS", "CROSS_TENANT_ACCESS_DENIED", "NOT_FOUND", "ENTITY_NOT_FOUND")

    # Tenant B tries to access Tenant A's evidence
    cross_e = execute_get_evidence_register(db=db_session, case_id=str(case.case_id), auth_token=token_op_b)
    assert cross_e.success is False
    assert cross_e.error["code"] in ("CROSS_TENANT_ACCESS", "CROSS_TENANT_ACCESS_DENIED", "NOT_FOUND", "ENTITY_NOT_FOUND")

    # =========================================================================
    # Step 15: Attempt State-Changing Actions Using Unauthorized Role
    # =========================================================================
    # CLIENT_VIEWER attempts to generate a report
    unauth_gen = execute_generate_land_intelligence_report(
        db=db_session,
        case_id=str(case.case_id),
        parcel_id=str(parcel.parcel_id),
        auth_token=token_view_a
    )
    assert unauth_gen.success is False
    assert unauth_gen.error["code"] in ("FORBIDDEN", "PERMISSION_DENIED", "GENERATION_FAILED")
    assert "not authorized" in unauth_gen.error["message"].lower()

    # CLIENT_VIEWER attempts to create a field task
    unauth_task = execute_create_field_verification_request(
        db=db_session,
        case_id=str(case.case_id),
        parcel_id=str(parcel.parcel_id),
        title="Unauthorized task attempt",
        reason="Testing RBAC",
        auth_token=token_view_a
    )
    assert unauth_task.success is False
    assert unauth_task.error["code"] in ("FORBIDDEN", "PERMISSION_DENIED", "MUTATION_FAILED")
    assert "not authorized" in unauth_task.error["message"].lower()

    # =========================================================================
    # Step 16: Confirm Audit Log Integrity
    # =========================================================================
    audits = db_session.query(AuditLog).filter(AuditLog.org_id == org_a.org_id).all()
    actions = [a.action for a in audits]
    assert "REVIEW_FIELD_REPORT" in actions
    assert "GENERATE_LAND_REPORT" in actions
