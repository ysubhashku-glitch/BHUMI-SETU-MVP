import io
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.case import Case, CaseStatus, TransactionReadinessState
from app.models.parcel import Parcel
from app.models.finding import Finding, FindingSeverity, FindingStatus, RequiredAction, ActionStatus
from app.models.field_task import FieldVerificationTask, TaskStatus, TaskPriority, ReviewOutcome
from app.models.field_survey import FieldSurvey
from app.models.evidence import Evidence
from app.core.security import hash_password, create_access_token

@pytest.fixture
def amin_a(db_session: Session, tenant_a: Organization) -> User:
    amin = User(
        org_id=tenant_a.org_id,
        email="amin_deoghar@bhumisetu.local",
        hashed_password=hash_password("Password123!"),
        full_name="DEMO_DATA: Rameshwar Amin",
        phone_number="9800000030",
        role=UserRole.FIELD_EXPERT,
        is_active=True
    )
    db_session.add(amin)
    db_session.commit()
    db_session.refresh(amin)
    return amin

@pytest.fixture
def amin_b(db_session: Session, tenant_b: Organization) -> User:
    amin = User(
        org_id=tenant_b.org_id,
        email="amin_dumka@bhumisetu.local",
        hashed_password=hash_password("Password123!"),
        full_name="DEMO_DATA: Suresh Amin",
        phone_number="9800000040",
        role=UserRole.FIELD_EXPERT,
        is_active=True
    )
    db_session.add(amin)
    db_session.commit()
    db_session.refresh(amin)
    return amin

@pytest.fixture
def reviewer_a(db_session: Session, tenant_a: Organization) -> User:
    reviewer = User(
        org_id=tenant_a.org_id,
        email="reviewer_a@bhumisetu.local",
        hashed_password=hash_password("Password123!"),
        full_name="DEMO_DATA: Legal Reviewer A",
        phone_number="9800000050",
        role=UserRole.LEGAL_REVIEWER,
        is_active=True
    )
    db_session.add(reviewer)
    db_session.commit()
    db_session.refresh(reviewer)
    return reviewer

@pytest.fixture
def headers_amin_a(amin_a: User) -> dict:
    token = create_access_token(data={"sub": str(amin_a.user_id), "tenant_id": str(amin_a.org_id), "role": amin_a.role})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def headers_amin_b(amin_b: User) -> dict:
    token = create_access_token(data={"sub": str(amin_b.user_id), "tenant_id": str(amin_b.org_id), "role": amin_b.role})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def headers_reviewer_a(reviewer_a: User) -> dict:
    token = create_access_token(data={"sub": str(reviewer_a.user_id), "tenant_id": str(reviewer_a.org_id), "role": reviewer_a.role})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def test_case_a(db_session: Session, tenant_a: Organization, client_party) -> Case:
    case = Case(
        org_id=tenant_a.org_id,
        case_number=f"BS-JH-2026-{uuid.uuid4().hex[:5].upper()}",
        primary_client_party_id=client_party.party_id,
        status=CaseStatus.PROCESSING,
        transaction_readiness_state=TransactionReadinessState.NOT_READY
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case

@pytest.fixture
def test_parcel_a(db_session: Session, tenant_a: Organization) -> Parcel:
    parcel = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id=f"JH-DEO-{uuid.uuid4().hex[:6]}",
        state_code="JH",
        district_name="Deoghar",
        subdistrict_anchal_name="Deoghar Sadar",
        mauza_village_name="Jasidih",
        census_village_code="256789",
        khata_number="12",
        plot_khesra_number="104",
        recorded_area_acres=1.5000,
        land_nature="Raiyati",
        authoritative_boundary="SRID=4326;POLYGON((86.69 24.51, 86.70 24.51, 86.70 24.52, 86.69 24.52, 86.69 24.51))"
    )
    db_session.add(parcel)
    db_session.commit()
    db_session.refresh(parcel)
    return parcel

