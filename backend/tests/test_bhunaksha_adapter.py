import pytest
import uuid
import json
from datetime import datetime, timezone

from app.models.parcel import Parcel, ParcelVersion
from app.models.evidence import Evidence, EvidenceType, AuthorityTier
from app.models.claim import Claim, ClaimPredicate
from app.models.case import Case, CaseStatus
from app.models.party import Party, PartyType
from app.services.scrapers.bhunaksha import (
    BiharBhuNakshaAdapter,
    BhuNakshaQuery,
    BhuNakshaPlotRecord,
    BhuNakshaSearchResult,
    BhuNakshaIngestRequest,
    RevenueMapComparisonRequest,
    RevenueMapComparisonResult,
    GeometryValidationResult,
    BiharBhuNakshaError,
    BiharBhuNakshaSourceUnavailableError,
    BiharBhuNakshaInvalidQueryError,
    BiharBhuNakshaNotFoundError,
    BiharBhuNakshaGeometryValidationError,
    BiharBhuNakshaRateLimitError,
    validate_and_normalize_geometry,
    BIHAR_BHUNAKSHA_DISTRICTS,
    SQM_PER_ACRE
)

# Realistic Cadastral Geometry Fixtures for Bihar
# 1. UTM Zone 45N (EPSG:32645) Polygon in Patna (~1.50 Acres = ~6070.28 sqm)
SAMPLE_UTM_GEOJSON = {
    "type": "Polygon",
    "coordinates": [[
        [312450.0, 2835600.0],
        [312550.0, 2835600.0],
        [312550.0, 2835660.7],
        [312450.0, 2835660.7],
        [312450.0, 2835600.0]
    ]]
}

# 2. WGS 84 (EPSG:4326) Polygon in Danapur, Patna (~25.61 N, 85.05 E)
SAMPLE_WGS84_GEOJSON = {
    "type": "Feature",
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [85.0500, 25.6100],
            [85.0510, 25.6100],
            [85.0510, 25.6108],
            [85.0500, 25.6108],
            [85.0500, 25.6100]
        ]]
    },
    "properties": {
        "khesra": "112",
        "sheet": "01",
        "khata": "48"
    }
}

# 3. SVG Polygon snippet (as rendered by Bhu-Naksha viewer)
SAMPLE_SVG_POLYGON = """
<svg width="500" height="500" xmlns="http://www.w3.org/2000/svg">
    <g id="plots">
        <polygon id="plot_112" points="312450.0,2835600.0 312550.0,2835600.0 312550.0,2835660.7 312450.0,2835660.7" fill="#f0e68c" stroke="#000" />
    </g>
</svg>
"""

# 4. SVG Path snippet
SAMPLE_SVG_PATH = """
<svg xmlns="http://www.w3.org/2000/svg">
    <path d="M 312450.0 2835600.0 L 312550.0 2835600.0 L 312550.0 2835660.7 L 312450.0 2835660.7 Z" />
</svg>
"""


# =====================================================================
# Unit Tests — Query & District Validation
# =====================================================================

def test_query_district_validation_success():
    """Verifies that official district names and 2-digit codes normalize correctly."""
    q1 = BhuNakshaQuery(
        district="Patna",
        circle="Danapur",
        mauza="Kothwan",
        plot_khesra_number="112"
    )
    assert q1.district == "PATNA"
    
    # Passing 2-digit code for Patna (28)
    q2 = BhuNakshaQuery(
        district="28",
        circle="Danapur",
        mauza="Kothwan",
        plot_khesra_number="112"
    )
    assert q2.district == "PATNA"


def test_query_district_validation_invalid():
    """Verifies that an unknown district raises a validation error."""
    with pytest.raises(ValueError, match="Invalid Bihar district"):
        BhuNakshaQuery(
            district="Bangalore",
            circle="South",
            mauza="Koramangala",
            plot_khesra_number="1"
        )


# =====================================================================
# Unit Tests — Geometry Validation & CRS Metrology
# =====================================================================

def test_validate_and_normalize_geometry_geojson_utm32645():
    """Tests UTM Zone 45N projected geometry parsing, bounds, and area in Sqm & Acres."""
    geom, val = validate_and_normalize_geometry(
        raw_geom=SAMPLE_UTM_GEOJSON,
        crs="EPSG:32645"
    )
    assert val.is_valid is True
    assert val.crs == "EPSG:32645"
    assert val.vertex_count == 5
    # Width = 100m, Height = 60.7m -> Area = 6070.0 sqm -> ~1.50 Acres
    assert 6060.0 <= val.calculated_area_sqm <= 6080.0
    assert 1.49 <= val.calculated_area_acres <= 1.51
    assert val.centroid[0] == 312500.0


