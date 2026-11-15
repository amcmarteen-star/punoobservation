"""
Site requests: only active organization members may send one.

Runs the real Flask routes against a throwaway SQLite database. Uploads go
to a temporary folder and no email is sent.

WHAT IS UNDER TEST

    1  an individual's POST is refused, and no request row is made
    2  a pending member's POST is refused
    3  a CENRO admin's POST is refused; the page links to Review Requests
    4  a field officer's POST is refused; the page has no link
    5  an active member's POST is saved with the member's own organization,
       even when the form posts a different organization_id
    6  the map's request mode is closed to anyone who may not send a request
    7  a request keeps its organization after the member leaves
    8  Review Requests opens for admins and not for field officers

RUN

    python tests/test_request_org_gate.py

Exit code 0 when every check passes, 1 otherwise.
"""

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# importing this first points DATABASE_URL at a temporary SQLite file
import test_publish_boundary as base                    # noqa: E402
from app.extensions import db                            # noqa: E402
from app.models import Location, Organization, Request, User  # noqa: E402
from app.routes import dashboard as dashboard_routes    # noqa: E402

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append({'name': name, 'ok': bool(ok)})
    print(('PASS  ' if ok else 'FAIL  ') + name
          + (f'  [{detail}]' if detail and not ok else ''))
    return bool(ok)


def pdf():
    return (io.BytesIO(b'%PDF-1.4 synthetic'), 'plan.pdf')


def form(**over):
    data = {
        'request_type': 'Seedling Supply',
        'municipality': 'Villasis', 'barangay': 'Bacag',
        'contact_name': 'Maria Santos', 'contact_number': '09171234567',
        'contact_email': 'maria@synthetic.test',
    }
    data.update(over)
    return data


def post_request(client, **over):
    data = form(attachments=[pdf()], **over)
    return client.post('/requests', data=data,
                       content_type='multipart/form-data')


def request_count():
    db.session.remove()
    return Request.query.count()


def make_user(username, org_id=None, org_status=None, role='normal_user'):
    u = User(username=username, email_address=f'{username}@example.test',
             role=role, organization_id=org_id,
             org_role='member' if org_id else None,
             org_status=org_status, email_verified=True)
    u.set_password('Synthetic-pass-1')
    db.session.add(u)
    db.session.flush()
    return u.user_id


def run(app):
    s = base.seed()
    org_id = db.session.query(Organization.organization_id).filter_by(
        organization_name='Synthetic Peoples Organization').scalar()
    other = Organization(organization_name='Synthetic Other Org',
                         organization_type='POs')
    db.session.add(other)
    db.session.flush()
    other_id = other.organization_id
    pending_id = make_user('syn_pending_member', org_id, 'pending')
    active_id = make_user('syn_active_member', org_id, 'active')
    db.session.commit()

    individual = app.test_client()
    base.login(individual, s.citizen_id, s.citizen_name, 'normal_user', None)
    pending = app.test_client()
    base.login(pending, pending_id, 'syn_pending_member', 'normal_user', None)
    admin = app.test_client()
    base.login(admin, s.cenro_admin_id, s.cenro_admin_name, 'admin',
               'Urdaneta City')
    field = app.test_client()
    base.login(field, s.officer_id, s.officer_name, 'field_officer',
               'Urdaneta City')
    member = app.test_client()
    base.login(member, active_id, 'syn_active_member', 'normal_user', None)

    # ------------------------------------------------------------------
    # 1. individual
    # ------------------------------------------------------------------
    before = request_count()
    r = post_request(individual)
    check('1 individual POST is refused (redirected)', r.status_code == 302)
    check('1 individual POST saves nothing', request_count() == before)
    page = individual.get('/requests').get_data(as_text=True)
    check('1 individual sees the invite message',
          'Only organization members can request sites. Ask your organization'
          ' leader for an invite link.' in page)
    check('1 individual has no working Add Request button',
          'class="um-btn-add" href="/gis-map?request=1"' not in page)

    # ------------------------------------------------------------------
    # 2. pending member
    # ------------------------------------------------------------------
    before = request_count()
    post_request(pending)
    check('2 pending POST is refused', request_count() == before)
    page = pending.get('/requests').get_data(as_text=True)
    check('2 pending member sees the approval message',
          'You can request sites once your leader approves you.' in page)

    # ------------------------------------------------------------------
    # 3-4. staff
    # ------------------------------------------------------------------
    before = request_count()
    post_request(admin)
    check('3 CENRO admin POST is refused', request_count() == before)
    page = admin.get('/requests').get_data(as_text=True)
    check('3 CENRO admin sees the staff message and the Review Requests link',
          'Staff create sites from approved requests.' in page
          and 'href="/admin/requests"' in page)

    before = request_count()
    post_request(field)
    check('4 field officer POST is refused', request_count() == before)
    page = field.get('/requests').get_data(as_text=True)
    check('4 field officer sees the field message, with no link',
          'Field officers record visits and reports. Site requests come from'
          ' organizations.' in page
          and 'href="/admin/requests"' not in page)

    # ------------------------------------------------------------------
    # 5. active member: own organization, posted one ignored
    # ------------------------------------------------------------------
    before = request_count()
    r = post_request(member, organization_id=str(other_id))
    check('5 active member POST is saved', request_count() == before + 1,
          r.status_code)
    db.session.remove()
    saved = Request.query.order_by(Request.request_id.desc()).first()
    check("5 saved request has the member's own organization",
          saved.organization_id == org_id, f'{saved.organization_id} != {org_id}')
    check('5 posted organization_id is ignored',
          saved.organization_id != other_id)

    # ------------------------------------------------------------------
    # 6. map request mode is closed when blocked
    # ------------------------------------------------------------------
    r = individual.get('/gis-map?request=1')
    check('6 individual is sent back from the map request mode',
          r.status_code == 302 and '/requests' in r.headers.get('Location', ''))
    r = member.get('/gis-map?request=1')
    check('6 active member can open the map request mode',
          r.status_code == 200)

    # ------------------------------------------------------------------
    # 7. the request keeps its organization after the member leaves
    # ------------------------------------------------------------------
    db.session.remove()
    leaver = db.session.get(User, active_id)
    leaver.organization_id = None
    leaver.org_role = None
    leaver.org_status = None
    db.session.commit()
    db.session.remove()
    kept = db.session.get(Request, saved.request_id)
    check('7 request still names the organization after the member leaves',
          kept.organization_id == org_id)

    # ------------------------------------------------------------------
    # 8. Review Requests
    # ------------------------------------------------------------------
    check('8 CENRO admin can open Review Requests',
          admin.get('/admin/requests').status_code == 200)
    check('8 field officer cannot open Review Requests',
          field.get('/admin/requests').status_code != 200)


def main():
    app = base.create_app()
    app.config['TESTING'] = True
    app.config['MAIL_SERVER'] = ''
    app.config['APP_BASE_URL'] = 'http://localhost'
    # Forms are posted without a CSRF token here; CSRF has its own test.
    app.config['WTF_CSRF_ENABLED'] = False

    temp = os.path.join(base.TMPDIR, 'static')
    real_doc = dashboard_routes.save_request_file
    dashboard_routes.save_request_file = (
        lambda f, _static, key, index: real_doc(f, temp, key, index))

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
