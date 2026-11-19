"""add invoice retention: purged documents, plan-ended date, warning notices

Revision ID: a7c41e90b2d3
Revises: d81f4c2a6e07
Create Date: 2026-11-19

documents.purged_at             when the retention job removed the content
organizations.paid_plan_ended_at  when a paid plan last ended
retention_notices               warning emails already sent, per plan period

All new columns are nullable, so the previous code keeps working against
the new schema.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7c41e90b2d3'
down_revision: Union[str, None] = 'd81f4c2a6e07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('purged_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_documents_purged_at', 'documents', ['purged_at'])
    op.add_column('organizations', sa.Column('paid_plan_ended_at', sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        'retention_notices',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('organization_id', 'period_start', 'kind', name='uq_retention_notice'),
    )
    op.create_index('ix_retention_notices_id', 'retention_notices', ['id'])
    op.create_index('ix_retention_notices_organization_id', 'retention_notices', ['organization_id'])


def downgrade() -> None:
    op.drop_table('retention_notices')
    op.drop_column('organizations', 'paid_plan_ended_at')
    op.drop_index('ix_documents_purged_at', table_name='documents')
    op.drop_column('documents', 'purged_at')
