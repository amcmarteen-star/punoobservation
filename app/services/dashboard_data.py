"""
The figures for each role's dashboard.

Everything here reuses the rules the official figures already follow:
  - official_sites(): a site counts once its request is approved, and an
    archived site is left out. Temporary sites under review are not official.
  - DENR_THRESHOLD (85%) is the survival target.
  - Survival is averaged per site first, then across sites, as the
    analytics endpoint does.

No new metric is defined here. A figure with no data is None, never 0.
"""

from datetime import date, timedelta

from flask import url_for
from sqlalchemy import func

from app.extensions import db
from app.models import (
    Location, Organization, ReforestationRecord, Request, Site, SiteVisit,
    User, VisitAssignment,
)
from app.services.monitoring import DENR_THRESHOLD
from app.services.recommender import recommend_for_location
from app.services.request_site import site_position
from app.services.request_stage import AT_ORGANIZATION, APPROVED
from app.services.request_timeline import build_timeline
from app.utils.jurisdiction import official_sites, without_archived
from app.utils.timeutil import manila_now


# ----------------------------------------------------------------------
# site sets and their figures
# ----------------------------------------------------------------------

def official_site_ids(*criteria):
    q = db.session.query(Site.site_id).join(
        Location, Site.location_id == Location.location_id)
    if criteria:
        q = q.filter(*criteria)
    return [row[0] for row in official_sites(q).all()]


def site_figures(site_ids):
    """Seedlings targeted and planted, and survival over the sites."""
    if not site_ids:
        return {'sites': 0, 'target': 0, 'actual': 0,
                'survival': None, 'monitored': 0}
    target, actual = db.session.query(
        func.coalesce(func.sum(ReforestationRecord.target_quantity), 0),
        func.coalesce(func.sum(ReforestationRecord.actual_quantity_planted), 0),
    ).filter(ReforestationRecord.site_id.in_(site_ids)).one()
    per_site = (db.session.query(ReforestationRecord.site_id,
                                 func.avg(ReforestationRecord.survival_rate))
                .filter(ReforestationRecord.site_id.in_(site_ids),
                        ReforestationRecord.survival_rate.isnot(None))
                .group_by(ReforestationRecord.site_id).all())
    values = [v for _, v in per_site if v is not None]
    return {
        'sites': len(site_ids),
        'target': int(target),
        'actual': int(actual),
        'survival': (sum(values) / len(values)) if values else None,
        'monitored': len(values),
    }


def _plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def story_for(fig, where):
    """One sentence about the figures. `where` reads like 'in Bacag, Villasis'."""
    if fig['sites'] == 0:
        return f"No reforestation sites {where} yet."
    if fig['survival'] is None:
        return (f"{_plural(fig['sites'], 'site')} {where}. "
                "No monitoring reports yet.")
    return (f"{_plural(fig['sites'], 'site')} {where} "
            f"{'has' if fig['sites'] == 1 else 'have'} planted "
            f"{fig['actual']:,} seedlings. Survival is "
            f"{fig['survival']:.0f}%, against the "
            f"{DENR_THRESHOLD:.0f}% target.")


MEMBER_SECTIONS = {'sites': '#dash-sites', 'seedlings': '#dash-sites',
                   'survival': '#dash-sites'}
LEADER_SECTIONS = {'sites': '#dash-org-sites', 'seedlings': '#dash-years',
                   'survival': '#dash-survival'}


def tiles_for(fig, sections=MEMBER_SECTIONS):
    """The three KPI tiles every member and leader sees. Each jumps to
    its section on the same dashboard."""
    if fig['survival'] is None:
        survival = {'label': 'Survival', 'value': 'No reports yet',
                    'sub': f"Target {DENR_THRESHOLD:.0f}%", 'tone': 'neutral'}
    else:
        below = fig['survival'] < DENR_THRESHOLD
        survival = {'label': 'Survival', 'value': f"{fig['survival']:.0f}%",
                    'sub': f"Target {DENR_THRESHOLD:.0f}%",
                    'tone': 'below' if below else 'ok'}
    survival['href'] = sections['survival']
    return [
        {'label': 'Sites', 'value': f"{fig['sites']:,}",
         'sub': 'official sites', 'tone': 'neutral',
         'href': sections['sites'], 'go': 'See map'},
        {'label': 'Seedlings (contracted)', 'value': f"{fig['target']:,}",
         'sub': 'in the contracts', 'tone': 'neutral',
         'href': sections['seedlings']},
        survival,
    ]


