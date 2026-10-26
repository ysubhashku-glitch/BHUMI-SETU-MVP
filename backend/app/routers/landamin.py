import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.field_task import FieldVerificationTask
from app.core.dependencies import get_current_user, require_roles
from app.core.exceptions import EntityNotFoundError, CrossTenantAccessError, ForbiddenError
from app.schemas.field_task import (
    TaskCreateRequest,
    TaskAssignRequest,
    TaskDeclineRequest,
    TaskCancelRequest,
    FieldReportSubmitRequest,
    TaskReviewRequest,
    FieldTaskResponse,
    FieldTaskDetailResponse,
    EligibleWorkerResponse
)
from app.services.amin_service import (
    create_field_verification_task,
    list_eligible_amins,
    assign_field_task,
    accept_field_task,
    decline_field_task,
    start_field_visit,
    submit_field_report,
    review_field_report,
    cancel_field_task,
    upload_field_photo_evidence
)

router = APIRouter(prefix="/landamin", tags=["LandAmin Field Dispatcher"])

def _build_task_response(task: FieldVerificationTask) -> FieldTaskResponse:
    return FieldTaskResponse.model_validate(task)

def _build_task_detail_response(task: FieldVerificationTask) -> FieldTaskDetailResponse:
    obs = task.field_observations or {}
    evidence_uuids = []
    for eid in (task.evidence_ids or []):
        try:
            evidence_uuids.append(uuid.UUID(str(eid)))
        except (ValueError, TypeError):
            pass

    return FieldTaskDetailResponse(
        task_id=task.task_id,
        org_id=task.org_id,
        case_id=task.case_id,
        parcel_id=task.parcel_id,
        finding_id=task.finding_id,
        action_id=task.action_id,
        survey_id=task.survey_id,
        task_number=task.task_number,
        title=task.title,
        reason=task.reason,
        requested_activities=task.requested_activities or [],
        priority=task.priority,
        status=task.status,
        assigned_amin_id=task.assigned_amin_id,
        assigned_by_user_id=task.assigned_by_user_id,
        reviewer_user_id=task.reviewer_user_id,
        assigned_at=task.assigned_at,
        due_date=task.due_date,
        instructions=task.instructions,
        decline_reason=task.decline_reason,
        cancellation_reason=task.cancellation_reason,
        visit_started_at=task.visit_started_at,
        visit_completed_at=task.visit_completed_at,
        review_status=task.review_status,
        review_notes=task.review_notes,
        reviewed_at=task.reviewed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
        field_observations=obs,
        evidence_ids=evidence_uuids,
        boundary_comparison=obs.get("spatial_comparison")
    )


# =====================================================================
# Dispatcher Dashboard Endpoints
# =====================================================================

@router.post("/tasks", response_model=FieldTaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    request: TaskCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.CASE_OPERATOR))
):
    """
    Creates a new field-verification request linked to case, parcel, or discrepancy finding.
    """
    task = create_field_verification_task(db, request, current_user)
    return _build_task_response(task)

@router.get("/tasks", response_model=List[FieldTaskResponse])
def list_tasks(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = None,
    case_id: Optional[uuid.UUID] = None,
    parcel_id: Optional[uuid.UUID] = None,
    assigned_amin_id: Optional[uuid.UUID] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists field-verification requests within the tenant with optional status/priority filtering.
    """
    query = db.query(FieldVerificationTask).filter(FieldVerificationTask.org_id == current_user.org_id)
    if status_filter:
        query = query.filter(FieldVerificationTask.status == status_filter.upper())
    if priority:
        query = query.filter(FieldVerificationTask.priority == priority.upper())
    if case_id:
        query = query.filter(FieldVerificationTask.case_id == case_id)
    if parcel_id:
        query = query.filter(FieldVerificationTask.parcel_id == parcel_id)
    if assigned_amin_id:
        query = query.filter(FieldVerificationTask.assigned_amin_id == assigned_amin_id)

    tasks = query.order_by(FieldVerificationTask.created_at.desc()).offset(offset).limit(limit).all()
    return [_build_task_response(t) for t in tasks]

@router.get("/tasks/{task_id}", response_model=FieldTaskDetailResponse)
def get_task_detail(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves full details of a field-verification task including observations and boundary comparison.
    """
    task = db.query(FieldVerificationTask).filter(FieldVerificationTask.task_id == task_id).first()
    if not task:
        raise EntityNotFoundError("FieldVerificationTask", task_id)
    if task.org_id != current_user.org_id:
        raise CrossTenantAccessError()
    return _build_task_detail_response(task)

@router.post("/tasks/{task_id}/assign", response_model=FieldTaskResponse)
def assign_task(
    task_id: uuid.UUID,
    request: TaskAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.CASE_OPERATOR))
):
    """
    Assigns or reassigns a verification task to an eligible field worker.
    """
    task = assign_field_task(db, task_id, request, current_user)
    return _build_task_response(task)

@router.post("/tasks/{task_id}/cancel", response_model=FieldTaskResponse)
def cancel_task(
    task_id: uuid.UUID,
    request: TaskCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.CASE_OPERATOR))
):
    """
    Cancels an active or pending field verification task with a recorded reason.
    """
    task = cancel_field_task(db, task_id, request.reason, current_user)
    return _build_task_response(task)

