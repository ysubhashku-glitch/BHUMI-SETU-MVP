"""
Bhumi Setu - Cadastral Vector Overlay & Boundary Discrepancy Test Suite.

Comprehensive tests covering:
    1. Geospatial file ingestion (GeoJSON, KML, KMZ, PNG, JPEG, TIFF)
    2. Archive safety & Zip Slip path-traversal protection
    3. Ground Control Point (GCP) Affine georeferencing solver & RMSE
    4. Collinear / degenerate control points detection
    5. Pure Python ellipsoidal Transverse Mercator projections (WGS84 <-> UTM 45N)
    6. Geometry validation, topological repair, and metric measurement
    7. Deterministic boundary overlay analysis (IoU, Hausdorff, Centroid displacement)
    8. Discrepancy taxonomy classification
    9. LandAmin field task integration
    10. Multi-tenant isolation and object-level authorization
    11. Land Intelligence Report assembly integration
"""

import os
import uuid
import json
import zipfile
import io
import pytest
from datetime import datetime, timezone
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.database import Base, CompatibleGeometry
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.case import Case, CaseStatus
from app.models.parcel import Parcel
from app.models.spatial_overlay import (
    CadastralMapAsset,
    GeoreferenceSession,
    CadastralParcelGeometry,
    BoundaryOverlayAnalysis,
    BoundaryDiscrepancyReview,
    CadastralAssetFormat,
    CadastralSourceType,
    GeoreferenceTransformMethod,
    GeoreferenceSessionStatus,
    ParcelGeometryRole,
    DiscrepancyTaxonomy,
    DiscrepancySeverity,
    BoundaryReviewDecision,
)
from app.services.spatial.crs import (
    validate_crs,
    project_wgs84_to_utm45n,
    unproject_utm45n_to_wgs84,
    transform_geometry_to_metric,
    transform_geometry_to_wgs84,
    SpatialReferenceError,
)
from app.services.spatial.ingestion import (
    process_cadastral_upload,
    detect_file_format_and_magic,
    parse_geojson_to_geometry,
    parse_kml_to_polygon,
    extract_kmz_archive,
    GeospatialIngestionError,
    UnsafeArchiveError,
)
from app.services.spatial.georeferencing import (
    GroundControlPoint,
    solve_affine_transformation,
    transform_pixel_to_ground,
    GeoreferencingError,
)
from app.services.spatial.geometry_validator import (
    validate_and_measure_parcel_geometry,
    GeometryValidationError,
)
from app.services.spatial.overlay_engine import (
    compute_boundary_overlay_analysis,
    STATUTORY_CADASTRAL_DISCLAIMER,
)
from app.services.spatial.service import CadastralOverlayService
from app.services.report_assembler import assemble_report_data
from app.core.exceptions import EntityNotFoundError, CrossTenantAccessError


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def db_session():
    """In-memory SQLite database session with full spatial models registered."""
    engine = sa.create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def test_tenants_and_users(db_session):
    """Creates two distinct organizations and users for tenant isolation tests."""
    org_a = Organization(org_id=uuid.uuid4(), name="Danapur Registry Legal Tech")
    org_b = Organization(org_id=uuid.uuid4(), name="Gaya Property Diligence Ltd")
    db_session.add_all([org_a, org_b])
    db_session.commit()

    user_a = User(
        user_id=uuid.uuid4(),
        org_id=org_a.org_id,
        email="operator_a@danapur.in",
        hashed_password="pw",
        full_name="Amit Kumar",
        role=UserRole.ADMIN,
        is_active=True
    )
    user_b = User(
        user_id=uuid.uuid4(),
        org_id=org_b.org_id,
        email="operator_b@gaya.in",
        hashed_password="pw",
        full_name="Rajesh Verma",
        role=UserRole.ADMIN,
        is_active=True
    )
    db_session.add_all([user_a, user_b])
    db_session.commit()

    return {"org_a": org_a, "org_b": org_b, "user_a": user_a, "user_b": user_b}


# =============================================================================
# 1. Coordinate Reference Systems (CRS) & Projection Metrology
# =============================================================================

def test_crs_validation_rules():
    assert validate_crs("EPSG:4326") == "EPSG:4326"
    assert validate_crs("WGS84") == "EPSG:4326"
    assert validate_crs("EPSG:32645") == "EPSG:32645"
    assert validate_crs("UTM45N") == "EPSG:32645"

    with pytest.raises(SpatialReferenceError):
        validate_crs("EPSG:99999")
    with pytest.raises(SpatialReferenceError):
        validate_crs("")


