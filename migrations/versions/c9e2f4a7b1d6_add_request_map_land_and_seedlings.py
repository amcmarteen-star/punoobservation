"""Add request map pin, drawn area, land details and seedling estimate

Revision ID: c9e2f4a7b1d6
Revises: b3c7e1f9a2d4
Create Date: 2026-09-13 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9e2f4a7b1d6'
down_revision = 'b3c7e1f9a2d4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('request', schema=None) as batch_op:
        batch_op.add_column(sa.Column('latitude', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('longitude', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('boundary_geojson', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('boundary_area_ha', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('land_ownership', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('land_cover', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('planting_density_per_ha', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('estimated_seedlings', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('request', schema=None) as batch_op:
        batch_op.drop_column('estimated_seedlings')
        batch_op.drop_column('planting_density_per_ha')
        batch_op.drop_column('land_cover')
        batch_op.drop_column('land_ownership')
        batch_op.drop_column('boundary_area_ha')
        batch_op.drop_column('boundary_geojson')
        batch_op.drop_column('longitude')
        batch_op.drop_column('latitude')
