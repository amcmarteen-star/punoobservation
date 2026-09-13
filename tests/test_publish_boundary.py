"""
Publish-boundary boundary test.

Runs the real Flask routes against a throwaway SQLite database seeded
with synthetic data. Nothing touches the production Postgres: the
DATABASE_URL environment variable is overwritten before the app package
is imported.

WHAT IS UNDER TEST

A captured site boundary must cross two gates before the public map
shows it:

    field officer captures corners
        -> CENRO admin approves the report      (approval_status)
        -> provincial admin publishes it        (publication_status)
        -> /api/published-boundaries serves it

The "publish boundary" is the line between a polygon that merely exists
in the database and a polygon that is an official record on the map.
This script tries to cross that line every wrong way it can, then
crosses it the right way and confirms the map changes.

RUN

    python tests/test_publish_boundary.py

Exit code 0 when every check passes, 1 otherwise.
"""

import os
import sys
import json
import shutil
import tempfile
from datetime import date, datetime

# --- isolate from the real database BEFORE app.config is imported ------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TMPDIR = tempfile.mkdtemp(prefix='puno_boundary_test_')
DB_FILE = os.path.join(TMPDIR, 'boundary_test.db').replace('\\', '/')
os.environ['DATABASE_URL'] = 'sqlite:///' + DB_FILE
os.environ['SECRET_KEY'] = 'test-only-not-a-secret'

from app import create_app                              # noqa: E402
from app.extensions import db                           # noqa: E402
from app.models import (                                # noqa: E402
    AuditLog, Location, MonitoringReport, Notification, Organization,
    ReforestationRecord, Site, TreeSpecie, User,
)
from app.services.monitoring import build_boundary      # noqa: E402


# ======================================================================
# result recorder
# ======================================================================

RESULTS = []
NOTES = []


def check(group, name, ok, detail=''):
    RESULTS.append({'group': group, 'name': name,
                    'ok': bool(ok), 'detail': detail})
    return bool(ok)


def note(text):
    NOTES.append(text)


# ======================================================================
# synthetic geography
# ======================================================================

def square_corners(cx, cy, half_deg):
    """Four GPS corners around a centre point, in (lon, lat) order."""
    return [
        (cx - half_deg, cy - half_deg),
        (cx + half_deg, cy - half_deg),
        (cx + half_deg, cy + half_deg),
        (cx - half_deg, cy + half_deg),
    ]


def synthetic_boundary(cx, cy, half_deg, contract_ha):
    """
    Build a boundary through the real service, exactly as a submitted
    report would. Returns the dict build_boundary() produces.
    """
    b = build_boundary(square_corners(cx, cy, half_deg), contract_ha)
    if not b['ok']:
        raise RuntimeError('synthetic boundary failed to build: '
                           + str(b['reason']))
    return b


# ======================================================================
# session and request helpers
# ======================================================================

def login(client, uid, username, role, cenro):
    with client.session_transaction() as s:
        s.clear()
        s['user_id'] = uid
        s['username'] = username
        s['role'] = role
        s['cenro'] = cenro
        s['must_change_password'] = False


def logout(client):
    with client.session_transaction() as s:
        s.clear()


def fresh():
    """Drop the outer session so the next query re-reads committed rows."""
    db.session.remove()


def get_site(site_id):
    fresh()
    return db.session.get(Site, site_id)


def get_report(report_id):
    fresh()
    return db.session.get(MonitoringReport, report_id)


def api_boundaries(client):
    r = client.get('/api/published-boundaries')
    if r.status_code != 200:
        return None
    return json.loads(r.data.decode('utf-8'))


def site_ids_in_api(client):
    payload = api_boundaries(client)
    if payload is None:
        return set()
    return {b['site_id'] for b in payload['boundaries']}


def publish_post(client, report_id, action, note_text=''):
    return client.post(
        '/admin/publications/%d/publish' % report_id,
        data={'action': action, 'publication_note': note_text},
        follow_redirects=False,
    )


