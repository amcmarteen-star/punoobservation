"""
Organization membership: join links, approval, leaders, leaving.

Runs the real Flask routes against a throwaway SQLite database. Nothing
touches Postgres, and no email is sent.

WHAT IS UNDER TEST

    1  an invite link opens the sign-up page for that organization
    2  a made-up link is refused with the message
    3  sign-up through a link makes a pending member; plain sign-up does not
    4  a signed-in person asks to join with a pending request, and only
       when they belong to no organization
    5  a leader approves, rejects and removes members of their own org
    6  a leader cannot act on another organization, on self, or on a leader
    7  an unverified pending person cannot be approved
    8  CENRO admins appoint and remove leaders in their CENRO only
    9  CENRO admins approve members only when no active leader exists
   10  the last active leader cannot leave
   11  a regenerated link stops working; the new one works
   12  members pages: own org for leaders, never another org
   13  the organizations list is limited to the CENRO; provincial sees all
   14  every change writes an audit row

RUN

    python tests/test_org_membership.py

Exit code 0 when every check passes, 1 otherwise.
"""

import os
import sys
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# importing this first points DATABASE_URL at a temporary SQLite file
import test_publish_boundary as base                    # noqa: E402
from app.extensions import db                            # noqa: E402
from app.models import AuditLog, Location, Organization, User  # noqa: E402
from app.utils.organization import ensure_join_token    # noqa: E402

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append({'name': name, 'ok': bool(ok), 'detail': detail})
    print(('PASS  ' if ok else 'FAIL  ') + name
          + (f'  [{detail}]' if detail and not ok else ''))
    return bool(ok)


def login(client, user_id):
    """Sign in as a user, read fresh from the database."""
    db.session.remove()
    u = db.session.get(User, user_id)
    base.login(client, u.user_id, u.username, u.role, u.cenro)


def user_row(user_id):
    """A fresh copy of a user row. Always read after a request."""
    db.session.remove()
    return db.session.get(User, user_id)


def make_user(username, role='normal_user', cenro=None, org_id=None,
              org_role=None, org_status=None, verified=True):
    u = User(username=username, email_address=f'{username}@example.test',
             role=role, cenro=cenro, organization_id=org_id,
             org_role=org_role, org_status=org_status,
             email_verified=verified)
    u.set_password('Synthetic-pass-1')
    db.session.add(u)
    db.session.flush()
    return u.user_id


def audit_count(action):
    db.session.remove()
    return AuditLog.query.filter_by(action=action).count()


def seed():
    """Four organizations' worth of synthetic people. Returns plain ids."""
    org_a = Organization(organization_name='Synthetic Org A',
                         organization_type='POs', cenro='Urdaneta City')
    org_b = Organization(organization_name='Synthetic Org B',
                         organization_type='POs', cenro='Dagupan')
    org_c = Organization(organization_name='Synthetic Org C',
                         organization_type='POs', cenro=None)
    db.session.add_all([org_a, org_b, org_c])
    db.session.flush()
    a, b, c = org_a.organization_id, org_b.organization_id, org_c.organization_id

    ids = {
        'org_a': a, 'org_b': b, 'org_c': c,
        'leader_a': make_user('syn_leader_a', org_id=a, org_role='leader',
                              org_status='active'),
        'pending_a': make_user('syn_pending_a', org_id=a, org_role='member',
                               org_status='pending'),
        'unverified_a': make_user('syn_unverified_a', org_id=a,
                                  org_role='member', org_status='pending',
                                  verified=False),
        'active_a': make_user('syn_active_a', org_id=a, org_role='member',
                              org_status='active'),
        'member_b': make_user('syn_member_b', org_id=b, org_role='member',
                              org_status='pending'),
        'cenro_admin': make_user('syn_cenro_admin', role='admin',
                                 cenro='Urdaneta City'),
        'provincial': make_user('syn_provincial', role='admin', cenro=None),
        'individual': make_user('syn_individual'),
    }
    location = Location(psgc_code='SYN-SIGNUP', region='Region I',
                        province='Pangasinan', municipality='Villasis',
                        barangay='Bacag', latitude=15.9, longitude=120.6,
                        elevation_m=30.0)
    db.session.add(location)
    db.session.commit()
    ids['location'] = location.location_id

    # seed() gives no join links; make them the way the app does.
    ids['token_a'] = ensure_join_token(db.session.get(Organization, a))
    ids['token_b'] = ensure_join_token(db.session.get(Organization, b))
    db.session.commit()
    return ids


