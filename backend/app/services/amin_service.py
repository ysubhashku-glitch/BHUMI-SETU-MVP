import uuid
import math
import hashlib
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from shapely.geometry import Polygon

from app.models.base import utc_now
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.models.case import Case, CaseParcel
from app.models.parcel import Parcel
from app.models.party import Party, PartyType
from app.models.field_survey import FieldSurvey
from app.models.field_task import FieldVerificationTask, TaskStatus, TaskPriority, ReviewOutcome
from app.models.finding import Finding, RequiredAction, Resolution, FindingStatus, ActionStatus
from app.models.evidence import Evidence, EvidenceType, AuthorityTier, CaseEvidence
from app.models.audit import AuditLog
from app.core.exceptions import (
    EntityNotFoundError,
    CrossTenantAccessError,
    ForbiddenError,
    DomainValidationError,
    StateTransitionError
)
from app.core.storage import get_document_storage, validate_upload_security
from app.schemas.field_task import (
    TaskCreateRequest,
    TaskAssignRequest,
    FieldReportSubmitRequest,
    TaskReviewRequest,
    EligibleWorkerResponse
)

SQM_PER_ACRE = 4046.8564224

# Allowed state transitions
VALID_STATE_TRANSITIONS: Dict[str, List[str]] = {
    TaskStatus.DRAFT: [TaskStatus.READY_FOR_ASSIGNMENT, TaskStatus.CANCELLED],
    TaskStatus.READY_FOR_ASSIGNMENT: [TaskStatus.ASSIGNED, TaskStatus.CANCELLED],
    TaskStatus.ASSIGNED: [TaskStatus.ACCEPTED, TaskStatus.DECLINED, TaskStatus.ASSIGNED, TaskStatus.CANCELLED],
    TaskStatus.DECLINED: [TaskStatus.READY_FOR_ASSIGNMENT, TaskStatus.ASSIGNED, TaskStatus.CANCELLED],
    TaskStatus.ACCEPTED: [TaskStatus.IN_PROGRESS, TaskStatus.ASSIGNED, TaskStatus.CANCELLED],
    TaskStatus.IN_PROGRESS: [TaskStatus.SUBMITTED, TaskStatus.CANCELLED],
    TaskStatus.SUBMITTED: [TaskStatus.UNDER_REVIEW, TaskStatus.REVISION_REQUESTED, TaskStatus.REVIEW_ACCEPTED, TaskStatus.REJECTED, TaskStatus.CANCELLED],
    TaskStatus.UNDER_REVIEW: [TaskStatus.REVIEW_ACCEPTED, TaskStatus.REVISION_REQUESTED, TaskStatus.REJECTED, TaskStatus.CLOSED],
    TaskStatus.REVISION_REQUESTED: [TaskStatus.IN_PROGRESS, TaskStatus.SUBMITTED, TaskStatus.CANCELLED],
    TaskStatus.REVIEW_ACCEPTED: [TaskStatus.CLOSED],
    TaskStatus.REJECTED: [TaskStatus.CLOSED, TaskStatus.READY_FOR_ASSIGNMENT],
    TaskStatus.CLOSED: [],
    TaskStatus.CANCELLED: []
}

def generate_task_number(db: Session) -> str:
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"FT-{today_str}-{short_uuid}"

def list_eligible_amins(db: Session, org_id: uuid.UUID) -> List[EligibleWorkerResponse]:
    """
    Returns list of eligible field Amins for assignment.
    Distinctly separates registered field personnel from independently verified credentials.
    """
    amins = db.query(User).filter(
        User.org_id == org_id,
        User.role == UserRole.FIELD_EXPERT,
        User.is_active == True
    ).all()

    result = []
    for amin in amins:
        # Count active tasks
        active_count = db.query(FieldVerificationTask).filter(
            FieldVerificationTask.assigned_amin_id == amin.user_id,
            FieldVerificationTask.status.in_([
                TaskStatus.ASSIGNED,
                TaskStatus.ACCEPTED,
                TaskStatus.IN_PROGRESS,
                TaskStatus.REVISION_REQUESTED
            ])
        ).count()

        result.append(EligibleWorkerResponse(
            user_id=amin.user_id,
            org_id=amin.org_id,
            full_name=amin.full_name,
            email=amin.email,
            phone_number=amin.phone_number,
            role=amin.role,
            is_active=amin.is_active,
            verified_qualifications=False,
            qualification_notes="Registered field personnel (Bhumi Setu field network; state credential verification independent)",
            active_tasks_count=active_count
        ))
    return result