def test_validate_and_normalize_geometry_geojson_wgs84():
    """Tests WGS 84 geographic coordinates parsing and bounds checking."""
    geom, val = validate_and_normalize_geometry(
        raw_geom=SAMPLE_WGS84_GEOJSON,
        crs="EPSG:4326"
    )
    assert val.is_valid is True
    assert val.crs == "EPSG:4326"
    assert val.calculated_area_acres > 0.0
    assert 85.0 <= val.centroid[0] <= 85.1
    assert 25.6 <= val.centroid[1] <= 25.7


def test_validate_and_normalize_geometry_svg_polygon():
    """Tests SVG polygon coordinate parsing into a valid Shapely Polygon."""
    geom, val = validate_and_normalize_geometry(
        raw_geom=SAMPLE_SVG_POLYGON,
        crs="EPSG:32645"
    )
    assert val.is_valid is True
    assert val.calculated_area_sqm > 5000.0


def test_validate_and_normalize_geometry_svg_path():
    """Tests SVG path coordinate parsing."""
    geom, val = validate_and_normalize_geometry(
        raw_geom=SAMPLE_SVG_PATH,
        crs="EPSG:32645"
    )
    assert val.is_valid is True
    assert val.calculated_area_sqm > 5000.0


def test_validate_geometry_missing_crs_error():
    """Verifies that missing or blank CRS raises an explicit error."""
    with pytest.raises(BiharBhuNakshaGeometryValidationError, match="Missing or undocumented Coordinate Reference System"):
        validate_and_normalize_geometry(
            raw_geom=SAMPLE_UTM_GEOJSON,
            crs=None
        )


def test_validate_geometry_unsupported_crs_error():
    """Verifies that unsupported CRS raises an explicit error."""
    with pytest.raises(BiharBhuNakshaGeometryValidationError, match="Unsupported CRS"):
        validate_and_normalize_geometry(
            raw_geom=SAMPLE_UTM_GEOJSON,
            crs="EPSG:2154"  # French Lambert grid
        )


def test_validate_geometry_empty_error():
    """Verifies that empty geometry raises validation error."""
    with pytest.raises(BiharBhuNakshaGeometryValidationError, match="empty"):
        validate_and_normalize_geometry(
            raw_geom={"type": "Polygon", "coordinates": []},
            crs="EPSG:32645"
        )


def test_validate_geometry_out_of_bounds_bihar():
    """Verifies that coordinates far outside Bihar spatial bounds are rejected."""
    out_of_bounds_geojson = {
        "type": "Polygon",
        "coordinates": [[
            [72.80, 18.90],
            [72.90, 18.90],
            [72.90, 19.00],
            [72.80, 19.00],
            [72.80, 18.90]
        ]]  # Mumbai coordinates
    }
    with pytest.raises(BiharBhuNakshaGeometryValidationError, match="fall outside Bihar"):
        validate_and_normalize_geometry(
            raw_geom=out_of_bounds_geojson,
            crs="EPSG:4326"
        )


def test_validate_geometry_topology_repair_applied():
    """Verifies that a self-intersecting bowtie polygon is safely repaired and tracked."""
    # Bowtie self-intersecting polygon
    bowtie_wkt = "POLYGON((312450 2835600, 312550 2835660, 312550 2835600, 312450 2835660, 312450 2835600))"
    geom, val = validate_and_normalize_geometry(
        raw_geom=bowtie_wkt,
        crs="EPSG:32645",
        allow_repair=True
    )
    assert val.is_valid is True
    assert val.repair_applied is True
    assert val.topology_error is not None


# =====================================================================
# Unit Tests — Ingestion & Cryptographic Provenance
# =====================================================================

def test_ingest_cadastral_artifact_deduplication():
    """Tests artifact ingestion computes reproducible SHA-256 digests."""
    adapter = BiharBhuNakshaAdapter()
    query = BhuNakshaQuery(
        district="PATNA",
        circle="Danapur",
        mauza="Kothwan",
        plot_khesra_number="112",
        khata_number="48",
        sheet_number="01"
    )
    geojson_str = json.dumps(SAMPLE_UTM_GEOJSON)
    rec1 = adapter.ingest_cadastral_artifact(query, "GEOJSON", geojson_str, "EPSG:32645")
    rec2 = adapter.ingest_cadastral_artifact(query, "GEOJSON", geojson_str, "EPSG:32645")
    
    assert rec1.sha256_hash == rec2.sha256_hash
    assert rec1.validation.calculated_area_acres == rec2.validation.calculated_area_acres
    assert rec1.khesra_plot_number == "112"
    assert rec1.state == "Bihar"


# =====================================================================
# Integration Tests — Database Persistence & Epistemic Claims
# =====================================================================

