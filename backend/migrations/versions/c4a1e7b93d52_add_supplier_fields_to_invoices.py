"""add supplier fields to invoices

Revision ID: c4a1e7b93d52
Revises: 22b9c16345b2
Create Date: 2026-11-17

An invoice has two parties. Until now only the client_* columns existed,
so the issuing company had nowhere to go. Adds supplier_name and
supplier_email to the staging table and to the saved invoices.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4a1e7b93d52'
down_revision: Union[str, None] = '22b9c16345b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ('extracted_invoice_header', 'invoices')


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column('supplier_name', sa.String(), nullable=True))
        op.add_column(table, sa.Column('supplier_email', sa.String(), nullable=True))


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, 'supplier_email')
        op.drop_column(table, 'supplier_name')