def create_field_verification_task(
    db: Session,
    request: TaskCreateRequest,
    current_user: User
) -> FieldVerificationTask:
    """
    Creates a new field-verification request linked to case, parcel, or finding.
    """
    # 1. Verify case
    case = db.query(Case).filter(Case.case_id == request.case_id).first()
    if not case:
        raise EntityNotFoundError("Case", request.case_id)
    if case.org_id != current_user.org_id:
        raise CrossTenantAccessError("Cannot dispatch task for a case belonging to another organization.")

    # 2. Check permissions: Dispatcher or Admin or Case Operator
    if current_user.role not in [UserRole.ADMIN, UserRole.CASE_OPERATOR]:
        raise ForbiddenError("Only authorized dispatchers (CASE_OPERATOR or ADMIN) can create verification tasks.")

    # 3. Verify parcel if specified
    if request.parcel_id:
        parcel = db.query(Parcel).filter(Parcel.parcel_id == request.parcel_id).first()
        if not parcel:
            raise EntityNotFoundError("Parcel", request.parcel_id)
        if parcel.org_id != current_user.org_id:
            raise CrossTenantAccessError("Cannot reference parcel belonging to another organization.")

    # 4. Verify finding if specified
    if request.finding_id:
        finding = db.query(Finding).filter(Finding.finding_id == request.finding_id).first()
        if not finding:
            raise EntityNotFoundError("Finding", request.finding_id)
        if finding.case_id != request.case_id:
            raise DomainValidationError("Referenced finding does not belong to the specified case.")

    # 5. Verify action if specified
    if request.action_id:
        action = db.query(RequiredAction).filter(RequiredAction.action_id == request.action_id).first()
        if not action:
            raise EntityNotFoundError("RequiredAction", request.action_id)
        if action.case_id != request.case_id:
            raise DomainValidationError("Referenced action does not belong to the specified case.")

    task_number = generate_task_number(db)
    task = FieldVerificationTask(
        org_id=current_user.org_id,
        case_id=request.case_id,
        parcel_id=request.parcel_id,
        finding_id=request.finding_id,
        action_id=request.action_id,
        task_number=task_number,
        title=request.title,
        reason=request.reason,
        requested_activities=request.requested_activities,
        priority=request.priority,
        status=TaskStatus.READY_FOR_ASSIGNMENT,
        due_date=request.due_date,
        instructions=request.instructions,
        field_observations={},
        evidence_ids=[]
    )
    db.add(task)
    db.flush()

    # Audit Log
    audit = AuditLog(
        org_id=current_user.org_id,
        actor_party_id=None,
        action="CREATE_FIELD_TASK",
        entity_name="FIELD_TASK",
        entity_id=task.task_id,
        previous_state=None,
        new_state={
            "task_number": task_number,
            "status": TaskStatus.READY_FOR_ASSIGNMENT,
            "case_id": str(request.case_id),
            "parcel_id": str(request.parcel_id) if request.parcel_id else None,
            "finding_id": str(request.finding_id) if request.finding_id else None,
            "created_by": current_user.email
        }
    )
    db.add(audit)
    db.commit()
    db.refresh(task)
    return task

