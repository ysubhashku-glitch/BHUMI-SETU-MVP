import uuid
import sqlalchemy as sa
from sqlalchemy.orm import relationship
from app.database import Base, CompatibleGeometry
from app.models.base import GUID, utc_now

class FieldSurvey(Base):
    __tablename__ = "field_surveys"

    survey_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    case_id = sa.Column(GUID, sa.ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False, index=True)
    parcel_id = sa.Column(GUID, sa.ForeignKey("parcels.parcel_id", ondelete="CASCADE"), nullable=False, index=True)
    surveyor_party_id = sa.Column(GUID, sa.ForeignKey("parties.party_id"), nullable=False)
    
    gnss_receiver_model = sa.Column(sa.String(64), nullable=True)
    measured_area_acres = sa.Column(sa.Numeric(10, 4), nullable=False)
    measured_boundary_geometry = sa.Column(CompatibleGeometry("POLYGON", srid=4326), nullable=False)
    
    north_ground_neighbor = sa.Column(sa.String(128), nullable=True)
    south_ground_neighbor = sa.Column(sa.String(128), nullable=True)
    east_ground_neighbor = sa.Column(sa.String(128), nullable=True)
    west_ground_neighbor = sa.Column(sa.String(128), nullable=True)
    
    road_access_type = sa.Column(sa.String(32), default="PUCCA_ROAD") # 'PUCCA_ROAD', 'KACHA_RASTA', 'LANDLOCKED'
    road_frontage_feet = sa.Column(sa.Numeric(8, 2), nullable=True)
    physical_possessor_name = sa.Column(sa.String(128), nullable=True)
    
    completed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    case = relationship("Case", back_populates="surveys")
    parcel = relationship("Parcel", back_populates="surveys")