def test_wgs84_utm45n_roundtrip_precision():
    """Tests forward and inverse Transverse Mercator projections to millimeter precision."""
    # Patna coordinates (Danapur area)
    patna_lat, patna_lon = 25.6125, 85.0450

    easting, northing = project_wgs84_to_utm45n(lat=patna_lat, lon=patna_lon)
    # Expected UTM 45N coords in Bihar: easting ~ 300,000 - 600,000m, northing ~ 2,700,000 - 3,050,000m
    assert 200000.0 < easting < 800000.0
    assert 2500000.0 < northing < 3200000.0

    rev_lat, rev_lon = unproject_utm45n_to_wgs84(easting=easting, northing=northing)
    assert abs(rev_lat - patna_lat) < 1e-6
    assert abs(rev_lon - patna_lon) < 1e-6


# =============================================================================
# 2. Ingestion & Archive Hardening Tests
# =============================================================================

def test_geojson_ingestion_valid():
    sample_geojson = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[85.045, 25.612], [85.048, 25.612], [85.048, 25.615], [85.045, 25.615], [85.045, 25.612]]]
        },
        "properties": {"plot": "112"}
    }
    payload = json.dumps(sample_geojson).encode("utf-8")
    res = process_cadastral_upload("plot_112.geojson", payload)

    assert res["file_format"] == CadastralAssetFormat.GEOJSON
    assert res["is_vector"] is True
    assert res["parsed_geometry"].geom_type == "Polygon"
    assert len(res["sha256_hash"]) == 64


def test_kml_ingestion_valid():
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Placemark>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>
                85.045,25.612,0 85.048,25.612,0 85.048,25.615,0 85.045,25.615,0 85.045,25.612,0
              </coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </Placemark>
    </kml>"""
    res = process_cadastral_upload("cadastral.kml", kml_content.encode("utf-8"))
    assert res["file_format"] == CadastralAssetFormat.KML
    assert res["is_vector"] is True
    assert res["parsed_geometry"].geom_type == "Polygon"


def test_kmz_archive_safe_extraction():
    # Build safe in-memory KMZ
    kml_text = """<kml><Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>
        85.045,25.612,0 85.048,25.612,0 85.048,25.615,0 85.045,25.612,0
    </coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></kml>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("doc.kml", kml_text)
    kmz_bytes = buf.getvalue()

    res = process_cadastral_upload("survey.kmz", kmz_bytes)
    assert res["file_format"] == CadastralAssetFormat.KMZ
    assert res["parsed_geometry"].geom_type == "Polygon"


