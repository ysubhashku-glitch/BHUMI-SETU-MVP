import os
import time
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect

from app.database import get_db, engine
from app.config import settings
from app.core.storage import get_document_storage

router = APIRouter(tags=["Health & Observability"])

START_TIME = time.time()


@router.get("/health", tags=["Health & Observability"])
def legacy_health_check():
    """
    Backwards-compatible legacy health endpoint.
    """
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": "1.2.0",
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": round(time.time() - START_TIME, 2)
    }


@router.get("/health/live", tags=["Health & Observability"])
def liveness_probe():
    """
    Lightweight Kubernetes / Container liveness probe.
    Returns 200 if the process is up and accepting HTTP traffic.
    """
    return {
        "status": "alive",
        "timestamp": time.time(),
        "uptime_seconds": round(time.time() - START_TIME, 2)
    }


@router.get("/health/ready", tags=["Health & Observability"])
def readiness_probe(response: Response, db: Session = Depends(get_db)):
    """
    Comprehensive readiness probe evaluating critical and optional dependencies:
    - Database connectivity (Critical)
    - Database schema & migrations (Critical)
    - PostGIS spatial extensions (Optional/Conditional)
    - Storage Vault accessibility (Critical)
    - Redis & Celery broker (Optional in dev, Critical in async staging)
    - OCR & PDF generation libraries (Critical)

    Returns:
    - 200 "ready": All components healthy.
    - 200 "degraded": Critical components healthy, optional components unavailable.
    - 503 "unready": One or more critical components unavailable.
    """
    checks: Dict[str, Dict[str, Any]] = {}
    is_ready = True
    is_degraded = False

    # 1. Database Connectivity (Critical)
    try:
        db.execute(text("SELECT 1"))
        dialect_name = db.bind.dialect.name if db.bind else engine.dialect.name
        checks["database"] = {"status": "healthy", "dialect": dialect_name}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        is_ready = False

    # 2. Database Schema Availability (Critical)
    try:
        target_bind = db.bind or engine
        inspector = inspect(target_bind)
        tables = set(inspector.get_table_names())
        required_tables = {"organizations", "users", "cases", "parcels", "evidence"}
        missing = required_tables - tables
        if missing:
            checks["schema"] = {"status": "unhealthy", "missing_tables": sorted(list(missing))}
            is_ready = False
        else:
            checks["schema"] = {
                "status": "healthy",
                "table_count": len(tables),
                "has_alembic": "alembic_version" in tables
            }
    except Exception as e:
        checks["schema"] = {"status": "unhealthy", "error": str(e)}
        is_ready = False

    # 3. PostGIS Extension (Conditional: checked if PostgreSQL)
    current_dialect = db.bind.dialect.name if db.bind else engine.dialect.name
    if current_dialect == "postgresql":
        try:
            version_res = db.execute(text("SELECT PostGIS_Version();")).scalar()
            checks["postgis"] = {"status": "healthy", "version": version_res}
        except Exception as e:
            checks["postgis"] = {"status": "unhealthy", "error": str(e)}
            # If PostgreSQL is configured, PostGIS is required for spatial ops
            is_ready = False
    else:
        checks["postgis"] = {"status": "skipped", "reason": "non-postgresql dialect (sqlite fallback)"}

    # 4. Storage Vault Readiness (Critical)
    try:
        storage = get_document_storage()
        if settings.STORAGE_ADAPTER == "local":
            storage_dir = settings.STORAGE_DIR
            os.makedirs(storage_dir, exist_ok=True)
            is_writable = os.access(storage_dir, os.W_OK)
            checks["storage"] = {
                "status": "healthy" if is_writable else "unhealthy",
                "adapter": "local",
                "path": storage_dir,
                "writable": is_writable
            }
            if not is_writable:
                is_ready = False
        elif settings.STORAGE_ADAPTER in ("s3", "minio"):
            bucket = getattr(storage, "bucket_name", None)
            checks["storage"] = {
                "status": "configured" if bucket else "unhealthy",
                "adapter": settings.STORAGE_ADAPTER,
                "bucket": bucket
            }
            if not bucket:
                is_ready = False
    except Exception as e:
        checks["storage"] = {"status": "unhealthy", "error": str(e)}
        is_ready = False

    # 5. Redis Connectivity (Optional in dev, required if ASYNC_PROCESSING=True)
    try:
        import redis
        r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=1.0)
        r.ping()
        checks["redis"] = {"status": "healthy", "url": settings.REDIS_URL.split("@")[-1]}
    except Exception as e:
        status_label = "unhealthy" if settings.ASYNC_PROCESSING else "unavailable"
        checks["redis"] = {"status": status_label, "error": str(e), "async_enabled": settings.ASYNC_PROCESSING}
        if settings.ASYNC_PROCESSING:
            is_ready = False
        else:
            is_degraded = True

    # 6. Celery Worker (Optional in dev, required if ASYNC_PROCESSING=True)
    try:
        from app.worker import celery_app
        if celery_app:
            checks["celery"] = {"status": "configured", "broker": settings.CELERY_BROKER_URL.split("@")[-1]}
        else:
            checks["celery"] = {"status": "disabled", "reason": "celery_app not initialized"}
    except Exception as e:
        checks["celery"] = {"status": "unavailable", "error": str(e)}
        if settings.ASYNC_PROCESSING:
            is_ready = False
        else:
            is_degraded = True

    # 7. Document OCR & PDF Generator Engine Capabilities (Critical)
    try:
        import fpdf
        import qrcode
        import PIL
        checks["document_engines"] = {
            "status": "healthy",
            "pdf_renderer": getattr(fpdf, "__version__", "installed"),
            "qr_generator": getattr(qrcode, "__version__", "installed"),
            "imaging": getattr(PIL, "__version__", "installed")
        }
    except Exception as e:
        checks["document_engines"] = {"status": "unhealthy", "error": str(e)}
        is_ready = False

    # Status aggregation
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        overall_status = "unready"
    elif is_degraded:
        response.status_code = status.HTTP_200_OK
        overall_status = "degraded"
    else:
        response.status_code = status.HTTP_200_OK
        overall_status = "ready"

    return {
        "status": overall_status,
        "environment": settings.ENVIRONMENT,
        "timestamp": time.time(),
        "checks": checks
    }
