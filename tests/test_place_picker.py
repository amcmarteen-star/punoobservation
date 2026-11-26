"""
The shared place picker (Step 2a).

Runs the real Flask routes against a throwaway SQLite database.

WHAT IS UNDER TEST

    1  Recommendations, Register, My Account and New Request each render the
       shared picker, and none still has its own municipality dropdown
    2  Register and My Account submit a location id; New Request submits names
    3  the combobox code exists once, in static/js/place-picker.js
    4  every page that needs it loads the script

The forms themselves are exercised by the other tests (sign-up in
test_org_membership.py, the barangay setter in test_dashboards.py, and
requests in test_request_org_gate.py).

RUN

    python tests/test_place_picker.py
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_publish_boundary as base                    # noqa: E402
from app.extensions import db                            # noqa: E402
from app.models import Organization, User                # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append({'name': name, 'ok': bool(ok)})
    print(('PASS  ' if ok else 'FAIL  ') + name
          + (f'  [{detail}]' if detail and not ok else ''))
    return bool(ok)


def no_old_dropdown(html):
    return not re.search(r'<select[^>]*name="(municipality|barangay|location_id)"', html) \
        and 'reg_province' not in html


def run(app):
    s = base.seed()
    org_id = db.session.query(Organization.organization_id).first()[0]
    member = User(username='syn_picker_member', email_address='syn_picker@example.test',
                  role='normal_user', organization_id=org_id, org_role='member',
                  org_status='active', email_verified=True)
    member.set_password('Synthetic-pass-1')
    db.session.add(member)
    db.session.commit()

    guest = app.test_client()
    citizen = app.test_client()
    base.login(citizen, s.citizen_id, s.citizen_name, 'normal_user', None)
    mem = app.test_client()
    base.login(mem, member.user_id, 'syn_picker_member', 'normal_user', None)

    pages = {
        'Recommendations': citizen.get('/recommendations').get_data(as_text=True),
        'Register': guest.get('/register').get_data(as_text=True),
        'My Account': citizen.get('/account').get_data(as_text=True),
        'New Request': mem.get('/requests').get_data(as_text=True),
    }
    for name, html in pages.items():
        check(f'1 {name} renders the shared picker',
              'id="' in html and 'data-role="municipality"' in html
              and 'place-combo-list' in html)
        check(f'1 {name} has no old municipality dropdown', no_old_dropdown(html))
        check(f'4 {name} loads place-picker.js', 'js/place-picker.js' in html)

    check('2 Register submits a location id',
          'name="location_id"' in pages['Register']
          and 'data-role="location-id"' in pages['Register'])
    check('2 My Account submits a location id',
          'name="location_id"' in pages['My Account'])
    nr = pages['New Request']
    check('2 New Request submits municipality and barangay names',
          'name="municipality"' in nr and 'name="barangay"' in nr
          and 'name="location_id"' not in nr)
    check('2 Recommendations keeps its own reload lists',
          'id="municipality-data"' in pages['Recommendations']
          and 'id="barangay-data"' in pages['Recommendations'])

    # the combobox code lives in one file
    copies = []
    for folder, _dirs, files in os.walk(os.path.join(ROOT, 'app')):
        for f in files:
            if f.endswith(('.html', '.js')):
                path = os.path.join(folder, f)
                with open(path, encoding='utf-8', errors='ignore') as fh:
                    if 'function makeCombo' in fh.read():
                        copies.append(os.path.relpath(path, ROOT))
    check('3 the combobox code exists once, in place-picker.js',
          copies == [os.path.join('app', 'static', 'js', 'place-picker.js')], copies)
    check('3 the old register.js is gone',
          not os.path.exists(os.path.join(ROOT, 'app', 'static', 'javascript', 'register.js')))


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
    return 0 if RESULTS and passed == len(RESULTS) else 1


if __name__ == '__main__':
    sys.exit(main())
