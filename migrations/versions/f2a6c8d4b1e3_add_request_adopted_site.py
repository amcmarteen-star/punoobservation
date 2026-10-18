"""Link an Adoption request to the existing site it adopts

Also renames the request type "Site Rehabilitation" to "Adoption".

Revision ID: f2a6c8d4b1e3
Revises: d8f3a1c5e2b7
Create Date: 2026-10-09 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2a6c8d4b1e3'
down_revision = 'd8f3a1c5e2b7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('request', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adopted_site_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_request_adopted_site_id_site', 'site',
            ['adopted_site_id'], ['site_id'])

    op.execute(
        "UPDATE request SET request_type = 'Adoption' "
        "WHERE request_type = 'Site Rehabilitation'"
    )


def downgrade():
    op.execute(
        "UPDATE request SET request_type = 'Site Rehabilitation' "
        "WHERE request_type = 'Adoption'"
    )

    with op.batch_alter_table('request', schema=None) as batch_op:
        batch_op.drop_constraint('fk_request_adopted_site_id_site', type_='foreignkey')
        batch_op.drop_column('adopted_site_id')
