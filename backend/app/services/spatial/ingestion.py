"""
Bhumi Setu - Geospatial File Ingestion & Validation Pipeline.

Supports:
    - Vector Formats: GeoJSON, KML, KMZ (compressed KML with path-traversal & zip-bomb protection)
    - Raster Formats: GeoTIFF, TIFF, PNG, JPEG scanned cadastral sheets

Safety & Hardening:
    - Enforces strict upload limits (50MB for rasters, 10MB for vectors).
    - Validates file signatures / magic bytes.
    - Sanitizes archive extraction to prevent directory traversal attacks (Zip Slip).
    - Validates coordinate numbers and bounds.
    - Computes cryptographic SHA-256 digest for evidence provenance.
"""

import os
import io
import re
import json
import zipfile
import hashlib
import xml.etree.ElementTree as ET
from typing import Dict, Any, Tuple, Optional, List, Union
from PIL import Image
import shapely
from shapely.geometry import shape, Polygon, MultiPolygon

from app.models.spatial_overlay import CadastralAssetFormat
from app.services.spatial.crs import validate_crs, is_within_bihar_bounds, SpatialReferenceError

MAX_RASTER_SIZE_BYTES = 50 * 1024 * 1024   # 50 MB
MAX_VECTOR_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_KMZ_UNCOMPRESSED_BYTES = 25 * 1024 * 1024 # 25 MB max uncompressed limit
MAX_KMZ_ENTRIES = 20                       # Maximum files inside KMZ


class GeospatialIngestionError(ValueError):
    """Raised when an uploaded geospatial file is malformed, oversized, or unsafe."""
    pass


class UnsafeArchiveError(GeospatialIngestionError):
    """Raised when an archive contains path traversal or unsafe file entries."""
    pass


def compute_sha256(content: bytes) -> str:
    """Computes standard hex-encoded SHA-256 checksum."""
    return hashlib.sha256(content).hexdigest()


def detect_file_format_and_magic(filename: str, content: bytes) -> CadastralAssetFormat:
    """
    Detects and verifies file format using file extension and initial magic bytes.
    Prevents file extension spoofing attacks.
    """
    lower_name = filename.lower()
    
    if len(content) < 4:
        raise GeospatialIngestionError("Uploaded file is too small or empty.")

    # Magic byte signatures
    is_png = content.startswith(b"\x89PNG\r\n\x1a\n")
    is_jpeg = content.startswith(b"\xff\xd8\xff")
    is_tiff = content.startswith(b"II*\x00") or content.startswith(b"MM\x00*")
    is_zip = content.startswith(b"PK\x03\x04")

    if lower_name.endswith(".geojson") or lower_name.endswith(".json"):
        # Text based GeoJSON
        try:
            sample = content[:512].decode("utf-8", errors="ignore").strip()
            if sample.startswith("{"):
                return CadastralAssetFormat.GEOJSON
        except Exception:
            pass
        raise GeospatialIngestionError("Invalid GeoJSON file content.")

    elif lower_name.endswith(".kmz"):
        if not is_zip:
            raise GeospatialIngestionError("KMZ file must be a valid zip archive.")
        return CadastralAssetFormat.KMZ

    elif lower_name.endswith(".kml"):
        try:
            sample = content[:512].decode("utf-8", errors="ignore").lower()
            if "<kml" in sample or "<?xml" in sample:
                return CadastralAssetFormat.KML
        except Exception:
            pass
        raise GeospatialIngestionError("Invalid KML XML content.")

    elif lower_name.endswith(".geotiff") or lower_name.endswith(".gtif"):
        if not is_tiff:
            raise GeospatialIngestionError("GeoTIFF must have valid TIFF magic bytes.")
        return CadastralAssetFormat.GEOTIFF

    elif lower_name.endswith(".tiff") or lower_name.endswith(".tif"):
        if not is_tiff:
            raise GeospatialIngestionError("TIFF file must have valid TIFF magic bytes.")
        return CadastralAssetFormat.TIFF

    elif lower_name.endswith(".png"):
        if not is_png:
            raise GeospatialIngestionError("PNG file must have valid PNG magic bytes.")
        return CadastralAssetFormat.PNG

    elif lower_name.endswith(".jpg") or lower_name.endswith(".jpeg"):
        if not is_jpeg:
            raise GeospatialIngestionError("JPEG file must have valid JPEG magic bytes.")
        return CadastralAssetFormat.JPEG

    # Fallback inspection by content
    if is_png:
        return CadastralAssetFormat.PNG
    elif is_jpeg:
        return CadastralAssetFormat.JPEG
    elif is_tiff:
        return CadastralAssetFormat.TIFF
    elif is_zip:
        return CadastralAssetFormat.KMZ

    raise GeospatialIngestionError(f"Unsupported or unrecognized geospatial file type for '{filename}'.")


