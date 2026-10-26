"""
Bhumi Setu - Bihar Bhu-Naksha Cadastral Map Ingestion & Spatial Cache Adapter.

Official Source:
    Directorate of Land Records & Survey (DLRS), Department of Revenue and Land Reforms, Government of Bihar.
    Portal URL: https://bhunaksha.bihar.gov.in/
    Gateway: https://biharbhumi.bihar.gov.in/

Operational Characteristics:
    - Provides cadastral village maps (Cadastral Survey / Revision Survey sheets)
      with mapped parcel boundary polygons, Khesra (plot) numbers, and Land Parcel Map (LPM) certificates.
    - Official coordinate reference systems:
        * EPSG:32645 (WGS 84 / UTM Zone 45N - standard DILRMP Bihar projected grid)
        * EPSG:4326 (WGS 84 geographic latitude/longitude)
    - Legal & Epistemic Boundaries:
        * Cadastral maps constitute prima facie evidence of revenue survey demarcation;
          they reflect historical settlement survey lines and fiscal partitions.
        * Map geometry alone does NOT prove current physical possession, absence of adverse
          possession, or lack of unrecorded boundary ridge (aal) encroachments.
        * Official LPM certificates provide indicative cadastral boundaries, not court-decreed title.
"""

from __future__ import annotations

import re
import json
import uuid
import math
import hashlib
import logging
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

import httpx
from pydantic import BaseModel, Field, field_validator
import shapely
from shapely.geometry import shape, mapping, Polygon, MultiPolygon, Point
from shapely.validation import explain_validity, make_valid
from sqlalchemy.orm import Session

from app.core.exceptions import BhumiSetuException
from app.models.base import utc_now
from app.models.parcel import Parcel, ParcelVersion
from app.models.evidence import (
    Evidence,
    EvidenceType,
    AuthorityTier,
    CaseEvidence,
    Document,
    DocumentCategory,
    DocumentProcessingStatus,
)
from app.models.claim import Claim, ClaimPredicate, ClaimStatus
from app.models.case import Case, CaseParcel
from app.services.consistency_service import check_area_delta, ConsistencyCheckResult

logger = logging.getLogger("bhumisetu.scrapers.bhunaksha")

# Standard 38 Districts of Bihar mapped to official NIC Bhu-Naksha 2-digit codes
BIHAR_BHUNAKSHA_DISTRICTS: Dict[str, str] = {
    "NALANDA": "01",
    "PURBI CHAMPARAN": "02",
    "EAST CHAMPARAN": "02",
    "MOTIHARI": "02",
    "SHEOHAR": "03",
    "SITAMARHI": "04",
    "MADHUBANI": "05",
    "SUPAUL": "06",
    "ARARIA": "07",
    "KISHANGANJ": "08",
    "PURNIA": "09",
    "PURNEA": "09",
    "KATIHAR": "10",
    "MADHEPURA": "11",
    "SAHARSA": "12",
    "DARBHANGA": "13",
    "MUZAFFARPUR": "14",
    "GOPALGANJ": "15",
    "SIWAN": "16",
    "SARAN": "17",
    "CHHAPRA": "17",
    "VAISHALI": "18",
    "HAJIPUR": "18",
    "SAMASTIPUR": "19",
    "BEGUSARAI": "20",
    "KHAGARIA": "21",
    "BHAGALPUR": "22",
    "BANKA": "23",
    "MUNGER": "24",
    "MONGHYR": "24",
    "LAKHISARAI": "25",
    "SHEIKHPURA": "26",
    "PASHCHIM CHAMPARAN": "27",
    "WEST CHAMPARAN": "27",
    "BETTIAH": "27",
    "PATNA": "28",
    "BHOJPUR": "29",
    "ARRAH": "29",
    "BUXAR": "30",
    "KAIMUR": "31",
    "BHABUA": "31",
    "ROHTAS": "32",
    "SASARAM": "32",
    "JEHANABAD": "33",
    "AURANGABAD": "34",
    "GAYA": "35",
    "NAWADA": "36",
    "JAMUI": "37",
    "ARWAL": "38",
}

# Bihar Geographic and Projected Spatial Envelopes for Range Validation
BIHAR_BOUNDS_WGS84 = {
    "min_lon": 83.0,
    "max_lon": 88.5,
    "min_lat": 24.0,
    "max_lat": 27.8,
}

BIHAR_BOUNDS_UTM32645 = {
    "min_easting": 150000.0,
    "max_easting": 950000.0,
    "min_northing": 2600000.0,
    "max_northing": 3150000.0,
}

SQM_PER_ACRE = 4046.8564224


# =====================================================================
# Domain Exceptions
# =====================================================================

class BiharBhuNakshaError(BhumiSetuException):
    """Base exception for Bihar Bhu-Naksha cadastral map operations."""
    def __init__(self, message: str, code: str = "BHUNAKSHA_ERROR", status_code: int = 400, details: Optional[Dict[str, Any]] = None):
        super().__init__(code=code, message=message, status_code=status_code, details=details)


