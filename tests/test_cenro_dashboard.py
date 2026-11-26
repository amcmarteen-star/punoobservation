"""
The CENRO and provincial dashboard (Module 6).

Runs the real Flask routes against a throwaway SQLite database.

WHAT IS UNDER TEST

    1  a CENRO admin sees only that CENRO's municipalities; the provincial
       admin sees every municipality
    2  the story says how many sites are active, and counts only judged
       municipalities as problems
    3  a municipality with fewer than 3 monitored sites is grey, labelled
       "Too few sites", left out of the problem count and the scatter
    4  the scatter shows only with at least 6 judged municipalities, and is
       replaced by an explanation otherwise
    5  the page has at most 6 charts and maps
    6  chart titles state the finding
    7  an office with no sites gets an empty state in every block
    8  the action strip counts requests in the CENRO's area

RUN

    python tests/test_cenro_dashboard.py

Exit code 0 when every check passes, 1 otherwise.
"""

import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# importing this first points DATABASE_URL at a temporary SQLite file
import test_publish_boundary as base                    # noqa: E402
from app.extensions import db                            # noqa: E402
from app.models import (                                 # noqa: E402
    Location, Organization, ReforestationRecord, Request, Site, SiteVisit,
    TreeSpecie, User,
)
from app.utils.jurisdiction import CENRO_MUNICIPALITIES  # noqa: E402

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append({'name': name, 'ok': bool(ok)})
    print(('PASS  ' if ok else 'FAIL  ') + name
          + (f'  [{detail}]' if detail and not ok else ''))
    return bool(ok)


def page_data(html):
    """The figures the page's script reads (the first `var CD = {...};`)."""
    m = re.search(r'var CD = (\{.*?\});\n', html)
    return json.loads(m.group(1)) if m else None


def add_municipality(name, survivals, org_id, tree_id, cost=500000.0,
                     cenro='Urdaneta City', simulated=False):
    """One municipality with one site per survival value."""
    loc = Location(psgc_code=f'SYN-CD-{name}', region='Region I',
                   province='Pangasinan', municipality=name,
                   barangay=f'{name} Poblacion', latitude=16.0,
                   longitude=120.6, elevation_m=30.0)
    db.session.add(loc)
    db.session.flush()
    for i, s in enumerate(survivals):
        site = Site(location_id=loc.location_id, organization_id=org_id,
                    site_name=f'{name} site {i}', site_code=f'CD-{name}-{i}',
                    area_size_ha=10.0, site_status='Active',
                    cenro=cenro, year_contracted=2024 + (i % 2),
                    is_simulated=simulated,
                    project_cost_3yr=cost * (1 + i * 0.1))
        db.session.add(site)
        db.session.flush()
        db.session.add(ReforestationRecord(
            site_id=site.site_id, tree_id=tree_id,
            date_planted=date(2024, 6, 1), target_quantity=1000,
            actual_quantity_planted=900, survival_rate=s))
    db.session.flush()