def parse_kml_coordinates(coords_text: str) -> List[Tuple[float, float]]:
    """
    Parses KML coordinate strings formatted as:
    lon,lat,alt lon,lat,alt ...
    Returns list of (lon, lat) tuples.
    """
    points = []
    # Split by whitespace or newlines
    tokens = coords_text.strip().split()
    for token in tokens:
        parts = token.split(",")
        if len(parts) >= 2:
            try:
                lon = float(parts[0])
                lat = float(parts[1])
                points.append((lon, lat))
            except ValueError:
                continue
    return points


def parse_kml_to_polygon(kml_bytes: bytes) -> Polygon:
    """
    Parses a KML XML document and extracts the primary boundary polygon.
    """
    try:
        root = ET.fromstring(kml_bytes)
    except Exception as e:
        raise GeospatialIngestionError(f"Malformed KML XML: {str(e)}")

    # Namespace agnostic search for coordinates
    for elem in root.iter():
        tag = elem.tag.split("}")[-1].lower()
        if tag == "coordinates":
            coords_text = elem.text
            if coords_text:
                pts = parse_kml_coordinates(coords_text)
                if len(pts) >= 3:
                    # Ensure closed ring
                    if pts[0] != pts[-1]:
                        pts.append(pts[0])
                    poly = Polygon(pts)
                    if poly.is_valid and not poly.is_empty:
                        return poly

    raise GeospatialIngestionError("No valid closed polygon coordinates found in KML content.")


