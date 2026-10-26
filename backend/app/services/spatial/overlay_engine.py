"""
Bhumi Setu - Boundary Overlay & Discrepancy Analysis Engine.

Performs deterministic, explainable geometric comparisons between two parcel boundaries:
    - Baseline Geometry (e.g. Historical Cadastral Survey sheet boundary)
    - Comparison Geometry (e.g. Modern Bhu-Naksha, field GNSS survey, or deed sketch)

Metrological Rigor:
    - Transforms geometries to projected metric CRS (EPSG:32645 - UTM Zone 45N)
    - Calculates true ground measurements:
        * Intersection Area (sqm)
        * Union Area (sqm)
        * Intersection over Union (IoU / Jaccard Index)
        * Symmetric Difference Area (sqm)
        * Centroid Displacement Distance (meters)
        * Hausdorff Distance / Maximum Boundary Discrepancy (meters)
        * Area and Perimeter delta percentages

Epistemic & Legal Disclaimers:
    - Geometric variance does NOT constitute proof of illegal encroachment, adverse possession,
      or defective title. Survey era differences (1890s chain survey vs modern GNSS) and paper
      shrinkage naturally produce geometric shifts.
"""

import math
from typing import Dict, Any, Tuple, Optional, Union
import shapely
from shapely.geometry import Polygon, MultiPolygon, mapping

from app.models.spatial_overlay import DiscrepancyTaxonomy, DiscrepancySeverity
from app.services.spatial.crs import (
    validate_crs,
    transform_geometry_to_metric,
    transform_geometry_to_wgs84,
)
from app.services.spatial.geometry_validator import validate_and_measure_parcel_geometry

STATUTORY_CADASTRAL_DISCLAIMER = (
    "Geometric boundary differences represent computational spatial comparisons between independent "
    "survey sources, digitized map sheets, or ground observations. They do not constitute a legal survey, "
    "nor do they establish property title, legal ownership, adverse possession, or illegal encroachment. "
    "Authoritative boundary determination rests solely with the competent revenue authority and survey officer."
)


