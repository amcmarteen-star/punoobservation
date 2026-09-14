"""Store imported survival rates as percentages

Revision ID: 3f1c9a7b2d40
Revises: ed6ab626fac9
Create Date: 2026-09-13 10:00:00.000000

Data only; no schema change.

The DENR dataset import saved "SURVIVAL RATE ON THE 3RD YEAR" as the
fraction Excel keeps behind a percentage cell (86% -> 0.86). Approved
monitoring reports write the same column as a percentage (86.0). The
dashboard averages both and compares them with the 85% threshold, so
every imported value drew as a near-zero red bar, and a municipality
with both kinds (San Manuel) averaged to about 32%.

The importer now scales fractions up (admin._to_percent). This converts
the rows already stored the same way: a value above 0 and at most 1 is a
fraction. A genuine survival rate of 1% or less does not occur in the
DENR data, and 0 and NULL are left alone.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '3f1c9a7b2d40'
down_revision = 'ed6ab626fac9'
branch_labels = None
depends_on = None


# Kept as a constant so tests can run exactly this statement.
UPGRADE_SQL = (
    "UPDATE reforestation_record "
    "SET survival_rate = ROUND(CAST(survival_rate * 100 AS numeric), 2) "
    "WHERE survival_rate > 0 AND survival_rate <= 1"
)


def upgrade():
    op.execute(UPGRADE_SQL)


def downgrade():
    # Not reversible: once converted, an imported 86.0 cannot be told apart
    # from a monitoring report's 86.0. Nothing to undo that would be safe.
    pass
