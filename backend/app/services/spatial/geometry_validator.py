"""
Bhumi Setu - Parcel Geometry Validation & Normalization Service.

Enforces topological validity, repairs non-destructive defects (e.g. self-intersections),
and calculates ground metrics (area in sqm and acres, perimeter, centroid) using
projected coordinate reference systems (EPSG:32645).
"""

from typing import Tuple, Dict, Any, Union, Optional
import shapely
from shapely.geometry import Polygon, MultiPolygon, shape, mapping
from shapely.validation import explain_validity, make_valid

from app.services.spatial.crs import (
    validate_crs,
    transform_geometry_to_metric,
    transform_geometry_to_wgs84,
    is_within_bihar_bounds,
    SpatialReferenceError,
)

ACRES_PER_SQM = 1.0 / 4046.8564224


class GeometryValidationError(ValueError):
    """Raised when a parcel geometry is empty, non-polygonal, or topologically defective."""
    pass


def validate_and_measure_parcel_geometry(
    raw_geom: Union[Polygon, MultiPolygon, Dict[str, Any], str],
    input_crs: str = "EPSG:4326",
    allow_repair: bool = True
) -> Dict[str, Any]:
    """
    Validates, repairs, and extracts standardized spatial metrics from a parcel boundary.
    Returns:
        - normalized_geom_wgs84 (Polygon/MultiPolygon in EPSG:4326)
        - wkt_wgs84 (str)
        - geojson_wgs84 (Dict)
        - calculated_area_sqm (float in EPSG:32645)
        - calculated_area_acres (float)
        - perimeter_meters (float in EPSG:32645)
        - centroid_lat (float)
        - centroid_lon (float)
        - is_valid (bool)
        - validation_error (Optional[str])
    """
    clean_crs = validate_crs(input_crs)

    # 1. Parse into Shapely geometry
    geom: Union[Polygon, MultiPolygon]
    if isinstance(raw_geom, (Polygon, MultiPolygon)):
        geom = raw_geom
    elif isinstance(raw_geom, dict):
        geom = shape(raw_geom)
    elif isinstance(raw_geom, str):
        clean_str = raw_geom.strip()
        if clean_str.startswith("{"):
            import json
            data = json.loads(clean_str)
            geom = shape(data)
        else:
            geom = shapely.from_wkt(clean_str)
    else:
        raise GeometryValidationError(f"Unsupported geometry type: {type(raw_geom)}")

    if geom is None or geom.is_empty:
        raise GeometryValidationError("Parcel boundary geometry is empty.")

    if not isinstance(geom, (Polygon, MultiPolygon)):
        raise GeometryValidationError(
            f"Cadastral boundary must be a Polygon or MultiPolygon. Received: {geom.geom_type}"
        )

    # 2. Topology validation & repair
    is_valid = geom.is_valid
    validation_error = None
    if not is_valid:
        validation_error = explain_validity(geom)
        if allow_repair:
            repaired = make_valid(geom)
            if isinstance(repaired, (Polygon, MultiPolygon)) and repaired.is_valid and not repaired.is_empty:
                geom = repaired
                is_valid = True
            else:
                raise GeometryValidationError(f"Irreparable topological defect: {validation_error}")
        else:
            raise GeometryValidationError(f"Invalid polygon geometry: {validation_error}")

    # 3. Standardize to WGS84 for storage and display
    if clean_crs == "EPSG:32645":
        geom_wgs84 = transform_geometry_to_wgs84(geom, source_crs="EPSG:32645")
        geom_metric = geom
    elif clean_crs == "EPSG:4326":
        geom_wgs84 = geom
        geom_metric = transform_geometry_to_metric(geom, source_crs="EPSG:4326")
    else:
        raise SpatialReferenceError(f"Unsupported CRS for parcel measurement: {clean_crs}")

    # 4. Calculate metric planar measurements
    area_sqm = float(geom_metric.area)
    area_acres = area_sqm * ACRES_PER_SQM
    perimeter_m = float(geom_metric.length)

    # Centroid in WGS84
    centroid = geom_wgs84.centroid
    c_lon = float(centroid.x)
    c_lat = float(centroid.y)

    return {
        "geometry_wgs84": geom_wgs84,
        "wkt_wgs84": shapely.to_wkt(geom_wgs84),
        "geojson_wgs84": mapping(geom_wgs84),
        "calculated_area_sqm": round(area_sqm, 2),
        "calculated_area_acres": round(area_acres, 4),
        "perimeter_meters": round(perimeter_m, 2),
        "centroid_lat": round(c_lat, 6),
        "centroid_lon": round(c_lon, 6),
        "is_valid": is_valid,
        "validation_error": validation_error,
    }