def assign_field_task(
    db: Session,
    task_id: uuid.UUID,
    request: TaskAssignRequest,
    current_user: User
) -> FieldVerificationTask:
    """
    Assigns or reassigns a verification task to an eligible field worker.
    """
    task = db.query(FieldVerificationTask).filter(FieldVerificationTask.task_id == task_id).first()
    if not task:
        raise EntityNotFoundError("FieldVerificationTask", task_id)
    if task.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    if current_user.role not in [UserRole.ADMIN, UserRole.CASE_OPERATOR]:
        raise ForbiddenError("Only authorized dispatchers can assign field tasks.")

    # Target worker
    amin = db.query(User).filter(User.user_id == request.amin_user_id).first()
    if not amin:
        raise EntityNotFoundError("User", request.amin_user_id)
    if amin.org_id != current_user.org_id:
        raise CrossTenantAccessError("Cannot assign field worker from another organization.")
    if amin.role != UserRole.FIELD_EXPERT:
        raise DomainValidationError(f"Target user role is '{amin.role}'; must be 'FIELD_EXPERT'.")
    if not amin.is_active:
        raise DomainValidationError("Cannot assign task to an inactive field worker.")

    # Validate state transition
    if task.status not in [TaskStatus.READY_FOR_ASSIGNMENT, TaskStatus.ASSIGNED, TaskStatus.DECLINED, TaskStatus.ACCEPTED]:
        raise StateTransitionError(task.status, TaskStatus.ASSIGNED, "Task cannot be assigned in its current state.")

    old_state = {
        "status": task.status,
        "assigned_amin_id": str(task.assigned_amin_id) if task.assigned_amin_id else None
    }

    task.assigned_amin_id = amin.user_id
    task.assigned_by_user_id = current_user.user_id
    task.assigned_at = utc_now()
    if request.due_date:
        task.due_date = request.due_date
    if request.instructions:
        task.instructions = request.instructions
    task.decline_reason = None
    task.status = TaskStatus.ASSIGNED

    audit = AuditLog(
        org_id=current_user.org_id,
        action="ASSIGN_FIELD_TASK",
        entity_name="FIELD_TASK",
        entity_id=task.task_id,
        previous_state=old_state,
        new_state={
            "status": TaskStatus.ASSIGNED,
            "assigned_amin_id": str(amin.user_id),
            "assigned_amin_name": amin.full_name,
            "assigned_by": current_user.email
        }
    )
    db.add(audit)
    db.commit()
    db.refresh(task)
    return task

def accept_field_task(
    db: Session,
    task_id: uuid.UUID,
    current_user: User
) -> FieldVerificationTask:
    """
    Assigned worker accepts the field task.
    """
    task = db.query(FieldVerificationTask).filter(FieldVerificationTask.task_id == task_id).first()
    if not task:
        raise EntityNotFoundError("FieldVerificationTask", task_id)
    if task.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    if task.assigned_amin_id != current_user.user_id and current_user.role != UserRole.ADMIN:
        raise ForbiddenError("You can only accept tasks specifically assigned to you.")

    if task.status != TaskStatus.ASSIGNED:
        raise StateTransitionError(task.status, TaskStatus.ACCEPTED, "Only tasks in 'ASSIGNED' state can be accepted.")

    task.status = TaskStatus.ACCEPTED
    audit = AuditLog(
        org_id=current_user.org_id,
        action="ACCEPT_FIELD_TASK",
        entity_name="FIELD_TASK",
        entity_id=task.task_id,
        previous_state={"status": TaskStatus.ASSIGNED},
        new_state={"status": TaskStatus.ACCEPTED, "accepted_by": current_user.email}
    )
    db.add(audit)
    db.commit()
    db.refresh(task)
    return task

def decline_field_task(
    db: Session,
    task_id: uuid.UUID,
    reason: str,
    current_user: User
) -> FieldVerificationTask:
    """
    Assigned worker declines the field task with a reason.
    """
    task = db.query(FieldVerificationTask).filter(FieldVerificationTask.task_id == task_id).first()
    if not task:
        raise EntityNotFoundError("FieldVerificationTask", task_id)
    if task.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    if task.assigned_amin_id != current_user.user_id and current_user.role != UserRole.ADMIN:
        raise ForbiddenError("You can only decline tasks specifically assigned to you.")

    if task.status != TaskStatus.ASSIGNED:
        raise StateTransitionError(task.status, TaskStatus.DECLINED, "Only tasks in 'ASSIGNED' state can be declined.")

    task.status = TaskStatus.DECLINED
    task.decline_reason = reason

    audit = AuditLog(
        org_id=current_user.org_id,
        action="DECLINE_FIELD_TASK",
        entity_name="FIELD_TASK",
        entity_id=task.task_id,
        previous_state={"status": TaskStatus.ASSIGNED},
        new_state={"status": TaskStatus.DECLINED, "decline_reason": reason, "declined_by": current_user.email}
    )
    db.add(audit)
    db.commit()
    db.refresh(task)
    return task

