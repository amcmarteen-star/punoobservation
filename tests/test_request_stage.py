"""
Site requests through the organization stage, then the CENRO.

Runs the real Flask routes against a throwaway SQLite database. Uploads go
to a temporary folder and no email is sent.

WHAT IS UNDER TEST

    Every row of the transition table, allowed and refused:

    member sends                   -> Pending Org Approval
    leader sends                   -> Submitted (Pending CENRO)
    org forward                    -> Submitted
    org return (note)              -> Returned
    org return (no note)           refused
    org reject (note)              -> Rejected, final
    org reject (no note)           refused
    org action on a non-pending    refused
    member resubmit (documents)    -> Pending Org Approval
    member resubmit (no documents) refused
    other member resubmit          refused
    CENRO review Submitted         -> Under Review, Approved, Rejected
    CENRO reject (no note)         refused
    CENRO set Submitted            refused
    CENRO act on Pending Org Approval or Returned   refused (read-only)
    member cancel: Returned, Pending Org Approval, Submitted (allowed)
    member cancel: Approved        refused

    Also: cross-org 403, member (not leader) 403, the no-leader fallback,
    the CENRO queue, the notifications, and the audit entries.

RUN

    python tests/test_request_stage.py

Exit code 0 when every check passes, 1 otherwise.
"""

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# importing this first points DATABASE_URL at a temporary SQLite file
import test_publish_boundary as base                    # noqa: E402
from app.extensions import db                            # noqa: E402
from app.models import (                                 # noqa: E402
    AuditLog, Notification, Organization, Request, RequestAttachment, Site,
    SiteVisit, User,
)
from datetime import datetime                            # noqa: E402
from zoneinfo import ZoneInfo                            # noqa: E402
from app.routes import dashboard as dashboard_routes    # noqa: E402
import test_request_flow as rf                           # noqa: E402

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append({'name': name, 'ok': bool(ok)})
    print(('PASS  ' if ok else 'FAIL  ') + name
          + (f'  [{detail}]' if detail and not ok else ''))
    return bool(ok)


def pdf(name='plan.pdf'):
    return (io.BytesIO(b'%PDF-1.4 synthetic'), name)


def form(**over):
    data = {
        'request_type': 'Seedling Supply',
        'municipality': 'Villasis', 'barangay': 'Bacag',
        'contact_name': 'Maria Santos', 'contact_number': '09171234567',
        'contact_email': 'maria@synthetic.test',
    }
    data.update(over)
    return data


def send(client, **over):
    return client.post('/requests', data=form(attachments=[pdf()], **over),
                       content_type='multipart/form-data')


def latest_request(user_id):
    db.session.remove()
    return (Request.query.filter_by(user_id=user_id)
            .order_by(Request.request_id.desc()).first())


def row(request_id):
    db.session.remove()
    return db.session.get(Request, request_id)


def status_of(request_id):
    r = row(request_id)
    return r.status if r else None


def make_user(username, org_id=None, org_role=None, org_status=None,
              role='normal_user', cenro=None):
    u = User(username=username, email_address=f'{username}@example.test',
             role=role, cenro=cenro, organization_id=org_id,
             org_role=org_role, org_status=org_status, email_verified=True)
    u.set_password('Synthetic-pass-1')
    db.session.add(u)
    db.session.flush()
    return u.user_id


def make_org(name, cenro=None):
    o = Organization(organization_name=name, organization_type='POs',
                     cenro=cenro)
    db.session.add(o)
    db.session.flush()
    return o.organization_id


def notes_to(user_id, text):
    db.session.remove()
    return Notification.query.filter(
        Notification.user_id == user_id,
        Notification.message.contains(text)).count()


def audit(action, username=None):
    db.session.remove()
    q = AuditLog.query.filter_by(action=action)
    if username:
        q = q.filter_by(username=username)
    return q.count()


def request_count():
    db.session.remove()
    return Request.query.count()


