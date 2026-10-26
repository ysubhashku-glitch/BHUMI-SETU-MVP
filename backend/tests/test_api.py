import pytest
import io
from app.models.case import CaseStatus

def test_auth_login_success(client, user_a):
    response = client.post(
        "/api/v1/auth/token",
        json={"email": user_a.email, "password": "Password123!"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == user_a.role
    assert data["tenant_id"] == str(user_a.org_id)

def test_auth_login_invalid_password(client, user_a):
    response = client.post(
        "/api/v1/auth/token",
        json={"email": user_a.email, "password": "WrongPassword!"}
    )
    assert response.status_code == 401
    data = response.json()
    assert data["code"] == "AUTHENTICATION_FAILED"

def test_create_and_get_parcel(client, auth_headers_a):
    payload = {
        "state_code": "JH",
        "district_name": "Deoghar",
        "subdistrict_anchal_name": "Mohanpur",
        "halka_number": "02",
        "mauza_village_name": "Chopamo",
        "census_village_code": "364000",
        "khata_number": "15",
        "plot_khesra_number": "301",
        "recorded_area_acres": 0.75,
        "land_nature": "AGRICULTURAL_RAIYATI"
    }
    create_res = client.post("/api/v1/parcels", json=payload, headers=auth_headers_a)
    assert create_res.status_code == 201
    parcel_data = create_res.json()
    assert parcel_data["plot_khesra_number"] == "301"
    assert parcel_data["bhumi_id"].startswith("JH-DEO-364000-301")

    # Get by ID
    get_res = client.get(f"/api/v1/parcels/{parcel_data['parcel_id']}", headers=auth_headers_a)
    assert get_res.status_code == 200
    assert get_res.json()["parcel_id"] == parcel_data["parcel_id"]

def test_create_case_and_invalid_state_transition(client, auth_headers_a, client_party):
    case_payload = {
        "primary_client_party_id": str(client_party.party_id),
        "target_transaction_type": "PURCHASE"
    }
    res = client.post("/api/v1/cases", json=case_payload, headers=auth_headers_a)
    assert res.status_code == 201
    case_data = res.json()
    assert case_data["status"] == CaseStatus.DRAFT

    # Illegal transition: DRAFT directly to FINAL (should raise STATE_TRANSITION_ERROR)
    trans_res = client.post(
        f"/api/v1/cases/{case_data['case_id']}/transition",
        json={"next_status": CaseStatus.FINAL, "transition_reason": "Skipping steps"},
        headers=auth_headers_a
    )
    assert trans_res.status_code == 400
    err_body = trans_res.json()
    assert err_body["code"] == "STATE_TRANSITION_ERROR"

def test_document_upload_and_evidence_attachment(client, auth_headers_a, client_party):
    # Create a draft case
    case_payload = {"primary_client_party_id": str(client_party.party_id)}
    case_res = client.post("/api/v1/cases", json=case_payload, headers=auth_headers_a)
    case_id = case_res.json()["case_id"]

    # Upload mock PDF
    file_bytes = b"%PDF-1.4 Mock Legal Certified Deed Content"
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": ("certified_deed.pdf", io.BytesIO(file_bytes), "application/pdf")},
        data={"document_type": "REGISTERED_DOCUMENT"},
        headers=auth_headers_a
    )
    assert upload_res.status_code == 201
    doc_data = upload_res.json()
    assert doc_data["original_filename"] == "certified_deed.pdf"
    assert doc_data["file_size_bytes"] == len(file_bytes)
    assert len(doc_data["sha256_hash"]) == 64
