"""Add users.location_id for the sign-up barangay

Revision ID: e4a9c1d7b2f8
Revises: c3e8b5f7a2d9
Create Date: 2026-11-12 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e4a9c1d7b2f8'
down_revision = 'c3e8b5f7a2d9'
branch_labels = None
depends_on = None


def upgrade():
    # Nullable, so existing accounts need no value. They simply get no
    # default barangay on the recommendation page.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('location_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_users_location_id', 'location', ['location_id'], ['location_id']
        )


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('fk_users_location_id', type_='foreignkey')
        batch_op.drop_column('location_id')
