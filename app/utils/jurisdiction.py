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

from app.models import Site, Location


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
    Restrict a Site query to the user's CENRO.

    Matches on site.cenro, which the DENR importer populates from the
    IMPLEMENTING CENRO column.
    """
    cenro = current_cenro()
    if cenro is None:
        return query
    return query.filter(Site.cenro == cenro)


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


def can_see_municipality(name):
    """Used by API routes that receive a municipality name directly."""
    allowed = allowed_municipalities()
    if allowed is None:
        return True
    return name in allowed


def scope_label():
    """Short description of the current user's scope, for the interface."""
    cenro = current_cenro()
    if cenro is None:
        return "Province-wide"
    return f"CENRO {cenro}"