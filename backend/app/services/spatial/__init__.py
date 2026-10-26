"""
Bhumi Setu - Spatial & Cadastral Vector Overlay Engine Package.
"""

from app.services.spatial.crs import (
    validate_crs,
    project_wgs84_to_utm45n,
    unproject_utm45n_to_wgs84,
    transform_geometry_to_metric,
    transform_geometry_to_wgs84,
    is_within_bihar_bounds,
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
    transform_pixel_polygon_to_ground,
    GeoreferenceSolveResult,
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

__all__ = [
    "validate_crs",
    "project_wgs84_to_utm45n",
    "unproject_utm45n_to_wgs84",
    "transform_geometry_to_metric",
    "transform_geometry_to_wgs84",
    "is_within_bihar_bounds",
    "SpatialReferenceError",
    "process_cadastral_upload",
    "detect_file_format_and_magic",
    "parse_geojson_to_geometry",
    "parse_kml_to_polygon",
    "extract_kmz_archive",
    "GeospatialIngestionError",
    "UnsafeArchiveError",
    "GroundControlPoint",
    "solve_affine_transformation",
    "transform_pixel_to_ground",
    "transform_pixel_polygon_to_ground",
    "GeoreferenceSolveResult",
    "GeoreferencingError",
    "validate_and_measure_parcel_geometry",
    "GeometryValidationError",
    "compute_boundary_overlay_analysis",
    "STATUTORY_CADASTRAL_DISCLAIMER",
    "CadastralOverlayService",
]