def run(app):
    s = base.seed()
    tree_id = TreeSpecie.query.first().tree_id
    org_id = db.session.query(Organization.organization_id).first()[0]

    # Six judged municipalities: two below 85%, four above. Laoac has one
    # monitored site, so it is too small to judge, even though it is low.
    add_municipality('Alcala', [60, 62, 58], org_id, tree_id, cost=900000)
    add_municipality('Asingan', [70, 72, 68], org_id, tree_id, cost=800000)
    add_municipality('Balungao', [90, 92, 91], org_id, tree_id, cost=400000)
    add_municipality('Bautista', [88, 90, 89], org_id, tree_id, cost=450000)
    add_municipality('Binalonan', [95, 93, 94], org_id, tree_id, cost=300000)
    add_municipality('Natividad', [87, 86, 88], org_id, tree_id, cost=500000)
    add_municipality('Laoac', [40], org_id, tree_id, cost=950000)
    # Simulated rollout in another CENRO: very low survival, many sites.
    # It must be drawn and labelled, but never reach a finding.
    add_municipality('Mangaldan', [20, 22, 21, 19], org_id, tree_id,
                     cost=1500000, cenro='Dagupan', simulated=True)
    # A mixed municipality: 3 real sites (90%, 10 ha each) and 2 simulated
    # ones (10%, 500 ha each). Every value must come from the real sites.
    add_municipality('Calasiao', [90, 90, 90], org_id, tree_id, cenro='Dagupan')
    cal = Location.query.filter_by(municipality='Calasiao').first()
    for i in range(2):
        sim = Site(location_id=cal.location_id, organization_id=org_id,
                   site_name=f'Calasiao simulated {i}', site_code=f'CD-CALSIM-{i}',
                   area_size_ha=500.0, site_status='Active', cenro='Dagupan',
                   year_contracted=2024, is_simulated=True)
        db.session.add(sim)
        db.session.flush()
        db.session.add(ReforestationRecord(
            site_id=sim.site_id, tree_id=tree_id, date_planted=date(2024, 6, 1),
            target_quantity=1000, actual_quantity_planted=10, survival_rate=10))

    # an office with no sites at all
    db.session.add(User(username='syn_alaminos_admin',
                        email_address='syn_alaminos_admin@example.test',
                        role='admin', cenro='Alaminos', email_verified=True,
                        password_hash='x'))
    # a request waiting in the Urdaneta area
    bacag = Location.query.filter_by(barangay='Bacag').first()
    db.session.add(Request(user_id=s.citizen_id, location_id=bacag.location_id,
                           request_type='New Planting Site', status='Submitted',
                           contact_name='Maria Santos',
                           contact_email='maria@synthetic.test'))
    db.session.commit()
    alaminos_id = User.query.filter_by(username='syn_alaminos_admin').first().user_id

    def as_(uid, name, role, cenro):
        c = app.test_client()
        base.login(c, uid, name, role, cenro)
        return c

    urdaneta = as_(s.cenro_admin_id, s.cenro_admin_name, 'admin', 'Urdaneta City')
    dagupan = as_(s.dagupan_admin_id, s.dagupan_admin_name, 'admin', 'Dagupan')
    provincial = as_(s.penro_id, s.penro_name, 'admin', None)
    alaminos = as_(alaminos_id, 'syn_alaminos_admin', 'admin', 'Alaminos')

    html = urdaneta.get('/dashboard').get_data(as_text=True)
    cd = page_data(html)
    check('the CENRO page builds and carries its figures', cd is not None)
    munis = {m['municipality']: m for m in cd['munis']} if cd else {}

    # ------------------------------------------------------------------
    # 1. scope
    # ------------------------------------------------------------------
    urdaneta_list = set(CENRO_MUNICIPALITIES['Urdaneta City'])
    check('1 the Urdaneta CENRO sees only Urdaneta municipalities',
          munis and set(munis) <= urdaneta_list, sorted(munis))
    check('1 the Urdaneta CENRO does not see Dagupan City',
          'Dagupan City' not in munis)
    pcd = page_data(provincial.get('/dashboard').get_data(as_text=True))
    pmunis = {m['municipality'] for m in pcd['munis']} if pcd else set()
    check('1 the provincial admin sees every municipality, Dagupan City too',
          'Dagupan City' in pmunis and 'Alcala' in pmunis)

    # ------------------------------------------------------------------
    # 2-3. story and the small-sample rule
    # ------------------------------------------------------------------
    story = re.search(r'<p class="cd-story">(.*?)</p>', html, re.S)
    story = story.group(1) if story else ''
    check('2 the story says how many sites are active',
          re.search(r'\d+ of \d+ sites are active', story) is not None, story)
    judged = [m for m in cd['munis'] if m['judged']]
    below = [m for m in judged if m['below']]
    check('2 the problem count uses judged municipalities only (2 of 6)',
          len(judged) == 6 and len(below) == 2
          and '2 of 6 municipalities with enough data are below' in story,
          story)
    check('2 the insight names the lowest judged municipality',
          'Alcala is lowest' in story, story)
    check('3 a municipality with 1 monitored site is not judged',
          munis.get('Laoac', {}).get('judged') is False)
    check('3 it is never marked as a problem (never orange)',
          munis.get('Laoac', {}).get('below') is False)
    check('3 Villasis, with 2 seeded sites, is not judged either',
          munis.get('Villasis', {}).get('judged') is False)
    check('3 the page labels small samples "Too few sites"',
          'Too few sites' in html)
    check('3 every municipality value carries its site count',
          all('sites' in m and m['sites'] >= 1 for m in cd['munis']))

    # ------------------------------------------------------------------
    # 4. the scatter
    # ------------------------------------------------------------------
    sc = cd['scatter']
    labels = {p['label'] for p in sc['points']}
    check('4 the scatter shows with 6 judged municipalities',
          sc['show'] is True and 'id="cd-scatter"' in html)
    check('4 small samples are left out of the scatter',
          'Laoac' not in labels and 'Villasis' not in labels)
    check('4 the scatter title states a finding, not a topic',
          sc['title'].startswith('No clear link')
          or sc['title'].startswith('Higher cost per hectare goes with'),
          sc['title'])
    dhtml = dagupan.get('/dashboard').get_data(as_text=True)
    dcd = page_data(dhtml)
    check('4 with fewer than 6 judged municipalities, no scatter',
          dcd and dcd['scatter']['show'] is False
          and 'id="cd-scatter"' not in dhtml and 'Not shown.' in dhtml)

    # ------------------------------------------------------------------
    # 5-6. at most six charts; titles state the finding
    # ------------------------------------------------------------------
    check('5 at most 6 charts and maps on the page',
          html.count('class="cd-chart') <= 6, html.count('class="cd-chart'))
    bar_title = re.search(r'<h3 id="cd-bar-title">(.*?)</h3>', html)
    check('6 the ranking title states the finding',
          bar_title and bar_title.group(1) == '2 municipalities below 85% survival',
          bar_title.group(1) if bar_title else '')
    gauge_title = re.search(r'<h3 id="cd-gauge-title">(.*?)</h3>', html)
    check('6 the gauge title states the finding',
          gauge_title and gauge_title.group(1).startswith('Survival is'))

    # ------------------------------------------------------------------
    # 7. an office with no sites
    # ------------------------------------------------------------------
    ahtml = alaminos.get('/dashboard').get_data(as_text=True)
    check('7 an office with no sites gets a page, not an error',
          'class="cd-story"' in ahtml)
    check('7 the story says there are no sites',
          'No official sites in CENRO Alaminos yet.' in ahtml)
    check('7 every chart shows its empty state',
          'No contract years recorded yet.' in ahtml
          and 'No monitoring reports yet' in ahtml
          and ahtml.count('No municipalities with sites yet.') == 2
          and 'Not shown.' in ahtml)

    # ------------------------------------------------------------------
    # 8. the action strip
    # ------------------------------------------------------------------
    waiting = (Request.query.join(Location, Request.location_id == Location.location_id)
               .filter(Request.status.in_(['Submitted', 'Under Review']),
                       Location.municipality.in_(list(urdaneta_list))).count())
    check('8 the action strip counts requests in the CENRO area',
          f'<strong>{waiting}</strong> request' in html, waiting)
    check('8 the CENRO admin can open the request queue from the strip',
          'href="/admin/requests"' in html)

    # ------------------------------------------------------------------
    # 9. simulated data
    # ------------------------------------------------------------------
    banner = 'Includes simulated data for districts without real records.'
    check('9 the Urdaneta CENRO dashboard has no simulated rows',
          not any(m.get('simulated') for m in cd['munis']))
    check('9 the Urdaneta CENRO dashboard shows no simulated banner',
          banner not in html)
    phtml = provincial.get('/dashboard').get_data(as_text=True)
    pcd2 = page_data(phtml)
    pm = {m['municipality']: m for m in pcd2['munis']}
    check('9 the provincial page shows the banner', banner in phtml)
    check('9 the simulated municipality is drawn and flagged',
          pm.get('Mangaldan', {}).get('simulated') is True)
    check('9 the map labels simulated municipalities',
          'Simulated (' in phtml)
    check('9 a simulated municipality is never judged',
          pm.get('Mangaldan', {}).get('judged') is False)
    pstory = re.search(r'<p class="cd-story">(.*?)</p>', phtml, re.S).group(1)
    check('9 the story ignores simulated data',
          'Mangaldan' not in pstory
          and '2 of 7 municipalities with enough data are below' in pstory,
          pstory)
    check('9 the ranking leaves simulated municipalities out',
          'Mangaldan' not in {m['municipality'] for m in pcd2['ranked']})
    check('9 the scatter leaves simulated municipalities out',
          'Mangaldan' not in {p['label'] for p in pcd2['scatter']['points']})
    check('9 simulated sites are counted apart, labelled',
          'Simulated sites' in phtml)

    # the GIS map draws simulated municipalities dashed, labelled
    def map_simulated(client):
        g = client.get('/gis-map').get_data(as_text=True)
        m = re.search(r'id="map-files">(.*?)</script>', g, re.S)
        return json.loads(m.group(1)).get('simulated') if m else None
    check('9 the provincial GIS map marks the simulated municipality',
          map_simulated(provincial) == ['Mangaldan'])
    check('9 the Urdaneta GIS map marks nothing simulated',
          map_simulated(urdaneta) == [])
    check('9 the GIS map styles and labels simulated municipalities',
          '" (Simulated)"' in provincial.get('/gis-map').get_data(as_text=True))

    # mixed municipality: flagged, real values only, labelled
    cal_row = pm.get('Calasiao', {})
    check('10 a mixed municipality is flagged mixed, not simulated',
          cal_row.get('mixed') is True and cal_row.get('simulated') is False)
    check('10 its survival uses real sites only (90%, not pulled down)',
          cal_row.get('survival') == 90.0, cal_row.get('survival'))
    check('10 its area uses real sites only (30 ha, not 1,030)',
          cal_row.get('area') == 30.0, cal_row.get('area'))
    check('11 the seedlings tile says contracted, with no percentage',
          'Seedlings (contracted)' in phtml and 'planted against target' not in phtml)
    check('11 no Delivery tile while no site visit has a field count',
          '>Delivery<' not in phtml)
    check('11 Delivery is no longer a map metric',
          'data-metric="delivery"' not in phtml and 'delivery' not in pcd2.get('mapTitles', {}))
    check('10 the dashboard map labels it "(includes simulated)"',
          '(includes simulated)' in phtml)
    g = provincial.get('/gis-map').get_data(as_text=True)
    files = json.loads(re.search(r'id="map-files">(.*?)</script>', g, re.S).group(1))
    check('10 the GIS map lists it as mixed, not simulated',
          files.get('mixed') == ['Calasiao'] and 'Calasiao' not in files.get('simulated'))
    check('10 the GIS map labels it "(includes simulated)"',
          '(includes simulated)' in g)

    # an approved visit with a field count turns the Delivery tile on
    alcala = Site.query.filter_by(site_name='Alcala site 0').first()
    db.session.add(SiteVisit(site_id=alcala.site_id, user_id=s.officer_id,
                             visit_date=date(2025, 1, 10),
                             visit_type='Planting confirmation', finding='Suitable',
                             status='Approved', seedlings_planted=450))
    db.session.commit()
    uhtml = urdaneta.get('/dashboard').get_data(as_text=True)
    check('11 Delivery appears once a field count exists, from field counts only',
          '>Delivery<' in uhtml and '>45%<' in uhtml and 'field counts, 1 site' in uhtml)

    # what the real scatter says, for the report
    print()
    print('NOTE scatter on the test data:', sc['title'], '| r =', sc['r'])

    run_drill(app, s, org_id, urdaneta, provincial)