def review_post(client, report_id, status, note_text=''):
    return client.post(
        '/admin/reports/%d/review' % report_id,
        data={'status': status, 'review_note': note_text},
        follow_redirects=False,
    )


# ======================================================================
# seed
# ======================================================================

class Seed:
    pass


def seed():
    """Synthetic province: two CENROs, three sites, five reports."""
    s = Seed()

    org = Organization(organization_name='Synthetic Peoples Organization',
                       organization_type='POs')
    db.session.add(org)

    loc_u = Location(psgc_code='SYN-URD-001', region='Region I',
                     province='Pangasinan', municipality='Villasis',
                     barangay='Bacag', latitude=15.9008,
                     longitude=120.5893, elevation_m=32.0)
    loc_d = Location(psgc_code='SYN-DAG-001', region='Region I',
                     province='Pangasinan', municipality='Dagupan City',
                     barangay='Bonuan', latitude=16.0500,
                     longitude=120.3400, elevation_m=5.0)
    db.session.add_all([loc_u, loc_d])

    specie = TreeSpecie(specie_name='Narra',
                        scientific_name='Pterocarpus indicus',
                        native_to='Philippines')
    db.session.add(specie)
    db.session.flush()

    # --- sites --------------------------------------------------------
    site_a = Site(location_id=loc_u.location_id,
                  organization_id=org.organization_id,
                  site_name='Synthetic Site A - Bacag',
                  site_code='SYN-A', area_size_ha=5.0,
                  date_established=date(2022, 1, 15),
                  cenro='Urdaneta City', penro='Pangasinan',
                  congressional_district='6')

    # Site B already carries a polygon written straight onto the site by
    # the submission route (dashboard.py: "only replace the stored site
    # boundary if there is none yet"). It has never been published, so
    # the map must not show it.
    b_pre = synthetic_boundary(120.5990, 15.9100, 0.0016, 3.0)
    site_b = Site(location_id=loc_u.location_id,
                  organization_id=org.organization_id,
                  site_name='Synthetic Site B - Bacag East',
                  site_code='SYN-B', area_size_ha=3.0,
                  date_established=date(2022, 3, 1),
                  cenro='Urdaneta City', penro='Pangasinan',
                  congressional_district='6',
                  boundary_geojson=b_pre['geojson'],
                  boundary_area_ha=b_pre['area_ha'])

    site_c = Site(location_id=loc_d.location_id,
                  organization_id=org.organization_id,
                  site_name='Synthetic Site C - Bonuan',
                  site_code='SYN-C', area_size_ha=4.0,
                  date_established=date(2022, 5, 10),
                  cenro='Dagupan', penro='Pangasinan',
                  congressional_district='4')
    db.session.add_all([site_a, site_b, site_c])
    db.session.flush()

    # --- users --------------------------------------------------------
    def mk(username, role, cenro):
        u = User(username=username,
                 email_address=username + '@synthetic.test',
                 role=role, cenro=cenro, is_active=True,
                 must_change_password=False,
                 organization_id=org.organization_id)
        u.set_password('synthetic-password')
        db.session.add(u)
        return u

    s.officer = mk('syn_officer', 'field_officer', 'Urdaneta City')
    s.cenro_admin = mk('syn_cenro_urdaneta', 'admin', 'Urdaneta City')
    s.dagupan_admin = mk('syn_cenro_dagupan', 'admin', 'Dagupan')
    s.penro = mk('syn_penro', 'admin', None)            # provincial admin
    s.superadmin = mk('syn_superadmin', 'superadmin', None)
    s.citizen = mk('syn_citizen', 'normal_user', None)
    db.session.flush()

    # --- planting records ---------------------------------------------
    rec_a = ReforestationRecord(site_id=site_a.site_id,
                                tree_id=specie.tree_id,
                                date_planted=date(2022, 7, 1),
                                target_quantity=5000,
                                actual_quantity_planted=4800)
    rec_b = ReforestationRecord(site_id=site_b.site_id,
                                tree_id=specie.tree_id,
                                date_planted=date(2022, 8, 1),
                                target_quantity=3000,
                                actual_quantity_planted=2900)
    rec_c = ReforestationRecord(site_id=site_c.site_id,
                                tree_id=specie.tree_id,
                                date_planted=date(2022, 9, 1),
                                target_quantity=4000,
                                actual_quantity_planted=3900)
    db.session.add_all([rec_a, rec_b, rec_c])
    db.session.flush()

    # --- monitoring reports -------------------------------------------
    def mk_report(record, site, when, boundary, survival):
        r = MonitoringReport(
            record_id=record.record_id, site_id=site.site_id,
            user_id=s.officer.user_id, monitoring_date=when,
            survival_rate=survival, plots_recorded=5, plot_size_sqm=100.0,
            approval_status='Pending', publication_status='Not Applicable',
        )
        if boundary is not None:
            r.boundary_geojson = boundary['geojson']
            r.captured_area_ha = boundary['area_ha']
            r.area_difference_pct = boundary['difference_pct']
        db.session.add(r)
        return r

    b1 = synthetic_boundary(120.5893, 15.9008, 0.0021, 5.0)
    b2 = synthetic_boundary(120.5893, 15.9008, 0.0023, 5.0)   # re-survey
    b3 = synthetic_boundary(120.5990, 15.9100, 0.0016, 3.0)
    b5 = synthetic_boundary(120.3400, 16.0500, 0.0019, 4.0)

    s.rp1 = mk_report(rec_a, site_a, date(2023, 6, 10), b1, 88.5)
    s.rp2 = mk_report(rec_a, site_a, date(2024, 6, 12), b2, 84.0)
    s.rp3 = mk_report(rec_b, site_b, date(2024, 7, 5), b3, 76.0)
    s.rp4 = mk_report(rec_b, site_b, date(2024, 8, 8), None, 79.0)
    s.rp5 = mk_report(rec_c, site_c, date(2024, 7, 20), b5, 81.0)
    db.session.flush()

    # a report with no polygon, already approved: the "nothing to
    # publish" path
    s.rp4.approval_status = 'Approved'
    s.rp4.reviewed_by = s.cenro_admin.user_id
    s.rp4.date_reviewed = datetime(2024, 8, 9, 9, 0, 0)

    db.session.commit()

    s.site_a_id = site_a.site_id
    s.site_b_id = site_b.site_id
    s.site_c_id = site_c.site_id
    s.b1_geojson = b1['geojson']
    s.b2_geojson = b2['geojson']
    s.b1_area = b1['area_ha']
    s.b2_area = b2['area_ha']

    # collapse to plain ids so nothing goes stale later
    for attr in ('officer', 'cenro_admin', 'dagupan_admin', 'penro',
                 'superadmin', 'citizen'):
        u = getattr(s, attr)
        setattr(s, attr + '_id', u.user_id)
        setattr(s, attr + '_name', u.username)
    for attr in ('rp1', 'rp2', 'rp3', 'rp4', 'rp5'):
        setattr(s, attr + '_id', getattr(s, attr).report_id)

    return s