def run(app):
    client = app.test_client()
    s = seed()
    A, B, C = s['org_a'], s['org_b'], s['org_c']

    # ------------------------------------------------------------------
    # 1-3. invite links and sign-up
    # ------------------------------------------------------------------
    r = client.get(f"/join/{s['token_a']}")
    check('1 link opens sign-up for the org',
          r.status_code == 200 and b'Joining' in r.data
          and b'Synthetic Org A' in r.data)

    r = client.get('/join/not-a-real-token')
    check('2 made-up link shows the message',
          r.status_code == 200 and b'This link no longer works' in r.data)

    r = client.get('/register')
    check('3 plain sign-up page has no organization dropdown',
          b'name="organization_id"' not in r.data)

    base_form = {
        'email_address': '', 'password': 'Synthetic-pass-1',
        'confirmPassword': 'Synthetic-pass-1',
        'location_id': str(s['location']),
    }

    def signup(name, token):
        data = dict(base_form, username=name,
                    email_address=f'{name}@example.test', join_token=token)
        with mock.patch('app.routes.auth._send_verification'):
            return client.post('/register', data=data)

    signup('syn_joiner', s['token_a'])
    joiner = User.query.filter_by(username='syn_joiner').first()
    check('3 sign-up through a link makes a pending member',
          joiner is not None and joiner.organization_id == A
          and joiner.org_role == 'member' and joiner.org_status == 'pending')
    joiner_id = joiner.user_id if joiner else None

    r = signup('syn_stale', 'old-token-nobody-has')
    check('3 stale link stops sign-up with the message, creates nobody',
          b'This link no longer works' in r.data
          and User.query.filter_by(username='syn_stale').first() is None)

    signup('syn_plain', '')
    db.session.remove()
    plain = User.query.filter_by(username='syn_plain').first()
    check('3 plain sign-up is an individual',
          plain is not None and plain.organization_id is None
          and plain.org_status is None)

    # ------------------------------------------------------------------
    # 4. signed-in join request
    # ------------------------------------------------------------------
    login(client, s['individual'])
    client.post(f"/join/{s['token_b']}/request")
    ind = user_row(s['individual'])
    check('4 individual asks to join: pending in B',
          ind.organization_id == B and ind.org_status == 'pending'
          and ind.org_role == 'member')

    client.post(f"/join/{s['token_a']}/request")
    check('4 second join is refused while in an org',
          user_row(s['individual']).organization_id == B)

    # ------------------------------------------------------------------
    # 5. leader approves, rejects, removes in own org
    # ------------------------------------------------------------------
    login(client, s['leader_a'])
    client.post(f"/org/{A}/members/{s['pending_a']}/approve")
    check('5 leader approves a pending member',
          user_row(s['pending_a']).org_status == 'active')

    client.post(f"/org/{A}/members/{joiner_id}/reject")
    j = user_row(joiner_id)
    check('5 leader rejects clears all three org fields',
          j.organization_id is None and j.org_role is None
          and j.org_status is None)

    client.post(f"/org/{A}/members/{s['active_a']}/remove")
    m = user_row(s['active_a'])
    check('5 leader removes an active member and clears the fields',
          m.organization_id is None and m.org_role is None
          and m.org_status is None)
    # put that member back for the checks below
    db.session.remove()
    back = db.session.get(User, s['active_a'])
    back.organization_id, back.org_role, back.org_status = A, 'member', 'active'
    db.session.commit()

    # ------------------------------------------------------------------
    # 6-7. cross-org, self, leaders, unverified
    # ------------------------------------------------------------------
    r = client.post(f"/org/{A}/members/{s['member_b']}/approve")
    check("6 leader of A approves a member of B via A's URL: 403",
          r.status_code == 403)
    r = client.post(f"/org/{B}/members/{s['member_b']}/approve")
    check("6 leader of A uses B's URL: 403", r.status_code == 403)
    r = client.post(f"/org/{A}/members/{s['leader_a']}/remove")
    check('6 leader cannot remove self: 403', r.status_code == 403)
    client.post(f"/org/{A}/members/{s['unverified_a']}/approve")
    check('7 unverified pending member cannot be approved',
          user_row(s['unverified_a']).org_status == 'pending')

    # ------------------------------------------------------------------
    # 8-9. CENRO admin: own CENRO only; approve only without a leader
    # ------------------------------------------------------------------
    login(client, s['cenro_admin'])
    r = client.post(f"/org/{B}/leaders/{s['member_b']}/appoint")
    check('8 CENRO admin cannot appoint in another CENRO: 403',
          r.status_code == 403)

    client.post(f"/org/{A}/leaders/{s['active_a']}/appoint")
    check('8 CENRO admin appoints a leader in own CENRO',
          user_row(s['active_a']).org_role == 'leader')

    r = client.post(f"/org/{A}/members/{s['unverified_a']}/approve")
    check('9 CENRO admin cannot approve while an active leader exists: 403',
          r.status_code == 403)

    # Leader role check. The second leader is removed, leaving one leader.
    client.post(f"/org/{A}/leaders/{s['active_a']}/remove")
    check('8 CENRO admin removes a leader role',
          user_row(s['active_a']).org_role == 'member')

    # ------------------------------------------------------------------
    # 10. last active leader cannot leave
    # ------------------------------------------------------------------
    login(client, s['leader_a'])
    client.post('/org/leave')
    check('10 last active leader cannot leave',
          user_row(s['leader_a']).organization_id == A)

    # ------------------------------------------------------------------
    # 11. regenerate: old link dies, new one works
    # ------------------------------------------------------------------
    client.post(f'/org/{A}/token/regenerate')
    db.session.remove()
    new_token = db.session.get(Organization, A).join_token
    check('11 regenerate makes a new token', new_token != s['token_a'])
    r = client.get(f"/join/{s['token_a']}")
    check('11 old link no longer works',
          b'This link no longer works' in r.data)
    r = client.get(f'/join/{new_token}')
    check('11 new link works',
          r.status_code == 200 and b'Synthetic Org A' in r.data
          and b'This link no longer works' not in r.data)

    # ------------------------------------------------------------------
    # 12. members pages
    # ------------------------------------------------------------------
    login(client, s['leader_a'])
    r = client.get('/org/members')
    check('12 leader sees own members page', r.status_code == 200)
    r = client.get(f'/org/{B}/members')
    check("12 leader of A cannot open B's members page: 403",
          r.status_code == 403)

    login(client, s['member_b'])
    r = client.get('/org/members')
    check('12 plain member cannot open the members page: 403',
          r.status_code == 403)

    # ------------------------------------------------------------------
    # 13. organizations list
    # ------------------------------------------------------------------
    login(client, s['cenro_admin'])
    r = client.get('/org/organizations')
    check('13 CENRO admin list shows own CENRO only',
          r.status_code == 200 and b'Synthetic Org A' in r.data
          and b'Synthetic Org B' not in r.data
          and b'Synthetic Org C' not in r.data)

    login(client, s['provincial'])
    r = client.get('/org/organizations')
    check('13 provincial admin sees every organization',
          r.status_code == 200 and b'Synthetic Org A' in r.data
          and b'Synthetic Org B' in r.data and b'Synthetic Org C' in r.data)
    r = client.get(f'/org/{C}/members')
    check('13 provincial admin can open an org with no CENRO',
          r.status_code == 200)

    login(client, s['leader_a'])
    r = client.get('/org/organizations')
    check('13 leader (normal user) cannot open the list: 403',
          r.status_code == 403)

    # ------------------------------------------------------------------
    # 9b. fallback: no active leader, CENRO admin may approve
    # ------------------------------------------------------------------
    db.session.remove()
    org_d = Organization(organization_name='Synthetic Org D',
                         organization_type='POs', cenro='Urdaneta City')
    db.session.add(org_d)
    db.session.flush()
    d = org_d.organization_id
    waiting_d = make_user('syn_waiting_d', org_id=d, org_role='member',
                          org_status='pending')
    db.session.commit()
    login(client, s['cenro_admin'])
    client.post(f'/org/{d}/members/{waiting_d}/approve')
    check('9 CENRO admin approves when no active leader exists',
          user_row(waiting_d).org_status == 'active')

    # ------------------------------------------------------------------
    # 15. what each person sees on the pages
    # ------------------------------------------------------------------
    login(client, s['member_b'])
    r = client.get('/account')
    check('15 pending member sees the waiting banner',
          b'Waiting for your leader to approve you.' in r.data)
    check('15 pending member sees the leave button on My Account',
          b'Leave organization' in r.data)

    login(client, s['leader_a'])
    r = client.get('/account')
    check('15 leader sees My Organization in the sidebar',
          b'>My Organization<' in r.data)

    login(client, s['cenro_admin'])
    r = client.get('/account')
    check('15 CENRO admin sees the Organizations link',
          b'href="/org/organizations"' in r.data)

    login(client, s['provincial'])
    r = client.get('/account')
    check('15 person with no organization sees no banner or leave button',
          b'Waiting for your leader' not in r.data
          and b'Leave organization' not in r.data
          and b'>My Organization<' not in r.data)

    # ------------------------------------------------------------------
    # 14. audit rows
    # ------------------------------------------------------------------
    check('14 join requests are logged', audit_count('join_request') >= 1)
    check('14 approvals are logged', audit_count('approve_member') >= 1)
    check('14 rejections are logged', audit_count('reject_member') >= 1)
    check('14 removals are logged', audit_count('remove_member') >= 1)
    check('14 role changes are logged',
          audit_count('appoint_leader') >= 1
          and audit_count('remove_leader') >= 1)
    check('14 link regeneration is logged',
          audit_count('regenerate_join_link') >= 1)


def main():
    app = base.create_app()
    app.config['TESTING'] = True
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
    return 0 if passed == len(RESULTS) and RESULTS else 1


if __name__ == '__main__':
    sys.exit(main())
