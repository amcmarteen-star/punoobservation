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

import json
import os
import re
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


from app.utils.tour import TOUR_VERSION  # noqa: E402


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
    check('1 CENRO staff get the CENRO dashboard',
          'class="cd-story"' in page)
    member_page = indiv_c.get('/dashboard').get_data(as_text=True)
    check('1 a member page does not load the admin charts',
          'cd-gauge' not in member_page and 'chart.umd' not in member_page)

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
    db.session.get(User, current).tour_version = TOUR_VERSION
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
          db.session.get(User, old).tour_version == TOUR_VERSION == 3)

    run_profile(app, as_, indiv, leader)
    run_tour_branches(app, as_, s, indiv, waiting, leader, org_id, bacag_id)
    run_faq(app, as_, s, indiv, leader, org_id)
    run_user_management(app, as_, s, org_id)


def run_user_management(app, as_, s, org_id):
    """11 User Management labels; a User's CENRO grants nothing."""
    sa = as_(s.superadmin_id, s.superadmin_name, 'superadmin')

    # a User created with a CENRO is stored without one
    sa.post('/admin/users/create', data={
        'username': 'syn_um_user', 'email_address': 'syn_um_user@example.test',
        'password': 'Synthetic-pass-1', 'role': 'normal_user',
        'cenro': 'Urdaneta City'})
    db.session.remove()
    made = User.query.filter_by(username='syn_um_user').first()
    check('11 creating a User never stores a CENRO',
          made is not None and made.cenro is None, made and made.cenro)

    # the data error: a leader with users.cenro set
    bad = make_user('syn_um_bad_leader', cenro='Urdaneta City', org_id=org_id,
                    org_role='leader', org_status='active')
    pend = make_user('syn_um_pending', org_id=org_id, org_role='member',
                     org_status='pending')
    db.session.commit()
    c = as_(bad, 'syn_um_bad_leader', 'normal_user', 'Urdaneta City')
    plain = as_(pend, 'syn_um_pending', 'normal_user', None)
    check('11 a User with a CENRO cannot open Review Requests',
          c.get('/admin/requests').status_code != 200)
    check('11 a User with a CENRO cannot open the Organizations list',
          c.get('/org/organizations').status_code in (302, 403))
    with app.test_request_context():
        from flask import session as fs
        from app.utils.jurisdiction import current_cenro
        fs['role'], fs['cenro'] = 'normal_user', 'Urdaneta City'
        check('11 current_cenro() ignores a User\'s CENRO', current_cenro() is None)
    count = lambda cl: re.search(r'id="sites-count">(\d+)<',
                                 cl.get('/sites').get_data(as_text=True))
    a1, a2 = count(c), count(plain)
    check('11 a User with a CENRO sees the same sites as one without',
          a1 and a2 and a1.group(1) == a2.group(1),
          f'{a1 and a1.group(1)} vs {a2 and a2.group(1)}')

    page = sa.get('/admin/user-management').get_data(as_text=True)
    rows = [r.split('</tr>')[0] for r in page.split('<tr data-role')[1:]]
    def row(name):
        return next((r for r in rows
                     if re.search(r'um-name">\s*' + re.escape(name) + r'\s*<', r)), '')
    r_bad = row('syn_um_bad_leader')
    check('11 a User never shows a jurisdiction',
          r_bad and 'CENRO Urdaneta City' not in r_bad, r_bad[:200])
    check('11 a User with no org shows "Individual"', 'Individual' in row('syn_um_user'))
    r_sa = row(s.superadmin_name)
    check('11 staff show "—" for partner organization',
          r_sa and 'Individual' not in r_sa and '&mdash;' in r_sa)
    r_p = row('syn_um_pending')
    check('11 Pending Member badge is neutral grey',
          'role-pending' in r_p and 'Pending Member' in r_p)
    check('11 org name has a full-text tooltip and a 2-line clamp',
          re.search(r'class="um-role um-org[^"]*"[^>]*title="Partner Org Leader', r_bad)
          is not None and '-webkit-line-clamp: 2' in page)


