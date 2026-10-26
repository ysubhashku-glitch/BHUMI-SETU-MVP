"""add land intelligence reports

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-24 22:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import app.models.base

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'land_intelligence_reports',
        sa.Column('report_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('org_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('case_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('parcel_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('report_number', sa.String(length=32), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('verification_token', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('sha256_hash', sa.String(length=64), nullable=False),
        sa.Column('pdf_storage_uri', sa.String(length=512), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('page_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('source_snapshots', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('summary_counts', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('generated_by_user_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('superseded_by_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['generated_by_user_id'], ['users.user_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parcel_id'], ['parcels.parcel_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['superseded_by_id'], ['land_intelligence_reports.report_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('report_id')
    )
    op.create_index(op.f('ix_land_intelligence_reports_case_id'), 'land_intelligence_reports', ['case_id'], unique=False)
    op.create_index(op.f('ix_land_intelligence_reports_org_id'), 'land_intelligence_reports', ['org_id'], unique=False)
    op.create_index(op.f('ix_land_intelligence_reports_parcel_id'), 'land_intelligence_reports', ['parcel_id'], unique=False)
    op.create_index(op.f('ix_land_intelligence_reports_report_number'), 'land_intelligence_reports', ['report_number'], unique=True)
    op.create_index(op.f('ix_land_intelligence_reports_sha256_hash'), 'land_intelligence_reports', ['sha256_hash'], unique=False)
    op.create_index(op.f('ix_land_intelligence_reports_status'), 'land_intelligence_reports', ['status'], unique=False)
    op.create_index(op.f('ix_land_intelligence_reports_verification_token'), 'land_intelligence_reports', ['verification_token'], unique=True)

def downgrade() -> None:
    op.drop_index(op.f('ix_land_intelligence_reports_verification_token'), table_name='land_intelligence_reports')
    op.drop_index(op.f('ix_land_intelligence_reports_status'), table_name='land_intelligence_reports')
    op.drop_index(op.f('ix_land_intelligence_reports_sha256_hash'), table_name='land_intelligence_reports')
    op.drop_index(op.f('ix_land_intelligence_reports_report_number'), table_name='land_intelligence_reports')
    op.drop_index(op.f('ix_land_intelligence_reports_parcel_id'), table_name='land_intelligence_reports')
    op.drop_index(op.f('ix_land_intelligence_reports_org_id'), table_name='land_intelligence_reports')
    op.drop_index(op.f('ix_land_intelligence_reports_case_id'), table_name='land_intelligence_reports')
    op.drop_table('land_intelligence_reports')
