"""add passport synthesis and explainable risk intelligence tables

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-10-26 21:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import app.models.base

revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. passport_assessments
    op.create_table(
        'passport_assessments',
        sa.Column('assessment_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('org_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('parcel_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('case_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('assessment_number', sa.String(length=64), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='COMPLETED'),
        sa.Column('overall_risk_tier', sa.String(length=32), nullable=False, server_default='MEDIUM'),
        sa.Column('composite_priority_score', sa.Numeric(precision=5, scale=2), nullable=False, server_default='50.00'),
        sa.Column('scoring_formula_version', sa.String(length=32), nullable=False, server_default='v1.0-deterministic-weighted'),
        sa.Column('dimension_scores', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('reconciliation_summary', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('facts_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('inferences_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('findings_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('evidence_gaps_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('previous_assessment_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('sha256_snapshot_hash', sa.String(length=64), nullable=False),
        sa.Column('statutory_disclaimer', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parcel_id'], ['parcels.parcel_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['previous_assessment_id'], ['passport_assessments.assessment_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('assessment_id')
    )
    op.create_index(op.f('ix_passport_assessments_org_id'), 'passport_assessments', ['org_id'], unique=False)
    op.create_index(op.f('ix_passport_assessments_parcel_id'), 'passport_assessments', ['parcel_id'], unique=False)
    op.create_index(op.f('ix_passport_assessments_case_id'), 'passport_assessments', ['case_id'], unique=False)
    op.create_index(op.f('ix_passport_assessments_assessment_number'), 'passport_assessments', ['assessment_number'], unique=True)

    # 2. assessment_facts
    op.create_table(
        'assessment_facts',
        sa.Column('fact_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('assessment_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('subsystem', sa.String(length=32), nullable=False),
        sa.Column('fact_category', sa.String(length=64), nullable=False),
        sa.Column('source_reference', sa.String(length=256), nullable=False),
        sa.Column('source_retrieval_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('applicable_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('raw_value', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('normalized_value', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('verification_status', sa.String(length=32), nullable=False, server_default='UNVERIFIED'),
        sa.Column('limitations', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['passport_assessments.assessment_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('fact_id')
    )
    op.create_index(op.f('ix_assessment_facts_assessment_id'), 'assessment_facts', ['assessment_id'], unique=False)

    # 3. assessment_inferences
    op.create_table(
        'assessment_inferences',
        sa.Column('inference_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('assessment_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('rule_id', sa.String(length=64), nullable=False),
        sa.Column('rule_version', sa.String(length=32), nullable=False, server_default='v1.0'),
        sa.Column('input_evidence_ids', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('inference_category', sa.String(length=64), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('assumptions', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Numeric(precision=4, scale=2), nullable=False, server_default='0.50'),
        sa.Column('uncertainty_representation', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('review_status', sa.String(length=32), nullable=False, server_default='AUTOMATED_VALIDATED'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['passport_assessments.assessment_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('inference_id')
    )
    op.create_index(op.f('ix_assessment_inferences_assessment_id'), 'assessment_inferences', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_assessment_inferences_rule_id'), 'assessment_inferences', ['rule_id'], unique=False)

    # 4. assessment_findings
    op.create_table(
        'assessment_findings',
        sa.Column('finding_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('assessment_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('dimension', sa.String(length=32), nullable=False),
        sa.Column('finding_code', sa.String(length=64), nullable=False),
        sa.Column('severity', sa.String(length=16), nullable=False, server_default='INFO'),
        sa.Column('title', sa.String(length=256), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('supporting_evidence', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('recommended_action', sa.Text(), nullable=True),
        sa.Column('requires_human_review', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('review_status', sa.String(length=32), nullable=False, server_default='UNREVIEWED'),
        sa.Column('reviewed_by_user_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['passport_assessments.assessment_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.user_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('finding_id')
    )
    op.create_index(op.f('ix_assessment_findings_assessment_id'), 'assessment_findings', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_assessment_findings_dimension'), 'assessment_findings', ['dimension'], unique=False)
    op.create_index(op.f('ix_assessment_findings_finding_code'), 'assessment_findings', ['finding_code'], unique=False)

    # 5. assessment_evidence_gaps
    op.create_table(
        'assessment_evidence_gaps',
        sa.Column('gap_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('assessment_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('subsystem', sa.String(length=32), nullable=False),
        sa.Column('gap_code', sa.String(length=64), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('impact_on_assessment', sa.Text(), nullable=False),
        sa.Column('remedy_action', sa.Text(), nullable=True),
        sa.Column('is_blocking', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['passport_assessments.assessment_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('gap_id')
    )
    op.create_index(op.f('ix_assessment_evidence_gaps_assessment_id'), 'assessment_evidence_gaps', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_assessment_evidence_gaps_gap_code'), 'assessment_evidence_gaps', ['gap_code'], unique=False)

    # 6. assessment_review_actions
    op.create_table(
        'assessment_review_actions',
        sa.Column('action_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('assessment_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('finding_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('user_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('action_type', sa.String(length=64), nullable=False),
        sa.Column('previous_state', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('new_state', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('justification', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['passport_assessments.assessment_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['finding_id'], ['assessment_findings.finding_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('action_id')
    )
    op.create_index(op.f('ix_assessment_review_actions_assessment_id'), 'assessment_review_actions', ['assessment_id'], unique=False)


def downgrade() -> None:
    op.drop_table('assessment_review_actions')
    op.drop_table('assessment_evidence_gaps')
    op.drop_table('assessment_findings')
    op.drop_table('assessment_inferences')
    op.drop_table('assessment_facts')
    op.drop_table('passport_assessments')