@pytest.fixture
def test_finding_and_action(db_session: Session, test_case_a: Case, test_parcel_a: Parcel) -> tuple[Finding, RequiredAction]:
    finding = Finding(
        case_id=test_case_a.case_id,
        parcel_id=test_parcel_a.parcel_id,
        rule_id="RULE_SPATIAL_AREA_DISCREPANCY",
        severity=FindingSeverity.HIGH,
        status=FindingStatus.OPEN,
        observed_values={"recorded_acres": 1.5, "gis_acres": 1.25, "variance_pct": -16.67},
        explanation="Cadastral map Bhu-Naksha area (1.25 ac) differs significantly from revenue record (1.50 ac).",
        recommended_action="Dispatch field Amin to conduct GNSS boundary survey."
    )
    db_session.add(finding)
    db_session.flush()

    action = RequiredAction(
        finding_id=finding.finding_id,
        case_id=test_case_a.case_id,
        action_type="PHYSICAL_FIELD_SURVEY",
        assigned_role="FIELD_AMIN",
        status=ActionStatus.OPEN
    )
    db_session.add(action)
    db_session.commit()
    db_session.refresh(finding)
    db_session.refresh(action)
    return finding, action


# =====================================================================
# Stage A: Task Creation & Eligibility Tests
# =====================================================================

def test_list_eligible_workers(client: TestClient, auth_headers_a: dict, amin_a: User):
    resp = client.get("/api/v1/landamin/workers/eligible", headers=auth_headers_a)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    worker_emails = [w["email"] for w in data]
    assert amin_a.email in worker_emails
    for worker in data:
        assert worker["role"] == UserRole.FIELD_EXPERT
        assert worker["verified_qualifications"] is False  # Explicitly distinguished

def test_create_field_verification_task_success(
    client: TestClient,
    auth_headers_a: dict,
    test_case_a: Case,
    test_parcel_a: Parcel,
    test_finding_and_action: tuple[Finding, RequiredAction]
):
    finding, action = test_finding_and_action
    payload = {
        "case_id": str(test_case_a.case_id),
        "parcel_id": str(test_parcel_a.parcel_id),
        "finding_id": str(finding.finding_id),
        "action_id": str(action.action_id),
        "title": "Field Boundary Verification for Plot 104",
        "reason": "16.7% area discrepancy between Bhu-Naksha cadastral map and Jamabandi",
        "requested_activities": ["BOUNDARY_WALK", "CHAUHADDI_CHECK", "SITE_PHOTOS"],
        "priority": "HIGH",
        "instructions": "Locate southern canal ridge and record GPS points of boundary turns."
    }
    resp = client.post("/api/v1/landamin/tasks", json=payload, headers=auth_headers_a)
    assert resp.status_code == 201
    data = resp.json()
    assert data["task_number"].startswith("FT-")
    assert data["status"] == TaskStatus.READY_FOR_ASSIGNMENT
    assert data["case_id"] == str(test_case_a.case_id)
    assert data["priority"] == "HIGH"
    assert data["finding_id"] == str(finding.finding_id)

def test_create_task_cross_tenant_forbidden(client: TestClient, auth_headers_b: dict, test_case_a: Case):
    # Operator from Tenant B attempts to create task on Tenant A's case
    payload = {
        "case_id": str(test_case_a.case_id),
        "title": "Cross Tenant Intrusion",
        "reason": "Unauthorized access attempt"
    }
    resp = client.post("/api/v1/landamin/tasks", json=payload, headers=auth_headers_b)
    assert resp.status_code == 403


# =====================================================================
# Stage B: Assignment & Security Tests
# =====================================================================

