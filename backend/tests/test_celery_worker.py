import uuid
import pytest
from app.worker import (
    celery_app,
    process_document_ocr_task_logic,
    generate_report_task_logic
)
from app.models.evidence import (
    Document,
    DocumentVersion,
    DocumentCategory,
    DocumentProcessingStatus,
    Evidence,
    EvidenceType,
    AuthorityTier,
    CaseEvidence
)
from app.models.user import User, UserRole
from app.models.case import Case, CaseStatus
from app.models.parcel import Parcel


def test_celery_app_configuration():
    """Verifies that Celery application is configured with secure JSON serialization."""
    if celery_app is not None:
        conf = celery_app.conf
        assert conf.task_serializer == "json"
        assert conf.result_serializer == "json"
        assert "json" in conf.accept_content
        assert conf.task_acks_late is True
        assert "app.worker.process_document_ocr_task" in conf.task_routes


def test_ocr_task_idempotency_skip_already_completed(db_session, tenant_a):
    """If a document version is already COMPLETED, worker skips it without re-running."""
    doc = Document(
        org_id=tenant_a.org_id,
        document_category=DocumentCategory.SALE_DEED,
        original_filename="completed_doc.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        storage_uri="file:///tmp/doc.pdf",
        sha256_hash="a" * 64
    )
    db_session.add(doc)
    db_session.flush()

    ver = DocumentVersion(
        document_id=doc.document_id,
        version_number=1,
        content_hash="a" * 64,
        storage_reference="file:///tmp/doc.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        processing_status=DocumentProcessingStatus.PROCESSED
    )
    db_session.add(ver)
    db_session.commit()

    res = process_document_ocr_task_logic(
        document_id=str(doc.document_id),
        version_id=str(ver.version_id),
        case_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        db=db_session
    )

    assert res["status"] == "SKIPPED"
    assert res["reason"] == "ALREADY_COMPLETED"


def test_ocr_task_missing_version(db_session):
    """If document version is not found, worker returns structured failure without crashing."""
    random_id = str(uuid.uuid4())
    res = process_document_ocr_task_logic(
        document_id=random_id,
        version_id=random_id,
        case_id=random_id,
        user_id=random_id,
        db=db_session
    )
    assert res["status"] == "FAILED"
    assert res["error"] == "DOCUMENT_VERSION_NOT_FOUND"


def test_report_task_missing_user(db_session):
    """If requesting user is not found, worker returns structured failure."""
    random_id = str(uuid.uuid4())
    res = generate_report_task_logic(
        request_data={"case_id": random_id},
        user_id=random_id,
        org_id=random_id,
        db=db_session
    )
    assert res["status"] == "FAILED"
    assert res["error"] == "USER_NOT_FOUND"


def test_celery_task_apply_eager():
    """Verifies that Celery registered tasks can be executed via .apply() pipeline."""
    if celery_app is not None:
        from app.worker import process_document_ocr_task
        random_id = str(uuid.uuid4())
        res = process_document_ocr_task.apply(args=[random_id, random_id, random_id, random_id])
        assert res.successful()
        result_data = res.result
        assert result_data["status"] == "FAILED"
        assert result_data["error"] == "DOCUMENT_VERSION_NOT_FOUND"


def test_health_ping_task_logic_and_eager():
    """Verifies that health_ping_task executes and returns expected status and echo."""
    from app.worker import health_ping_task_logic, health_ping_task
    # Direct logic call
    res = health_ping_task_logic(echo="test_ping")
    assert res["status"] == "SUCCESS"
    assert res["echo"] == "test_ping"
    assert "timestamp" in res
    assert res["worker_name"] == "bhumisetu_staging_worker"

    # Eager Celery apply if available
    if celery_app is not None:
        async_res = health_ping_task.apply(kwargs={"echo": "eager_ping"})
        assert async_res.successful()
        assert async_res.result["status"] == "SUCCESS"
        assert async_res.result["echo"] == "eager_ping"

