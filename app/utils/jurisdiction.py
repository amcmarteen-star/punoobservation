"""
CENRO jurisdiction filtering.

DENR structure:

    PENRO Pangasinan            provincial oversight    -> superadmin
      CENRO Urdaneta            Eastern Pangasinan      -> admin
      CENRO Dagupan             Central Pangasinan      -> admin
      CENRO Alaminos            Western Pangasinan      -> admin

A superadmin sees the province. An admin sees their own CENRO. Field
officers and ordinary users inherit whatever CENRO they are assigned.

FAILS OPEN. A user with no CENRO sees everything. See the note in the
Part 1 document for why.
"""

from flask import session
from sqlalchemy import or_

from app.models import Site, Location, User


# Which municipalities belong to which CENRO.
#
# Districts 5 and 6 are the CENRO Urdaneta jurisdiction and are the only
# ones we hold data for. Dagupan and Alaminos are listed so the mapping
# is complete and so a panel can see the structure, even though those
# municipalities carry no data yet.
CENRO_MUNICIPALITIES = {
    "Urdaneta City": [
        "Alcala", "Asingan", "Balungao", "Bautista", "Binalonan",
        "Laoac", "Natividad", "Pozorrubio", "Rosales", "San Manuel",
        "San Nicolas", "San Quintin", "Santa Maria", "Santo Tomas",
        "Sison", "Tayug", "Umingan", "Urdaneta City", "Villasis",
    ],
    "Dagupan": [],      # Central Pangasinan - no data imported
    "Alaminos": [],     # Western Pangasinan - no data imported
}

CENRO_LIST = list(CENRO_MUNICIPALITIES.keys())

# The part of the province each CENRO covers, as the interface names it.
CENRO_REGIONS = {
    "Urdaneta City": "Eastern Pangasinan",
    "Dagupan": "Central Pangasinan",
    "Alaminos": "Western Pangasinan",
}


def current_cenro():
    """
    The CENRO the logged-in user is limited to, or None for no limit.

    None means province-wide: superadmins, and anyone without an
    assignment.
    """
    if session.get('role') == 'superadmin':
        return None
    return session.get('cenro') or None


def is_superadmin():
    return session.get('role') == 'superadmin'


def scope_sites(query):
    """
    Restrict a Site query to the sites the user may see.

    Two rules:
      1. CENRO: an admin or officer sees their own CENRO's sites.
      2. Official only, for guests and normal users: a site created from
         a request is hidden until the province publishes its GPS
         boundary. Staff (STAFF_ROLES) see it from the day it is created.

    Matches on site.cenro, which the DENR importer populates from the
    IMPLEMENTING CENRO column.
    """
    cenro = current_cenro()
    if cenro is not None:
        query = query.filter(Site.cenro == cenro)

    if not can_see_unofficial_sites():
        query = query.filter(or_(
            Site.source_request_id.is_(None),
            Site.boundary_published.is_(True),
        ))
    return query


def scope_locations(query):
    """
    Restrict a Location query to the user's CENRO.

    Location has no CENRO column, so the municipality list is used
    instead. A CENRO with no municipalities listed yields no rows, which
    is correct: that office has no jurisdiction recorded yet.
    """
    cenro = current_cenro()
    if cenro is None:
        return query

    munis = CENRO_MUNICIPALITIES.get(cenro, [])
    if not munis:
        return query.filter(False)

    return query.filter(Location.municipality.in_(munis))


def allowed_municipalities():
    """
    Municipality names the current user may see.

    None means all of them, which callers should treat as no filter
    rather than as an empty list.
    """
    cenro = current_cenro()
    if cenro is None:
        return None
    return CENRO_MUNICIPALITIES.get(cenro, [])


# The GeoJSON files write municipality names differently from the
# database. barangay.geojson and district5.geojson drop the space
# ("UrdanetaCity", "SanNicolas") and district5.geojson spells Pozorrubio
# as "Pozzorubio". Those names reach can_see_municipality() straight from
# a map click, so a plain string match rejected towns the user owns.
MUNICIPALITY_ALIASES = {
    "pozzorubio": "pozorrubio",
}


