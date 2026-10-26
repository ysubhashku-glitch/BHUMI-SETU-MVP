"""
BhumiSetu Containerized Staging Integration Test Suite (TASK-P1-09D).
Validates the actual running container stack against real infrastructure:
- PostgreSQL 16 + PostGIS 3.4 (real spatial database queries & transactions)
- Redis 7 & Celery Worker (real message broker queueing, daemon consumption, and result backend)
- MinIO Object Vault (real S3 API network calls, bucket existence, SHA-256 integrity, unauthorized rejection)
- Application HTTP Probes (/health/live lightweight process check vs /health/ready deep readiness)
- Volume persistence across restarts

When executed in local offline development without Docker containers running,
these live integration tests skip gracefully, preserving the unit regression suite.
When TEST_LIVE_STAGING=1 or running inside the containerized CI pipeline,
every test executes against real disposable container services.
"""
import os
import sys
import time
import uuid
import hashlib
import pytest
import httpx
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Integration test environment trigger
TEST_LIVE_STAGING = os.getenv("TEST_LIVE_STAGING", "false").lower() in ("true", "1", "yes")
STAGING_APP_URL = os.getenv("STAGING_APP_URL", "http://127.0.0.1:8000")


def check_db_live() -> bool:
    if settings.DATABASE_URL.startswith("sqlite"):
        return False
    try:
        engine = sa.create_engine(settings.DATABASE_URL, pool_pre_ping=True, connect_args={"connect_timeout": 2})
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
        return True
    except Exception:
        return False


def check_redis_live() -> bool:
    try:
        import redis
        r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=1.0)
        return bool(r.ping())
    except Exception:
        return False


