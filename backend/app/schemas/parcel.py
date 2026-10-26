from typing import Optional, List
from datetime import date
from pydantic import BaseModel, Field, ConfigDict

class ParcelCreateRequest(BaseModel):
    state_code: str = "JH"
    district_name: str
    subdistrict_anchal_name: str
    halka_number: Optional[str] = None
    mauza_village_name: str
    census_village_code: str
    khata_number: str
    plot_khesra_number: str
    subdivision_hissa_number: Optional[str] = None
    recorded_area_acres: float
    land_nature: str = "AGRICULTURAL_RAIYATI"
    centroid_lat: Optional[float] = None
    centroid_lon: Optional[float] = None
    boundary_wkt: Optional[str] = None

class ParcelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    parcel_id: str
    org_id: str
    bhumi_id: str
    state_code: str
    district_name: str
    subdistrict_anchal_name: str
    halka_number: Optional[str] = None
    mauza_village_name: str
    census_village_code: str
    khata_number: str
    plot_khesra_number: str
    subdivision_hissa_number: Optional[str] = None
    recorded_area_acres: float
    land_nature: str
    centroid_point: Optional[str] = None
    authoritative_boundary: Optional[str] = None

class ParcelRelationshipCreateRequest(BaseModel):
    parent_parcel_id: str
    child_parcel_id: str
    relationship_type: str  # SUBDIVIDED_TO, MERGED_TO, RENUMBERED_TO, CORRECTED_TO
    effective_date: Optional[date] = None
    mutation_order_reference: Optional[str] = None

class ParcelRelationshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    relationship_id: str
    parent_parcel_id: str
    child_parcel_id: str
    relationship_type: str
    effective_date: date
    mutation_order_reference: Optional[str] = None

class ParcelSpatialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    parcel_id: str
    bhumi_id: str
    state_code: str
    district_name: str
    subdistrict_anchal_name: str
    mauza_village_name: str
    plot_khesra_number: str
    khata_number: str
    recorded_area_acres: float
    land_nature: str
    boundary_wkt: Optional[str] = None
    boundary_geojson: Optional[dict] = None
    centroid_point: Optional[str] = None
    bounds: Optional[List[float]] = None
    calculated_area_sqm: Optional[float] = None
    calculated_area_acres: Optional[float] = None
    crs: str = "EPSG:32645"
    has_authoritative_geometry: bool = False
    evidence_provenance: List[dict] = []