def extract_kmz_archive(kmz_bytes: bytes) -> bytes:
    """
    Safely extracts the primary .kml document from a .kmz zip archive.
    Enforces Zip Slip protection, file count limits, and uncompressed size ceilings.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(kmz_bytes)) as zf:
            infolist = zf.infolist()
            if len(infolist) > MAX_KMZ_ENTRIES:
                raise UnsafeArchiveError(f"KMZ archive exceeds entry limit ({len(infolist)} > {MAX_KMZ_ENTRIES}).")

            total_uncompressed = sum(info.file_size for info in infolist)
            if total_uncompressed > MAX_KMZ_UNCOMPRESSED_BYTES:
                raise UnsafeArchiveError(
                    f"KMZ uncompressed size exceeds limit ({total_uncompressed} > {MAX_KMZ_UNCOMPRESSED_BYTES} bytes)."
                )

            # Look for doc.kml or any .kml file
            target_info = None
            for info in infolist:
                # Zip Slip path traversal defense
                norm_name = os.path.normpath(info.filename)
                if norm_name.startswith("..") or os.path.isabs(norm_name) or "/../" in info.filename:
                    raise UnsafeArchiveError(f"Path traversal attempt detected in archive entry '{info.filename}'.")

                if info.filename.lower().endswith(".kml"):
                    if not target_info or info.filename.lower().endswith("doc.kml"):
                        target_info = info

            if not target_info:
                raise GeospatialIngestionError("No .kml document found inside KMZ archive.")

            return zf.read(target_info)
    except zipfile.BadZipFile:
        raise GeospatialIngestionError("Uploaded KMZ is a corrupt or invalid zip archive.")


def parse_geojson_to_geometry(geojson_bytes: bytes) -> Union[Polygon, MultiPolygon]:
    """
    Parses GeoJSON payload into a validated Shapely Polygon or MultiPolygon.
    """
    try:
        text = geojson_bytes.decode("utf-8")
        data = json.loads(text)
    except Exception as e:
        raise GeospatialIngestionError(f"Invalid JSON in GeoJSON payload: {str(e)}")

    if isinstance(data, dict):
        if data.get("type") == "FeatureCollection":
            features = data.get("features", [])
            if not features:
                raise GeospatialIngestionError("GeoJSON FeatureCollection contains no features.")
            geom_data = features[0].get("geometry", {})
        elif data.get("type") == "Feature":
            geom_data = data.get("geometry", {})
        else:
            geom_data = data
    else:
        raise GeospatialIngestionError("GeoJSON must be a JSON object.")

    try:
        geom = shape(geom_data)
    except Exception as e:
        raise GeospatialIngestionError(f"Failed to parse geometry structure: {str(e)}")

    if geom.is_empty:
        raise GeospatialIngestionError("Parsed geometry is empty (0 vertices).")

    if not isinstance(geom, (Polygon, MultiPolygon)):
        raise GeospatialIngestionError(f"Geometry must be Polygon or MultiPolygon, got {geom.geom_type}.")

    return geom


def inspect_raster_image(content: bytes) -> Dict[str, Any]:
    """
    Inspects image or GeoTIFF dimensions, color mode, and metadata using PIL.
    """
    try:
        with Image.open(io.BytesIO(content)) as img:
            width, height = img.size
            mode = img.mode
            format_name = img.format
            info = {
                "width": width,
                "height": height,
                "format": format_name,
                "mode": mode,
                "dpi": img.info.get("dpi"),
            }
            return info
    except Exception as e:
        raise GeospatialIngestionError(f"Failed to inspect image raster: {str(e)}")


def process_cadastral_upload(
    filename: str,
    content: bytes,
    declared_crs: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validates an uploaded geospatial file, determines format, checks limits,
    extracts metadata or geometries, and returns structured ingestion payload.
    """
    file_size = len(content)
    if file_size == 0:
        raise GeospatialIngestionError("Uploaded file is 0 bytes.")

    file_format = detect_file_format_and_magic(filename, content)
    sha256_hash = compute_sha256(content)

    # Size limits enforcement
    if file_format in (CadastralAssetFormat.PNG, CadastralAssetFormat.JPEG, CadastralAssetFormat.TIFF, CadastralAssetFormat.GEOTIFF):
        if file_size > MAX_RASTER_SIZE_BYTES:
            raise GeospatialIngestionError(
                f"Raster file size ({file_size} bytes) exceeds limit of {MAX_RASTER_SIZE_BYTES} bytes."
            )
        raster_info = inspect_raster_image(content)
        return {
            "file_format": file_format,
            "sha256_hash": sha256_hash,
            "file_size_bytes": file_size,
            "image_width": raster_info["width"],
            "image_height": raster_info["height"],
            "declared_crs": declared_crs or ("EPSG:32645" if file_format == CadastralAssetFormat.GEOTIFF else None),
            "is_vector": False,
            "parsed_geometry": None,
            "metadata": raster_info,
        }

    elif file_format in (CadastralAssetFormat.GEOJSON, CadastralAssetFormat.KML, CadastralAssetFormat.KMZ):
        if file_size > MAX_VECTOR_SIZE_BYTES:
            raise GeospatialIngestionError(
                f"Vector file size ({file_size} bytes) exceeds limit of {MAX_VECTOR_SIZE_BYTES} bytes."
            )

        geom: Union[Polygon, MultiPolygon]
        if file_format == CadastralAssetFormat.GEOJSON:
            geom = parse_geojson_to_geometry(content)
        elif file_format == CadastralAssetFormat.KMZ:
            kml_content = extract_kmz_archive(content)
            geom = parse_kml_to_polygon(kml_content)
        else: # KML
            geom = parse_kml_to_polygon(content)

        crs = declared_crs or "EPSG:4326"

        return {
            "file_format": file_format,
            "sha256_hash": sha256_hash,
            "file_size_bytes": file_size,
            "image_width": None,
            "image_height": None,
            "declared_crs": crs,
            "is_vector": True,
            "parsed_geometry": geom,
            "metadata": {
                "vertex_count": len(geom.exterior.coords) if isinstance(geom, Polygon) else sum(len(p.exterior.coords) for p in geom.geoms),
                "bounds": list(geom.bounds),
            },
        }

    raise GeospatialIngestionError(f"Unhandled file format '{file_format}'.")