def start_field_visit(
    db: Session,
    task_id: uuid.UUID,
    current_user: User
) -> FieldVerificationTask:
    """
    Worker starts an authorized field visit.
    """
    task = db.query(FieldVerificationTask).filter(FieldVerificationTask.task_id == task_id).first()
    if not task:
        raise EntityNotFoundError("FieldVerificationTask", task_id)
    if task.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    if task.assigned_amin_id != current_user.user_id and current_user.role != UserRole.ADMIN:
        raise ForbiddenError("You can only start visits for tasks assigned to you.")

    if task.status not in [TaskStatus.ACCEPTED, TaskStatus.REVISION_REQUESTED]:
        raise StateTransitionError(task.status, TaskStatus.IN_PROGRESS, "Visit can only start from 'ACCEPTED' or 'REVISION_REQUESTED' state.")

    task.status = TaskStatus.IN_PROGRESS
    task.visit_started_at = utc_now()

    audit = AuditLog(
        org_id=current_user.org_id,
        action="START_FIELD_VISIT",
        entity_name="FIELD_TASK",
        entity_id=task.task_id,
        previous_state={"status": task.status},
        new_state={"status": TaskStatus.IN_PROGRESS, "visit_started_at": task.visit_started_at.isoformat()}
    )
    db.add(audit)
    db.commit()
    db.refresh(task)
    return task

def calculate_polygon_area_acres(boundary_points: List[Dict[str, Any]]) -> Tuple[Optional[float], Optional[float]]:
    """
    Computes area in square meters and acres from boundary points.
    Uses local planar approximation for WGS84 coordinates in Bihar latitude (~25.5 deg).
    Returns: (area_sqm, area_acres)
    """
    if len(boundary_points) < 3:
        return None, None

    coords = [(p.get("longitude", 0.0), p.get("latitude", 0.0)) for p in boundary_points]
    # Check if first and last are identical for closing
    if coords[0] != coords[-1]:
        coords.append(coords[0])

    avg_lat = sum(p.get("latitude", 0.0) for p in boundary_points) / len(boundary_points)
    lat_rad = math.radians(avg_lat)
    # 1 deg lat ≈ 110800m, 1 deg lon ≈ 111320m * cos(lat)
    m_per_deg_lat = 110800.0
    m_per_deg_lon = 111320.0 * math.cos(lat_rad)

    # Convert to local meters relative to first point
    origin_lon, origin_lat = coords[0]
    local_xy = []
    for lon, lat in coords:
        x = (lon - origin_lon) * m_per_deg_lon
        y = (lat - origin_lat) * m_per_deg_lat
        local_xy.append((x, y))

    try:
        poly = Polygon(local_xy)
        if not poly.is_valid:
            poly = poly.buffer(0)
        area_sqm = float(poly.area)
        area_acres = area_sqm / SQM_PER_ACRE
        return round(area_sqm, 2), round(area_acres, 4)
    except Exception:
        return None, None

def compare_field_with_cadastral(
    measured_area_acres: Optional[float],
    parcel: Optional[Parcel]
) -> Optional[Dict[str, Any]]:
    """
    Compares field-observed area with recorded cadastral area.
    Never overwrites authoritative cadastral geometry!
    """
    if not parcel or measured_area_acres is None:
        return None

    recorded_acres = float(parcel.recorded_area_acres)
    if recorded_acres <= 0:
        return None

    delta_acres = measured_area_acres - recorded_acres
    delta_percentage = (delta_acres / recorded_acres) * 100.0
    is_concordant = abs(delta_percentage) <= 5.0

    return {
        "recorded_cadastral_acres": recorded_acres,
        "field_measured_acres": measured_area_acres,
        "delta_acres": round(delta_acres, 4),
        "delta_percentage": round(delta_percentage, 2),
        "is_concordant": is_concordant,
        "comparison_method": "GNSS boundary walk local planar approximation vs Jamabandi/Bhu-Naksha recorded area",
        "legal_limitation": (
            "Field observation is indicative supporting evidence only. "
            "It does not automatically establish or modify authoritative revenue boundaries or court-decreed ownership."
        )
    }

