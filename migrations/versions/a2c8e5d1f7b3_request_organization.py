"""Site requests record the organization they were made for.

Revision ID: a2c8e5d1f7b3
Revises: f1a7c3e9b5d2
Create Date: 2026-11-14

Adds request.organization_id, nullable. Requests made before this change
keep NULL: they are not backfilled, because a member who has since left
would be wrongly tied to an organization. New requests take the member's
organization from their membership when they are sent.
"""

import sqlalchemy as sa
from alembic import op

revision = 'a2c8e5d1f7b3'
down_revision = 'f1a7c3e9b5d2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('request', sa.Column(
        'organization_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_request_organization_id', 'request', 'organization',
        ['organization_id'], ['organization_id'])


def downgrade():
    op.drop_constraint('fk_request_organization_id', 'request',
                       type_='foreignkey')
    op.drop_column('request', 'organization_id')
