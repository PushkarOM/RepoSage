"""add refresh_token_jti to users

Revision ID: a1c9e4f2b7d3
Revises: 7732ed049ebb
Create Date: 2026-08-07 00:00:00.000000

Adds the column the fixed /refresh rotation logic keys its atomic
compare-and-swap off of (see app/api/auth.py). The old refresh_token_hash
column is left in place -- unused by the app now, but not worth a
destructive drop in the same migration as a behavior fix. Drop it in a
follow-up migration once the new column has been running cleanly.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c9e4f2b7d3'
down_revision: Union[str, Sequence[str], None] = '7732ed049ebb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('refresh_token_jti', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'refresh_token_jti')
