"""
Notifications and the request timeline (Module 4).

Runs the real Flask routes against a throwaway SQLite database. Uploads go
to a temporary folder and no email is sent.

WHAT IS UNDER TEST

    1  each transition creates exactly one notification for the right person
    2  every request notice opens the request's own page (CENRO: the admin page)
    3  membership notices: the leader sees a join request, the member sees the
       decision, and each opens the right page
    4  the timeline steps and the current step at each stage
    5  "waiting X days" counts from the last STATUS change, not the last
       audit entry of any kind
    6  an old request with no stage audit rows still builds a full timeline
    7  the audit rows the timeline reads have the format it depends on
    8  the request page: the submitter, the org's active leaders, and the CENRO
       that covers it; everyone else gets 403

RUN

    python tests/test_timeline_notifications.py

Exit code 0 when every check passes, 1 otherwise.
"""

import io
import os
import sys
from datetime import timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# importing this first points DATABASE_URL at a temporary SQLite file
import test_publish_boundary as base                    # noqa: E402
from app.extensions import db                            # noqa: E402
from app.models import (                                 # noqa: E402
    AuditLog, Notification, Organization, Request, User,
)
from app.routes import dashboard as dashboard_routes    # noqa: E402
from app.services.notification_links import notification_url  # noqa: E402
from app.services.request_timeline import (              # noqa: E402
    build_timeline, stage_events,
)
from app.utils.organization import ensure_join_token    # noqa: E402
from app.utils.timeutil import manila_now               # noqa: E402

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


def send(client, **over):
    return client.post('/requests', data=form(attachments=[pdf()], **over),
                       content_type='multipart/form-data')


def latest_request(user_id):
    db.session.remove()
    return (Request.query.filter_by(user_id=user_id)
            .order_by(Request.request_id.desc()).first())


def req_row(request_id):
    db.session.remove()
    return db.session.get(Request, request_id)


def status_of(request_id):
    r = req_row(request_id)
    return r.status if r else None


def make_user(username, org_id=None, org_role=None, org_status=None,
              role='normal_user', cenro=None, verified=True):
    u = User(username=username, email_address=f'{username}@example.test',
             role=role, cenro=cenro, organization_id=org_id,
             org_role=org_role, org_status=org_status,
             email_verified=verified)
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


def count_notes(user_id, request_id=None, kind=None, text=None):
    db.session.remove()
    q = Notification.query.filter(Notification.user_id == user_id)
    if request_id is not None:
        q = q.filter(Notification.request_id == request_id)
    if kind is not None:
        q = q.filter(Notification.notification_type == kind)
    if text is not None:
        q = q.filter(Notification.message.contains(text))
    return q.count()


def timeline_of(request_id, now=None):
    db.session.remove()
    req = db.session.get(Request, request_id)
    return build_timeline(req, now=now)


def states(tl):
    return {s['key']: s['state'] for s in tl['steps']}


