import uuid
from datetime import date
import sqlalchemy as sa
from sqlalchemy.orm import relationship, synonym
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

    # Synonyms and Aliases
    state = synonym("state_code")
    district = synonym("district_name")
    circle = synonym("subdistrict_anchal_name")
    anchal = synonym("subdistrict_anchal_name")
    subdistrict_anchal = synonym("subdistrict_anchal_name")
    mauza = synonym("mauza_village_name")
    khesra_number = synonym("plot_khesra_number")
    recorded_area_acre = synonym("recorded_area_acres")
    land_classification = synonym("land_nature")

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
    passport_assessments = relationship("PassportAssessment", back_populates="parcel", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        # Map aliases to column names
        if "state" in kwargs and "state_code" not in kwargs:
            val = kwargs.pop("state")
            kwargs["state_code"] = val[:4].upper() if len(val) > 4 else val
        if "state_code" not in kwargs:
            kwargs["state_code"] = "BR"

        if "district" in kwargs and "district_name" not in kwargs:
            kwargs["district_name"] = kwargs.pop("district")
        if "district_name" not in kwargs:
            kwargs["district_name"] = "UNKNOWN"

        if "subdistrict_anchal" in kwargs and "subdistrict_anchal_name" not in kwargs:
            kwargs["subdistrict_anchal_name"] = kwargs.pop("subdistrict_anchal")

        if "subdistrict_anchal_name" not in kwargs:
            if "circle" in kwargs:
                kwargs["subdistrict_anchal_name"] = kwargs.pop("circle")
            elif "anchal" in kwargs:
                kwargs["subdistrict_anchal_name"] = kwargs.pop("anchal")
            else:
                kwargs["subdistrict_anchal_name"] = "UNKNOWN"
        else:
            kwargs.pop("circle", None)
            kwargs.pop("anchal", None)
            kwargs.pop("subdistrict_anchal", None)

        if "mauza" in kwargs and "mauza_village_name" not in kwargs:
            kwargs["mauza_village_name"] = kwargs.pop("mauza")
        if "mauza_village_name" not in kwargs:
            kwargs["mauza_village_name"] = "UNKNOWN"

        if "census_village_code" not in kwargs:
            kwargs["census_village_code"] = "000000"

        if "khesra_number" in kwargs and "plot_khesra_number" not in kwargs:
            kwargs["plot_khesra_number"] = kwargs.pop("khesra_number")
        if "plot_khesra_number" not in kwargs:
            kwargs["plot_khesra_number"] = "0"

        if "khata_number" not in kwargs:
            kwargs["khata_number"] = "0"

        if "recorded_area_acre" in kwargs and "recorded_area_acres" not in kwargs:
            kwargs["recorded_area_acres"] = kwargs.pop("recorded_area_acre")
        if "recorded_area_acres" not in kwargs:
            kwargs["recorded_area_acres"] = 1.0

        if "land_classification" in kwargs and "land_nature" not in kwargs:
            kwargs["land_nature"] = kwargs.pop("land_classification")
        if "land_nature" not in kwargs:
            kwargs["land_nature"] = "AGRICULTURAL_RAIYATI"

        if "bhumi_id" not in kwargs:
            dist = kwargs.get("district_name", "PAT")[:3].upper()
            kh = kwargs.get("khata_number", "0")
            khs = kwargs.get("plot_khesra_number", "0")
            kwargs["bhumi_id"] = f"BR-{dist}-{kh}-{khs}-{uuid.uuid4().hex[:6]}"

        extra_attrs = ["source_portal", "source_authority", "recorded_raiyat"]
        extras = {k: kwargs.pop(k) for k in extra_attrs if k in kwargs}

        super().__init__(**kwargs)

        for k, v in extras.items():
            setattr(self, k, v)


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
