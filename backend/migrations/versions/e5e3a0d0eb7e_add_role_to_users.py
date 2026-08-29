"""add role to users

Revision ID: e5e3a0d0eb7e
Revises: af0d45e354c1
Create Date: 2026-08-08 14:54:24.821393

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5e3a0d0eb7e'
down_revision: Union[str, None] = 'af0d45e354c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default added by hand - existing users all correctly
    # default to the "user" role (nobody is silently made an admin).
    op.add_column(
        'users',
        sa.Column('role', sa.String(), nullable=False, server_default='user'),
    )


def downgrade() -> None:
    op.drop_column('users', 'role')