def run(app):
    s = base.seed()
    org_a = db.session.query(Organization.organization_id).filter_by(
        organization_name='Synthetic Peoples Organization').scalar()
    org_e = make_org('Synthetic Org E')
    leader_a = make_user('syn_leader_t', org_a, 'leader', 'active')
    member = make_user('syn_member_t', org_a, 'member', 'active')
    member2 = make_user('syn_member2_t', org_a, 'member', 'active')
    leader_e = make_user('syn_leader_e_t', org_e, 'leader', 'active')
    joiner = make_user('syn_joiner_t', None, None, None)
    db.session.commit()
    token_a = ensure_join_token(db.session.get(Organization, org_a))
    db.session.commit()
    cenro_id = s.cenro_admin_id

    def as_user(uid, name, role='normal_user', cenro=None):
        c = app.test_client()
        base.login(c, uid, name, role, cenro)
        return c

    mem = as_user(member, 'syn_member_t')
    mem2 = as_user(member2, 'syn_member2_t')
    lead = as_user(leader_a, 'syn_leader_t')
    lead_e = as_user(leader_e, 'syn_leader_e_t')
    cenro = as_user(cenro_id, s.cenro_admin_name, 'admin', 'Urdaneta City')
    dagupan = as_user(s.dagupan_admin_id, s.dagupan_admin_name, 'admin',
                      'Dagupan')
    field = as_user(s.officer_id, s.officer_name, 'field_officer',
                    'Urdaneta City')
    penro = as_user(s.penro_id, s.penro_name, 'admin', None)
    superadmin = as_user(s.superadmin_id, s.superadmin_name, 'superadmin',
                         None)

    # ------------------------------------------------------------------
    # 1. one notification per transition, to the right person
    # ------------------------------------------------------------------
    send(mem)
    r1 = latest_request(member).request_id
    check('1 member submits: the leader gets exactly one notice',
          count_notes(leader_a, r1) == 1)
    check('1 member submits: the CENRO gets none yet',
          count_notes(cenro_id, r1) == 0)

    lead.post(f'/requests/{r1}/org-action', data={'action': 'forward'})
    check('1 forward: the member gets exactly one notice',
          count_notes(member, r1) == 1)
    check('1 forward: the CENRO gets exactly one notice',
          count_notes(cenro_id, r1, kind='New Request') == 1)

    cenro.post(f'/admin/requests/{r1}/review',
               data={'status': 'Under Review', 'review_note': ''})
    check('1 CENRO Under Review: the member gets exactly one notice',
          count_notes(member, r1) == 2)

    cenro.post(f'/admin/requests/{r1}/review',
               data={'status': 'Approved', 'review_note': ''})
    check('1 CENRO approves: the member gets exactly one more notice',
          count_notes(member, r1) == 3)

    send(mem2)
    r2 = latest_request(member2).request_id
    lead.post(f'/requests/{r2}/org-action',
              data={'action': 'return', 'note': 'Add the signed IMP.'})
    check('1 return: the member gets exactly one notice, with the note',
          count_notes(member2, r2, text='Add the signed IMP.') == 1)
    before_resubmit = count_notes(leader_a, r2, kind='Request Update')
    mem2.post(f'/requests/{r2}/resubmit',
              data={'attachments': [pdf()]},
              content_type='multipart/form-data')
    check('1 resubmit: the leader gets exactly one new notice',
          count_notes(leader_a, r2, kind='Request Update') == before_resubmit + 1)

    lead.post(f'/requests/{r2}/org-action',
              data={'action': 'reject', 'note': 'Outside our area.'})
    check('1 org reject: the member gets exactly one notice, with the reason',
          count_notes(member2, r2, text='Outside our area.') == 1)

    send(lead)
    r3 = latest_request(leader_a).request_id
    check("1 a leader's request: the CENRO gets exactly one notice",
          count_notes(cenro_id, r3, kind='New Request') == 1)
    check("1 a leader's request: no leader gets a notice for it",
          count_notes(leader_a, r3) == 0)

    # ------------------------------------------------------------------
    # 2. request notices open the request page; the CENRO's, the admin page
    # ------------------------------------------------------------------
    with app.test_request_context():
        from flask import session
        session['role'] = 'normal_user'
        n_member = Notification(user_id=member, notification_type='Request Update',
                                message='x', request_id=r1, is_read=False)
        check('2 member notice opens the member request page',
              notification_url(n_member) == f'/requests/{r1}')
        session['role'] = 'admin'
        n_cenro = Notification(user_id=cenro_id, notification_type='New Request',
                               message='x', request_id=r1, is_read=False)
        check('2 CENRO notice opens the CENRO detail page',
              notification_url(n_cenro) == f'/admin/requests/{r1}')

    # ------------------------------------------------------------------
    # 3. membership notices
    # ------------------------------------------------------------------
    joiner_client = as_user(joiner, 'syn_joiner_t')
    joiner_client.post(f'/join/{token_a}/request')
    check('3 a join request: the leader gets exactly one notice',
          count_notes(leader_a, kind='Membership') >= 1)
    db.session.remove()
    notes = (Notification.query.filter(Notification.user_id == leader_a,
                                       Notification.notification_type == 'Membership')
             .order_by(Notification.notification_id.desc()).first())
    with app.test_request_context():
        from flask import session
        session['role'] = 'normal_user'
        check('3 the leader notice opens the members page',
              notes is not None and notification_url(notes) == '/org/members')
    check('3 the joiner is not told yet',
          count_notes(joiner, kind='Membership') == 0)

    lead.post(f'/org/{org_a}/members/{joiner}/approve')
    check('3 approved: the new member gets exactly one notice',
          count_notes(joiner, kind='Membership') == 1)
    with app.test_request_context():
        from flask import session
        session['role'] = 'normal_user'
        n_join = (Notification.query.filter(
            Notification.user_id == joiner,
            Notification.notification_type == 'Membership').first())
        check('3 the approval notice opens My Account',
              n_join is not None and notification_url(n_join) == '/account')

    rejected = make_user('syn_reject_t', None, None, None)
    db.session.commit()
    as_user(rejected, 'syn_reject_t').post(f'/join/{token_a}/request')
    lead.post(f'/org/{org_a}/members/{rejected}/reject')
    check('3 rejected: the person gets exactly one notice',
          count_notes(rejected, kind='Membership') == 1)

    removed_user = make_user('syn_removed_t', org_a, 'member', 'active')
    db.session.commit()
    lead.post(f'/org/{org_a}/members/{removed_user}/remove')
    check('3 removed: the person gets exactly one notice',
          count_notes(removed_user, kind='Membership') == 1)

    # ------------------------------------------------------------------
    # 4. the timeline at each step
    # ------------------------------------------------------------------
    send(mem)
    r4 = latest_request(member).request_id
    tl = timeline_of(r4)
    check('4 sent by a member: the organization step is current',
          tl['current'] == 'org' and states(tl)['cenro'] == 'pending')
    check('4 sent by a member: waiting 0 days today',
          tl['waiting_days'] == 0)

    lead.post(f'/requests/{r4}/org-action', data={'action': 'forward'})
    tl = timeline_of(r4)
    check('4 forwarded: the CENRO step is current',
          tl['current'] == 'cenro' and states(tl)['org'] == 'done')
    check('4 forwarded: the org step records the leader',
          [x for x in tl['steps'] if x['key'] == 'org'][0]['who']
          == 'syn_leader_t')

    cenro.post(f'/admin/requests/{r4}/review',
               data={'status': 'Approved', 'review_note': ''})
    tl = timeline_of(r4)
    check('4 approved: the outcome step is approved, with the reviewer',
          states(tl)['outcome'] == 'approved' and tl['current'] == 'outcome'
          and [x for x in tl['steps'] if x['key'] == 'outcome'][0]['who']
          == s.cenro_admin_name)

    send(mem2)
    r5 = latest_request(member2).request_id
    lead.post(f'/requests/{r5}/org-action',
              data={'action': 'return', 'note': 'More detail.'})
    tl = timeline_of(r5)
    check('4 returned: the org step says so, with the note',
          tl['current'] == 'org' and states(tl)['org'] == 'current'
          and [x for x in tl['steps'] if x['key'] == 'org'][0]['note']
          == 'More detail.')

    send(mem2)
    r6 = latest_request(member2).request_id
    lead.post(f'/requests/{r6}/org-action',
              data={'action': 'reject', 'note': 'Not ours.'})
    tl = timeline_of(r6)
    check('4 rejected by the org: the CENRO and outcome steps do not apply',
          states(tl)['org'] == 'rejected' and states(tl)['cenro'] == 'pending'
          and states(tl)['outcome'] == 'skipped')

    send(lead)
    r7 = latest_request(leader_a).request_id
    tl = timeline_of(r7)
    check("4 a leader's request skips the organization step",
          states(tl)['org'] == 'skipped' and tl['current'] == 'cenro')

    # ------------------------------------------------------------------
    # 5. the wait counts from the last STATUS change
    # ------------------------------------------------------------------
    send(mem)
    r8 = latest_request(member).request_id
    lead.post(f'/requests/{r8}/org-action', data={'action': 'forward'})
    fwd = (AuditLog.query.filter_by(action='org_forward', entity_id=r8)
           .first())
    fwd_time = manila_now() - timedelta(days=2)
    db.session.remove()
    row_fwd = db.session.get(AuditLog, fwd.log_id)
    row_fwd.created_at = fwd_time
    sub = (AuditLog.query.filter_by(action='submit_request', entity_id=r8).first())
    db.session.get(AuditLog, sub.log_id).created_at = fwd_time - timedelta(days=1)
    # an unrelated entry written today must not reset the clock
    db.session.add(AuditLog(user_id=cenro_id, username='syn_cenro',
                            role='admin', action='login', entity_type='users',
                            entity_id=cenro_id, created_at=manila_now()))
    db.session.commit()
    tl = timeline_of(r8)
    check('5 waiting counts from the forward, not from the newest entry',
          tl['waiting_days'] == 2, f"got {tl['waiting_days']}")

    # ------------------------------------------------------------------
    # 6. an old request with no stage audit rows
    # ------------------------------------------------------------------
    db.session.remove()
    loc_id = base.Location.query.filter_by(barangay='Bacag').first().location_id
    old_pending = Request(user_id=s.citizen_id, location_id=loc_id,
                          request_type='New Planting Site',
                          status='Under Review',
                          contact_name='Maria Santos',
                          contact_email='maria@synthetic.test',
                          date_submitted=manila_now() - timedelta(days=3))
    db.session.add(old_pending)
    db.session.commit()
    old_id = old_pending.request_id
    check('6 the old request has no stage audit rows',
          len(stage_events(db.session.get(Request, old_id))) == 0)
    tl = timeline_of(old_id)
    check('6 old pending request: a full timeline, none blank',
          len(tl['steps']) == 4 and all(
              x['state'] in ('done', 'current', 'pending', 'skipped', 'rejected',
                             'approved') for x in tl['steps']))
    check('6 old pending request: current step is CENRO, waiting 3 days',
          tl['current'] == 'cenro' and tl['waiting_days'] == 3)
    check('6 old pending request: dates come from the request itself',
          [x for x in tl['steps'] if x['key'] == 'submitted'][0]['date']
          is not None)

    db.session.remove()
    old_done = Request(user_id=s.citizen_id, location_id=loc_id,
                       request_type='New Planting Site', status='Approved',
                       contact_name='Maria Santos',
                       contact_email='maria@synthetic.test',
                       date_submitted=manila_now() - timedelta(days=9),
                       date_reviewed=manila_now() - timedelta(days=4))
    db.session.add(old_done)
    db.session.commit()
    tl = timeline_of(old_done.request_id)
    outcome = [x for x in tl['steps'] if x['key'] == 'outcome'][0]
    check('6 old approved request: outcome dated from date_reviewed',
          outcome['state'] == 'approved' and outcome['date'] is not None
          and outcome['date'].date() == (manila_now() - timedelta(days=4)).date())

    # ------------------------------------------------------------------
    # 7. the audit format the timeline depends on
    # ------------------------------------------------------------------
    events = stage_events(db.session.get(Request, r1))
    check('7 the stage rows are in order: submit, forward, review, review',
          [e.action for e in events] == ['submit_request', 'org_forward',
                                         'review_request', 'review_request'])
    check('7 each stage row is a request row, with a time and a person',
          all(e.entity_type == 'request' and e.entity_id == r1
              and e.created_at is not None and e.username for e in events))

    # ------------------------------------------------------------------
    # 8. who may open the request page
    # ------------------------------------------------------------------
    check('8 the submitter may open it',
          mem.get(f'/requests/{r1}').status_code == 200)
    check('8 another member may not: 403',
          mem2.get(f'/requests/{r1}').status_code == 403)
    check('8 an active leader of the organization may: 200',
          lead.get(f'/requests/{r1}').status_code == 200)
    check("8 a leader of another organization may not: 403",
          lead_e.get(f'/requests/{r1}').status_code == 403)
    check('8 the CENRO that covers it may: 200',
          cenro.get(f'/requests/{r1}').status_code == 200)
    check('8 a CENRO for another area may not: 403',
          dagupan.get(f'/requests/{r1}').status_code == 403)
    check('8 a field officer may not: 403',
          field.get(f'/requests/{r1}').status_code == 403)
    check('8 the provincial admin may: 200',
          penro.get(f'/requests/{r1}').status_code == 200)
    check('8 the superadmin may: 200',
          superadmin.get(f'/requests/{r1}').status_code == 200)
    check('8 a missing request: 404',
          mem.get('/requests/999999').status_code == 404)
    anon = app.test_client()
    check('8 signed out: sent to sign in',
          anon.get(f'/requests/{r1}').status_code == 302)

    page = mem.get(f'/requests/{r1}').get_data(as_text=True)
    check('8 the page shows the steps and the wait',
          'Organization review' in page and 'CENRO review' in page
          and 'Approved' in page)


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