def test_assign_task_success(
    client: TestClient,
    auth_headers_a: dict,
    test_case_a: Case,
    amin_a: User
):
    # 1. Create task
    create_resp = client.post(
        "/api/v1/landamin/tasks",
        json={"case_id": str(test_case_a.case_id), "title": "Plot Inspection", "reason": "General boundary check"},
        headers=auth_headers_a
    )
    task_id = create_resp.json()["task_id"]

    # 2. Assign to Amin A
    due_date = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    assign_payload = {
        "amin_user_id": str(amin_a.user_id),
        "due_date": due_date,
        "instructions": "Verify possession and Chauhaddi."
    }
    assign_resp = client.post(f"/api/v1/landamin/tasks/{task_id}/assign", json=assign_payload, headers=auth_headers_a)
    assert assign_resp.status_code == 200
    data = assign_resp.json()
    assert data["status"] == TaskStatus.ASSIGNED
    assert data["assigned_amin_id"] == str(amin_a.user_id)

def test_assign_task_cross_tenant_worker_forbidden(
    client: TestClient,
    auth_headers_a: dict,
    test_case_a: Case,
    amin_b: User
):
    # Operator A cannot assign worker from tenant B
    create_resp = client.post(
        "/api/v1/landamin/tasks",
        json={"case_id": str(test_case_a.case_id), "title": "Plot Inspection", "reason": "Check"},
        headers=auth_headers_a
    )
    task_id = create_resp.json()["task_id"]

    resp = client.post(
        f"/api/v1/landamin/tasks/{task_id}/assign",
        json={"amin_user_id": str(amin_b.user_id)},
        headers=auth_headers_a
    )
    assert resp.status_code == 403

def test_worker_cannot_assign_tasks(client: TestClient, headers_amin_a: dict, test_case_a: Case, amin_a: User):
    # Field worker role cannot assign tasks (principle of least privilege)
    resp = client.post(
        f"/api/v1/landamin/tasks/{uuid.uuid4()}/assign",
        json={"amin_user_id": str(amin_a.user_id)},
        headers=headers_amin_a
    )
    assert resp.status_code == 403


# =====================================================================
# Stage C & D: Mobile Field Worker Lifecycle (Accept, Decline, Visit)
# =====================================================================

def test_mobile_my_tasks_and_worker_isolation(
    client: TestClient,
    auth_headers_a: dict,
    headers_amin_a: dict,
    headers_amin_b: dict,
    test_case_a: Case,
    amin_a: User
):
    # Create and assign task to Amin A
    c_resp = client.post(
        "/api/v1/landamin/tasks",
        json={"case_id": str(test_case_a.case_id), "title": "Amin A Task", "reason": "Verification"},
        headers=auth_headers_a
    )
    task_id = c_resp.json()["task_id"]
    client.post(f"/api/v1/landamin/tasks/{task_id}/assign", json={"amin_user_id": str(amin_a.user_id)}, headers=auth_headers_a)

    # Amin A sees the task
    resp_a = client.get("/api/v1/landamin/mobile/my-tasks", headers=headers_amin_a)
    assert resp_a.status_code == 200
    task_ids_a = [t["task_id"] for t in resp_a.json()]
    assert task_id in task_ids_a

    # Amin B cannot access Amin A's task
    resp_b = client.get(f"/api/v1/landamin/mobile/tasks/{task_id}", headers=headers_amin_b)
    assert resp_b.status_code == 403

def test_accept_and_start_field_visit(
    client: TestClient,
    auth_headers_a: dict,
    headers_amin_a: dict,
    test_case_a: Case,
    amin_a: User
):
    c_resp = client.post(
        "/api/v1/landamin/tasks",
        json={"case_id": str(test_case_a.case_id), "title": "Field Inspection Walk", "reason": "Discrepancy"},
        headers=auth_headers_a
    )
    task_id = c_resp.json()["task_id"]
    client.post(f"/api/v1/landamin/tasks/{task_id}/assign", json={"amin_user_id": str(amin_a.user_id)}, headers=auth_headers_a)

    # Accept
    acc_resp = client.post(f"/api/v1/landamin/mobile/tasks/{task_id}/accept", headers=headers_amin_a)
    assert acc_resp.status_code == 200
    assert acc_resp.json()["status"] == TaskStatus.ACCEPTED

    # Start Visit
    visit_resp = client.post(f"/api/v1/landamin/mobile/tasks/{task_id}/start-visit", headers=headers_amin_a)
    assert visit_resp.status_code == 200
    assert visit_resp.json()["status"] == TaskStatus.IN_PROGRESS
    assert visit_resp.json()["visit_started_at"] is not None

