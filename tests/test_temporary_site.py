"""
Temporary site to published boundary, end to end.

A site made from a resident's request is "temporary" (proposed): staff
see it, the public does not, and the map draws the requester's area as a
dashed outline. It becomes an official public site only when the province
publishes a GPS boundary. This test walks one such site through every
step, through the real pages and forms:

    1  a resident requests a New Planting Site, with a pin and a plot
    2  the CENRO approves the request
    3  the CENRO creates the site from it            -> temporary site
    4  who can see it while it is temporary
    5  a field officer submits a report with 4 GPS corner photos
    6  the CENRO approves the report                 -> waits for province
    7  only the provincial administrator may publish
    8  the province publishes                        -> official site
    9  withdrawing it hides it again; declining needs a reason

Reuses the synthetic seed and throwaway SQLite database from
test_publish_boundary.py. Nothing touches the production Postgres, the
photos are saved in a temporary folder, and no email is sent.

RUN

    python tests/test_temporary_site.py

Exit code 0 when every check passes, 1 otherwise.
"""

import io
import json
import os
import sys
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# importing this first points DATABASE_URL at a temporary SQLite file
import test_publish_boundary as base                    # noqa: E402

from PIL import Image                                   # noqa: E402
from PIL.ExifTags import Base as ExifBase, GPS          # noqa: E402

from app import create_app                              # noqa: E402
from app.extensions import db                           # noqa: E402
from app.models import (                                # noqa: E402
    MonitoringReport, Notification, ReforestationRecord, Request, Site,
)
from app.routes import dashboard as dashboard_routes    # noqa: E402
from app.services.request_site import site_position     # noqa: E402


RESULTS = []
NOTES = []

# Inside the real Bacag, Villasis outline (app/static/geojson/eastern).
CENTRE_LAT, CENTRE_LON = 15.94064, 120.58656
PLOT = 0.002          # the requester's plot: centre +/- this many degrees
CORNER = 0.0019       # the officer's corner photos, just inside the plot
SITE_NAME = 'Temporary Test Site - Bacag'


def check(step, name, ok, detail=''):
    RESULTS.append((step, name, bool(ok), detail))


def note(text):
    NOTES.append(text)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def gps_photo(lat, lon, name, when):
    """A small JPEG carrying GPS and a timestamp, like a GPS camera app."""
    img = Image.new('RGB', (40, 30), (34, 139, 34))
    exif = Image.Exif()
    stamp = when.strftime('%Y:%m:%d 09:00:00')
    exif[ExifBase.DateTimeOriginal] = stamp
    exif[ExifBase.DateTime] = stamp

    def dms(v):
        v = abs(v)
        d = int(v)
        m = int((v - d) * 60)
        return (d, m, round(((v - d) * 60 - m) * 60, 4))

    gps = exif.get_ifd(0x8825)
    gps[GPS.GPSLatitudeRef] = 'N'
    gps[GPS.GPSLatitude] = dms(lat)
    gps[GPS.GPSLongitudeRef] = 'E'
    gps[GPS.GPSLongitude] = dms(lon)
    buf = io.BytesIO()
    img.save(buf, 'JPEG', exif=exif)
    buf.seek(0)
    return (buf, name)


def square(cx, cy, half):
    ring = [[cx - half, cy - half], [cx + half, cy - half],
            [cx + half, cy + half], [cx - half, cy + half]]
    return {'type': 'Polygon', 'coordinates': [ring + [ring[0]]]}


def get_json(client, url):
    r = client.get(url)
    return r.status_code, (r.get_json(silent=True) or {})


def names_in(payload):
    """Every site name anywhere in a JSON response, as one string."""
    return json.dumps(payload)


def as_officer(client, s):
    base.login(client, s.officer_id, s.officer_name, 'field_officer',
               'Urdaneta City')


def as_citizen(client, s):
    base.login(client, s.citizen_id, s.citizen_name, 'normal_user', None)


