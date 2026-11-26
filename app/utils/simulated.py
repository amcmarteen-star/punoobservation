"""Simulated data: rows that stand in for districts without real records.

Site.is_simulated and Organization.is_simulated mark them. They show a
province-wide rollout and are labelled wherever they appear. They are never
used in a stated finding (see app/services/cenro_dashboard.py).
"""

from flask import session

from app.extensions import db
from app.models import Organization, Site

# Pages that list sites or organizations, and so may show simulated rows.
SITE_PAGES = {
    'dashboard.index',
    'dashboard.gis_map',
    'dashboard.Reforestation_sites',
    'admin.provincial_overview',
}
ORG_PAGES = {'organization.organizations_list'}

STAFF_ROLES = ('admin', 'superadmin')


def simulated_municipalities(mixed=False):
    """Municipalities the user can see whose sites are all simulated, or
    with mixed=True, those that have both real and simulated sites."""
    from app.models import Location
    from app.utils.jurisdiction import scope_sites
    q = (db.session.query(Location.municipality, Site.is_simulated)
         .select_from(Site)
         .join(Location, Site.location_id == Location.location_id))
    kinds = {}
    for muni, simulated in scope_sites(q).all():
        kinds.setdefault(muni, set()).add(bool(simulated))
    if mixed:
        return sorted(m for m, k in kinds.items() if k == {True, False})
    return sorted(m for m, k in kinds.items() if k == {True})


def page_shows_simulated(endpoint):
    """True when this page shows the user at least one simulated row."""
    if endpoint in SITE_PAGES:
        # Member, leader and officer dashboards show their own area only.
        if endpoint == 'dashboard.index' and session.get('role') not in STAFF_ROLES:
            return False
        from app.utils.jurisdiction import scope_sites
        q = db.session.query(Site.site_id).filter(Site.is_simulated.is_(True))
        return scope_sites(q).first() is not None
    if endpoint in ORG_PAGES:
        from app.utils.jurisdiction import current_cenro
        q = db.session.query(Organization.organization_id).filter(
            Organization.is_simulated.is_(True))
        cenro = current_cenro()
        if cenro is not None:
            q = q.filter(Organization.cenro == cenro)
        return q.first() is not None
    return False