def test_decline_field_assignment(
    client: TestClient,
    auth_headers_a: dict,
    headers_amin_a: dict,
    test_case_a: Case,
    amin_a: User
):
    c_resp = client.post(
        "/api/v1/landamin/tasks",
        json={"case_id": str(test_case_a.case_id), "title": "Flood Prone Plot", "reason": "Check"},
        headers=auth_headers_a
    )
    task_id = c_resp.json()["task_id"]
    client.post(f"/api/v1/landamin/tasks/{task_id}/assign", json={"amin_user_id": str(amin_a.user_id)}, headers=auth_headers_a)

    decline_resp = client.post(
        f"/api/v1/landamin/mobile/tasks/{task_id}/decline",
        json={"reason": "Site currently inaccessible due to heavy monsoon waterlogging."},
        headers=headers_amin_a
    )
    assert decline_resp.status_code == 200
    assert decline_resp.json()["status"] == TaskStatus.DECLINED
    assert decline_resp.json()["decline_reason"] == "Site currently inaccessible due to heavy monsoon waterlogging."


# =====================================================================
# Geospatial Observation, Coordinate Validation & Boundary Comparison
# =====================================================================

def test_coordinate_validation_bounds():
    from app.schemas.field_task import GPSPointObservation
    # Valid coordinates in Bihar
    valid_pt = GPSPointObservation(latitude=24.5123, longitude=86.6987, crs="EPSG:4326", accuracy_meters=3.5)
    assert valid_pt.latitude == 24.5123

    # Out-of-bounds latitude
    with pytest.raises(ValueError):
        GPSPointObservation(latitude=95.0, longitude=86.6987)

    # Out-of-bounds longitude
    with pytest.raises(ValueError):
        GPSPointObservation(latitude=24.5123, longitude=-190.0)

    # Unsupported CRS rejected
    with pytest.raises(ValueError):
        GPSPointObservation(latitude=24.5123, longitude=86.6987, crs="UNKNOWN_LOCAL_GRID")

    # Negative accuracy rejected
    with pytest.raises(ValueError):
        GPSPointObservation(latitude=24.5123, longitude=86.6987, accuracy_meters=-5.0)