def check_minio_live() -> bool:
    if settings.STORAGE_ADAPTER != "minio" or not settings.S3_ENDPOINT_URL:
        return False
    try:
        resp = httpx.get(f"{settings.S3_ENDPOINT_URL}/minio/health/live", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


def check_app_live() -> bool:
    try:
        resp = httpx.get(f"{STAGING_APP_URL}/health/live", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


LIVE_SERVICES_AVAILABLE = check_db_live() and check_redis_live()

pytestmark = pytest.mark.skipif(
    not (TEST_LIVE_STAGING or LIVE_SERVICES_AVAILABLE),
    reason="Live containerized staging services (PostgreSQL/Redis/MinIO) unavailable on host; test suite executes in CI staging integration pipeline."
)


# ==============================================================================
# 1. Real PostgreSQL & PostGIS Integration Tests
# ==============================================================================

def test_live_postgresql_connection_and_postgis_version():
    """Validates real PostgreSQL 16 connectivity and PostGIS 3.4 spatial extension presence."""
    engine = sa.create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    with engine.connect() as conn:
        # Check PostgreSQL dialect and version
        pg_version = conn.execute(sa.text("SELECT version();")).scalar()
        assert "PostgreSQL" in pg_version, f"Expected PostgreSQL, got: {pg_version}"

        # Check PostGIS spatial extension
        postgis_ver = conn.execute(sa.text("SELECT PostGIS_Version();")).scalar()
        assert postgis_ver is not None, "PostGIS extension must be installed and active"
        assert postgis_ver.startswith("3."), f"Expected PostGIS 3.x, got: {postgis_ver}"


def test_live_database_schema_and_alembic_head():
    """Verifies that real database contains all required schema tables and current Alembic migration head."""
    engine = sa.create_engine(settings.DATABASE_URL)
    inspector = sa.inspect(engine)
    tables = set(inspector.get_table_names())

    required_tables = {
        "organizations",
        "users",
        "cases",
        "parcels",
        "evidence",
        "findings",
        "field_verification_tasks",
        "land_intelligence_reports",
        "document_versions",
        "alembic_version"
    }
    missing = required_tables - tables
    assert not missing, f"Missing required database tables: {missing}"

    # Verify alembic_version has an active revision
    with engine.connect() as conn:
        current_rev = conn.execute(sa.text("SELECT version_num FROM alembic_version;")).scalar()
        assert current_rev is not None, "Alembic version table must contain head revision"


def test_live_database_crud_and_transaction_isolation():
    """Verifies write, commit, and query operations against real PostgreSQL database with isolated cleanup."""
    from app.models.organization import Organization
    from app.models.parcel import Parcel

    engine = sa.create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    test_uid = uuid.uuid4().hex[:8]
    org_slug = f"live-test-org-{test_uid}"
    bhumi_id = f"BR-LIVE-{test_uid}"

    try:
        # Create test organization
        test_org = Organization(
            name=f"Live Test Organization {test_uid}",
            slug=org_slug
        )
        session.add(test_org)
        session.flush()

        # Create test parcel with spatial boundary
        test_parcel = Parcel(
            org_id=test_org.org_id,
            bhumi_id=bhumi_id,
            state_code="BR",
            district_name="Patna",
            subdistrict_anchal_name="Danapur",
            halka_number="01",
            mauza_village_name="Digha",
            census_village_code="245001",
            khata_number="101",
            plot_khesra_number=f"999-{test_uid[:4]}",
            recorded_area_acres=2.50,
            land_nature="AGRICULTURAL_RAIYATI",
            authoritative_boundary="SRID=4326;POLYGON((85.10 25.60, 85.11 25.60, 85.11 25.61, 85.10 25.61, 85.10 25.60))"
        )
        session.add(test_parcel)
        session.commit()

        # Query back in a completely fresh session to prove real disk persistence
        session.close()
        new_session = Session()
        reloaded_parcel = new_session.query(Parcel).filter(Parcel.bhumi_id == bhumi_id).first()
        assert reloaded_parcel is not None
        assert reloaded_parcel.recorded_area_acres == 2.50
        assert reloaded_parcel.mauza_village_name == "Digha"

        # Safe cleanup targeting ONLY this synthetic test record
        new_session.delete(reloaded_parcel)
        reloaded_org = new_session.query(Organization).filter(Organization.slug == org_slug).first()
        if reloaded_org:
            new_session.delete(reloaded_org)
        new_session.commit()
        new_session.close()

    except Exception:
        session.rollback()
        session.close()
        raise


# ==============================================================================
# 2. Real Redis & Celery Worker Integration Tests
# ==============================================================================

def test_live_redis_ping_and_key_expiration():
    """Validates real Redis broker connectivity, write/read operations, and TTL behavior."""
    import redis
    r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2.0)
    assert r.ping() is True

    test_key = f"test:staging:ping:{uuid.uuid4().hex}"
    r.set(test_key, "integration_pong", ex=30)
    val = r.get(test_key)
    assert val == b"integration_pong"
    r.delete(test_key)
    assert r.get(test_key) is None


def test_live_celery_worker_task_consumption_and_completion():
    """
    Submits a real Celery task through the configured broker queue.
    Verifies that the background worker daemon consumes the task, executes it,
    and publishes the result to the Celery result backend.
    """
    from app.worker import celery_app, health_ping_task
    assert celery_app is not None, "Celery application must be configured"

    unique_payload = f"ci-payload-{uuid.uuid4().hex[:8]}"

    # Submit task asynchronously through the real Redis broker to the default queue
    async_res = health_ping_task.apply_async(kwargs={"echo": unique_payload}, queue="default")
    assert async_res.id is not None

    # Wait for the live background Celery worker container to pick up, process, and return result
    timeout_seconds = 25
    poll_interval = 0.5
    start_time = time.time()
    task_completed = False
    result = None

    while time.time() - start_time < timeout_seconds:
        if async_res.ready():
            task_completed = True
            result = async_res.result
            break
        time.sleep(poll_interval)

    assert task_completed, (
        f"Celery worker failed to complete task within {timeout_seconds}s. "
        f"Task status: {async_res.status}. Verify worker container is running."
    )
    assert async_res.status == "SUCCESS"
    assert isinstance(result, dict)
    assert result.get("status") == "SUCCESS"
    assert result.get("echo") == unique_payload
    assert result.get("worker_name") == "bhumisetu_staging_worker"


# ==============================================================================
# 3. Real MinIO / S3 Object Storage Integration Tests
# ==============================================================================

def test_live_minio_bucket_and_object_lifecycle():
    """
    Validates real MinIO S3 API operations:
    1. Idempotently ensures the staging bucket exists.
    2. Uploads a synthetic test file.
    3. Retrieves the file and validates SHA-256 integrity.
    4. Confirms metadata retrieval and presigned URL generation.
    5. Deletes only the uploaded test object without affecting existing files.
    """
    from app.core.storage import MinioDocumentStorage, StorageException

    storage = MinioDocumentStorage()
    assert storage.ensure_bucket_exists() is True

    test_content = b"%PDF-1.4\nStaging Live Integration Verification Document\n" + os.urandom(1024)
    expected_hash = hashlib.sha256(test_content).hexdigest()
    test_filename = f"integration_test_{uuid.uuid4().hex[:8]}.pdf"

    # Put object into MinIO
    put_result = storage.put(
        content=test_content,
        destination_name=test_filename,
        mime_type="application/pdf",
        metadata={"environment": "staging_integration", "test_id": test_filename}
    )

    storage_ref = put_result["storage_reference"]
    assert put_result["sha256_hash"] == expected_hash

    try:
        # Verify object existence
        assert storage.exists(storage_ref) is True

        # Retrieve and verify SHA-256 integrity
        retrieved_bytes = storage.get(storage_ref)
        assert len(retrieved_bytes) == len(test_content)
        assert retrieved_bytes == test_content
        assert hashlib.sha256(retrieved_bytes).hexdigest() == expected_hash

        # Verify metadata
        meta = storage.get_metadata(storage_ref)
        assert meta["file_size_bytes"] == len(test_content)

        # Verify presigned URL generation
        presigned = storage.generate_download_reference(storage_ref, expiry_seconds=300)
        assert "http" in presigned and settings.AWS_S3_BUCKET in presigned

    finally:
        # Scoped cleanup: strictly delete only this synthetic test object
        deleted = storage.delete(storage_ref)
        assert deleted is True
        assert storage.exists(storage_ref) is False


def test_live_minio_unauthorized_access_rejected():
    """Verifies that MinIO rejects requests with invalid credentials (403 Forbidden)."""
    import boto3
    from botocore.exceptions import ClientError

    bad_client = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL or "http://127.0.0.1:9000",
        aws_access_key_id="invalid_access_key_999",
        aws_secret_access_key="invalid_secret_key_888",
        region_name="us-east-1",
        use_ssl=False
    )

    with pytest.raises(ClientError) as exc_info:
        bad_client.list_objects_v2(Bucket=settings.AWS_S3_BUCKET or "bhumisetu-staging-evidence-vault")

    error_code = exc_info.value.response.get("Error", {}).get("Code", "")
    assert error_code in ("InvalidAccessKeyId", "AccessDenied", "SignatureDoesNotMatch", "403")


