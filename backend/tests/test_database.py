import pytest
import uuid
from sqlalchemy.exc import IntegrityError
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.party import Party, PartyType, CommunityCategory
from app.models.parcel import Parcel
from app.models.case import Case, CaseStatus, TransactionReadinessState
from app.core.security import hash_password

def test_tenant_creation_and_guid_pk(db_session):
    org = Organization(name="DEMO_DATA: Test Org", slug="test-org-db")
    db_session.add(org)
    db_session.commit()
    
    assert org.org_id is not None
    assert isinstance(org.org_id, uuid.UUID)
    assert org.created_at is not None

def test_unique_user_email_constraint(db_session, tenant_a):
    user1 = User(
        org_id=tenant_a.org_id,
        email="duplicate@bhumisetu.local",
        hashed_password=hash_password("Pass1!"),
        full_name="User One",
        phone_number="1111111111",
        role=UserRole.CASE_OPERATOR
    )
    db_session.add(user1)
    db_session.commit()

    user2 = User(
        org_id=tenant_a.org_id,
        email="duplicate@bhumisetu.local",
        hashed_password=hash_password("Pass2!"),
        full_name="User Two",
        phone_number="2222222222",
        role=UserRole.CASE_OPERATOR
    )
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_unique_bhumi_id_constraint(db_session, tenant_a):
    p1 = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id="JH-DEO-MOH-UNIQUE-01",
        state_code="JH",
        district_name="Deoghar",
        subdistrict_anchal_name="Mohanpur",
        mauza_village_name="Chopamo",
        census_village_code="364",
        khata_number="10",
        plot_khesra_number="101",
        recorded_area_acres=1.2
    )
    db_session.add(p1)
    db_session.commit()

    p2 = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id="JH-DEO-MOH-UNIQUE-01",
        state_code="JH",
        district_name="Deoghar",
        subdistrict_anchal_name="Mohanpur",
        mauza_village_name="Chopamo",
        census_village_code="364",
        khata_number="10",
        plot_khesra_number="102",
        recorded_area_acres=1.5
    )
    db_session.add(p2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_cascade_delete_organization(db_session):
    org = Organization(name="DEMO_DATA: Transient Org", slug="transient-org")
    db_session.add(org)
    db_session.commit()

    user = User(
        org_id=org.org_id,
        email="transient@bhumisetu.local",
        hashed_password=hash_password("Pass1!"),
        full_name="Transient User",
        phone_number="9999999999",
        role=UserRole.ADMIN
    )
    db_session.add(user)
    db_session.commit()

    # Delete org should cascade delete user
    db_session.delete(org)
    db_session.commit()

    deleted_user = db_session.query(User).filter(User.user_id == user.user_id).first()
    assert deleted_user is None
