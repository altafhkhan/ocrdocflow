"""support multiple invoices per document

Revision ID: af0d45e354c1
Revises: 031bb2df58bd
Create Date: 2026-08-02 14:05:15.511381

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af0d45e354c1'
down_revision: Union[str, None] = '031bb2df58bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOTE: server_default='0' added by hand (Alembic's autogenerate
    # didn't include one). Without it, this fails on any table that
    # already has rows - existing invoices are correctly treated as
    # "invoice_index 0" (the first/only invoice in their file).
    op.add_column(
        'extracted_invoice_header',
        sa.Column('invoice_index', sa.Integer(), nullable=False, server_default='0'),
    )
    op.drop_index('ix_extracted_invoice_header_document_id', table_name='extracted_invoice_header')
    op.create_index(op.f('ix_extracted_invoice_header_document_id'), 'extracted_invoice_header', ['document_id'], unique=False)
    op.create_unique_constraint('uq_extracted_header_doc_index', 'extracted_invoice_header', ['document_id', 'invoice_index'])

    op.add_column(
        'extracted_invoice_items',
        sa.Column('invoice_index', sa.Integer(), nullable=False, server_default='0'),
    )

    op.add_column(
        'invoices',
        sa.Column('invoice_index', sa.Integer(), nullable=False, server_default='0'),
    )
    op.drop_index('ix_invoices_document_id', table_name='invoices')
    op.create_index(op.f('ix_invoices_document_id'), 'invoices', ['document_id'], unique=False)
    op.create_unique_constraint('uq_invoice_doc_index', 'invoices', ['document_id', 'invoice_index'])


def downgrade() -> None:
    op.drop_constraint('uq_invoice_doc_index', 'invoices', type_='unique')
    op.drop_index(op.f('ix_invoices_document_id'), table_name='invoices')
    op.create_index('ix_invoices_document_id', 'invoices', ['document_id'], unique=True)
    op.drop_column('invoices', 'invoice_index')

    op.drop_column('extracted_invoice_items', 'invoice_index')

    op.drop_constraint('uq_extracted_header_doc_index', 'extracted_invoice_header', type_='unique')
    op.drop_index(op.f('ix_extracted_invoice_header_document_id'), table_name='extracted_invoice_header')
    op.create_index('ix_extracted_invoice_header_document_id', 'extracted_invoice_header', ['document_id'], unique=True)
    op.drop_column('extracted_invoice_header', 'invoice_index')