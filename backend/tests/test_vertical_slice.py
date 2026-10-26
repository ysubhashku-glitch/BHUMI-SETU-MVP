import io
import uuid
from app.models.case import CaseStatus
from app.models.finding import FindingStatus, ActionStatus

def test_complete_vertical_slice(client, db_session, tenant_a, user_a, auth_headers_a, client_party):
    """
    Vertical Slice End-to-End Test:
    Tenant -> User -> Case -> Parcel -> Link Parcel -> Upload Document ->
    Create Evidence -> Attach Evidence -> Create Claim -> Create Finding ->
    Create Action -> Resolve Action & Finding
    """

    # 1. Create Case
    case_res = client.post(
        "/api/v1/cases",
        json={"primary_client_party_id": str(client_party.party_id), "target_transaction_type": "PURCHASE"},
        headers=auth_headers_a
    )
    assert case_res.status_code == 201
    case_data = case_res.json()
    case_id = case_data["case_id"]
    assert case_data["status"] == CaseStatus.DRAFT

    # 2. Create Parcel
    parcel_payload = {
        "state_code": "JH",
        "district_name": "Deoghar",
        "subdistrict_anchal_name": "Mohanpur",
        "halka_number": "04",
        "mauza_village_name": "Chopamo",
        "census_village_code": "364000",
        "khata_number": "12",
        "plot_khesra_number": "542",
        "recorded_area_acres": 1.5,
        "land_nature": "AGRICULTURAL_RAIYATI"
    }
    parcel_res = client.post("/api/v1/parcels", json=parcel_payload, headers=auth_headers_a)
    assert parcel_res.status_code == 201
    parcel_data = parcel_res.json()
    parcel_id = parcel_data["parcel_id"]

    # 3. Associate Parcel to Case
    link_res = client.post(
        f"/api/v1/cases/{case_id}/parcels",
        json={"parcel_id": parcel_id, "is_primary": True},
        headers=auth_headers_a
    )
    assert link_res.status_code == 201

    # Transition Case to PROPERTY_IDENTIFIED now that parcel is associated
    trans_res = client.post(
        f"/api/v1/cases/{case_id}/transition",
        json={"next_status": CaseStatus.PROPERTY_IDENTIFIED, "transition_reason": "Parcel linked"},
        headers=auth_headers_a
    )
    assert trans_res.status_code == 200
    assert trans_res.json()["status"] == CaseStatus.PROPERTY_IDENTIFIED

    # 4. Upload Document
    dummy_pdf = b"%PDF-1.4 Mock Certified Jamabandi Record Content"
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": ("jamabandi_record.pdf", io.BytesIO(dummy_pdf), "application/pdf")},
        data={"document_type": "GOVERNMENT_RECORD"},
        headers=auth_headers_a
    )
    assert upload_res.status_code == 201
    doc_data = upload_res.json()
    doc_id = doc_data["document_id"]
    doc_sha256 = doc_data["sha256_hash"]

    # 5. Create Standalone Evidence in Evidence Vault
    ev_payload = {
        "evidence_type": "GOVERNMENT_RECORD",
        "authority_tier": "REVENUE_RECORD",
        "source_name": "Certified Revenue Register Panji II",
        "storage_uri": f"mock://documents/{doc_id}.pdf",
        "sha256_hash": doc_sha256,
        "metadata": {"circle": "Mohanpur", "khatiyan": "Cadastral"}
    }
    ev_res = client.post("/api/v1/evidence", json=ev_payload, headers=auth_headers_a)
    assert ev_res.status_code == 201
    evidence_data = ev_res.json()
    evidence_id = evidence_data["evidence_id"]

    # 6. Associate Evidence to Case
    case_ev_res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        json={"evidence_id": evidence_id},
        headers=auth_headers_a
    )
    assert case_ev_res.status_code == 201

    # 7. Create Claim
    claim_payload = {
        "case_id": case_id,
        "parcel_id": parcel_id,
        "evidence_id": evidence_id,
        "subject_entity_type": "PARCEL",
        "subject_id": parcel_id,
        "predicate": "RECORDED_OWNER",
        "object_value": {"owner_name": "DEMO_DATA: Suresh Marandi", "share": "1/1"},
        "authority_tier": "REVENUE_RECORD",
        "confidence_score": 0.98,
        "status": "ACTIVE"
    }
    claim_res = client.post("/api/v1/claims", json=claim_payload, headers=auth_headers_a)
    assert claim_res.status_code == 201
    claim_data = claim_res.json()
    assert claim_data["predicate"] == "RECORDED_OWNER"

    # 8. Create Finding (e.g. area mismatch or statutory restriction)
    finding_payload = {
        "case_id": case_id,
        "parcel_id": parcel_id,
        "rule_id": "LEGAL_RULE_JH_SPT_SEC_20",
        "severity": "CRITICAL",
        "status": "OPEN",
        "observed_values": {"district": "Deoghar", "record_holder_caste": "ST"},
        "explanation": "Tribal Raiyati holding subject to Section 20 SPT Act 1949 statutory restriction.",
        "recommended_action": "Verify if Deputy Commissioner permission exists or obtain DC revenue order."
    }
    finding_res = client.post("/api/v1/findings", json=finding_payload, headers=auth_headers_a)
    assert finding_res.status_code == 201
    finding_data = finding_res.json()
    finding_id = finding_data["finding_id"]
    assert finding_data["status"] == FindingStatus.OPEN

    # 9. Create Required Action on Finding
    action_payload = {
        "action_type": "STATUTORY_CLEARANCE_VERIFICATION",
        "assigned_role": "LEGAL_ADVOCATE"
    }
    action_res = client.post(f"/api/v1/findings/{finding_id}/actions", json=action_payload, headers=auth_headers_a)
    assert action_res.status_code == 201
    action_data = action_res.json()
    action_id = action_data["action_id"]
    assert action_data["status"] == ActionStatus.OPEN

    # 10. Resolve Finding with required evidence
    resolve_payload = {
        "action_id": action_id,
        "resolving_evidence_id": evidence_id,
        "reviewer_party_id": str(client_party.party_id),
        "resolution_outcome": "RESOLVED_STATUTORY_PERMISSION_VERIFIED",
        "notes": "Verified certified DC Revenue Permission Order No. 441/1985."
    }
    resolve_res = client.post(f"/api/v1/findings/{finding_id}/resolve", json=resolve_payload, headers=auth_headers_a)
    assert resolve_res.status_code == 201
    resolve_data = resolve_res.json()
    assert resolve_data["resolution_outcome"] == "RESOLVED_STATUTORY_PERMISSION_VERIFIED"

    # 11. Verify that Finding status is now RESOLVED
    findings_list_res = client.get(f"/api/v1/cases/{case_id}/findings", headers=auth_headers_a)
    assert findings_list_res.status_code == 200
    case_findings = findings_list_res.json()
    target_finding = next(f for f in case_findings if f["finding_id"] == finding_id)
    assert target_finding["status"] == FindingStatus.RESOLVED

    # 12. Query Grounded Mock AI Expert on the resolved case
    ai_res = client.post(
        f"/api/v1/cases/{case_id}/ai/query",
        json={"query": "Is there any active statutory title defect on this property?"},
        headers=auth_headers_a
    )
    assert ai_res.status_code == 200
    ai_data = ai_res.json()
    assert ai_data["mode"] == "MOCK_AI"
    assert "grounding_contract" in ai_data
    assert ai_data["grounding_contract"]["read_only"] is True
