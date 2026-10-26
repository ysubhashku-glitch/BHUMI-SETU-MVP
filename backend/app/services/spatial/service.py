"""
Bhumi Setu - Cadastral Overlay Subsystem Orchestration Service.

Coordinates:
    - Map asset ingestion and storage
    - Georeferencing session computation and approval
    - Parcel boundary geometry registration
    - Boundary overlay discrepancy analysis
    - Human and LandAmin review workflow
    - Field task dispatching for unresolved boundary discrepancies
    - Multi-tenant isolation enforcement
"""

import uuid
import os
import shutil
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.spatial_overlay import (
    CadastralMapAsset,
    GeoreferenceSession,
    CadastralParcelGeometry,
    BoundaryOverlayAnalysis,
    BoundaryDiscrepancyReview,
    CadastralAssetFormat,
    CadastralSourceType,
    GeoreferenceTransformMethod,
    GeoreferenceSessionStatus,
    ParcelGeometryRole,
    BoundaryReviewDecision,
    DiscrepancyTaxonomy,
    DiscrepancySeverity,
)
from app.models.case import Case
from app.models.parcel import Parcel
from app.models.field_task import FieldVerificationTask, TaskStatus, TaskPriority
from app.models.user import User
from app.core.exceptions import EntityNotFoundError, CrossTenantAccessError, BusinessRuleViolationError
from app.services.spatial.ingestion import process_cadastral_upload
from app.services.spatial.georeferencing import (
    GroundControlPoint,
    solve_affine_transformation,
)
from app.services.spatial.geometry_validator import validate_and_measure_parcel_geometry
from app.services.spatial.overlay_engine import compute_boundary_overlay_analysis

STORAGE_DIR = os.path.join("storage", "cadastral_maps")


