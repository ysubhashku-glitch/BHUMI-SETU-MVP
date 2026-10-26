import pytest
import uuid
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.database import Base, get_db
from app.main import app
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.party import Party, PartyType, CommunityCategory
from app.core.security import hash_password, create_access_token

# Test database: using file-based or in-memory sqlite
TEST_DATABASE_URL = "sqlite:///./test_bhumisetu.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()

@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def tenant_a(db_session: Session) -> Organization:
    org = Organization(name="DEMO_DATA: Deoghar Operations Tenant A", slug="deoghar-a")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org

@pytest.fixture
def tenant_b(db_session: Session) -> Organization:
    org = Organization(name="DEMO_DATA: Dumka Operations Tenant B", slug="dumka-b")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org

@pytest.fixture
def user_a(db_session: Session, tenant_a: Organization) -> User:
    user = User(
        org_id=tenant_a.org_id,
        email="operator_a@bhumisetu.local",
        hashed_password=hash_password("Password123!"),
        full_name="DEMO_DATA: Operator A",
        phone_number="9800000010",
        role=UserRole.CASE_OPERATOR,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def user_b(db_session: Session, tenant_b: Organization) -> User:
    user = User(
        org_id=tenant_b.org_id,
        email="operator_b@bhumisetu.local",
        hashed_password=hash_password("Password123!"),
        full_name="DEMO_DATA: Operator B",
        phone_number="9800000020",
        role=UserRole.CASE_OPERATOR,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def auth_headers_a(user_a: User) -> dict:
    token = create_access_token(
        data={"sub": str(user_a.user_id), "tenant_id": str(user_a.org_id), "role": user_a.role}
    )
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def auth_headers_b(user_b: User) -> dict:
    token = create_access_token(
        data={"sub": str(user_b.user_id), "tenant_id": str(user_b.org_id), "role": user_b.role}
    )
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def client_party(db_session: Session, tenant_a: Organization) -> Party:
    party = Party(
        org_id=tenant_a.org_id,
        party_type=PartyType.PERSON,
        primary_name="DEMO_DATA: Test Client Buyer",
        phone_number="9876543210",
        community_caste_category=CommunityCategory.GENERAL,
        is_tribal=False
    )
    db_session.add(party)
    db_session.commit()
    db_session.refresh(party)
    return party
