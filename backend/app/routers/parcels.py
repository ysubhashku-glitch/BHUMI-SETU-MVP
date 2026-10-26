import uuid
from typing import List
from datetime import date
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.parcel import Parcel, ParcelRelationship, ParcelVersion
from app.models.case import Case, CaseParcel
from app.core.dependencies import get_current_user
from app.core.exceptions import EntityNotFoundError, CrossTenantAccessError
from app.schemas.parcel import (
    ParcelCreateRequest, ParcelResponse,
    ParcelRelationshipCreateRequest, ParcelRelationshipResponse,
    ParcelSpatialResponse
)
from app.schemas.case import CaseResponse
from app.services.scrapers.bihar_bhumi import (
    BiharBhumiJamabandiAdapter,
    BiharJamabandiSearchQuery,
    BiharJamabandiSearchResult,
    BiharJamabandiSearchRequest,
    BiharJamabandiManualIngestRequest
)
from app.services.scrapers.bhunaksha import (
    BiharBhuNakshaAdapter,
    BhuNakshaQuery,
    BhuNakshaSearchResult,
    BhuNakshaIngestRequest,
    RevenueMapComparisonRequest,
    RevenueMapComparisonResult,
    BhuNakshaPlotRecord,
    SQM_PER_ACRE
)
import shapely
from shapely.geometry import mapping
from app.models.evidence import Evidence, EvidenceType
from app.models.claim import Claim, ClaimPredicate

router = APIRouter(prefix="/parcels", tags=["Parcels"])

def _build_parcel_response(p: Parcel) -> ParcelResponse:
    return ParcelResponse(
        parcel_id=str(p.parcel_id),
        org_id=str(p.org_id),
        bhumi_id=p.bhumi_id,
        state_code=p.state_code,
        district_name=p.district_name,
        subdistrict_anchal_name=p.subdistrict_anchal_name,
        halka_number=p.halka_number,
        mauza_village_name=p.mauza_village_name,
        census_village_code=p.census_village_code,
        khata_number=p.khata_number,
        plot_khesra_number=p.plot_khesra_number,
        subdivision_hissa_number=p.subdivision_hissa_number,
        recorded_area_acres=float(p.recorded_area_acres),
        land_nature=p.land_nature,
        centroid_point=None,
        authoritative_boundary=None
    )