def normalize_municipality(name):
    """Lowercase and strip spaces, dots and dashes, then fold aliases."""
    if not name:
        return ""
    key = name.lower()
    for ch in (" ", ".", "-", "'"):
        key = key.replace(ch, "")
    return MUNICIPALITY_ALIASES.get(key, key)


# Every municipality the province knows about, in the spelling the
# database uses.
ALL_MUNICIPALITIES = [
    m for munis in CENRO_MUNICIPALITIES.values() for m in munis
]


def canonical_municipality(name):
    """
    The database spelling of a municipality name, or None if unknown.

    Callers pass a name that came off the map ("UrdanetaCity",
    "Pozzorubio") and get back the name the Location rows actually hold
    ("Urdaneta City", "Pozorrubio"), so the query can match exactly.
    """
    wanted = normalize_municipality(name)
    for m in ALL_MUNICIPALITIES:
        if normalize_municipality(m) == wanted:
            return m
    return None


def can_see_municipality(name):
    """
    Used by API routes that receive a municipality name directly.

    Compared on the normalized form so a map click on "UrdanetaCity"
    matches the "Urdaneta City" held in CENRO_MUNICIPALITIES.
    """
    allowed = allowed_municipalities()
    if allowed is None:
        return True
    wanted = normalize_municipality(name)
    return any(normalize_municipality(m) == wanted for m in allowed)


def region_label():
    """
    The area the current user works in, for page titles.

    A CENRO's staff get their part of the province, e.g. "Eastern
    Pangasinan". Everyone without a CENRO (PENRO, superadmin, normal
    users, guests) gets the whole province.
    """
    cenro = current_cenro()
    if cenro is None:
        return "Pangasinan"
    return CENRO_REGIONS.get(cenro, "Pangasinan")


def scope_label():
    """Short description of the current user's scope, for the interface."""
    cenro = current_cenro()
    if cenro is None:
        return "Province-wide"
    return f"CENRO {cenro}"


def cenro_for_municipality(municipality):
    """
    The CENRO whose jurisdiction lists this municipality, or None.

    Compared on the normalized form, so "UrdanetaCity" from the map and
    "Urdaneta City" from the database both resolve.
    """
    key = normalize_municipality(municipality)
    if not key:
        return None
    for cenro, municipalities in CENRO_MUNICIPALITIES.items():
        if any(normalize_municipality(m) == key for m in municipalities):
            return cenro
    return None


def reviewing_admins(cenro):
    """
    Active admins who review requests and reports for one CENRO.

    Review is a CENRO function, so only that office is notified. The
    provincial (PENRO) admins and the superadmins cannot act on a request
    or a monitoring report, so sending them the notice only filled their
    bell with work that belongs to someone else.

    Fallback: when the CENRO is unknown or has no active admin, nobody
    could act on the notice. It then goes to the provincial admins, so the
    item is at least seen instead of being lost without a trace.
    """
    admins = []
    if cenro:
        admins = User.query.filter(
            User.role == 'admin',
            User.cenro == cenro,
            User.is_active.is_(True),
        ).all()

    if not admins:
        admins = User.query.filter(
            User.role == 'admin',
            User.cenro.is_(None),
            User.is_active.is_(True),
        ).all()

    return admins


# Roles that plan, survey, review or publish sites. They see sites made
# from a request, and their proposed boundaries, before anything is
# official. Guests and normal users see only official records.
STAFF_ROLES = ('field_officer', 'admin', 'superadmin')


def can_see_unofficial_sites():
    """True for staff. False for guests and normal users."""
    return session.get('role') in STAFF_ROLES


def can_see_site(site):
    """
    The official-only rule from scope_sites(), for one site already loaded.

    Imported DENR sites are always official. A site created from a
    request becomes official when the province publishes its boundary.
    """
    if can_see_unofficial_sites():
        return True
    return site.source_request_id is None or bool(site.boundary_published)