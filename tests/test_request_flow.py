"""
The new-site request flow and email verification.

    1  supporting documents are required, on every request type
    2  a temporary site is made while the request is Under Review
    3  the organization list is filtered by barangay, like sign-up
    4  the assigned officer sees the request; admins re-assign and withdraw
    5  a rejected visit reopens the assignment
    6  a requester cannot cancel once a site exists
    7  temporary sites stay out of the official figures
    8  rejecting a request closes its site
    9  email verification on sign-up, and the admin-created account email
   10  the GIS map's filters start on None, with no All

Reuses the synthetic seed and throwaway SQLite database from
test_publish_boundary.py. Nothing touches Postgres, uploads go to a
temporary folder, and no email is sent.

RUN

    python tests/test_request_flow.py

Exit code 0 when every check passes, 1 otherwise.
"""

import io
import os
import re
import shutil
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# importing this first points DATABASE_URL at a temporary SQLite file
import test_publish_boundary as base                    # noqa: E402
from test_temporary_site import as_citizen, as_officer  # noqa: E402

from app import create_app                              # noqa: E402
from app.extensions import db                           # noqa: E402
from app.models import (                                # noqa: E402
    Location, MonitoringReport, Notification, Organization, Request,
    RequestAttachment, Site, SiteVisit, User, VisitAssignment,
)
from app.routes import auth as auth_routes              # noqa: E402
from app.routes import dashboard as dashboard_routes    # noqa: E402
from app.routes import visits as visits_routes          # noqa: E402
from app.services import mailer                         # noqa: E402
from app.utils.jurisdiction import official_sites       # noqa: E402

RESULTS = []
PASSWORD = 'Synthetic-pass1'


def check(step, name, ok, detail=''):
    RESULTS.append((step, name, bool(ok), detail))


def pdf(name='plan.pdf'):
    return (io.BytesIO(b'%PDF-1.4 synthetic'), name)


def request_form(**over):
    data = {
        'request_type': 'Seedling Supply',
        'municipality': 'Villasis', 'barangay': 'Bacag',
        'contact_name': 'Maria Santos', 'contact_number': '09171234567',
        'contact_email': 'maria@synthetic.test',
    }
    data.update(over)
    return data


def new_request(s, status='Under Review', contact='Maria Santos'):
    """A New Planting Site request with one document on file."""
    base.fresh()
    loc = Location.query.filter_by(barangay='Bacag').first()
    req = Request(user_id=s.citizen_id, location_id=loc.location_id,
                  request_type='New Planting Site', status=status,
                  contact_name=contact, contact_email='maria@synthetic.test')
    db.session.add(req)
    db.session.flush()
    db.session.add(RequestAttachment(
        request_id=req.request_id, file_url='uploads/requests/synthetic.pdf',
        original_name='management-plan.pdf', file_hash='x',
        mime_type='application/pdf'))
    db.session.commit()
    return req.request_id


def site_form(s, name, **over):
    today = datetime.now(ZoneInfo('Asia/Manila')).date().isoformat()
    data = {
        'site_name': name, 'site_code': '', 'organization_id': '',
        'new_organization': 'Bacag Tree Planters %s' % name,
        'area_size_ha': '5', 'date_established': today, 'zone_type': '',
        'target_seedlings': '1000', 'date_planted': today,
        'contact_person': 'Maria Santos', 'officer_id': str(s.officer_id),
        'visit_type': 'Pre-planting check', 'target_date': '',
        'assignment_note': 'Meet the barangay captain.',
    }
    data.update(over)
    return data


def make_site(cenro, s, name):
    """Under Review request -> temporary site with the officer assigned.
    Returns (request_id, site_id)."""
    req_id = new_request(s)
    cenro.post('/admin/requests/%d/create-site' % req_id, data=site_form(s, name))
    base.fresh()
    site = Site.query.filter_by(site_name=name).first()
    return req_id, site.site_id if site else None


def link_in(mail, path):
    m = re.search(r'(/%s/[^\s<"]+)' % path, mail.get('text', ''))
    return m.group(1) if m else None


