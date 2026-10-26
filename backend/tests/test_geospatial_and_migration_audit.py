import os
import uuid
import tempfile
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
from alembic.config import Config
from alembic import command
import shapely
from shapely.geometry import shape, mapping
from shapely import wkt

from app.database import Base
import app.models
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.case import Case, CaseStatus, CaseParcel
from app.models.parcel import Parcel
from app.models.party import Party, PartyType
from app.models.evidence import Evidence, EvidenceType, AuthorityTier, CaseEvidence
from app.models.field_task import FieldVerificationTask, TaskStatus, TaskPriority
from app.models.report import LandIntelligenceReport, ReportStatus
from app.services.scrapers.bhunaksha import (
    validate_and_normalize_geometry,
    BiharBhuNakshaAdapter,
    BhuNakshaPlotRecord,
    BiharBhuNakshaGeometryValidationError,
    SQM_PER_ACRE
)


# =============================================================================
# PART 1: DATABASE AND MIGRATION VALIDATION
# =============================================================================

def test_alembic_complete_migration_lifecycle():
    """
    Executes the complete Alembic migration chain on a fresh SQLite database:
    1. Upgrade empty database to head.
    2. Confirm expected tables and constraints exist.
    3. Downgrade to base.
    4. Re-upgrade to head to verify migration reversibility.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        tmp_db_path = tmp_db.name

    try:
        db_url = f"sqlite:///{tmp_db_path.replace(os.sep, '/')}"
        
        # Configure Alembic programmatically
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        # Ensure script_location points to backend/alembic
        alembic_cfg.set_main_option("script_location", os.path.abspath("alembic"))

        # Step 1: Upgrade to latest revision (head)
        command.upgrade(alembic_cfg, "head")

        # Step 2: Inspect created tables
        engine = sa.create_engine(db_url)
        inspector = sa.inspect(engine)
        table_names = set(inspector.get_table_names())

        required_tables = {
            "organizations",
            "users",
            "parties",
            "cases",
            "parcels",
            "case_parcels",
            "documents",
            "document_versions",
            "extracted_fields",
            "evidence",
            "case_evidence",
            "claims",
            "findings",
            "required_actions",
            "resolutions",
            "field_verification_tasks",
            "land_intelligence_reports",
            "audit_logs"
        }
        missing_tables = required_tables - table_names
        assert not missing_tables, f"Alembic upgrade missed tables: {missing_tables}"

        # Step 3: Insert representative data into upgraded database
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        org = Organization(name="Migration Test Org", slug="mig-test-org")
        session.add(org)
        session.commit()
        assert org.org_id is not None
        session.close()

        # Step 4: Downgrade to base (reversibility test)
        command.downgrade(alembic_cfg, "base")
        inspector_after_down = sa.inspect(engine)
        tables_after_down = set(inspector_after_down.get_table_names())
        # Only alembic_version (or empty) should remain
        assert "cases" not in tables_after_down
        assert "land_intelligence_reports" not in tables_after_down

        # Step 5: Re-upgrade to head
        command.upgrade(alembic_cfg, "head")
        inspector_reup = sa.inspect(engine)
        tables_reup = set(inspector_reup.get_table_names())
        assert required_tables.issubset(tables_reup)

        engine.dispose()
    finally:
        if os.path.exists(tmp_db_path):
            try:
                os.remove(tmp_db_path)
            except OSError:
                pass


def test_model_registration_and_relationship_consistency(db_session):
    """
    Verifies that all core SQLAlchemy models are properly mapped, relationships
    have valid reciprocal back_populates, and foreign keys function correctly.
    """
    # Verify entity relationship mappings
    org = Organization(name="Rel Org", slug="rel-org")
    db_session.add(org)
    db_session.flush()

    party = Party(org_id=org.org_id, party_type=PartyType.PERSON, primary_name="Rel Client")
    db_session.add(party)
    db_session.flush()

    case = Case(org_id=org.org_id, case_number="CAS-REL-01", primary_client_party_id=party.party_id)
    parcel = Parcel(
        org_id=org.org_id,
        bhumi_id="REL-PARCEL-01",
        state_code="BR",
        district_name="Patna",
        subdistrict_anchal_name="Danapur",
        mauza_village_name="Kothawan",
        census_village_code="245000",
        khata_number="10",
        plot_khesra_number="20",
        recorded_area_acres=1.0
    )
    db_session.add_all([case, parcel])
    db_session.flush()

    case_parcel = CaseParcel(case_id=case.case_id, parcel_id=parcel.parcel_id, is_primary=True)
    db_session.add(case_parcel)
    db_session.commit()

    # Verify bidirectional relationship navigation
    db_session.refresh(case)
    assert len(case.parcel_associations) == 1
    assert case.parcel_associations[0].parcel.bhumi_id == "REL-PARCEL-01"


def test_transaction_rollback_and_session_cleanup_on_failure(db_session, tenant_a):
    """
    Confirms that a database integrity error rolls back cleanly without
    leaving the session in an uncommitted dirty or broken state.
    """
    p1 = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id="PARCEL-ROLLBACK-TEST-01",
        state_code="BR",
        district_name="Patna",
        subdistrict_anchal_name="Danapur",
        mauza_village_name="Kothawan",
        census_village_code="245000",
        khata_number="1",
        plot_khesra_number="1",
        recorded_area_acres=1.0
    )
    db_session.add(p1)
    db_session.commit()

    # Attempt to insert identical bhumi_id within a nested transaction/savepoint
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            p_dup = Parcel(
                org_id=tenant_a.org_id,
                bhumi_id="PARCEL-ROLLBACK-TEST-01",
                state_code="BR",
                district_name="Patna",
                subdistrict_anchal_name="Danapur",
                mauza_village_name="Kothawan",
                census_village_code="245000",
                khata_number="2",
                plot_khesra_number="2",
                recorded_area_acres=2.0
            )
            db_session.add(p_dup)
            db_session.flush()

    # Next query on clean session must work without PendingRollbackError
    fetched = db_session.query(Parcel).filter(Parcel.bhumi_id == "PARCEL-ROLLBACK-TEST-01").first()
    assert fetched is not None


# =============================================================================
# PART 2: GEOSPATIAL CORRECTNESS
# =============================================================================

def test_valid_wgs84_polygon_geometry_validation():
    """Valid closed WGS84 polygon in Patna passes validation with accurate area."""
    # A box of delta_lat ~ 0.00062 deg and delta_lon ~ 0.00071 deg (~1.21 Acres)
    min_lon, min_lat = 85.0420, 25.6120
    max_lon, max_lat = 85.04271, 25.61262
    wkt_poly = f"POLYGON(({min_lon} {min_lat}, {max_lon} {min_lat}, {max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))"

    geom, val = validate_and_normalize_geometry(wkt_poly, crs="EPSG:4326")
    assert val.is_valid is True
    assert val.crs == "EPSG:4326"
    assert geom.geom_type == "Polygon"
    assert 1.15 <= val.calculated_area_acres <= 1.25
    assert 4600 <= val.calculated_area_sqm <= 5100
    assert val.centroid is not None
    assert 85.04 <= val.centroid[0] <= 85.05
    assert 25.61 <= val.centroid[1] <= 25.62


def test_valid_utm_zone_45n_geometry_validation():
    """Valid UTM Zone 45N (EPSG:32645) projected polygon calculates exact planar area."""
    # 100m x 60.7m rectangle = 6070 sqm ~ 1.50 Acres
    utm_poly = "POLYGON((312450.0 2835600.0, 312550.0 2835600.0, 312550.0 2835660.7, 312450.0 2835660.7, 312450.0 2835600.0))"

    geom, val = validate_and_normalize_geometry(utm_poly, crs="EPSG:32645")
    assert val.is_valid is True
    assert val.crs == "EPSG:32645"
    assert abs(val.calculated_area_acres - 1.50) < 0.02
    assert abs(val.calculated_area_sqm - 6070.0) < 5.0


def test_self_intersecting_bowtie_polygon_repair_behavior():
    """
    Self-intersecting bowtie polygon:
    - allow_repair=False: Raises validation error.
    - allow_repair=True: Auto-repairs into valid geometry while recording original.
    """
    bowtie_wkt = "POLYGON((85.0 25.0, 85.0 25.01, 85.01 25.0, 85.01 25.01, 85.0 25.0))"

    # Strict mode: must raise
    with pytest.raises(BiharBhuNakshaGeometryValidationError):
        validate_and_normalize_geometry(bowtie_wkt, crs="EPSG:4326", allow_repair=False)

    # Permissive repair mode: must repair and flag repair_applied=True
    geom, val = validate_and_normalize_geometry(bowtie_wkt, crs="EPSG:4326", allow_repair=True)
    assert val.is_valid is True
    assert val.repair_applied is True


def test_missing_or_unsupported_crs_rejected():
    """Missing or unsupported CRS must never be silently assumed."""
    valid_wkt = "POLYGON((85.0 25.0, 85.01 25.0, 85.01 25.01, 85.0 25.01, 85.0 25.0))"

    with pytest.raises(BiharBhuNakshaGeometryValidationError) as exc_info:
        validate_and_normalize_geometry(valid_wkt, crs="UNKNOWN_PROJECTION_9999")
    assert "Unsupported" in str(exc_info.value) or "CRS" in str(exc_info.value)


def test_bihar_coordinate_range_bounds_validation():
    """Coordinates outside the official Bihar bounding box (lat 24-28, lon 83-89) must be flagged."""
    # Point in southern India (lat 12.97, lon 77.59 Bangalore) passed as Bihar WGS84 polygon
    outside_bihar_wkt = "POLYGON((77.59 12.97, 77.60 12.97, 77.60 12.98, 77.59 12.98, 77.59 12.97))"

    # Should raise bounds error or flag boundary warning
    with pytest.raises(BiharBhuNakshaGeometryValidationError) as exc_info:
        validate_and_normalize_geometry(outside_bihar_wkt, crs="EPSG:4326")
    assert "bounding box" in str(exc_info.value).lower() or "bounds" in str(exc_info.value).lower()


def test_swapped_coordinates_detected_out_of_bounds():
    """Swapped lat/lon coordinates (lat 85.0, lon 25.6) must be flagged as out of range."""
    swapped_wkt = "POLYGON((25.61 85.04, 25.62 85.04, 25.62 85.05, 25.61 85.05, 25.61 85.04))"

    with pytest.raises(BiharBhuNakshaGeometryValidationError):
        validate_and_normalize_geometry(swapped_wkt, crs="EPSG:4326")


def test_degenerate_and_empty_geometry_rejected():
    """Empty geometries and degenerate lines passed as polygons must be rejected."""
    # Empty string
    with pytest.raises(BiharBhuNakshaGeometryValidationError):
        validate_and_normalize_geometry("", crs="EPSG:4326")

    # GeometryCollection empty
    with pytest.raises(BiharBhuNakshaGeometryValidationError):
        validate_and_normalize_geometry("GEOMETRYCOLLECTION EMPTY", crs="EPSG:4326")

    # Degenerate line with 0 area
    line_wkt = "LINESTRING(85.0 25.0, 85.01 25.01)"
    with pytest.raises(BiharBhuNakshaGeometryValidationError):
        validate_and_normalize_geometry(line_wkt, crs="EPSG:4326")


def test_revenue_vs_geometric_area_discrepancy_thresholds():
    """
    Verifies that the consistency comparison accurately classifies:
    - Concordant (<= 5% variance)
    - Area Discrepancy (> 5% variance)
    """
    from app.services.scrapers.bhunaksha import GeometryValidationResult
    adapter = BiharBhuNakshaAdapter()

    val_1_50 = GeometryValidationResult(
        is_valid=True,
        repair_applied=False,
        crs="EPSG:4326",
        bounds=[85.0, 25.0, 85.01, 25.01],
        calculated_area_sqm=6151.0,
        calculated_area_acres=1.52,
        centroid=(85.005, 25.005),
        vertex_count=5
    )
    plot_record_1_50 = BhuNakshaPlotRecord(
        district_name="Patna",
        district_code="28",
        circle_name="Danapur",
        mauza_name="Kothawan",
        khesra_plot_number="112",
        khata_number="42",
        geometry_geojson={"type": "Polygon", "coordinates": [[[85.0, 25.0], [85.01, 25.0], [85.01, 25.01], [85.0, 25.01], [85.0, 25.0]]]},
        geometry_wkt="POLYGON((85.0 25.0, 85.01 25.0, 85.01 25.01, 85.0 25.01, 85.0 25.0))",
        crs="EPSG:4326",
        validation=val_1_50,
        sha256_hash="dummy"
    )

    # 1. Concordant: 1.52 Acres vs 1.50 Acres (~1.33% delta)
    comp_concordant = adapter.compare_cadastral_to_revenue(
        cadastral_record=plot_record_1_50,
        jamabandi_recorded_area_acres=1.50,
        jamabandi_khesra_number="112",
        jamabandi_khata_number="42"
    )
    assert comp_concordant.status == "CONCORDANT"
    assert abs(comp_concordant.area_delta_pct) <= 5.0

    # 2. Area Discrepancy: 1.20 Acres vs 1.50 Acres (20.0% delta)
    val_1_20 = GeometryValidationResult(
        is_valid=True,
        repair_applied=False,
        crs="EPSG:4326",
        bounds=[85.0, 25.0, 85.01, 25.01],
        calculated_area_sqm=4856.0,
        calculated_area_acres=1.20,
        centroid=(85.005, 25.005),
        vertex_count=5
    )
    plot_record_1_20 = BhuNakshaPlotRecord(
        district_name="Patna",
        district_code="28",
        circle_name="Danapur",
        mauza_name="Kothawan",
        khesra_plot_number="112",
        khata_number="42",
        geometry_geojson={"type": "Polygon", "coordinates": [[[85.0, 25.0], [85.01, 25.0], [85.01, 25.01], [85.0, 25.01], [85.0, 25.0]]]},
        geometry_wkt="POLYGON((85.0 25.0, 85.01 25.0, 85.01 25.01, 85.0 25.01, 85.0 25.0))",
        crs="EPSG:4326",
        validation=val_1_20,
        sha256_hash="dummy"
    )
    comp_discrepant = adapter.compare_cadastral_to_revenue(
        cadastral_record=plot_record_1_20,
        jamabandi_recorded_area_acres=1.50,
        jamabandi_khesra_number="112",
        jamabandi_khata_number="42"
    )
    assert comp_discrepant.status == "AREA_DISCREPANCY"
    assert abs(comp_discrepant.area_delta_pct) >= 15.0
