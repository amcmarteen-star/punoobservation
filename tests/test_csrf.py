"""
CSRF protection, with CSRF ON.

Every other test file turns CSRF off so it can test business rules. This
one leaves it on, to check the protection itself.

WHAT IS UNDER TEST

    1  a form POST with no token is refused (400)
    2  a form POST with the token from the page is accepted
    3  a fetch POST with a bad token gets JSON 400 with the message
    4  a POST to /logout without a token does not sign the user out
    5  a POST to /logout with the token signs the user out
    6  a GET to /logout is not allowed (405)

RUN

    python tests/test_csrf.py

Exit code 0 when every check passes, 1 otherwise.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# importing this first points DATABASE_URL at a temporary SQLite file
import test_publish_boundary as base                    # noqa: E402
from app.extensions import db                            # noqa: E402
from app.models import User                              # noqa: E402

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append({'name': name, 'ok': bool(ok)})
    print(('PASS  ' if ok else 'FAIL  ') + name
          + (f'  [{detail}]' if detail and not ok else ''))
    return bool(ok)


def token_from(html):
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return m.group(1) if m else None


def meta_token_from(html):
    m = re.search(r'name="csrf-token" content="([^"]+)"', html)
    return m.group(1) if m else None


def run(app):
    client = app.test_client()

    # ------------------------------------------------------------------
    # 1-2. the sign-in form
    # ------------------------------------------------------------------
    page = client.get('/login').get_data(as_text=True)
    token = token_from(page)
    check('the sign-in page carries a token', bool(token))

    r = client.post('/login', data={'username': 'nobody', 'password': 'x'})
    # Refused: sent back to the page with a message, nothing signed in.
    with client.session_transaction() as s:
        signed_in = 'user_id' in s
    check('1 POST without a token is refused (redirected, not accepted)',
          r.status_code == 302 and not signed_in, r.status_code)

    r = client.post('/login', data={'username': 'nobody', 'password': 'x',
                                    'csrf_token': token})
    check('2 POST with the page token is accepted (not 400)',
          r.status_code == 200 and b'Incorrect Username or Password' in r.data,
          r.status_code)

    # ------------------------------------------------------------------
    # 3. fetch with a bad token: JSON, not a redirect
    # ------------------------------------------------------------------
    r = client.post('/login', data={}, headers={'X-CSRFToken': 'bad-token'})
    body = r.get_json(silent=True) or {}
    check('3 fetch POST with a bad token gets JSON 400 with the message',
          r.status_code == 400 and body.get('ok') is False
          and 'expired' in body.get('error', ''),
          (r.status_code, body))

    # ------------------------------------------------------------------
    # 4-6. sign-out
    # ------------------------------------------------------------------
    # The user row is made in its own app context. The requests below must
    # NOT run inside an outer app context: Flask-WTF caches the token in g,
    # which would then be shared by every request.
    with app.app_context():
        db.session.remove()
        user = User(username='syn_csrf_user',
                    email_address='syn_csrf_user@example.test',
                    role='normal_user', email_verified=True)
        user.set_password('Synthetic-pass-1')
        db.session.add(user)
        db.session.commit()
        uid = user.user_id
    base.login(client, uid, 'syn_csrf_user', 'normal_user', None)

    page = client.get('/account').get_data(as_text=True)
    token = meta_token_from(page)
    check('signed-in pages carry the meta token', bool(token))

    r = client.post('/logout')
    with client.session_transaction() as s:
        still_in = s.get('user_id') == uid
    check('4 logout without a token does not sign out',
          still_in and r.status_code == 302)

    r = client.post('/logout', data={'csrf_token': token})
    with client.session_transaction() as s:
        signed_out = 'user_id' not in s
    check('5 logout with the token signs out', signed_out
          and r.status_code == 302)

    r = client.get('/logout')
    check('6 GET /logout is not allowed (405)', r.status_code == 405,
          r.status_code)


def main():
    app = base.create_app()
    app.config['TESTING'] = True
    # CSRF stays ON here. Do not turn it off in this file.
    if app.config.get('WTF_CSRF_ENABLED') is False:
        app.config['WTF_CSRF_ENABLED'] = True

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
