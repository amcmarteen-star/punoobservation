"""Add users.tour_completed_at for the first-time tour

Revision ID: b7d3f1a9c2e5
Revises: c4e8a2f6b9d1
Create Date: 2026-10-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7d3f1a9c2e5'
down_revision = 'c4e8a2f6b9d1'
branch_labels = None
depends_on = None


def upgrade():
    # Nullable, so existing accounts need no default: they read as "not
    # seen yet" and get the tour once on their next Dashboard visit.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tour_completed_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('tour_completed_at')