class BiharBhuNakshaSourceUnavailableError(BiharBhuNakshaError):
    """Raised when the official Bhu-Naksha portal is unreachable or returns 5xx/gateway error."""
    def __init__(self, message: str = "Bihar Bhu-Naksha GIS portal is temporarily unreachable.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="BHUNAKSHA_UNAVAILABLE", status_code=503, details=details)


class BiharBhuNakshaInvalidQueryError(BiharBhuNakshaError):
    """Raised when location or plot search parameters are missing or invalid."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="BHUNAKSHA_INVALID_QUERY", status_code=422, details=details)


class BiharBhuNakshaNotFoundError(BiharBhuNakshaError):
    """Raised when no digitized cadastral sheet or plot polygon is found for the given criteria."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="BHUNAKSHA_NOT_FOUND", status_code=404, details=details)


class BiharBhuNakshaGeometryValidationError(BiharBhuNakshaError):
    """Raised when cadastral polygon geometry is empty, malformed, topologically invalid, or missing CRS."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="BHUNAKSHA_GEOMETRY_INVALID", status_code=422, details=details)


class BiharBhuNakshaRateLimitError(BiharBhuNakshaError):
    """Raised when upstream server returns HTTP 429 or WAF block."""
    def __init__(self, message: str = "Bihar Bhu-Naksha upstream server rate limit encountered.", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="BHUNAKSHA_RATE_LIMITED", status_code=429, details=details)


class BiharBhuNakshaAmbiguousMatchError(BiharBhuNakshaError):
    """Raised when plot search returns multiple ambiguous polygon candidates."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="BHUNAKSHA_AMBIGUOUS_MATCH", status_code=409, details=details)


# =====================================================================
# Pydantic Request & Response Schemas
# =====================================================================

class BhuNakshaQuery(BaseModel):
    state: str = "Bihar"
    district: str = Field(..., description="Bihar district name or 2-digit code")
    circle: str = Field(..., description="Circle / Anchal name")
    mauza: str = Field(..., description="Revenue village / Mauza name")
    plot_khesra_number: str = Field(..., description="Plot / Khesra number")
    sheet_number: Optional[str] = Field(None, description="Cadastral map sheet number")
    khata_number: Optional[str] = Field(None, description="Optional cross-referenced Khata number")

    @field_validator("district")
    @classmethod
    def validate_district(cls, v: str) -> str:
        clean = v.strip().upper()
        if clean in BIHAR_BHUNAKSHA_DISTRICTS:
            return clean
        # Check if 2-digit code was passed
        for name, code in BIHAR_BHUNAKSHA_DISTRICTS.items():
            if clean == code:
                return name
        valid_sample = ", ".join(sorted(list(BIHAR_BHUNAKSHA_DISTRICTS.keys()))[:8])
        raise ValueError(f"Invalid Bihar district '{v}'. Must be one of 38 official districts (e.g., {valid_sample}).")

    @field_validator("circle", "mauza", "plot_khesra_number")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Field cannot be blank.")
        return clean


class GeometryValidationResult(BaseModel):
    is_valid: bool
    topology_error: Optional[str] = None
    repair_applied: bool = False
    crs: str
    bounds: List[float] = Field(..., description="Bounding box [minx, miny, maxx, maxy]")
    calculated_area_sqm: float
    calculated_area_acres: float
    centroid: Tuple[float, float]
    vertex_count: int


class BhuNakshaPlotRecord(BaseModel):
    state: str = "Bihar"
    district_name: str
    district_code: str
    circle_name: str
    mauza_name: str
    khesra_plot_number: str
    khata_number: Optional[str] = None
    sheet_number: Optional[str] = None
    gis_code: Optional[str] = None
    
    # Geometry and Spatial Metrology
    geometry_geojson: Dict[str, Any]
    geometry_wkt: str
    crs: str = "EPSG:32645"
    validation: GeometryValidationResult
    
    # Adjoining Parcel Neighbors (if captured on map sheet)
    north_neighbor_plot: Optional[str] = None
    south_neighbor_plot: Optional[str] = None
    east_neighbor_plot: Optional[str] = None
    west_neighbor_plot: Optional[str] = None
    
    # Provenance & Audit
    source_format: str = "GEOJSON"  # 'GEOJSON', 'SVG', 'LPM_PDF', 'WMS_VECTOR'
    sha256_hash: str
    retrieval_timestamp: datetime = Field(default_factory=utc_now)
    statutory_caveat: str = (
        "Cadastral map boundaries reflect historical government revenue settlement survey demarcation. "
        "They do not certify real-time physical possession, title, or the absence of boundary encroachments."
    )


class BhuNakshaSearchResult(BaseModel):
    success: bool
    query: BhuNakshaQuery
    record: Optional[BhuNakshaPlotRecord] = None
    candidate_records: List[BhuNakshaPlotRecord] = Field(default_factory=list)
    message: str
    execution_time_ms: float
    retrieval_timestamp: datetime = Field(default_factory=utc_now)


class BhuNakshaIngestRequest(BaseModel):
    query: BhuNakshaQuery
    artifact_format: str = Field(..., description="Format: 'GEOJSON', 'SVG', 'WKT', or 'LPM_PDF'")
    artifact_content: str = Field(..., description="Raw string content or Base64 encoded payload")
    crs: Optional[str] = Field("EPSG:32645", description="Coordinate Reference System (e.g. EPSG:32645 or EPSG:4326)")
    case_id: Optional[uuid.UUID] = None
    persist: bool = True


class RevenueMapComparisonRequest(BaseModel):
    parcel_id: Optional[uuid.UUID] = None
    case_id: Optional[uuid.UUID] = None
    cadastral_record: Optional[BhuNakshaPlotRecord] = None
    jamabandi_recorded_area_acres: Optional[float] = None
    jamabandi_khesra_number: Optional[str] = None
    jamabandi_khata_number: Optional[str] = None


class RevenueMapComparisonResult(BaseModel):
    identifiers_matched: bool
    identifier_match_summary: str
    
    # Area comparison
    recorded_revenue_area_acres: Optional[float] = None
    mapped_cadastral_area_acres: float
    area_delta_pct: Optional[float] = None
    area_consistency_check: Optional[Dict[str, Any]] = None
    
    # Topology and Spatial overlap
    overlap_detected: bool = False
    overlap_area_sqm: Optional[float] = None
    
    # Discrepancies and Findings
    discrepancies: List[str] = Field(default_factory=list)
    status: str  # 'CONCORDANT', 'AREA_DISCREPANCY', 'IDENTIFIER_MISMATCH', 'INSUFFICIENT_DATA'
    statutory_disclaimers: List[str] = Field(default_factory=list)


# =====================================================================
# Geometry Parsing, CRS & Topology Validation Engine
# =====================================================================

def parse_svg_to_polygon(svg_content: str) -> Polygon:
    """
    Parses SVG XML snippet containing <polygon points="..."> or <path d="...">
    and constructs a 2D Shapely Polygon.
    """
    try:
        # Strip XML namespaces or wrap if bare snippet
        wrapped = svg_content.strip()
        if not wrapped.startswith("<svg") and not wrapped.startswith("<?xml"):
            wrapped = f"<svg xmlns='http://www.w3.org/2000/svg'>{wrapped}</svg>"
        
        root = ET.fromstring(wrapped)
        # Search for polygon points
        for elem in root.iter():
            tag = elem.tag.split("}")[-1].lower()
            if tag == "polygon":
                points_str = elem.attrib.get("points", "").strip()
                if points_str:
                    coords = []
                    # Points can be separated by spaces or commas
                    pairs = re.findall(r"([-+]?[0-9]*\.?[0-9]+)[,\s]+([-+]?[0-9]*\.?[0-9]+)", points_str)
                    for x_str, y_str in pairs:
                        coords.append((float(x_str), float(y_str)))
                    if len(coords) >= 3:
                        return Polygon(coords)
            elif tag == "path":
                d = elem.attrib.get("d", "").strip()
                if d:
                    # Extract M/L coordinate pairs
                    pairs = re.findall(r"([ML\s])\s*([-+]?[0-9]*\.?[0-9]+)[,\s]+([-+]?[0-9]*\.?[0-9]+)", d, re.IGNORECASE)
                    coords = [(float(p[1]), float(p[2])) for p in pairs]
                    if len(coords) >= 3:
                        return Polygon(coords)
    except Exception as e:
        raise BiharBhuNakshaGeometryValidationError(f"Failed to parse SVG geometry: {str(e)}")

    raise BiharBhuNakshaGeometryValidationError("No valid <polygon> or <path> coordinates found in SVG artifact.")


def validate_and_normalize_geometry(
    raw_geom: Union[Dict[str, Any], str, Polygon, MultiPolygon],
    crs: Optional[str] = "EPSG:32645",
    allow_repair: bool = True
) -> Tuple[Union[Polygon, MultiPolygon], GeometryValidationResult]:
    """
    Validates, repairs (if safe and non-destructive), and extracts standardized metrics
    from a spatial geometry. Enforces CRS and spatial bounds checking.
    """
    if not crs or not crs.strip():
        raise BiharBhuNakshaGeometryValidationError(
            "Missing or undocumented Coordinate Reference System (CRS). "
            "Bhumi Setu requires explicit CRS (e.g. 'EPSG:32645' or 'EPSG:4326') to prevent coordinate hallucination."
        )

    clean_crs = crs.strip().upper()
    if clean_crs not in ("EPSG:32645", "EPSG:4326", "EPSG:3857"):
        raise BiharBhuNakshaGeometryValidationError(
            f"Unsupported CRS '{crs}'. Supported systems: EPSG:32645 (UTM Zone 45N), EPSG:4326 (WGS 84), EPSG:3857 (Web Mercator)."
        )

    # 1. Parse into Shapely Geometry
    geom: Optional[Union[Polygon, MultiPolygon]] = None
    try:
        if isinstance(raw_geom, (Polygon, MultiPolygon)):
            geom = raw_geom
        elif isinstance(raw_geom, dict):
            # GeoJSON dict
            if raw_geom.get("type") == "Feature":
                geom = shape(raw_geom.get("geometry", {}))
            elif raw_geom.get("type") == "FeatureCollection":
                features = raw_geom.get("features", [])
                if not features:
                    raise BiharBhuNakshaGeometryValidationError("FeatureCollection contains 0 features.")
                geom = shape(features[0].get("geometry", {}))
            else:
                geom = shape(raw_geom)
        elif isinstance(raw_geom, str):
            clean_str = raw_geom.strip()
            if clean_str.startswith("{"):
                # GeoJSON string
                parsed = json.loads(clean_str)
                if parsed.get("type") == "Feature":
                    geom = shape(parsed.get("geometry", {}))
                elif parsed.get("type") == "FeatureCollection":
                    features = parsed.get("features", [])
                    if not features:
                        raise BiharBhuNakshaGeometryValidationError("FeatureCollection contains 0 features.")
                    geom = shape(features[0].get("geometry", {}))
                else:
                    geom = shape(parsed)
            elif "<svg" in clean_str.lower() or "<polygon" in clean_str.lower() or "<path" in clean_str.lower():
                geom = parse_svg_to_polygon(clean_str)
            elif clean_str.upper().startswith("POLYGON") or clean_str.upper().startswith("MULTIPOLYGON"):
                geom = shapely.from_wkt(clean_str)
            else:
                raise BiharBhuNakshaGeometryValidationError(f"Unrecognized geometry string format. Must be GeoJSON, WKT, or SVG.")
        else:
            raise BiharBhuNakshaGeometryValidationError(f"Unsupported geometry object type: {type(raw_geom)}")
    except Exception as e:
        if isinstance(e, BiharBhuNakshaGeometryValidationError):
            raise
        raise BiharBhuNakshaGeometryValidationError(f"Geometry parsing error: {str(e)}")

    if geom is None or geom.is_empty:
        raise BiharBhuNakshaGeometryValidationError("Parsed geometry is empty (0 vertices).")

    if not isinstance(geom, (Polygon, MultiPolygon)):
        raise BiharBhuNakshaGeometryValidationError(
            f"Cadastral plot geometry must be a Polygon or MultiPolygon. Found: {geom.geom_type}"
        )

    # 2. Topology Validation
    is_valid = geom.is_valid
    topology_error = None
    repair_applied = False

    if not is_valid:
        topology_error = explain_validity(geom)
        if allow_repair:
            repaired = make_valid(geom)
            if isinstance(repaired, (Polygon, MultiPolygon)) and repaired.is_valid and not repaired.is_empty:
                geom = repaired
                repair_applied = True
                is_valid = True
                logger.info(f"Geometry repaired using make_valid. Original defect: {topology_error}")
            else:
                raise BiharBhuNakshaGeometryValidationError(
                    f"Irreparable topological defect in plot boundary: {topology_error}"
                )
        else:
            raise BiharBhuNakshaGeometryValidationError(
                f"Invalid polygon topology: {topology_error}"
            )

    # 3. Coordinate Envelope Range Check (Bihar Spatial Sanity)
    bounds = list(geom.bounds)  # [minx, miny, maxx, maxy]
    minx, miny, maxx, maxy = bounds

    if clean_crs == "EPSG:4326":
        if (minx < BIHAR_BOUNDS_WGS84["min_lon"] or maxx > BIHAR_BOUNDS_WGS84["max_lon"] or
            miny < BIHAR_BOUNDS_WGS84["min_lat"] or maxy > BIHAR_BOUNDS_WGS84["max_lat"]):
            raise BiharBhuNakshaGeometryValidationError(
                f"Coordinates {bounds} fall outside Bihar administrative bounds in WGS 84 "
                f"(Lon {BIHAR_BOUNDS_WGS84['min_lon']}-{BIHAR_BOUNDS_WGS84['max_lon']}, "
                f"Lat {BIHAR_BOUNDS_WGS84['min_lat']}-{BIHAR_BOUNDS_WGS84['max_lat']})."
            )
    elif clean_crs == "EPSG:32645":
        if (minx < BIHAR_BOUNDS_UTM32645["min_easting"] or maxx > BIHAR_BOUNDS_UTM32645["max_easting"] or
            miny < BIHAR_BOUNDS_UTM32645["min_northing"] or maxy > BIHAR_BOUNDS_UTM32645["max_northing"]):
            raise BiharBhuNakshaGeometryValidationError(
                f"Coordinates {bounds} fall outside Bihar UTM Zone 45N bounds "
                f"(Easting {BIHAR_BOUNDS_UTM32645['min_easting']}-{BIHAR_BOUNDS_UTM32645['max_easting']}, "
                f"Northing {BIHAR_BOUNDS_UTM32645['min_northing']}-{BIHAR_BOUNDS_UTM32645['max_northing']})."
            )

    # 4. Area & Metrology Calculation
    if clean_crs == "EPSG:32645":
        # Projected meters
        calc_area_sqm = round(float(geom.area), 2)
        calc_area_acres = round(calc_area_sqm / SQM_PER_ACRE, 4)
    elif clean_crs == "EPSG:4326":
        # Geographic degrees: approximate geodesic area using mid-latitude scale
        mid_lat = (miny + maxy) / 2.0
        lat_rad = math.radians(mid_lat)
        deg_to_m_lat = 110540.0
        deg_to_m_lon = 111320.0 * math.cos(lat_rad)
        # Approximate scaling factor
        scale_factor = deg_to_m_lat * deg_to_m_lon
        calc_area_sqm = round(float(geom.area) * scale_factor, 2)
        calc_area_acres = round(calc_area_sqm / SQM_PER_ACRE, 4)
    else:
        calc_area_sqm = round(float(geom.area), 2)
        calc_area_acres = round(calc_area_sqm / SQM_PER_ACRE, 4)

    centroid_pt = geom.centroid
    centroid = (round(float(centroid_pt.x), 6), round(float(centroid_pt.y), 6))

    # Vertex count
    if isinstance(geom, Polygon):
        vertex_count = len(geom.exterior.coords)
    else:
        vertex_count = sum(len(p.exterior.coords) for p in geom.geoms)

    val_result = GeometryValidationResult(
        is_valid=is_valid,
        topology_error=topology_error,
        repair_applied=repair_applied,
        crs=clean_crs,
        bounds=bounds,
        calculated_area_sqm=calc_area_sqm,
        calculated_area_acres=calc_area_acres,
        centroid=centroid,
        vertex_count=vertex_count
    )

    return geom, val_result


# =====================================================================
# Upstream Bhu-Naksha Live Client
# =====================================================================

class BhuNakshaLiveClient:
    """
    Client for observing, querying, and interacting with the official
    Bihar Bhu-Naksha portal (https://bhunaksha.bihar.gov.in/).
    Maintains F5 WAF session tokens and connection pooling.
    """
    BASE_URL = "https://bhunaksha.bihar.gov.in"
    TIMEOUT = httpx.Timeout(connect=10.0, read=25.0, write=15.0, pool=30.0)

    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        self._client = http_client
        self.cookie_jar: Dict[str, str] = {}

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
            "Referer": f"{self.BASE_URL}/10/indexmain.jsp",
            "Origin": self.BASE_URL,
        }
        if self.cookie_jar:
            headers["Cookie"] = "; ".join([f"{k}={v}" for k, v in self.cookie_jar.items()])
        return headers

    def _update_cookies(self, response: httpx.Response) -> None:
        for k, v in response.cookies.items():
            self.cookie_jar[k] = v

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                verify=False,
                follow_redirects=True,
                timeout=self.TIMEOUT,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        return self._client

    async def init_session(self) -> None:
        """Warps initial gateway to acquire JSESSIONID and WAF ASM TS012e5105 tokens."""
        client = await self.get_client()
        try:
            res = await client.get(f"{self.BASE_URL}/10/index.jsp", headers=self._get_headers())
            self._update_cookies(res)
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise BiharBhuNakshaSourceUnavailableError(
                f"Failed to establish connection to Bihar Bhu-Naksha portal: {str(e)}"
            )

    async def get_village_extent_georef(self, gis_levels: str) -> Dict[str, Any]:
        """
        Queries /rest/MapInfo/getVVVVExtentGeoref to acquire CRS, bounding box, and GIS Code.
        """
        client = await self.get_client()
        if not self.cookie_jar:
            await self.init_session()

        data = {
            "state": "10",
            "gisLevels": gis_levels,
            "srs": "0"
        }
        try:
            res = await client.post(
                f"{self.BASE_URL}/rest/MapInfo/getVVVVExtentGeoref",
                data=data,
                headers=self._get_headers()
            )
            self._update_cookies(res)
            if res.status_code == 429:
                raise BiharBhuNakshaRateLimitError("Upstream Bhu-Naksha portal rate limit encountered.")
            if res.status_code != 200:
                raise BiharBhuNakshaSourceUnavailableError(f"Map extent query failed with HTTP {res.status_code}")
            return res.json()
        except httpx.HTTPError as e:
            raise BiharBhuNakshaSourceUnavailableError(f"HTTP communication error querying Bhu-Naksha: {str(e)}")

    async def fetch_lpm_report_pdf(self, gis_code: str, plot_no: str) -> bytes:
        """
        Retrieves official Land Parcel Map (LPM) Certificate PDF from /rest/Reports/PlotReportPDF.
        Returns decoded binary PDF bytes.
        """
        import base64
        client = await self.get_client()
        if not self.cookie_jar:
            await self.init_session()

        data = {
            "state": "10",
            "giscode": gis_code,
            "plotno": str(plot_no),
            "sameownerplotreport": "false",
            "derivedlayerids": "-1",
            "selectedlayerids": "-1",
            "scaletextfield": "0"
        }
        try:
            res = await client.post(
                f"{self.BASE_URL}/rest/Reports/PlotReportPDF",
                data=data,
                headers=self._get_headers()
            )
            self._update_cookies(res)
            if res.status_code == 429:
                raise BiharBhuNakshaRateLimitError("Upstream LPM Report server rate limit encountered.")
            if res.status_code != 200:
                raise BiharBhuNakshaSourceUnavailableError(f"PlotReportPDF failed with status {res.status_code}")

            body_text = res.text.strip()
            if not body_text.startswith("JVBERi0"):
                raise BiharBhuNakshaNotFoundError(
                    f"Bihar Bhu-Naksha returned no valid LPM Certificate PDF for plot #{plot_no} in GIS code {gis_code}."
                )

            return base64.b64decode(body_text)
        except httpx.HTTPError as e:
            raise BiharBhuNakshaSourceUnavailableError(f"LPM report request failed: {str(e)}")


