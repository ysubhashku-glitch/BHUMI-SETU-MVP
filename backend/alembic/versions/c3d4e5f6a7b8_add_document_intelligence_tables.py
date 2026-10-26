"""add document intelligence tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-25 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op, context
import sqlalchemy as sa
import app.models.base

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. document_versions
    op.create_table(
        'document_versions',
        sa.Column('version_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('document_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('storage_reference', sa.String(length=512), nullable=False),
        sa.Column('mime_type', sa.String(length=64), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('page_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('processing_status', sa.String(length=32), nullable=False, server_default='UPLOADED'),
        sa.Column('parser_version', sa.String(length=64), nullable=True),
        sa.Column('ocr_engine', sa.String(length=64), nullable=True),
        sa.Column('ocr_engine_version', sa.String(length=64), nullable=True),
        sa.Column('extraction_pipeline_version', sa.String(length=64), nullable=True),
        sa.Column('failure_reason', sa.String(length=512), nullable=True),
        sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.document_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('version_id')
    )
    op.create_index(op.f('ix_document_versions_document_id'), 'document_versions', ['document_id'], unique=False)
    op.create_index(op.f('ix_document_versions_content_hash'), 'document_versions', ['content_hash'], unique=False)
    op.create_index(op.f('ix_document_versions_processing_status'), 'document_versions', ['processing_status'], unique=False)

    # 2. Add document_pages extensions (if columns do not exist)
    if context.is_offline_mode():
        existing_cols = set()
    else:
        conn = op.get_bind()
        try:
            insp = sa.inspect(conn)
            existing_cols = {col['name'] for col in insp.get_columns('document_pages')}
        except Exception:
            existing_cols = set()
    
    if 'version_id' not in existing_cols:
        op.add_column('document_pages', sa.Column('version_id', app.models.base.GUID(length=36), nullable=True))
    if 'ocr_confidence' not in existing_cols:
        op.add_column('document_pages', sa.Column('ocr_confidence', sa.Numeric(precision=5, scale=2), nullable=True))
    if 'width_px' not in existing_cols:
        op.add_column('document_pages', sa.Column('width_px', sa.Integer(), nullable=True))
    if 'height_px' not in existing_cols:
        op.add_column('document_pages', sa.Column('height_px', sa.Integer(), nullable=True))
    if 'rotation_deg' not in existing_cols:
        op.add_column('document_pages', sa.Column('rotation_deg', sa.Integer(), nullable=False, server_default='0'))
    if 'resolution_dpi' not in existing_cols:
        op.add_column('document_pages', sa.Column('resolution_dpi', sa.Integer(), nullable=True))
    if 'has_selectable_text' not in existing_cols:
        op.add_column('document_pages', sa.Column('has_selectable_text', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    if 'is_blank' not in existing_cols:
        op.add_column('document_pages', sa.Column('is_blank', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    if 'page_hash' not in existing_cols:
        op.add_column('document_pages', sa.Column('page_hash', sa.String(length=64), nullable=True))
    if 'page_metadata' not in existing_cols:
        op.add_column('document_pages', sa.Column('page_metadata', app.models.base.JSONCompatible(), nullable=False, server_default='{}'))

    # 3. evidence_spans
    op.create_table(
        'evidence_spans',
        sa.Column('span_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('document_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('version_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('page_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('x_min', sa.Float(), nullable=True),
        sa.Column('y_min', sa.Float(), nullable=True),
        sa.Column('x_max', sa.Float(), nullable=True),
        sa.Column('y_max', sa.Float(), nullable=True),
        sa.Column('char_start', sa.Integer(), nullable=True),
        sa.Column('char_end', sa.Integer(), nullable=True),
        sa.Column('extracted_text', sa.Text(), nullable=False),
        sa.Column('source_type', sa.String(length=64), nullable=False, server_default='OCR'),
        sa.Column('extraction_method', sa.String(length=64), nullable=False, server_default='OCR_LAYOUT'),
        sa.Column('confidence', sa.Numeric(precision=5, scale=2), nullable=False, server_default='1.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.document_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['version_id'], ['document_versions.version_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['page_id'], ['document_pages.page_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('span_id')
    )
    op.create_index(op.f('ix_evidence_spans_document_id'), 'evidence_spans', ['document_id'], unique=False)
    op.create_index(op.f('ix_evidence_spans_version_id'), 'evidence_spans', ['version_id'], unique=False)
    op.create_index(op.f('ix_evidence_spans_page_id'), 'evidence_spans', ['page_id'], unique=False)

    # 4. extracted_fields
    op.create_table(
        'extracted_fields',
        sa.Column('field_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('document_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('version_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('page_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('evidence_span_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('field_name', sa.String(length=128), nullable=False),
        sa.Column('raw_value', sa.Text(), nullable=True),
        sa.Column('normalized_value', app.models.base.JSONCompatible(), nullable=True),
        sa.Column('unit', sa.String(length=32), nullable=True),
        sa.Column('data_type', sa.String(length=32), nullable=False, server_default='STRING'),
        sa.Column('extraction_method', sa.String(length=64), nullable=False, server_default='TEMPLATE_RULE'),
        sa.Column('extraction_model', sa.String(length=64), nullable=True),
        sa.Column('confidence', sa.Numeric(precision=5, scale=2), nullable=False, server_default='1.0'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='CANDIDATE'),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_by_user_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.document_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['version_id'], ['document_versions.version_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['page_id'], ['document_pages.page_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['evidence_span_id'], ['evidence_spans.span_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.user_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('field_id')
    )
    op.create_index(op.f('ix_extracted_fields_document_id'), 'extracted_fields', ['document_id'], unique=False)
    op.create_index(op.f('ix_extracted_fields_version_id'), 'extracted_fields', ['version_id'], unique=False)
    op.create_index(op.f('ix_extracted_fields_field_name'), 'extracted_fields', ['field_name'], unique=False)
    op.create_index(op.f('ix_extracted_fields_status'), 'extracted_fields', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_extracted_fields_status'), table_name='extracted_fields')
    op.drop_index(op.f('ix_extracted_fields_field_name'), table_name='extracted_fields')
    op.drop_index(op.f('ix_extracted_fields_version_id'), table_name='extracted_fields')
    op.drop_index(op.f('ix_extracted_fields_document_id'), table_name='extracted_fields')
    op.drop_table('extracted_fields')

    op.drop_index(op.f('ix_evidence_spans_page_id'), table_name='evidence_spans')
    op.drop_index(op.f('ix_evidence_spans_version_id'), table_name='evidence_spans')
    op.drop_index(op.f('ix_evidence_spans_document_id'), table_name='evidence_spans')
    op.drop_table('evidence_spans')

    op.drop_index(op.f('ix_document_versions_processing_status'), table_name='document_versions')
    op.drop_index(op.f('ix_document_versions_content_hash'), table_name='document_versions')
    op.drop_index(op.f('ix_document_versions_document_id'), table_name='document_versions')
    op.drop_table('document_versions')