def flashes(client):
    with client.session_transaction() as sess:
        return ' '.join(m for _, m in sess.get('_flashes', []))


def run(app, s):
    guest = app.test_client()
    citizen = app.test_client()
    as_citizen(citizen, s)
    officer = app.test_client()
    as_officer(officer, s)
    cenro = app.test_client()
    base.as_cenro(cenro, s)
    dagupan = app.test_client()
    base.login(dagupan, s.dagupan_admin_id, s.dagupan_admin_name, 'admin', 'Dagupan')
    superadmin = app.test_client()
    base.login(superadmin, s.superadmin_id, s.superadmin_name, 'superadmin', None)
    box = mailer.outbox()

    # --- 1. documents ---------------------------------------------------
    step = '1 documents'
    before = Request.query.count()
    citizen.post('/requests', data=request_form(),
                 content_type='multipart/form-data')
    check(step, 'refused with no document', Request.query.count() == before)
    citizen.post('/requests', data=request_form(attachments=[pdf('virus.exe')]),
                 content_type='multipart/form-data')
    check(step, 'refused when no file is an allowed type',
          Request.query.count() == before)
    r = citizen.post('/requests', data=request_form(attachments=[pdf()]),
                     content_type='multipart/form-data')
    base.fresh()
    check(step, 'accepted with a PDF', Request.query.count() == before + 1, r.status_code)
    saved = Request.query.order_by(Request.request_id.desc()).first()
    check(step, 'the document is stored', len(saved.attachments) == 1)
    page = citizen.get('/requests').get_data(as_text=True)
    check(step, 'the form marks it required', 'Attach at least one' in page)

    # --- 2. when a site can be made ---------------------------------------
    step = '2 create site'
    submitted = new_request(s, status='Submitted')
    url = '/admin/requests/%d/create-site' % submitted
    cenro.post(url, data=site_form(s, 'From Submitted'))
    base.fresh()
    check(step, 'refused while Submitted',
          Site.query.filter_by(site_name='From Submitted').count() == 0)
    page = cenro.get('/admin/requests/%d' % submitted).get_data(as_text=True)
    check(step, 'request page says to mark it Under Review first',
          'Mark the request Under Review first' in page and url not in page)

    req_id = new_request(s)
    url = '/admin/requests/%d/create-site' % req_id
    page = cenro.get('/admin/requests/%d' % req_id).get_data(as_text=True)
    check(step, 'request page offers it while Under Review',
          url in page and 'Create temporary site and assign an officer' in page)
    page = cenro.get(url).get_data(as_text=True)
    check(step, 'the form opens, with the officer list and the documents',
          'Create Temporary Site' in page and s.officer_name in page
          and 'management-plan.pdf' in page)
    cenro.post(url, data=site_form(s, 'No Officer', officer_id=''))
    base.fresh()
    check(step, 'refused with no officer',
          Site.query.filter_by(site_name='No Officer').count() == 0)
    cenro.post(url, data=site_form(s, 'Wrong Officer', officer_id=str(s.cenro_admin_id)))
    base.fresh()
    check(step, 'refused when the person is not a field officer',
          Site.query.filter_by(site_name='Wrong Officer').count() == 0)
    page = cenro.post(url, data=site_form(s, 'Keeps Values', officer_id='')
                      ).get_data(as_text=True)
    check(step, 'an error keeps what was typed', 'Keeps Values' in page)
    dagupan.post(url, data=site_form(s, 'Other CENRO'))
    base.fresh()
    check(step, 'another CENRO cannot create it',
          Site.query.filter_by(site_name='Other CENRO').count() == 0)
    box.clear()
    cenro.post(url, data=site_form(s, 'Good Site'))
    base.fresh()
    site = Site.query.filter_by(site_name='Good Site').first()
    check(step, 'created while Under Review', site is not None)
    if site is None:
        return
    good_id = site.site_id
    check(step, 'the request stays Under Review',
          db.session.get(Request, req_id).status == 'Under Review')
    a = VisitAssignment.query.filter_by(site_id=good_id).first()
    check(step, 'the assignment is open, with the note',
          a is not None and a.status == 'Open' and 'captain' in (a.note or ''))
    check(step, 'the officer is notified and emailed',
          Notification.query.filter_by(user_id=s.officer_id, site_id=good_id).count() == 1
          and any(m.get('to') == [s.officer_name + '@synthetic.test'] for m in box))
    page = cenro.get('/admin/requests/%d' % req_id).get_data(as_text=True)
    check(step, 'request page links to the visits and names the officer',
          '/sites/%d/visits' % good_id in page and 'Assigned to visit' in page)

    approved = new_request(s, status='Approved')
    cenro.post('/admin/requests/%d/create-site' % approved,
               data=site_form(s, 'From Approved'))
    base.fresh()
    check(step, 'an Approved request still works',
          Site.query.filter_by(site_name='From Approved').count() == 1)

    # --- 3. organization filter -------------------------------------------
    step = '3 organizations'
    elsewhere = Organization(organization_name='Bonuan Only Org',
                             organization_type='POs')
    db.session.add(elsewhere)
    db.session.flush()
    bonuan = Location.query.filter_by(barangay='Bonuan').first()
    db.session.add(Site(location_id=bonuan.location_id,
                        organization_id=elsewhere.organization_id,
                        site_name='Bonuan Org Site', area_size_ha=1.0, cenro='Dagupan'))
    unsited = Organization(organization_name='No Sites Org', organization_type='POs')
    db.session.add(unsited)
    db.session.commit()
    elsewhere_id = elsewhere.organization_id
    org_req = new_request(s)
    page = cenro.get('/admin/requests/%d/create-site' % org_req).get_data(as_text=True)
    check(step, "an organization in the barangay is listed",
          'Synthetic Peoples Organization' in page)
    check(step, 'one from another barangay is not',
          'Bonuan Only Org' not in page and 'No Sites Org' not in page)
    check(step, 'the page says how the list works',
          'Only organizations in this barangay are listed' in page)
    cenro.post('/admin/requests/%d/create-site' % org_req, data=site_form(
        s, 'Bad Org', new_organization='', organization_id=str(elsewhere_id)))
    base.fresh()
    check(step, 'posting one from another barangay is refused',
          Site.query.filter_by(site_name='Bad Org').count() == 0)

    # --- 4. the officer's view, re-assigning ---------------------------------
    step = '4 assignments'
    page = officer.get('/sites/%d/visits' % good_id).get_data(as_text=True)
    check(step, 'the officer sees the request details',
          'Maria Santos' in page and 'management-plan.pdf' in page)
    page = officer.get('/site-visits').get_data(as_text=True)
    check(step, 'it is under Assigned to you', 'Assigned to you' in page
          and 'Good Site' in page)
    a_id = VisitAssignment.query.filter_by(site_id=good_id).first().assignment_id
    officer.post('/assignments/%d/cancel' % a_id)
    base.fresh()
    check(step, 'an officer cannot withdraw it',
          db.session.get(VisitAssignment, a_id).status == 'Open')
    dagupan.post('/assignments/%d/cancel' % a_id)
    base.fresh()
    check(step, 'another CENRO cannot withdraw it',
          db.session.get(VisitAssignment, a_id).status == 'Open')
    cenro.post('/assignments/%d/cancel' % a_id)
    base.fresh()
    check(step, 'the CENRO withdraws it',
          db.session.get(VisitAssignment, a_id).status == 'Cancelled')
    check(step, 'the officer can no longer record a visit',
          officer.get('/sites/%d/visits/new' % good_id).status_code == 302)
    check(step, 'and is told',
          Notification.query.filter(Notification.user_id == s.officer_id,
                                    Notification.site_id == good_id,
                                    Notification.message.like('%was%')).count() >= 1)
    cenro.post('/sites/%d/assignments' % good_id, data={
        'officer_id': str(s.officer_id), 'visit_type': 'Pre-planting check',
        'target_date': '2000-01-01', 'note': ''})
    base.fresh()
    check(step, 'a target date in the past is refused',
          VisitAssignment.query.filter_by(site_id=good_id, status='Open').count() == 0)
    cenro.post('/sites/%d/assignments' % good_id, data={
        'officer_id': str(s.officer_id), 'visit_type': 'Pre-planting check',
        'target_date': '', 'note': 'Second try.'})
    base.fresh()
    check(step, 'the CENRO can assign again',
          VisitAssignment.query.filter_by(site_id=good_id, status='Open').count() == 1)

    # --- 5. a rejected visit goes back to the officer -------------------------
    step = '5 rejected visit'
    today = datetime.now(ZoneInfo('Asia/Manila')).date()
    officer.post('/sites/%d/visits/new' % good_id, data={
        'visit_date': today.isoformat(), 'visit_type': 'Pre-planting check',
        'finding': 'Suitable', 'land_matches': 'yes', 'ownership_confirmed': 'yes',
        'accessible': 'yes', 'remarks': 'Looks fine.',
    }, content_type='multipart/form-data')
    base.fresh()
    visit = SiteVisit.query.filter_by(site_id=good_id).first()
    check(step, 'the visit is saved', visit is not None)
    if visit is not None:
        cenro.post('/visits/%d/review' % visit.visit_id,
                   data={'status': 'Rejected', 'review_note': 'Too few details.'})
        base.fresh()
        reopened = VisitAssignment.query.filter_by(site_id=good_id, status='Open').first()
        check(step, 'rejecting it opens the assignment again',
              reopened is not None and reopened.visit_id is None)
        check(step, 'the officer can record it again',
              officer.get('/sites/%d/visits/new' % good_id).status_code == 200)
        check(step, 'the request stays Under Review',
              db.session.get(Request, req_id).status == 'Under Review')

    # --- 6. cancelling --------------------------------------------------------
    step = '6 cancel'
    page = citizen.get('/requests?status=all').get_data(as_text=True)
    check(step, 'no Cancel button once a site exists',
          '/requests/%d/cancel' % req_id not in page, req_id)
    citizen.post('/requests/%d/cancel' % req_id)
    base.fresh()
    check(step, 'posting a cancel is refused too',
          db.session.get(Request, req_id) is not None)

    # --- 7. official figures ---------------------------------------------------
    step = '7 official figures'
    base.fresh()
    official = official_sites(Site.query)
    check(step, 'a temporary site is left out',
          official.filter(Site.site_id == good_id).count() == 0)
    check(step, 'an imported DENR site is kept',
          official.filter(Site.site_id == s.site_a_id).count() == 1)
    from_approved = Site.query.filter_by(site_name='From Approved').first()
    check(step, 'a site whose request is Approved is counted',
          official.filter(Site.site_id == from_approved.site_id).count() == 1)

    # --- 8. rejecting a request closes its site ----------------------------------
    step = '8 reject'
    rej_req, rej_site = make_site(cenro, s, 'To Reject')
    cenro.post('/admin/requests/%d/review' % rej_req,
               data={'status': 'Rejected', 'review_note': 'Protected area.'})
    base.fresh()
    check(step, 'the request is rejected',
          db.session.get(Request, rej_req).status == 'Rejected')
    check(step, 'the site is closed',
          db.session.get(Site, rej_site).site_status == 'Not Suitable')
    check(step, 'the assignment is withdrawn',
          VisitAssignment.query.filter_by(site_id=rej_site, status='Open').count() == 0)
    cenro.post('/admin/requests/%d/review' % rej_req, data={'status': 'Approved'})
    base.fresh()
    check(step, 'a closed site cannot be approved again',
          db.session.get(Request, rej_req).status == 'Rejected')

    # archived: off the site lists, kept on record, open from Site Visits
    step = '8b archived'
    rows = officer.get('/api/sites-in-barangay?municipality=Villasis&barangay=Bacag').get_json()
    ids = [r['site_id'] for r in rows]
    check(step, "off the map's barangay list and the report form's site list",
          rej_site not in ids and good_id in ids, ids)
    page = cenro.get('/sites').get_data(as_text=True)
    check(step, 'off the Reforestation Sites page, which says one is archived',
          'data-site-name="To Reject"' not in page
          and 'data-site-name="Good Site"' in page
          and '1 archived site not listed' in page,
          re.findall(r'\d+ archived site[^<]*', page))
    page = cenro.get('/site-visits').get_data(as_text=True)
    check(step, 'still listed in Site Visits, marked archived',
          'To Reject' in page and 'Archived: not suitable' in page)
    check(step, 'its page still opens, with its history',
          cenro.get('/sites/%d/visits' % rej_site).status_code == 200)
    check(step, 'the record is kept', db.session.get(Site, rej_site) is not None)
    before = MonitoringReport.query.count()
    officer.post('/reports/submit', data={
        'site_id': str(rej_site), 'monitoring_date': today.isoformat(),
        'plot_count': ['10'], 'plot_note': [''], 'remarks': 'archived site',
    }, content_type='multipart/form-data')
    check(step, 'a monitoring report for it is refused',
          MonitoringReport.query.count() == before)
    officer.post('/reports/submit', data={
        'site_id': str(s.site_c_id), 'monitoring_date': today.isoformat(),
        'plot_count': ['10'], 'plot_note': [''], 'remarks': 'other cenro',
    }, content_type='multipart/form-data')
    check(step, "a report for another CENRO's site is refused",
          MonitoringReport.query.count() == before)

    # --- 9. email verification ---------------------------------------------------
    step = '9 verification'
    bacag = Location.query.filter_by(barangay='Bacag').first()
    box.clear()
    r = guest.post('/register', data={
        'username': 'new_resident', 'email_address': 'new@synthetic.test',
        'password': PASSWORD, 'confirmPassword': PASSWORD,
        'location_id': str(bacag.location_id), 'organization_id': '',
    })
    base.fresh()
    user = User.query.filter_by(username='new_resident').first()
    check(step, 'sign-up creates an unverified account',
          user is not None and user.email_verified is False, r.status_code)
    if user is None:
        return
    uid = user.user_id
    mail = box[-1] if box else {}
    link = link_in(mail, 'verify-email')
    check(step, 'the link is emailed to the address',
          mail.get('to') == ['new@synthetic.test'] and link, mail)
    check(step, 'the password is not in the email',
          PASSWORD not in mail.get('text', '') and PASSWORD not in (mail.get('html') or ''))

    def try_login():
        client = app.test_client()
        resp = client.post('/login', data={'username': 'new_resident',
                                           'password': PASSWORD})
        with client.session_transaction() as sess:
            return resp, sess.get('user_id')

    resp, signed_in = try_login()
    page = resp.get_data(as_text=True)
    check(step, 'sign-in is refused until verified', signed_in is None)
    check(step, 'and offers a new link', '/resend-verification' in page)
    wrong = app.test_client().post('/login', data={'username': 'new_resident',
                                                   'password': 'wrong-password1'})
    check(step, 'a wrong password does not reveal the account is unverified',
          '/resend-verification' not in wrong.get_data(as_text=True))

    r = guest.get(link[:-3] + 'abc')
    base.fresh()
    check(step, 'a tampered link is refused',
          'not valid' in r.get_data(as_text=True)
          and db.session.get(User, uid).email_verified is False)

    time.sleep(1.1)
    hours = app.config['EMAIL_VERIFY_HOURS']
    app.config['EMAIL_VERIFY_HOURS'] = 0
    r = guest.get(link)
    app.config['EMAIL_VERIFY_HOURS'] = hours
    base.fresh()
    check(step, 'an expired link is refused',
          'expired' in r.get_data(as_text=True)
          and db.session.get(User, uid).email_verified is False)

    check(step, 'the resend page opens',
          guest.get('/resend-verification').status_code == 200)
    box.clear()
    guest.post('/resend-verification', data={'email_address': 'new@synthetic.test'})
    check(step, 'resend is limited, so it cannot be used to flood an inbox',
          len(box) == 0, len(box))
    auth_routes._last_verify_email.clear()
    box.clear()
    known = app.test_client()
    known.post('/resend-verification', data={'email_address': ' NEW@synthetic.test '})
    known_msg = flashes(known)
    check(step, 'resend sends a new link', len(box) == 1 and link_in(box[-1], 'verify-email'))
    box.clear()
    unknown = app.test_client()
    unknown.post('/resend-verification', data={'email_address': 'nobody@synthetic.test'})
    check(step, 'an unknown address gets nothing, and the same answer',
          len(box) == 0 and flashes(unknown) == known_msg)
    verified = app.test_client()
    verified.post('/resend-verification', data={'email_address': s.officer_name + '@synthetic.test'})
    check(step, 'a verified address gets nothing', len(box) == 0)

    r = guest.get(link)
    base.fresh()
    check(step, 'the link verifies the account',
          r.status_code == 302 and db.session.get(User, uid).email_verified is True)
    resp, signed_in = try_login()
    check(step, 'sign-in now works', signed_in == uid, signed_in)
    r = guest.get(link)
    check(step, 'opening the link twice is harmless', r.status_code == 302)

    stuck = User(username='stuck_user', email_address='stuck@synthetic.test',
                 role='normal_user', email_verified=False, is_active=True)
    stuck.set_password(PASSWORD)
    db.session.add(stuck)
    db.session.commit()
    stuck_id = stuck.user_id
    superadmin.post('/admin/users/%d/reset-password' % stuck_id,
                    data={'new_password': PASSWORD, 'password': PASSWORD,
                          'confirm_password': PASSWORD})
    base.fresh()
    check(step, 'an admin password reset unlocks a stuck account',
          db.session.get(User, stuck_id).email_verified is True)

    box.clear()
    superadmin.post('/admin/users/create', data={
        'username': 'new_officer', 'email_address': 'newofficer@synthetic.test',
        'password': PASSWORD, 'role': 'field_officer', 'cenro': 'Urdaneta City',
    })
    base.fresh()
    created = User.query.filter_by(username='new_officer').first()
    check(step, 'an admin-created account is usable right away',
          created is not None and created.email_verified is True)
    mail = box[-1] if box else {}
    check(step, 'its owner is emailed that it was created',
          mail.get('to') == ['newofficer@synthetic.test'], mail)
    check(step, 'without the password',
          PASSWORD not in mail.get('text', '') and PASSWORD not in (mail.get('html') or ''))

    # --- 10. GIS map filters -----------------------------------------------------
    step = '10 GIS filters'
    page = guest.get('/gis-map').get_data(as_text=True)
    check(step, 'no All choice in either row',
          not re.search(r'name="(areaFilter|districtFilter)"\s+value="all"', page))
    check(step, 'None is ticked by default',
          re.search(r'name="districtFilter" value="none" checked', page)
          and re.search(r'name="areaFilter" value="none" checked', page))
    check(step, 'the map starts with no colour',
          'let showDistrictFill = false;' in page)


def print_results():
    print()
    print('NEW-SITE REQUEST FLOW AND EMAIL VERIFICATION  (synthetic data)')
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
    app.config['APP_BASE_URL'] = 'http://localhost'

    temp = os.path.join(base.TMPDIR, 'static')
    real_doc = dashboard_routes.save_request_file
    dashboard_routes.save_request_file = (
        lambda f, _static, key, index: real_doc(f, temp, key, index))
    real_photo = visits_routes.save_photo
    visits_routes.save_photo = (
        lambda f, _static, key, index: real_photo(f, temp, key, index))

    failed = 1
    try:
        with app.app_context():
            db.create_all()
            s = base.seed()
            run(app, s)
            failed = print_results()
    finally:
        dashboard_routes.save_request_file = real_doc
        visits_routes.save_photo = real_photo
        shutil.rmtree(base.TMPDIR, ignore_errors=True)

    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
