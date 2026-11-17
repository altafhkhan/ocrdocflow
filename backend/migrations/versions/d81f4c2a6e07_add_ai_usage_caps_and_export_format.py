"""add AI usage tracking, spending caps and export format preference

Revision ID: d81f4c2a6e07
Revises: 22b9c16345b2
Create Date: 2026-11-17

documents:      what each upload cost in AI processing (model, tokens, USD)
                and how many plan invoices it used (long invoices count
                as several - see services/ai_cost.py).
organizations:  per-customer overrides for the monthly AI spending cap and
                the plan's invoice limit (NULL = use the plan default).
users:          preferred download format (csv / xlsx).

All columns are nullable or have a default, so the previous code keeps
working against the new schema.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd81f4c2a6e07'
down_revision: Union[str, None] = '22b9c16345b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('ai_model', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('ai_input_tokens', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('ai_output_tokens', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('ai_cost_usd', sa.Numeric(12, 6), nullable=True))
    op.add_column('documents', sa.Column('billable_invoice_count', sa.Integer(), nullable=True))
    op.add_column('organizations', sa.Column('monthly_cost_cap_usd', sa.Numeric(10, 2), nullable=True))
    op.add_column('organizations', sa.Column('invoice_limit_override', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('export_format', sa.String(), nullable=False, server_default='csv'))


def downgrade() -> None:
    op.drop_column('users', 'export_format')
    op.drop_column('organizations', 'invoice_limit_override')
    op.drop_column('organizations', 'monthly_cost_cap_usd')
    op.drop_column('documents', 'billable_invoice_count')
    op.drop_column('documents', 'ai_cost_usd')
    op.drop_column('documents', 'ai_output_tokens')
    op.drop_column('documents', 'ai_input_tokens')
    op.drop_column('documents', 'ai_model')