def visibility(client, site_id):
    """What one viewer sees of the site on the map and in the APIs."""
    _, in_brgy = get_json(client, '/api/sites-in-barangay'
                                  '?municipality=Villasis&barangay=Bacag')
    _, geo = get_json(client, '/api/sites-geo')
    _, published = get_json(client, '/api/published-boundaries')
    _, proposed = get_json(client, '/api/proposed-boundaries')
    history = client.get('/api/site-history/%d' % site_id).status_code
    row = next((x for x in in_brgy if x.get('site_id') == site_id), None) \
        if isinstance(in_brgy, list) else None
    return {
        'barangay_list': row is not None,
        'barangay_row': row,
        'map_marker': SITE_NAME in names_in(geo),
        'published': any(b['site_id'] == site_id
                         for b in published.get('boundaries', [])),
        'proposed': any(b['site_id'] == site_id
                        for b in proposed.get('boundaries', [])),
        'history': history,
    }


# ----------------------------------------------------------------------
# the walk
# ----------------------------------------------------------------------

def run(app, s):
    guest = app.test_client()
    citizen = app.test_client()
    as_citizen(citizen, s)
    officer = app.test_client()
    as_officer(officer, s)
    cenro = app.test_client()
    base.as_cenro(cenro, s)
    penro = app.test_client()
    base.as_penro(penro, s)
    dagupan = app.test_client()
    base.login(dagupan, s.dagupan_admin_id, s.dagupan_admin_name, 'admin', 'Dagupan')
    superadmin = app.test_client()
    base.login(superadmin, s.superadmin_id, s.superadmin_name, 'superadmin', None)
    today = datetime.now(ZoneInfo('Asia/Manila')).date()

    # --- 1. the request -------------------------------------------------
    step = '1 request'
    plot = square(CENTRE_LON, CENTRE_LAT, PLOT)
    r = citizen.post('/requests', data={
        'request_type': 'New Planting Site',
        'municipality': 'Villasis', 'barangay': 'Bacag',
        'latitude': str(CENTRE_LAT), 'longitude': str(CENTRE_LON),
        'boundary_geojson': json.dumps(plot),
        'planting_type': 'timber',
        'contact_name': 'Juan dela Cruz', 'contact_number': '09171234567',
        'contact_email': 'juan@synthetic.test',
    })
    base.fresh()
    req = Request.query.filter_by(user_id=s.citizen_id,
                                  request_type='New Planting Site').first()
    check(step, 'resident can submit with a pin and a drawn plot',
          r.status_code == 302 and req is not None, r.status_code)
    if req is None:
        return
    req_id = req.request_id
    check(step, 'pin and plot are stored',
          req.latitude is not None and req.boundary_geojson is not None)
    check(step, 'drawn plot is measured (about 19 ha)',
          req.boundary_area_ha and 17 < req.boundary_area_ha < 21,
          req.boundary_area_ha)
    check(step, 'seedlings estimated from timber spacing (2 m x 3 m)',
          req.estimated_seedlings and req.estimated_seedlings > 25000,
          req.estimated_seedlings)
    check(step, 'reviewing CENRO is notified',
          Notification.query.filter_by(user_id=s.cenro_admin_id,
                                       notification_type='New Request').count() >= 1)

    # --- 2. approve -------------------------------------------------------
    step = '2 approve request'
    r = dagupan.post('/admin/requests/%d/review' % req_id, data={'status': 'Approved'})
    base.fresh()
    check(step, 'another CENRO cannot approve it',
          db.session.get(Request, req_id).status == 'Submitted')
    r = cenro.post('/admin/requests/%d/review' % req_id, data={'status': 'Approved'})
    base.fresh()
    check(step, 'its own CENRO approves it',
          db.session.get(Request, req_id).status == 'Approved')

    # --- 3. create the site -------------------------------------------------
    step = '3 create site'
    form = {
        'site_name': SITE_NAME, 'site_code': '',
        'organization_id': '', 'new_organization': 'Bacag Tree Planters',
        'area_size_ha': '19', 'date_established': today.isoformat(),
        'zone_type': 'Production', 'target_seedlings': '30000',
        'date_planted': today.isoformat(), 'contact_person': 'Juan dela Cruz',
    }
    page = cenro.get('/admin/requests/%d/create-site' % req_id)
    check(step, 'create-site form opens for the CENRO', page.status_code == 200)
    r = cenro.post('/admin/requests/%d/create-site' % req_id, data=form)
    base.fresh()
    site = Site.query.filter_by(site_name=SITE_NAME).first()
    check(step, 'site is created', site is not None, r.status_code)
    if site is None:
        return
    site_id = site.site_id
    check(step, 'linked to its request', site.source_request_id == req_id)
    check(step, 'placed under the creating CENRO', site.cenro == 'Urdaneta City')
    check(step, 'temporary: no boundary, not published',
          site.boundary_geojson is None and not site.boundary_published)
    record = ReforestationRecord.query.filter_by(site_id=site_id).first()
    check(step, 'planting record holds the target seedlings',
          record is not None and record.target_quantity == 30000)
    r = cenro.post('/admin/requests/%d/create-site' % req_id, data=form)
    check(step, 'a second site cannot be made from the same request',
          Site.query.filter_by(source_request_id=req_id).count() == 1)
    r = cenro.post('/admin/requests/%d/review' % req_id, data={'status': 'Rejected',
                                                               'review_note': 'x'})
    base.fresh()
    check(step, 'request is locked to Approved once it has a site',
          db.session.get(Request, req_id).status == 'Approved')

    # --- 4. while temporary -------------------------------------------------
    step = '4 temporary'
    for who, client in (('guest', guest), ('resident', citizen)):
        v = visibility(client, site_id)
        check(step, f'{who}: not in the barangay site list', not v['barangay_list'])
        check(step, f'{who}: no map marker', not v['map_marker'])
        check(step, f'{who}: no dashed proposed outline', not v['proposed'])
        check(step, f'{who}: monitoring history hidden', v['history'] != 200,
              v['history'])
    v = visibility(officer, site_id)
    check(step, 'staff: in the barangay site list', v['barangay_list'])
    check(step, 'staff: shows the proposed area',
          v['barangay_row'] and v['barangay_row'].get('proposed_area') is not None)
    check(step, 'staff: map marker shown', v['map_marker'])
    check(step, 'staff: dashed proposed outline shown', v['proposed'])
    check(step, 'nobody: no official boundary yet',
          not v['published'] and not visibility(guest, site_id)['published'])
    base.fresh()
    pos = site_position(db.session.get(Site, site_id))
    check(step, "marker sits on the requester's pin",
          pos and pos[2] == "requester's pin", pos)
    sites_page = cenro.get('/sites').get_data(as_text=True)
    check(step, 'Sites page marks it as from a request',
          'From request #%d' % req_id in sites_page)

    # --- 5. the field report ------------------------------------------------
    step = '5 field report'
    corners = [(CENTRE_LAT - CORNER, CENTRE_LON - CORNER),
               (CENTRE_LAT - CORNER, CENTRE_LON + CORNER),
               (CENTRE_LAT + CORNER, CENTRE_LON + CORNER),
               (CENTRE_LAT + CORNER, CENTRE_LON - CORNER)]
    check(step, 'officer can open the report form',
          officer.get('/reports').status_code == 200)
    r = officer.post('/reports/submit', data={
        'site_id': str(site_id),
        'monitoring_date': today.isoformat(),
        'plot_count': ['26500'], 'plot_note': ['whole site'],
        'remarks': 'Synthetic field visit.',
        'plot_photos': [gps_photo(CENTRE_LAT, CENTRE_LON, 'plot.jpg', today)],
        'boundary_photos': [gps_photo(lat, lon, 'corner%d.jpg' % i, today)
                            for i, (lat, lon) in enumerate(corners, 1)],
    }, content_type='multipart/form-data')
    base.fresh()
    report = MonitoringReport.query.filter_by(site_id=site_id).first()
    check(step, 'report is submitted and pending',
          r.status_code == 302 and report is not None
          and report.approval_status == 'Pending', r.status_code)
    if report is None:
        return
    report_id = report.report_id
    check(step, 'boundary built from the 4 corner photos',
          report.boundary_geojson is not None and report.captured_area_ha
          and 13 < report.captured_area_ha < 19, report.captured_area_ha)
    check(step, 'captured area within 10% of the contracted 19 ha',
          report.area_difference_pct is not None
          and abs(report.area_difference_pct) <= 10, report.area_difference_pct)
    flagged = [p.flags for p in report.photos if p.flags]
    check(step, 'no photo flagged (GPS present, inside Bacag, dated today)',
          not flagged, flagged)
    site = db.session.get(Site, site_id)
    check(step, 'first capture is stored on the site, unpublished',
          site.boundary_geojson is not None and not site.boundary_published)
    check(step, 'still hidden from the public after the report',
          not visibility(guest, site_id)['barangay_list']
          and not visibility(guest, site_id)['published'])
    # A site made from a request has a target but no "actually planted"
    # figure, so there is no rate to work out. It must read as unknown,
    # never as 0% (every seedling dead).
    check(step, 'survival is unknown, not 0%', report.survival_rate is None,
          report.survival_rate)
    check(step, 'the count itself is kept',
          report.total_counted == 26500 and report.estimated_survivors == 26500)
    page = officer.get('/reports/%d' % report_id).get_data(as_text=True)
    check(step, 'report page says Unknown and why',
          'Unknown' in page and 'no seedlings actually planted' in page)
    check(step, 'My Reports shows Unknown, not None%',
          'None%' not in officer.get('/my-reports').get_data(as_text=True))

    # --- 6. CENRO approves the report ---------------------------------------
    step = '6 approve report'
    page = cenro.get('/admin/reports/%d' % report_id).get_data(as_text=True)
    check(step, 'review page warns there is no rate to record',
          'No survival rate to record' in page)
    base.review_post(cenro, report_id, 'Approved')
    base.fresh()
    report = db.session.get(MonitoringReport, report_id)
    check(step, 'report approved', report.approval_status == 'Approved')
    record = ReforestationRecord.query.filter_by(site_id=site_id).first()
    check(step, 'planting record survival stays unknown, not 0%',
          record.survival_rate is None, record.survival_rate)
    _, analytics = get_json(cenro, '/api/dashboard-analytics')
    villasis = next((m for m in analytics.get('by_municipality', [])
                     if m['municipality'] == 'Villasis'), {})
    check(step, 'dashboard survival for Villasis is not dragged to 0',
          villasis.get('survival') != 0, villasis.get('survival'))
    check(step, 'boundary now waits for the province',
          report.publication_status == 'Pending Publication',
          report.publication_status)
    check(step, 'provincial administrator is notified',
          Notification.query.filter(Notification.user_id == s.penro_id,
                                    Notification.message.like('Boundary awaiting%'))
          .count() >= 1)
    check(step, 'still hidden from the public',
          not visibility(guest, site_id)['published']
          and not visibility(guest, site_id)['barangay_list'])

    # --- 7. who may publish ---------------------------------------------------
    step = '7 who may publish'
    for who, client in (('CENRO admin', cenro), ('system admin', superadmin),
                        ('field officer', officer)):
        base.publish_post(client, report_id, 'publish')
        base.fresh()
        check(step, f'{who} cannot publish',
              not db.session.get(Site, site_id).boundary_published)
    r = base.publish_post(penro, report_id, 'decline', '')
    base.fresh()
    check(step, 'declining without a reason is refused',
          db.session.get(MonitoringReport, report_id).publication_status
          == 'Pending Publication')

    # --- 8. the province publishes -------------------------------------------
    step = '8 publish'
    base.publish_post(penro, report_id, 'publish')
    base.fresh()
    site = db.session.get(Site, site_id)
    report = db.session.get(MonitoringReport, report_id)
    check(step, 'site is published', site.boundary_published is True)
    check(step, "site boundary is the report's", site.boundary_geojson
          == report.boundary_geojson and site.boundary_source_report_id == report_id)
    check(step, 'report marked Published', report.publication_status == 'Published')
    for who, client in (('guest', guest), ('resident', citizen)):
        v = visibility(client, site_id)
        check(step, f'{who}: now in the barangay site list', v['barangay_list'])
        check(step, f'{who}: now has a map marker', v['map_marker'])
        check(step, f'{who}: official boundary drawn', v['published'])
        check(step, f'{who}: monitoring history open', v['history'] == 200,
              v['history'])
    check(step, 'public report page opens for a guest',
          guest.get('/monitoring-reports/%d' % report_id).status_code == 200)
    check(step, 'dashed proposed outline is gone (official one replaces it)',
          not visibility(officer, site_id)['proposed'])
    pos = site_position(site)
    check(step, 'marker moves to the published boundary centre',
          pos and pos[2] == 'published boundary', pos)
    told = {n.user_id for n in Notification.query.filter(
        Notification.message.like('%Boundary published%'))}
    check(step, 'field officer and approving CENRO are told',
          {s.officer_id, s.cenro_admin_id} <= told, told)

    # --- 9. withdraw and decline -----------------------------------------------
    step = '9 withdraw / decline'
    base.publish_post(penro, report_id, 'unpublish')
    base.fresh()
    v = visibility(guest, site_id)
    check(step, 'withdrawn: hidden from the public again',
          not v['published'] and not v['barangay_list'])
    check(step, 'withdrawn: back in the publication queue',
          db.session.get(MonitoringReport, report_id).publication_status
          == 'Pending Publication')
    base.publish_post(penro, report_id, 'decline', 'Corners do not match the parcel.')
    base.fresh()
    check(step, 'declined with a reason: stays off the map',
          db.session.get(MonitoringReport, report_id).publication_status == 'Declined'
          and not visibility(guest, site_id)['published'])

    # --- 10. a site WITH a planted figure still gets a real rate --------------
    # Synthetic Site A: 5 ha (whole-site count), 4,800 seedlings planted.
    step = '10 known survival'
    officer.post('/reports/submit', data={
        'site_id': str(s.site_a_id), 'monitoring_date': today.isoformat(),
        'plot_count': ['4200'], 'plot_note': [''],
        'remarks': 'Known-rate check.',
    }, content_type='multipart/form-data')
    base.fresh()
    known = MonitoringReport.query.filter_by(remarks='Known-rate check.').first()
    check(step, 'survival is worked out: 4,200 / 4,800 = 87.5%',
          known is not None and known.survival_rate == 87.5,
          known.survival_rate if known else None)
    if known is None:
        return
    base.review_post(cenro, known.report_id, 'Approved')
    base.fresh()
    record_a = ReforestationRecord.query.filter_by(site_id=s.site_a_id).first()
    check(step, 'approving writes 87.5% to the planting record',
          record_a.survival_rate == 87.5, record_a.survival_rate)


