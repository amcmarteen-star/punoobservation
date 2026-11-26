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
    Location, Organization, ReforestationRecord, Request, Site, TreeSpecie,
    User,
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
    check('10 its delivery uses real sites only (90%)',
          cal_row.get('achievement') == 90.0, cal_row.get('achievement'))
    check('10 the dashboard map labels it "(includes simulated)"',
          '(includes simulated)' in phtml)
    g = provincial.get('/gis-map').get_data(as_text=True)
    files = json.loads(re.search(r'id="map-files">(.*?)</script>', g, re.S).group(1))
    check('10 the GIS map lists it as mixed, not simulated',
          files.get('mixed') == ['Calasiao'] and 'Calasiao' not in files.get('simulated'))
    check('10 the GIS map labels it "(includes simulated)"',
          '(includes simulated)' in g)

    # what the real scatter says, for the report
    print()
    print('NOTE scatter on the test data:', sc['title'], '| r =', sc['r'])


def main():
    app = base.create_app()
    app.config['TESTING'] = True
    app.config['MAIL_SERVER'] = ''
    app.config['WTF_CSRF_ENABLED'] = False

    try:
        with app.app_context():
            db.create_all()
            run(app)
    finally:
        base.shutil.rmtree(base.TMPDIR, ignore_errors=True)

    passed = sum(r['ok'] for r in RESULTS)
    print()
    print(f"{passed} of {len(RESULTS)} passed")
    return 0 if RESULTS and passed == len(RESULTS) else 1


if __name__ == '__main__':
    sys.exit(main())
