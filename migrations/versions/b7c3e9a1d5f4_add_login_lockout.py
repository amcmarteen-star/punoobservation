"""Count wrong passwords and lock the login after too many

Revision ID: b7c3e9a1d5f4
Revises: a1d9e5f3c7b2
Create Date: 2026-10-09 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c3e9a1d5f4'
down_revision = 'a1d9e5f3c7b2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'failed_login_count', sa.Integer(), nullable=False,
            server_default='0'))
        batch_op.add_column(sa.Column('locked_until', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('locked_until')
        batch_op.drop_column('failed_login_count')