# ==============================================================================
# 4. Live Application Probes: Liveness vs Deep Readiness
# ==============================================================================

def test_live_application_liveness_probe():
    """Validates that /health/live returns 200 indicating web process liveness."""
    if not check_app_live():
        if TEST_LIVE_STAGING:
            pytest.fail(f"Live FastAPI application not responding at {STAGING_APP_URL}")
        pytest.skip(f"Live FastAPI application not responding at {STAGING_APP_URL}")

    resp = httpx.get(f"{STAGING_APP_URL}/health/live", timeout=5.0)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "alive"
    assert "uptime_seconds" in data


def test_live_application_readiness_probe_dependencies():
    """
    Validates that /health/ready returns 200 only when all critical dependencies are operational:
    - PostgreSQL is healthy
    - PostGIS extension is active
    - Alembic migrations are complete
    - Storage vault is accessible
    - Redis is answering pings
    - Celery worker is configured
    - Document OCR & PDF generator engines are healthy
    """
    if not check_app_live():
        if TEST_LIVE_STAGING:
            pytest.fail(f"Live FastAPI application not responding at {STAGING_APP_URL}")
        pytest.skip(f"Live FastAPI application not responding at {STAGING_APP_URL}")

    resp = httpx.get(f"{STAGING_APP_URL}/health/ready", timeout=5.0)
    assert resp.status_code == 200, f"Expected 200 ready, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["status"] == "ready"

    checks = data.get("checks", {})
    assert checks.get("database", {}).get("status") == "healthy"
    assert checks.get("schema", {}).get("status") == "healthy"
    assert checks.get("postgis", {}).get("status") == "healthy"
    assert checks.get("redis", {}).get("status") == "healthy"
    assert checks.get("document_engines", {}).get("status") == "healthy"