TILE_RE = (r'<a class="dash-tile[^"]*" href="([^"]+)"[^>]*>\s*'
           r'<span class="dash-tile-label">{}</span>\s*'
           r'<span class="dash-tile-value">([^<]+)</span>')


def tile(html, label):
    """(href, value) of a KPI tile, or (None, None)."""
    m = re.search(TILE_RE.format(re.escape(label)), html)
    return (m.group(1).replace('&amp;', '&'), m.group(2)) if m else (None, None)


def num(value):
    return int(re.sub(r'[^0-9]', '', value or '') or -1)


def jumps_to(html, href):
    """The tile's target section is on this page."""
    return bool(href and href.startswith('#')
                and f'id="{href[1:]}"' in html)


def section_fig(html, key):
    m = re.search(rf'<strong data-fig="{key}">([^<]+)</strong>', html)
    return m.group(1) if m else None


def check_section_matches_tiles(who, html):
    """Each tile's number equals what its map section shows."""
    for label, key in (('Sites', 'sites'), ('Seedlings (contracted)', 'seedlings'),
                       ('Survival', 'survival')):
        value = tile(html, label)[1]
        shown = section_fig(html, key)
        check(f'5 {who}: {label} tile equals its section',
              value is not None and value.strip() == (shown or '').strip(),
              f'{value} vs {shown}')


