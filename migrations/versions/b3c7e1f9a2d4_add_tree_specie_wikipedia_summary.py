"""Add tree_specie Wikipedia summary

Revision ID: b3c7e1f9a2d4
Revises: a8e4d2c61b93
Create Date: 2026-09-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3c7e1f9a2d4'
down_revision = 'a8e4d2c61b93'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tree_specie', schema=None) as batch_op:
        batch_op.add_column(sa.Column('wiki_title', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('wiki_extract', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('wiki_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('wiki_fetched_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('tree_specie', schema=None) as batch_op:
        batch_op.drop_column('wiki_fetched_at')
        batch_op.drop_column('wiki_url')
        batch_op.drop_column('wiki_extract')
        batch_op.drop_column('wiki_title')
