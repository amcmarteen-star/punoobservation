"""Site visit: its own field for the reason a site is not suitable.

Revision ID: b8d3f5a1c7e4
Revises: a4c7e1f9d2b6
Create Date: 2026-11-26

Older "Not suitable" visits kept the reason in the remarks, so it is
copied across.
"""

import sqlalchemy as sa
from alembic import op

revision = 'b8d3f5a1c7e4'
down_revision = 'a4c7e1f9d2b6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('site_visit',
                  sa.Column('unsuitable_reason', sa.Text(), nullable=True))
    op.execute("UPDATE site_visit SET unsuitable_reason = remarks "
               "WHERE finding = 'Not suitable'")


def downgrade():
    op.drop_column('site_visit', 'unsuitable_reason')