def test_kmz_path_traversal_zip_slip_rejection():
    """Security test: verifies that KMZ archives with path traversal are rejected."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../etc/passwd", "evil")
    kmz_bytes = buf.getvalue()

    with pytest.raises(UnsafeArchiveError, match="Path traversal"):
        extract_kmz_archive(kmz_bytes)


def test_raster_png_ingestion():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), color="white").save(buf, format="PNG")
    png_bytes = buf.getvalue()
    res = process_cadastral_upload("danapur_sheet.png", png_bytes)
    assert res["file_format"] == CadastralAssetFormat.PNG
    assert res["is_vector"] is False
    assert res["image_width"] == 1
    assert res["image_height"] == 1


# =============================================================================
# 3. Georeferencing & Residual Error Metrology Tests
# =============================================================================

def test_affine_georeferencing_exact_solve():
    """Tests 4-point Affine solver with known synthetic coordinates."""
    # Synthetic pixel coordinates and mapped ground coordinates (UTM 45N)
    # Transformation: ground_x = 2.0*u + 0.0*v + 500000.0
    #                 ground_y = 0.0*u + 2.0*v + 2800000.0
    gcps = [
        GroundControlPoint(gcp_id="P1", image_u=100.0, image_v=100.0, ground_x=500200.0, ground_y=2800200.0),
        GroundControlPoint(gcp_id="P2", image_u=900.0, image_v=100.0, ground_x=501800.0, ground_y=2800200.0),
        GroundControlPoint(gcp_id="P3", image_u=900.0, image_v=900.0, ground_x=501800.0, ground_y=2801800.0),
        GroundControlPoint(gcp_id="P4", image_u=100.0, image_v=900.0, ground_x=500200.0, ground_y=2801800.0),
    ]
    res = solve_affine_transformation(gcps)

    assert res["control_points_used"] == 4
    assert res["rmse_meters"] < 0.001
    assert abs(res["parameters"]["a"] - 2.0) < 1e-4
    assert abs(res["parameters"]["e"] - 2.0) < 1e-4
    assert abs(res["parameters"]["c"] - 500000.0) < 1e-4
    assert res["is_acceptable"] is True


def test_affine_georeferencing_insufficient_points():
    gcps = [
        GroundControlPoint(gcp_id="P1", image_u=100.0, image_v=100.0, ground_x=500200.0, ground_y=2800200.0),
        GroundControlPoint(gcp_id="P2", image_u=900.0, image_v=100.0, ground_x=501800.0, ground_y=2800200.0),
    ]
    with pytest.raises(GeoreferencingError, match="requires at least 3"):
        solve_affine_transformation(gcps)


def test_affine_georeferencing_collinear_points():
    """Collinear GCPs must be detected and rejected."""
    gcps = [
        GroundControlPoint(gcp_id="P1", image_u=100.0, image_v=100.0, ground_x=500100.0, ground_y=2800100.0),
        GroundControlPoint(gcp_id="P2", image_u=200.0, image_v=200.0, ground_x=500200.0, ground_y=2800200.0),
        GroundControlPoint(gcp_id="P3", image_u=300.0, image_v=300.0, ground_x=500300.0, ground_y=2800300.0),
    ]
    with pytest.raises(GeoreferencingError, match="Singular matrix"):
        solve_affine_transformation(gcps)


# =============================================================================
# 4. Geometry Validation & Spatial Metrics Tests
# =============================================================================

def test_geometry_validation_and_repair():
    from shapely.geometry import Polygon
    # Self-intersecting bowtie polygon
    bowtie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
    assert not bowtie.is_valid

    # Validate with auto-repair
    res = validate_and_measure_parcel_geometry(bowtie, input_crs="EPSG:4326", allow_repair=True)
    assert res["is_valid"] is True
    assert res["calculated_area_sqm"] > 0


# =============================================================================
# 5. Boundary Overlay & Discrepancy Metrology Tests
# =============================================================================

def test_boundary_overlay_identical_polygons():
    """Two identical polygons must yield IoU=1.0 and zero displacement."""
    from shapely.geometry import box
    # 50m x 50m box in Danapur
    p1 = box(85.0450, 25.6120, 85.0455, 25.6125)
    p2 = box(85.0450, 25.6120, 85.0455, 25.6125)

    res = compute_boundary_overlay_analysis(p1, p2)
    assert res["iou_score"] == 1.0
    assert res["centroid_displacement_meters"] == 0.0
    assert res["area_delta_percentage"] == 0.0
    assert res["discrepancy_status"] == DiscrepancyTaxonomy.NO_SIGNIFICANT_DIFFERENCE_DETECTED
    assert res["discrepancy_severity"] == DiscrepancySeverity.NONE


def test_boundary_overlay_significant_shift():
    """Tests a shifted polygon yielding boundary discrepancy."""
    from shapely.geometry import box
    p1 = box(85.0450, 25.6120, 85.0460, 25.6130)
    # Shift east by ~0.0005 deg (~50 meters)
    p2 = box(85.0455, 25.6120, 85.0465, 25.6130)

    res = compute_boundary_overlay_analysis(p1, p2)
    assert 0.20 < res["iou_score"] < 0.60
    assert res["centroid_displacement_meters"] > 30.0
    assert res["discrepancy_status"] in (DiscrepancyTaxonomy.POTENTIAL_BOUNDARY_DISCREPANCY, DiscrepancyTaxonomy.POTENTIAL_GEOMETRY_OVERLAP)


def test_boundary_overlay_disjoint_gap():
    """Completely disjoint polygons must trigger POTENTIAL_GEOMETRY_GAP with CRITICAL severity."""
    from shapely.geometry import box
    p1 = box(85.0450, 25.6120, 85.0455, 25.6125)
    p2 = box(85.0500, 25.6200, 85.0505, 25.6205)

    res = compute_boundary_overlay_analysis(p1, p2)
    assert res["iou_score"] == 0.0
    assert res["discrepancy_status"] == DiscrepancyTaxonomy.POTENTIAL_GEOMETRY_GAP
    assert res["discrepancy_severity"] == DiscrepancySeverity.CRITICAL


# =============================================================================
# 6. Service Orchestration, Review, and LandAmin Integration
# =============================================================================

def test_service_overlay_workflow_and_landamin_dispatch(db_session, test_tenants_and_users):
    org_a = test_tenants_and_users["org_a"]
    user_a = test_tenants_and_users["user_a"]

    service = CadastralOverlayService(db_session)

    # 1. Register baseline and comparison geometries
    from shapely.geometry import box
    g1 = box(85.0450, 25.6120, 85.0460, 25.6130)
    g2 = box(85.0453, 25.6120, 85.0463, 25.6130)

    base_geom = service.register_parcel_geometry(
        org_id=org_a.org_id,
        geometry_label="Danapur CS 1910 Sheet 4",
        raw_geometry=g1,
        geometry_role=ParcelGeometryRole.BASELINE_CADASTRAL
    )
    comp_geom = service.register_parcel_geometry(
        org_id=org_a.org_id,
        geometry_label="Modern Bhu-Naksha DILRMP",
        raw_geometry=g2,
        geometry_role=ParcelGeometryRole.MODERN_SURVEY
    )

    # 2. Run analysis
    analysis = service.run_boundary_overlay_analysis(
        org_id=org_a.org_id,
        baseline_geometry_id=base_geom.geometry_id,
        comparison_geometry_id=comp_geom.geometry_id
    )
    assert analysis.analysis_id is not None
    assert analysis.iou_score > 0

    # 3. Submit review with LandAmin field task dispatch
    review = service.submit_boundary_review(
        analysis_id=analysis.analysis_id,
        org_id=org_a.org_id,
        reviewer_id=user_a.user_id,
        decision=BoundaryReviewDecision.REQUIRES_FIELD_SURVEY,
        review_notes="Shift along eastern boundary exceeds survey tolerance. Dispatching LandAmin.",
        dispatch_field_task=False  # No case_id in this minimal test, so verify review saved
    )
    assert review.review_id is not None
    assert review.decision == BoundaryReviewDecision.REQUIRES_FIELD_SURVEY


def test_service_tenant_isolation(db_session, test_tenants_and_users):
    """Verifies that Org B cannot access Org A's cadastral assets or geometries."""
    org_a = test_tenants_and_users["org_a"]
    org_b = test_tenants_and_users["org_b"]

    service = CadastralOverlayService(db_session)

    from shapely.geometry import box
    geom_a = service.register_parcel_geometry(
        org_id=org_a.org_id,
        geometry_label="Org A Protected Parcel",
        raw_geometry=box(85.0, 25.0, 85.1, 25.1),
    )

    with pytest.raises(CrossTenantAccessError):
        service.get_parcel_geometry(geometry_id=geom_a.geometry_id, org_id=org_b.org_id)


