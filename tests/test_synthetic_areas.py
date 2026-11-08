"""
Synthetic site areas test.

Runs the area placement, the script and the map endpoints against a
throwaway SQLite database seeded with synthetic data. Nothing touches the
production Postgres: DATABASE_URL is overwritten before the app package is
imported. The barangay and district outlines are the real map files.

WHAT IS UNDER TEST
- each area has the site's hectares, an irregular outline, and lies
  wholly inside its barangay and inside Eastern Pangasinan
- NO TWO SITES OVERLAP, even in a crowded barangay, and no area lands on
  a published boundary or a requester's proposed area
- a barangay too small for a site shrinks the area and says so
- the same seed gives the same areas; re-running replaces, never adds
- --site keeps the other sites' areas and avoids them
- sites that already have a position (published boundary, requester's
  pin) get no area; sites outside Eastern Pangasinan or with no area are
  skipped
- site, location and planting records are never changed
- every site gets its own tree marker, labelled approximate
- /api/approximate-areas and /api/site-areas serve the shapes

RUN

    python tests/test_synthetic_areas.py

Exit code 0 when every check passes, 1 otherwise.
"""

import json
import os
import shutil
import sys
import tempfile
from datetime import date

# --- isolate from the real database BEFORE app.config is imported ------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TMPDIR = tempfile.mkdtemp(prefix='puno_areas_test_')
DB_FILE = os.path.join(TMPDIR, 'areas_test.db').replace('\\', '/')
os.environ['DATABASE_URL'] = 'sqlite:///' + DB_FILE
os.environ['SECRET_KEY'] = 'test-only-not-a-secret'

from app import create_app                              # noqa: E402
from app.extensions import db                           # noqa: E402
from app.models import (                                # noqa: E402
    Location, Organization, ReforestationRecord, Request, Site,
    SyntheticSiteArea, TreeSpecie, User,
)
from app.services.request_site import barangay_point    # noqa: E402
from app.services.synthetic_areas import (              # noqa: E402
    AREA_VERTICES, DEFAULT_SEED, area_outline, area_problems,
    barangay_index, place_areas,
)
from app.utils.jurisdiction import place_key            # noqa: E402
from scripts.tools.make_synthetic_areas import run      # noqa: E402

STATIC = os.path.join(ROOT, 'app', 'static')
RESULTS = []


def check(group, name, ok, detail=''):
    RESULTS.append((group, name, bool(ok), detail))
    return bool(ok)


def quiet(*_args, **_kw):
    """Swallows the script's summary printout."""


def square(lat, lng, half_deg):
    ring = [[lng - half_deg, lat - half_deg], [lng + half_deg, lat - half_deg],
            [lng + half_deg, lat + half_deg], [lng - half_deg, lat + half_deg],
            [lng - half_deg, lat - half_deg]]
    return {"type": "Polygon", "coordinates": [ring]}


def no_overlaps(shapes, barangay, outline):
    """Problems found when each shape is checked against all the others."""
    found = []
    for i, s in enumerate(shapes):
        p = area_problems(s, barangay, outline, shapes[:i] + shapes[i + 1:])
        if p:
            found.append(p)
    return found


# ======================================================================
# 1. placement alone
# ======================================================================

def test_placement(outline, diaz, bacag, carmen):
    g = 'placement'
    sites = [(1, 50), (2, 40), (3, 12), (4, 8), (5, 30), (6, 2)]
    r = place_areas(diaz, sites, DEFAULT_SEED, outline)
    check(g, 'six sites in one barangay: six areas',
          all(r[s] is not None for s, _ in sites))
    check(g, 'each area has its site\'s hectares',
          all(abs(r[s]['area_ha'] - ha) < 0.05 for s, ha in sites),
          str({s: r[s]['area_ha'] for s, _ in sites}))
    check(g, f'each area is an irregular {AREA_VERTICES}-corner outline',
          all(len(r[s]['geojson']['coordinates'][0]) == AREA_VERTICES + 1
              for s, _ in sites))
    shapes = [r[s]['geojson'] for s, _ in sites]
    probs = no_overlaps(shapes, diaz, outline)
    check(g, 'all inside the barangay and the area, none overlapping',
          not probs, str(probs))
    check(g, 'same seed: same areas',
          place_areas(diaz, sites, DEFAULT_SEED, outline) == r)
    check(g, 'another seed: different areas',
          place_areas(diaz, sites, 7, outline) != r)

    crowd = [(30 + i, 25) for i in range(8)]
    rc = place_areas(bacag, crowd, DEFAULT_SEED, outline)
    shapes = [rc[s]['geojson'] for s, _ in crowd if rc[s]]
    probs = no_overlaps(shapes, bacag, outline)
    check(g, 'crowded barangay (8 x 25 ha): still no overlap',
          len(shapes) == 8 and not probs, f'{len(shapes)} placed, {probs}')

    lat, lng = barangay_point(bacag)
    blocker = square(lat, lng, 0.004)
    rb = place_areas(bacag, [(40, 20), (41, 10)], DEFAULT_SEED, outline,
                     obstacles=[blocker])
    shapes = [rb[s]['geojson'] for s in (40, 41)]
    check(g, 'areas keep off an existing boundary',
          all(not area_problems(s, bacag, outline, [blocker]) for s in shapes))

    big = place_areas(carmen, [(9, 500)], DEFAULT_SEED, outline)[9]
    check(g, '500 ha in a small barangay: shrinks and says so',
          big is not None and big['area_ha'] < 500
          and any('shrunk' in e for e in big['eased']), str(big and big['eased']))
    check(g, 'shrunk area still wholly inside',
          big is not None and not area_problems(big['geojson'], carmen, outline))

    sea = square(16.2, 119.5, 0.02)
    check(g, 'barangay outside Eastern Pangasinan: no area',
          place_areas(sea, [(10, 5)], DEFAULT_SEED, outline)[10] is None)


