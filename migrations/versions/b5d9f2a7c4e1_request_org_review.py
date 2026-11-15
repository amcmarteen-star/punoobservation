"""Organization review of site requests.

Revision ID: b5d9f2a7c4e1
Revises: a2c8e5d1f7b3
Create Date: 2026-11-15

Adds three nullable columns to request for the organization's decision:
org_reviewed_by, org_reviewed_at, org_review_note.

No status data is changed. The stored status 'Submitted' keeps its name
and is shown as "Pending CENRO". The new stored values 'Pending Org
Approval' and 'Returned' need no migration: no existing row has them.
"""

import sqlalchemy as sa
from alembic import op

revision = 'b5d9f2a7c4e1'
down_revision = 'a2c8e5d1f7b3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('request', sa.Column(
        'org_reviewed_by', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_request_org_reviewed_by', 'request', 'users',
        ['org_reviewed_by'], ['user_id'])
    op.add_column('request', sa.Column(
        'org_reviewed_at', sa.DateTime(), nullable=True))
    op.add_column('request', sa.Column(
        'org_review_note', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('request', 'org_review_note')
    op.drop_column('request', 'org_reviewed_at')
    op.drop_constraint('fk_request_org_reviewed_by', 'request',
                       type_='foreignkey')
    op.drop_column('request', 'org_reviewed_by')
