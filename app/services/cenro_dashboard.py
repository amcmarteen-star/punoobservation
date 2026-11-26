"""
The CENRO and provincial dashboard: a story, what is waiting, and charts.

Reuses, without changing them:
  - the analytics endpoint's figures (api_dashboard_analytics): headline,
    by_year, by_municipality, plant_next, unplanted_top
  - the scope rules: scope_sites() (a CENRO sees its own sites, the
    province sees all), official_sites(), allowed_municipalities()
  - the 85% survival target (DENR_THRESHOLD)

Adds two things the page needs:
  - THE SMALL-SAMPLE RULE. A municipality is judged only when it has at
    least MIN_MONITORED sites with survival data. Fewer: it is grey,
    labelled "Too few sites", never orange, and it is left out of the
    story's problem count and out of the scatter.
  - CHART TITLES THAT STATE THE FINDING, built from the same figures.
"""

import math

from app.extensions import db
from app.models import (
    Location, MonitoringReport, ReforestationRecord, Request, Site, SiteVisit,
)
from app.services.monitoring import DENR_THRESHOLD
from app.utils.jurisdiction import (
    allowed_municipalities, current_cenro, official_sites, scope_sites,
)

MIN_MONITORED = 3      # sites with survival data before a municipality is judged
MIN_SCATTER = 6        # judged municipalities needed before the scatter is shown
WEAK_PATTERN = 0.3     # |r| below this is reported as no clear link

TARGET = DENR_THRESHOLD


# ----------------------------------------------------------------------
# sites in scope
# ----------------------------------------------------------------------

def _scope_sites():
    """The official sites the user may see, the same rule as the analytics
    endpoint, with what the real-only figures need."""
    q = (db.session.query(Site, Location.municipality)
         .join(Location, Site.location_id == Location.location_id))
    return official_sites(scope_sites(q)).all()


def _survival_by_site(site_ids):
    """Average survival per site, for sites that have any."""
    if not site_ids:
        return {}
    from sqlalchemy import func
    rows = (db.session.query(ReforestationRecord.site_id,
                             func.avg(ReforestationRecord.survival_rate))
            .filter(ReforestationRecord.site_id.in_(site_ids),
                    ReforestationRecord.survival_rate.isnot(None))
            .group_by(ReforestationRecord.site_id).all())
    return {sid: v for sid, v in rows if v is not None}


def _planting(site_ids):
    """Seedlings targeted and planted over these sites."""
    if not site_ids:
        return 0, 0
    from sqlalchemy import func
    target, actual = db.session.query(
        func.coalesce(func.sum(ReforestationRecord.target_quantity), 0),
        func.coalesce(func.sum(ReforestationRecord.actual_quantity_planted), 0),
    ).filter(ReforestationRecord.site_id.in_(site_ids)).one()
    return int(target), int(actual)


def field_delivery(site_ids):
    """Delivery from field counts only: seedlings planted, as recorded on
    approved site visits, against the contracted seedlings of the same
    sites. None until approved visits carry a count.

    The spreadsheet's planted column repeats the contracted quantity, so it
    is never used for delivery."""
    if not site_ids:
        return None
    from sqlalchemy import func
    rows = (db.session.query(SiteVisit.site_id, func.sum(SiteVisit.seedlings_planted))
            .filter(SiteVisit.site_id.in_(site_ids),
                    SiteVisit.status == 'Approved',
                    SiteVisit.seedlings_planted.isnot(None))
            .group_by(SiteVisit.site_id).all())
    if not rows:
        return None
    planted = sum(int(n or 0) for _, n in rows)
    target, _ = _planting([sid for sid, _ in rows])
    if not target:
        return None
    return {'pct': planted / target * 100, 'planted': planted,
            'target': target, 'sites': len(rows)}


def _achievement(site_ids):
    """Seedlings planted against target, in percent, or None."""
    target, actual = _planting(site_ids)
    return round(actual / target * 100, 1) if target else None


def _mean(values):
    values = [v for v in values if v is not None]
    return (sum(values) / len(values)) if values else None


# ----------------------------------------------------------------------
# what is waiting
# ----------------------------------------------------------------------

