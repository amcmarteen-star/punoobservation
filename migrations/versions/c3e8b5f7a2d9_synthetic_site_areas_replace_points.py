"""Replace synthetic site points with synthetic site areas

Revision ID: c3e8b5f7a2d9
Revises: b9f2d6e4a1c8
Create Date: 2026-11-07 15:00:00.000000

The map now draws one made-up square per site instead of a cloud of
made-up points. synthetic_site_point held only generated data, so it is
dropped; scripts/tools/make_synthetic_areas.py fills the new
synthetic_site_area (see SyntheticSiteArea in app/models.py). No table
holding real records is changed.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3e8b5f7a2d9'
down_revision = 'b9f2d6e4a1c8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'synthetic_site_area',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('geometry_geojson', sa.Text(), nullable=False),
        sa.Column('area_ha', sa.Float(), nullable=False),
        sa.Column('placement_note', sa.String(length=300), nullable=True),
        sa.Column('is_synthetic', sa.Boolean(), server_default=sa.true(),
                  nullable=False),
        sa.Column('seed', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['site_id'], ['site.site_id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('site_id', name='uq_synthetic_site_area_site'),
    )

    with op.batch_alter_table('synthetic_site_point', schema=None) as batch_op:
        batch_op.drop_index('ix_synthetic_site_point_site_id')
    op.drop_table('synthetic_site_point')


def downgrade():
    # The points were generated; rerun the old script to refill them.
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

    op.drop_table('synthetic_site_area')
