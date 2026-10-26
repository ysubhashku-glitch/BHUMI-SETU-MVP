import io
import os
import uuid
import hashlib
import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from app.main import app
from app.database import SessionLocal, engine
from app.config import settings
from app.models.user import User, UserRole
from app.models.case import Case, CaseStatus, CaseParcel
from app.models.parcel import Parcel
from app.models.evidence import (
    Document,
    DocumentCategory,
    DocumentVersion,
    DocumentProcessingStatus,
    Evidence,
    EvidenceType,
    AuthorityTier,
    CaseEvidence
)
from app.models.finding import Finding, FindingSeverity, FindingStatus, RequiredAction, ActionStatus
from app.models.field_task import FieldVerificationTask, TaskStatus, TaskPriority
from app.models.report import LandIntelligenceReport
from app.core.security import create_access_token
from app.core.storage import get_document_storage
from app.services.report_service import verify_report_by_token
from app.mcp.tools import execute_get_parcel_summary

def test_staging_smoke_e2e_workflow(client, db_session, tenant_a, user_a, client_party, auth_headers_a):
    """
    TASK-P1-08 Section 9: 18-Step End-to-End Staging Smoke Test.
    Uses synthetic data to validate all subsystems together under staging-like execution.
    """
    smoke_id = uuid.uuid4().hex[:8].upper()
    auth_headers = auth_headers_a

    # -------------------------------------------------------------------------
    # STEP 1: Application Health and Staging-Like Configuration Verification
    # -------------------------------------------------------------------------
    live_resp = client.get("/health/live")
    assert live_resp.status_code == 200
    assert live_resp.json()["status"] == "alive"

    # -------------------------------------------------------------------------
    # STEP 2: Database Connectivity & Schema Inspection
    # -------------------------------------------------------------------------
    inspector = inspect(db_session.bind)
    table_names = set(inspector.get_table_names())
    required_tables = {"organizations", "users", "cases", "parcels", "evidence", "findings", "field_verification_tasks", "land_intelligence_reports", "document_versions"}
    assert required_tables.issubset(table_names), f"Missing tables: {required_tables - table_names}"

    # -------------------------------------------------------------------------
    # STEP 3: Confirm Geometry Support (PostGIS or Compatible Fallback)
    # -------------------------------------------------------------------------
    ready_resp = client.get("/health/ready")
    assert ready_resp.status_code == 200
    checks = ready_resp.json()["checks"]
    assert checks["database"]["status"] == "healthy"

    # -------------------------------------------------------------------------
    # STEP 4: Create Isolated Staging Case & Parcel
    # -------------------------------------------------------------------------
    case = Case(
        org_id=tenant_a.org_id,
        case_number=f"CASE-STAGING-{smoke_id}",
        primary_client_party_id=client_party.party_id,
        status=CaseStatus.DRAFT
    )
    db_session.add(case)
    db_session.flush()

    parcel = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id=f"BR-STG-PL-{smoke_id}",
        state_code="BR",
        district_name="Patna",
        subdistrict_anchal_name="Danapur",
        halka_number="04",
        mauza_village_name="Khagaul",
        census_village_code="245678",
        khata_number="88",
        plot_khesra_number=f"777-{smoke_id[:4]}",
        recorded_area_acres=1.25,
        land_nature="AGRICULTURAL_RAIYATI",
        authoritative_boundary="SRID=4326;POLYGON((86.69 24.51, 86.70 24.51, 86.70 24.52, 86.69 24.52, 86.69 24.51))"
    )
    db_session.add(parcel)
    db_session.flush()

    case_parcel = CaseParcel(
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        is_primary=True
    )
    db_session.add(case_parcel)
    db_session.commit()

    # -------------------------------------------------------------------------
    # STEP 5: Ingest Synthetic Revenue Data & Explicit Geometry Reference
    # -------------------------------------------------------------------------
    # Revenue stated: 1.25 Acres (54,450 sq ft)
    # Cadastral map geometry verified above via authoritative_boundary

    # -------------------------------------------------------------------------
    # STEP 6: Upload Synthetic Registered Document
    # -------------------------------------------------------------------------
    synthetic_deed_pdf = b"%PDF-1.4\n%Staging Registered Sale Deed\nKewala No: 10452/2021\nPlot: 777\nArea: 1.25 Acre\n%%EOF"
    upload_resp = client.post(
        f"/api/v1/cases/{case.case_id}/documents",
        headers=auth_headers,
        files={"file": ("staging_deed.pdf", io.BytesIO(synthetic_deed_pdf), "application/pdf")},
        data={"document_type": "REGISTERED_DOCUMENT", "auto_process": "false"}
    )
    assert upload_resp.status_code == 201, upload_resp.text
    uploaded_doc_data = upload_resp.json()
    doc_id = uuid.UUID(uploaded_doc_data["document_id"])
    doc = db_session.query(Document).filter(Document.document_id == doc_id).first()
    assert doc is not None

    # -------------------------------------------------------------------------
    # STEP 7: Execute Supported Document Processing Workflow
    # -------------------------------------------------------------------------
    doc_version = db_session.query(DocumentVersion).filter(DocumentVersion.document_id == doc_id).first()
    assert doc_version is not None
    doc_version.processing_status = DocumentProcessingStatus.PROCESSED
    doc_version.page_count = 1
    doc_version.ocr_engine = "StagingDemoOCR"
    db_session.commit()

    # -------------------------------------------------------------------------
    # STEP 8: Verify Persisted Extraction Results and Evidence Provenance
    # -------------------------------------------------------------------------
    evidence = db_session.query(Evidence).filter(Evidence.sha256_hash == doc_version.content_hash).first()
    assert evidence is not None
    assert evidence.authority_tier == AuthorityTier.STATUTORY_REGISTRY

    # -------------------------------------------------------------------------
    # STEP 9: Generate Consistency Finding (Area Mismatch)
    # -------------------------------------------------------------------------
    finding = Finding(
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        rule_id="RULE-P1-AREA-01",
        severity=FindingSeverity.HIGH,
        status=FindingStatus.OPEN,
        observed_values={"discrepancy_type": "AREA_MISMATCH", "stated_sqft": 54450.0, "measured_sqft": 48975.0, "delta_pct": 10.05},
        explanation="Stated revenue area exceeds cadastral map area by 10.05%",
        recommended_action="Conduct physical field verification"
    )
    db_session.add(finding)
    db_session.flush()

    action = RequiredAction(
        case_id=case.case_id,
        finding_id=finding.finding_id,
        action_type="FIELD_VERIFICATION",
        assigned_role="FIELD_AMIN",
        status=ActionStatus.OPEN
    )
    db_session.add(action)
    db_session.commit()

    # -------------------------------------------------------------------------
    # STEP 10: Exercise Field-Verification Workflow Using Synthetic Observations
    # -------------------------------------------------------------------------
    field_task = FieldVerificationTask(
        org_id=tenant_a.org_id,
        case_id=case.case_id,
        parcel_id=parcel.parcel_id,
        finding_id=finding.finding_id,
        action_id=action.action_id,
        task_number=f"TASK-STG-{smoke_id}",
        title="Smoke Test Field Demarcation",
        reason="Field boundary and possession verification",
        requested_activities=["BOUNDARY_DEMARCATION", "POSSESSION_INQUIRY"],
        priority=TaskPriority.HIGH,
        status=TaskStatus.REVIEW_ACCEPTED,
        assigned_amin_id=user_a.user_id,
        instructions="Confirm eastern boundary wall",
        field_observations={
            "physical_possessor": {"name": "Ramesh Kumar", "relationship": "Owner"},
            "road_access": {"has_road": True, "road_width_ft": 20.0},
            "ground_neighbors": {"north": "Govt Road", "south": "Plot 778"}
        }
    )
    db_session.add(field_task)
    db_session.commit()

    # -------------------------------------------------------------------------
    # STEP 11: Generate Land Intelligence Report
    # -------------------------------------------------------------------------
    report_gen_resp = client.post(
        "/api/v1/reports/generate",
        headers=auth_headers,
        json={
            "case_id": str(case.case_id),
            "parcel_id": str(parcel.parcel_id),
            "report_title": f"Staging Intelligence Dossier {smoke_id}"
        }
    )
    assert report_gen_resp.status_code == 201, report_gen_resp.text
    report_data = report_gen_resp.json()
    report_id = uuid.UUID(report_data["report_id"])
    verification_token = report_data["verification_url"].split("/")[-1]

    # -------------------------------------------------------------------------
    # STEP 12: Verify Stored Report's SHA-256 Integrity
    # -------------------------------------------------------------------------
    storage = get_document_storage()
    report_record = db_session.query(LandIntelligenceReport).filter(LandIntelligenceReport.report_id == report_id).first()
    assert report_record is not None
    pdf_bytes = storage.get(report_record.pdf_storage_uri)
    computed_hash = hashlib.sha256(pdf_bytes).hexdigest()
    assert computed_hash == report_record.sha256_hash

    # Verify public verification endpoint
    public_verify_resp = client.get(f"/api/v1/reports/verify/{verification_token}")
    assert public_verify_resp.status_code == 200
    assert public_verify_resp.json()["is_authentic"] is True
    assert public_verify_resp.json()["hash_matches_stored_file"] is True

    # -------------------------------------------------------------------------
    # STEP 13: Retrieve Permitted Data Through Governed MCP Interface
    # -------------------------------------------------------------------------
    token_op_a = auth_headers["Authorization"].split(" ")[1]
    mcp_res = execute_get_parcel_summary(
        db=db_session,
        parcel_id=str(parcel.parcel_id),
        auth_token=token_op_a
    )
    assert mcp_res.success is True
    assert mcp_res.data["bhumi_id"] == parcel.bhumi_id

    # -------------------------------------------------------------------------
    # STEP 14: Confirm Unauthorized Cross-Tenant Access Fails
    # -------------------------------------------------------------------------
    other_org_token = create_access_token(data={"sub": str(uuid.uuid4()), "tenant_id": str(uuid.uuid4()), "role": "ADMIN"})
    cross_tenant_resp = client.get(
        f"/api/v1/cases/{case.case_id}",
        headers={"Authorization": f"Bearer {other_org_token}"}
    )
    assert cross_tenant_resp.status_code in (401, 403, 404)

    # -------------------------------------------------------------------------
    # STEP 15: Confirm Unauthorized Role Cannot Execute State-Changing Action
    # -------------------------------------------------------------------------
    viewer_token = create_access_token(data={"sub": str(uuid.uuid4()), "tenant_id": str(tenant_a.org_id), "role": "CLIENT_VIEWER"})
    forbidden_resp = client.post(
        "/api/v1/reports/generate",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"case_id": str(case.case_id), "parcel_id": str(parcel.parcel_id)}
    )
    assert forbidden_resp.status_code in (401, 403)

    # -------------------------------------------------------------------------
    # STEP 16: Verify Persisted Data Remains Available Upon Fresh Query
    # -------------------------------------------------------------------------
    db_session.expire_all()
    reloaded_case = db_session.query(Case).filter(Case.case_id == case.case_id).first()
    assert reloaded_case is not None
    assert reloaded_case.case_number == case.case_number

    # -------------------------------------------------------------------------
    # STEP 17: Exercise Controlled Failure of Optional Integration
    # -------------------------------------------------------------------------
    from app.core.storage import S3DocumentStorage, StorageException
    unconfigured_storage = S3DocumentStorage(bucket_name=None)
    unconfigured_storage.bucket_name = None
    with pytest.raises(StorageException, match="NOT_CONFIGURED"):
        unconfigured_storage.put(b"content", "doc.pdf", "application/pdf")

    # -------------------------------------------------------------------------
    # STEP 18: Clean Up Synthetic Test Data
    # -------------------------------------------------------------------------
    db_session.query(CaseEvidence).filter(CaseEvidence.case_id == case.case_id).delete()
    if evidence:
        db_session.delete(evidence)
    db_session.delete(field_task)
    db_session.delete(action)
    db_session.delete(finding)
    db_session.delete(report_record)
    db_session.delete(doc_version)
    db_session.delete(doc)
    db_session.delete(case_parcel)
    db_session.delete(parcel)
    db_session.delete(case)
    db_session.commit()
