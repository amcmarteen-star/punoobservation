"""Link a site to the request it was created from

Revision ID: e7b3d5c2a9f1
Revises: c9e2f4a7b1d6
Create Date: 2026-09-13 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7b3d5c2a9f1'
down_revision = 'c9e2f4a7b1d6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('site', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source_request_id', sa.Integer(), nullable=True))
        batch_op.create_unique_constraint(
            'uq_site_source_request_id', ['source_request_id'])
        batch_op.create_foreign_key(
            'fk_site_source_request_id_request', 'request',
            ['source_request_id'], ['request_id'])


def downgrade():
    with op.batch_alter_table('site', schema=None) as batch_op:
        batch_op.drop_constraint('fk_site_source_request_id_request', type_='foreignkey')
        batch_op.drop_constraint('uq_site_source_request_id', type_='unique')
        batch_op.drop_column('source_request_id')
