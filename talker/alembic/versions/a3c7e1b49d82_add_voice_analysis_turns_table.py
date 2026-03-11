"""add voice_analysis_turns table

Revision ID: a3c7e1b49d82
Revises: 1fae8f057dd9
Create Date: 2026-03-11 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a3c7e1b49d82'
down_revision: Union[str, Sequence[str], None] = '1fae8f057dd9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('voice_analysis_turns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('room_name', sa.String(length=255), nullable=False),
        sa.Column('turn_number', sa.Integer(), nullable=False),
        sa.Column('features', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('mood', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_voice_analysis_turns_room_name'), 'voice_analysis_turns', ['room_name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_voice_analysis_turns_room_name'), table_name='voice_analysis_turns')
    op.drop_table('voice_analysis_turns')
