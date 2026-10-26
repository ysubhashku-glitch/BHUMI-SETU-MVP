"""
Bhumi Setu - Cadastral Vector Overlay & Boundary Discrepancy Schemas.
"""

import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.spatial_overlay import (
    CadastralAssetFormat,
    CadastralSourceType,
    GeoreferenceTransformMethod,
    GeoreferenceSessionStatus,
    ParcelGeometryRole,
    DiscrepancyTaxonomy,
    DiscrepancySeverity,
    BoundaryReviewDecision,
)
from app.services.spatial.overlay_engine import STATUTORY_CADASTRAL_DISCLAIMER


class CadastralMapAssetResponse(BaseModel):
    asset_id: uuid.UUID
    org_id: uuid.UUID
    case_id: Optional[uuid.UUID] = None
    parcel_id: Optional[uuid.UUID] = None
    asset_name: str
    file_format: CadastralAssetFormat
    source_type: CadastralSourceType
    sha256_hash: str
    file_size_bytes: int
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    declared_crs: Optional[str] = None
    is_georeferenced: bool
    district: Optional[str] = None
    anchal: Optional[str] = None
    mauza: Optional[str] = None
    sheet_number: Optional[str] = None
    survey_year: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ControlPointInput(BaseModel):
    gcp_id: str
    image_u: float
    image_v: float
    ground_x: float
    ground_y: float
    is_active: bool = True


class GeoreferenceRequest(BaseModel):
    control_points: List[ControlPointInput]
    method: GeoreferenceTransformMethod = GeoreferenceTransformMethod.AFFINE
    target_crs: str = "EPSG:32645"


class GeoreferenceSessionResponse(BaseModel):
    session_id: uuid.UUID
    org_id: uuid.UUID
    asset_id: uuid.UUID
    transformation_method: GeoreferenceTransformMethod
    target_crs: str
    control_points: List[Dict[str, Any]]
    transformation_parameters: Optional[Dict[str, Any]] = None
    rmse_meters: Optional[float] = None
    max_residual_meters: Optional[float] = None
    status: GeoreferenceSessionStatus
    reviewed_by: Optional[uuid.UUID] = None
    review_comments: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class GeoreferenceVerifyRequest(BaseModel):
    approve: bool
    comments: Optional[str] = None


class ParcelGeometryRegisterRequest(BaseModel):
    geometry_label: str
    raw_geometry: Any = Field(..., description="GeoJSON dict or WKT string")
    geometry_role: ParcelGeometryRole = ParcelGeometryRole.BASELINE_CADASTRAL
    crs: str = "EPSG:4326"
    parcel_id: Optional[uuid.UUID] = None
    case_id: Optional[uuid.UUID] = None
    asset_id: Optional[uuid.UUID] = None
    session_id: Optional[uuid.UUID] = None
    positional_uncertainty_meters: Optional[float] = None
    digitization_method: Optional[str] = None
    source_attribution: Optional[str] = None


class ParcelGeometryResponse(BaseModel):
    geometry_id: uuid.UUID
    org_id: uuid.UUID
    parcel_id: Optional[uuid.UUID] = None
    case_id: Optional[uuid.UUID] = None
    asset_id: Optional[uuid.UUID] = None
    session_id: Optional[uuid.UUID] = None
    geometry_label: str
    geometry_role: ParcelGeometryRole
    crs: str
    calculated_area_sqm: float
    calculated_area_acres: float
    perimeter_meters: float
    centroid_lat: float
    centroid_lon: float
    positional_uncertainty_meters: Optional[float] = None
    is_valid: bool
    validation_error: Optional[str] = None
    raw_geojson: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BoundaryOverlayAnalysisRequest(BaseModel):
    baseline_geometry_id: uuid.UUID
    comparison_geometry_id: uuid.UUID
    case_id: Optional[uuid.UUID] = None
    parcel_id: Optional[uuid.UUID] = None


class BoundaryOverlayAnalysisResponse(BaseModel):
    analysis_id: uuid.UUID
    org_id: uuid.UUID
    case_id: Optional[uuid.UUID] = None
    parcel_id: Optional[uuid.UUID] = None
    baseline_geometry_id: uuid.UUID
    comparison_geometry_id: uuid.UUID
    analysis_crs: str
    intersection_area_sqm: float
    union_area_sqm: float
    iou_score: float
    symmetric_diff_area_sqm: float
    area_delta_percentage: float
    perimeter_delta_percentage: float
    centroid_displacement_meters: float
    hausdorff_distance_meters: float
    discrepancy_status: DiscrepancyTaxonomy
    discrepancy_severity: DiscrepancySeverity
    findings_summary: str
    detailed_metrics: Dict[str, Any]
    algorithm_version: str
    field_task_id: Optional[uuid.UUID] = None
    statutory_disclaimer: str = STATUTORY_CADASTRAL_DISCLAIMER
    created_at: datetime

    class Config:
        from_attributes = True


class BoundaryReviewRequest(BaseModel):
    decision: BoundaryReviewDecision
    review_notes: str
    dispatch_field_task: bool = False


class BoundaryReviewResponse(BaseModel):
    review_id: uuid.UUID
    org_id: uuid.UUID
    analysis_id: uuid.UUID
    reviewer_id: Optional[uuid.UUID] = None
    decision: BoundaryReviewDecision
    review_notes: str
    field_task_dispatched: bool
    reviewed_at: datetime

    class Config:
        from_attributes = True
