"""add valuation and mvr tables

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-26 19:50:00.000000

"""
from typing import Sequence, Union
from alembic import op, context
import sqlalchemy as sa
import app.models.base

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. mvr_schedules table
    op.create_table(
        'mvr_schedules',
        sa.Column('schedule_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('org_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('schedule_code', sa.String(length=64), nullable=False),
        sa.Column('district', sa.String(length=64), nullable=False),
        sa.Column('registration_office', sa.String(length=128), nullable=False),
        sa.Column('anchal_circle', sa.String(length=128), nullable=False),
        sa.Column('mauza', sa.String(length=128), nullable=False),
        sa.Column('thana_number', sa.String(length=32), nullable=True),
        sa.Column('jurisdiction_type', sa.String(length=32), nullable=False, server_default='RURAL'),
        sa.Column('property_category', sa.String(length=64), nullable=False, server_default='AGRICULTURAL'),
        sa.Column('land_classification', sa.String(length=64), nullable=False, server_default='DHANHAR_I'),
        sa.Column('road_category', sa.String(length=64), nullable=False, server_default='RURAL_ROAD_OR_NO_ROAD'),
        sa.Column('rate_per_decimal', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('rate_per_sqft', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('rate_per_katha', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('unit_basis', sa.String(length=32), nullable=False, server_default='DECIMAL'),
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('effective_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('verification_status', sa.String(length=32), nullable=False, server_default='VERIFIED_OFFICIAL'),
        sa.Column('source_gazette_reference', sa.String(length=256), nullable=True),
        sa.Column('source_url', sa.String(length=512), nullable=True),
        sa.Column('source_provider', sa.String(length=64), nullable=False, server_default='OFFICIAL_GAZETTE'),
        sa.Column('raw_source_payload', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('schedule_id')
    )
    op.create_index(op.f('ix_mvr_schedules_schedule_code'), 'mvr_schedules', ['schedule_code'], unique=True)
    op.create_index(op.f('ix_mvr_schedules_district'), 'mvr_schedules', ['district'], unique=False)
    op.create_index(op.f('ix_mvr_schedules_anchal_circle'), 'mvr_schedules', ['anchal_circle'], unique=False)
    op.create_index(op.f('ix_mvr_schedules_mauza'), 'mvr_schedules', ['mauza'], unique=False)

    # 2. property_valuations table
    op.create_table(
        'property_valuations',
        sa.Column('valuation_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('org_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('case_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('parcel_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('schedule_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('valuation_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('total_area_decimal', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('input_area_value', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('input_area_unit', sa.String(length=32), nullable=False, server_default='DECIMAL'),
        sa.Column('unit_circle_rate', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('calculated_land_value', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('built_up_area_sqft', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('construction_rate_sqft', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('calculated_structure_value', sa.Numeric(precision=14, scale=2), nullable=False, server_default='0.0'),
        sa.Column('total_government_valuation', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('declared_transaction_consideration', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('assessment_base', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('buyer_category', sa.String(length=32), nullable=False, server_default='MALE'),
        sa.Column('stamp_duty_rate_percent', sa.Numeric(precision=5, scale=2), nullable=False, server_default='6.0'),
        sa.Column('stamp_duty_amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('registration_fee_rate_percent', sa.Numeric(precision=5, scale=2), nullable=False, server_default='2.0'),
        sa.Column('registration_fee_amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('municipal_surcharge_percent', sa.Numeric(precision=5, scale=2), nullable=False, server_default='0.0'),
        sa.Column('municipal_surcharge_amount', sa.Numeric(precision=14, scale=2), nullable=False, server_default='0.0'),
        sa.Column('total_statutory_charges', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('concession_applied', sa.String(length=128), nullable=True),
        sa.Column('discrepancy_status', sa.String(length=64), nullable=False, server_default='NO_DISCREPANCY_DETECTED'),
        sa.Column('discrepancy_amount', sa.Numeric(precision=14, scale=2), nullable=False, server_default='0.0'),
        sa.Column('discrepancy_percentage', sa.Numeric(precision=6, scale=2), nullable=False, server_default='0.0'),
        sa.Column('discrepancy_explanation', sa.Text(), nullable=False),
        sa.Column('rule_version', sa.String(length=64), nullable=False, server_default='BIHAR_STAMP_RULES_v2026.1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by_user_id', app.models.base.GUID(length=36), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['parcel_id'], ['parcels.parcel_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['schedule_id'], ['mvr_schedules.schedule_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.user_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('valuation_id')
    )
    op.create_index(op.f('ix_property_valuations_case_id'), 'property_valuations', ['case_id'], unique=False)
    op.create_index(op.f('ix_property_valuations_parcel_id'), 'property_valuations', ['parcel_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_property_valuations_parcel_id'), table_name='property_valuations')
    op.drop_index(op.f('ix_property_valuations_case_id'), table_name='property_valuations')
    op.drop_table('property_valuations')

    op.drop_index(op.f('ix_mvr_schedules_mauza'), table_name='mvr_schedules')
    op.drop_index(op.f('ix_mvr_schedules_anchal_circle'), table_name='mvr_schedules')
    op.drop_index(op.f('ix_mvr_schedules_district'), table_name='mvr_schedules')
    op.drop_index(op.f('ix_mvr_schedules_schedule_code'), table_name='mvr_schedules')
    op.drop_table('mvr_schedules')