def submit_field_report(
    db: Session,
    task_id: uuid.UUID,
    payload: FieldReportSubmitRequest,
    current_user: User
) -> FieldVerificationTask:
    """
    Worker submits completed field observations, GPS boundary, and narrative report.
    """
    task = db.query(FieldVerificationTask).filter(FieldVerificationTask.task_id == task_id).first()
    if not task:
        raise EntityNotFoundError("FieldVerificationTask", task_id)
    if task.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    if task.assigned_amin_id != current_user.user_id and current_user.role != UserRole.ADMIN:
        raise ForbiddenError("You can only submit reports for tasks assigned to you.")

    if task.status not in [TaskStatus.IN_PROGRESS, TaskStatus.ACCEPTED, TaskStatus.REVISION_REQUESTED]:
        raise StateTransitionError(task.status, TaskStatus.SUBMITTED, "Task is not in a submittable state.")

    # Auto-record visit start if not recorded
    if not task.visit_started_at:
        task.visit_started_at = utc_now()
    task.visit_completed_at = utc_now()

    # Calculate observed area from boundary points if provided
    boundary_dicts = [p.model_dump() for p in payload.boundary_points]
    area_sqm, calculated_acres = calculate_polygon_area_acres(boundary_dicts)
    measured_acres = payload.measured_area_acres if payload.measured_area_acres is not None else calculated_acres

    # Spatial comparison
    parcel = db.query(Parcel).filter(Parcel.parcel_id == task.parcel_id).first() if task.parcel_id else None
    spatial_comp = compare_field_with_cadastral(measured_acres, parcel)

    # Structured observations payload
    observations_data: Dict[str, Any] = {
        "narrative_report": payload.narrative_report,
        "gps_points": [p.model_dump() for p in payload.gps_points],
        "boundary_points": boundary_dicts,
        "calculated_area_sqm": area_sqm,
        "measured_area_acres": measured_acres,
        "ground_neighbors": payload.ground_neighbors.model_dump() if payload.ground_neighbors else None,
        "road_access": payload.road_access.model_dump() if payload.road_access else None,
        "physical_possessor": payload.physical_possessor.model_dump() if payload.physical_possessor else None,
        "site_conditions": payload.site_conditions,
        "client_observation_id": payload.client_observation_id,
        "incomplete_reason": payload.incomplete_reason,
        "spatial_comparison": spatial_comp,
        "device_accuracy_notice": "Positional readings reflect field GNSS receiver; not certified as DGPS/ETS survey grade unless accompanied by calibration records."
    }

    task.field_observations = observations_data
    if payload.evidence_ids:
        # Merge evidence IDs preserving unique
        existing_evidence = set(task.evidence_ids or [])
        for eid in payload.evidence_ids:
            existing_evidence.add(str(eid))
        task.evidence_ids = list(existing_evidence)

    task.status = TaskStatus.SUBMITTED

    audit = AuditLog(
        org_id=current_user.org_id,
        action="SUBMIT_FIELD_REPORT",
        entity_name="FIELD_TASK",
        entity_id=task.task_id,
        previous_state={"status": TaskStatus.IN_PROGRESS},
        new_state={
            "status": TaskStatus.SUBMITTED,
            "measured_area_acres": measured_acres,
            "submitted_by": current_user.email
        }
    )
    db.add(audit)
    db.commit()
    db.refresh(task)
    return task

def review_field_report(
    db: Session,
    task_id: uuid.UUID,
    request: TaskReviewRequest,
    current_user: User
) -> FieldVerificationTask:
    """
    Reviewer evaluates submitted field evidence.
    Accepts, requests revision, or rejects.
    """
    task = db.query(FieldVerificationTask).filter(FieldVerificationTask.task_id == task_id).first()
    if not task:
        raise EntityNotFoundError("FieldVerificationTask", task_id)
    if task.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    if current_user.role not in [UserRole.LEGAL_REVIEWER, UserRole.REVIEWER, UserRole.ADMIN]:
        raise ForbiddenError("Only authorized reviewers can assess field reports.")

    # Conflict of interest: Reviewer cannot approve their own submission
    if task.assigned_amin_id == current_user.user_id and current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Reviewers cannot assess tasks for which they were the assigned field worker.")

    if task.status not in [TaskStatus.SUBMITTED, TaskStatus.UNDER_REVIEW]:
        raise StateTransitionError(task.status, request.outcome, "Only submitted reports can be reviewed.")

    task.reviewer_user_id = current_user.user_id
    task.reviewed_at = utc_now()
    task.review_notes = request.review_notes

    outcome = request.outcome.upper()
    if outcome == ReviewOutcome.ACCEPT:
        task.status = TaskStatus.REVIEW_ACCEPTED
        task.review_status = ReviewOutcome.ACCEPT

        # If requested, create or update FieldSurvey record
        if request.create_field_survey_record and task.parcel_id:
            create_or_link_field_survey(db, task, current_user)

        # If task was triggered by an action/finding, mark action completed
        if task.finding_id and task.action_id:
            resolve_task_finding(db, task, current_user)

    elif outcome == ReviewOutcome.REVISION_REQUESTED:
        task.status = TaskStatus.REVISION_REQUESTED
        task.review_status = ReviewOutcome.REVISION_REQUESTED
    elif outcome == ReviewOutcome.REJECT:
        task.status = TaskStatus.REJECTED
        task.review_status = ReviewOutcome.REJECT
    elif outcome == ReviewOutcome.INCONCLUSIVE:
        task.status = TaskStatus.UNDER_REVIEW
        task.review_status = ReviewOutcome.INCONCLUSIVE
    else:
        raise DomainValidationError(f"Invalid review outcome '{request.outcome}'. Allowed: ACCEPT, REVISION_REQUESTED, REJECT, INCONCLUSIVE.")

    audit = AuditLog(
        org_id=current_user.org_id,
        action="REVIEW_FIELD_REPORT",
        entity_name="FIELD_TASK",
        entity_id=task.task_id,
        previous_state={"status": TaskStatus.SUBMITTED},
        new_state={
            "status": task.status,
            "review_status": task.review_status,
            "reviewer": current_user.email,
            "review_notes": request.review_notes
        }
    )
    db.add(audit)
    db.commit()
    db.refresh(task)
    return task