@router.post("/tasks/{task_id}/review", response_model=FieldTaskDetailResponse)
def review_task(
    task_id: uuid.UUID,
    request: TaskReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.LEGAL_REVIEWER, UserRole.REVIEWER, UserRole.ADMIN))
):
    """
    Reviews submitted field observations. Can ACCEPT, REQUEST_REVISION, REJECT, or mark INCONCLUSIVE.
    """
    task = review_field_report(db, task_id, request, current_user)
    return _build_task_detail_response(task)

@router.get("/workers/eligible", response_model=List[EligibleWorkerResponse])
def get_eligible_workers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.CASE_OPERATOR))
):
    """
    Lists field Amins eligible for task assignment in the caller's organization.
    """
    return list_eligible_amins(db, current_user.org_id)


# =====================================================================
# Mobile Field Worker Endpoints
# =====================================================================

@router.get("/mobile/my-tasks", response_model=List[FieldTaskResponse])
def get_my_assigned_tasks(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FIELD_EXPERT, UserRole.ADMIN))
):
    """
    Mobile endpoint for field worker to retrieve tasks assigned to them.
    """
    query = db.query(FieldVerificationTask).filter(
        FieldVerificationTask.org_id == current_user.org_id,
        FieldVerificationTask.assigned_amin_id == current_user.user_id
    )
    if status_filter:
        query = query.filter(FieldVerificationTask.status == status_filter.upper())

    tasks = query.order_by(FieldVerificationTask.created_at.desc()).all()
    return [_build_task_response(t) for t in tasks]

@router.get("/mobile/tasks/{task_id}", response_model=FieldTaskDetailResponse)
def get_mobile_task_detail(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FIELD_EXPERT, UserRole.ADMIN))
):
    """
    Mobile endpoint to retrieve assigned task details and permitted attachments.
    """
    task = db.query(FieldVerificationTask).filter(FieldVerificationTask.task_id == task_id).first()
    if not task:
        raise EntityNotFoundError("FieldVerificationTask", task_id)
    if task.org_id != current_user.org_id:
        raise CrossTenantAccessError()
    if task.assigned_amin_id != current_user.user_id and current_user.role != UserRole.ADMIN:
        raise ForbiddenError("You can only access tasks assigned to you.")

    return _build_task_detail_response(task)

@router.post("/mobile/tasks/{task_id}/accept", response_model=FieldTaskResponse)
def accept_task_assignment(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FIELD_EXPERT, UserRole.ADMIN))
):
    """
    Assigned worker accepts the field assignment.
    """
    task = accept_field_task(db, task_id, current_user)
    return _build_task_response(task)

@router.post("/mobile/tasks/{task_id}/decline", response_model=FieldTaskResponse)
def decline_task_assignment(
    task_id: uuid.UUID,
    request: TaskDeclineRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FIELD_EXPERT, UserRole.ADMIN))
):
    """
    Assigned worker declines the assignment with a reason.
    """
    task = decline_field_task(db, task_id, request.reason, current_user)
    return _build_task_response(task)

@router.post("/mobile/tasks/{task_id}/start-visit", response_model=FieldTaskResponse)
def start_visit(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FIELD_EXPERT, UserRole.ADMIN))
):
    """
    Records the start of an on-site field inspection visit.
    """
    task = start_field_visit(db, task_id, current_user)
    return _build_task_response(task)

@router.post("/mobile/tasks/{task_id}/photos", status_code=status.HTTP_201_CREATED)
async def upload_photo(
    task_id: uuid.UUID,
    file: UploadFile = File(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    accuracy_meters: Optional[float] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FIELD_EXPERT, UserRole.ADMIN))
):
    """
    Uploads a field inspection photograph, validates MIME & SHA-256, and links to task evidence.
    """
    file_bytes = await file.read()
    evidence = upload_field_photo_evidence(
        db=db,
        task_id=task_id,
        file_bytes=file_bytes,
        filename=file.filename or "field_photo.jpg",
        declared_mime=file.content_type or "image/jpeg",
        current_user=current_user,
        latitude=latitude,
        longitude=longitude,
        accuracy_meters=accuracy_meters
    )
    return {
        "evidence_id": str(evidence.evidence_id),
        "source_name": evidence.source_name,
        "storage_uri": evidence.storage_uri,
        "sha256_hash": evidence.sha256_hash,
        "captured_at": evidence.captured_at.isoformat() if evidence.captured_at else None,
        "evidence_metadata": evidence.evidence_metadata
    }

@router.post("/mobile/tasks/{task_id}/submit", response_model=FieldTaskDetailResponse)
def submit_report(
    task_id: uuid.UUID,
    payload: FieldReportSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FIELD_EXPERT, UserRole.ADMIN))
):
    """
    Worker submits final structured observations, GPS points, Chauhaddi neighbors, and narrative report.
    """
    task = submit_field_report(db, task_id, payload, current_user)
    return _build_task_detail_response(task)