def tour_steps(page, name='STEPS'):
    m = re.search(r'const ' + name + r' = (\[.*?\]);\n', page, re.S)
    return json.loads(m.group(1)) if m else None


def run_tour_branches(app, as_, s, indiv, waiting, leader, org_id, bacag_id):
    """12 one tour branch per role, at most 6 steps, role-specific words."""
    member = make_user('syn_tour_member_d', org_id=org_id, org_role='member',
                       org_status='active', location_id=bacag_id)
    db.session.commit()
    who = {
        'Individual': (as_(indiv, 'syn_indiv_d'), 'You are an Individual'),
        'Pending Member': (as_(waiting, 'syn_waiting_d'), 'Pending Member'),
        'Partner Org Member': (as_(member, 'syn_tour_member_d'), 'Partner Org Member of'),
        'Partner Org Leader': (as_(leader, 'syn_leader_d'), 'Partner Org Leader of'),
        'Field Officer': (as_(s.officer_id, s.officer_name, 'field_officer',
                              'Urdaneta City'), 'You are a Field Officer'),
        'CENRO Administrator': (as_(s.cenro_admin_id, s.cenro_admin_name, 'admin',
                                    'Urdaneta City'), 'CENRO Administrator'),
        'Provincial Administrator': (as_(s.penro_id, s.penro_name, 'admin', None),
                                     'Provincial Administrator'),
        'System Administrator': (as_(s.superadmin_id, s.superadmin_name,
                                     'superadmin', None), 'System Administrator'),
    }
    for label, (client, words) in who.items():
        page = client.get('/dashboard').get_data(as_text=True)
        steps = tour_steps(page)
        new = tour_steps(page, 'NEW_STEPS')
        check(f'12 {label}: own tour branch, at most 6 steps',
              steps is not None and 1 <= len(steps) <= 6
              and words in steps[0]['text'], steps and steps[0]['text'])
        check(f'12 {label}: version-3 steps exist for returning users',
              new is not None and len(new) >= 1
              and all(x.get('v') == 3 for x in new))
        check(f'12 {label}: no "Normal User" in the tour',
              steps is not None and 'Normal User' not in json.dumps(steps))
    lp = who['Partner Org Leader'][0].get('/dashboard').get_data(as_text=True)
    check('12 leader tour points at the request queue on the dashboard',
          '"#dash-queue"' in lp and 'id="dash-queue"' in lp)


