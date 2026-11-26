"""
One dashboard per role (Module 5).

Runs the real Flask routes against a throwaway SQLite database.

WHAT IS UNDER TEST

    1  each role gets its own page; the admin page is for CENRO and provincial staff
    2  the admin analytics endpoint refuses everyone who is not admin (403)
    3  a person with no barangay is told, with a link to set it in My Account
    4  My Account sets the barangay; a made-up id is refused
    5  the story sentence: real numbers, and no 0% for a missing survival figure
    6  the leader's gauge leaves out sites under review, and marks below-target rows
    7  the officer's overdue count: an open assignment past its date with no visit
    8  the tour: a new user gets every step; a user of an older version gets only
       the new steps; a finished current user gets nothing automatic
    9  the tour records its version when it is finished

RUN

    python tests/test_dashboards.py

Exit code 0 when every check passes, 1 otherwise.
"""

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# importing this first points DATABASE_URL at a temporary SQLite file
import test_publish_boundary as base                    # noqa: E402
from app.extensions import db                            # noqa: E402
from app.models import (                                 # noqa: E402
    Location, Organization, ReforestationRecord, Request, Site, SiteVisit,
    TreeSpecie, User, VisitAssignment,
)
from app.utils.organization import ensure_join_token    # noqa: E402
from app.utils.timeutil import manila_now               # noqa: E402

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append({'name': name, 'ok': bool(ok)})
    print(('PASS  ' if ok else 'FAIL  ') + name
          + (f'  [{detail}]' if detail and not ok else ''))
    return bool(ok)


def make_user(username, role='normal_user', cenro=None, org_id=None,
              org_role=None, org_status=None, location_id=None,
              verified=True):
    u = User(username=username, email_address=f'{username}@example.test',
             role=role, cenro=cenro, organization_id=org_id,
             org_role=org_role, org_status=org_status,
             location_id=location_id, email_verified=verified)
    u.set_password('Synthetic-pass-1')
    db.session.add(u)
    db.session.flush()
    return u.user_id


def add_site(name, location_id, org_id, survival=None, actual=0, target=100,
             year=2025, request_status=None, tree_id=None):
    req_id = None
    if request_status is not None:
        req = Request(user_id=db.session.query(User.user_id).first()[0],
                      location_id=location_id,
                      request_type='New Planting Site', status=request_status,
                      contact_name='Maria Santos',
                      contact_email='maria@synthetic.test')
        db.session.add(req)
        db.session.flush()
        req_id = req.request_id
    site = Site(location_id=location_id, organization_id=org_id,
                site_name=name, site_code=name.replace(' ', '-'), area_size_ha=1.0,
                site_status='Active', year_contracted=year,
                source_request_id=req_id)
    db.session.add(site)
    db.session.flush()
    db.session.add(ReforestationRecord(
        site_id=site.site_id, tree_id=tree_id,
        date_planted=date(year, 6, 1), target_quantity=target,
        actual_quantity_planted=actual, survival_rate=survival))
    db.session.flush()
    return site.site_id