def run_drill(app, s, org_id, urdaneta, provincial):
    """Step 5: tiles stay on the dashboard and jump to their section."""
    want = {'Official sites': '#cd-map-section', 'Area': '#cd-years-chart',
            'Seedlings (contracted)': '#cd-map-section'}
    for name, client in (('CENRO', urdaneta), ('provincial', provincial)):
        html = client.get('/dashboard').get_data(as_text=True)
        for label, target in want.items():
            href, _ = tile(html, label)
            check(f'5 {name}: {label} jumps to {target}',
                  href == target and jumps_to(html, href), href)
        check(f'5 {name}: no tile leaves the page',
              all(h.startswith('#') for h in
                  re.findall(r'<a class="dash-tile[^"]*" href="([^"]+)"', html)))
        check(f'5 {name}: Seedlings tile selects the Seedlings map metric',
              'data-metric="seedlings"' in html
              and '<button type="button" data-metric="seedlings"' in html)
        cd = page_data(html)
        real = sum(m['seedlings'] or 0 for m in cd['munis'] if not m['simulated'])
        check(f'5 {name}: map seedlings add up to the Seedlings tile',
              real == num(tile(html, 'Seedlings (contracted)')[1]),
              f"{real} vs {tile(html, 'Seedlings (contracted)')[1]}")
        check(f'5 {name}: Delivery tile, when shown, is plain (no link)',
              tile(html, 'Delivery')[0] is None
              and not re.search(r'href="#cd-gauge', html))
        check(f'5 {name}: waiting chips still link to queues',
              not re.search(r'<a class="cd-action[^"]*"\s*>', html))
    phtml = provincial.get('/dashboard').get_data(as_text=True)
    href, _ = tile(phtml, 'Simulated sites')
    check('5 provincial: Simulated jumps to the map',
          href == '#cd-map-section' and jumps_to(phtml, href), href)
    uhtml = urdaneta.get('/dashboard').get_data(as_text=True)
    check('5 CENRO: no Simulated tile', tile(uhtml, 'Simulated sites')[0] is None)

    citizen = db.session.get(User, s.citizen_id)
    citizen.organization_id, citizen.org_role, citizen.org_status = org_id, 'member', 'active'
    # a barangay with real org sites, so every member check has numbers
    home = (Site.query.filter_by(organization_id=org_id, is_simulated=False)
            .first().location_id)
    citizen.location_id = home
    db.session.commit()
    member = app.test_client()
    base.login(member, s.citizen_id, s.citizen_name, 'normal_user', None)
    mhtml = member.get('/dashboard').get_data(as_text=True)
    check('5 member: every tile jumps to a section on the page',
          all(jumps_to(mhtml, tile(mhtml, l)[0])
              for l in ('Sites', 'Seedlings (contracted)', 'Survival')))
    check('5 org member: map section is the organization sites',
          "Your organization&#39;s sites" in mhtml
          or "Your organization's sites" in mhtml)
    check_section_matches_tiles('org member', mhtml)
    dm = re.search(r'window.DASH_MAP = (\{.*?\});', mhtml, re.S)
    pts = json.loads(dm.group(1))['points'] if dm else []
    check('5 org member: own-barangay sites are marked, with a legend',
          any(p.get('home') for p in pts) and 'Your barangay' in mhtml
          or not pts, len(pts))
    check('5 org member: the map never uses orange',
          '#f59e0b' not in mhtml and '#ea580c' not in mhtml)
    check('5 org member: the org has sites to show',
          num(tile(mhtml, 'Sites')[1]) > 0, tile(mhtml, 'Sites')[1])

    citizen.org_status = 'pending'
    db.session.commit()
    phtml = member.get('/dashboard').get_data(as_text=True)
    check('5 pending member: map section is the barangay',
          'Sites in your barangay' in phtml)
    check_section_matches_tiles('pending member', phtml)
    citizen.organization_id = citizen.org_role = citizen.org_status = None
    db.session.commit()
    ihtml = member.get('/dashboard').get_data(as_text=True)
    check('5 individual: map section is the barangay',
          'Sites in your barangay' in ihtml)
    check_section_matches_tiles('individual', ihtml)
    citizen.organization_id, citizen.org_role, citizen.org_status = org_id, 'member', 'active'
    db.session.commit()

    citizen.org_role = 'leader'
    db.session.commit()
    lhtml = member.get('/dashboard').get_data(as_text=True)
    check('5 leader: tiles jump to org sites, years and survival',
          [tile(lhtml, l)[0] for l in ('Sites', 'Seedlings (contracted)', 'Survival')]
          == ['#dash-org-sites', '#dash-years', '#dash-survival']
          and all(f'id="{x}"' in lhtml for x in ('dash-org-sites', 'dash-years', 'dash-survival')))
    citizen.organization_id = citizen.org_role = citizen.org_status = None
    db.session.commit()

    officer = app.test_client()
    base.login(officer, s.officer_id, s.officer_name, 'field_officer', 'Urdaneta City')
    ohtml = officer.get('/dashboard').get_data(as_text=True)
    check('5 officer: every tile jumps to the to-do list',
          all(tile(ohtml, l)[0] == '#dash-todo' for l in
              ('Visits this week', 'Overdue', 'Awaiting approval'))
          and jumps_to(ohtml, '#dash-todo'))