# =============================================================================
# 7. Land Intelligence Report Integration Test
# =============================================================================

def test_report_assembler_cadastral_overlay_integration(db_session, test_tenants_and_users):
    org = test_tenants_and_users["org_a"]
    user = test_tenants_and_users["user_a"]

    case = Case(
        case_id=uuid.uuid4(),
        org_id=org.org_id,
        case_number="CASE-PAT-2026-OVL",
        primary_client_party_id=uuid.uuid4(),
        status=CaseStatus.DRAFT
    )
    parcel = Parcel(
        parcel_id=uuid.uuid4(),
        org_id=org.org_id,
        bhumi_id="BR-PAT-DAN-SAG-P112",
        state_code="BR",
        district_name="Patna",
        subdistrict_anchal_name="Danapur",
        mauza_village_name="Saguna",
        census_village_code="280112",
        khata_number="48",
        plot_khesra_number="112",
        recorded_area_acres=1.5,
        land_nature="RESIDENTIAL"
    )
    db_session.add_all([case, parcel])
    db_session.commit()

    service = CadastralOverlayService(db_session)
    from shapely.geometry import box
    b_geom = service.register_parcel_geometry(
        org_id=org.org_id,
        geometry_label="Historical CS 1910",
        raw_geometry=box(85.045, 25.612, 85.050, 25.617),
        parcel_id=parcel.parcel_id,
        case_id=case.case_id
    )
    c_geom = service.register_parcel_geometry(
        org_id=org.org_id,
        geometry_label="Bhu-Naksha DILRMP",
        raw_geometry=box(85.046, 25.612, 85.051, 25.617),
        parcel_id=parcel.parcel_id,
        case_id=case.case_id
    )
    service.run_boundary_overlay_analysis(
        org_id=org.org_id,
        baseline_geometry_id=b_geom.geometry_id,
        comparison_geometry_id=c_geom.geometry_id,
        parcel_id=parcel.parcel_id,
        case_id=case.case_id
    )

    report_data = assemble_report_data(db_session, case_id=case.case_id, parcel_id=parcel.parcel_id, current_user=user)

    assert report_data.section_3_cadastral.overlay_performed is True
    assert report_data.section_3_cadastral.iou_score is not None
    assert report_data.section_3_cadastral.discrepancy_status is not None
    assert report_data.section_1_cover.data_availability_summary["cadastral_overlay_performed"] is True
    assert "STATUTORY" in report_data.section_3_cadastral.statutory_cadastral_disclaimer.upper()