def run(app):
    s = base.seed()
    tree = TreeSpecie.query.first()
    tree_id = tree.tree_id if tree else None
    bacag = Location.query.filter_by(barangay='Bacag').first()
    bacag_id = bacag.location_id
    org_id = db.session.query(Organization.organization_id).filter_by(
        organization_name='Synthetic Peoples Organization').scalar()

    # ---- people ----------------------------------------------------------
    indiv = make_user('syn_indiv_d')                       # no barangay
    indiv_b = make_user('syn_indiv_bgy_d', location_id=bacag_id)
    leader = make_user('syn_leader_d', org_id=org_id, org_role='leader',
                       org_status='active', location_id=bacag_id)
    waiting = make_user('syn_waiting_d', org_id=org_id, org_role='member',
                        org_status='pending', location_id=bacag_id)
    officer_id = s.officer_id
    db.session.commit()

    # ---- sites -------------------------------------------------------------
    # an official site below target, and one that is still under review
    below_id = add_site('Dash Below Site', bacag_id, org_id, survival=60.0,
                        actual=80, target=100, tree_id=tree_id)
    add_site('Dash Under Review Site', bacag_id, org_id, survival=10.0,
             actual=5, target=50, request_status='Under Review',
             tree_id=tree_id)
    add_site('Dash Good Site', bacag_id, org_id, survival=90.0, actual=200,
             target=200, tree_id=tree_id)
    db.session.commit()
    ensure_join_token(db.session.get(Organization, org_id))
    db.session.commit()

    def as_(uid, name, role='normal_user', cenro=None):
        c = app.test_client()
        base.login(c, uid, name, role, cenro)
        return c

    indiv_c = as_(indiv, 'syn_indiv_d')
    indiv_bc = as_(indiv_b, 'syn_indiv_bgy_d')
    leader_c = as_(leader, 'syn_leader_d')
    officer_c = as_(officer_id, s.officer_name, 'field_officer', 'Urdaneta City')
    cenro_c = as_(s.cenro_admin_id, s.cenro_admin_name, 'admin',
                  'Urdaneta City')
    super_c = as_(s.superadmin_id, s.superadmin_name, 'superadmin', None)

    # ------------------------------------------------------------------
    # 1-2. one page per role; the admin analytics endpoint is admin-only
    # ------------------------------------------------------------------
    page = indiv_c.get('/dashboard').get_data(as_text=True)
    check('1 a member gets the member page',
          'What you need to know today.' in page)
    page = officer_c.get('/dashboard').get_data(as_text=True)
    check('1 a field officer gets the to-do page', 'To do' in page)
    page = leader_c.get('/dashboard').get_data(as_text=True)
    check("1 a leader gets the action queue", 'Needs your action' in page)
    page = cenro_c.get('/dashboard').get_data(as_text=True)
    check('1 CENRO staff keep the analytics page',
          'api/dashboard-analytics' in page)
    check('1 a member page does not load the admin chart script',
          'api/dashboard-analytics' not in indiv_c.get('/dashboard').get_data(
              as_text=True))

    check('2 normal user: analytics endpoint 403',
          indiv_c.get('/api/dashboard-analytics').status_code == 403)
    check('2 field officer: analytics endpoint 403',
          officer_c.get('/api/dashboard-analytics').status_code == 403)
    check('2 CENRO admin: analytics endpoint 200',
          cenro_c.get('/api/dashboard-analytics').status_code == 200)
    check('2 superadmin: analytics endpoint 200',
          super_c.get('/api/dashboard-analytics').status_code == 200)
    anon = app.test_client()
    check('2 signed out: sent to sign in',
          anon.get('/api/dashboard-analytics').status_code == 302)

    # ------------------------------------------------------------------
    # 3-4. no barangay, and My Account sets it
    # ------------------------------------------------------------------
    page = indiv_c.get('/dashboard').get_data(as_text=True)
    check('3 no barangay: a message with a link to My Account',
          'Your barangay is not set yet' in page
          and 'href="/account#barangay"' in page)

    r = indiv_c.post('/account/barangay', data={'location_id': str(bacag_id)})
    db.session.remove()
    check('4 My Account saves a barangay',
          db.session.get(User, indiv).location_id == bacag_id)
    check('4 saving sends them back to the barangay panel',
          r.status_code == 302 and r.headers.get('Location', '').endswith(
              '/account#barangay'))
    indiv_c.post('/account/barangay', data={'location_id': '999999'})
    db.session.remove()
    check('4 a made-up barangay id is refused, nothing changes',
          db.session.get(User, indiv).location_id == bacag_id)
    check('4 the account page has the barangay panel',
          'Your barangay' in indiv_c.get('/account').get_data(as_text=True))

    # ------------------------------------------------------------------
    # 5. the story: real numbers, no fake 0%
    # ------------------------------------------------------------------
    page = indiv_bc.get('/dashboard').get_data(as_text=True)
    check('5 the story names the barangay and the survival',
          'in Bacag, Villasis' in page and 'Survival is' in page)
    check('5 a missing survival figure is never shown as 0%',
          '0%' not in page.split('Survival')[0])

    empty = Location(psgc_code='SYN-EMPTY-D', region='Region I',
                     province='Pangasinan', municipality='Villasis',
                     barangay='Empty Barangay', latitude=15.95,
                     longitude=120.62, elevation_m=40.0)
    db.session.add(empty)
    db.session.flush()
    nobody = make_user('syn_empty_d', location_id=empty.location_id)
    db.session.commit()
    page = as_(nobody, 'syn_empty_d').get('/dashboard').get_data(as_text=True)
    check('5 a barangay with no sites says so',
          'No reforestation sites in' in page)

    # ------------------------------------------------------------------
    # 6. the leader's gauge and table
    # ------------------------------------------------------------------
    page = leader_c.get('/dashboard').get_data(as_text=True)
    check('6 the leader sees one waiting member in the queue',
          'waiting to join' in page)
    check('6 the under-review site is labelled, not counted',
          'Under review' in page and 'Dash Under Review Site' in page)
    check('6 a below-target row is highlighted',
          'rgba(185,28,28,0.08)' in page)
    # the gauge figure: the official sites only (60 and 90 -> 75%)
    check('6 the gauge uses the official sites only (75%)',
          '75% survival' in page, 'gauge line not found')

    # ------------------------------------------------------------------
    # 7. the officer's overdue count
    # ------------------------------------------------------------------
    overdue_site = add_site('Dash Overdue Site', bacag_id, org_id,
                            tree_id=tree_id)
    done_site = add_site('Dash Visited Site', bacag_id, org_id,
                         tree_id=tree_id)
    db.session.flush()
    yesterday = manila_now().date() - timedelta(days=1)
    past_created = manila_now() - timedelta(days=10)
    db.session.add(VisitAssignment(
        site_id=overdue_site, officer_id=officer_id, assigned_by=s.cenro_admin_id,
        visit_type='Pre-planting check', target_date=yesterday, status='Open',
        created_at=past_created))
    db.session.add(VisitAssignment(
        site_id=done_site, officer_id=officer_id, assigned_by=s.cenro_admin_id,
        visit_type='Pre-planting check', target_date=yesterday, status='Open',
        created_at=past_created))
    db.session.add(SiteVisit(
        site_id=done_site, user_id=officer_id,
        visit_date=manila_now().date(),
        visit_type='Pre-planting check', finding='Suitable', status='Pending'))
    db.session.commit()
    page = officer_c.get('/dashboard').get_data(as_text=True)
    check('7 an open assignment past its date with no visit is overdue',
          'Dash Overdue Site' in page and 'Overdue' in page)
    import re as _re
    row = _re.search(r'<tr[^>]*>(?:(?!</tr>).)*Dash Visited Site(?:(?!</tr>).)*</tr>', page, _re.S)
    check('7 a visited assignment is not overdue',
          row is not None and '>Open<' in row.group(0))
    check('7 a visit awaiting approval is a neutral tile, not an alert',
          'Awaiting approval' in page)

    # ------------------------------------------------------------------
    # 8-9. the tour: versions
    # ------------------------------------------------------------------
    fresh = make_user('syn_fresh_tour_d', location_id=bacag_id)
    old = make_user('syn_old_tour_d', location_id=bacag_id)
    current = make_user('syn_current_tour_d', location_id=bacag_id)
    db.session.commit()
    from datetime import datetime as _dt
    db.session.remove()
    db.session.get(User, old).tour_completed_at = manila_now()
    db.session.get(User, old).tour_version = None
    db.session.get(User, current).tour_completed_at = manila_now()
    db.session.get(User, current).tour_version = 2
    db.session.commit()

    page = as_(fresh, 'syn_fresh_tour_d').get('/dashboard').get_data(as_text=True)
    check('8 a new user gets the full tour automatically',
          'window.startTour(false)' in page)
    page = as_(old, 'syn_old_tour_d').get('/dashboard').get_data(as_text=True)
    check('8 a user of an older version gets only the new steps',
          'window.startTour(true)' in page)
    page = as_(current, 'syn_current_tour_d').get('/dashboard').get_data(
        as_text=True)
    check('8 a user on the current version gets no automatic tour',
          'window.startTour(false)' not in page
          and 'window.startTour(true)' not in page)

    db.session.remove()
    client_old = as_(old, 'syn_old_tour_d')
    client_old.post('/api/tour/done', headers={'X-CSRFToken': 'x'})
    db.session.remove()
    check('9 finishing the tour records the current version',
          db.session.get(User, old).tour_version == 2)


def main():
    app = base.create_app()
    app.config['TESTING'] = True
    app.config['MAIL_SERVER'] = ''
    app.config['APP_BASE_URL'] = 'http://localhost'
    # Forms are posted without a CSRF token here; CSRF has its own test.
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
