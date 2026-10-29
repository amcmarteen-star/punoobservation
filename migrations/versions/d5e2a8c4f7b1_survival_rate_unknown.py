"""Survival rate may be unknown instead of a stored 0%

Revision ID: d5e2a8c4f7b1
Revises: b7d3f1a9c2e5
Create Date: 2026-10-29 12:00:00.000000

A survival rate is survivors divided by seedlings actually planted. A site
made from a request has no planted figure yet, so its reports had no rate
to store, and 0.0 was stored in its place. Approving such a report then
copied the 0 onto the planting record, where it read as "every seedling
died" and pulled down the dashboard and overview averages.

From now on the rate is NULL when it cannot be worked out. This migration
also turns the zeros already stored that way back into NULL. It only
touches rows whose planting record has no planted figure, so a real 0%
(seedlings planted, none survived) is left as it is.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5e2a8c4f7b1'
down_revision = 'b7d3f1a9c2e5'
branch_labels = None
depends_on = None


NO_PLANTED_FIGURE = (
    "(actual_quantity_planted IS NULL OR actual_quantity_planted = 0)"
)


def upgrade():
    with op.batch_alter_table('monitoring_report', schema=None) as batch_op:
        batch_op.alter_column('survival_rate', existing_type=sa.Float(),
                              nullable=True)

    op.execute(
        "UPDATE monitoring_report SET survival_rate = NULL "
        "WHERE survival_rate = 0 AND record_id IN ("
        "SELECT record_id FROM reforestation_record WHERE "
        + NO_PLANTED_FIGURE + ")"
    )
    op.execute(
        "UPDATE reforestation_record SET survival_rate = NULL "
        "WHERE survival_rate = 0 AND " + NO_PLANTED_FIGURE
    )


def downgrade():
    # The old column cannot hold "unknown", so unknown goes back to 0.
    op.execute("UPDATE monitoring_report SET survival_rate = 0 "
               "WHERE survival_rate IS NULL")
    with op.batch_alter_table('monitoring_report', schema=None) as batch_op:
        batch_op.alter_column('survival_rate', existing_type=sa.Float(),
                              nullable=False)