# ======================================================================
# 2. the script and the endpoints, on a synthetic database
# ======================================================================

def seed_db(bacag):
    org = Organization(organization_name='Synthetic PO', organization_type='POs')
    db.session.add(org)
    loc_u = Location(psgc_code='SYN-URD-001', region='Region I',
                     province='Pangasinan', municipality='Villasis',
                     barangay='Bacag', latitude=15.9008, longitude=120.5893,
                     elevation_m=32.0)
    loc_d = Location(psgc_code='SYN-DAG-001', region='Region I',
                     province='Pangasinan', municipality='Dagupan City',
                     barangay='Bonuan', latitude=16.05, longitude=120.34,
                     elevation_m=5.0)
    sp = TreeSpecie(specie_name='Narra', scientific_name='Pterocarpus indicus')
    user = User(username='syn_user', email_address='syn@synthetic.test',
                role='normal_user', is_active=True, must_change_password=False)
    user.set_password('synthetic-password')
    db.session.add_all([loc_u, loc_d, sp, user])
    db.session.flush()

    lat, lng = barangay_point(bacag)
    boundary = square(lat, lng, 0.0008)
    proposed = square(lat + 0.004, lng + 0.004, 0.0006)
    req = Request(user_id=user.user_id, location_id=loc_u.location_id,
                  request_type='Tree Planting', status='Approved',
                  latitude=lat + 0.004, longitude=lng + 0.004,
                  boundary_geojson=json.dumps(proposed))
    db.session.add(req)
    db.session.flush()

    def mk(name, loc, ha, **kw):
        s = Site(location_id=loc.location_id,
                 organization_id=org.organization_id, site_name=name,
                 area_size_ha=ha, date_established=date(2022, 1, 1),
                 site_status='Active', **kw)
        db.session.add(s)
        return s

    sites = {
        'a': mk('Site A', loc_u, 5.0, cenro='Urdaneta City'),
        'e': mk('Site E', loc_u, 3.0, cenro='Urdaneta City'),
        'b': mk('Site B - published boundary', loc_u, 3.0, cenro='Urdaneta City',
                boundary_geojson=json.dumps(boundary), boundary_published=True,
                boundary_area_ha=3.1),
        'r': mk('Site R - from a request', loc_u, 2.0, cenro='Urdaneta City',
                source_request_id=req.request_id),
        'c': mk('Site C - Dagupan', loc_d, 4.0, cenro='Dagupan'),
        'd': mk('Site D - no area', loc_u, 0.0, cenro='Urdaneta City'),
    }
    db.session.flush()
    db.session.add(ReforestationRecord(
        site_id=sites['a'].site_id, tree_id=sp.tree_id,
        date_planted=date(2022, 7, 1), target_quantity=5000,
        actual_quantity_planted=4800))
    db.session.commit()
    return {k: v.site_id for k, v in sites.items()}, boundary, proposed


def snapshot():
    rows = []
    for model in (Site, Location, ReforestationRecord, Request):
        for r in model.query.order_by(*model.__table__.primary_key.columns):
            rows.append(tuple(getattr(r, c.name) for c in model.__table__.columns))
    return rows


def stored(site_id):
    row = SyntheticSiteArea.query.filter_by(site_id=site_id).first()
    return None if row is None else (row.geometry_geojson, row.area_ha,
                                     row.is_synthetic, row.seed)


