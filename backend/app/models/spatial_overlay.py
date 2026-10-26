import uuid
from datetime import datetime, timezone
from enum import Enum
import sqlalchemy as sa
from sqlalchemy.orm import relationship
from app.database import Base, CompatibleGeometry
from app.models.base import GUID, JSONCompatible, utc_now

# =============================================================================
# Domain Enums for Cadastral Map Assets & Overlay Analysis
# =============================================================================

class CadastralAssetFormat(str, Enum):
    GEOTIFF = "GEOTIFF"
    TIFF = "TIFF"
    PNG = "PNG"
    JPEG = "JPEG"
    GEOJSON = "GEOJSON"
    KML = "KML"
    KMZ = "KMZ"
    WKT = "WKT"


class CadastralSourceType(str, Enum):
    CADASTRAL_SURVEY_SHEET = "CADASTRAL_SURVEY_SHEET"       # Historical Cadastral Survey (CS) 1888-1920
    REVISION_SURVEY_MAP = "REVISION_SURVEY_MAP"             # Revision Survey (RS) 1960-1990
    BHUNAKSHA_VECTOR = "BHUNAKSHA_VECTOR"                   # Digitized DILRMP Bihar Bhu-Naksha map
    FIELD_SURVEY_SKETCH = "FIELD_SURVEY_SKETCH"             # LandAmin ground survey sketch
    DRONE_ORTHOMOSAIC = "DRONE_ORTHOMOSAIC"                 # High-resolution UAV orthophoto
    OPERATOR_DIGITIZED = "OPERATOR_DIGITIZED"               # Manual GIS boundary digitization
    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"                 # Synthetic regression test fixture


class GeoreferenceTransformMethod(str, Enum):
    AFFINE = "AFFINE"               # 1st-order polynomial (6-parameter: scale_x, scale_y, rot_x, rot_y, trans_x, trans_y)
    SIMILARITY = "SIMILARITY"       # 4-parameter conformal (uniform scale, rotation, translation)
    PROJECTIVE = "PROJECTIVE"       # 8-parameter homography
    POLYNOMIAL_2ND = "POLYNOMIAL_2ND" # 2nd-order polynomial for non-linear paper shrinkage


class GeoreferenceSessionStatus(str, Enum):
    DRAFT = "DRAFT"
    CALCULATED = "CALCULATED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class ParcelGeometryRole(str, Enum):
    BASELINE_CADASTRAL = "BASELINE_CADASTRAL"             # Authoritative historical benchmark
    MODERN_SURVEY = "MODERN_SURVEY"                       # Current survey or satellite extraction
    BHUNAKSHA_AUTHORITATIVE = "BHUNAKSHA_AUTHORITATIVE"   # Bihar DLRS Bhu-Naksha geometry
    FIELD_OBSERVATION = "FIELD_OBSERVATION"               # LandAmin GNSS ground boundary
    DEED_CHAUHADDI = "DEED_CHAUHADDI"                     # Reconstructed from registered deed Chauhaddi
    CANDIDATE_EXTRACTION = "CANDIDATE_EXTRACTION"         # Unverified automated vectorization
    SYNTHETIC_TEST = "SYNTHETIC_TEST"                     # Unit test boundary


class DiscrepancyTaxonomy(str, Enum):
    NO_SIGNIFICANT_DIFFERENCE_DETECTED = "NO_SIGNIFICANT_DIFFERENCE_DETECTED"
    POTENTIAL_GEOMETRY_OVERLAP = "POTENTIAL_GEOMETRY_OVERLAP"
    POTENTIAL_GEOMETRY_GAP = "POTENTIAL_GEOMETRY_GAP"
    POTENTIAL_BOUNDARY_DISCREPANCY = "POTENTIAL_BOUNDARY_DISCREPANCY"
    INSUFFICIENT_SPATIAL_REFERENCE = "INSUFFICIENT_SPATIAL_REFERENCE"
    INSUFFICIENT_ACCURACY_INFORMATION = "INSUFFICIENT_ACCURACY_INFORMATION"
    INVALID_GEOMETRY = "INVALID_GEOMETRY"
    REQUIRES_HUMAN_REVIEW = "REQUIRES_HUMAN_REVIEW"


