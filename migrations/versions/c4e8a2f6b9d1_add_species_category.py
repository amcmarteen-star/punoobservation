"""Tag species with CENRO use categories (Timber, Agroforestry, ...)

The same table as docs/schema.md. Apply EITHER this migration
(flask db upgrade) OR the SQL there, not both: the SQL also moves
alembic_version to this revision, so the two stay in step.

Revision ID: c4e8a2f6b9d1
Revises: b7c3e9a1d5f4
Create Date: 2026-10-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4e8a2f6b9d1'
down_revision = 'b7c3e9a1d5f4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'species_category',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('species_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(['species_id'], ['tree_specie.tree_id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('species_id', 'category',
                            name='uq_species_category'),
    )
    op.create_index('ix_species_category_species_id', 'species_category',
                    ['species_id'])


def downgrade():
    op.drop_index('ix_species_category_species_id',
                  table_name='species_category')
    op.drop_table('species_category')
