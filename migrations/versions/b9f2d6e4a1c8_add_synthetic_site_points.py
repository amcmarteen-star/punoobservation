"""Add synthetic site points for the GIS map heat layer

Revision ID: b9f2d6e4a1c8
Revises: a4c9e7d2f1b6
Create Date: 2026-11-07 12:00:00.000000

New table synthetic_site_point (see SyntheticSitePoint in app/models.py).
Made-up plot locations, filled by scripts/tools/make_synthetic_points.py.
No existing table is changed.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b9f2d6e4a1c8'
down_revision = 'a4c9e7d2f1b6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'synthetic_site_point',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('weight', sa.Float(), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('is_synthetic', sa.Boolean(), server_default=sa.true(),
                  nullable=False),
        sa.Column('seed', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['site_id'], ['site.site_id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('synthetic_site_point', schema=None) as batch_op:
        batch_op.create_index('ix_synthetic_site_point_site_id', ['site_id'])


def downgrade():
    with op.batch_alter_table('synthetic_site_point', schema=None) as batch_op:
        batch_op.drop_index('ix_synthetic_site_point_site_id')
    op.drop_table('synthetic_site_point')