def waiting_counts():
    """Requests, reports and boundaries waiting, in the user's scope."""
    munis = allowed_municipalities()
    cenro = current_cenro()

    rq = Request.query.filter(Request.status.in_(['Submitted', 'Under Review']))
    if munis is not None:
        rq = (rq.join(Location, Request.location_id == Location.location_id)
              .filter(Location.municipality.in_(munis)))

    rep = MonitoringReport.query.filter(
        MonitoringReport.approval_status == 'Pending')
    pub_reports = MonitoringReport.query.filter(
        MonitoringReport.publication_status == 'Pending Publication')
    pub_visits = SiteVisit.query.filter(
        SiteVisit.publication_status == 'Pending Publication')
    if cenro is not None:
        rep = rep.join(Site, MonitoringReport.site_id == Site.site_id).filter(
            Site.cenro == cenro)
        pub_reports = pub_reports.join(
            Site, MonitoringReport.site_id == Site.site_id).filter(
            Site.cenro == cenro)
        pub_visits = pub_visits.join(
            Site, SiteVisit.site_id == Site.site_id).filter(
            Site.cenro == cenro)

    return {
        'requests': rq.count(),
        'reports': rep.count(),
        'boundaries': pub_reports.count() + pub_visits.count(),
    }


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def _plural(n, word, plural=None):
    return f"{n} {word}" if n == 1 else f"{n} {plural or word + 's'}"


def pct(value):
    """A percentage for people. Whole numbers, unless rounding would hide
    which side of the target the value is on (84.6 must not read 85%)."""
    whole = f"{value:.0f}"
    if (value < TARGET) != (round(value) < TARGET):
        return f"{value:.1f}"
    return whole


def _pearson(points):
    n = len(points)
    if n < 2:
        return None
    xs = [p['x'] for p in points]
    ys = [p['y'] for p in points]
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sxy / math.sqrt(sxx * syy)


# ----------------------------------------------------------------------
# the page
# ----------------------------------------------------------------------

FLAT_BAND = 0.10   # full years within 10% of the peak read as steady


def hectares_per_year(by_year, current_year=None):
    """Every year from the first contract year to now, 0 where empty, and
    a title that states the trend.

    by_year: {year: hectares}, real sites only. The current year is
    labelled "<year> (to date)" and left out of the trend, since it is
    not over. Trend: the peak full year against the latest full year.
    """
    if current_year is None:
        from datetime import date
        current_year = date.today().year
    if not by_year:
        return [], "No contract years recorded yet"
    first = min(by_year)
    last = max(current_year, max(by_year))
    years = []
    for y in range(first, last + 1):
        years.append({
            'year': y,
            'label': f"{y} (to date)" if y == current_year else str(y),
            'area': round(by_year.get(y, 0.0), 1),
        })
    full = [y for y in years if y['year'] < current_year]
    if len(full) < 2:
        return years, "Too few full years to show a trend"
    peak = max(full, key=lambda y: y['area'])
    latest = full[-1]
    if peak['area'] == 0:
        return years, "No hectares contracted in any full year"
    low = min(y['area'] for y in full)
    if peak['area'] - low <= FLAT_BAND * peak['area']:
        return years, (f"Contracting held steady at about "
                       f"{peak['area']:,.0f} ha a year")
    if peak is latest:
        start = full[0]
        return years, (f"Contracting rose from {start['area']:,.0f} ha in "
                       f"{start['year']} to {latest['area']:,.0f} ha in "
                       f"{latest['year']}")
    return years, (f"Contracting fell from {peak['area']:,.0f} ha in "
                   f"{peak['year']} to {latest['area']:,.0f} ha in "
                   f"{latest['year']}")


def _seedlings_title(rows):
    """Map title for contracted seedlings, real municipalities only."""
    with_seedlings = [m for m in rows if m.get('seedlings')]
    if not with_seedlings:
        return "No contracted seedlings yet"
    top = max(with_seedlings, key=lambda m: m['seedlings'])
    return (f"{top['municipality']} has the most contracted seedlings: "
            f"{top['seedlings']:,}")