def as_penro(client, s):
    login(client, s.penro_id, s.penro_name, 'admin', None)


def as_cenro(client, s):
    login(client, s.cenro_admin_id, s.cenro_admin_name, 'admin',
          'Urdaneta City')


# ======================================================================
# scenarios
# ======================================================================

def run(app, s):
    client = app.test_client()

    # ------------------------------------------------------------------
    G = '1. Who may publish'
    # ------------------------------------------------------------------
    logout(client)
    r = publish_post(client, s.rp1_id, 'publish')
    check(G, 'anonymous POST publish is refused',
          r.status_code == 302
          and 'login' in (r.headers.get('Location') or ''),
          'status=%s location=%s' % (r.status_code,
                                     r.headers.get('Location')))
    check(G, 'anonymous attempt left the site unpublished',
          get_site(s.site_a_id).boundary_published is False)

    login(client, s.citizen_id, s.citizen_name, 'normal_user', None)
    r = publish_post(client, s.rp1_id, 'publish')
    check(G, 'normal_user POST publish is refused',
          r.status_code == 302
          and get_site(s.site_a_id).boundary_published is False,
          'status=%s location=%s' % (r.status_code,
                                     r.headers.get('Location')))

    login(client, s.officer_id, s.officer_name, 'field_officer',
          'Urdaneta City')
    r = publish_post(client, s.rp1_id, 'publish')
    check(G, 'field_officer POST publish is refused',
          r.status_code == 302
          and get_site(s.site_a_id).boundary_published is False,
          'status=%s location=%s' % (r.status_code,
                                     r.headers.get('Location')))

    as_cenro(client, s)
    r = client.get('/admin/publications')
    check(G, 'CENRO admin cannot open the publications page',
          r.status_code == 302,
          'status=%s location=%s' % (r.status_code,
                                     r.headers.get('Location')))
    r = publish_post(client, s.rp1_id, 'publish')
    check(G, 'CENRO admin POST publish is refused',
          get_site(s.site_a_id).boundary_published is False,
          'status=%s location=%s' % (r.status_code,
                                     r.headers.get('Location')))

    login(client, s.superadmin_id, s.superadmin_name, 'superadmin', None)
    r = client.get('/admin/publications')
    check(G, 'superadmin (MIS) cannot open the publications page',
          r.status_code == 302,
          'status=%s location=%s' % (r.status_code,
                                     r.headers.get('Location')))
    r = publish_post(client, s.rp1_id, 'publish')
    check(G, 'superadmin POST publish is refused',
          get_site(s.site_a_id).boundary_published is False,
          'status=%s location=%s' % (r.status_code,
                                     r.headers.get('Location')))

    as_penro(client, s)
    r = client.get('/admin/publications')
    check(G, 'provincial admin CAN open the publications page',
          r.status_code == 200, 'status=%s' % r.status_code)

    # ------------------------------------------------------------------
    G = '2. Approval gate'
    # ------------------------------------------------------------------
    as_penro(client, s)
    publish_post(client, s.rp1_id, 'publish')
    rp1 = get_report(s.rp1_id)
    check(G, 'a report not yet CENRO-approved cannot be published',
          get_site(s.site_a_id).boundary_published is False
          and rp1.publication_status != 'Published',
          'publication_status=%s' % rp1.publication_status)

    login(client, s.dagupan_admin_id, s.dagupan_admin_name, 'admin',
          'Dagupan')
    review_post(client, s.rp1_id, 'Approved')
    check(G, 'an out-of-jurisdiction CENRO admin cannot approve the report',
          get_report(s.rp1_id).approval_status == 'Pending',
          'approval_status=%s' % get_report(s.rp1_id).approval_status)

    as_cenro(client, s)
    review_post(client, s.rp1_id, 'Approved')
    rp1 = get_report(s.rp1_id)
    check(G, 'CENRO approval queues the boundary for publication',
          rp1.approval_status == 'Approved'
          and rp1.publication_status == 'Pending Publication',
          'approval=%s publication=%s' % (rp1.approval_status,
                                          rp1.publication_status))
    check(G, 'CENRO approval does NOT put the boundary on the map',
          get_site(s.site_a_id).boundary_published is False)

    as_penro(client, s)
    publish_post(client, s.rp1_id, 'delete')
    check(G, 'an unknown action is refused',
          get_site(s.site_a_id).boundary_published is False
          and get_report(s.rp1_id).publication_status
          == 'Pending Publication')

    publish_post(client, s.rp1_id, 'decline', '')
    check(G, 'declining without a reason is refused',
          get_report(s.rp1_id).publication_status == 'Pending Publication',
          'publication_status=%s'
          % get_report(s.rp1_id).publication_status)

    publish_post(client, s.rp4_id, 'publish')
    check(G, 'an approved report with no polygon cannot be published',
          get_site(s.site_b_id).boundary_published is False
          and get_report(s.rp4_id).publication_status != 'Published',
          'publication_status=%s'
          % get_report(s.rp4_id).publication_status)

    # ------------------------------------------------------------------
    G = '3. Map exposure before publication'
    # ------------------------------------------------------------------
    as_penro(client, s)
    payload = api_boundaries(client)
    check(G, '/api/published-boundaries responds', payload is not None)
    served_ids = {b['site_id'] for b in (payload or {'boundaries': []})['boundaries']}
    check(G, 'an approved-but-unpublished boundary is NOT served',
          s.site_a_id not in served_ids,
          'sites served: %s' % sorted(served_ids))
    check(G, 'a polygon stored on the site by the submission route is '
             'NOT served while unpublished',
          get_site(s.site_b_id).boundary_geojson is not None
          and s.site_b_id not in served_ids,
          'site B stored polygon present: %s'
          % bool(get_site(s.site_b_id).boundary_geojson))

    # ------------------------------------------------------------------
    G = '4. Publishing'
    # ------------------------------------------------------------------
    as_penro(client, s)
    publish_post(client, s.rp1_id, 'publish', 'Corners verified on site.')
    site_a = get_site(s.site_a_id)
    rp1 = get_report(s.rp1_id)

    check(G, 'site is marked published', site_a.boundary_published is True)
    check(G, 'the report polygon was copied onto the site',
          site_a.boundary_geojson == s.b1_geojson)
    check(G, 'the captured area was copied onto the site',
          site_a.boundary_area_ha == s.b1_area,
          'site=%s report=%s' % (site_a.boundary_area_ha, s.b1_area))
    check(G, 'the source report is recorded on the site',
          site_a.boundary_source_report_id == s.rp1_id)
    check(G, 'the publishing officer is recorded on the site',
          site_a.boundary_published_by == s.penro_id)
    check(G, 'publication timestamp is set',
          site_a.boundary_published_at is not None)
    check(G, "report publication_status is 'Published'",
          rp1.publication_status == 'Published', rp1.publication_status)
    check(G, 'the publication note is stored',
          rp1.publication_note == 'Corners verified on site.',
          str(rp1.publication_note))

    fresh()
    logs = (AuditLog.query
            .filter_by(action='publish_boundary', entity_id=s.site_a_id)
            .all())
    check(G, 'the publication is written to the audit log',
          len(logs) >= 1 and any(g.user_id == s.penro_id for g in logs),
          '%d publish_boundary row(s)' % len(logs))

    fresh()
    notes_officer = Notification.query.filter_by(
        user_id=s.officer_id, report_id=s.rp1_id).all()
    notes_reviewer = Notification.query.filter_by(
        user_id=s.cenro_admin_id, report_id=s.rp1_id).all()
    check(G, 'the submitting officer is notified',
          any('publish' in n.message.lower() for n in notes_officer),
          '%d notification(s)' % len(notes_officer))
    check(G, 'the approving CENRO admin is notified',
          any('publish' in n.message.lower() for n in notes_reviewer),
          '%d notification(s)' % len(notes_reviewer))

    # ------------------------------------------------------------------
    G = '5. Map exposure after publication'
    # ------------------------------------------------------------------
    as_penro(client, s)
    payload = api_boundaries(client)
    served = {b['site_id']: b for b in payload['boundaries']}
    check(G, 'the published boundary is now served', s.site_a_id in served)
    if s.site_a_id in served:
        b = served[s.site_a_id]
        check(G, 'the served geometry matches the published polygon',
              b['geometry'] == json.loads(s.b1_geojson))
        check(G, 'contract area and captured area are both reported',
              b['contract_area_ha'] == 5.0
              and b['captured_area_ha'] == s.b1_area,
              'contract=%s captured=%s' % (b['contract_area_ha'],
                                           b['captured_area_ha']))
    check(G, 'site B is still not served', s.site_b_id not in served)

    login(client, s.officer_id, s.officer_name, 'field_officer',
          'Urdaneta City')
    check(G, 'an officer inside the CENRO sees the published boundary',
          s.site_a_id in site_ids_in_api(client))

    login(client, s.dagupan_admin_id, s.dagupan_admin_name, 'admin',
          'Dagupan')
    check(G, 'a CENRO Dagupan admin does NOT see the Urdaneta boundary',
          s.site_a_id not in site_ids_in_api(client),
          'served: %s' % sorted(site_ids_in_api(client)))

    logout(client)
    check(G, 'an anonymous visitor sees the published boundary '
             '(this API has no login gate)',
          s.site_a_id in site_ids_in_api(client),
          'served anonymously: %s' % sorted(site_ids_in_api(client)))

    # ------------------------------------------------------------------
    G = '6. One published boundary per site'
    # ------------------------------------------------------------------
    as_cenro(client, s)
    review_post(client, s.rp2_id, 'Approved')
    as_penro(client, s)
    publish_post(client, s.rp2_id, 'publish', 'Re-survey supersedes 2023.')

    site_a = get_site(s.site_a_id)
    rp1 = get_report(s.rp1_id)
    rp2 = get_report(s.rp2_id)
    check(G, 'the newer report becomes the published one',
          rp2.publication_status == 'Published', rp2.publication_status)
    check(G, 'the older published report is stood down',
          rp1.publication_status != 'Published', rp1.publication_status)
    check(G, 'the site now carries the newer polygon',
          site_a.boundary_geojson == s.b2_geojson)
    check(G, 'the site source report points at the newer report',
          site_a.boundary_source_report_id == s.rp2_id)

    payload = api_boundaries(client)
    served = {b['site_id']: b for b in payload['boundaries']}
    check(G, 'exactly one boundary is served for the site',
          sum(1 for b in payload['boundaries']
              if b['site_id'] == s.site_a_id) == 1)
    check(G, 'the served geometry is the newer polygon',
          s.site_a_id in served
          and served[s.site_a_id]['geometry'] == json.loads(s.b2_geojson))

    # ------------------------------------------------------------------
    G = '7. Withdrawing a boundary'
    # ------------------------------------------------------------------
    as_penro(client, s)
    publish_post(client, s.rp2_id, 'unpublish', 'Corner 3 disputed.')
    site_a = get_site(s.site_a_id)
    rp2 = get_report(s.rp2_id)
    check(G, 'the site is no longer marked published',
          site_a.boundary_published is False)
    check(G, 'the report returns to the pending queue',
          rp2.publication_status == 'Pending Publication',
          rp2.publication_status)
    check(G, 'the boundary disappears from the map',
          s.site_a_id not in site_ids_in_api(client))
    check(G, 'the polygon itself is retained, not destroyed',
          site_a.boundary_geojson == s.b2_geojson)

    logout(client)
    check(G, 'an anonymous visitor no longer sees it either',
          s.site_a_id not in site_ids_in_api(client))

    # ------------------------------------------------------------------
    G = '8. Declining a boundary'
    # ------------------------------------------------------------------
    as_cenro(client, s)
    review_post(client, s.rp3_id, 'Approved')
    as_penro(client, s)
    publish_post(client, s.rp3_id, 'decline',
                 'Captured area is 40% off the contract.')
    rp3 = get_report(s.rp3_id)
    check(G, "report publication_status is 'Declined'",
          rp3.publication_status == 'Declined', rp3.publication_status)
    check(G, 'the decline reason is stored',
          bool(rp3.publication_note), str(rp3.publication_note))
    check(G, 'the declined site is never served by the map',
          s.site_b_id not in site_ids_in_api(client))
    check(G, 'a decline does not publish the site',
          get_site(s.site_b_id).boundary_published is False)

    # ------------------------------------------------------------------
    G = '9. Rejection closes the door'
    # ------------------------------------------------------------------
    login(client, s.dagupan_admin_id, s.dagupan_admin_name, 'admin',
          'Dagupan')
    review_post(client, s.rp5_id, 'Rejected', 'Corner photos lack GPS.')
    rp5 = get_report(s.rp5_id)
    check(G, 'a rejected report is marked Not Applicable for publication',
          rp5.publication_status == 'Not Applicable',
          rp5.publication_status)
    as_penro(client, s)
    publish_post(client, s.rp5_id, 'publish')
    check(G, 'a rejected report cannot be published',
          get_site(s.site_c_id).boundary_published is False
          and get_report(s.rp5_id).publication_status != 'Published',
          'publication_status=%s'
          % get_report(s.rp5_id).publication_status)

    # ------------------------------------------------------------------
    G = '10. Notification routing'
    # ------------------------------------------------------------------
    fresh()
    to_super = Notification.query.filter(
        Notification.user_id == s.superadmin_id,
        Notification.message.like('%awaiting publication%')).count()
    to_penro = Notification.query.filter(
        Notification.user_id == s.penro_id,
        Notification.message.like('%awaiting publication%')).count()
    check(G, 'the account that can actually publish is told a boundary '
             'is waiting',
          to_penro > 0,
          'provincial admin got %d, superadmin got %d'
          % (to_penro, to_super))
    if to_penro == 0:
        note("'Boundary awaiting publication' notifications are sent to "
             "role='superadmin' (app/routes/admin.py, review_report), but "
             "the publications page refuses superadmin and is reserved "
             "for a provincial admin (role='admin', cenro=None). The "
             "account that can publish is never told there is anything "
             "waiting.")


