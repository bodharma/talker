"""add visitor tracking tables

Revision ID: 1fae8f057dd9
Revises: b6cf4ef71605
Create Date: 2026-03-11 13:04:32.169591

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '1fae8f057dd9'
down_revision: Union[str, Sequence[str], None] = 'b6cf4ef71605'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('visitors',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('first_name', sa.String(length=255), nullable=False),
    sa.Column('last_name', sa.String(length=255), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('company', sa.String(length=255), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('visit_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_visit_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('visitor_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('visitor_id', sa.Integer(), nullable=False),
    sa.Column('visiting_person', sa.String(length=255), nullable=False),
    sa.Column('visiting_company', sa.String(length=255), nullable=False),
    sa.Column('floor', sa.Integer(), nullable=False),
    sa.Column('mood_impression', sa.String(length=100), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['visitor_id'], ['visitors.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('visitor_logs')
    op.drop_table('visitors')
