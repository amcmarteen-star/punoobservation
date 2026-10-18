"""Add a contact name and email to requests

Revision ID: a1d9e5f3c7b2
Revises: f2a6c8d4b1e3
Create Date: 2026-10-09 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1d9e5f3c7b2'
down_revision = 'f2a6c8d4b1e3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('request', schema=None) as batch_op:
        batch_op.add_column(sa.Column('contact_name', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('contact_email', sa.String(length=120), nullable=True))


def downgrade():
    with op.batch_alter_table('request', schema=None) as batch_op:
        batch_op.drop_column('contact_email')
        batch_op.drop_column('contact_name')