# ======================================================================
# report
# ======================================================================

def print_report(s):
    width = 74
    print()
    print('=' * width)
    print('PUBLISH-BOUNDARY MONITORING REPORT  (synthetic data)')
    print('=' * width)
    print('database : %s' % DB_FILE)
    print('run at   : %s' % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print('sites    : A=%d Urdaneta  B=%d Urdaneta  C=%d Dagupan'
          % (s.site_a_id, s.site_b_id, s.site_c_id))
    print('reports  : rp1=%d rp2=%d rp3=%d rp4=%d rp5=%d'
          % (s.rp1_id, s.rp2_id, s.rp3_id, s.rp4_id, s.rp5_id))
    print()

    current = None
    for r in RESULTS:
        if r['group'] != current:
            current = r['group']
            print('-' * width)
            print(current)
            print('-' * width)
        print('  [%s] %s' % ('PASS' if r['ok'] else 'FAIL', r['name']))
        if r['detail'] and not r['ok']:
            print('         %s' % r['detail'])

    passed = sum(1 for r in RESULTS if r['ok'])
    failed = len(RESULTS) - passed

    print()
    print('=' * width)
    print('SUMMARY:  %d checks   %d passed   %d failed'
          % (len(RESULTS), passed, failed))
    print('=' * width)

    if failed:
        print()
        print('FAILED CHECKS')
        for r in RESULTS:
            if not r['ok']:
                print('  - [%s] %s' % (r['group'], r['name']))
                if r['detail']:
                    print('      %s' % r['detail'])

    if NOTES:
        print()
        print('FINDINGS')
        for n in NOTES:
            print('  * ' + n)

    print()
    return failed


def main():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    failed = 1
    try:
        with app.app_context():
            db.create_all()
            s = seed()
            run(app, s)
            failed = print_report(s)
    finally:
        shutil.rmtree(TMPDIR, ignore_errors=True)

    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
