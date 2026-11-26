"""Mark simulated sites and organizations.

Revision ID: e2b6c9d4a7f3
Revises: d7f3b2c8e5a1
Create Date: 2026-11-26

Adds site.is_simulated and organization.is_simulated (NOT NULL, default
false). The data loaded to simulate a province-wide rollout is marked true
here, once. This is the only place the old markers are read; code uses
is_simulated from now on.

    sites:          site_code starting 'SYN', or the recorded CENRO is the
                    synthetic 'Synthetic City Project Unit ...'
    organizations:  name ending '(Synthetic)', or owning only simulated sites
"""

import sqlalchemy as sa
from alembic import op

revision = 'e2b6c9d4a7f3'
down_revision = 'd7f3b2c8e5a1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('site', sa.Column('is_simulated', sa.Boolean(),
                                    nullable=False, server_default=sa.false()))
    op.add_column('organization', sa.Column('is_simulated', sa.Boolean(),
                                            nullable=False,
                                            server_default=sa.false()))
    op.execute("""
        UPDATE site SET is_simulated = TRUE
        WHERE site_code LIKE 'SYN%'
           OR cenro LIKE 'Synthetic City Project Unit%'
    """)
    op.execute("""
        UPDATE organization SET is_simulated = TRUE
        WHERE organization_name LIKE '%(Synthetic)'
           OR (EXISTS (SELECT 1 FROM site s
                       WHERE s.organization_id = organization.organization_id)
               AND NOT EXISTS (SELECT 1 FROM site s
                               WHERE s.organization_id = organization.organization_id
                                 AND s.is_simulated = FALSE))
    """)


def downgrade():
    op.drop_column('organization', 'is_simulated')
    op.drop_column('site', 'is_simulated')
