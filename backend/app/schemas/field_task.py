import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from app.models.field_task import TaskPriority, TaskStatus, ReviewOutcome

class GPSPointObservation(BaseModel):
    latitude: float = Field(..., description="WGS84 Latitude between -90 and 90")
    longitude: float = Field(..., description="WGS84 Longitude between -180 and 180")
    altitude_meters: Optional[float] = None
    accuracy_meters: Optional[float] = Field(None, description="Reported GNSS horizontal accuracy in meters")
    crs: str = Field("EPSG:4326", description="Coordinate Reference System, e.g. EPSG:4326 or EPSG:32645")
    timestamp: Optional[datetime] = None
    point_type: str = Field("BOUNDARY_POINT", description="Point classification: CORNER, BOUNDARY_POINT, LANDMARK, ACCESS_POINT")
    label: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("latitude")
    @classmethod
    def validate_lat(cls, v: float) -> float:
        if v < -90.0 or v > 90.0:
            raise ValueError(f"Latitude {v} out of bounds [-90, 90]")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_lon(cls, v: float) -> float:
        if v < -180.0 or v > 180.0:
            raise ValueError(f"Longitude {v} out of bounds [-180, 180]")
        return v

    @field_validator("crs")
    @classmethod
    def validate_crs(cls, v: str) -> str:
        v_upper = v.strip().upper()
        allowed_crs = {"EPSG:4326", "EPSG:32645", "WGS84"}
        if v_upper not in allowed_crs:
            raise ValueError(f"Unsupported CRS '{v}'. Supported: {', '.join(sorted(allowed_crs))}")
        return v_upper

    @field_validator("accuracy_meters")
    @classmethod
    def validate_accuracy(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("Accuracy meters must be non-negative")
        return v

class GroundChauhaddi(BaseModel):
    north: Optional[str] = None
    south: Optional[str] = None
    east: Optional[str] = None
    west: Optional[str] = None

class RoadAccessObservation(BaseModel):
    road_type: str = Field("PUCCA_ROAD", description="PUCCA_ROAD, KACHA_RASTA, PATHWAY, LANDLOCKED")
    frontage_feet: Optional[float] = None
    notes: Optional[str] = None

class PhysicalPossessorObservation(BaseModel):
    name: Optional[str] = None
    relationship_or_claim: Optional[str] = None
    possession_years: Optional[int] = None
    remarks: Optional[str] = None

class TaskCreateRequest(BaseModel):
    case_id: uuid.UUID
    parcel_id: Optional[uuid.UUID] = None
    finding_id: Optional[uuid.UUID] = None
    action_id: Optional[uuid.UUID] = None
    title: str = Field(..., min_length=3, max_length=256)
    reason: str = Field(..., min_length=5)
    requested_activities: List[str] = Field(default_factory=lambda: ["BOUNDARY_WALK", "CHAUHADDI_CHECK"])
    priority: str = Field(TaskPriority.MEDIUM)
    due_date: Optional[datetime] = None
    instructions: Optional[str] = None

class TaskAssignRequest(BaseModel):
    amin_user_id: uuid.UUID
    due_date: Optional[datetime] = None
    instructions: Optional[str] = None

class TaskDeclineRequest(BaseModel):
    reason: str = Field(..., min_length=3)

class TaskCancelRequest(BaseModel):
    reason: str = Field(..., min_length=3)

class FieldReportSubmitRequest(BaseModel):
    client_observation_id: Optional[str] = None
    narrative_report: str = Field(..., min_length=5, description="Amin's field inspection narrative summary")
    gps_points: List[GPSPointObservation] = Field(default_factory=list)
    boundary_points: List[GPSPointObservation] = Field(default_factory=list)
    measured_area_acres: Optional[float] = None
    ground_neighbors: Optional[GroundChauhaddi] = None
    road_access: Optional[RoadAccessObservation] = None
    physical_possessor: Optional[PhysicalPossessorObservation] = None
    site_conditions: Optional[Dict[str, Any]] = None
    incomplete_reason: Optional[str] = None
    evidence_ids: List[uuid.UUID] = Field(default_factory=list)

class TaskReviewRequest(BaseModel):
    outcome: str = Field(..., description="ACCEPT, REVISION_REQUESTED, REJECT, INCONCLUSIVE")
    review_notes: str = Field(..., min_length=3)
    create_field_survey_record: bool = Field(True, description="Create or update official FieldSurvey record on acceptance")

class FieldTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: uuid.UUID
    org_id: uuid.UUID
    case_id: uuid.UUID
    parcel_id: Optional[uuid.UUID] = None
    finding_id: Optional[uuid.UUID] = None
    action_id: Optional[uuid.UUID] = None
    survey_id: Optional[uuid.UUID] = None
    task_number: str
    title: str
    reason: str
    requested_activities: List[str]
    priority: str
    status: str
    assigned_amin_id: Optional[uuid.UUID] = None
    assigned_by_user_id: Optional[uuid.UUID] = None
    reviewer_user_id: Optional[uuid.UUID] = None
    assigned_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    instructions: Optional[str] = None
    decline_reason: Optional[str] = None
    cancellation_reason: Optional[str] = None
    visit_started_at: Optional[datetime] = None
    visit_completed_at: Optional[datetime] = None
    review_status: Optional[str] = None
    review_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class FieldTaskDetailResponse(FieldTaskResponse):
    field_observations: Dict[str, Any] = Field(default_factory=dict)
    evidence_ids: List[uuid.UUID] = Field(default_factory=list)
    boundary_comparison: Optional[Dict[str, Any]] = None

class EligibleWorkerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    org_id: uuid.UUID
    full_name: str
    email: str
    phone_number: str
    role: str
    is_active: bool
    verified_qualifications: bool = False
    qualification_notes: Optional[str] = None
    active_tasks_count: int = 0
