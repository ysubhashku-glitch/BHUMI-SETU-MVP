import uuid
import time
import logging
from typing import Dict, Any, Optional

from app.config import settings
from app.database import SessionLocal
from app.models.evidence import DocumentVersion, DocumentProcessingStatus
from app.models.user import User
from app.schemas.report import ReportGenerateRequest

logger = logging.getLogger("bhumisetu.worker")

try:
    from celery import Celery, Task
    CELERY_AVAILABLE = True
except ImportError:
    Celery = None
    Task = object
    CELERY_AVAILABLE = False


class BaseBhumiSetuTask(Task if CELERY_AVAILABLE else object):
    """
    Base Celery task providing automatic DB session cleanup,
    exponential retry backoff, and structured logging.
    """
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 60
    retry_jitter = True
    max_retries = 3

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task [{self.name}] failed permanently (task_id={task_id}): {exc}")


def create_celery_app():
    if not CELERY_AVAILABLE:
        return None

    app = Celery(
        "bhumisetu",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND
    )

    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_reject_on_worker_lost=True,
        task_default_queue="default",
        task_routes={
            "app.worker.process_document_ocr_task": {"queue": "ocr_queue"},
            "app.worker.generate_report_task": {"queue": "report_queue"},
        }
    )
    return app


celery_app = create_celery_app()


from sqlalchemy.orm import Session


def process_document_ocr_task_logic(
    document_id: str,
    version_id: str,
    case_id: str,
    user_id: str,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Core business logic for asynchronous document OCR and candidate claim extraction.
    Ensures safe DB session lifecycle, bounded retries, and idempotency.
    """
    logger.info(f"Starting OCR task for document_id={document_id}, version_id={version_id}")
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        doc_uuid = uuid.UUID(document_id)
        ver_uuid = uuid.UUID(version_id)
        case_uuid = uuid.UUID(case_id)
        user_uuid = uuid.UUID(user_id)

        # Idempotency check: don't re-process if already COMPLETED
        version = db.query(DocumentVersion).filter(DocumentVersion.version_id == ver_uuid).first()
        if not version:
            logger.error(f"DocumentVersion {version_id} not found.")
            return {"status": "FAILED", "error": "DOCUMENT_VERSION_NOT_FOUND"}

        if version.processing_status in (DocumentProcessingStatus.PROCESSED, DocumentProcessingStatus.EXTRACTION_COMPLETE, "COMPLETED"):
            logger.info(f"DocumentVersion {version_id} already marked processed. Skipping.")
            return {"status": "SKIPPED", "reason": "ALREADY_COMPLETED", "version_id": version_id}

        from app.services.document_pipeline import DocumentPipelineService
        from app.models.evidence import ExtractedField
        from app.models.claim import CandidateClaim

        processed_version = DocumentPipelineService.execute_pipeline(
            document_id=doc_uuid,
            version_id=ver_uuid,
            db=db,
            case_id=case_uuid
        )

        field_count = db.query(ExtractedField).filter(ExtractedField.version_id == ver_uuid).count()
        claim_count = db.query(CandidateClaim).filter(CandidateClaim.version_id == ver_uuid).count()

        logger.info(f"Successfully finished OCR task for document_id={document_id}")
        return {
            "status": "SUCCESS",
            "document_id": document_id,
            "version_id": version_id,
            "extracted_fields_count": field_count,
            "claims_count": claim_count
        }
    except Exception as exc:
        if close_db:
            db.rollback()
        logger.error(f"Failed OCR task execution for document {document_id}: {str(exc)}", exc_info=True)
        raise exc
    finally:
        if close_db:
            db.close()


def generate_report_task_logic(
    request_data: Dict[str, Any],
    user_id: str,
    org_id: str,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Core business logic for asynchronous Land Intelligence Report compilation.
    """
    logger.info(f"Starting report generation task for case_id={request_data.get('case_id')}")
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        user_uuid = uuid.UUID(user_id)
        user = db.query(User).filter(User.user_id == user_uuid).first()
        if not user:
            logger.error(f"User {user_id} not found for report generation task.")
            return {"status": "FAILED", "error": "USER_NOT_FOUND"}

        from app.services.report_service import generate_and_store_report
        req = ReportGenerateRequest(**request_data)
        report = generate_and_store_report(db, req, user)

        logger.info(f"Successfully generated report_id={report.report_id}")
        return {
            "status": "SUCCESS",
            "report_id": str(report.report_id),
            "report_number": report.report_number,
            "sha256_hash": report.sha256_hash,
            "file_size_bytes": report.file_size_bytes
        }
    except Exception as exc:
        if close_db:
            db.rollback()
        logger.error(f"Failed report generation task: {str(exc)}", exc_info=True)
        raise exc
    finally:
        if close_db:
            db.close()


def health_ping_task_logic(echo: str = "ping") -> Dict[str, Any]:
    """
    Lightweight, deterministic test task used for staging integration validation.
    Verifies that worker can consume from queue and write to result backend.
    """
    return {
        "status": "SUCCESS",
        "echo": echo,
        "timestamp": time.time(),
        "worker_name": "bhumisetu_staging_worker"
    }


# Register Celery task decorators if Celery is installed
if celery_app:
    @celery_app.task(base=BaseBhumiSetuTask, bind=True, name="app.worker.health_ping_task")
    def health_ping_task(self, echo: str = "ping"):
        return health_ping_task_logic(echo)

    @celery_app.task(base=BaseBhumiSetuTask, bind=True, name="app.worker.process_document_ocr_task")
    def process_document_ocr_task(self, document_id: str, version_id: str, case_id: str, user_id: str):
        return process_document_ocr_task_logic(document_id, version_id, case_id, user_id)

    @celery_app.task(base=BaseBhumiSetuTask, bind=True, name="app.worker.generate_report_task")
    def generate_report_task(self, request_data: Dict[str, Any], user_id: str, org_id: str):
        return generate_report_task_logic(request_data, user_id, org_id)
else:
    # Fallback callable stubs for environments without Celery
    def health_ping_task(echo: str = "ping"):
        return health_ping_task_logic(echo)

    def process_document_ocr_task(document_id: str, version_id: str, case_id: str, user_id: str):
        return process_document_ocr_task_logic(document_id, version_id, case_id, user_id)

    def generate_report_task(request_data: Dict[str, Any], user_id: str, org_id: str):
        return generate_report_task_logic(request_data, user_id, org_id)

