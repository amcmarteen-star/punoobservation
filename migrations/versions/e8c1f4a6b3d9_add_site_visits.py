"""Add site visits for sites made from a request

Revision ID: e8c1f4a6b3d9
Revises: d5e2a8c4f7b1
Create Date: 2026-10-29 15:00:00.000000

New tables site_visit and site_visit_photo (see SiteVisit in
app/models.py), plus two pointers: which visit a published site boundary
came from, and which visit a notification is about.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8c1f4a6b3d9'
down_revision = 'd5e2a8c4f7b1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'site_visit',
        sa.Column('visit_id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('visit_date', sa.Date(), nullable=False),
        sa.Column('visit_type', sa.String(length=40), nullable=False),
        sa.Column('land_matches', sa.Boolean(), nullable=True),
        sa.Column('ownership_confirmed', sa.Boolean(), nullable=True),
        sa.Column('accessible', sa.Boolean(), nullable=True),
        sa.Column('finding', sa.String(length=20), nullable=False),
        sa.Column('seedlings_planted', sa.Integer(), nullable=True),
        sa.Column('date_planted', sa.Date(), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('boundary_geojson', sa.Text(), nullable=True),
        sa.Column('captured_area_ha', sa.Float(), nullable=True),
        sa.Column('area_difference_pct', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('review_note', sa.Text(), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('date_reviewed', sa.DateTime(), nullable=True),
        sa.Column('suggested_location_id', sa.Integer(), nullable=True),
        sa.Column('suggestion_note', sa.Text(), nullable=True),
        sa.Column('publication_status', sa.String(length=30), nullable=False,
                  server_default='Not Applicable'),
        sa.Column('published_by', sa.Integer(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('publication_note', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['site_id'], ['site.site_id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.user_id']),
        sa.ForeignKeyConstraint(['published_by'], ['users.user_id']),
        sa.ForeignKeyConstraint(['suggested_location_id'], ['location.location_id']),
        sa.PrimaryKeyConstraint('visit_id'),
    )
    op.create_table(
        'site_visit_photo',
        sa.Column('photo_id', sa.Integer(), nullable=False),
        sa.Column('visit_id', sa.Integer(), nullable=False),
        sa.Column('photo_url', sa.String(length=255), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=True),
        sa.Column('photo_type', sa.String(length=20), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('date_time_taken', sa.DateTime(), nullable=True),
        sa.Column('upload_time', sa.DateTime(), nullable=False),
        sa.Column('inside_boundary', sa.Boolean(), nullable=False),
        sa.Column('distance_from_centroid_m', sa.Float(), nullable=True),
        sa.Column('flags', sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(['visit_id'], ['site_visit.visit_id']),
        sa.PrimaryKeyConstraint('photo_id'),
    )
    with op.batch_alter_table('site', schema=None) as batch_op:
        batch_op.add_column(sa.Column('boundary_source_visit_id', sa.Integer(), nullable=True))
    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.add_column(sa.Column('visit_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_notification_visit', 'site_visit',
                                    ['visit_id'], ['visit_id'])


def downgrade():
    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.drop_constraint('fk_notification_visit', type_='foreignkey')
        batch_op.drop_column('visit_id')
    with op.batch_alter_table('site', schema=None) as batch_op:
        batch_op.drop_column('boundary_source_visit_id')
    op.drop_table('site_visit_photo')
    op.drop_table('site_visit')