class DiscrepancySeverity(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class BoundaryReviewDecision(str, Enum):
    CONFIRMED_DISCREPANCY = "CONFIRMED_DISCREPANCY"
    SURVEY_TOLERANCE_ACCEPTABLE = "SURVEY_TOLERANCE_ACCEPTABLE"
    FALSE_POSITIVE_ALIGNMENT_ERROR = "FALSE_POSITIVE_ALIGNMENT_ERROR"
    REQUIRES_FIELD_SURVEY = "REQUIRES_FIELD_SURVEY"
    LEGAL_REPRESENTATION_REQUIRED = "LEGAL_REPRESENTATION_REQUIRED"


# =============================================================================
# Database Models
# =============================================================================

class CadastralMapAsset(Base):
    """
    Represents an uploaded or registered cadastral map artifact (scanned sheet,
    GeoTIFF, vector GeoJSON/KML) with cryptographic provenance and audit metadata.
    """
    __tablename__ = "cadastral_map_assets"

    asset_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = sa.Column(GUID, sa.ForeignKey("cases.case_id", ondelete="SET NULL"), nullable=True, index=True)
    parcel_id = sa.Column(GUID, sa.ForeignKey("parcels.parcel_id", ondelete="SET NULL"), nullable=True, index=True)

    asset_name = sa.Column(sa.String(256), nullable=False)
    file_format = sa.Column(sa.String(32), nullable=False, default=CadastralAssetFormat.PNG)
    source_type = sa.Column(sa.String(64), nullable=False, default=CadastralSourceType.CADASTRAL_SURVEY_SHEET)

    # Storage and cryptographic integrity
    storage_path = sa.Column(sa.String(512), nullable=False)
    sha256_hash = sa.Column(sa.String(64), nullable=False, index=True)
    file_size_bytes = sa.Column(sa.Integer, nullable=False)

    # Raster metadata (if image or GeoTIFF)
    image_width = sa.Column(sa.Integer, nullable=True)
    image_height = sa.Column(sa.Integer, nullable=True)

    # Spatial reference
    declared_crs = sa.Column(sa.String(32), nullable=True)
    is_georeferenced = sa.Column(sa.Boolean, nullable=False, default=False)

    # Administrative identification
    district = sa.Column(sa.String(64), nullable=True)
    anchal = sa.Column(sa.String(64), nullable=True)
    mauza = sa.Column(sa.String(128), nullable=True)
    sheet_number = sa.Column(sa.String(32), nullable=True)
    survey_year = sa.Column(sa.Integer, nullable=True)

    provenance_metadata = sa.Column(JSONCompatible, nullable=False, default=dict)

    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    organization = relationship("Organization")
    case = relationship("Case")
    parcel = relationship("Parcel")
    georeference_sessions = relationship("GeoreferenceSession", back_populates="map_asset", cascade="all, delete-orphan")
    parcel_geometries = relationship("CadastralParcelGeometry", back_populates="map_asset")


class GeoreferenceSession(Base):
    """
    Tracks control points, transformation estimation, and residual errors
    for georeferencing historical cadastral map sheets into Bihar standard CRS.
    """
    __tablename__ = "georeference_sessions"

    session_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = sa.Column(GUID, sa.ForeignKey("cadastral_map_assets.asset_id", ondelete="CASCADE"), nullable=False, index=True)

    transformation_method = sa.Column(sa.String(32), nullable=False, default=GeoreferenceTransformMethod.AFFINE)
    target_crs = sa.Column(sa.String(32), nullable=False, default="EPSG:32645")  # UTM Zone 45N standard

    # List of GCPs: [{gcp_id, image_u, image_v, ground_x, ground_y, residual_x, residual_y, residual_total, is_active}]
    control_points = sa.Column(JSONCompatible, nullable=False, default=list)

    # Solved transformation parameters (e.g. {a, b, c, d, e, f} for affine)
    transformation_parameters = sa.Column(JSONCompatible, nullable=True)

    # Aggregate error metrics
    rmse_meters = sa.Column(sa.Float, nullable=True)
    max_residual_meters = sa.Column(sa.Float, nullable=True)

    # Review & approval
    status = sa.Column(sa.String(32), nullable=False, default=GeoreferenceSessionStatus.DRAFT)
    reviewed_by = sa.Column(GUID, sa.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    review_comments = sa.Column(sa.Text, nullable=True)
    reviewed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)

    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    map_asset = relationship("CadastralMapAsset", back_populates="georeference_sessions")
    reviewer = relationship("User")
    derived_geometries = relationship("CadastralParcelGeometry", back_populates="georeference_session")


class CadastralParcelGeometry(Base):
    """
    Persists distinct geometric representations of a parcel boundary (e.g., historical
    cadastral map survey vs Bhu-Naksha vector vs LandAmin GNSS field polygon).
    """
    __tablename__ = "cadastral_parcel_geometries"

    geometry_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False, index=True)
    parcel_id = sa.Column(GUID, sa.ForeignKey("parcels.parcel_id", ondelete="SET NULL"), nullable=True, index=True)
    case_id = sa.Column(GUID, sa.ForeignKey("cases.case_id", ondelete="SET NULL"), nullable=True, index=True)
    asset_id = sa.Column(GUID, sa.ForeignKey("cadastral_map_assets.asset_id", ondelete="SET NULL"), nullable=True, index=True)
    session_id = sa.Column(GUID, sa.ForeignKey("georeference_sessions.session_id", ondelete="SET NULL"), nullable=True, index=True)

    geometry_label = sa.Column(sa.String(128), nullable=False)
    geometry_role = sa.Column(sa.String(64), nullable=False, default=ParcelGeometryRole.BASELINE_CADASTRAL)
    crs = sa.Column(sa.String(32), nullable=False, default="EPSG:4326")

    # Spatial representation (WKT text on SQLite, PostGIS Polygon/MultiPolygon on PostgreSQL)
    polygon_geometry = sa.Column(CompatibleGeometry("POLYGON", srid=4326), nullable=False)

    # Precalculated metrics
    calculated_area_sqm = sa.Column(sa.Float, nullable=False)
    calculated_area_acres = sa.Column(sa.Float, nullable=False)
    perimeter_meters = sa.Column(sa.Float, nullable=False)
    centroid_lat = sa.Column(sa.Float, nullable=False)
    centroid_lon = sa.Column(sa.Float, nullable=False)

    # Accuracy and validation
    positional_uncertainty_meters = sa.Column(sa.Float, nullable=True)
    is_valid = sa.Column(sa.Boolean, nullable=False, default=True)
    validation_error = sa.Column(sa.Text, nullable=True)

    # Provenance metadata
    digitization_method = sa.Column(sa.String(64), nullable=True)
    source_attribution = sa.Column(sa.String(256), nullable=True)
    raw_geojson = sa.Column(JSONCompatible, nullable=True)

    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    parcel = relationship("Parcel")
    case = relationship("Case", back_populates="cadastral_geometries")
    map_asset = relationship("CadastralMapAsset", back_populates="parcel_geometries")
    georeference_session = relationship("GeoreferenceSession", back_populates="derived_geometries")