def test_submit_field_report_with_boundary_comparison(
    client: TestClient,
    auth_headers_a: dict,
    headers_amin_a: dict,
    test_case_a: Case,
    test_parcel_a: Parcel,
    amin_a: User
):
    # 1. Create and assign task linked to parcel
    c_resp = client.post(
        "/api/v1/landamin/tasks",
        json={
            "case_id": str(test_case_a.case_id),
            "parcel_id": str(test_parcel_a.parcel_id),
            "title": "Ground Demarcation Survey",
            "reason": "Cadastral area discrepancy"
        },
        headers=auth_headers_a
    )
    task_id = c_resp.json()["task_id"]
    client.post(f"/api/v1/landamin/tasks/{task_id}/assign", json={"amin_user_id": str(amin_a.user_id)}, headers=auth_headers_a)
    client.post(f"/api/v1/landamin/mobile/tasks/{task_id}/accept", headers=headers_amin_a)
    client.post(f"/api/v1/landamin/mobile/tasks/{task_id}/start-visit", headers=headers_amin_a)

    # 2. Prepare field report with 4 corner boundary points (~1.45 acres polygon around lat 24.51, lon 86.69)
    # 1 deg lat ≈ 110800m. 0.0007 deg ≈ 77.5m. 0.00075 deg lon ≈ 75.3m. 77.5 * 75.3 ≈ 5835 sqm ≈ 1.44 acres
    boundary_points = [
        {"latitude": 24.51000, "longitude": 86.69000, "point_type": "CORNER", "label": "SW Pillar", "accuracy_meters": 3.2},
        {"latitude": 24.51070, "longitude": 86.69000, "point_type": "CORNER", "label": "NW Pillar", "accuracy_meters": 3.0},
        {"latitude": 24.51070, "longitude": 86.69075, "point_type": "CORNER", "label": "NE Pillar", "accuracy_meters": 3.5},
        {"latitude": 24.51000, "longitude": 86.69075, "point_type": "CORNER", "label": "SE Pillar", "accuracy_meters": 2.8},
        {"latitude": 24.51000, "longitude": 86.69000, "point_type": "CORNER", "label": "SW Pillar (Close)", "accuracy_meters": 3.2}
    ]

    report_payload = {
        "client_observation_id": str(uuid.uuid4()),
        "narrative_report": "Field boundary points surveyed using GNSS receiver along existing cement boundary pillars. South side abuts irrigation canal.",
        "boundary_points": boundary_points,
        "gps_points": boundary_points[:2],
        "ground_neighbors": {
            "north": "Ramlal Sah",
            "south": "Irrigation Canal (Distributary 4)",
            "east": "Village Pathway 12ft",
            "west": "Devendra Yadav"
        },
        "road_access": {
            "road_type": "PUCCA_ROAD",
            "frontage_feet": 45.0,
            "notes": "Direct access to eastern village road."
        },
        "physical_possessor": {
            "name": "Devendra Yadav",
            "relationship_or_claim": "Self / Cultivator",
            "possession_years": 18,
            "remarks": "Paddy crop standing at inspection time."
        }
    }

    submit_resp = client.post(f"/api/v1/landamin/mobile/tasks/{task_id}/submit", json=report_payload, headers=headers_amin_a)
    assert submit_resp.status_code == 200
    res_data = submit_resp.json()
    assert res_data["status"] == TaskStatus.SUBMITTED

    obs = res_data["field_observations"]
    assert obs["measured_area_acres"] > 1.0  # Computed ~1.44 acres
    assert obs["ground_neighbors"]["north"] == "Ramlal Sah"
    assert obs["physical_possessor"]["name"] == "Devendra Yadav"

    # Spatial comparison check
    comp = res_data["boundary_comparison"]
    assert comp is not None
    assert comp["recorded_cadastral_acres"] == 1.5000
    assert abs(comp["delta_acres"]) < 0.20
    assert "indicative supporting evidence" in comp["legal_limitation"].lower()

    # CRITICAL: Verify Authoritative Cadastral Boundary of parcel was NOT overwritten
    detail_resp = client.get(f"/api/v1/landamin/tasks/{task_id}", headers=auth_headers_a)
    assert detail_resp.status_code == 200
    assert test_parcel_a.recorded_area_acres == 1.5000
    assert "86.69" in str(test_parcel_a.authoritative_boundary)


# =====================================================================
# Photo Evidence Management Tests
# =====================================================================

def test_photo_upload_and_evidence_anchoring(
    client: TestClient,
    auth_headers_a: dict,
    headers_amin_a: dict,
    test_case_a: Case,
    amin_a: User
):
    c_resp = client.post(
        "/api/v1/landamin/tasks",
        json={"case_id": str(test_case_a.case_id), "title": "Boundary Pillar Photos", "reason": "Visual inspection"},
        headers=auth_headers_a
    )
    task_id = c_resp.json()["task_id"]
    client.post(f"/api/v1/landamin/tasks/{task_id}/assign", json={"amin_user_id": str(amin_a.user_id)}, headers=auth_headers_a)
    client.post(f"/api/v1/landamin/mobile/tasks/{task_id}/accept", headers=headers_amin_a)

    # Valid JPEG file bytes (\xff\xd8\xff signature)
    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00" + b"\x00" * 100
    files = {"file": ("boundary_pillar_ne.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")}
    data = {"latitude": "24.5107", "longitude": "86.69075", "accuracy_meters": "2.5"}

    upload_resp = client.post(
        f"/api/v1/landamin/mobile/tasks/{task_id}/photos",
        files=files,
        data=data,
        headers=headers_amin_a
    )
    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()
    assert upload_data["sha256_hash"] is not None
    assert upload_data["evidence_metadata"]["latitude"] == 24.5107

    # Check that task details reflect the linked evidence ID
    detail_resp = client.get(f"/api/v1/landamin/mobile/tasks/{task_id}", headers=headers_amin_a)
    assert upload_data["evidence_id"] in [str(eid) for eid in detail_resp.json()["evidence_ids"]]