def test_persist_plot_record_to_domain(db_session, tenant_a, user_a):
    """
    Verifies that cadastral plot record persists to:
    - Parcel (with authoritative boundary WKT and centroid)
    - ParcelVersion (with change_reason)
    - Evidence (EvidenceType.MAP, AuthorityTier.REVENUE_RECORD)
    - Claim (ClaimPredicate.CADASTRAL_GEOMETRY)
    - Case associations
    """
    adapter = BiharBhuNakshaAdapter()
    query = BhuNakshaQuery(
        district="PATNA",
        circle="Danapur",
        mauza="Kothwan",
        plot_khesra_number="112",
        khata_number="48"
    )
    geojson_str = json.dumps(SAMPLE_UTM_GEOJSON)
    record = adapter.ingest_cadastral_artifact(query, "GEOJSON", geojson_str, "EPSG:32645")

    # Create dummy case
    case = Case(
        case_id=uuid.uuid4(),
        org_id=tenant_a.org_id,
        case_number=f"CASE-TEST-{uuid.uuid4().hex[:6].upper()}",
        primary_client_party_id=user_a.user_id,
        status=CaseStatus.DRAFT,
        transaction_readiness_state="NOT_READY"
    )
    db_session.add(case)
    db_session.commit()

    parcel = adapter.persist_plot_record_to_domain(
        db=db_session,
        record=record,
        org_id=tenant_a.org_id,
        case_id=case.case_id,
        uploader_party_id=user_a.user_id
    )
    db_session.commit()

    assert parcel.parcel_id is not None
    assert parcel.plot_khesra_number == "112"
    assert parcel.authoritative_boundary is not None
    assert "POLYGON" in str(parcel.authoritative_boundary)

    # Verify Evidence created
    evidence = db_session.query(Evidence).filter(Evidence.sha256_hash == record.sha256_hash).first()
    assert evidence is not None
    assert evidence.evidence_type == EvidenceType.MAP
    assert evidence.authority_tier == AuthorityTier.REVENUE_RECORD

    # Verify Claim created
    claim = db_session.query(Claim).filter(
        Claim.parcel_id == parcel.parcel_id,
        Claim.predicate == ClaimPredicate.CADASTRAL_GEOMETRY
    ).first()
    assert claim is not None
    assert claim.object_value["crs"] == "EPSG:32645"
    assert claim.object_value["calculated_area_acres"] > 1.0


# =====================================================================
# Unit & Integration Tests — Revenue & Cadastral Cross-Referencing
# =====================================================================

def test_compare_cadastral_to_revenue_concordant():
    """Verifies that matching khesra and area delta <= 5% returns CONCORDANT."""
    adapter = BiharBhuNakshaAdapter()
    query = BhuNakshaQuery(
        district="PATNA",
        circle="Danapur",
        mauza="Kothwan",
        plot_khesra_number="112",
        khata_number="48"
    )
    geojson_str = json.dumps(SAMPLE_UTM_GEOJSON)  # Area = ~1.50 Acres
    rec = adapter.ingest_cadastral_artifact(query, "GEOJSON", geojson_str, "EPSG:32645")

    res = adapter.compare_cadastral_to_revenue(
        cadastral_record=rec,
        jamabandi_recorded_area_acres=1.52,  # 1.52 vs 1.50 -> delta ~1.3% (within 5% tolerance)
        jamabandi_khesra_number="112",
        jamabandi_khata_number="48"
    )

    assert res.status == "CONCORDANT"
    assert res.identifiers_matched is True
    assert len(res.discrepancies) == 0
    assert res.area_consistency_check["passed"] is True


def test_compare_cadastral_to_revenue_area_discrepancy():
    """Verifies that an area mismatch (>15%) flags AREA_DISCREPANCY with Amin action."""
    adapter = BiharBhuNakshaAdapter()
    query = BhuNakshaQuery(
        district="PATNA",
        circle="Danapur",
        mauza="Kothwan",
        plot_khesra_number="112"
    )
    geojson_str = json.dumps(SAMPLE_UTM_GEOJSON)  # Area = ~1.50 Acres
    rec = adapter.ingest_cadastral_artifact(query, "GEOJSON", geojson_str, "EPSG:32645")

    res = adapter.compare_cadastral_to_revenue(
        cadastral_record=rec,
        jamabandi_recorded_area_acres=2.50,  # 2.50 vs 1.50 -> delta ~40% (high deficit)
        jamabandi_khesra_number="112"
    )

    assert res.status == "AREA_DISCREPANCY"
    assert res.identifiers_matched is True
    assert len(res.discrepancies) > 0
    assert "Discrepancy" in res.discrepancies[0]
    assert res.area_consistency_check["passed"] is False


