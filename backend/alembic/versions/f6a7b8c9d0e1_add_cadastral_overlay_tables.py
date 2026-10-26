"""add cadastral overlay tables

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-26 21:15:00.000000

"""
from typing import Sequence, Union
from alembic import op, context
import sqlalchemy as sa
from geoalchemy2 import Geometry
import app.models.base
from app.database import CompatibleGeometry

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. cadastral_map_assets table
    op.create_table(
        'cadastral_map_assets',
        sa.Column('asset_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('org_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('case_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('parcel_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('asset_name', sa.String(length=256), nullable=False),
        sa.Column('file_format', sa.String(length=32), nullable=False, server_default='PNG'),
        sa.Column('source_type', sa.String(length=64), nullable=False, server_default='CADASTRAL_SURVEY_SHEET'),
        sa.Column('storage_path', sa.String(length=512), nullable=False),
        sa.Column('sha256_hash', sa.String(length=64), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('image_width', sa.Integer(), nullable=True),
        sa.Column('image_height', sa.Integer(), nullable=True),
        sa.Column('declared_crs', sa.String(length=32), nullable=True),
        sa.Column('is_georeferenced', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('district', sa.String(length=64), nullable=True),
        sa.Column('anchal', sa.String(length=64), nullable=True),
        sa.Column('mauza', sa.String(length=128), nullable=True),
        sa.Column('sheet_number', sa.String(length=32), nullable=True),
        sa.Column('survey_year', sa.Integer(), nullable=True),
        sa.Column('provenance_metadata', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['parcel_id'], ['parcels.parcel_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('asset_id')
    )
    op.create_index(op.f('ix_cadastral_map_assets_org_id'), 'cadastral_map_assets', ['org_id'], unique=False)
    op.create_index(op.f('ix_cadastral_map_assets_case_id'), 'cadastral_map_assets', ['case_id'], unique=False)
    op.create_index(op.f('ix_cadastral_map_assets_parcel_id'), 'cadastral_map_assets', ['parcel_id'], unique=False)
    op.create_index(op.f('ix_cadastral_map_assets_sha256_hash'), 'cadastral_map_assets', ['sha256_hash'], unique=False)

    # 2. georeference_sessions table
    op.create_table(
        'georeference_sessions',
        sa.Column('session_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('org_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('asset_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('transformation_method', sa.String(length=32), nullable=False, server_default='AFFINE'),
        sa.Column('target_crs', sa.String(length=32), nullable=False, server_default='EPSG:32645'),
        sa.Column('control_points', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('transformation_parameters', app.models.base.JSONCompatible(), nullable=True),
        sa.Column('rmse_meters', sa.Float(), nullable=True),
        sa.Column('max_residual_meters', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='DRAFT'),
        sa.Column('reviewed_by', app.models.base.GUID(length=36), nullable=True),
        sa.Column('review_comments', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['asset_id'], ['cadastral_map_assets.asset_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.user_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('session_id')
    )
    op.create_index(op.f('ix_georeference_sessions_org_id'), 'georeference_sessions', ['org_id'], unique=False)
    op.create_index(op.f('ix_georeference_sessions_asset_id'), 'georeference_sessions', ['asset_id'], unique=False)

    # 3. cadastral_parcel_geometries table
    # Check if PostgreSQL dialect for PostGIS geometry, fallback to Text for SQLite
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    geom_col = sa.Column('polygon_geometry', Geometry('POLYGON', srid=4326), nullable=False) if is_postgres else sa.Column('polygon_geometry', sa.Text(), nullable=False)

    op.create_table(
        'cadastral_parcel_geometries',
        sa.Column('geometry_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('org_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('parcel_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('case_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('asset_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('session_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('geometry_label', sa.String(length=128), nullable=False),
        sa.Column('geometry_role', sa.String(length=64), nullable=False, server_default='BASELINE_CADASTRAL'),
        sa.Column('crs', sa.String(length=32), nullable=False, server_default='EPSG:4326'),
        geom_col,
        sa.Column('calculated_area_sqm', sa.Float(), nullable=False),
        sa.Column('calculated_area_acres', sa.Float(), nullable=False),
        sa.Column('perimeter_meters', sa.Float(), nullable=False),
        sa.Column('centroid_lat', sa.Float(), nullable=False),
        sa.Column('centroid_lon', sa.Float(), nullable=False),
        sa.Column('positional_uncertainty_meters', sa.Float(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('validation_error', sa.Text(), nullable=True),
        sa.Column('digitization_method', sa.String(length=64), nullable=True),
        sa.Column('source_attribution', sa.String(length=256), nullable=True),
        sa.Column('raw_geojson', app.models.base.JSONCompatible(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parcel_id'], ['parcels.parcel_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['asset_id'], ['cadastral_map_assets.asset_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['session_id'], ['georeference_sessions.session_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('geometry_id')
    )
    op.create_index(op.f('ix_cadastral_parcel_geometries_org_id'), 'cadastral_parcel_geometries', ['org_id'], unique=False)
    op.create_index(op.f('ix_cadastral_parcel_geometries_parcel_id'), 'cadastral_parcel_geometries', ['parcel_id'], unique=False)
    op.create_index(op.f('ix_cadastral_parcel_geometries_case_id'), 'cadastral_parcel_geometries', ['case_id'], unique=False)

    # 4. boundary_overlay_analyses table
    op.create_table(
        'boundary_overlay_analyses',
        sa.Column('analysis_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('org_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('case_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('parcel_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('baseline_geometry_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('comparison_geometry_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('analysis_crs', sa.String(length=32), nullable=False, server_default='EPSG:32645'),
        sa.Column('intersection_area_sqm', sa.Float(), nullable=False),
        sa.Column('union_area_sqm', sa.Float(), nullable=False),
        sa.Column('iou_score', sa.Float(), nullable=False),
        sa.Column('symmetric_diff_area_sqm', sa.Float(), nullable=False),
        sa.Column('area_delta_percentage', sa.Float(), nullable=False),
        sa.Column('perimeter_delta_percentage', sa.Float(), nullable=False),
        sa.Column('centroid_displacement_meters', sa.Float(), nullable=False),
        sa.Column('hausdorff_distance_meters', sa.Float(), nullable=False),
        sa.Column('discrepancy_status', sa.String(length=64), nullable=False, server_default='REQUIRES_HUMAN_REVIEW'),
        sa.Column('discrepancy_severity', sa.String(length=32), nullable=False, server_default='MEDIUM'),
        sa.Column('findings_summary', sa.Text(), nullable=False),
        sa.Column('detailed_metrics', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('algorithm_version', sa.String(length=32), nullable=False, server_default='v1.0-bihar-cadastral'),
        sa.Column('field_task_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['parcel_id'], ['parcels.parcel_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['baseline_geometry_id'], ['cadastral_parcel_geometries.geometry_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['comparison_geometry_id'], ['cadastral_parcel_geometries.geometry_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['field_task_id'], ['field_verification_tasks.task_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('analysis_id')
    )
    op.create_index(op.f('ix_boundary_overlay_analyses_org_id'), 'boundary_overlay_analyses', ['org_id'], unique=False)
    op.create_index(op.f('ix_boundary_overlay_analyses_case_id'), 'boundary_overlay_analyses', ['case_id'], unique=False)
    op.create_index(op.f('ix_boundary_overlay_analyses_parcel_id'), 'boundary_overlay_analyses', ['parcel_id'], unique=False)

    # 5. boundary_discrepancy_reviews table
    op.create_table(
        'boundary_discrepancy_reviews',
        sa.Column('review_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('org_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('analysis_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('reviewer_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('decision', sa.String(length=64), nullable=False, server_default='REQUIRES_FIELD_SURVEY'),
        sa.Column('review_notes', sa.Text(), nullable=False),
        sa.Column('field_task_dispatched', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['analysis_id'], ['boundary_overlay_analyses.analysis_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.user_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('review_id')
    )
    op.create_index(op.f('ix_boundary_discrepancy_reviews_org_id'), 'boundary_discrepancy_reviews', ['org_id'], unique=False)
    op.create_index(op.f('ix_boundary_discrepancy_reviews_analysis_id'), 'boundary_discrepancy_reviews', ['analysis_id'], unique=False)


def downgrade() -> None:
    op.drop_table('boundary_discrepancy_reviews')
    op.drop_table('boundary_overlay_analyses')
    op.drop_table('cadastral_parcel_geometries')
    op.drop_table('georeference_sessions')
    op.drop_table('cadastral_map_assets')