def compute_boundary_overlay_analysis(
    baseline_geom: Union[Polygon, MultiPolygon, Dict[str, Any], str],
    comparison_geom: Union[Polygon, MultiPolygon, Dict[str, Any], str],
    baseline_crs: str = "EPSG:4326",
    comparison_crs: str = "EPSG:4326",
    positional_uncertainty_meters: Optional[float] = None
) -> Dict[str, Any]:
    """
    Executes a deterministic spatial overlay comparison between baseline and comparison geometries.
    All distance and area metrics are calculated in projected metric CRS (EPSG:32645).
    """
    # 1. Validate both input geometries
    base_eval = validate_and_measure_parcel_geometry(baseline_geom, input_crs=baseline_crs)
    comp_eval = validate_and_measure_parcel_geometry(comparison_geom, input_crs=comparison_crs)

    if not base_eval["is_valid"] or not comp_eval["is_valid"]:
        return {
            "discrepancy_status": DiscrepancyTaxonomy.INVALID_GEOMETRY,
            "discrepancy_severity": DiscrepancySeverity.HIGH,
            "findings_summary": "One or both parcel geometries have invalid topology.",
            "iou_score": 0.0,
            "intersection_area_sqm": 0.0,
            "union_area_sqm": 0.0,
            "symmetric_diff_area_sqm": 0.0,
            "area_delta_percentage": 100.0,
            "perimeter_delta_percentage": 100.0,
            "centroid_displacement_meters": 0.0,
            "hausdorff_distance_meters": 0.0,
            "detailed_metrics": {
                "baseline_validity": base_eval["validation_error"],
                "comparison_validity": comp_eval["validation_error"],
            },
            "statutory_caveat": STATUTORY_CADASTRAL_DISCLAIMER,
        }

    # 2. Transform to metric EPSG:32645 for true planar calculations
    base_metric = transform_geometry_to_metric(base_eval["geometry_wgs84"], source_crs="EPSG:4326")
    comp_metric = transform_geometry_to_metric(comp_eval["geometry_wgs84"], source_crs="EPSG:4326")

    base_area_sqm = float(base_metric.area)
    comp_area_sqm = float(comp_metric.area)
    base_perimeter_m = float(base_metric.length)
    comp_perimeter_m = float(comp_metric.length)

    # 3. Intersect, Union, and Differences
    intersection = base_metric.intersection(comp_metric)
    union = base_metric.union(comp_metric)
    sym_diff = base_metric.symmetric_difference(comp_metric)
    missing_in_comp = base_metric.difference(comp_metric)   # Baseline territory not in comparison
    extra_in_comp = comp_metric.difference(base_metric)     # Comparison territory extending outside baseline

    intersection_area_sqm = float(intersection.area) if not intersection.is_empty else 0.0
    union_area_sqm = float(union.area) if not union.is_empty else (base_area_sqm + comp_area_sqm)
    sym_diff_area_sqm = float(sym_diff.area) if not sym_diff.is_empty else 0.0
    missing_area_sqm = float(missing_in_comp.area) if not missing_in_comp.is_empty else 0.0
    extra_area_sqm = float(extra_in_comp.area) if not extra_in_comp.is_empty else 0.0

    # 4. Intersection over Union (IoU)
    iou_score = intersection_area_sqm / union_area_sqm if union_area_sqm > 0 else 0.0
    iou_score = max(0.0, min(1.0, iou_score))

    # 5. Centroid displacement
    c_base = base_metric.centroid
    c_comp = comp_metric.centroid
    centroid_displacement_meters = math.sqrt((c_base.x - c_comp.x)**2 + (c_base.y - c_comp.y)**2)

    # 6. Hausdorff distance (maximum boundary shift)
    try:
        hausdorff_meters = float(shapely.hausdorff_distance(base_metric, comp_metric))
    except Exception:
        hausdorff_meters = centroid_displacement_meters

    # 7. Deltas
    max_area = max(base_area_sqm, comp_area_sqm)
    area_delta_pct = (abs(base_area_sqm - comp_area_sqm) / max_area * 100.0) if max_area > 0 else 0.0

    max_perim = max(base_perimeter_m, comp_perimeter_m)
    perim_delta_pct = (abs(base_perimeter_m - comp_perimeter_m) / max_perim * 100.0) if max_perim > 0 else 0.0

    # 8. Discrepancy diagnosis taxonomy
    status: DiscrepancyTaxonomy
    severity: DiscrepancySeverity
    summary: str

    if iou_score >= 0.95 and centroid_displacement_meters <= 2.0 and area_delta_pct <= 3.0:
        status = DiscrepancyTaxonomy.NO_SIGNIFICANT_DIFFERENCE_DETECTED
        severity = DiscrepancySeverity.NONE
        summary = (
            f"High geometric concordance (IoU {iou_score:.3f}). Centroid displacement is {centroid_displacement_meters:.2f}m "
            f"and area delta is {area_delta_pct:.2f}%, within acceptable historical survey tolerances."
        )

    elif iou_score == 0.0:
        status = DiscrepancyTaxonomy.POTENTIAL_GEOMETRY_GAP
        severity = DiscrepancySeverity.CRITICAL
        summary = (
            f"Geometries are completely disjoint (IoU 0.00). Centroid displacement is {centroid_displacement_meters:.2f}m. "
            f"Investigate coordinate reference alignment or possible plot number mismatch."
        )

    elif iou_score < 0.50 or centroid_displacement_meters > 10.0 or area_delta_pct > 25.0:
        status = DiscrepancyTaxonomy.POTENTIAL_BOUNDARY_DISCREPANCY
        severity = DiscrepancySeverity.HIGH
        summary = (
            f"Significant boundary discrepancy detected (IoU {iou_score:.3f}). Area variance is {area_delta_pct:.1f}% "
            f"and centroid shift is {centroid_displacement_meters:.2f}m. Ground verification recommended."
        )

    elif missing_area_sqm > extra_area_sqm * 2.0 and missing_area_sqm > 50.0:
        status = DiscrepancyTaxonomy.POTENTIAL_GEOMETRY_GAP
        severity = DiscrepancySeverity.MEDIUM
        summary = (
            f"Apparent geometry gap ({missing_area_sqm:.1f} sqm missing in comparison geometry). "
            f"Centroid displacement is {centroid_displacement_meters:.2f}m."
        )

    elif extra_area_sqm > missing_area_sqm * 2.0 and extra_area_sqm > 50.0:
        status = DiscrepancyTaxonomy.POTENTIAL_GEOMETRY_OVERLAP
        severity = DiscrepancySeverity.MEDIUM
        summary = (
            f"Comparison geometry extends {extra_area_sqm:.1f} sqm beyond baseline cadastral demarcations. "
            f"Centroid displacement is {centroid_displacement_meters:.2f}m."
        )

    elif positional_uncertainty_meters and positional_uncertainty_meters > 5.0:
        status = DiscrepancyTaxonomy.REQUIRES_HUMAN_REVIEW
        severity = DiscrepancySeverity.LOW
        summary = (
            f"Moderate boundary shift (IoU {iou_score:.3f}) with high source positional uncertainty "
            f"(±{positional_uncertainty_meters:.1f}m). Requires operator inspection."
        )

    else:
        status = DiscrepancyTaxonomy.POTENTIAL_BOUNDARY_DISCREPANCY
        severity = DiscrepancySeverity.LOW
        summary = (
            f"Minor boundary discrepancy (IoU {iou_score:.3f}). Area delta is {area_delta_pct:.2f}% "
            f"and centroid displacement is {centroid_displacement_meters:.2f}m."
        )

    # 9. Format WGS84 GeoJSON difference geometries for display in UI
    diff_geojson = None
    if not sym_diff.is_empty:
        sym_diff_wgs84 = transform_geometry_to_wgs84(sym_diff, source_crs="EPSG:32645")
        diff_geojson = mapping(sym_diff_wgs84)

    return {
        "discrepancy_status": status,
        "discrepancy_severity": severity,
        "findings_summary": summary,
        "iou_score": round(iou_score, 4),
        "intersection_area_sqm": round(intersection_area_sqm, 2),
        "union_area_sqm": round(union_area_sqm, 2),
        "symmetric_diff_area_sqm": round(sym_diff_area_sqm, 2),
        "area_delta_percentage": round(area_delta_pct, 2),
        "perimeter_delta_percentage": round(perim_delta_pct, 2),
        "centroid_displacement_meters": round(centroid_displacement_meters, 2),
        "hausdorff_distance_meters": round(hausdorff_meters, 2),
        "detailed_metrics": {
            "baseline_area_sqm": round(base_area_sqm, 2),
            "comparison_area_sqm": round(comp_area_sqm, 2),
            "baseline_perimeter_meters": round(base_perimeter_m, 2),
            "comparison_perimeter_meters": round(comp_perimeter_m, 2),
            "missing_in_comparison_sqm": round(missing_area_sqm, 2),
            "extra_in_comparison_sqm": round(extra_area_sqm, 2),
            "baseline_centroid": [round(c_base.x, 2), round(c_base.y, 2)],
            "comparison_centroid": [round(c_comp.x, 2), round(c_comp.y, 2)],
            "difference_geojson": diff_geojson,
        },
        "statutory_caveat": STATUTORY_CADASTRAL_DISCLAIMER,
    }