def test_compare_cadastral_to_revenue_identifier_mismatch():
    """Verifies that differing Khesra numbers return IDENTIFIER_MISMATCH."""
    adapter = BiharBhuNakshaAdapter()
    query = BhuNakshaQuery(
        district="PATNA",
        circle="Danapur",
        mauza="Kothwan",
        plot_khesra_number="112"
    )
    geojson_str = json.dumps(SAMPLE_UTM_GEOJSON)
    rec = adapter.ingest_cadastral_artifact(query, "GEOJSON", geojson_str, "EPSG:32645")

    res = adapter.compare_cadastral_to_revenue(
        cadastral_record=rec,
        jamabandi_recorded_area_acres=1.50,
        jamabandi_khesra_number="113"  # Mismatch: 112 vs 113
    )

    assert res.status == "IDENTIFIER_MISMATCH"
    assert res.identifiers_matched is False


# =====================================================================
# API Integration & Tenant Isolation Tests
# =====================================================================

def test_api_bhunaksha_query_endpoint(client, auth_headers_a):
    """Tests POST /api/v1/parcels/bihar/bhunaksha/query endpoint."""
    payload = {
        "district": "Patna",
        "circle": "Danapur",
        "mauza": "Kothwan",
        "plot_khesra_number": "112"
    }
    res = client.post("/api/v1/parcels/bihar/bhunaksha/query", json=payload, headers=auth_headers_a)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "Bhu-Naksha spatial metadata" in data["message"]


def test_api_bhunaksha_ingest_endpoint(client, auth_headers_a):
    """Tests POST /api/v1/parcels/bihar/bhunaksha/ingest endpoint."""
    payload = {
        "query": {
            "district": "Patna",
            "circle": "Danapur",
            "mauza": "Kothwan",
            "plot_khesra_number": "112",
            "khata_number": "48"
        },
        "artifact_format": "GEOJSON",
        "artifact_content": json.dumps(SAMPLE_UTM_GEOJSON),
        "crs": "EPSG:32645",
        "persist": True
    }
    res = client.post("/api/v1/parcels/bihar/bhunaksha/ingest", json=payload, headers=auth_headers_a)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["record"]["khesra_plot_number"] == "112"
    assert data["record"]["validation"]["is_valid"] is True


def test_api_bhunaksha_compare_revenue_endpoint(client, auth_headers_a):
    """Tests POST /api/v1/parcels/bihar/bhunaksha/compare-revenue endpoint."""
    # First ingest a parcel
    ingest_payload = {
        "query": {
            "district": "Patna",
            "circle": "Danapur",
            "mauza": "Kothwan",
            "plot_khesra_number": "112",
            "khata_number": "48"
        },
        "artifact_format": "GEOJSON",
        "artifact_content": json.dumps(SAMPLE_UTM_GEOJSON),
        "crs": "EPSG:32645",
        "persist": True
    }
    ingest_res = client.post("/api/v1/parcels/bihar/bhunaksha/ingest", json=ingest_payload, headers=auth_headers_a)
    record = ingest_res.json()["record"]

    compare_payload = {
        "cadastral_record": record,
        "jamabandi_recorded_area_acres": 1.50,
        "jamabandi_khesra_number": "112",
        "jamabandi_khata_number": "48"
    }
    compare_res = client.post("/api/v1/parcels/bihar/bhunaksha/compare-revenue", json=compare_payload, headers=auth_headers_a)
    assert compare_res.status_code == 200
    res_data = compare_res.json()
    assert res_data["status"] == "CONCORDANT"
    assert res_data["identifiers_matched"] is True


def test_api_get_parcel_spatial_tenant_isolation(client, db_session, tenant_a, tenant_b, auth_headers_a, auth_headers_b, user_a):
    """Verifies that GET /parcels/{id}/spatial enforces multi-tenant boundary checks."""
    adapter = BiharBhuNakshaAdapter()
    query = BhuNakshaQuery(
        district="PATNA",
        circle="Danapur",
        mauza="Kothwan",
        plot_khesra_number="112",
        khata_number="48"
    )
    rec = adapter.ingest_cadastral_artifact(query, "GEOJSON", json.dumps(SAMPLE_UTM_GEOJSON), "EPSG:32645")
    parcel = adapter.persist_plot_record_to_domain(db_session, rec, org_id=tenant_a.org_id, uploader_party_id=user_a.user_id)
    db_session.commit()

    # Tenant A access -> 200 OK with geometry and metrics
    res_a = client.get(f"/api/v1/parcels/{parcel.parcel_id}/spatial", headers=auth_headers_a)
    assert res_a.status_code == 200
    spatial_data = res_a.json()
    assert spatial_data["has_authoritative_geometry"] is True
    assert spatial_data["boundary_geojson"] is not None
    assert spatial_data["calculated_area_acres"] > 1.0

    # Tenant B access -> 403 Forbidden
    res_b = client.get(f"/api/v1/parcels/{parcel.parcel_id}/spatial", headers=auth_headers_b)
    assert res_b.status_code == 403