def run_years():
    """Step 4: hectares per year, every year, trend title."""
    from app.services.cenro_dashboard import hectares_per_year
    years, _ = hectares_per_year({2017: 940.0, 2020: 50.0}, current_year=2026)
    check('years: every year from first to current',
          [y['year'] for y in years] == list(range(2017, 2027)))
    check('years: empty year is 0', years[1]['area'] == 0)
    check('years: current year says (to date)',
          years[-1]['label'] == '2026 (to date)' and years[0]['label'] == '2017')
    _, t = hectares_per_year({2017: 940.0, 2025: 120.0, 2026: 999.0}, 2026)
    check('years: fell title uses peak and latest full year',
          t == 'Contracting fell from 940 ha in 2017 to 120 ha in 2025', t)
    _, t = hectares_per_year({2023: 10.0, 2025: 300.0}, 2026)
    check('years: rose title', t.startswith('Contracting rose from 10 ha in 2023'), t)
    _, t = hectares_per_year({2023: 100.0, 2024: 95.0, 2025: 100.0}, 2026)
    check('years: flat title', 'held steady' in t, t)
    _, t = hectares_per_year({2026: 50.0}, 2026)
    check('years: too short title', t == 'Too few full years to show a trend', t)


def run_roles():
    """Step 6: role labels."""
    from app.utils.roles import org_position_label as o, system_role_label as r
    check('roles: system labels',
          [r(None), r('normal_user'), r('field_officer'), r('admin', 'X'),
           r('admin'), r('superadmin')] ==
          ['Guest', 'User', 'Field Officer', 'CENRO Administrator',
           'Provincial Administrator', 'System Administrator'])
    org = 'San Vicente Farmers Assoc.'
    check('roles: positions carry the org name',
          [o('normal_user', 'leader', 'active', org),
           o('normal_user', 'member', 'active', org),
           o('normal_user', 'member', 'pending', org)] ==
          [f'Partner Org Leader · {org}', f'Partner Org Member · {org}',
           f'Pending Member · {org}'])
    check('roles: no org is Individual', o('normal_user', None, None) == 'Individual')
    check('roles: staff have no org position', o('admin', 'leader', 'active', 'X') is None)


def main():
    app = base.create_app()
    app.config['TESTING'] = True
    app.config['MAIL_SERVER'] = ''
    app.config['WTF_CSRF_ENABLED'] = False

    try:
        with app.app_context():
            db.create_all()
            run(app)
            run_years()
            run_roles()
    finally:
        base.shutil.rmtree(base.TMPDIR, ignore_errors=True)

    passed = sum(r['ok'] for r in RESULTS)
    print()
    print(f"{passed} of {len(RESULTS)} passed")
    return 0 if RESULTS and passed == len(RESULTS) else 1


if __name__ == '__main__':
    sys.exit(main())

