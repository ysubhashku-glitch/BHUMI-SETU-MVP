"""add mutation intelligence tables

Revision ID: a2b3c4d5e6f7
Revises: f6a7b8c9d0e1
Create Date: 2026-10-26 21:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import app.models.base

revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. mutation_cases table
    op.create_table(
        'mutation_cases',
        sa.Column('mutation_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('org_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('parcel_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('case_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('case_number', sa.String(length=64), nullable=False),
        sa.Column('source_case_no', sa.String(length=64), nullable=True),
        sa.Column('financial_year', sa.String(length=16), nullable=False, server_default='2024-2025'),
        sa.Column('district', sa.String(length=64), nullable=False),
        sa.Column('anchal', sa.String(length=64), nullable=False),
        sa.Column('halka', sa.String(length=32), nullable=True),
        sa.Column('mauza', sa.String(length=128), nullable=False),
        sa.Column('khata_number', sa.String(length=32), nullable=False),
        sa.Column('plot_khesra_number', sa.String(length=32), nullable=False),
        sa.Column('transferred_area_acres', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('applicant_name', sa.String(length=256), nullable=False),
        sa.Column('applicant_relation', sa.String(length=64), nullable=True),
        sa.Column('buyer_parties', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('seller_parties', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('deed_number', sa.String(length=64), nullable=True),
        sa.Column('deed_date', sa.Date(), nullable=True),
        sa.Column('mutation_type', sa.String(length=64), nullable=False, server_default='SALE_DEED'),
        sa.Column('current_status', sa.String(length=32), nullable=False, server_default='RECEIVED'),
        sa.Column('raw_source_status', sa.String(length=128), nullable=False),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('rejection_code', sa.String(length=64), nullable=True),
        sa.Column('filing_date', sa.Date(), nullable=True),
        sa.Column('disposal_date', sa.Date(), nullable=True),
        sa.Column('source_authority', sa.String(length=128), nullable=False, server_default='BIHAR_BHUMI_DORLR'),
        sa.Column('verification_status', sa.String(length=32), nullable=False, server_default='UNVERIFIED'),
        sa.Column('provenance_metadata', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parcel_id'], ['parcels.parcel_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('mutation_id')
    )
    op.create_index(op.f('ix_mutation_cases_org_id'), 'mutation_cases', ['org_id'], unique=False)
    op.create_index(op.f('ix_mutation_cases_case_number'), 'mutation_cases', ['case_number'], unique=False)
    op.create_index(op.f('ix_mutation_cases_district'), 'mutation_cases', ['district'], unique=False)
    op.create_index(op.f('ix_mutation_cases_anchal'), 'mutation_cases', ['anchal'], unique=False)
    op.create_index(op.f('ix_mutation_cases_mauza'), 'mutation_cases', ['mauza'], unique=False)
    op.create_index(op.f('ix_mutation_cases_plot_khesra_number'), 'mutation_cases', ['plot_khesra_number'], unique=False)
    op.create_index(op.f('ix_mutation_cases_current_status'), 'mutation_cases', ['current_status'], unique=False)

    # 2. mutation_events table
    op.create_table(
        'mutation_events',
        sa.Column('event_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('mutation_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('org_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('event_date', sa.Date(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source_authority', sa.String(length=128), nullable=False),
        sa.Column('source_payload', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('payload_hash', sa.String(length=64), nullable=False),
        sa.Column('event_description', sa.Text(), nullable=False),
        sa.Column('action_taken_by', sa.String(length=128), nullable=True),
        sa.Column('source_document_ref', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['mutation_id'], ['mutation_cases.mutation_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('event_id')
    )
    op.create_index(op.f('ix_mutation_events_mutation_id'), 'mutation_events', ['mutation_id'], unique=False)
    op.create_index(op.f('ix_mutation_events_org_id'), 'mutation_events', ['org_id'], unique=False)
    op.create_index(op.f('ix_mutation_events_event_type'), 'mutation_events', ['event_type'], unique=False)

    # 3. mutation_documents table
    op.create_table(
        'mutation_documents',
        sa.Column('document_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('mutation_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('org_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('document_type', sa.String(length=64), nullable=False, server_default='NOTICE_FORM_IX'),
        sa.Column('original_filename', sa.String(length=256), nullable=False),
        sa.Column('storage_path', sa.String(length=512), nullable=False),
        sa.Column('sha256_hash', sa.String(length=64), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('extracted_fields', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('ocr_confidence', sa.Float(), nullable=True),
        sa.Column('review_status', sa.String(length=32), nullable=False, server_default='PENDING_REVIEW'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['mutation_id'], ['mutation_cases.mutation_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('document_id')
    )
    op.create_index(op.f('ix_mutation_documents_mutation_id'), 'mutation_documents', ['mutation_id'], unique=False)
    op.create_index(op.f('ix_mutation_documents_sha256_hash'), 'mutation_documents', ['sha256_hash'], unique=False)

    # 4. mutation_entity_resolutions table
    op.create_table(
        'mutation_entity_resolutions',
        sa.Column('resolution_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('org_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('mutation_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('parcel_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('case_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('matching_method', sa.String(length=64), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('matching_details', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('is_confirmed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('reviewed_by', app.models.base.GUID(length=36), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['mutation_id'], ['mutation_cases.mutation_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parcel_id'], ['parcels.parcel_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.user_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('resolution_id')
    )
    op.create_index(op.f('ix_mutation_entity_resolutions_org_id'), 'mutation_entity_resolutions', ['org_id'], unique=False)
    op.create_index(op.f('ix_mutation_entity_resolutions_mutation_id'), 'mutation_entity_resolutions', ['mutation_id'], unique=False)
    op.create_index(op.f('ix_mutation_entity_resolutions_parcel_id'), 'mutation_entity_resolutions', ['parcel_id'], unique=False)

    # 5. mutation_reconciliation_runs table
    op.create_table(
        'mutation_reconciliation_runs',
        sa.Column('run_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('org_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('adapter_name', sa.String(length=64), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completion_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('records_observed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('records_new', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('records_updated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('records_conflicting', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='IN_PROGRESS'),
        sa.Column('error_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('run_id')
    )
    op.create_index(op.f('ix_mutation_reconciliation_runs_org_id'), 'mutation_reconciliation_runs', ['org_id'], unique=False)


def downgrade() -> None:
    op.drop_table('mutation_reconciliation_runs')
    op.drop_table('mutation_entity_resolutions')
    op.drop_table('mutation_documents')
    op.drop_table('mutation_events')
    op.drop_table('mutation_cases')
