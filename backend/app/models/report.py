import uuid
import sqlalchemy as sa
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import GUID, JSONCompatible, utc_now

class ReportStatus(str):
    GENERATED = "GENERATED"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"

class LandIntelligenceReport(Base):
    __tablename__ = "land_intelligence_reports"

    report_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = sa.Column(GUID, sa.ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False, index=True)
    parcel_id = sa.Column(GUID, sa.ForeignKey("parcels.parcel_id", ondelete="SET NULL"), nullable=True, index=True)

    report_number = sa.Column(sa.String(32), unique=True, nullable=False, index=True)
    version_number = sa.Column(sa.Integer, nullable=False, default=1)
    verification_token = sa.Column(sa.String(64), unique=True, nullable=False, index=True)

    status = sa.Column(sa.String(32), nullable=False, default=ReportStatus.GENERATED, index=True)
    sha256_hash = sa.Column(sa.String(64), nullable=False, index=True)
    pdf_storage_uri = sa.Column(sa.String(512), nullable=False)
    file_size_bytes = sa.Column(sa.Integer, nullable=False, default=0)
    page_count = sa.Column(sa.Integer, nullable=False, default=1)

    # Persisted snapshots of sources and summary metrics for auditable provenance
    source_snapshots = sa.Column(JSONCompatible, nullable=False, default=dict)
    summary_counts = sa.Column(JSONCompatible, nullable=False, default=dict)

    generated_by_user_id = sa.Column(GUID, sa.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    superseded_by_id = sa.Column(GUID, sa.ForeignKey("land_intelligence_reports.report_id", ondelete="SET NULL"), nullable=True)

    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    organization = relationship("Organization")
    case = relationship("Case", back_populates="reports")
    parcel = relationship("Parcel")
    generated_by = relationship("User", foreign_keys=[generated_by_user_id])
    superseded_by = relationship("LandIntelligenceReport", remote_side=[report_id])
