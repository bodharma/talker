"""add admin_notes to sessions

Revision ID: e6b496b96c9f
Revises: 9436dc433733
Create Date: 2026-03-11 07:39:32.821939

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e6b496b96c9f'
down_revision: Union[str, Sequence[str], None] = '9436dc433733'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('sessions', sa.Column('admin_notes', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('sessions', 'admin_notes')
