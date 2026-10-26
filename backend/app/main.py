import uuid
import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from app.config import settings
from app.core.logging_config import setup_logging
from app.core.exceptions import BhumiSetuException
from app.routers import (
    auth_router,
    cases_router,
    parcels_router,
    documents_router,
    evidence_router,
    claims_router,
    findings_router,
    ai_router,
    landamin_router,
    reports_router,
    mcp_router,
    health_router
)

# Configure structured logging
setup_logging(settings.ENVIRONMENT)
logger = logging.getLogger("bhumisetu")

app = FastAPI(
    title="BhumiSetu Land Intelligence Platform API",
    description="Production-grade database and backend foundation for Indian land verification and intelligence.",
    version="1.2.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID & Audit context middleware
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# Error Handlers adhering to strict API contract
@app.exception_handler(BhumiSetuException)
async def bhumisetu_exception_handler(request: Request, exc: BhumiSetuException):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.warning(f"Domain error [{exc.code}]: {exc.message} (request_id={request_id})")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
            "request_id": request_id
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
        content={
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed.",
            "details": exc.errors(),
            "request_id": request_id
        }
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.error(f"Unhandled server error: {str(exc)} (request_id={request_id})", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected internal server error occurred.",
            "details": None,
            "request_id": request_id
        }
    )

from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
import os

@app.get("/", include_in_schema=False)
def root_redirect():
    return RedirectResponse(url="/ui/document-viewer")

# Health & Observability Router
app.include_router(health_router)

@app.get("/ui/document-viewer", tags=["UI"])
def document_viewer_ui():
    static_file = os.path.join(os.path.dirname(__file__), "static", "document_viewer.html")
    if os.path.exists(static_file):
        return FileResponse(static_file, media_type="text/html")
    return JSONResponse(status_code=404, content={"message": "Document viewer UI not found."})

# API v1 Router Registration
app.include_router(auth_router, prefix="/api/v1")
app.include_router(cases_router, prefix="/api/v1")
app.include_router(parcels_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(evidence_router, prefix="/api/v1")
app.include_router(claims_router, prefix="/api/v1")
app.include_router(findings_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(landamin_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(mcp_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")
