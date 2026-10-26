import uuid
from datetime import date
import sqlalchemy as sa
from sqlalchemy.orm import relationship
from app.database import Base, CompatibleGeometry
from app.models.base import GUID, utc_now

class ParcelRelationshipType(str):
    SUBDIVIDED_TO = "SUBDIVIDED_TO"
    MERGED_TO = "MERGED_TO"
    RENUMBERED_TO = "RENUMBERED_TO"
    CORRECTED_TO = "CORRECTED_TO"

class Parcel(Base):
    __tablename__ = "parcels"

    parcel_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False, index=True)
    bhumi_id = sa.Column(sa.String(64), unique=True, nullable=False, index=True)
    
    # Administrative Hierarchy
    state_code = sa.Column(sa.String(4), nullable=False)
    district_name = sa.Column(sa.String(64), nullable=False)
    subdistrict_anchal_name = sa.Column(sa.String(64), nullable=False)
    halka_number = sa.Column(sa.String(16), nullable=True)
    mauza_village_name = sa.Column(sa.String(128), nullable=False)
    census_village_code = sa.Column(sa.String(32), nullable=False, index=True)
    
    # State-Agnostic Identifiers
    khata_number = sa.Column(sa.String(32), nullable=False)
    plot_khesra_number = sa.Column(sa.String(32), nullable=False)
    subdivision_hissa_number = sa.Column(sa.String(32), nullable=True)
    
    # Stated Extent
    recorded_area_acres = sa.Column(sa.Numeric(10, 4), nullable=False)
    land_nature = sa.Column(sa.String(32), default="AGRICULTURAL_RAIYATI", nullable=False)
    
    # Spatial Geometry
    centroid_point = sa.Column(CompatibleGeometry("POINT", srid=4326), nullable=True)
    authoritative_boundary = sa.Column(CompatibleGeometry("MULTIPOLYGON", srid=4326), nullable=True)
    
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    organization = relationship("Organization", back_populates="parcels")
    case_associations = relationship("CaseParcel", back_populates="parcel")
    versions = relationship("ParcelVersion", back_populates="parcel", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="parcel")
    findings = relationship("Finding", back_populates="parcel")
    surveys = relationship("FieldSurvey", back_populates="parcel")
    judicial_matches = relationship("ParcelJudicialMatch", back_populates="parcel", cascade="all, delete-orphan")
    valuations = relationship("PropertyValuation", back_populates="parcel", cascade="all, delete-orphan")
    cadastral_geometries = relationship("CadastralParcelGeometry", back_populates="parcel")
    mutation_cases = relationship("MutationCase", back_populates="parcel")

class ParcelVersion(Base):
    __tablename__ = "parcel_versions"

    version_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    parcel_id = sa.Column(GUID, sa.ForeignKey("parcels.parcel_id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = sa.Column(sa.Integer, nullable=False)
    recorded_area_acres = sa.Column(sa.Numeric(10, 4), nullable=False)
    boundary_geometry = sa.Column(CompatibleGeometry("MULTIPOLYGON", srid=4326), nullable=True)
    change_reason = sa.Column(sa.String(256), nullable=False)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    parcel = relationship("Parcel", back_populates="versions")

class ParcelRelationship(Base):
    __tablename__ = "parcel_relationships"

    relationship_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    parent_parcel_id = sa.Column(GUID, sa.ForeignKey("parcels.parcel_id", ondelete="CASCADE"), nullable=False, index=True)
    child_parcel_id = sa.Column(GUID, sa.ForeignKey("parcels.parcel_id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = sa.Column(sa.String(32), nullable=False)
    effective_date = sa.Column(sa.Date, nullable=False, default=date.today)
    mutation_order_reference = sa.Column(sa.String(128), nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)
