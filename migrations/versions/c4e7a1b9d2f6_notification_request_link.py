"""Notifications can point at a site request.

Revision ID: c4e7a1b9d2f6
Revises: b5d9f2a7c4e1
Create Date: 2026-11-16

Adds notification.request_id, nullable. Notices made before this column
keep NULL and link as they did before. New request notices carry the
request, so they open the request's page.
"""

import sqlalchemy as sa
from alembic import op

revision = 'c4e7a1b9d2f6'
down_revision = 'b5d9f2a7c4e1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('notification', sa.Column(
        'request_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_notification_request_id', 'notification', 'request',
        ['request_id'], ['request_id'])


def downgrade():
    op.drop_constraint('fk_notification_request_id', 'notification',
                       type_='foreignkey')
    op.drop_column('notification', 'request_id')