def test_photo_upload_invalid_signature_rejected(
    client: TestClient,
    auth_headers_a: dict,
    headers_amin_a: dict,
    test_case_a: Case,
    amin_a: User
):
    c_resp = client.post(
        "/api/v1/landamin/tasks",
        json={"case_id": str(test_case_a.case_id), "title": "Pillar Photo Check", "reason": "Check"},
        headers=auth_headers_a
    )
    task_id = c_resp.json()["task_id"]
    client.post(f"/api/v1/landamin/tasks/{task_id}/assign", json={"amin_user_id": str(amin_a.user_id)}, headers=auth_headers_a)

    # Fake JPEG with malicious text bytes
    fake_bytes = b"MALICIOUS_EXECUTABLE_SHELL_SCRIPT_CODE_HERE"
    files = {"file": ("malicious.jpg", io.BytesIO(fake_bytes), "image/jpeg")}

    upload_resp = client.post(
        f"/api/v1/landamin/mobile/tasks/{task_id}/photos",
        files=files,
        headers=headers_amin_a
    )
    assert upload_resp.status_code == 400


# =====================================================================
# Review & Resolution Workflow Tests
# =====================================================================

def test_review_and_resolve_finding(
    client: TestClient,
    auth_headers_a: dict,
    headers_amin_a: dict,
    headers_reviewer_a: dict,
    test_case_a: Case,
    test_parcel_a: Parcel,
    test_finding_and_action: tuple[Finding, RequiredAction],
    amin_a: User
):
    finding, action = test_finding_and_action

    # 1. Create and complete task linked to finding and action
    c_resp = client.post(
        "/api/v1/landamin/tasks",
        json={
            "case_id": str(test_case_a.case_id),
            "parcel_id": str(test_parcel_a.parcel_id),
            "finding_id": str(finding.finding_id),
            "action_id": str(action.action_id),
            "title": "Resolve Boundary Conflict",
            "reason": "Verify boundary lines and area discrepancy"
        },
        headers=auth_headers_a
    )
    task_id = c_resp.json()["task_id"]
    client.post(f"/api/v1/landamin/tasks/{task_id}/assign", json={"amin_user_id": str(amin_a.user_id)}, headers=auth_headers_a)
    client.post(f"/api/v1/landamin/mobile/tasks/{task_id}/accept", headers=headers_amin_a)
    client.post(f"/api/v1/landamin/mobile/tasks/{task_id}/start-visit", headers=headers_amin_a)
    client.post(
        f"/api/v1/landamin/mobile/tasks/{task_id}/submit",
        json={"narrative_report": "Boundary physical check matches 1.48 acres within 1.3% variance of Jamabandi.", "measured_area_acres": 1.48},
        headers=headers_amin_a
    )

    # 2. Reviewer accepts report
    review_payload = {
        "outcome": ReviewOutcome.ACCEPT,
        "review_notes": "Field evidence adequate. Ground boundary pillars and possessor verified. Area delta within acceptable tolerance.",
        "create_field_survey_record": True
    }
    rev_resp = client.post(f"/api/v1/landamin/tasks/{task_id}/review", json=review_payload, headers=headers_reviewer_a)
    assert rev_resp.status_code == 200
    rev_data = rev_resp.json()
    assert rev_data["status"] == TaskStatus.REVIEW_ACCEPTED
    assert rev_data["review_status"] == ReviewOutcome.ACCEPT
    assert rev_data["survey_id"] is not None

    # Verify originating finding & action were updated
    assert action.status == ActionStatus.COMPLETED
    assert finding.status == FindingStatus.RESOLVED

