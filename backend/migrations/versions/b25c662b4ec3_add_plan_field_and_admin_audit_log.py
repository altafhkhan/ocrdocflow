"""add plan field and admin audit log

Revision ID: b25c662b4ec3
Revises: e5e3a0d0eb7e
Create Date: 2026-08-08 19:22:35.651961

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b25c662b4ec3'
down_revision: Union[str, None] = 'e5e3a0d0eb7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('admin_audit_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('admin_user_id', sa.Integer(), nullable=False),
    sa.Column('action', sa.String(), nullable=False),
    sa.Column('target_type', sa.String(), nullable=False),
    sa.Column('target_id', sa.Integer(), nullable=False),
    sa.Column('details', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['admin_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_admin_audit_log_admin_user_id'), 'admin_audit_log', ['admin_user_id'], unique=False)
    op.create_index(op.f('ix_admin_audit_log_id'), 'admin_audit_log', ['id'], unique=False)

    # server_default added by hand - existing users all correctly
    # default to the "free" plan.
    op.add_column(
        'users',
        sa.Column('plan', sa.String(), nullable=False, server_default='free'),
    )


def downgrade() -> None:
    op.drop_column('users', 'plan')
    op.drop_index(op.f('ix_admin_audit_log_id'), table_name='admin_audit_log')
    op.drop_index(op.f('ix_admin_audit_log_admin_user_id'), table_name='admin_audit_log')
    op.drop_table('admin_audit_log')