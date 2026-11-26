"""The first-time tour has versions. Users remember the version they saw.

Revision ID: d7f3b2c8e5a1
Revises: c4e7a1b9d2f6
Create Date: 2026-11-24

Adds users.tour_version, nullable. NULL means version 1: everyone who
finished the tour before versions existed. The current version is set in
app/utils/tour.py. A user with an older version sees only the new steps,
once. A user who has never finished the tour sees all of them.
"""

import sqlalchemy as sa
from alembic import op

revision = 'd7f3b2c8e5a1'
down_revision = 'c4e7a1b9d2f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('tour_version', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('users', 'tour_version')
