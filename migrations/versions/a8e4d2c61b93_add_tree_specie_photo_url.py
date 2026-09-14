"""Add tree_specie photo_url

Revision ID: a8e4d2c61b93
Revises: 3f1c9a7b2d40
Create Date: 2026-09-13 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a8e4d2c61b93'
down_revision = '3f1c9a7b2d40'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tree_specie', schema=None) as batch_op:
        batch_op.add_column(sa.Column('photo_url', sa.String(length=300), nullable=True))


def downgrade():
    with op.batch_alter_table('tree_specie', schema=None) as batch_op:
        batch_op.drop_column('photo_url')
