"""Store timestamps as Manila wall-clock time

Revision ID: d8f3a1c5e2b7
Revises: e7b3d5c2a9f1
Create Date: 2026-09-17 23:00:00.000000

Data only; no schema change.

The app saved datetime.now(ZoneInfo("Asia/Manila")), an aware value, into
TIMESTAMP WITHOUT TIME ZONE columns. PostgreSQL converts an aware value
into the server's own zone before dropping the zone, so every stored time
is in the server's zone, not Manila's. A server on America/Los_Angeles
put records 15 hours behind; one on UTC puts them 8 hours behind.

The app now saves naive Manila time (app/utils/timeutil.manila_now), which
PostgreSQL stores unchanged. This converts the rows already saved:

    (value AT TIME ZONE <server zone>) AT TIME ZONE 'Asia/Manila'

reads each value as server-zone time and rewrites it as Manila time. The
server zone is current_setting('TimeZone'), the zone those rows were
written in. On a server already set to Asia/Manila this changes nothing.

Left alone on purpose:
  - monitoring_photo.date_time_taken  camera EXIF time, saved naive
  - site.boundary_captured_at         mixes converted times with plain
                                      monitoring dates; only shown as a date
  - tree_specie.wiki_fetched_at       saved as naive UTC; only shown as a date

Run it straight after deploying the code change, before new records are
written, or those new records would be shifted too.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'd8f3a1c5e2b7'
down_revision = 'e7b3d5c2a9f1'
branch_labels = None
depends_on = None


# (table, column) pairs that were written from an aware Manila datetime.
COLUMNS = [
    ("monitoring_report", "submitted_at"),
    ("monitoring_report", "date_reviewed"),
    ("monitoring_report", "published_at"),
    ("monitoring_photo", "upload_time"),
    ("request", "date_submitted"),
    ("request", "date_reviewed"),
    ("request_attachment", "uploaded_at"),
    ("notification", "created_at"),
    ("audit_log", "created_at"),
    ("users", "password_changed_at"),
    ("site", "boundary_published_at"),
]

SERVER_ZONE = "current_setting('TimeZone')"
MANILA = "'Asia/Manila'"


def _convert(from_zone, to_zone):
    # SQLite (the test database) stores what it is given, so it has
    # nothing to repair.
    if op.get_bind().dialect.name != "postgresql":
        return
    for table, column in COLUMNS:
        op.execute(
            f'UPDATE "{table}" '
            f'SET "{column}" = ("{column}" AT TIME ZONE {from_zone}) '
            f'AT TIME ZONE {to_zone} '
            f'WHERE "{column}" IS NOT NULL'
        )


def upgrade():
    _convert(SERVER_ZONE, MANILA)


def downgrade():
    _convert(MANILA, SERVER_ZONE)
