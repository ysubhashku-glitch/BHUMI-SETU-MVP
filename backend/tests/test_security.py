import pytest
from app.models.case import Case, CaseStatus, TransactionReadinessState
from app.models.parcel import Parcel
from app.models.party import Party, PartyType, CommunityCategory

def test_cross_tenant_case_access_denied(client, db_session, tenant_b, user_b, auth_headers_a):
    # Create Party and Case in Tenant B
    party_b = Party(
        org_id=tenant_b.org_id,
        party_type=PartyType.PERSON,
        primary_name="DEMO_DATA: Client Tenant B",
        phone_number="9800000099"
    )
    db_session.add(party_b)
    db_session.flush()

    case_b = Case(
        org_id=tenant_b.org_id,
        case_number="BS-TENANT-B-001",
        primary_client_party_id=party_b.party_id,
        status=CaseStatus.DRAFT
    )
    db_session.add(case_b)
    db_session.commit()

    # User A (Tenant A) attempts to access Case B
    response = client.get(f"/api/v1/cases/{case_b.case_id}", headers=auth_headers_a)
    assert response.status_code == 403
    err = response.json()
    assert err["code"] == "CROSS_TENANT_ACCESS_DENIED"

def test_cross_tenant_parcel_access_denied(client, db_session, tenant_b, auth_headers_a):
    parcel_b = Parcel(
        org_id=tenant_b.org_id,
        bhumi_id="JH-DUM-PARCEL-B",
        state_code="JH",
        district_name="Dumka",
        subdistrict_anchal_name="Dumka",
        mauza_village_name="Dumka",
        census_village_code="365000",
        khata_number="01",
        plot_khesra_number="10",
        recorded_area_acres=0.5
    )
    db_session.add(parcel_b)
    db_session.commit()

    # User A attempts to view Parcel B
    response = client.get(f"/api/v1/parcels/{parcel_b.parcel_id}", headers=auth_headers_a)
    assert response.status_code == 403
    err = response.json()
    assert err["code"] == "CROSS_TENANT_ACCESS_DENIED"

def test_cross_tenant_document_upload_denied(client, db_session, tenant_b, user_b, auth_headers_a):
    party_b = Party(
        org_id=tenant_b.org_id,
        party_type=PartyType.PERSON,
        primary_name="DEMO_DATA: Client Tenant B",
        phone_number="9800000099"
    )
    db_session.add(party_b)
    db_session.flush()

    case_b = Case(
        org_id=tenant_b.org_id,
        case_number="BS-TENANT-B-DOC-001",
        primary_client_party_id=party_b.party_id,
        status=CaseStatus.DRAFT
    )
    db_session.add(case_b)
    db_session.commit()

    import io
    response = client.post(
        f"/api/v1/cases/{case_b.case_id}/documents",
        files={"file": ("deed.pdf", io.BytesIO(b"dummy"), "application/pdf")},
        data={"document_type": "REGISTERED_DOCUMENT"},
        headers=auth_headers_a  # Tenant A attempts to upload to Tenant B case
    )
    assert response.status_code == 403
    assert response.json()["code"] == "CROSS_TENANT_ACCESS_DENIED"

def test_cross_tenant_claim_creation_denied(client, db_session, tenant_b, user_b, auth_headers_a):
    party_b = Party(
        org_id=tenant_b.org_id,
        party_type=PartyType.PERSON,
        primary_name="DEMO_DATA: Client Tenant B",
        phone_number="9800000099"
    )
    parcel_b = Parcel(
        org_id=tenant_b.org_id,
        bhumi_id="JH-DUM-CLAIM-TEST",
        state_code="JH",
        district_name="Dumka",
        subdistrict_anchal_name="Dumka",
        mauza_village_name="Dumka",
        census_village_code="365000",
        khata_number="01",
        plot_khesra_number="10",
        recorded_area_acres=0.5
    )
    db_session.add_all([party_b, parcel_b])
    db_session.flush()

    case_b = Case(
        org_id=tenant_b.org_id,
        case_number="BS-TENANT-B-CLAIM-001",
        primary_client_party_id=party_b.party_id,
        status=CaseStatus.DRAFT
    )
    db_session.add(case_b)
    db_session.commit()

    # User A tries to create claim on Case B
    response = client.post(
        "/api/v1/claims",
        json={
            "case_id": str(case_b.case_id),
            "parcel_id": str(parcel_b.parcel_id),
            "evidence_id": "00000000-0000-0000-0000-000000000001",
            "subject_entity_type": "PARCEL",
            "subject_id": str(parcel_b.parcel_id),
            "predicate": "RECORDED_OWNER",
            "object_value": {"owner": "Adversary"},
            "authority_tier": "USER_SUBMISSION",
            "confidence_score": 1.0,
            "status": "ACTIVE"
        },
        headers=auth_headers_a
    )
    assert response.status_code == 403
    assert response.json()["code"] == "CROSS_TENANT_ACCESS_DENIED"

def test_cross_tenant_evidence_attachment_denied(client, db_session, tenant_b, user_b, auth_headers_a):
    party_b = Party(
        org_id=tenant_b.org_id,
        party_type=PartyType.PERSON,
        primary_name="DEMO_DATA: Client Tenant B",
        phone_number="9800000099"
    )
    db_session.add(party_b)
    db_session.flush()

    case_b = Case(
        org_id=tenant_b.org_id,
        case_number="BS-TENANT-B-EV-001",
        primary_client_party_id=party_b.party_id,
        status=CaseStatus.DRAFT
    )
    db_session.add(case_b)
    db_session.commit()

    # User A tries to attach evidence to Case B
    response = client.post(
        f"/api/v1/cases/{case_b.case_id}/evidence",
        json={"evidence_id": "00000000-0000-0000-0000-000000000001"},
        headers=auth_headers_a
    )
    assert response.status_code == 403
    assert response.json()["code"] == "CROSS_TENANT_ACCESS_DENIED"

def test_unauthenticated_request_denied(client):
    response = client.get("/api/v1/cases")
    assert response.status_code == 401
    err = response.json()
    assert err["code"] == "AUTHENTICATION_FAILED"
