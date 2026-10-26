"""
Bhumi Setu - Coordinate Reference Systems (CRS) and Projection Engine.

Supported Coordinate Reference Systems:
    - EPSG:4326: WGS 84 geographic latitude/longitude (standard API and storage CRS).
    - EPSG:32645: WGS 84 / UTM Zone 45N (official Bihar DILRMP survey projection).
      Central meridian 87°E covers Bihar (longitude 83.3°E to 88.3°E).
      Units: true ground meters. Suitable for planar distance, perimeter, and area metrology.
    - EPSG:3857: WGS 84 / Pseudo-Mercator (Web tile displays only; not for cadastral area metrology).
"""

import math
from typing import Tuple, List, Union
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely.ops import transform as shapely_transform

# Bihar Administrative Bounding Box (WGS 84 degrees)
BIHAR_BOUNDS_WGS84 = {
    "min_lon": 83.18,
    "max_lon": 88.30,
    "min_lat": 24.28,
    "max_lat": 27.53,
}

# WGS 84 Ellipsoid Constants
WGS84_A = 6378137.0                  # Semi-major axis in meters
WGS84_F = 1.0 / 298.257223563        # Flattening
WGS84_B = WGS84_A * (1.0 - WGS84_F)  # Semi-minor axis in meters
WGS84_E2 = 2.0 * WGS84_F - WGS84_F**2 # First eccentricity squared
WGS84_E_PRIME2 = WGS84_E2 / (1.0 - WGS84_E2) # Second eccentricity squared

# UTM Zone 45N Parameters for Bihar
UTM_ZONE_45N_CENTRAL_MERIDIAN = 87.0 # degrees East
UTM_FALSE_EASTING = 500000.0         # meters
UTM_FALSE_NORTHING = 0.0             # meters (Northern Hemisphere)
UTM_SCALE_FACTOR = 0.9996            # Central scale reduction factor


class SpatialReferenceError(ValueError):
    """Raised when an invalid, unsupported, or out-of-bounds CRS is encountered."""
    pass


def validate_crs(crs: str) -> str:
    """
    Validates and standardizes a CRS identifier string.
    Rejects unknown or ambiguous coordinate reference systems.
    """
    if not crs or not isinstance(crs, str):
        raise SpatialReferenceError("Coordinate Reference System (CRS) must be explicitly specified.")
    
    clean = crs.strip().upper()
    if clean.startswith("URN:OGC:DEF:CRS:"):
        clean = "EPSG:" + clean.split(":")[-1]

    if clean in ("EPSG:4326", "WGS84", "CRS84", "OGC:CRS84"):
        return "EPSG:4326"
    elif clean in ("EPSG:32645", "UTM45N", "WGS 84 / UTM ZONE 45N"):
        return "EPSG:32645"
    elif clean in ("EPSG:3857", "EPSG:900913", "WEB_MERCATOR"):
        return "EPSG:3857"
    else:
        raise SpatialReferenceError(
            f"Unsupported CRS '{crs}'. Bhumi Setu requires 'EPSG:4326' (WGS 84) "
            f"or 'EPSG:32645' (UTM Zone 45N) for cadastral operations."
        )


def is_within_bihar_bounds(lon: float, lat: float) -> bool:
    """Verifies that geographic coordinates fall within Bihar territory."""
    return (
        BIHAR_BOUNDS_WGS84["min_lon"] <= lon <= BIHAR_BOUNDS_WGS84["max_lon"] and
        BIHAR_BOUNDS_WGS84["min_lat"] <= lat <= BIHAR_BOUNDS_WGS84["max_lat"]
    )


def project_wgs84_to_utm45n(lat: float, lon: float) -> Tuple[float, float]:
    """
    Direct forward Transverse Mercator ellipsoidal projection from WGS 84 (lat, lon)
    to UTM Zone 45N Easting and Northing (EPSG:32645) in meters.
    Mathematically rigorous to millimeter precision without external C library dependencies.
    """
    phi = math.radians(lat)
    lambda_rad = math.radians(lon)
    lambda_0 = math.radians(UTM_ZONE_45N_CENTRAL_MERIDIAN)
    delta_lambda = lambda_rad - lambda_0

    sin_phi = math.sin(phi)
    cos_phi = math.cos(phi)
    tan_phi = math.tan(phi)

    N = WGS84_A / math.sqrt(1.0 - WGS84_E2 * sin_phi**2)
    T = tan_phi**2
    C = WGS84_E_PRIME2 * cos_phi**2
    A = cos_phi * delta_lambda

    # Meridional distance M
    M = WGS84_A * (
        (1.0 - WGS84_E2 / 4.0 - 3.0 * WGS84_E2**2 / 64.0 - 5.0 * WGS84_E2**3 / 256.0) * phi
        - (3.0 * WGS84_E2 / 8.0 + 3.0 * WGS84_E2**2 / 32.0 + 45.0 * WGS84_E2**3 / 1024.0) * math.sin(2.0 * phi)
        + (15.0 * WGS84_E2**2 / 256.0 + 45.0 * WGS84_E2**3 / 1024.0) * math.sin(4.0 * phi)
        - (35.0 * WGS84_E2**3 / 3072.0) * math.sin(6.0 * phi)
    )

    # Easting
    easting = UTM_FALSE_EASTING + UTM_SCALE_FACTOR * N * (
        A
        + (1.0 - T + C) * A**3 / 6.0
        + (5.0 - 18.0 * T + T**2 + 72.0 * C - 58.0 * WGS84_E_PRIME2) * A**5 / 120.0
    )

    # Northing
    northing = UTM_FALSE_NORTHING + UTM_SCALE_FACTOR * (
        M + N * tan_phi * (
            A**2 / 2.0
            + (5.0 - T + 9.0 * C + 4.0 * C**2) * A**4 / 24.0
            + (61.0 - 58.0 * T + T**2 + 600.0 * C - 330.0 * WGS84_E_PRIME2) * A**6 / 720.0
        )
    )

    return easting, northing