def run_faq(app, as_, s, indiv, leader, org_id):
    """13 FAQ: required entries, role-specific dashboard, real behaviour."""
    ic = as_(indiv, 'syn_indiv_d')
    lc = as_(leader, 'syn_leader_d')
    sa = as_(s.superadmin_id, s.superadmin_name, 'superadmin')
    officer = as_(s.officer_id, s.officer_name, 'field_officer', 'Urdaneta City')
    cenro = as_(s.cenro_admin_id, s.cenro_admin_name, 'admin', 'Urdaneta City')
    # The Recommendations page itself fails on a barangay with no rainfall
    # (a separate, older bug), so its FAQ partial is rendered on its own.
    from flask import render_template
    with app.test_request_context('/recommendations'):
        recs = render_template('partials/faq/_recommendations.html')
    pages = {
        'recs': recs,
        'requests': ic.get('/requests').get_data(as_text=True),
        'org': lc.get('/org/members').get_data(as_text=True),
        'gis': ic.get('/gis-map').get_data(as_text=True),
        'dash_user': ic.get('/dashboard').get_data(as_text=True),
        'dash_admin': cenro.get('/dashboard').get_data(as_text=True),
        'dash_officer': officer.get('/dashboard').get_data(as_text=True),
        'reports': officer.get('/reports').get_data(as_text=True),
        'visits': officer.get('/site-visits').get_data(as_text=True),
        'review': cenro.get('/admin/requests').get_data(as_text=True),
    }
    need = [
        ('org', "I don&#39;t have an invite link", "I don't have an invite link"),
        ('org', 'My approval is taking long', None),
        ('requests', "Why can&#39;t I request a site?", "Why can't I request a site?"),
        ('requests', 'What does Returned for revision mean?', None),
        ('org', 'How do I invite members?', None),
        ('gis', 'Why is a location approximate?', None),
        ('gis', 'What is simulated data?', None),
        ('dash_admin', 'What is simulated data?', None),
        ('reports', 'Why was my photo marked No GPS?', None),
        ('visits', 'What does Not suitable do?', None),
        ('dash_user', 'What do the dashboard numbers mean?', None),
    ]
    for page, q, alt in need:
        html = pages[page]
        check(f'13 FAQ "{alt or q}" on {page}',
              f'<summary>{q}</summary>' in html
              or (alt and f'<summary>{alt}</summary>' in html))
    check('13 dashboard FAQ: users do not get admin chart entries',
          'What is cost per hectare?' not in pages['dash_user']
          and 'What is cost per hectare?' in pages['dash_admin'])
    check('13 dashboard FAQ: officers get their own numbers',
          'Visits this week:' in pages['dash_officer']
          and 'Official sites:' not in pages['dash_officer'])
    from app.models import SpeciesCategory
    tagged = SpeciesCategory.query.count() > 0
    check('13 purpose filter FAQ matches whether species are classified',
          ('Species purposes are not classified yet' in pages['recs']) != tagged)
    with app.test_request_context('/recommendations'):
        SpeciesCategory.query.delete()
        none_page = render_template('partials/faq/_recommendations.html')
        db.session.rollback()
    check('13 with no category rows it says purposes are not classified yet',
          'Species purposes are not classified yet' in none_page)
    st = pages['requests']
    check('13 request statuses FAQ has the organization and CENRO stages',
          all(x in st for x in ('<strong>Pending Org Approval:</strong>',
                                '<strong>Returned:</strong>',
                                '<strong>Pending CENRO:</strong>')))
    check('13 Review Requests FAQ explains the three groups',
          'Needs your action' in pages['review'] and 'At organization' in pages['review'])
    allhtml = ' '.join(pages.values()) + sa.get('/admin/user-management').get_data(as_text=True)
    check('13 no "Normal User" on any page checked', 'Normal User' not in allhtml)


def run_profile(app, as_, indiv, leader):
    """10 profile details, request prefill, sidebar org line."""
    from app.utils.profile import normalize_ph_mobile as n
    check('10 PH mobile: spaces, dashes and +63 accepted',
          n('0917 123 4567') == n('0917-123-4567') == n('+639171234567')
          == '09171234567' and n('') == '')
    check('10 PH mobile: wrong length or prefix refused',
          n('0817123456') is None and n('12345') is None and n('091712345678') is None)

    c = as_(indiv, 'syn_indiv_d')
    page = c.get('/requests').get_data(as_text=True)
    name_val = re.search(r'id="contact_name"[^>]*?value="([^"]*)"', page, re.S)
    check('10 empty profile: contact name stays empty, never the username',
          name_val is not None and name_val.group(1) == ''
          and 'value="syn_indiv_d"' not in page)

    c.post('/account/profile', data={'full_name': '  Maria   Santos ',
                                     'contact_number': '0917-123-4567'})
    db.session.remove()
    u = db.session.get(User, indiv)
    check('10 My Account saves full name and number',
          u.full_name == 'Maria Santos' and u.contact_number == '09171234567',
          f'{u.full_name} {u.contact_number}')
    c.post('/account/profile', data={'full_name': 'X', 'contact_number': '12345'})
    db.session.remove()
    check('10 an invalid number is refused, nothing changes',
          db.session.get(User, indiv).full_name == 'Maria Santos')

    page = c.get('/requests').get_data(as_text=True)
    check('10 request form is prefilled from the profile',
          'value="Maria Santos"' in page and 'value="09171234567"' in page
          and f'value="{u.email_address}"' in page)

    lpage = as_(leader, 'syn_leader_d').get('/dashboard').get_data(as_text=True)
    m = re.search(r'class="role-pill-role role-pill-org" title="([^"]+)">([^<]+)<', lpage)
    check('10 sidebar org line carries the full text as a tooltip',
          m is not None and m.group(1) == m.group(2)
          and m.group(1).startswith('Partner Org Leader'))


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