def test_reviewer_conflict_of_interest_rejected(
    client: TestClient,
    auth_headers_a: dict,
    headers_amin_a: dict,
    test_case_a: Case,
    amin_a: User
):
    # If the assigned worker tries to review their own task
    c_resp = client.post(
        "/api/v1/landamin/tasks",
        json={"case_id": str(test_case_a.case_id), "title": "Self Check", "reason": "Check"},
        headers=auth_headers_a
    )
    task_id = c_resp.json()["task_id"]
    client.post(f"/api/v1/landamin/tasks/{task_id}/assign", json={"amin_user_id": str(amin_a.user_id)}, headers=auth_headers_a)

    # Amin A submits
    client.post(f"/api/v1/landamin/mobile/tasks/{task_id}/accept", headers=headers_amin_a)
    client.post(f"/api/v1/landamin/mobile/tasks/{task_id}/submit", json={"narrative_report": "Done"}, headers=headers_amin_a)

    # Amin A cannot review their own report
    resp = client.post(
        f"/api/v1/landamin/tasks/{task_id}/review",
        json={"outcome": ReviewOutcome.ACCEPT, "review_notes": "Self approval attempt"},
        headers=headers_amin_a
    )
    assert resp.status_code == 403

def test_reviewer_request_revision_and_resubmit(
    client: TestClient,
    auth_headers_a: dict,
    headers_amin_a: dict,
    headers_reviewer_a: dict,
    test_case_a: Case,
    amin_a: User
):
    c_resp = client.post(
        "/api/v1/landamin/tasks",
        json={"case_id": str(test_case_a.case_id), "title": "Revision Flow Task", "reason": "Check"},
        headers=auth_headers_a
    )
    task_id = c_resp.json()["task_id"]
    client.post(f"/api/v1/landamin/tasks/{task_id}/assign", json={"amin_user_id": str(amin_a.user_id)}, headers=auth_headers_a)
    client.post(f"/api/v1/landamin/mobile/tasks/{task_id}/accept", headers=headers_amin_a)
    client.post(f"/api/v1/landamin/mobile/tasks/{task_id}/submit", json={"narrative_report": "Initial partial report"}, headers=headers_amin_a)

    # Reviewer requests revision
    rev_resp = client.post(
        f"/api/v1/landamin/tasks/{task_id}/review",
        json={"outcome": ReviewOutcome.REVISION_REQUESTED, "review_notes": "Please verify north ground neighbor name."},
        headers=headers_reviewer_a
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["status"] == TaskStatus.REVISION_REQUESTED

    # Worker resubmits corrected report
    resubmit_resp = client.post(
        f"/api/v1/landamin/mobile/tasks/{task_id}/submit",
        json={"narrative_report": "Updated with North neighbor verified as Ramlal Sah.", "ground_neighbors": {"north": "Ramlal Sah"}},
        headers=headers_amin_a
    )
    assert resubmit_resp.status_code == 200
    assert resubmit_resp.json()["status"] == TaskStatus.SUBMITTED

def test_cancel_task_with_reason(client: TestClient, auth_headers_a: dict, test_case_a: Case):
    c_resp = client.post(
        "/api/v1/landamin/tasks",
        json={"case_id": str(test_case_a.case_id), "title": "Task to Cancel", "reason": "Preliminary check"},
        headers=auth_headers_a
    )
    task_id = c_resp.json()["task_id"]

    cancel_resp = client.post(
        f"/api/v1/landamin/tasks/{task_id}/cancel",
        json={"reason": "Litigation stay order received from Sub-divisional Court."},
        headers=auth_headers_a
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == TaskStatus.CANCELLED
    assert cancel_resp.json()["cancellation_reason"] == "Litigation stay order received from Sub-divisional Court."