def unproject_utm45n_to_wgs84(easting: float, northing: float) -> Tuple[float, float]:
    """
    Inverse Transverse Mercator ellipsoidal projection from UTM Zone 45N (Easting, Northing)
    back to WGS 84 geographic latitude and longitude (degrees).
    """
    x = (easting - UTM_FALSE_EASTING) / UTM_SCALE_FACTOR
    y = (northing - UTM_FALSE_NORTHING) / UTM_SCALE_FACTOR

    # Meridional distance to footprint latitude phi_1
    M = y
    mu = M / (WGS84_A * (1.0 - WGS84_E2 / 4.0 - 3.0 * WGS84_E2**2 / 64.0 - 5.0 * WGS84_E2**3 / 256.0))

    e1 = (1.0 - math.sqrt(1.0 - WGS84_E2)) / (1.0 + math.sqrt(1.0 - WGS84_E2))
    phi_1 = (
        mu
        + (3.0 * e1 / 2.0 - 27.0 * e1**3 / 32.0) * math.sin(2.0 * mu)
        + (21.0 * e1**2 / 16.0 - 55.0 * e1**4 / 32.0) * math.sin(4.0 * mu)
        + (151.0 * e1**3 / 96.0) * math.sin(6.0 * mu)
        + (1097.0 * e1**4 / 512.0) * math.sin(8.0 * mu)
    )

    sin_phi1 = math.sin(phi_1)
    cos_phi1 = math.cos(phi_1)
    tan_phi1 = math.tan(phi_1)

    N1 = WGS84_A / math.sqrt(1.0 - WGS84_E2 * sin_phi1**2)
    T1 = tan_phi1**2
    C1 = WGS84_E_PRIME2 * cos_phi1**2
    R1 = WGS84_A * (1.0 - WGS84_E2) / ((1.0 - WGS84_E2 * sin_phi1**2)**1.5)
    D = x / N1

    # Latitude
    lat_rad = phi_1 - (N1 * tan_phi1 / R1) * (
        D**2 / 2.0
        - (5.0 + 3.0 * T1 + 10.0 * C1 - 4.0 * C1**2 - 9.0 * WGS84_E_PRIME2) * D**4 / 24.0
        + (61.0 + 90.0 * T1 + 298.0 * C1 + 45.0 * T1**2 - 252.0 * WGS84_E_PRIME2 - 3.0 * C1**2) * D**6 / 720.0
    )

    # Longitude
    lon_rad = math.radians(UTM_ZONE_45N_CENTRAL_MERIDIAN) + (
        D
        - (1.0 + 2.0 * T1 + C1) * D**3 / 6.0
        + (5.0 - 2.0 * C1 + 28.0 * T1 - 3.0 * C1**2 + 8.0 * WGS84_E_PRIME2 + 24.0 * T1**2) * D**5 / 120.0
    ) / cos_phi1

    return math.degrees(lat_rad), math.degrees(lon_rad)


def transform_geometry_to_metric(geom: Union[Polygon, MultiPolygon], source_crs: str) -> Union[Polygon, MultiPolygon]:
    """
    Transforms a Shapely geometry from source CRS (EPSG:4326) to projected metric CRS (EPSG:32645).
    Enables true metric planar calculations (area in square meters, Hausdorff distance in meters).
    """
    clean_crs = validate_crs(source_crs)
    if clean_crs == "EPSG:32645":
        return geom
    elif clean_crs == "EPSG:4326":
        def _forward(x, y, z=None):
            easting, northing = project_wgs84_to_utm45n(lat=y, lon=x)
            return easting, northing
        return shapely_transform(_forward, geom)
    else:
        raise SpatialReferenceError(f"Cannot directly project geometry from {source_crs} to EPSG:32645.")


def transform_geometry_to_wgs84(geom: Union[Polygon, MultiPolygon], source_crs: str) -> Union[Polygon, MultiPolygon]:
    """
    Transforms a Shapely geometry from source CRS (EPSG:32645) to geographic WGS 84 (EPSG:4326).
    """
    clean_crs = validate_crs(source_crs)
    if clean_crs == "EPSG:4326":
        return geom
    elif clean_crs == "EPSG:32645":
        def _inverse(x, y, z=None):
            lat, lon = unproject_utm45n_to_wgs84(easting=x, northing=y)
            return lon, lat
        return shapely_transform(_inverse, geom)
    else:
        raise SpatialReferenceError(f"Cannot unproject geometry from {source_crs} to EPSG:4326.")
