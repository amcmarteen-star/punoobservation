"""
Public report detail test.

Checks the read-only report page opened from the map's monitoring
history panel: /monitoring-reports/<id>.

Reuses the synthetic seed and throwaway SQLite database from
test_publish_boundary.py. Nothing touches the production Postgres.

WHAT IS UNDER TEST

The map is open to guests, and its history panel lists approved
monitoring visits. "View full report" must show those same visits in
full, and nothing the panel would not show:

    approved report      -> visible, same CENRO rules as the map
    pending or rejected  -> 404
    another CENRO        -> sent back to the map
    reviewer's note      -> never shown on this page

RUN

    python tests/test_public_report_detail.py

Exit code 0 when every check passes, 1 otherwise.
"""

import os
import sys
import json
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# importing this first points DATABASE_URL at a temporary SQLite file
import test_publish_boundary as base                    # noqa: E402

from app import create_app                              # noqa: E402
from app.extensions import db                           # noqa: E402
from app.models import MonitoringReport                 # noqa: E402


RESULTS = []

INTERNAL_NOTE = 'INTERNAL-REVIEWER-NOTE-7731'


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))


def page(client, report_id):
    r = client.get('/monitoring-reports/%d' % report_id)
    return r, r.data.decode('utf-8')


def run(app, s):
    client = app.test_client()

    # --- arrange ------------------------------------------------------
    # rp4 (site B, Urdaneta) is already approved by the seed.
    # Give it a reviewer's note, reject rp3, and approve rp5 (Dagupan).
    base.fresh()
    rp3 = db.session.get(MonitoringReport, s.rp3_id)
    rp4 = db.session.get(MonitoringReport, s.rp4_id)
    rp5 = db.session.get(MonitoringReport, s.rp5_id)
    rp3.approval_status = 'Rejected'
    rp4.review_note = INTERNAL_NOTE
    rp5.approval_status = 'Approved'
    db.session.commit()

    # --- guests -------------------------------------------------------
    base.logout(client)

    r, body = page(client, s.rp4_id)
    check('guest can open an approved report', r.status_code == 200,
          'status=%s' % r.status_code)
    check('the page shows the report\'s site',
          'Synthetic Site B' in body)
    check('the page has no decision form', 'Save decision' not in body)
    check('the reviewer\'s note is hidden', INTERNAL_NOTE not in body)
    check('"Back to the map" reopens this site\'s history',
          'Back to the map' in body
          and ('site=%d' % s.site_b_id) in body
          and 'view=history' in body)

    r, _ = page(client, s.rp1_id)
    check('a pending report is 404', r.status_code == 404,
          'status=%s' % r.status_code)

    r, _ = page(client, s.rp3_id)
    check('a rejected report is 404', r.status_code == 404,
          'status=%s' % r.status_code)

    r, _ = page(client, 999999)
    check('a missing report is 404', r.status_code == 404,
          'status=%s' % r.status_code)

    # --- the link target matches what the panel lists -----------------
    r = client.get('/api/site-history/%d' % s.site_b_id)
    ids = [h['report_id'] for h in json.loads(r.data)['history']]
    check('the history panel lists the approved report the link opens',
          s.rp4_id in ids, 'history ids=%s' % ids)

    # --- CENRO jurisdiction -------------------------------------------
    base.login(client, s.dagupan_admin_id, s.dagupan_admin_name,
               'admin', 'Dagupan')
    r, _ = page(client, s.rp4_id)
    check('a Dagupan admin is sent back to the map for an Urdaneta report',
          r.status_code == 302
          and '/gis-map' in (r.headers.get('Location') or ''),
          'status=%s location=%s' % (r.status_code,
                                     r.headers.get('Location')))
    r, _ = page(client, s.rp5_id)
    check('a Dagupan admin can open a Dagupan report',
          r.status_code == 200, 'status=%s' % r.status_code)

    base.login(client, s.officer_id, s.officer_name, 'field_officer',
               'Urdaneta City')
    r, _ = page(client, s.rp5_id)
    check('an Urdaneta officer is sent back to the map for a Dagupan report',
          r.status_code == 302, 'status=%s' % r.status_code)
    r, _ = page(client, s.rp4_id)
    check('an Urdaneta officer can open an Urdaneta report',
          r.status_code == 200, 'status=%s' % r.status_code)

    # --- the existing officer route still works -----------------------
    r = client.get('/reports/%d' % s.rp4_id)
    check('the officer\'s own report page is unchanged',
          r.status_code == 200, 'status=%s' % r.status_code)


def print_results():
    print()
    print('PUBLIC REPORT DETAIL  (synthetic data)')
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
