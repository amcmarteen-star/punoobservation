"""Optional full name and contact number on users.

Revision ID: a4c7e1f9d2b6
Revises: e2b6c9d4a7f3
Create Date: 2026-11-26

Both nullable: existing accounts have neither, and both stay optional.
"""

import sqlalchemy as sa
from alembic import op

revision = 'a4c7e1f9d2b6'
down_revision = 'e2b6c9d4a7f3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('full_name', sa.String(120), nullable=True))
    op.add_column('users', sa.Column('contact_number', sa.String(11), nullable=True))


def downgrade():
    op.drop_column('users', 'contact_number')
    op.drop_column('users', 'full_name')