class CadastralOverlayService:
    def __init__(self, db: Session):
        self.db = db

    def upload_map_asset(
        self,
        org_id: uuid.UUID,
        filename: str,
        content: bytes,
        source_type: CadastralSourceType,
        case_id: Optional[uuid.UUID] = None,
        parcel_id: Optional[uuid.UUID] = None,
        district: Optional[str] = None,
        anchal: Optional[str] = None,
        mauza: Optional[str] = None,
        sheet_number: Optional[str] = None,
        survey_year: Optional[int] = None,
        declared_crs: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CadastralMapAsset:
        """
        Validates, securely stores, and registers a cadastral map asset.
        """
        ingest_res = process_cadastral_upload(filename, content, declared_crs=declared_crs)

        # Save to local storage vault
        os.makedirs(STORAGE_DIR, exist_ok=True)
        safe_name = f"{uuid.uuid4().hex}_{os.path.basename(filename)}"
        disk_path = os.path.join(STORAGE_DIR, safe_name)
        with open(disk_path, "wb") as f:
            f.write(content)

        asset = CadastralMapAsset(
            asset_id=uuid.uuid4(),
            org_id=org_id,
            case_id=case_id,
            parcel_id=parcel_id,
            asset_name=filename,
            file_format=ingest_res["file_format"],
            source_type=source_type,
            storage_path=disk_path,
            sha256_hash=ingest_res["sha256_hash"],
            file_size_bytes=ingest_res["file_size_bytes"],
            image_width=ingest_res["image_width"],
            image_height=ingest_res["image_height"],
            declared_crs=ingest_res["declared_crs"],
            is_georeferenced=(ingest_res["file_format"] == CadastralAssetFormat.GEOTIFF or ingest_res["is_vector"]),
            district=district,
            anchal=anchal,
            mauza=mauza,
            sheet_number=sheet_number,
            survey_year=survey_year,
            provenance_metadata={
                **(metadata or {}),
                "ingest_metadata": ingest_res.get("metadata", {}),
            },
        )
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def get_map_asset(self, asset_id: uuid.UUID, org_id: uuid.UUID) -> CadastralMapAsset:
        asset = self.db.query(CadastralMapAsset).filter(CadastralMapAsset.asset_id == asset_id).first()
        if not asset:
            raise EntityNotFoundError("CadastralMapAsset", asset_id)
        if asset.org_id != org_id:
            raise CrossTenantAccessError("Cannot access cadastral asset across organization boundaries.")
        return asset

    def list_map_assets(
        self,
        org_id: uuid.UUID,
        case_id: Optional[uuid.UUID] = None,
        parcel_id: Optional[uuid.UUID] = None
    ) -> List[CadastralMapAsset]:
        q = self.db.query(CadastralMapAsset).filter(CadastralMapAsset.org_id == org_id)
        if case_id:
            q = q.filter(CadastralMapAsset.case_id == case_id)
        if parcel_id:
            q = q.filter(CadastralMapAsset.parcel_id == parcel_id)
        return q.order_by(CadastralMapAsset.created_at.desc()).all()

    def georeference_map_asset(
        self,
        asset_id: uuid.UUID,
        org_id: uuid.UUID,
        control_points: List[Dict[str, Any]],
        method: GeoreferenceTransformMethod = GeoreferenceTransformMethod.AFFINE,
        target_crs: str = "EPSG:32645"
    ) -> GeoreferenceSession:
        """
        Solves transformation parameters for control points, calculates residual error
        metrics, and records georeferencing session.
        """
        asset = self.get_map_asset(asset_id, org_id)

        # Convert to GroundControlPoint models
        gcps = [GroundControlPoint(**p) for p in control_points]
        solve_res = solve_affine_transformation(gcps)

        session = GeoreferenceSession(
            session_id=uuid.uuid4(),
            org_id=org_id,
            asset_id=asset.asset_id,
            transformation_method=method,
            target_crs=target_crs,
            control_points=[g.model_dump() for g in gcps],
            transformation_parameters=solve_res["parameters"],
            rmse_meters=solve_res["rmse_meters"],
            max_residual_meters=solve_res["max_residual_meters"],
            status=GeoreferenceSessionStatus.CALCULATED,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def verify_georeference_session(
        self,
        session_id: uuid.UUID,
        org_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        approve: bool,
        comments: Optional[str] = None
    ) -> GeoreferenceSession:
        session = self.db.query(GeoreferenceSession).filter(GeoreferenceSession.session_id == session_id).first()
        if not session:
            raise EntityNotFoundError("GeoreferenceSession", session_id)
        if session.org_id != org_id:
            raise CrossTenantAccessError("Cannot verify session across tenant boundaries.")

        session.status = GeoreferenceSessionStatus.VERIFIED if approve else GeoreferenceSessionStatus.REJECTED
        session.reviewed_by = reviewer_id
        session.review_comments = comments
        session.reviewed_at = datetime.now(timezone.utc)

        if approve:
            # Mark map asset as georeferenced
            session.map_asset.is_georeferenced = True

        self.db.commit()
        self.db.refresh(session)
        return session

    def register_parcel_geometry(
        self,
        org_id: uuid.UUID,
        geometry_label: str,
        raw_geometry: Any,
        geometry_role: ParcelGeometryRole = ParcelGeometryRole.BASELINE_CADASTRAL,
        crs: str = "EPSG:4326",
        parcel_id: Optional[uuid.UUID] = None,
        case_id: Optional[uuid.UUID] = None,
        asset_id: Optional[uuid.UUID] = None,
        session_id: Optional[uuid.UUID] = None,
        positional_uncertainty_meters: Optional[float] = None,
        digitization_method: Optional[str] = None,
        source_attribution: Optional[str] = None,
    ) -> CadastralParcelGeometry:
        """
        Validates, normalizes, and persists a parcel boundary geometry.
        """
        val_res = validate_and_measure_parcel_geometry(raw_geometry, input_crs=crs)

        geom_record = CadastralParcelGeometry(
            geometry_id=uuid.uuid4(),
            org_id=org_id,
            parcel_id=parcel_id,
            case_id=case_id,
            asset_id=asset_id,
            session_id=session_id,
            geometry_label=geometry_label,
            geometry_role=geometry_role,
            crs="EPSG:4326",
            polygon_geometry=val_res["wkt_wgs84"],
            calculated_area_sqm=val_res["calculated_area_sqm"],
            calculated_area_acres=val_res["calculated_area_acres"],
            perimeter_meters=val_res["perimeter_meters"],
            centroid_lat=val_res["centroid_lat"],
            centroid_lon=val_res["centroid_lon"],
            positional_uncertainty_meters=positional_uncertainty_meters,
            is_valid=val_res["is_valid"],
            validation_error=val_res["validation_error"],
            digitization_method=digitization_method,
            source_attribution=source_attribution,
            raw_geojson=val_res["geojson_wgs84"],
        )
        self.db.add(geom_record)
        self.db.commit()
        self.db.refresh(geom_record)
        return geom_record

    def get_parcel_geometry(self, geometry_id: uuid.UUID, org_id: uuid.UUID) -> CadastralParcelGeometry:
        geom = self.db.query(CadastralParcelGeometry).filter(CadastralParcelGeometry.geometry_id == geometry_id).first()
        if not geom:
            raise EntityNotFoundError("CadastralParcelGeometry", geometry_id)
        if geom.org_id != org_id:
            raise CrossTenantAccessError("Cannot access parcel geometry across tenant boundary.")
        return geom

    def list_parcel_geometries(
        self,
        org_id: uuid.UUID,
        parcel_id: Optional[uuid.UUID] = None,
        case_id: Optional[uuid.UUID] = None
    ) -> List[CadastralParcelGeometry]:
        q = self.db.query(CadastralParcelGeometry).filter(CadastralParcelGeometry.org_id == org_id)
        if parcel_id:
            q = q.filter(CadastralParcelGeometry.parcel_id == parcel_id)
        if case_id:
            q = q.filter(CadastralParcelGeometry.case_id == case_id)
        return q.order_by(CadastralParcelGeometry.created_at.desc()).all()

    def run_boundary_overlay_analysis(
        self,
        org_id: uuid.UUID,
        baseline_geometry_id: uuid.UUID,
        comparison_geometry_id: uuid.UUID,
        case_id: Optional[uuid.UUID] = None,
        parcel_id: Optional[uuid.UUID] = None
    ) -> BoundaryOverlayAnalysis:
        """
        Executes deterministic spatial comparison between two registered geometries.
        """
        base_rec = self.get_parcel_geometry(baseline_geometry_id, org_id)
        comp_rec = self.get_parcel_geometry(comparison_geometry_id, org_id)

        analysis_metrics = compute_boundary_overlay_analysis(
            baseline_geom=base_rec.polygon_geometry,
            comparison_geom=comp_rec.polygon_geometry,
            baseline_crs=base_rec.crs,
            comparison_crs=comp_rec.crs,
            positional_uncertainty_meters=base_rec.positional_uncertainty_meters,
        )

        analysis = BoundaryOverlayAnalysis(
            analysis_id=uuid.uuid4(),
            org_id=org_id,
            case_id=case_id or base_rec.case_id or comp_rec.case_id,
            parcel_id=parcel_id or base_rec.parcel_id or comp_rec.parcel_id,
            baseline_geometry_id=base_rec.geometry_id,
            comparison_geometry_id=comp_rec.geometry_id,
            analysis_crs="EPSG:32645",
            intersection_area_sqm=analysis_metrics["intersection_area_sqm"],
            union_area_sqm=analysis_metrics["union_area_sqm"],
            iou_score=analysis_metrics["iou_score"],
            symmetric_diff_area_sqm=analysis_metrics["symmetric_diff_area_sqm"],
            area_delta_percentage=analysis_metrics["area_delta_percentage"],
            perimeter_delta_percentage=analysis_metrics["perimeter_delta_percentage"],
            centroid_displacement_meters=analysis_metrics["centroid_displacement_meters"],
            hausdorff_distance_meters=analysis_metrics["hausdorff_distance_meters"],
            discrepancy_status=analysis_metrics["discrepancy_status"],
            discrepancy_severity=analysis_metrics["discrepancy_severity"],
            findings_summary=analysis_metrics["findings_summary"],
            detailed_metrics=analysis_metrics["detailed_metrics"],
            algorithm_version="v1.0-bihar-cadastral",
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def submit_boundary_review(
        self,
        analysis_id: uuid.UUID,
        org_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        decision: BoundaryReviewDecision,
        review_notes: str,
        dispatch_field_task: bool = False
    ) -> BoundaryDiscrepancyReview:
        """
        Records human review decision for an automated spatial analysis run.
        Optionally dispatches a LandAmin field verification task.
        """
        analysis = self.db.query(BoundaryOverlayAnalysis).filter(BoundaryOverlayAnalysis.analysis_id == analysis_id).first()
        if not analysis:
            raise EntityNotFoundError("BoundaryOverlayAnalysis", analysis_id)
        if analysis.org_id != org_id:
            raise CrossTenantAccessError("Cannot review analysis across tenant boundaries.")

        review = BoundaryDiscrepancyReview(
            review_id=uuid.uuid4(),
            org_id=org_id,
            analysis_id=analysis.analysis_id,
            reviewer_id=reviewer_id,
            decision=decision,
            review_notes=review_notes,
            field_task_dispatched=dispatch_field_task,
        )
        self.db.add(review)

        if dispatch_field_task and analysis.case_id:
            task = self._create_field_verification_for_discrepancy(analysis, reviewer_id, review_notes)
            analysis.field_task_id = task.task_id

        self.db.commit()
        self.db.refresh(review)
        return review

    def _create_field_verification_for_discrepancy(
        self,
        analysis: BoundaryOverlayAnalysis,
        creator_id: uuid.UUID,
        notes: str
    ) -> FieldVerificationTask:
        """
        Integrates boundary discrepancy directly into the LandAmin Field Verification Task subsystem.
        """
        task_num = f"FT-DISC-{uuid.uuid4().hex[:6].upper()}"
        task = FieldVerificationTask(
            task_id=uuid.uuid4(),
            org_id=analysis.org_id,
            case_id=analysis.case_id,
            parcel_id=analysis.parcel_id,
            task_number=task_num,
            title=f"Boundary Discrepancy Verification ({analysis.discrepancy_status})",
            reason=f"Automated cadastral overlay detected {analysis.findings_summary}. Reviewer notes: {notes}",
            requested_activities=[
                "VERIFY_PHYSICAL_POSSESSION_RIDGE",
                "SURVEY_GROUND_CHAUHADDI",
                "CAPTURE_BOUNDARY_GNSS_COORDINATES",
            ],
            priority=TaskPriority.HIGH if analysis.discrepancy_severity in (DiscrepancySeverity.HIGH, DiscrepancySeverity.CRITICAL) else TaskPriority.MEDIUM,
            status=TaskStatus.READY_FOR_ASSIGNMENT,
            assigned_by_user_id=creator_id,
        )
        self.db.add(task)
        return task
