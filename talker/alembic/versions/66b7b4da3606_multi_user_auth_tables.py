"""multi-user auth tables

Revision ID: 66b7b4da3606
Revises: e6b496b96c9f
Create Date: 2026-03-11 08:24:11.112270

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '66b7b4da3606'
down_revision: Union[str, Sequence[str], None] = 'e6b496b96c9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Patient links table
    op.create_table('patient_links',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('clinician_id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['clinician_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # Invites table
    op.create_table('invites',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('clinician_id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('token', sa.String(length=100), nullable=False),
    sa.Column('instruments', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('schedule', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('accepted_at', sa.DateTime(), nullable=True),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['clinician_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token')
    )
    # Add user_id to sessions
    op.add_column('sessions', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'sessions', 'users', ['user_id'], ['id'])
    # Extend users table
    op.add_column('users', sa.Column('email', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('password_hash', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('role', sa.String(length=20), server_default='patient', nullable=False))
    op.add_column('users', sa.Column('oauth_provider', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('oauth_id', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('users', sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False))
    op.create_unique_constraint(None, 'users', ['email'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(None, 'users', type_='unique')
    op.drop_column('users', 'is_active')
    op.drop_column('users', 'email_verified')
    op.drop_column('users', 'oauth_id')
    op.drop_column('users', 'oauth_provider')
    op.drop_column('users', 'role')
    op.drop_column('users', 'password_hash')
    op.drop_column('users', 'email')
    op.drop_constraint(None, 'sessions', type_='foreignkey')
    op.drop_column('sessions', 'user_id')
    op.drop_table('invites')
    op.drop_table('patient_links')