class BoundaryOverlayAnalysis(Base):
    """
    Stores deterministic comparison metrics between a baseline cadastral boundary
    and a comparison boundary (e.g. modern satellite polygon or field survey).
    """
    __tablename__ = "boundary_overlay_analyses"

    analysis_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = sa.Column(GUID, sa.ForeignKey("cases.case_id", ondelete="SET NULL"), nullable=True, index=True)
    parcel_id = sa.Column(GUID, sa.ForeignKey("parcels.parcel_id", ondelete="SET NULL"), nullable=True, index=True)

    baseline_geometry_id = sa.Column(GUID, sa.ForeignKey("cadastral_parcel_geometries.geometry_id", ondelete="CASCADE"), nullable=False, index=True)
    comparison_geometry_id = sa.Column(GUID, sa.ForeignKey("cadastral_parcel_geometries.geometry_id", ondelete="CASCADE"), nullable=False, index=True)

    analysis_crs = sa.Column(sa.String(32), nullable=False, default="EPSG:32645")

    # Spatial metrics
    intersection_area_sqm = sa.Column(sa.Float, nullable=False)
    union_area_sqm = sa.Column(sa.Float, nullable=False)
    iou_score = sa.Column(sa.Float, nullable=False)  # Jaccard index [0.0 - 1.0]
    symmetric_diff_area_sqm = sa.Column(sa.Float, nullable=False)
    area_delta_percentage = sa.Column(sa.Float, nullable=False)
    perimeter_delta_percentage = sa.Column(sa.Float, nullable=False)
    centroid_displacement_meters = sa.Column(sa.Float, nullable=False)
    hausdorff_distance_meters = sa.Column(sa.Float, nullable=False)

    # Discrepancy diagnosis
    discrepancy_status = sa.Column(sa.String(64), nullable=False, default=DiscrepancyTaxonomy.REQUIRES_HUMAN_REVIEW)
    discrepancy_severity = sa.Column(sa.String(32), nullable=False, default=DiscrepancySeverity.MEDIUM)
    findings_summary = sa.Column(sa.Text, nullable=False)
    detailed_metrics = sa.Column(JSONCompatible, nullable=False, default=dict)
    algorithm_version = sa.Column(sa.String(32), nullable=False, default="v1.0-bihar-cadastral")

    # LandAmin field task integration
    field_task_id = sa.Column(GUID, sa.ForeignKey("field_verification_tasks.task_id", ondelete="SET NULL"), nullable=True, index=True)

    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    case = relationship("Case", back_populates="boundary_analyses")
    parcel = relationship("Parcel")
    baseline_geometry = relationship("CadastralParcelGeometry", foreign_keys=[baseline_geometry_id])
    comparison_geometry = relationship("CadastralParcelGeometry", foreign_keys=[comparison_geometry_id])
    field_task = relationship("FieldVerificationTask")
    reviews = relationship("BoundaryDiscrepancyReview", back_populates="analysis", cascade="all, delete-orphan")


class BoundaryDiscrepancyReview(Base):
    """
    Maintains an immutable audit trail of human / LandAmin reviewer evaluations
    of an automated geometric discrepancy analysis run.
    """
    __tablename__ = "boundary_discrepancy_reviews"

    review_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_id = sa.Column(GUID, sa.ForeignKey("boundary_overlay_analyses.analysis_id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = sa.Column(GUID, sa.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True)

    decision = sa.Column(sa.String(64), nullable=False, default=BoundaryReviewDecision.REQUIRES_FIELD_SURVEY)
    review_notes = sa.Column(sa.Text, nullable=False)
    field_task_dispatched = sa.Column(sa.Boolean, nullable=False, default=False)

    reviewed_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    analysis = relationship("BoundaryOverlayAnalysis", back_populates="reviews")
    reviewer = relationship("User")