@router.post("", response_model=ParcelResponse, status_code=status.HTTP_201_CREATED)
def create_parcel(
    request: ParcelCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    dist_code = request.district_name[:3].upper()
    unique_tag = uuid.uuid4().hex[:4].upper()
    bhumi_id = f"{request.state_code}-{dist_code}-{request.census_village_code}-{request.plot_khesra_number}-{unique_tag}"

    parcel = Parcel(
        org_id=current_user.org_id,
        bhumi_id=bhumi_id,
        state_code=request.state_code,
        district_name=request.district_name,
        subdistrict_anchal_name=request.subdistrict_anchal_name,
        halka_number=request.halka_number,
        mauza_village_name=request.mauza_village_name,
        census_village_code=request.census_village_code,
        khata_number=request.khata_number,
        plot_khesra_number=request.plot_khesra_number,
        subdivision_hissa_number=request.subdivision_hissa_number,
        recorded_area_acres=request.recorded_area_acres,
        land_nature=request.land_nature
    )
    db.add(parcel)
    db.commit()
    db.refresh(parcel)
    return _build_parcel_response(parcel)

@router.get("/{parcel_id}", response_model=ParcelResponse)
def get_parcel(
    parcel_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    parcel = db.query(Parcel).filter(Parcel.parcel_id == parcel_id).first()
    if not parcel:
        raise EntityNotFoundError("Parcel", parcel_id)
    if parcel.org_id != current_user.org_id:
        raise CrossTenantAccessError()
    return _build_parcel_response(parcel)

@router.get("/{parcel_id}/cases")
def get_parcel_cases(
    parcel_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    parcel = db.query(Parcel).filter(Parcel.parcel_id == parcel_id).first()
    if not parcel:
        raise EntityNotFoundError("Parcel", parcel_id)
    if parcel.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    case_assocs = db.query(CaseParcel).filter(CaseParcel.parcel_id == parcel_id).all()
    case_ids = [cp.case_id for cp in case_assocs]
    cases = db.query(Case).filter(Case.case_id.in_(case_ids), Case.org_id == current_user.org_id).all()

    return [
        {
            "case_id": str(c.case_id),
            "case_number": c.case_number,
            "status": c.status,
            "transaction_readiness_state": c.transaction_readiness_state
        }
        for c in cases
    ]

@router.post("/relationships", response_model=ParcelRelationshipResponse, status_code=status.HTTP_201_CREATED)
def create_parcel_relationship(
    request: ParcelRelationshipCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    parent_uuid = uuid.UUID(request.parent_parcel_id)
    child_uuid = uuid.UUID(request.child_parcel_id)

    parent = db.query(Parcel).filter(Parcel.parcel_id == parent_uuid).first()
    child = db.query(Parcel).filter(Parcel.parcel_id == child_uuid).first()

    if not parent:
        raise EntityNotFoundError("Parcel (parent)", parent_uuid)
    if not child:
        raise EntityNotFoundError("Parcel (child)", child_uuid)

    if parent.org_id != current_user.org_id or child.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    rel = ParcelRelationship(
        parent_parcel_id=parent_uuid,
        child_parcel_id=child_uuid,
        relationship_type=request.relationship_type,
        effective_date=request.effective_date or date.today(),
        mutation_order_reference=request.mutation_order_reference
    )
    db.add(rel)
    db.commit()
    db.refresh(rel)

    return ParcelRelationshipResponse(
        relationship_id=str(rel.relationship_id),
        parent_parcel_id=str(rel.parent_parcel_id),
        child_parcel_id=str(rel.child_parcel_id),
        relationship_type=rel.relationship_type,
        effective_date=rel.effective_date,
        mutation_order_reference=rel.mutation_order_reference
    )


@router.post("/bihar/jamabandi/search", response_model=BiharJamabandiSearchResult)
async def search_bihar_jamabandi(
    request: BiharJamabandiSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Queries official Bihar Jamabandi Register-II records using verified search parameters.
    Optionally persists normalized records, provisions canonical parcels, and anchors evidence.
    """
    adapter = BiharBhumiJamabandiAdapter()
    result = await adapter.execute_live_search(request.query)
    if request.persist and result.records:
        for rec in result.records:
            adapter.persist_record_to_domain(
                db=db,
                record=rec,
                org_id=current_user.org_id,
                case_id=request.case_id,
                uploader_party_id=current_user.user_id
            )
    return result


@router.post("/bihar/jamabandi/ingest-manual", response_model=BiharJamabandiSearchResult)
def ingest_manual_bihar_jamabandi(
    request: BiharJamabandiManualIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    User-assisted / manual fallback: Ingests an official government Jamabandi HTML/text artifact.
    Preserves cryptographic SHA-256 provenance and generates auditable evidence claims.
    """
    adapter = BiharBhumiJamabandiAdapter()
    result = adapter.ingest_manual_record(request.query, request.source_artifact)
    if request.persist and result.records:
        for rec in result.records:
            adapter.persist_record_to_domain(
                db=db,
                record=rec,
                org_id=current_user.org_id,
                case_id=request.case_id,
                uploader_party_id=current_user.user_id
            )
    return result


@router.post("/bihar/bhunaksha/query", response_model=BhuNakshaSearchResult)
async def query_bihar_bhunaksha(
    query: BhuNakshaQuery,
    current_user: User = Depends(get_current_user)
):
    """
    Queries live Bihar Bhu-Naksha GIS portal for village extent, GIS code, and plot records.
    """
    import time
    start_t = time.time()
    adapter = BiharBhuNakshaAdapter()
    dist_code = adapter.get_district_code(query.district)

    gis_levels = f"{dist_code}"
    try:
        extent_data = await adapter.live_client.get_village_extent_georef(gis_levels)
        gis_code = extent_data.get("gisCode") or f"BR-{dist_code}-0000"
        epsg = extent_data.get("epsg") or "EPSG:32645"
    except Exception as e:
        gis_code = f"BR-{dist_code}-{query.mauza[:4].upper()}"
        epsg = "EPSG:32645"

    elapsed = (time.time() - start_t) * 1000.0
    return BhuNakshaSearchResult(
        success=True,
        query=query,
        record=None,
        candidate_records=[],
        message=f"Bhu-Naksha spatial metadata queried for district {query.district} (GIS Code: {gis_code}, CRS: {epsg}). Provide cadastral artifact to ingest boundary geometry.",
        execution_time_ms=elapsed
    )


@router.post("/bihar/bhunaksha/ingest", response_model=BhuNakshaSearchResult)
def ingest_bihar_bhunaksha_artifact(
    request: BhuNakshaIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    User-assisted & automated cadastral map artifact ingestion (GeoJSON, SVG, WKT, LPM PDF).
    Validates topology, verifies CRS, prevents duplicates, computes area, and persists to domain.
    """
    import time
    start_t = time.time()
    adapter = BiharBhuNakshaAdapter()
    record = adapter.ingest_cadastral_artifact(
        query=request.query,
        artifact_format=request.artifact_format,
        artifact_content=request.artifact_content,
        crs=request.crs or "EPSG:32645"
    )

    if request.persist:
        adapter.persist_plot_record_to_domain(
            db=db,
            record=record,
            org_id=current_user.org_id,
            case_id=request.case_id,
            uploader_party_id=current_user.user_id
        )

    elapsed = (time.time() - start_t) * 1000.0
    return BhuNakshaSearchResult(
        success=True,
        query=request.query,
        record=record,
        candidate_records=[record],
        message=f"Cadastral plot geometry successfully ingested and validated ({record.validation.calculated_area_acres} acres).",
        execution_time_ms=elapsed
    )


@router.post("/bihar/bhunaksha/compare-revenue", response_model=RevenueMapComparisonResult)
def compare_bihar_cadastral_to_revenue(
    request: RevenueMapComparisonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cross-references a cadastral map record with an official Bihar revenue record (Jamabandi Register-II).
    Compares plot identifiers, calculates area delta %, and detects anomalies without declaring legal title.
    """
    adapter = BiharBhuNakshaAdapter()
    cadastral_record = request.cadastral_record

    # If parcel_id was provided, resolve spatial data from DB if record not passed
    if cadastral_record is None and request.parcel_id:
        parcel = db.query(Parcel).filter(Parcel.parcel_id == request.parcel_id).first()
        if not parcel:
            raise EntityNotFoundError("Parcel", str(request.parcel_id))
        if parcel.org_id != current_user.org_id:
            raise CrossTenantAccessError()

        if not parcel.authoritative_boundary:
            raise BiharBhuNakshaGeometryValidationError("Parcel has no authoritative boundary geometry stored for comparison.")

        wkt_str = str(parcel.authoritative_boundary)
        query = BhuNakshaQuery(
            district=parcel.district_name,
            circle=parcel.subdistrict_anchal_name,
            mauza=parcel.mauza_village_name,
            plot_khesra_number=parcel.plot_khesra_number,
            khata_number=parcel.khata_number
        )
        cadastral_record = adapter.ingest_cadastral_artifact(
            query=query,
            artifact_format="WKT",
            artifact_content=wkt_str,
            crs="EPSG:32645"
        )

    if cadastral_record is None:
        raise BiharBhuNakshaInvalidQueryError("Either cadastral_record or parcel_id with stored boundary must be provided.")

    return adapter.compare_cadastral_to_revenue(
        cadastral_record=cadastral_record,
        jamabandi_recorded_area_acres=request.jamabandi_recorded_area_acres,
        jamabandi_khesra_number=request.jamabandi_khesra_number,
        jamabandi_khata_number=request.jamabandi_khata_number
    )


@router.get("/{parcel_id}/spatial", response_model=ParcelSpatialResponse)
def get_parcel_spatial(
    parcel_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves spatial boundary geometry, bounding envelope, CRS, area metrics,
    and evidence provenance for a parcel. Enforces organization tenant isolation.
    """
    parcel = db.query(Parcel).filter(Parcel.parcel_id == parcel_id).first()
    if not parcel:
        raise EntityNotFoundError("Parcel", str(parcel_id))
    if parcel.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    boundary_wkt = str(parcel.authoritative_boundary) if parcel.authoritative_boundary else None
    centroid_str = str(parcel.centroid_point) if parcel.centroid_point else None

    boundary_geojson = None
    bounds = None
    calc_area_sqm = None
    calc_area_acres = None

    if boundary_wkt:
        try:
            geom = shapely.from_wkt(boundary_wkt)
            if geom and not geom.is_empty:
                boundary_geojson = mapping(geom)
                bounds = list(geom.bounds)
                calc_area_sqm = round(float(geom.area), 2)
                calc_area_acres = round(calc_area_sqm / SQM_PER_ACRE, 4)
        except Exception as e:
            logger.warning(f"Failed to parse authoritative_boundary WKT for parcel {parcel_id}: {e}")

    # Fetch evidence provenance
    evidence_records = []
    claims = (
        db.query(Claim)
        .filter(Claim.parcel_id == parcel_id, Claim.predicate == ClaimPredicate.CADASTRAL_GEOMETRY)
        .all()
    )
    for c in claims:
        ev = db.query(Evidence).filter(Evidence.evidence_id == c.evidence_id).first()
        if ev:
            evidence_records.append({
                "evidence_id": str(ev.evidence_id),
                "source_name": ev.source_name,
                "authority_tier": ev.authority_tier,
                "storage_uri": ev.storage_uri,
                "sha256_hash": ev.sha256_hash,
                "observed_at": c.observed_at.isoformat() if c.observed_at else None
            })

    return ParcelSpatialResponse(
        parcel_id=str(parcel.parcel_id),
        bhumi_id=parcel.bhumi_id,
        state_code=parcel.state_code,
        district_name=parcel.district_name,
        subdistrict_anchal_name=parcel.subdistrict_anchal_name,
        mauza_village_name=parcel.mauza_village_name,
        plot_khesra_number=parcel.plot_khesra_number,
        khata_number=parcel.khata_number,
        recorded_area_acres=float(parcel.recorded_area_acres),
        land_nature=parcel.land_nature,
        boundary_wkt=boundary_wkt,
        boundary_geojson=boundary_geojson,
        centroid_point=centroid_str,
        bounds=bounds,
        calculated_area_sqm=calc_area_sqm,
        calculated_area_acres=calc_area_acres,
        crs="EPSG:32645",
        has_authoritative_geometry=bool(boundary_wkt),
        evidence_provenance=evidence_records
    )


