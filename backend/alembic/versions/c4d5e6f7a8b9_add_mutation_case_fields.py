"""add mutation case and event extended fields

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-10-27 01:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import app.models.base

revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. mutation_cases extensions
    op.add_column('mutation_cases', sa.Column('jamabandi_number', sa.String(length=64), nullable=True))
    op.add_column('mutation_cases', sa.Column('filing_year', sa.Integer(), nullable=True))
    op.add_column('mutation_cases', sa.Column('deed_registered_office', sa.String(length=128), nullable=True))
    op.add_column('mutation_cases', sa.Column('source_portal', sa.String(length=64), nullable=True))
    op.add_column('mutation_cases', sa.Column('last_source_observation', sa.DateTime(timezone=True), nullable=True))
    op.add_column('mutation_cases', sa.Column('notes', sa.Text(), nullable=True))

    # 2. mutation_events extensions
    op.add_column('mutation_events', sa.Column('source_event_id', sa.String(length=128), nullable=True))
    op.add_column('mutation_events', sa.Column('ingested_timestamp', sa.DateTime(timezone=True), nullable=True))
    op.add_column('mutation_events', sa.Column('extracted_fields', app.models.base.JSONCompatible(), nullable=True))
    op.add_column('mutation_events', sa.Column('remarks', sa.Text(), nullable=True))
    op.add_column('mutation_events', sa.Column('provenance_type', sa.String(length=64), nullable=True, server_default='OFFICIAL_GOVERNMENT_PORTAL'))
    op.alter_column('mutation_events', 'org_id', existing_type=app.models.base.GUID(length=36), nullable=True)

    # 3. mutation_reconciliation_runs extensions
    op.add_column('mutation_reconciliation_runs', sa.Column('records_duplicate', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('mutation_reconciliation_runs', sa.Column('records_rejected', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('mutation_reconciliation_runs', sa.Column('records_unresolved', sa.Integer(), nullable=True, server_default='0'))


def downgrade() -> None:
    op.drop_column('mutation_reconciliation_runs', 'records_unresolved')
    op.drop_column('mutation_reconciliation_runs', 'records_rejected')
    op.drop_column('mutation_reconciliation_runs', 'records_duplicate')

    op.alter_column('mutation_events', 'org_id', existing_type=app.models.base.GUID(length=36), nullable=False)
    op.drop_column('mutation_events', 'provenance_type')
    op.drop_column('mutation_events', 'remarks')
    op.drop_column('mutation_events', 'extracted_fields')
    op.drop_column('mutation_events', 'ingested_timestamp')
    op.drop_column('mutation_events', 'source_event_id')

    op.drop_column('mutation_cases', 'notes')
    op.drop_column('mutation_cases', 'last_source_observation')
    op.drop_column('mutation_cases', 'source_portal')
    op.drop_column('mutation_cases', 'deed_registered_office')
    op.drop_column('mutation_cases', 'filing_year')
    op.drop_column('mutation_cases', 'jamabandi_number')