def print_results():
    print()
    print('TEMPORARY SITE TO PUBLISHED BOUNDARY  (synthetic data)')
    print('-' * 74)
    current = None
    for step, name, ok, detail in RESULTS:
        if step != current:
            print('  %s' % step)
            current = step
        print('    [%s] %s' % ('PASS' if ok else 'FAIL', name))
        if detail and not ok:
            print('           %s' % (detail,))
    failed = sum(1 for *_, ok, _ in RESULTS if not ok)
    print('-' * 74)
    for text in NOTES:
        print('  NOTE: %s' % text)
    print('SUMMARY:  %d checks   %d passed   %d failed'
          % (len(RESULTS), len(RESULTS) - failed, failed))
    print()
    return failed


def main():
    app = create_app()
    app.config['TESTING'] = True
    app.config['MAIL_SERVER'] = ''

    # Photos go to the temporary folder, not app/static/uploads. The map
    # outlines stay where they are: the report checks photos against them.
    photo_dir = os.path.join(base.TMPDIR, 'static')
    real_save = dashboard_routes.save_photo
    dashboard_routes.save_photo = (
        lambda f, _static, report_id, index: real_save(f, photo_dir, report_id, index))

    failed = 1
    try:
        with app.app_context():
            db.create_all()
            s = base.seed()
            run(app, s)
            failed = print_results()
    finally:
        dashboard_routes.save_photo = real_save
        shutil.rmtree(base.TMPDIR, ignore_errors=True)

    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
