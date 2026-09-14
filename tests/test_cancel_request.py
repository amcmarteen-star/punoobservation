"""
Request filter and cancellation test.

Checks the My Requests page (/requests): the status filter, and a
requester cancelling their own request (/requests/<id>/cancel).

Reuses the synthetic seed and throwaway SQLite database from
test_publish_boundary.py. Nothing touches the production Postgres.

WHAT IS UNDER TEST

    filter      Pending is the default and covers Submitted + Under Review
    cancel      only the requester, only while pending; the request and
                its attachment rows are deleted, admins are told, and the
                audit log records it

RUN

    python tests/test_cancel_request.py

Exit code 0 when every check passes, 1 otherwise.
"""

import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# importing this first points DATABASE_URL at a temporary SQLite file
import test_publish_boundary as base                    # noqa: E402

from app import create_app                              # noqa: E402
from app.extensions import db                           # noqa: E402
from app.models import (                                # noqa: E402
    AuditLog, Location, Notification, Request, RequestAttachment,
)


RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))


def mk_request(user_id, location_id, status, request_type):
    r = Request(user_id=user_id, location_id=location_id,
                request_type=request_type, status=status)
    db.session.add(r)
    db.session.flush()
    return r


def exists(request_id):
    base.fresh()
    return db.session.get(Request, request_id) is not None


def cancel(client, request_id, status='Pending'):
    return client.post('/requests/%d/cancel' % request_id,
                       data={'status': status}, follow_redirects=False)


def run(app, s):
    client = app.test_client()

    # --- arrange: one request per status for the citizen, one for the officer
    base.fresh()
    loc = Location.query.filter_by(barangay='Bacag').first()
    submitted = mk_request(s.citizen_id, loc.location_id, 'Submitted', 'TYPE-SUBMITTED')
    review = mk_request(s.citizen_id, loc.location_id, 'Under Review', 'TYPE-REVIEW')
    approved = mk_request(s.citizen_id, loc.location_id, 'Approved', 'TYPE-APPROVED')
    rejected = mk_request(s.citizen_id, loc.location_id, 'Rejected', 'TYPE-REJECTED')
    others = mk_request(s.officer_id, loc.location_id, 'Submitted', 'TYPE-OFFICER')
    db.session.add(RequestAttachment(request_id=submitted.request_id,
                                     file_url='uploads/requests/does-not-exist.pdf',
                                     original_name='letter.pdf'))
    db.session.commit()
    ids = {k: v.request_id for k, v in [('submitted', submitted), ('review', review),
                                       ('approved', approved), ('rejected', rejected),
                                       ('others', others)]}

    # --- filter ---------------------------------------------------------
    base.login(client, s.citizen_id, s.citizen_name, 'normal_user', None)

    body = client.get('/requests').data.decode('utf-8')
    check('default view is Pending: shows Submitted and Under Review',
          'TYPE-SUBMITTED' in body and 'TYPE-REVIEW' in body)
    check('default view hides Approved and Rejected',
          'TYPE-APPROVED' not in body and 'TYPE-REJECTED' not in body)
    check('another user\'s request is never listed', 'TYPE-OFFICER' not in body)
    check('pending rows show a Cancel button',
          body.count('onclick="reqOpenCancel(this)"') == 2,
          'buttons=%d' % body.count('onclick="reqOpenCancel(this)"'))
    check('the confirmation modal is on the page',
          'id="req-cancel-modal"' in body and 'Yes, cancel request' in body)

    body = client.get('/requests?status=Approved').data.decode('utf-8')
    check('Approved filter shows only approved',
          'TYPE-APPROVED' in body and 'TYPE-SUBMITTED' not in body
          and 'TYPE-REJECTED' not in body)
    check('reviewed rows have no Cancel button',
          'onclick="reqOpenCancel(this)"' not in body)

    body = client.get('/requests?status=Rejected').data.decode('utf-8')
    check('Rejected filter shows only rejected',
          'TYPE-REJECTED' in body and 'TYPE-APPROVED' not in body)

    body = client.get('/requests?status=all').data.decode('utf-8')
    check('All shows all four of the user\'s requests',
          all(t in body for t in ('TYPE-SUBMITTED', 'TYPE-REVIEW',
                                  'TYPE-APPROVED', 'TYPE-REJECTED')))

    # --- who may cancel -------------------------------------------------
    base.logout(client)
    r = cancel(client, ids['submitted'])
    check('anonymous cancel is refused',
          r.status_code == 302 and exists(ids['submitted']),
          'status=%s location=%s' % (r.status_code, r.headers.get('Location')))

    base.login(client, s.citizen_id, s.citizen_name, 'normal_user', None)
    cancel(client, ids['others'])
    check('a user cannot cancel someone else\'s request', exists(ids['others']))

    cancel(client, ids['approved'])
    check('an approved request cannot be cancelled', exists(ids['approved']))

    cancel(client, ids['rejected'])
    check('a rejected request cannot be cancelled', exists(ids['rejected']))

    # --- cancelling -----------------------------------------------------
    r = cancel(client, ids['submitted'], status='Pending')
    check('owner can cancel a Submitted request', not exists(ids['submitted']))
    check('redirects back to the same filter',
          r.status_code == 302 and 'status=Pending' in (r.headers.get('Location') or ''),
          'location=%s' % r.headers.get('Location'))

    base.fresh()
    check('its attachment rows are deleted too',
          RequestAttachment.query.filter_by(request_id=ids['submitted']).count() == 0)
    check('the audit log records the cancellation',
          AuditLog.query.filter_by(action='cancel_request',
                                   entity_id=ids['submitted']).count() == 1)
    check('admins are notified',
          Notification.query.filter(
              Notification.user_id == s.cenro_admin_id,
              Notification.message.like('%cancelled their request%')).count() >= 1)

    cancel(client, ids['review'])
    check('owner can cancel an Under Review request', not exists(ids['review']))

    r = cancel(client, ids['submitted'])
    check('cancelling an already-deleted request just redirects',
          r.status_code == 302)


def print_results():
    print()
    print('REQUEST FILTER AND CANCEL  (synthetic data)')
    print('-' * 74)
    for name, ok, detail in RESULTS:
        print('  [%s] %s' % ('PASS' if ok else 'FAIL', name))
        if detail and not ok:
            print('         %s' % detail)
    failed = sum(1 for _, ok, _ in RESULTS if not ok)
    print('-' * 74)
    print('SUMMARY:  %d checks   %d passed   %d failed'
          % (len(RESULTS), len(RESULTS) - failed, failed))
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
            s = base.seed()
            run(app, s)
            failed = print_results()
    finally:
        shutil.rmtree(base.TMPDIR, ignore_errors=True)

    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