def _barangay(user):
    if not user.location_id:
        return None
    return db.session.get(Location, user.location_id)


def _points(site_ids, home_location_id=None):
    """Map markers for sites: (lat, lon, name) where the position is known.
    `home` marks sites in the viewer's own barangay, drawn highlighted."""
    if not site_ids:
        return []
    out = []
    for site in Site.query.filter(Site.site_id.in_(site_ids)).all():
        pos = site_position(site)
        if pos:
            out.append({'lat': pos[0], 'lon': pos[1], 'name': site.site_name,
                        'home': bool(home_location_id)
                        and site.location_id == home_location_id})
    return out


def _timeline_for(user):
    req = (Request.query.filter_by(user_id=user.user_id)
           .order_by(Request.date_submitted.desc()).first())
    return (req, build_timeline(req)) if req else (None, None)


# ----------------------------------------------------------------------
# member (also the base of the leader page)
# ----------------------------------------------------------------------

def member_context(user):
    """Individuals and pending members: their barangay. Active members:
    their organization's official sites. The species card and the map are
    always the barangay."""
    barangay = _barangay(user)
    org = None
    if user.organization_id and user.org_status == 'active':
        org = db.session.get(Organization, user.organization_id)

    if org is not None:
        ids = official_site_ids(Site.organization_id == org.organization_id)
        fig = site_figures(ids)
        where = f"for {org.organization_name}"
        scope = 'organization'
    else:
        ids = (official_site_ids(Site.location_id == barangay.location_id)
               if barangay else [])
        fig = site_figures(ids)
        where = (f"in {barangay.barangay}, {barangay.municipality}"
                 if barangay else "")
        scope = 'barangay'

    species = None
    if barangay is not None:
        species = recommend_for_location(barangay, top_k=3)

    # The map section shows the same sites as the tiles: the organization's
    # for an active member (own barangay highlighted), else the barangay's.
    map_points = _points(ids, barangay.location_id
                         if org is not None and barangay else None)
    map_section = {
        'title': ("Your organization's sites" if org is not None
                  else "Sites in your barangay"),
        'figures': site_figures(ids),
        'unmapped': len(ids) - len(map_points),
        'shown': org is not None or barangay is not None,
    }

    req, timeline = _timeline_for(user)
    return {
        'scope': scope,
        'org': org,
        'barangay': barangay,
        'figures': fig,
        'kpis': tiles_for(fig),
        'story': story_for(fig, where) if barangay or org else None,
        'request': req,
        'timeline': timeline,
        'species': species,
        'points': map_points,
        'map_section': map_section,
    }


# ----------------------------------------------------------------------
# leader
# ----------------------------------------------------------------------

