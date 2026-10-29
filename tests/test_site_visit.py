"""
Site visits, end to end (app/routes/visits.py).

A temporary site (made from a request) is checked in the field with site
visits before it has seedlings to count. This test drives every part
through the real pages and forms:

    1  who can open a site's visits, and the map's Site visits button
    2  the form refuses bad input
    3  a pre-planting check with 4 GPS corner photos builds a boundary
    4  only the site's CENRO approves it; the boundary goes to the province
    5  the province publishes it from Boundary Publications
    6  a planting confirmation saves the seedlings actually planted, so a
       later monitoring report gets a real survival rate
    7  a "Not suitable" visit: the CENRO must suggest a new site, the
       requester is told and emailed, the dashed outline goes
    8  a decision is final

Reuses the synthetic seed and throwaway SQLite database from
test_publish_boundary.py, and the GPS photo maker from
test_temporary_site.py. Photos go to a temporary folder; no email is sent.

RUN

    python tests/test_site_visit.py

Exit code 0 when every check passes, 1 otherwise.
"""

import os
import sys
import shutil
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# importing this first points DATABASE_URL at a temporary SQLite file
import test_publish_boundary as base                    # noqa: E402
from test_temporary_site import (                       # noqa: E402
    CENTRE_LAT, CENTRE_LON, CORNER, gps_photo, get_json, visibility,
    as_officer, as_citizen,
)

from app import create_app                              # noqa: E402
from app.extensions import db                           # noqa: E402
from app.models import (                                # noqa: E402
    Location, MonitoringReport, Notification, ReforestationRecord, Request,
    Site, SiteVisit,
)
from app.routes import visits as visits_routes          # noqa: E402
from app.services import mailer                         # noqa: E402


RESULTS = []


def check(step, name, ok, detail=''):
    RESULTS.append((step, name, bool(ok), detail))


def make_temporary_site(s, name, with_plot=True):
    """A site as the CENRO's create-site form leaves it (tested in
    test_temporary_site.py): from an approved request, no boundary, a
    planting record with a target only."""
    loc = Location.query.filter_by(barangay='Bacag').first()
    req = Request(user_id=s.citizen_id, location_id=loc.location_id,
                  request_type='New Planting Site', status='Approved',
                  contact_name='Juan dela Cruz',
                  contact_email='juan.contact@synthetic.test',
                  latitude=CENTRE_LAT, longitude=CENTRE_LON)
    if with_plot:
        d = 0.002
        req.boundary_geojson = (
            '{"type": "Polygon", "coordinates": [[[%f, %f], [%f, %f], '
            '[%f, %f], [%f, %f], [%f, %f]]]}' % (
                CENTRE_LON - d, CENTRE_LAT - d, CENTRE_LON + d, CENTRE_LAT - d,
                CENTRE_LON + d, CENTRE_LAT + d, CENTRE_LON - d, CENTRE_LAT + d,
                CENTRE_LON - d, CENTRE_LAT - d))
        req.boundary_area_ha = 19.0
    db.session.add(req)
    db.session.flush()
    site = Site(location_id=loc.location_id,
                organization_id=db.session.get(Site, s.site_a_id).organization_id,
                site_name=name, area_size_ha=19.0, cenro='Urdaneta City',
                penro='Pangasinan', source_request_id=req.request_id)
    db.session.add(site)
    db.session.flush()
    db.session.add(ReforestationRecord(
        site_id=site.site_id, tree_id=db.session.get(
            ReforestationRecord, 1).tree_id,
        date_planted=date.today(), target_quantity=30000))
    db.session.commit()
    return site.site_id


def corner_photos(day):
    corners = [(CENTRE_LAT - CORNER, CENTRE_LON - CORNER),
               (CENTRE_LAT - CORNER, CENTRE_LON + CORNER),
               (CENTRE_LAT + CORNER, CENTRE_LON + CORNER),
               (CENTRE_LAT + CORNER, CENTRE_LON - CORNER)]
    return [gps_photo(lat, lon, 'corner%d.jpg' % i, day)
            for i, (lat, lon) in enumerate(corners, 1)]


