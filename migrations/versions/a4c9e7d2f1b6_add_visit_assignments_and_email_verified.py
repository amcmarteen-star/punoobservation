"""Add visit assignments and email verification

Revision ID: a4c9e7d2f1b6
Revises: e8c1f4a6b3d9
Create Date: 2026-11-03 12:00:00.000000

New table visit_assignment (see VisitAssignment in app/models.py), a link
from a notification to a site, and users.email_verified. Existing accounts
count as verified, so nobody already using the system is locked out.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4c9e7d2f1b6'
down_revision = 'e8c1f4a6b3d9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'visit_assignment',
        sa.Column('assignment_id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('officer_id', sa.Integer(), nullable=False),
        sa.Column('assigned_by', sa.Integer(), nullable=False),
        sa.Column('visit_type', sa.String(length=40), nullable=False),
        sa.Column('target_date', sa.Date(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('visit_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['site_id'], ['site.site_id']),
        sa.ForeignKeyConstraint(['officer_id'], ['users.user_id']),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.user_id']),
        sa.ForeignKeyConstraint(['visit_id'], ['site_visit.visit_id']),
        sa.PrimaryKeyConstraint('assignment_id'),
    )
    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.add_column(sa.Column('site_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_notification_site', 'site',
                                    ['site_id'], ['site_id'])
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_verified', sa.Boolean(),
                                      server_default=sa.true(), nullable=False))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('email_verified')
    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.drop_constraint('fk_notification_site', type_='foreignkey')
        batch_op.drop_column('site_id')
    op.drop_table('visit_assignment')
