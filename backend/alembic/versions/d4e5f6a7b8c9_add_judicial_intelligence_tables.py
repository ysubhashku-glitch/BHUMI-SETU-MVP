"""add judicial intelligence tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-26 18:30:00.000000

"""
from typing import Sequence, Union
from alembic import op, context
import sqlalchemy as sa
import app.models.base

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. judicial_cases table
    op.create_table(
        'judicial_cases',
        sa.Column('case_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('org_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('cnr_number', sa.String(length=32), nullable=False),
        sa.Column('court_name', sa.String(length=128), nullable=False),
        sa.Column('court_type', sa.String(length=32), nullable=False, server_default='DISTRICT_COURT'),
        sa.Column('district', sa.String(length=64), nullable=False),
        sa.Column('state', sa.String(length=32), nullable=False, server_default='Bihar'),
        sa.Column('case_type', sa.String(length=64), nullable=False),
        sa.Column('case_number', sa.String(length=64), nullable=False),
        sa.Column('filing_year', sa.Integer(), nullable=False),
        sa.Column('filing_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('registration_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('case_status', sa.String(length=32), nullable=False, server_default='PENDING'),
        sa.Column('stage_of_case', sa.String(length=128), nullable=True),
        sa.Column('petitioner_names', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('respondent_names', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('advocate_petitioner', sa.String(length=128), nullable=True),
        sa.Column('advocate_respondent', sa.String(length=128), nullable=True),
        sa.Column('acts_sections', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('property_schedule_raw', sa.Text(), nullable=True),
        sa.Column('extracted_land_identifiers', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('orders_summary', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('has_active_injunction', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('risk_category', sa.String(length=64), nullable=False, server_default='OTHER'),
        sa.Column('source_url', sa.String(length=512), nullable=True),
        sa.Column('source_provider', sa.String(length=64), nullable=False, server_default='MANUAL_IMPORT'),
        sa.Column('retrieval_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('evidence_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('raw_source_payload', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['evidence_id'], ['evidence.evidence_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('case_id')
    )
    op.create_index(op.f('ix_judicial_cases_cnr_number'), 'judicial_cases', ['cnr_number'], unique=True)
    op.create_index(op.f('ix_judicial_cases_district'), 'judicial_cases', ['district'], unique=False)
    op.create_index(op.f('ix_judicial_cases_case_type'), 'judicial_cases', ['case_type'], unique=False)
    op.create_index(op.f('ix_judicial_cases_case_status'), 'judicial_cases', ['case_status'], unique=False)
    op.create_index(op.f('ix_judicial_cases_org_id'), 'judicial_cases', ['org_id'], unique=False)

    # 2. parcel_judicial_matches table
    op.create_table(
        'parcel_judicial_matches',
        sa.Column('match_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('org_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('case_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('parcel_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('judicial_case_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('match_category', sa.String(length=64), nullable=False, server_default='WEAK_CANDIDATE_REVIEW_REQUIRED'),
        sa.Column('confidence_score', sa.Numeric(precision=5, scale=2), nullable=False, server_default='0.50'),
        sa.Column('matched_fields', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('matching_method', sa.String(length=64), nullable=False, server_default='DETERMINISTIC_ENTITY_RESOLUTION_v1.0'),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('review_status', sa.String(length=32), nullable=False, server_default='PENDING_REVIEW'),
        sa.Column('reviewed_by_user_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parcel_id'], ['parcels.parcel_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['judicial_case_id'], ['judicial_cases.case_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.user_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('match_id')
    )
    op.create_index(op.f('ix_parcel_judicial_matches_case_id'), 'parcel_judicial_matches', ['case_id'], unique=False)
    op.create_index(op.f('ix_parcel_judicial_matches_parcel_id'), 'parcel_judicial_matches', ['parcel_id'], unique=False)
    op.create_index(op.f('ix_parcel_judicial_matches_judicial_case_id'), 'parcel_judicial_matches', ['judicial_case_id'], unique=False)
    op.create_index(op.f('ix_parcel_judicial_matches_match_category'), 'parcel_judicial_matches', ['match_category'], unique=False)
    op.create_index(op.f('ix_parcel_judicial_matches_review_status'), 'parcel_judicial_matches', ['review_status'], unique=False)
    op.create_index(op.f('ix_parcel_judicial_matches_org_id'), 'parcel_judicial_matches', ['org_id'], unique=False)


def downgrade() -> None:
    op.drop_table('parcel_judicial_matches')
    op.drop_table('judicial_cases')