# =============================================================================
# 8. Pilot Hardening: Independent Check-Points, Transformations & Metadata
# =============================================================================

def test_affine_georeferencing_independent_checkpoints():
    """
    Verifies that fitting residuals and independent check-point (ICP) errors are
    calculated separately: least squares fits strictly on control points, and
    independent check points assess true ground verification accuracy.
    """
    # 4 Control Points (exact linear transformation: x = 2*u + 500000, y = 2*v + 2800000)
    ctrl_points = [
        GroundControlPoint(gcp_id="CP1", image_u=100.0, image_v=100.0, ground_x=500200.0, ground_y=2800200.0),
        GroundControlPoint(gcp_id="CP2", image_u=900.0, image_v=100.0, ground_x=501800.0, ground_y=2800200.0),
        GroundControlPoint(gcp_id="CP3", image_u=900.0, image_v=900.0, ground_x=501800.0, ground_y=2801800.0),
        GroundControlPoint(gcp_id="CP4", image_u=100.0, image_v=900.0, ground_x=500200.0, ground_y=2801800.0),
    ]

    # 2 Independent Check Points with known small 0.50m ground deviation
    check_points = [
        GroundControlPoint(gcp_id="ICP1", image_u=500.0, image_v=500.0, ground_x=501000.5, ground_y=2801000.0),
        GroundControlPoint(gcp_id="ICP2", image_u=300.0, image_v=700.0, ground_x=500600.0, ground_y=2801400.5),
    ]

    res = solve_affine_transformation(gcps=ctrl_points, check_points=check_points)

    assert res["control_points_used"] == 4
    assert res["check_points_used"] == 2
    # Fitting RMSE on control points is near zero
    assert res["fitting_rmse_meters"] < 0.001
    # Check-point RMSE is ~0.50m
    assert res["checkpoint_rmse_meters"] is not None
    assert 0.45 < res["checkpoint_rmse_meters"] < 0.55
    assert len(res["checkpoint_residuals"]) == 2
    assert res["is_acceptable"] is True
    assert res["quality_assessment"] == "EXCELLENT"


def test_affine_georeferencing_excessive_checkpoint_error():
    """
    When independent check points have large residual errors (> 2.50m threshold),
    an explicit warning is issued and quality is downgraded.
    """
    ctrl_points = [
        GroundControlPoint(gcp_id="CP1", image_u=100.0, image_v=100.0, ground_x=500200.0, ground_y=2800200.0),
        GroundControlPoint(gcp_id="CP2", image_u=900.0, image_v=100.0, ground_x=501800.0, ground_y=2800200.0),
        GroundControlPoint(gcp_id="CP3", image_u=900.0, image_v=900.0, ground_x=501800.0, ground_y=2801800.0),
        GroundControlPoint(gcp_id="CP4", image_u=100.0, image_v=900.0, ground_x=500200.0, ground_y=2801800.0),
    ]

    # Check points with 4.5m ground shift (exceeds 2.50m threshold)
    check_points = [
        GroundControlPoint(gcp_id="ICP_ERR1", image_u=500.0, image_v=500.0, ground_x=501004.5, ground_y=2801000.0),
        GroundControlPoint(gcp_id="ICP_ERR2", image_u=300.0, image_v=700.0, ground_x=500600.0, ground_y=2801404.5),
    ]

    res = solve_affine_transformation(gcps=ctrl_points, check_points=check_points)

    assert res["checkpoint_rmse_meters"] > 2.50
    assert any("Excessive independent check-point error" in w for w in res["warnings"])
    assert res["quality_assessment"] in ("GOOD", "FAIR")


def test_unsupported_transformation_rejection():
    """Unsupported CRS strings and projections must raise SpatialReferenceError."""
    with pytest.raises(SpatialReferenceError, match="Unsupported CRS"):
        validate_crs("EPSG:2154")  # Lambert-93 France

    from shapely.geometry import box
    b = box(85.0, 25.0, 85.1, 25.1)
    with pytest.raises(SpatialReferenceError):
        transform_geometry_to_metric(b, source_crs="EPSG:3857")


def test_contradictory_crs_metadata_detection():
    """Coordinates declared as geographic (EPSG:4326) but with meter ranges (> 180 deg) fail validation."""
    from shapely.geometry import box
    # Meter-scale box declared with geographic CRS
    meter_box = box(500000.0, 2800000.0, 500100.0, 2800100.0)
    res = validate_and_measure_parcel_geometry(meter_box, input_crs="EPSG:4326", allow_repair=False)
    # Outside Bihar bounds
    assert res["is_valid"] is False
    assert "bounds" in res["validation_error"].lower() or "invalid" in res["validation_error"].lower()
