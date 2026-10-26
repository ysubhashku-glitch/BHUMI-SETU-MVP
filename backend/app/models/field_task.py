import uuid
import sqlalchemy as sa
from sqlalchemy.orm import relationship, synonym
from app.database import Base
from app.models.base import GUID, JSONCompatible, utc_now

class TaskStatus(str):
    DRAFT = "DRAFT"
    READY_FOR_ASSIGNMENT = "READY_FOR_ASSIGNMENT"
    ASSIGNED = "ASSIGNED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    REVIEW_ACCEPTED = "REVIEW_ACCEPTED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"

class TaskPriority(str):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class ReviewOutcome(str):
    ACCEPT = "ACCEPT"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    REJECT = "REJECT"
    INCONCLUSIVE = "INCONCLUSIVE"

class FieldVerificationTask(Base):
    __tablename__ = "field_verification_tasks"

    task_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = sa.Column(GUID, sa.ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False, index=True)
    parcel_id = sa.Column(GUID, sa.ForeignKey("parcels.parcel_id", ondelete="SET NULL"), nullable=True, index=True)
    finding_id = sa.Column(GUID, sa.ForeignKey("findings.finding_id", ondelete="SET NULL"), nullable=True, index=True)
    action_id = sa.Column(GUID, sa.ForeignKey("required_actions.action_id", ondelete="SET NULL"), nullable=True, index=True)
    survey_id = sa.Column(GUID, sa.ForeignKey("field_surveys.survey_id", ondelete="SET NULL"), nullable=True)

    task_number = sa.Column(sa.String(32), unique=True, nullable=False, index=True)
    title = sa.Column(sa.String(256), nullable=False)
    reason = sa.Column(sa.Text, nullable=False)
    requested_activities = sa.Column(JSONCompatible, nullable=False, default=list)
    priority = sa.Column(sa.String(16), nullable=False, default=TaskPriority.MEDIUM)
    status = sa.Column(sa.String(32), nullable=False, default=TaskStatus.READY_FOR_ASSIGNMENT, index=True)

    assigned_amin_id = sa.Column(GUID, sa.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_by_user_id = sa.Column(GUID, sa.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    reviewer_user_id = sa.Column(GUID, sa.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)

    assigned_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    due_date = sa.Column(sa.DateTime(timezone=True), nullable=True)
    instructions = sa.Column(sa.Text, nullable=True)
    decline_reason = sa.Column(sa.Text, nullable=True)
    cancellation_reason = sa.Column(sa.Text, nullable=True)

    visit_started_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    visit_completed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)

    # Structured field observations (GPS points, dimensions, Chauhaddi neighbors, possessor, road access)
    field_observations = sa.Column(JSONCompatible, nullable=False, default=dict)
    # Linked evidence UUIDs (photos, signed field sketch, etc.)
    evidence_ids = sa.Column(JSONCompatible, nullable=False, default=list)

    review_status = sa.Column(sa.String(32), nullable=True)
    review_notes = sa.Column(sa.Text, nullable=True)
    reviewed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)

    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    organization = relationship("Organization")
    case = relationship("Case", back_populates="field_tasks")
    parcel = relationship("Parcel")
    finding = relationship("Finding")
    action = relationship("RequiredAction")
    assigned_amin = relationship("User", foreign_keys=[assigned_amin_id])
    assigned_by = relationship("User", foreign_keys=[assigned_by_user_id])
    reviewer = relationship("User", foreign_keys=[reviewer_user_id])
    survey = relationship("FieldSurvey")

    assigned_to_user_id = synonym("assigned_amin_id")

    def __init__(self, **kwargs):
        if "assigned_to_user_id" in kwargs and "assigned_amin_id" not in kwargs:
            kwargs["assigned_amin_id"] = kwargs.pop("assigned_to_user_id")
        if "title" not in kwargs:
            kwargs["title"] = kwargs.get("task_number", "Field Verification Task")
        if "reason" not in kwargs:
            kwargs["reason"] = "Field verification task"
        super().__init__(**kwargs)
