"""
Philippine time for everything the system records and shows.

STORING
Timestamps are stored as naive Manila wall-clock time, e.g.
2026-09-17 22:19. Use manila_now() for every value that is saved.

Do not save datetime.now(ZoneInfo("Asia/Manila")) directly. The columns
are TIMESTAMP WITHOUT TIME ZONE, and PostgreSQL converts an aware value
into the database server's own zone before dropping the zone. A server
set to America/Los_Angeles stored every record 15 hours behind; one set
to UTC stores it 8 hours behind. A naive value is saved exactly as given,
whatever the server's zone.

SHOWING
format_datetime() and format_date() are registered as the Jinja filters
datetime_ph and date_ph, so every page writes times the same way.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

MANILA = ZoneInfo("Asia/Manila")

DATETIME_FORMAT = "%d %b %Y, %I:%M %p"   # 17 Sep 2026, 10:19 PM
DATE_FORMAT = "%d %b %Y"                 # 17 Sep 2026


def manila_now():
    """The current Philippine time, naive, ready to store."""
    return datetime.now(MANILA).replace(tzinfo=None)


def _as_manila(dt):
    """An aware value is converted to Manila; a naive one already is."""
    if dt.tzinfo is not None:
        return dt.astimezone(MANILA).replace(tzinfo=None)
    return dt


def format_datetime(dt, empty=""):
    """'17 Sep 2026, 10:19 PM'. A plain date gets no time."""
    if dt is None:
        return empty
    if not isinstance(dt, datetime):
        return dt.strftime(DATE_FORMAT)
    return _as_manila(dt).strftime(DATETIME_FORMAT)


def format_date(dt, empty=""):
    """'17 Sep 2026'."""
    if dt is None:
        return empty
    if isinstance(dt, datetime):
        dt = _as_manila(dt)
    return dt.strftime(DATE_FORMAT)