def visit_form(day, **over):
    data = {'visit_date': day.isoformat(), 'visit_type': 'Pre-planting check',
            'finding': 'Suitable', 'land_matches': 'yes',
            'ownership_confirmed': 'yes', 'accessible': 'no',
            'remarks': 'Open grassland, road ends 200 m away.'}
    data.update(over)
    return data


def latest_visit(site_id):
    base.fresh()
    return (SiteVisit.query.filter_by(site_id=site_id)
            .order_by(SiteVisit.visit_id.desc()).first())


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
    today = datetime.now(ZoneInfo('Asia/Manila')).date()
    box = mailer.outbox()

    site_id = make_temporary_site(s, 'Visit Test Site - Bacag')
    page_url = '/sites/%d/visits' % site_id
    new_url = page_url + '/new'

    # --- 1. who can open it -------------------------------------------------
    step = '1 access'
    for who, client in (('guest', guest), ('resident', citizen),
                        ('another CENRO', dagupan)):
        r = client.get(page_url)
        check(step, f'{who} cannot open the visits', r.status_code == 302,
              r.status_code)
    page = officer.get(page_url).get_data(as_text=True)
    check(step, "site's field officer opens it, with Record site visit",
          'Site Visits' in page and 'Record site visit' in page)
    page = cenro.get(page_url).get_data(as_text=True)
    check(step, "site's CENRO admin opens it, without the record button",
          'Site Visits' in page and 'Record site visit' not in page)
    check(step, 'province-wide admin can look',
          penro.get(page_url).status_code == 200)
    check(step, 'CENRO admin cannot open the record form',
          cenro.get(new_url).status_code == 302)
    r = officer.get('/sites/%d/visits' % s.site_a_id)
    check(step, 'a DENR-imported site uses monitoring reports instead',
          r.status_code == 302)
    _, rows = get_json(officer, '/api/sites-in-barangay'
                                '?municipality=Villasis&barangay=Bacag')
    row = next((x for x in rows if x['site_id'] == site_id), {})
    check(step, 'map data marks the site as made from a request',
          row.get('from_request') is True)
    check(step, 'map page has the Site visits button for staff',
          'siteVisitsButton' in officer.get('/gis-map').get_data(as_text=True))

    # the sidebar link and its list page
    page = officer.get('/dashboard').get_data(as_text=True)
    nav = page.split('class="sidebar-nav"')[1].split('</nav>')[0]
    check(step, "field officer's sidebar has Site Visits",
          'href="/site-visits"' in nav and 'Site Visits' in nav)
    nav = cenro.get('/dashboard').get_data(as_text=True)
    nav = nav.split('class="sidebar-nav"')[1].split('</nav>')[0]
    check(step, "CENRO admin's sidebar does not", 'href="/site-visits"' not in nav)
    page = officer.get('/site-visits').get_data(as_text=True)
    check(step, 'Site Visits list shows the site as needing a first visit',
          'Visit Test Site - Bacag' in page and 'Needs a first visit' in page
          and '/sites/%d/visits/new' % site_id in page)
    check(step, 'the list highlights Site Visits in the sidebar',
          'class="nav-link active"' in page.split('href="/site-visits"')[1][:80])
    check(step, 'residents cannot open the list',
          citizen.get('/site-visits').status_code == 302)
    other = officer.get('/site-visits').get_data(as_text=True)
    check(step, "an imported DENR site is not listed",
          'Synthetic Site A' not in other)

    # --- 2. the form refuses bad input ----------------------------------------
    step = '2 validation'
    bad = [
        ('a future date', visit_form(today + timedelta(days=2))),
        ('Not suitable with no reason', visit_form(today, finding='Not suitable', remarks='')),
        ('a planting confirmation with no number',
         visit_form(today, visit_type='Planting confirmed', date_planted=today.isoformat())),
        ('a planting confirmation that finds the site not suitable',
         visit_form(today, visit_type='Planting confirmed', finding='Not suitable',
                    seedlings_planted='100', date_planted=today.isoformat())),
    ]
    for name, data in bad:
        officer.post(new_url, data=data, content_type='multipart/form-data')
        check(step, f'refuses {name}', latest_visit(site_id) is None)

    # --- 3. pre-planting check with a boundary ----------------------------------
    step = '3 pre-planting check'
    data = visit_form(today)
    data['site_photos'] = [gps_photo(CENTRE_LAT, CENTRE_LON, 'land.jpg', today)]
    data['boundary_photos'] = corner_photos(today)
    r = officer.post(new_url, data=data, content_type='multipart/form-data')
    v = latest_visit(site_id)
    check(step, 'visit is saved and pending',
          v is not None and v.status == 'Pending' and r.status_code == 302)
    if v is None:
        return
    visit_id = v.visit_id
    check(step, 'land check answers saved (yes, yes, no)',
          (v.land_matches, v.ownership_confirmed, v.accessible) == (True, True, False))
    check(step, 'boundary built from the 4 corners',
          v.boundary_geojson and 13 < v.captured_area_ha < 19, v.captured_area_ha)
    check(step, '1 site photo and 4 corner photos, none flagged',
          sorted(p.photo_type for p in v.photos) == ['boundary'] * 4 + ['site']
          and not [p.flags for p in v.photos if p.flags],
          [(p.photo_type, p.flags) for p in v.photos])
    check(step, 'the site is not touched before review',
          db.session.get(Site, site_id).boundary_geojson is None)
    n = Notification.query.filter_by(user_id=s.cenro_admin_id, visit_id=visit_id).first()
    check(step, 'CENRO is notified, linked to the visit', n is not None)
    _, notes = get_json(cenro, '/api/notifications')
    check(step, 'notification carries the visit id for its link',
          any(x.get('visit_id') == visit_id for x in notes.get('notifications', [])))
    page = officer.get('/visits/%d' % visit_id).get_data(as_text=True)
    check(step, 'detail page shows the finding and the boundary',
          'Suitable' in page and 'Captured' in page)

    # --- 4. CENRO review ----------------------------------------------------------
    step = '4 review'
    for who, client in (('another CENRO', dagupan), ('province-wide admin', penro),
                        ('field officer', officer)):
        client.post('/visits/%d/review' % visit_id, data={'status': 'Approved'})
        check(step, f'{who} cannot approve it', latest_visit(site_id).status == 'Pending')
    cenro.post('/visits/%d/review' % visit_id, data={'status': 'Rejected'})
    check(step, 'rejecting needs a reason', latest_visit(site_id).status == 'Pending')
    page = cenro.get('/visits/%d' % visit_id).get_data(as_text=True)
    check(step, 'review form says the boundary goes to the province',
          'sends the boundary to the provincial administrator' in page)
    cenro.post('/visits/%d/review' % visit_id, data={'status': 'Approved'})
    v = latest_visit(site_id)
    check(step, 'approved; boundary waits for publication',
          v.status == 'Approved' and v.publication_status == 'Pending Publication')
    check(step, 'provincial admin is notified',
          Notification.query.filter_by(user_id=s.penro_id, visit_id=visit_id).count() >= 1)
    check(step, 'field officer is told',
          Notification.query.filter(Notification.user_id == s.officer_id,
                                    Notification.visit_id == visit_id,
                                    Notification.message.like('%approved%')).count() == 1)

    # --- 5. publication -------------------------------------------------------------
    step = '5 publish'
    page = penro.get('/admin/publications').get_data(as_text=True)
    check(step, 'Boundary Publications lists the visit',
          'Site visit #%d' % visit_id in page)
    publish = '/admin/publications/visits/%d/publish' % visit_id
    cenro.post(publish, data={'action': 'publish'})
    check(step, 'CENRO admin cannot publish',
          not db.session.get(Site, site_id).boundary_published)
    penro.post(publish, data={'action': 'decline', 'publication_note': ''})
    check(step, 'declining needs a reason',
          latest_visit(site_id).publication_status == 'Pending Publication')
    penro.post(publish, data={'action': 'publish'})
    base.fresh()
    site = db.session.get(Site, site_id)
    check(step, 'published: the site takes the visit boundary',
          site.boundary_published and site.boundary_source_visit_id == visit_id
          and site.boundary_source_report_id is None
          and site.boundary_geojson == latest_visit(site_id).boundary_geojson)
    check(step, 'now official: guests see the boundary',
          visibility(guest, site_id)['published'])
    page = penro.get('/admin/publications?status=Published').get_data(as_text=True)
    check(step, 'listed under Published', 'Site visit #%d' % visit_id in page)

    # a second boundary for the same site, declined: withdrawing IT must not
    # take the published one off the map (review finding)
    data = visit_form(today)
    data['boundary_photos'] = corner_photos(today)
    officer.post(new_url, data=data, content_type='multipart/form-data')
    extra = latest_visit(site_id).visit_id
    cenro.post('/visits/%d/review' % extra, data={'status': 'Approved'})
    penro.post('/admin/publications/visits/%d/publish' % extra,
               data={'action': 'decline', 'publication_note': 'Corners too close.'})
    penro.post('/admin/publications/visits/%d/publish' % extra, data={'action': 'unpublish'})
    base.fresh()
    check(step, 'withdrawing a boundary that is not the published one is refused',
          db.session.get(Site, site_id).boundary_published
          and db.session.get(SiteVisit, extra).publication_status == 'Declined')
    penro.post(publish, data={'action': 'decline', 'publication_note': 'x'})
    base.fresh()
    check(step, 'declining the published boundary is refused',
          db.session.get(SiteVisit, visit_id).publication_status == 'Published'
          and db.session.get(Site, site_id).boundary_published)

    # --- 6. planting confirmation ------------------------------------------------------
    step = '6 planting'
    planted_on = today - timedelta(days=3)
    officer.post(new_url, data=visit_form(
        today, visit_type='Planting confirmed', seedlings_planted='15,000',
        date_planted=planted_on.isoformat(), remarks='Planted with the PO.'),
        content_type='multipart/form-data')
    v2 = latest_visit(site_id)
    check(step, 'a second visit to the same site is allowed',
          v2 and v2.visit_id != visit_id and v2.seedlings_planted == 15000)
    cenro.post('/visits/%d/review' % v2.visit_id, data={'status': 'Approved'})
    base.fresh()
    record = ReforestationRecord.query.filter_by(site_id=site_id).first()
    check(step, 'approving saves 15,000 actually planted to the record',
          record.actual_quantity_planted == 15000 and record.date_planted == planted_on,
          (record.actual_quantity_planted, record.date_planted))
    check(step, 'no boundary on this visit, so nothing to publish',
          latest_visit(site_id).publication_status == 'Not Applicable')
    officer.post('/reports/submit', data={
        'site_id': str(site_id), 'monitoring_date': today.isoformat(),
        'plot_count': ['12000'], 'plot_note': [''], 'remarks': 'After visits.',
    }, content_type='multipart/form-data')
    base.fresh()
    rep = MonitoringReport.query.filter_by(remarks='After visits.').first()
    check(step, 'a later monitoring report gets a real rate: 12,000 / 15,000 = 80%',
          rep is not None and rep.survival_rate == 80.0,
          rep.survival_rate if rep else None)

    # --- 7. not suitable --------------------------------------------------------------
    step = '7 not suitable'
    bad_id = make_temporary_site(s, 'Unsuitable Test Site - Bacag')
    check(step, 'the new temporary site has a dashed outline for staff',
          visibility(officer, bad_id)['proposed'])
    # first a Suitable visit with a boundary, approved, waiting for the
    # province; then a second Suitable visit left pending
    data = visit_form(today)
    data['boundary_photos'] = corner_photos(today)
    officer.post('/sites/%d/visits/new' % bad_id, data=data,
                 content_type='multipart/form-data')
    early = latest_visit(bad_id).visit_id
    cenro.post('/visits/%d/review' % early, data={'status': 'Approved'})
    officer.post('/sites/%d/visits/new' % bad_id, data=visit_form(today),
                 content_type='multipart/form-data')
    waiting = latest_visit(bad_id).visit_id
    check(step, 'earlier boundary is waiting for the province',
          db.session.get(SiteVisit, early).publication_status == 'Pending Publication')
    officer.post('/sites/%d/visits/new' % bad_id, data=visit_form(
        today, finding='Not suitable', remarks='Riverbank, floods every year.'),
        content_type='multipart/form-data')
    v3 = latest_visit(bad_id)
    check(step, 'Not suitable visit saved', v3 and v3.finding == 'Not suitable')
    page = cenro.get('/visits/%d' % v3.visit_id).get_data(as_text=True)
    check(step, 'review form asks for a suggested new site',
          'Suggest a new planting site' in page)
    cenro.post('/visits/%d/review' % v3.visit_id, data={'status': 'Approved'})
    check(step, 'approving without a suggestion is refused',
          latest_visit(bad_id).status == 'Pending')
    cenro.post('/visits/%d/review' % v3.visit_id, data={
        'status': 'Approved', 'suggested_municipality': 'Dagupan City',
        'suggested_barangay': 'Bonuan', 'suggestion_note': 'x'})
    check(step, "a suggestion outside the CENRO's area is refused",
          latest_visit(bad_id).status == 'Pending')
    box.clear()
    cenro.post('/visits/%d/review' % v3.visit_id, data={
        'status': 'Approved', 'suggested_municipality': 'Villasis',
        'suggested_barangay': 'Bacag',
        'suggestion_note': 'Plant on the upland part of Bacag, past the school.'})
    v3 = latest_visit(bad_id)
    check(step, 'approved, with the suggestion saved',
          v3.status == 'Approved' and v3.suggested_location is not None
          and 'upland' in (v3.suggestion_note or ''))
    check(step, 'site is marked Not Suitable',
          db.session.get(Site, bad_id).site_status == 'Not Suitable')
    check(step, 'its boundary is not sent for publication',
          v3.publication_status == 'Not Applicable')
    told = Notification.query.filter(Notification.user_id == s.citizen_id,
                                     Notification.message.like('%not suitable%')).first()
    check(step, 'requester notified with the suggestion',
          told is not None and 'upland' in told.message)
    mail = box[-1] if box else {}
    check(step, 'requester emailed, contact person copied',
          mail.get('to') == [s.citizen_name + '@synthetic.test']
          and mail.get('cc') == ['juan.contact@synthetic.test']
          and 'Bacag, Villasis' in mail.get('text', '')
          and 'Riverbank' in mail.get('text', ''), mail)
    check(step, 'the dashed outline is gone',
          not visibility(officer, bad_id)['proposed'])

    # the site is now closed (review finding)
    base.fresh()
    e = db.session.get(SiteVisit, early)
    check(step, 'the waiting boundary was declined, with the reason',
          e.publication_status == 'Declined' and 'not suitable' in (e.publication_note or ''))
    penro.post('/admin/publications/visits/%d/publish' % early, data={'action': 'publish'})
    base.fresh()
    check(step, 'it cannot be published afterwards',
          not db.session.get(Site, bad_id).boundary_published
          and not visibility(guest, bad_id)['published'])
    cenro.post('/visits/%d/review' % waiting, data={'status': 'Approved'})
    check(step, 'a visit still pending cannot be approved on the closed site',
          db.session.get(SiteVisit, waiting).status == 'Pending')
    cenro.post('/visits/%d/review' % waiting, data={'status': 'Rejected',
                                                   'review_note': 'Site closed.'})
    base.fresh()
    check(step, 'but it can be rejected',
          db.session.get(SiteVisit, waiting).status == 'Rejected')
    before = SiteVisit.query.filter_by(site_id=bad_id).count()
    officer.post('/sites/%d/visits/new' % bad_id, data=visit_form(today),
                 content_type='multipart/form-data')
    check(step, 'no new visit can be recorded on the closed site',
          SiteVisit.query.filter_by(site_id=bad_id).count() == before)
    check(step, 'its visits page has no Record button',
          'Record site visit' not in officer.get('/sites/%d/visits' % bad_id)
          .get_data(as_text=True))
    check(step, 'visits page shows the Not suitable notice',
          'Not suitable.' in officer.get('/sites/%d/visits' % bad_id).get_data(as_text=True))
    page = officer.get('/site-visits').get_data(as_text=True)
    check(step, 'Site Visits list: not suitable, with no Record button',
          'Not suitable</span>' in page
          and '/sites/%d/visits/new' % bad_id not in page)
    check(step, 'Site Visits list: the published site can still be visited',
          'Boundary published' in page and '/sites/%d/visits/new' % site_id in page)

    # --- 8. a decision is final ------------------------------------------------------------
    step = '8 final'
    cenro.post('/visits/%d/review' % visit_id, data={'status': 'Rejected',
                                                    'review_note': 'changed my mind'})
    check(step, 'an approved visit cannot be reviewed again',
          db.session.get(SiteVisit, visit_id).status == 'Approved')

    # --- 9. an account with site visits cannot be deleted (review finding) ---
    step = '9 accounts'
    from app.models import User
    lone = User(username='visit_only_officer', email_address='v@synthetic.test',
                role='field_officer', cenro='Urdaneta City', is_active=True)
    lone.set_password('synthetic-password1')
    db.session.add(lone)
    db.session.commit()
    db.session.add(SiteVisit(site_id=site_id, user_id=lone.user_id, visit_date=today,
                             visit_type='Pre-planting check', finding='Suitable',
                             status='Pending'))
    db.session.commit()
    lone_id = lone.user_id
    superadmin = app.test_client()
    base.login(superadmin, s.superadmin_id, s.superadmin_name, 'superadmin', None)
    superadmin.post('/admin/users/%d/delete' % lone_id,
                    data={'confirm_username': 'visit_only_officer'})
    base.fresh()
    check(step, 'an officer whose only work is site visits is kept',
          db.session.get(User, lone_id) is not None
          and SiteVisit.query.filter_by(user_id=lone_id).count() == 1)

    # --- 10. the lists stay fast as sites pile up (review finding) ----------
    # The query count must not grow with the number of sites or cards.
    step = '10 speed'
    from sqlalchemy import event
    counter = {'n': 0}

    def count_query(*_a, **_k):
        counter['n'] += 1

    def queries(client, url):
        counter['n'] = 0
        event.listen(db.engine, 'before_cursor_execute', count_query)
        try:
            client.get(url)
        finally:
            event.remove(db.engine, 'before_cursor_execute', count_query)
        return counter['n']

    list_before = queries(officer, '/site-visits')
    pub_before = queries(penro, '/admin/publications?status=Published')
    for i in range(10):
        extra_site = make_temporary_site(s, 'Speed Site %d' % i)
        db.session.add(SiteVisit(
            site_id=extra_site, user_id=s.officer_id, visit_date=today,
            visit_type='Pre-planting check', finding='Suitable',
            status='Approved', reviewed_by=s.cenro_admin_id,
            date_reviewed=datetime.now(), publication_status='Published',
            boundary_geojson=db.session.get(SiteVisit, visit_id).boundary_geojson,
            captured_area_ha=10.0))
    db.session.commit()
    list_after = queries(officer, '/site-visits')
    pub_after = queries(penro, '/admin/publications?status=Published')
    check(step, 'Site Visits list: same queries with 10 more sites',
          list_after == list_before, (list_before, list_after))
    check(step, 'Publications: same queries with 10 more cards',
          pub_after == pub_before, (pub_before, pub_after))


def print_results():
    print()
    print('SITE VISITS  (synthetic data)')
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
    print('SUMMARY:  %d checks   %d passed   %d failed'
          % (len(RESULTS), len(RESULTS) - failed, failed))
    print()
    return failed


def main():
    app = create_app()
    app.config['TESTING'] = True
    app.config['MAIL_SERVER'] = ''

    photo_dir = os.path.join(base.TMPDIR, 'static')
    real_save = visits_routes.save_photo
    visits_routes.save_photo = (
        lambda f, _static, key, index: real_save(f, photo_dir, key, index))
    from app.routes import dashboard as dashboard_routes
    real_report_save = dashboard_routes.save_photo
    dashboard_routes.save_photo = (
        lambda f, _static, key, index: real_report_save(f, photo_dir, key, index))

    failed = 1
    try:
        with app.app_context():
            db.create_all()
            s = base.seed()
            run(app, s)
            failed = print_results()
    finally:
        visits_routes.save_photo = real_save
        dashboard_routes.save_photo = real_report_save
        shutil.rmtree(base.TMPDIR, ignore_errors=True)

    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