def test_script_and_api(app, outline, bacag):
    g = 'script'
    ids, boundary, proposed = seed_db(bacag)
    before = snapshot()

    run(dry_run=True, static_dir=STATIC, out=quiet)
    check(g, 'dry run saves nothing', SyntheticSiteArea.query.count() == 0)

    s = run(static_dir=STATIC, out=quiet)
    a, e = stored(ids['a']), stored(ids['e'])
    check(g, 'areas for sites A and E', a is not None and e is not None)
    check(g, 'area A is 5 ha, marked synthetic, with the seed',
          a and abs(a[1] - 5.0) < 0.05 and a[2] is True and a[3] == DEFAULT_SEED)
    shapes = [json.loads(a[0]), json.loads(e[0]), boundary, proposed]
    check(g, 'A and E inside Bacag, apart, and off B and R\'s shapes',
          not area_problems(shapes[0], bacag, outline, shapes[1:])
          and not area_problems(shapes[1], bacag, outline,
                                [shapes[0], boundary, proposed]))
    positioned = dict(s['positioned'])
    check(g, 'published-boundary site and request site get no area',
          stored(ids['b']) is None and stored(ids['r']) is None
          and any('Site B' in k for k in positioned)
          and any('Site R' in k for k in positioned), str(positioned))
    skipped = dict(s['skipped'])
    check(g, 'Dagupan site skipped as outside Eastern Pangasinan',
          any('Dagupan' in k and 'outside Eastern Pangasinan' in v
              for k, v in skipped.items()), str(skipped))
    check(g, 'site with 0 ha skipped',
          any('no area' in k and 'hectare' in v for k, v in skipped.items()))
    check(g, 'no check failures', not s['failures'], str(s['failures']))

    run(static_dir=STATIC, out=quiet)
    check(g, 're-run: same areas, none added',
          stored(ids['a']) == a and stored(ids['e']) == e
          and SyntheticSiteArea.query.count() == 2)

    run(site_ids=[ids['e']], seed=7, static_dir=STATIC, out=quiet)
    e7 = stored(ids['e'])
    check(g, '--site with another seed: only that site moves',
          stored(ids['a']) == a and e7 is not None and e7 != e)
    check(g, '--site: the moved area still avoids every other site',
          not area_problems(json.loads(e7[0]), bacag, outline,
                            [json.loads(a[0]), boundary, proposed]))
    run(static_dir=STATIC, out=quiet)       # back to the default layout

    check(g, 'site, location, planting and request rows unchanged',
          snapshot() == before)

    # --- endpoints -----------------------------------------------------
    g = 'api'
    client = app.test_client()

    approx = client.get('/api/approximate-areas').get_json()
    by_id = {b['site_id']: b for b in approx['boundaries']}
    check(g, 'approximate areas: A and E only',
          approx['count'] == 2 and set(by_id) == {ids['a'], ids['e']},
          str(sorted(by_id)))
    check(g, 'approximate areas carry the note',
          'synthetic' in approx['note'])

    geo = client.get('/api/sites-geo').get_json()
    markers = {m['sites'][0]['site_id']: m for m in geo['barangays']
               if m['exact']}
    check(g, 'A and E each have their own tree, marked approximate',
          markers.get(ids['a'], {}).get('approximate') is True
          and markers.get(ids['e'], {}).get('approximate') is True
          and markers[ids['a']]['site_count'] == 1)
    check(g, 'B\'s tree is at its real boundary, not approximate',
          markers.get(ids['b'], {}).get('approximate') is False)

    muni = client.get('/api/municipality/Villasis').get_json()
    cards = {s['site_id']: s for s in muni.get('sites', [])}
    check(g, 'site list: Locate goes to A\'s approximate area',
          cards.get(ids['a'], {}).get('approximate') is True
          and cards[ids['a']]['exact'] is False, str(cards.get(ids['a'])))

    areas = client.get('/api/site-areas').get_json()
    by_id = {f['properties']['site_id']: f['properties'] for f in areas['features']}
    check(g, 'site areas view: A and E synthetic, B surveyed',
          by_id.get(ids['a'], {}).get('synthetic') is True
          and by_id.get(ids['e'], {}).get('synthetic') is True
          and by_id.get(ids['b'], {}).get('synthetic') is False,
          str(sorted(by_id)))
    check(g, 'seedlings value is the site\'s planted total',
          by_id[ids['a']]['value'] == 4800 and by_id[ids['e']]['value'] == 0)
    check(g, 'filter by barangay with no match: none',
          client.get('/api/site-areas?barangay=Nowhere').get_json()['sites'] == 0)
    check(g, 'unknown metric refused',
          client.get('/api/site-areas?metric=bogus').status_code == 400)


# ======================================================================

def main():
    outline = area_outline(STATIC)
    index = barangay_index(STATIC)
    bacag = index[place_key('Villasis', 'Bacag')]
    diaz = index[place_key('Umingan', 'Diaz')]
    carmen = index[place_key('Rosales', 'Carmen East')]

    app = create_app()
    app.config['TESTING'] = True
    try:
        with app.app_context():
            db.create_all()
            test_placement(outline, diaz, bacag, carmen)
            test_script_and_api(app, outline, bacag)
            db.session.remove()
            db.engine.dispose()
    finally:
        shutil.rmtree(TMPDIR, ignore_errors=True)

    failed = [r for r in RESULTS if not r[2]]
    group = None
    for grp, name, ok, detail in RESULTS:
        if grp != group:
            print(f'\n[{grp}]')
            group = grp
        print(f"  {'PASS' if ok else 'FAIL'}  {name}"
              + (f'  ({detail})' if detail and not ok else ''))
    print(f'\n{len(RESULTS) - len(failed)} of {len(RESULTS)} checks passed.')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