def run(app):
    s = base.seed()
    org_a = db.session.query(Organization.organization_id).filter_by(
        organization_name='Synthetic Peoples Organization').scalar()
    org_e = make_org('Synthetic Org E')
    org_d = make_org('Synthetic Org D (no leader)', cenro='Urdaneta City')
    member = make_user('syn_member', org_a, 'member', 'active')
    member2 = make_user('syn_member2', org_a, 'member', 'active')
    leader = make_user('syn_leader', org_a, 'leader', 'active')
    leader_e = make_user('syn_leader_e', org_e, 'leader', 'active')
    member_d = make_user('syn_member_d', org_d, 'member', 'active')
    db.session.commit()
    cenro_uid = s.cenro_admin_id
    cenro_name = s.cenro_admin_name

    mem = app.test_client()
    base.login(mem, member, 'syn_member', 'normal_user', None)
    mem2 = app.test_client()
    base.login(mem2, member2, 'syn_member2', 'normal_user', None)
    lead = app.test_client()
    base.login(lead, leader, 'syn_leader', 'normal_user', None)
    lead_e = app.test_client()
    base.login(lead_e, leader_e, 'syn_leader_e', 'normal_user', None)
    mem_d = app.test_client()
    base.login(mem_d, member_d, 'syn_member_d', 'normal_user', None)
    cenro = app.test_client()
    base.login(cenro, cenro_uid, cenro_name, 'admin', 'Urdaneta City')
    field = app.test_client()
    base.login(field, s.officer_id, s.officer_name, 'field_officer',
               'Urdaneta City')

    # ------------------------------------------------------------------
    # 1. a member's request waits for the organization; CENRO is not told
    # ------------------------------------------------------------------
    cenro_before = notes_to(cenro_uid, 'requested')
    send(mem)
    r1 = latest_request(member).request_id
    check('1 member sends: Pending Org Approval',
          status_of(r1) == 'Pending Org Approval')
    check('1 CENRO is not told yet',
          notes_to(cenro_uid, 'requested') == cenro_before)
    check('1 the leader is told',
          notes_to(leader, 'sent a site request') >= 1)

    # ------------------------------------------------------------------
    # 2. the CENRO can read it but not act on it (read-only)
    # ------------------------------------------------------------------
    page = cenro.get('/admin/requests?status=At+organization').get_data(
        as_text=True)
    check('2 CENRO sees the request, read-only',
          'With the organization' in page)
    cenro.post(f'/admin/requests/{r1}/review',
               data={'status': 'Approved', 'review_note': ''})
    check('2 CENRO cannot approve it while with the organization',
          status_of(r1) == 'Pending Org Approval')
    default = cenro.get('/admin/requests').get_data(as_text=True)
    check('2 the default CENRO queue leaves it out',
          'With the organization' not in default)

    # ------------------------------------------------------------------
    # 3. org actions: refused without a note, refused for a non-leader
    # ------------------------------------------------------------------
    lead.post(f'/requests/{r1}/org-action', data={'action': 'return', 'note': ''})
    check('3 return without a note is refused',
          status_of(r1) == 'Pending Org Approval')
    lead.post(f'/requests/{r1}/org-action', data={'action': 'reject', 'note': ''})
    check('3 reject without a note is refused',
          status_of(r1) == 'Pending Org Approval')
    r = mem.post(f'/requests/{r1}/org-action', data={'action': 'forward'})
    check('3 a member who is not a leader cannot act: 403',
          r.status_code == 403 and status_of(r1) == 'Pending Org Approval')

    # ------------------------------------------------------------------
    # 4. cross-org: a leader of another organization is refused: 403
    # ------------------------------------------------------------------
    r = lead_e.post(f'/requests/{r1}/org-action', data={'action': 'forward'})
    check("4 leader of another org acting on this request: 403",
          r.status_code == 403 and status_of(r1) == 'Pending Org Approval')

    # ------------------------------------------------------------------
    # 5. return for changes, with a note
    # ------------------------------------------------------------------
    lead.post(f'/requests/{r1}/org-action',
              data={'action': 'return', 'note': 'Add the signed IMP.'})
    check('5 leader returns with a note: Returned',
          status_of(r1) == 'Returned')
    check('5 the member is told, with the note',
          notes_to(member, 'Add the signed IMP.') == 1)
    check('5 return is logged with the actor',
          audit('org_return', 'syn_leader') >= 1)

    # ------------------------------------------------------------------
    # 6. resubmit: other members refused; no document refused; owner ok
    # ------------------------------------------------------------------
    docs_before = len(row(r1).attachments)
    r = mem2.post(f'/requests/{r1}/resubmit',
                  data={'attachments': [pdf('other.pdf')]},
                  content_type='multipart/form-data')
    check('6 another member cannot resubmit it',
          status_of(r1) == 'Returned')

    mem.post(f'/requests/{r1}/resubmit', data={}, content_type='multipart/form-data')
    check('6 resubmit with no document is refused',
          status_of(r1) == 'Returned')

    mem.post(f'/requests/{r1}/resubmit',
             data={'attachments': [pdf('signed-imp.pdf')]},
             content_type='multipart/form-data')
    check('6 owner resubmits with a document: Pending Org Approval',
          status_of(r1) == 'Pending Org Approval')
    check('6 resubmit adds documents only, the old ones stay',
          len(row(r1).attachments) == docs_before + 1)
    check('6 leader is told it came back',
          notes_to(leader, 'sent back the request') >= 1)
    check('6 resubmit is logged',
          audit('resubmit_request', 'syn_member') >= 1)

    # ------------------------------------------------------------------
    # 7. Returned cannot be forwarded straight away: only Pending Org can
    # ------------------------------------------------------------------
    lead.post(f'/requests/{r1}/org-action', data={'action': 'forward'})
    check('7 forward from Pending Org Approval works',
          status_of(r1) == 'Submitted')
    check('7 forwarded: the CENRO is told',
          notes_to(cenro_uid, 'forwarded') == 1)
    check('7 forward is logged with the leader',
          audit('org_forward', 'syn_leader') >= 1)
    lead.post(f'/requests/{r1}/org-action', data={'action': 'forward'})
    check('7 a forwarded request cannot be forwarded again',
          status_of(r1) == 'Submitted')

    # ------------------------------------------------------------------
    # 8. CENRO: review transitions from Submitted
    # ------------------------------------------------------------------
    cenro.post(f'/admin/requests/{r1}/review',
               data={'status': 'Submitted', 'review_note': ''})
    check('8 CENRO cannot set Submitted', status_of(r1) == 'Submitted')
    cenro.post(f'/admin/requests/{r1}/review',
               data={'status': 'Under Review', 'review_note': ''})
    check('8 CENRO marks Under Review', status_of(r1) == 'Under Review')
    cenro.post(f'/admin/requests/{r1}/review',
               data={'status': 'Rejected', 'review_note': ''})
    check('8 CENRO reject without a note is refused',
          status_of(r1) == 'Under Review')
    cenro.post(f'/admin/requests/{r1}/review',
               data={'status': 'Approved', 'review_note': ''})
    check('8 CENRO approves: Approved', status_of(r1) == 'Approved')
    check('8 CENRO review is logged with the old status',
          audit('review_request', cenro_name) >= 1)

    # ------------------------------------------------------------------
    # 9. org reject: final, reason shown, the member may send a new one
    # ------------------------------------------------------------------
    send(mem2)
    r9 = latest_request(member2).request_id
    lead.post(f'/requests/{r9}/org-action', data={'action': 'reject', 'note': ''})
    check('9 reject without a note is refused',
          status_of(r9) == 'Pending Org Approval')
    lead.post(f'/requests/{r9}/org-action',
              data={'action': 'reject', 'note': 'Outside our planting area.'})
    check('9 leader rejects with a reason: Rejected',
          status_of(r9) == 'Rejected')
    check('9 the member is told the reason',
          notes_to(member2, 'Outside our planting area.') == 1)
    lead.post(f'/requests/{r9}/org-action', data={'action': 'forward'})
    check('9 a rejected request is final (no forward)',
          status_of(r9) == 'Rejected')
    before = request_count()
    send(mem2)
    check('9 the member can send a new request afterwards',
          request_count() == before + 1)
    check('9 reject is logged', audit('org_reject', 'syn_leader') >= 1)

    # ------------------------------------------------------------------
    # 10. a leader's request skips the organization
    # ------------------------------------------------------------------
    send(lead)
    r10 = latest_request(leader).request_id
    check("10 a leader's request starts at the CENRO: Submitted",
          status_of(r10) == 'Submitted')
    check('10 the CENRO is told', notes_to(cenro_uid, 'requested') >= 1)

    # ------------------------------------------------------------------
    # 11. cancel: Returned and Pending Org allowed; Approved refused
    # ------------------------------------------------------------------
    send(mem)
    r11 = latest_request(member).request_id
    before = request_count()
    mem.post(f'/requests/{r11}/cancel', data={'status': 'Pending'})
    check('11 member cancels Pending Org Approval', request_count() == before - 1)

    send(mem)
    r12 = latest_request(member).request_id
    lead.post(f'/requests/{r12}/org-action',
              data={'action': 'return', 'note': 'More detail please.'})
    before = request_count()
    mem.post(f'/requests/{r12}/cancel', data={'status': 'Pending'})
    check('11 member cancels a Returned request', request_count() == before - 1)

    mem.post(f'/requests/{r1}/cancel', data={'status': 'Pending'})
    check('11 Approved cannot be cancelled', status_of(r1) == 'Approved')

    # ------------------------------------------------------------------
    # 12. no active leader: the CENRO acts on the organization stage
    # ------------------------------------------------------------------
    send(mem_d)
    r13 = latest_request(member_d).request_id
    check('12 member of an org with no leader: Pending Org Approval',
          status_of(r13) == 'Pending Org Approval')
    check('12 the CENRO is told when no leader can act',
          notes_to(cenro_uid, 'requested') >= 2)
    cenro.post(f'/requests/{r13}/org-action', data={'action': 'forward'})
    check('12 CENRO forwards when the org has no active leader',
          status_of(r13) == 'Submitted')

    # ------------------------------------------------------------------
    # 13. labels: the stored Submitted is shown as Pending CENRO
    # ------------------------------------------------------------------
    send(mem2)
    page = mem2.get('/requests').get_data(as_text=True)
    check('13 the member sees "Pending Org Approval"',
          'Pending Org Approval' in page)
    cpage = cenro.get('/admin/requests').get_data(as_text=True)
    check('13 the CENRO sees "Pending CENRO" for stored Submitted',
          'Pending CENRO' in cpage)

    # ------------------------------------------------------------------
    # 14. end to end, a regular member (not a leader):
    #     submit -> leader forwards -> CENRO Under Review -> temporary
    #     site -> CENRO Approved
    # ------------------------------------------------------------------
    e2e_member = make_user('syn_member_e2e', org_a, 'member', 'active')
    db.session.commit()
    e2e = app.test_client()
    base.login(e2e, e2e_member, 'syn_member_e2e', 'normal_user', None)

    # A site request, with a pin on the map (a temporary site needs one).
    send(e2e, request_type='New Planting Site',
         latitude='15.92434', longitude='120.58222')
    e2e_req = latest_request(e2e_member).request_id
    check('14 member submits: Pending Org Approval',
          status_of(e2e_req) == 'Pending Org Approval')

    lead.post(f'/requests/{e2e_req}/org-action', data={'action': 'forward'})
    check('14 leader forwards: Submitted (Pending CENRO)',
          status_of(e2e_req) == 'Submitted')

    cenro.post(f'/admin/requests/{e2e_req}/review',
               data={'status': 'Under Review', 'review_note': ''})
    check('14 CENRO marks Under Review', status_of(e2e_req) == 'Under Review')

    cenro.post(f'/admin/requests/{e2e_req}/create-site',
               data=rf.site_form(s, 'E2E Member Site'))
    db.session.remove()
    e2e_site = Site.query.filter_by(site_name='E2E Member Site').first()
    check('14 temporary site is created from the request',
          e2e_site is not None and e2e_site.source_request_id == e2e_req)
    check('14 the request stays Under Review while the site is temporary',
          status_of(e2e_req) == 'Under Review')

    cenro.post(f'/admin/requests/{e2e_req}/review',
               data={'status': 'Approved', 'review_note': ''})
    check('14 CENRO approves: Approved', status_of(e2e_req) == 'Approved')
    db.session.remove()
    check('14 the site stays open after approval',
          db.session.get(Site, e2e_site.site_id).site_status != 'Not Suitable')
    check('14 the member is told it was approved',
          notes_to(e2e_member, 'is now Approved') == 1)
    check('14 each step is in the audit log',
          audit('org_forward', 'syn_leader') >= 1
          and audit('review_request', cenro_name) >= 2)

    # ------------------------------------------------------------------
    # 15. Approved and Rejected: the blocked transitions
    # ------------------------------------------------------------------
    # r1 is Approved (no site), r9 is Rejected (no site), e2e_req is
    # Approved (with a temporary site that is still open)
    cenro.post(f'/admin/requests/{r1}/review',
               data={'status': 'Approved', 'review_note': ''})
    check('15 Approved -> Approved is blocked', status_of(r1) == 'Approved')
    cenro.post(f'/admin/requests/{r1}/review',
               data={'status': 'Under Review', 'review_note': ''})
    check('15 Approved -> Under Review is blocked', status_of(r1) == 'Approved')

    cenro.post(f'/admin/requests/{r9}/review',
               data={'status': 'Rejected', 'review_note': 'again'})
    check('15 Rejected -> Rejected is blocked', status_of(r9) == 'Rejected')
    cenro.post(f'/admin/requests/{r9}/review',
               data={'status': 'Under Review', 'review_note': ''})
    check('15 Rejected -> Under Review is blocked', status_of(r9) == 'Rejected')
    cenro.post(f'/admin/requests/{r9}/review',
               data={'status': 'Approved', 'review_note': ''})
    check('15 Rejected -> Approved is blocked', status_of(r9) == 'Rejected')

    send(mem2)
    r_ur = latest_request(member2).request_id
    lead.post(f'/requests/{r_ur}/org-action', data={'action': 'forward'})
    cenro.post(f'/admin/requests/{r_ur}/review',
               data={'status': 'Under Review', 'review_note': ''})
    cenro.post(f'/admin/requests/{r_ur}/review',
               data={'status': 'Under Review', 'review_note': ''})
    check('15 Under Review -> Under Review is blocked',
          status_of(r_ur) == 'Under Review')

    cenro.post(f'/admin/requests/{e2e_req}/review',
               data={'status': 'Approved', 'review_note': ''})
    check('15 Approved with a site -> Approved is blocked',
          status_of(e2e_req) == 'Approved')
    cenro.post(f'/admin/requests/{e2e_req}/review',
               data={'status': 'Under Review', 'review_note': ''})
    check('15 Approved with a site -> Under Review is blocked',
          status_of(e2e_req) == 'Approved')

    # A closed site comes only from a site visit found Not Suitable.
    cenro.post(f'/admin/requests/{r1}/review',
               data={'status': 'Rejected', 'review_note': 'Changed mind.'})
    check('15 manual Approved -> Rejected is refused',
          status_of(r1) == 'Approved')

    # ------------------------------------------------------------------
    # 16. the visit path still closes the site and rejects the request
    # ------------------------------------------------------------------
    page = cenro.get(f'/admin/requests/{e2e_req}').get_data(as_text=True)
    check('16 approved request page: no reject option, points to a site visit',
          'To close this site, assign a site visit and mark it Not Suitable.'
          in page and 'value="Rejected"' not in page)
    cenro.post(f'/admin/requests/{e2e_req}/review',
               data={'status': 'Rejected', 'review_note': 'No.'})
    check('16 manual reject of the approved request is refused',
          status_of(e2e_req) == 'Approved')

    e2e_site_id = db.session.query(Site.site_id).filter_by(
        site_name='E2E Member Site').scalar()
    cenro.post(f'/sites/{e2e_site_id}/assignments', data={
        'officer_id': str(s.officer_id), 'visit_type': 'Pre-planting check',
        'target_date': '', 'note': ''})
    today = datetime.now(ZoneInfo('Asia/Manila')).date()
    field.post(f'/sites/{e2e_site_id}/visits/new', data={
        'visit_date': today.isoformat(), 'visit_type': 'Pre-planting check',
        'finding': 'Not suitable', 'land_matches': 'yes',
        'ownership_confirmed': 'yes', 'accessible': 'no',
        'remarks': 'Riverbank, floods every year.'},
        content_type='multipart/form-data')
    db.session.remove()
    visit = (SiteVisit.query.filter_by(site_id=e2e_site_id)
             .order_by(SiteVisit.visit_id.desc()).first())
    check('16 the Not Suitable visit is saved',
          visit is not None and visit.finding == 'Not suitable')
    cenro.post(f'/visits/{visit.visit_id}/review', data={
        'status': 'Approved', 'suggested_municipality': 'Villasis',
        'suggested_barangay': 'Bacag',
        'suggestion_note': 'Plant on the upland part of Bacag.'})
    check('16 approving that visit closes the site',
          db.session.get(Site, e2e_site_id).site_status == 'Not Suitable')
    check('16 approving that visit rejects the request',
          status_of(e2e_req) == 'Rejected')


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
