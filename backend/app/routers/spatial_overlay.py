"""
Bhumi Setu - Cadastral Vector Overlay & Boundary Discrepancy REST API.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_active_user
from app.models.user import User
from app.models.spatial_overlay import (
    CadastralSourceType,
    GeoreferenceTransformMethod,
    ParcelGeometryRole,
    BoundaryReviewDecision,
)
from app.schemas.spatial_overlay import (
    CadastralMapAssetResponse,
    GeoreferenceRequest,
    GeoreferenceSessionResponse,
    GeoreferenceVerifyRequest,
    ParcelGeometryRegisterRequest,
    ParcelGeometryResponse,
    BoundaryOverlayAnalysisRequest,
    BoundaryOverlayAnalysisResponse,
    BoundaryReviewRequest,
    BoundaryReviewResponse,
)
from app.services.spatial.service import CadastralOverlayService

router = APIRouter(prefix="/spatial", tags=["Cadastral Vector Overlay & Spatial Discrepancy"])


@router.post("/maps/upload", response_model=CadastralMapAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_cadastral_map(
    file: UploadFile = File(...),
    source_type: CadastralSourceType = Form(CadastralSourceType.CADASTRAL_SURVEY_SHEET),
    case_id: Optional[uuid.UUID] = Form(None),
    parcel_id: Optional[uuid.UUID] = Form(None),
    district: Optional[str] = Form(None),
    anchal: Optional[str] = Form(None),
    mauza: Optional[str] = Form(None),
    sheet_number: Optional[str] = Form(None),
    survey_year: Optional[int] = Form(None),
    declared_crs: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Upload and register a historical cadastral map scan, GeoTIFF, or vector overlay.
    """
    content = await file.read()
    service = CadastralOverlayService(db)
    asset = service.upload_map_asset(
        org_id=current_user.org_id,
        filename=file.filename or "uploaded_map",
        content=content,
        source_type=source_type,
        case_id=case_id,
        parcel_id=parcel_id,
        district=district,
        anchal=anchal,
        mauza=mauza,
        sheet_number=sheet_number,
        survey_year=survey_year,
        declared_crs=declared_crs,
    )
    return asset


@router.get("/maps", response_model=List[CadastralMapAssetResponse])
def list_cadastral_maps(
    case_id: Optional[uuid.UUID] = None,
    parcel_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List cadastral map assets within the authenticated organization."""
    service = CadastralOverlayService(db)
    return service.list_map_assets(org_id=current_user.org_id, case_id=case_id, parcel_id=parcel_id)


@router.get("/maps/{asset_id}", response_model=CadastralMapAssetResponse)
def get_cadastral_map(
    asset_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Retrieve details and metadata for a specific cadastral map asset."""
    service = CadastralOverlayService(db)
    return service.get_map_asset(asset_id, current_user.org_id)


@router.post("/maps/{asset_id}/georeference", response_model=GeoreferenceSessionResponse)
def georeference_cadastral_map(
    asset_id: uuid.UUID,
    payload: GeoreferenceRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Submits control points linking map pixels to survey ground coordinates, solves
    transformation parameters, and computes residual error metrics (RMSE).
    """
    service = CadastralOverlayService(db)
    return service.georeference_map_asset(
        asset_id=asset_id,
        org_id=current_user.org_id,
        control_points=[p.model_dump() for p in payload.control_points],
        method=payload.method,
        target_crs=payload.target_crs,
    )


@router.post("/georeference/{session_id}/verify", response_model=GeoreferenceSessionResponse)
def verify_georeference_session(
    session_id: uuid.UUID,
    payload: GeoreferenceVerifyRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Reviews and formally approves or rejects a georeferenced session."""
    service = CadastralOverlayService(db)
    return service.verify_georeference_session(
        session_id=session_id,
        org_id=current_user.org_id,
        reviewer_id=current_user.user_id,
        approve=payload.approve,
        comments=payload.comments,
    )


@router.post("/geometries/register", response_model=ParcelGeometryResponse, status_code=status.HTTP_201_CREATED)
def register_parcel_geometry(
    payload: ParcelGeometryRegisterRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Registers a validated parcel boundary geometry (e.g. baseline cadastral or modern survey).
    """
    service = CadastralOverlayService(db)
    return service.register_parcel_geometry(
        org_id=current_user.org_id,
        geometry_label=payload.geometry_label,
        raw_geometry=payload.raw_geometry,
        geometry_role=payload.geometry_role,
        crs=payload.crs,
        parcel_id=payload.parcel_id,
        case_id=payload.case_id,
        asset_id=payload.asset_id,
        session_id=payload.session_id,
        positional_uncertainty_meters=payload.positional_uncertainty_meters,
        digitization_method=payload.digitization_method,
        source_attribution=payload.source_attribution,
    )


@router.get("/geometries", response_model=List[ParcelGeometryResponse])
def list_parcel_geometries(
    parcel_id: Optional[uuid.UUID] = None,
    case_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Lists registered parcel geometries for a parcel or case."""
    service = CadastralOverlayService(db)
    return service.list_parcel_geometries(
        org_id=current_user.org_id,
        parcel_id=parcel_id,
        case_id=case_id,
    )


@router.post("/overlay/analyze", response_model=BoundaryOverlayAnalysisResponse, status_code=status.HTTP_201_CREATED)
def analyze_boundary_overlay(
    payload: BoundaryOverlayAnalysisRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Executes deterministic boundary overlay comparison between two parcel geometries,
    calculating IoU, symmetric difference, centroid shift, and discrepancy diagnosis.
    """
    service = CadastralOverlayService(db)
    return service.run_boundary_overlay_analysis(
        org_id=current_user.org_id,
        baseline_geometry_id=payload.baseline_geometry_id,
        comparison_geometry_id=payload.comparison_geometry_id,
        case_id=payload.case_id,
        parcel_id=payload.parcel_id,
    )


@router.post("/overlay/{analysis_id}/review", response_model=BoundaryReviewResponse)
def submit_boundary_discrepancy_review(
    analysis_id: uuid.UUID,
    payload: BoundaryReviewRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Records human reviewer decision for a boundary discrepancy and optionally dispatches
    a LandAmin Field Verification Task.
    """
    service = CadastralOverlayService(db)
    return service.submit_boundary_review(
        analysis_id=analysis_id,
        org_id=current_user.org_id,
        reviewer_id=current_user.user_id,
        decision=payload.decision,
        review_notes=payload.review_notes,
        dispatch_field_task=payload.dispatch_field_task,
    )