def create_or_link_field_survey(db: Session, task: FieldVerificationTask, current_user: User):
    """
    Creates an official FieldSurvey record from reviewed field observations.
    """
    obs = task.field_observations or {}
    measured_acres = obs.get("measured_area_acres", 0.0)
    if measured_acres is None:
        measured_acres = 0.0

    neighbors = obs.get("ground_neighbors") or {}
    road = obs.get("road_access") or {}
    possessor = obs.get("physical_possessor") or {}

    # Find or create a surveyor party for the assigned Amin
    amin_user = db.query(User).filter(User.user_id == task.assigned_amin_id).first()
    party_id = None
    if amin_user:
        party = db.query(Party).filter(
            Party.org_id == task.org_id,
            Party.primary_name == amin_user.full_name
        ).first()
        if not party:
            party = Party(
                org_id=task.org_id,
                party_type=PartyType.PERSON,
                primary_name=amin_user.full_name,
                phone_number=amin_user.phone_number
            )
            db.add(party)
            db.flush()
        party_id = party.party_id

    # Fallback to case client if no party found
    if not party_id:
        case = db.query(Case).filter(Case.case_id == task.case_id).first()
        party_id = case.primary_client_party_id if case else uuid.uuid4()

    survey = FieldSurvey(
        case_id=task.case_id,
        parcel_id=task.parcel_id,
        surveyor_party_id=party_id,
        gnss_receiver_model="BHUMI_SETU_FIELD_APP_V1",
        measured_area_acres=measured_acres,
        measured_boundary_geometry="SRID=4326;POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))",
        north_ground_neighbor=neighbors.get("north"),
        south_ground_neighbor=neighbors.get("south"),
        east_ground_neighbor=neighbors.get("east"),
        west_ground_neighbor=neighbors.get("west"),
        road_access_type=road.get("road_type", "PUCCA_ROAD"),
        road_frontage_feet=road.get("frontage_feet"),
        physical_possessor_name=possessor.get("name"),
        completed_at=task.visit_completed_at or utc_now()
    )
    db.add(survey)
    db.flush()
    task.survey_id = survey.survey_id

def resolve_task_finding(db: Session, task: FieldVerificationTask, current_user: User):
    """
    Marks the originating RequiredAction completed and updates Finding status.
    """
    action = db.query(RequiredAction).filter(RequiredAction.action_id == task.action_id).first()
    if action:
        action.status = ActionStatus.COMPLETED
        action.resolution_notes = f"Field verification completed via task {task.task_number}: {task.review_notes}"
        action.resolved_at = utc_now()

    finding = db.query(Finding).filter(Finding.finding_id == task.finding_id).first()
    if finding:
        # Check if any remaining open actions
        open_count = db.query(RequiredAction).filter(
            RequiredAction.finding_id == finding.finding_id,
            RequiredAction.action_id != task.action_id,
            RequiredAction.status != ActionStatus.COMPLETED
        ).count()
        if open_count == 0:
            finding.status = FindingStatus.RESOLVED