def leader_context(user, org):
    member = member_context(user)
    fig = member['figures']
    member['kpis'] = tiles_for(fig, LEADER_SECTIONS)

    waiting_members = (User.query
                       .filter(User.organization_id == org.organization_id,
                               User.org_status == 'pending',
                               User.email_verified.is_(True))
                       .order_by(User.username).all())
    requests_to_review = (Request.query
                          .filter(Request.organization_id == org.organization_id,
                                  Request.status.in_(AT_ORGANIZATION))
                          .order_by(Request.date_submitted).all())

    # seedlings per year, official sites only
    sites = (Site.query.join(Location, Site.location_id == Location.location_id)
             .filter(Site.site_id.in_(official_site_ids(
                 Site.organization_id == org.organization_id))).all())
    by_year = {}
    for site in sites:
        year = site.year_contracted
        if not year:
            continue
        f = site_figures([site.site_id])
        bucket = by_year.setdefault(int(year), {'year': int(year),
                                                'target': 0, 'actual': 0})
        bucket['target'] += f['target']
        bucket['actual'] += f['actual']
    years = [by_year[y] for y in sorted(by_year)]

    # every site of the organization, including those under review
    rows = []
    for site in without_archived(
            Site.query.filter(Site.organization_id == org.organization_id)
    ).order_by(Site.site_name).all():
        under_review = (site.source_request_id is not None
                        and site.source_request is not None
                        and site.source_request.status != APPROVED)
        f = site_figures([site.site_id])
        below = (not under_review and f['survival'] is not None
                 and f['survival'] < DENR_THRESHOLD)
        rows.append({
            'name': site.site_name,
            'barangay': (f"{site.location.barangay}, {site.location.municipality}"
                         if site.location else ""),
            'target': f['target'],
            'actual': f['actual'],
            'survival': (f"{f['survival']:.0f}%"
                         if f['survival'] is not None else "No reports yet"),
            'under_review': under_review,
            'below': below,
        })

    invite_url = (url_for('organization.join_page', token=org.join_token,
                          _external=True) if org.join_token else None)
    return {
        **member,
        'queue': {
            'waiting_members': waiting_members,
            'requests': requests_to_review,
        },
        'gauge': fig['survival'],
        'years': years,
        'rows': rows,
        'invite_url': invite_url,
    }


# ----------------------------------------------------------------------
# field officer
# ----------------------------------------------------------------------

def _visited_since_assigned(assignment):
    since = (assignment.created_at.date() if assignment.created_at
             else date.min)
    return SiteVisit.query.filter(
        SiteVisit.site_id == assignment.site_id,
        SiteVisit.user_id == assignment.officer_id,
        SiteVisit.visit_date >= since,
    ).first() is not None


def officer_context(user):
    today = manila_now().date()
    week_start = today - timedelta(days=today.weekday())

    open_assignments = (VisitAssignment.query
                        .filter_by(officer_id=user.user_id, status='Open')
                        .all())
    todo = []
    for a in open_assignments:
        site = db.session.get(Site, a.site_id)
        if site is None:
            continue
        overdue = (a.target_date is not None and a.target_date < today
                   and not _visited_since_assigned(a))
        todo.append({
            'site': site,
            'site_name': site.site_name,
            'visit_type': a.visit_type,
            'target_date': a.target_date,
            'overdue': overdue,
        })
    todo.sort(key=lambda t: (not t['overdue'],
                             t['target_date'] or date.max))

    overdue_count = sum(1 for t in todo if t['overdue'])
    visits_this_week = SiteVisit.query.filter(
        SiteVisit.user_id == user.user_id,
        SiteVisit.visit_date >= week_start,
        SiteVisit.visit_date <= today,
    ).count()
    # Awaiting approval is the CENRO's step: a neutral tile, not an alert.
    awaiting = SiteVisit.query.filter_by(user_id=user.user_id,
                                         status='Pending').count()

    tiles = [
        {'label': 'Visits this week', 'value': f"{visits_this_week:,}",
         'sub': 'recorded since Monday', 'tone': 'neutral',
         'href': '#dash-todo', 'go': 'See list'},
        {'label': 'Overdue', 'value': f"{overdue_count:,}",
         'sub': 'past the target date, no visit yet',
         'tone': 'below' if overdue_count else 'ok',
         'href': '#dash-todo', 'go': 'See list'},
        {'label': 'Awaiting approval', 'value': f"{awaiting:,}",
         'sub': 'with your CENRO', 'tone': 'neutral',
         'href': '#dash-todo', 'go': 'See list'},
    ]
    if not todo and not visits_this_week and not awaiting:
        story = "No visits are assigned to you yet."
    else:
        story = (f"You have {_plural(len(todo), 'open visit')}"
                 + (f", {overdue_count} overdue." if overdue_count else "."))
    return {
        'story': story,
        'tiles': tiles,
        'todo': todo,
        'points': _points([t['site'].site_id for t in todo]),
    }