def build_context(analytics, scope_name):
    """Everything the CENRO and provincial dashboard shows.

    analytics is the JSON of api_dashboard_analytics(); scope_name reads
    like "CENRO Urdaneta City" or "the province".

    REAL DATA ONLY IN FINDINGS. Simulated sites (Site.is_simulated) may be
    counted and drawn on the map, labelled "Simulated", but the story, the
    chart titles, the ranking, the gauge, the years chart and the scatter
    use real sites only.
    """
    scope = _scope_sites()
    real = [(s, m) for s, m in scope if not s.is_simulated]
    simulated_sites = len(scope) - len(real)
    real_ids = [s.site_id for s, _ in real]
    survival_by_site = _survival_by_site(real_ids)

    # ---- real figures per municipality ---------------------------------
    simulated_by_muni = {}
    for site, muni in scope:
        if site.is_simulated:
            simulated_by_muni[muni] = simulated_by_muni.get(muni, 0) + 1

    per = {}
    for site, muni in real:
        m = per.setdefault(muni, {'sites': 0, 'survivals': [], 'cost': 0.0,
                                  'cost_area': 0.0, 'area': 0.0, 'ids': []})
        m['sites'] += 1
        m['ids'].append(site.site_id)
        m['area'] += float(site.area_size_ha or 0)
        if site.site_id in survival_by_site:
            m['survivals'].append(survival_by_site[site.site_id])
        area = float(site.area_size_ha or 0)
        if site.project_cost_3yr and area > 0:
            m['cost'] += float(site.project_cost_3yr)
            m['cost_area'] += area

    # ---- municipality rows: drawn on the map; judged only when real -------
    munis = []
    for row in analytics.get('by_municipality', []) or []:
        name = row['municipality']
        r = per.get(name)
        simulated = r is None
        survival = round(_mean(r['survivals']), 1) if r and r['survivals'] else None
        monitored = len(r['survivals']) if r else 0
        judged = (not simulated and monitored >= MIN_MONITORED
                  and survival is not None)
        munis.append({
            'municipality': name,
            'sites': r['sites'] if r else row.get('sites', 0),
            'monitored': monitored,
            # mixed or real: real sites only; fully simulated: as recorded
            'area': (round(r['area'], 2) if r else row.get('area')),
            'achievement': (_achievement(r['ids']) if r
                            else row.get('achievement')),
            # contracted seedlings, real sites only (None when all simulated)
            'seedlings': _planting(r['ids'])[0] if r else None,
            'survival': survival if not simulated else row.get('survival'),
            'cost_per_ha': (round(r['cost'] / r['cost_area'], 0)
                            if r and r['cost_area'] else None),
            'judged': judged,
            'below': judged and survival < TARGET,
            'simulated': simulated,
            'mixed': bool(r) and simulated_by_muni.get(name, 0) > 0,
        })
    real_rows = [m for m in munis if not m['simulated']]
    judged_rows = [m for m in real_rows if m['judged']]
    below_rows = sorted([m for m in judged_rows if m['below']],
                        key=lambda m: m['survival'])
    too_few = [m for m in real_rows if not m['judged']]

    total_sites = len(real)
    active_sites = sum(1 for s, _ in real if s.site_status == 'Active')
    real_area = sum(float(s.area_size_ha or 0) for s, _ in real)
    target, actual = _planting(real_ids)

    # ---- story: status -> problem -> insight, real sites only ------------
    if total_sites == 0:
        story = f"No official sites in {scope_name} yet."
    else:
        status = (f"{active_sites} of {_plural(total_sites, 'site')} are "
                  f"active, covering {real_area:,.0f} ha.")
        if not judged_rows:
            problem = ("There is not enough monitoring yet to judge any "
                       "municipality.")
            insight = ""
        elif not below_rows:
            problem = (f"All {_plural(len(judged_rows), 'municipality', 'municipalities')} "
                       f"with enough data meet the {TARGET:.0f}% survival target.")
            best = max(judged_rows, key=lambda m: m['survival'])
            insight = f" {best['municipality']} is highest at {pct(best['survival'])}%."
        else:
            problem = (f"{len(below_rows)} of {_plural(len(judged_rows), 'municipality', 'municipalities')} "
                       f"with enough data {'is' if len(below_rows) == 1 else 'are'} "
                       f"below the {TARGET:.0f}% survival target.")
            worst = below_rows[0]
            insight = (f" {worst['municipality']} is lowest at "
                       f"{pct(worst['survival'])}% across {worst['sites']} sites.")
        if too_few:
            insight += (f" {_plural(len(too_few), 'municipality', 'municipalities')} "
                        f"{'has' if len(too_few) == 1 else 'have'} too few "
                        "monitored sites to judge.")
        story = f"{status} {problem}{insight}"

    # ---- KPI tiles: real sites; simulated counted apart, labelled ----------
    # Each tile jumps to the section on this page that explains it.
    tiles = [
        {'label': 'Official sites', 'value': f"{total_sites:,}",
         'sub': f"{active_sites:,} active", 'tone': 'neutral',
         'href': '#cd-map-section'},
        {'label': 'Area', 'value': f"{real_area:,.0f} ha",
         'sub': 'under contract', 'tone': 'neutral', 'href': '#cd-years-chart'},
        # The spreadsheet's planted column repeats the contracted quantity,
        # so the tile shows contracted seedlings, with no percentage.
        {'label': 'Seedlings (contracted)', 'value': f"{target:,}",
         'sub': 'in the contracts', 'tone': 'neutral',
         'href': '#cd-map-section', 'metric': 'seedlings'},
    ]
    delivery = field_delivery(real_ids)
    if delivery is not None:
        tiles.append({'label': 'Delivery', 'value': f"{delivery['pct']:.0f}%",
                      'sub': (f"field counts, {_plural(delivery['sites'], 'site')}"),
                      'tone': 'neutral'})   # plain: no section explains it yet
    # Simulated: provincial and system admins only.
    if simulated_sites and current_cenro() is None:
        tiles.append({'label': 'Simulated sites',
                      'value': f"{simulated_sites:,}",
                      'sub': 'demonstration only, not in findings',
                      'tone': 'neutral', 'href': '#cd-map-section'})

    # ---- 1. hectares per year, real sites ----------------------------------
    by_year = {}
    for site, _ in real:
        if site.year_contracted:
            y = int(site.year_contracted)
            by_year[y] = by_year.get(y, 0.0) + float(site.area_size_ha or 0)
    years, years_title = hectares_per_year(by_year)

    # ---- 2. gauge, real sites ------------------------------------------------
    survival = _mean(survival_by_site.values())
    if survival is None:
        gauge_title = "No monitoring reports yet"
    else:
        gauge_title = (f"Survival is {pct(survival)}%, "
                       f"{'meeting' if survival >= TARGET else 'below'} "
                       f"the {TARGET:.0f}% target")

    # ---- 3. survival ranking, real municipalities ----------------------------
    ranked = sorted(judged_rows, key=lambda m: m['survival']) + sorted(
        too_few, key=lambda m: m['municipality'])
    if not real_rows:
        bar_title = "No municipalities with sites yet"
    elif not judged_rows:
        bar_title = "Too few monitored sites to judge any municipality"
    elif below_rows:
        bar_title = (f"{_plural(len(below_rows), 'municipality', 'municipalities')} "
                     f"below {TARGET:.0f}% survival")
    else:
        bar_title = (f"All {_plural(len(judged_rows), 'judged municipality', 'judged municipalities')} "
                     f"meet {TARGET:.0f}% survival")

    # ---- 4. map: every municipality drawn; titles from real ones -------------
    with_area = [m for m in real_rows if m['area']]
    map_titles = {
        'survival': bar_title,
        'area': (f"{max(with_area, key=lambda m: m['area'])['municipality']} has "
                 f"the most area under contract"
                 if with_area else "No contracted area yet"),
        'seedlings': _seedlings_title(real_rows),
    }

    # ---- 5. scatter, judged real municipalities -------------------------------
    scatter_points = [
        {'x': m['cost_per_ha'], 'y': m['survival'], 'label': m['municipality'],
         'sites': m['sites']}
        for m in judged_rows if m['cost_per_ha']
    ]
    scatter = {'show': len(scatter_points) >= MIN_SCATTER,
               'points': scatter_points, 'needed': MIN_SCATTER, 'r': None}
    if scatter['show']:
        r = _pearson(scatter_points)
        scatter['r'] = round(r, 2) if r is not None else None
        if r is None or abs(r) < WEAK_PATTERN:
            scatter['title'] = ("No clear link between cost per hectare and "
                                "survival")
        else:
            scatter['title'] = (f"Higher cost per hectare goes with "
                                f"{'higher' if r > 0 else 'lower'} survival "
                                f"(r = {r:.2f})")
    else:
        scatter['title'] = (f"Too few municipalities to compare cost and "
                            f"survival ({len(scatter_points)} of "
                            f"{MIN_SCATTER} needed)")

    # ---- 6. what next ---------------------------------------------------------
    plant = analytics.get('plant_next') or {}
    next_list = (analytics.get('unplanted_top') or [])[:8]
    if next_list:
        n_next = plant.get('without_site') or len(next_list)
        next_title = (f"{_plural(n_next, 'highly suitable barangay')} "
                      f"{'has' if n_next == 1 else 'have'} no site yet")
    else:
        next_title = "No unplanted suitable barangays found"

    return {
        'story': story,
        'tiles': tiles,
        'years': years, 'years_title': years_title,
        'survival': survival, 'gauge_title': gauge_title,
        'survival_text': pct(survival) if survival is not None else None,
        'ranked': ranked, 'bar_title': bar_title,
        'munis': munis, 'map_titles': map_titles,
        'scatter': scatter,
        'next_list': next_list, 'next_title': next_title,
        'target': TARGET,
        'min_monitored': MIN_MONITORED,
        'total_sites': total_sites,
        'simulated_sites': simulated_sites,
    }
