"""add scheduled assessments

Revision ID: b6cf4ef71605
Revises: 66b7b4da3606
Create Date: 2026-03-11 08:34:17.779271

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b6cf4ef71605'
down_revision: Union[str, Sequence[str], None] = '66b7b4da3606'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('scheduled_assessments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('clinician_id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=False),
    sa.Column('instruments', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('recurrence', sa.String(length=20), nullable=False),
    sa.Column('next_due', sa.DateTime(), nullable=False),
    sa.Column('last_completed', sa.DateTime(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['clinician_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('scheduled_assessments')