def cancel_field_task(
    db: Session,
    task_id: uuid.UUID,
    reason: str,
    current_user: User
) -> FieldVerificationTask:
    """
    Cancels a field task with a recorded reason.
    """
    task = db.query(FieldVerificationTask).filter(FieldVerificationTask.task_id == task_id).first()
    if not task:
        raise EntityNotFoundError("FieldVerificationTask", task_id)
    if task.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    if current_user.role not in [UserRole.ADMIN, UserRole.CASE_OPERATOR]:
        raise ForbiddenError("Only dispatchers and administrators can cancel field verification tasks.")

    if task.status in [TaskStatus.CLOSED, TaskStatus.REVIEW_ACCEPTED]:
        raise StateTransitionError(task.status, TaskStatus.CANCELLED, "Cannot cancel a task that has already been accepted or closed.")

    task.status = TaskStatus.CANCELLED
    task.cancellation_reason = reason

    audit = AuditLog(
        org_id=current_user.org_id,
        action="CANCEL_FIELD_TASK",
        entity_name="FIELD_TASK",
        entity_id=task.task_id,
        previous_state={"status": task.status},
        new_state={"status": TaskStatus.CANCELLED, "cancellation_reason": reason, "cancelled_by": current_user.email}
    )
    db.add(audit)
    db.commit()
    db.refresh(task)
    return task

def upload_field_photo_evidence(
    db: Session,
    task_id: uuid.UUID,
    file_bytes: bytes,
    filename: str,
    declared_mime: str,
    current_user: User,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    accuracy_meters: Optional[float] = None
) -> Evidence:
    """
    Validates, hashes, stores, and registers a field photo as an Evidence record.
    """
    task = db.query(FieldVerificationTask).filter(FieldVerificationTask.task_id == task_id).first()
    if not task:
        raise EntityNotFoundError("FieldVerificationTask", task_id)
    if task.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    if task.assigned_amin_id != current_user.user_id and current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Only the assigned field worker can upload photo evidence for this task.")

    # 1. Security & MIME validation
    detected_mime, sanitized_name, file_size = validate_upload_security(
        file_bytes, filename, declared_mime, max_size_bytes=25 * 1024 * 1024
    )

    # Strict magic bytes verification for field photos
    is_valid_image = False
    if file_bytes.startswith(b"\xff\xd8\xff"):  # JPEG
        is_valid_image = True
    elif file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):  # PNG
        is_valid_image = True
    elif len(file_bytes) > 12 and file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP":  # WEBP
        is_valid_image = True

    if not is_valid_image:
        raise DomainValidationError("Invalid file signature: Content bytes do not match recognized image format (JPEG/PNG/WEBP).")

    # 2. SHA-256 hash
    sha256 = hashlib.sha256(file_bytes).hexdigest()

    # 3. Store via DocumentStorage
    storage = get_document_storage()
    storage_res = storage.put(file_bytes, sanitized_name, detected_mime, metadata={"task_id": str(task_id)})

    # 4. Create Evidence Record
    evidence = Evidence(
        evidence_type=EvidenceType.FIELD_PHOTO,
        authority_tier=AuthorityTier.FIELD_OBSERVATION,
        source_name=f"Field Photo - {sanitized_name}",
        storage_uri=storage_res["storage_reference"],
        sha256_hash=sha256,
        evidence_metadata={
            "task_id": str(task_id),
            "task_number": task.task_number,
            "original_filename": sanitized_name,
            "mime_type": detected_mime,
            "file_size_bytes": file_size,
            "latitude": latitude,
            "longitude": longitude,
            "accuracy_meters": accuracy_meters,
            "uploader_user_id": str(current_user.user_id),
            "uploader_email": current_user.email
        }
    )
    db.add(evidence)
    db.flush()

    # Link to CaseEvidence
    case_ev = CaseEvidence(case_id=task.case_id, evidence_id=evidence.evidence_id)
    db.add(case_ev)

    # Link to task
    task_ev = list(task.evidence_ids or [])
    task_ev.append(str(evidence.evidence_id))
    task.evidence_ids = task_ev

    audit = AuditLog(
        org_id=current_user.org_id,
        action="UPLOAD_FIELD_PHOTO",
        entity_name="EVIDENCE",
        entity_id=evidence.evidence_id,
        new_state={
            "task_id": str(task_id),
            "sha256_hash": sha256,
            "uploaded_by": current_user.email
        }
    )
    db.add(audit)
    db.commit()
    db.refresh(evidence)
    return evidence
