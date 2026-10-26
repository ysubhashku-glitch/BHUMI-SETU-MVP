"""add field verification tasks

Revision ID: a1b2c3d4e5f6
Revises: 56683e40f899
Create Date: 2026-10-24 22:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import app.models.base

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '56683e40f899'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'field_verification_tasks',
        sa.Column('task_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('org_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('case_id', app.models.base.GUID(length=36), nullable=False),
        sa.Column('parcel_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('finding_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('action_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('survey_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('task_number', sa.String(length=32), nullable=False),
        sa.Column('title', sa.String(length=256), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('requested_activities', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('priority', sa.String(length=16), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('assigned_amin_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('assigned_by_user_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('reviewer_user_id', app.models.base.GUID(length=36), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('decline_reason', sa.Text(), nullable=True),
        sa.Column('cancellation_reason', sa.Text(), nullable=True),
        sa.Column('visit_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('visit_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('field_observations', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('evidence_ids', app.models.base.JSONCompatible(), nullable=False),
        sa.Column('review_status', sa.String(length=32), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['action_id'], ['required_actions.action_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assigned_amin_id'], ['users.user_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assigned_by_user_id'], ['users.user_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['finding_id'], ['findings.finding_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.org_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parcel_id'], ['parcels.parcel_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewer_user_id'], ['users.user_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['survey_id'], ['field_surveys.survey_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('task_id')
    )
    op.create_index(op.f('ix_field_verification_tasks_action_id'), 'field_verification_tasks', ['action_id'], unique=False)
    op.create_index(op.f('ix_field_verification_tasks_assigned_amin_id'), 'field_verification_tasks', ['assigned_amin_id'], unique=False)
    op.create_index(op.f('ix_field_verification_tasks_case_id'), 'field_verification_tasks', ['case_id'], unique=False)
    op.create_index(op.f('ix_field_verification_tasks_finding_id'), 'field_verification_tasks', ['finding_id'], unique=False)
    op.create_index(op.f('ix_field_verification_tasks_org_id'), 'field_verification_tasks', ['org_id'], unique=False)
    op.create_index(op.f('ix_field_verification_tasks_parcel_id'), 'field_verification_tasks', ['parcel_id'], unique=False)
    op.create_index(op.f('ix_field_verification_tasks_status'), 'field_verification_tasks', ['status'], unique=False)
    op.create_index(op.f('ix_field_verification_tasks_task_number'), 'field_verification_tasks', ['task_number'], unique=True)

def downgrade() -> None:
    op.drop_index(op.f('ix_field_verification_tasks_task_number'), table_name='field_verification_tasks')
    op.drop_index(op.f('ix_field_verification_tasks_status'), table_name='field_verification_tasks')
    op.drop_index(op.f('ix_field_verification_tasks_parcel_id'), table_name='field_verification_tasks')
    op.drop_index(op.f('ix_field_verification_tasks_org_id'), table_name='field_verification_tasks')
    op.drop_index(op.f('ix_field_verification_tasks_finding_id'), table_name='field_verification_tasks')
    op.drop_index(op.f('ix_field_verification_tasks_case_id'), table_name='field_verification_tasks')
    op.drop_index(op.f('ix_field_verification_tasks_assigned_amin_id'), table_name='field_verification_tasks')
    op.drop_index(op.f('ix_field_verification_tasks_action_id'), table_name='field_verification_tasks')
    op.drop_table('field_verification_tasks')