# =====================================================================
# Core Adapter Implementation
# =====================================================================

class BiharBhuNakshaAdapter:
    """
    Cadastral Map Ingestion, Geometry Normalization, Spatial Verification,
    and Epistemic Evidence Generation Adapter for Bihar Bhu-Naksha.
    """

    def __init__(self, live_client: Optional[BhuNakshaLiveClient] = None):
        self.live_client = live_client or BhuNakshaLiveClient()

    def get_district_code(self, district_name: str) -> str:
        clean = district_name.strip().upper()
        if clean not in BIHAR_BHUNAKSHA_DISTRICTS:
            raise BiharBhuNakshaInvalidQueryError(f"Unknown district name '{district_name}' for Bihar.")
        return BIHAR_BHUNAKSHA_DISTRICTS[clean]

    def ingest_cadastral_artifact(
        self,
        query: BhuNakshaQuery,
        artifact_format: str,
        artifact_content: str,
        crs: str = "EPSG:32645",
        khata_number: Optional[str] = None
    ) -> BhuNakshaPlotRecord:
        """
        Ingests user-supplied or system-retrieved cadastral map artifact
        (GeoJSON, SVG, WKT, or LPM Certificate PDF Base64).
        Validates geometry, computes cryptographic SHA-256 digest, and constructs normalized record.
        """
        if not artifact_content or not artifact_content.strip():
            raise BiharBhuNakshaGeometryValidationError("Empty artifact content provided for cadastral ingestion.")

        clean_format = artifact_format.strip().upper()
        content_bytes = artifact_content.encode("utf-8")
        sha256_hash = hashlib.sha256(content_bytes).hexdigest()

        # Parse and validate geometry
        geom, val_result = validate_and_normalize_geometry(
            raw_geom=artifact_content,
            crs=crs,
            allow_repair=True
        )

        dist_code = self.get_district_code(query.district)

        return BhuNakshaPlotRecord(
            state="Bihar",
            district_name=query.district,
            district_code=dist_code,
            circle_name=query.circle,
            mauza_name=query.mauza,
            khesra_plot_number=query.plot_khesra_number,
            khata_number=khata_number or query.khata_number,
            sheet_number=query.sheet_number,
            gis_code=f"BR-{dist_code}-{query.mauza[:4].upper()}",
            geometry_geojson=mapping(geom),
            geometry_wkt=shapely.to_wkt(geom),
            crs=val_result.crs,
            validation=val_result,
            source_format=clean_format,
            sha256_hash=sha256_hash,
            retrieval_timestamp=utc_now()
        )

    def persist_plot_record_to_domain(
        self,
        db: Session,
        record: BhuNakshaPlotRecord,
        org_id: uuid.UUID,
        case_id: Optional[uuid.UUID] = None,
        uploader_party_id: Optional[uuid.UUID] = None
    ) -> Parcel:
        """
        Persists validated cadastral plot geometry into the authoritative domain model:
        1. Generates canonical bhumi_id (`BR-{DIST}-{CIRCLE}-{MAUZA}-PL{PLOT}`).
        2. Idempotently creates or updates the Parcel record with boundary geometry and centroid.
        3. Creates a ParcelVersion record documenting the change reason.
        4. Anchors an immutable Evidence row with SHA-256 hash and authority tier.
        5. Associates with active Case if case_id provided.
        6. Formulates an auditable Claim entity with ClaimPredicate.CADASTRAL_GEOMETRY.
        """
        # Canonical composite identifier
        clean_dist = re.sub(r"[^A-Z0-9]", "", record.district_name.upper())[:3]
        clean_circle = re.sub(r"[^A-Z0-9]", "", record.circle_name.upper())[:3]
        clean_mauza = re.sub(r"[^A-Z0-9]", "", record.mauza_name.upper())[:3]
        clean_plot = re.sub(r"[^A-Z0-9]", "", record.khesra_plot_number.upper())
        canonical_bhumi_id = f"BR-{clean_dist}-{clean_circle}-{clean_mauza}-PL{clean_plot}"

        # 1. Idempotent Parcel Lookup
        existing_parcel = (
            db.query(Parcel)
            .filter(
                Parcel.org_id == org_id,
                Parcel.state_code == "BR",
                Parcel.district_name == record.district_name,
                Parcel.subdistrict_anchal_name == record.circle_name,
                Parcel.mauza_village_name == record.mauza_name,
                Parcel.plot_khesra_number == record.khesra_plot_number
            )
            .first()
        )

        wkt_boundary = record.geometry_wkt
        centroid_wkt = f"POINT({record.validation.centroid[0]} {record.validation.centroid[1]})"

        if existing_parcel:
            parcel = existing_parcel
            # Update authoritative boundary & centroid
            parcel.authoritative_boundary = wkt_boundary
            parcel.centroid_point = centroid_wkt
            if record.khata_number and (not parcel.khata_number or parcel.khata_number == "UNKNOWN"):
                parcel.khata_number = record.khata_number
        else:
            parcel = Parcel(
                parcel_id=uuid.uuid4(),
                org_id=org_id,
                bhumi_id=canonical_bhumi_id,
                state_code="BR",
                district_name=record.district_name,
                subdistrict_anchal_name=record.circle_name,
                halka_number="UNKNOWN",
                mauza_village_name=record.mauza_name,
                census_village_code=record.gis_code or "BR000000",
                khata_number=record.khata_number or "UNKNOWN",
                plot_khesra_number=record.khesra_plot_number,
                subdivision_hissa_number=None,
                recorded_area_acres=record.validation.calculated_area_acres,
                land_nature="AGRICULTURAL_RAIYATI",
                centroid_point=centroid_wkt,
                authoritative_boundary=wkt_boundary
            )
            db.add(parcel)
            db.flush()

        # 2. Append ParcelVersion (Audit Trail)
        existing_versions_count = (
            db.query(ParcelVersion)
            .filter(ParcelVersion.parcel_id == parcel.parcel_id)
            .count()
        )
        version = ParcelVersion(
            version_id=uuid.uuid4(),
            parcel_id=parcel.parcel_id,
            version_number=existing_versions_count + 1,
            recorded_area_acres=record.validation.calculated_area_acres,
            boundary_geometry=wkt_boundary,
            change_reason="BHUNAKSHA_CADASTRAL_INGESTION"
        )
        db.add(version)

        # 3. Prevent duplicate evidence creation via content hash
        existing_evidence = (
            db.query(Evidence)
            .filter(Evidence.sha256_hash == record.sha256_hash)
            .first()
        )
        if not existing_evidence:
            storage_uri = f"source://bhunaksha/cadastral/{record.district_name}/{record.mauza_name}/plot_{record.khesra_plot_number}"
            evidence = Evidence(
                evidence_id=uuid.uuid4(),
                evidence_type=EvidenceType.MAP,
                authority_tier=AuthorityTier.REVENUE_RECORD,
                source_name=f"Bihar Bhu-Naksha Cadastral Survey ({record.district_name})",
                storage_uri=storage_uri,
                sha256_hash=record.sha256_hash,
                captured_by_party_id=uploader_party_id,
                captured_at=record.retrieval_timestamp,
                evidence_metadata={
                    "portal": "bhunaksha.bihar.gov.in",
                    "gis_code": record.gis_code,
                    "sheet_number": record.sheet_number,
                    "crs": record.crs,
                    "calculated_area_sqm": record.validation.calculated_area_sqm,
                    "calculated_area_acres": record.validation.calculated_area_acres,
                    "bounds": record.validation.bounds,
                    "repair_applied": record.validation.repair_applied,
                    "parser_version": "BhuNakshaCadastralParser-v1.0"
                }
            )
            db.add(evidence)
            db.flush()
        else:
            evidence = existing_evidence

        # 4. Link to Case if requested
        if case_id:
            case_exists = db.query(Case).filter(Case.case_id == case_id).first()
            if case_exists:
                case_parcel_link = (
                    db.query(CaseParcel)
                    .filter(CaseParcel.case_id == case_id, CaseParcel.parcel_id == parcel.parcel_id)
                    .first()
                )
                if not case_parcel_link:
                    db.add(CaseParcel(case_id=case_id, parcel_id=parcel.parcel_id, is_primary=True))

                case_ev_link = (
                    db.query(CaseEvidence)
                    .filter(CaseEvidence.case_id == case_id, CaseEvidence.evidence_id == evidence.evidence_id)
                    .first()
                )
                if not case_ev_link:
                    db.add(CaseEvidence(case_id=case_id, evidence_id=evidence.evidence_id))

        # 5. Formulate Epistemic Claim
        claim = Claim(
            claim_id=uuid.uuid4(),
            case_id=case_id or uuid.uuid4(),  # Scoped or standalone
            parcel_id=parcel.parcel_id,
            evidence_id=evidence.evidence_id,
            subject_entity_type="PARCEL",
            subject_id=parcel.parcel_id,
            predicate=ClaimPredicate.CADASTRAL_GEOMETRY,
            object_value={
                "geometry": record.geometry_geojson,
                "crs": record.crs,
                "calculated_area_sqm": record.validation.calculated_area_sqm,
                "calculated_area_acres": record.validation.calculated_area_acres,
                "sheet_number": record.sheet_number,
                "gis_code": record.gis_code,
                "source_format": record.source_format,
                "statutory_disclaimer": record.statutory_caveat
            },
            authority_tier=AuthorityTier.REVENUE_RECORD,
            confidence_score=1.0,
            observed_at=record.retrieval_timestamp
        )
        db.add(claim)
        db.flush()

        return parcel

    def compare_cadastral_to_revenue(
        self,
        cadastral_record: BhuNakshaPlotRecord,
        jamabandi_recorded_area_acres: Optional[float] = None,
        jamabandi_khesra_number: Optional[str] = None,
        jamabandi_khata_number: Optional[str] = None,
        tolerance_pct: float = 5.0
    ) -> RevenueMapComparisonResult:
        """
        Cross-references cadastral map boundary record against official Bihar Jamabandi Register-II record:
        - Compares plot/khesra identifier match.
        - Compares revenue recorded area vs GIS calculated polygon area using check_area_delta.
        - Emits structured discrepancies without asserting unsupported legal conclusions.
        """
        discrepancies: List[str] = []
        
        # 1. Identifier Concordance
        plot_matched = True
        if jamabandi_khesra_number:
            if jamabandi_khesra_number.strip() != cadastral_record.khesra_plot_number.strip():
                plot_matched = False
                discrepancies.append(
                    f"Khesra number mismatch: Map indicates #{cadastral_record.khesra_plot_number}, "
                    f"while Revenue record specifies #{jamabandi_khesra_number}."
                )

        if jamabandi_khata_number and cadastral_record.khata_number:
            if jamabandi_khata_number.strip() != cadastral_record.khata_number.strip():
                discrepancies.append(
                    f"Khata number mismatch: Map attribute indicates #{cadastral_record.khata_number}, "
                    f"while Revenue record specifies #{jamabandi_khata_number}."
                )

        identifier_summary = (
            f"Khesra #{cadastral_record.khesra_plot_number} verified concordant across spatial map and revenue ledger."
            if plot_matched
            else f"Spatial-revenue identifier mismatch detected for plot #{cadastral_record.khesra_plot_number}."
        )

        # 2. Area Metrology Comparison
        area_check_dict = None
        delta_pct = None
        mapped_area_acres = cadastral_record.validation.calculated_area_acres

        if jamabandi_recorded_area_acres is not None and jamabandi_recorded_area_acres > 0:
            jamabandi_area_sqm = jamabandi_recorded_area_acres * SQM_PER_ACRE
            map_area_sqm = cadastral_record.validation.calculated_area_sqm

            res = check_area_delta(
                deed_area_sqm=jamabandi_area_sqm,
                survey_area_sqm=map_area_sqm,
                tolerance_pct=tolerance_pct
            )
            area_check_dict = {
                "rule_id": res.rule_id,
                "passed": res.passed,
                "severity": res.severity,
                "observed_values": res.observed_values,
                "explanation": res.explanation,
                "recommended_action": res.recommended_action
            }
            delta_pct = res.observed_values.get("delta_pct")
            if not res.passed:
                discrepancies.append(res.explanation)

        # 3. Overall Status Determination
        if not plot_matched:
            status = "IDENTIFIER_MISMATCH"
        elif discrepancies:
            status = "AREA_DISCREPANCY"
        elif jamabandi_recorded_area_acres is None:
            status = "INSUFFICIENT_DATA"
        else:
            status = "CONCORDANT"

        disclaimers = [
            "Cadastral map boundaries represent historical fiscal survey demarcation, not certified possession.",
            "Area differences exceeding tolerance warrant ground verification by a licensed Field Amin.",
            "This automated comparison does not constitute a legal determination of boundary dispute or title validity."
        ]

        return RevenueMapComparisonResult(
            identifiers_matched=plot_matched,
            identifier_match_summary=identifier_summary,
            recorded_revenue_area_acres=jamabandi_recorded_area_acres,
            mapped_cadastral_area_acres=mapped_area_acres,
            area_delta_pct=delta_pct,
            area_consistency_check=area_check_dict,
            overlap_detected=False,
            discrepancies=discrepancies,
            status=status,
            statutory_disclaimers=disclaimers
        )
