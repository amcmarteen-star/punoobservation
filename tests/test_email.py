"""
Email test: request status emails and "forgot password".

Reuses the synthetic seed and throwaway SQLite database from
test_publish_boundary.py. Nothing touches the production Postgres, and no
real email is sent: with MAIL_SERVER empty, app/services/mailer.py keeps
each email in outbox(), and the SMTP checks use a fake server.

WHAT IS UNDER TEST

    request status   a CENRO decision emails the requester, copies the
                     contact person, escapes the note in the HTML version
    forgot form      same answer for known and unknown addresses; one
                     email per cooldown; nothing for a deactivated account
    reset link       works once, expires, refuses tampering; saving a new
                     password unlocks the account and sends a notice
    links            built from APP_BASE_URL, never the Host header; no
                     email at all once MAIL_SERVER is set without it
    SMTP             STARTTLS, login and one multipart message

RUN

    python tests/test_email.py

Exit code 0 when every check passes, 1 otherwise.
"""

import os
import re
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# importing this first points DATABASE_URL at a temporary SQLite file
import test_publish_boundary as base                    # noqa: E402

from app import create_app                              # noqa: E402
from app.extensions import db                           # noqa: E402
from app.models import AuditLog, Location, Request, User  # noqa: E402
from app.routes import auth as auth_routes              # noqa: E402
from app.services import mailer                         # noqa: E402


RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))


def flashes(client):
    with client.session_transaction() as s:
        return [m for _, m in s.get('_flashes', [])]


def reset_link(email):
    m = re.search(r"(/reset-password/[^\s<\"]+)", email['text'])
    return m.group(1) if m else None


def run(app, s):
    box = mailer.outbox()
    cfg = app.config

    # ------------------------------------------------------------------
    # request status
    # ------------------------------------------------------------------
    base.fresh()
    loc = Location.query.filter_by(barangay='Bacag').first()
    req = Request(user_id=s.citizen_id, location_id=loc.location_id,
                  request_type='New Planting Site', status='Submitted',
                  contact_name='Maria Santos',
                  contact_email='maria.contact@synthetic.test')
    db.session.add(req)
    db.session.commit()
    req_id = req.request_id

    admin = app.test_client()
    base.as_cenro(admin, s)
    box.clear()
    r = admin.post('/admin/requests/%d/review' % req_id,
                   data={'status': 'Under Review', 'review_note': ''})
    check("request: saving a status still redirects", r.status_code == 302,
          r.status_code)
    check("request: one email per decision", len(box) == 1, box)
    mail = box[-1] if box else {}
    check("request: sent to the account's address",
          mail.get('to') == [s.citizen_name + '@synthetic.test'], mail.get('to'))
    check("request: contact person copied in",
          mail.get('cc') == ['maria.contact@synthetic.test'], mail.get('cc'))
    check("request: subject names the status",
          mail.get('subject') == "Your reforestation request is now Under Review",
          mail.get('subject'))
    check("request: greets the contact person",
          'Hello Maria Santos' in mail.get('text', ''))
    check("request: links to My Requests",
          'http://localhost/requests' in mail.get('text', ''), mail.get('text'))

    box.clear()
    note = 'Site overlaps <script>alert(1)</script> a protected area.'
    admin.post('/admin/requests/%d/review' % req_id,
               data={'status': 'Rejected', 'review_note': note})
    mail = box[-1] if box else {}
    check("request: rejection carries the note",
          note in mail.get('text', '') and 'Rejected' in mail.get('subject', ''))
    check("request: note is escaped in the HTML email",
          '<script>' not in (mail.get('html') or '')
          and '&lt;script&gt;' in (mail.get('html') or ''))

    # ------------------------------------------------------------------
    # forgot password form
    # ------------------------------------------------------------------
    guest = app.test_client()
    login_page = guest.get('/login').get_data(as_text=True)
    check("forgot: link on the sign-in page", '/forgot-password' in login_page)
    check("forgot: form opens",
          guest.get('/forgot-password').status_code == 200)

    box.clear()
    r = guest.post('/forgot-password',
                   data={'email_address': 'nobody@synthetic.test'})
    unknown_msg = flashes(guest)
    check("forgot: unknown address sends nothing", len(box) == 0, box)

    guest = app.test_client()
    auth_routes._last_reset_email.clear()
    r = guest.post('/forgot-password',
                   data={'email_address': '  SYN_OFFICER@synthetic.test '})
    known_msg = flashes(guest)
    check("forgot: same message for known and unknown addresses",
          known_msg == unknown_msg and known_msg, (known_msg, unknown_msg))
    check("forgot: known address (any case, spaces) gets one email",
          len(box) == 1, box)
    mail = box[-1] if box else {}
    link = reset_link(mail) if mail else None
    check("forgot: email carries a reset link", bool(link), mail.get('text'))
    check("forgot: request is in the audit log",
          AuditLog.query.filter_by(action='password_reset_requested',
                                   entity_id=s.officer_id).count() == 1)

    guest.post('/forgot-password',
               data={'email_address': 'syn_officer@synthetic.test'})
    check("forgot: second request inside the cooldown sends nothing",
          len(box) == 1, len(box))

    base.fresh()
    citizen = db.session.get(User, s.citizen_id)
    citizen.is_active = False
    db.session.commit()
    box.clear()
    guest.post('/forgot-password',
               data={'email_address': s.citizen_name + '@synthetic.test'})
    check("forgot: deactivated account gets no email", len(box) == 0, box)
    citizen = db.session.get(User, s.citizen_id)
    citizen.is_active = True
    db.session.commit()

    # ------------------------------------------------------------------
    # the reset link
    # ------------------------------------------------------------------
    base.fresh()
    officer = db.session.get(User, s.officer_id)
    officer.locked_until = base.datetime(2099, 1, 1)
    officer.failed_login_count = 3
    officer.must_change_password = True
    db.session.commit()

    page = guest.get(link).get_data(as_text=True)
    check("reset: link opens the form for that account",
          'Choose a new password' in page and s.officer_name in page)

    r = guest.post(link, data={'new_password': 'NewPass123',
                               'confirm_password': 'NewPass124'})
    check("reset: mismatched passwords refused",
          'do not match' in r.get_data(as_text=True))
    r = guest.post(link, data={'new_password': 'short',
                               'confirm_password': 'short'})
    check("reset: weak password refused",
          'at least' in r.get_data(as_text=True))

    box.clear()
    r = guest.post(link, data={'new_password': 'NewPass123',
                               'confirm_password': 'NewPass123'})
    base.fresh()
    officer = db.session.get(User, s.officer_id)
    check("reset: saved and sent to sign in",
          r.status_code == 302 and '/login' in r.headers.get('Location', ''))
    check("reset: new password works", officer.check_password('NewPass123'))
    check("reset: old password no longer works",
          not officer.check_password('synthetic-password'))
    check("reset: lock and forced change cleared",
          officer.locked_until is None and officer.failed_login_count == 0
          and not officer.must_change_password)
    check("reset: 'password changed' notice emailed",
          len(box) == 1 and 'was changed' in box[-1]['subject'], box)
    check("reset: change is in the audit log",
          AuditLog.query.filter_by(action='password_reset',
                                   entity_id=s.officer_id).count() == 1)

    page = guest.get(link).get_data(as_text=True)
    check("reset: the same link is refused afterwards",
          'already used' in page, page[:200])

    with app.test_request_context():
        token = auth_routes.make_reset_token(officer)
    check("reset: tampered link refused",
          'not valid' in guest.get('/reset-password/' + token[:-2] + 'xx')
          .get_data(as_text=True))
    cfg['PASSWORD_RESET_MINUTES'] = -1
    check("reset: expired link refused",
          'expired' in guest.get('/reset-password/' + token).get_data(as_text=True))
    cfg['PASSWORD_RESET_MINUTES'] = 60

    # ------------------------------------------------------------------
    # links come from APP_BASE_URL, never from the Host header
    # ------------------------------------------------------------------
    cfg['APP_BASE_URL'] = 'https://punoobservation.app'
    auth_routes._last_reset_email.clear()
    box.clear()
    app.test_client().post('/forgot-password',
                           data={'email_address': 'syn_superadmin@synthetic.test'},
                           headers={'Host': 'evil.example'})
    text = box[-1]['text'] if box else ''
    check("links: reset link uses APP_BASE_URL, not the Host header",
          'https://punoobservation.app/reset-password/' in text
          and 'evil.example' not in text, text)

    # MAIL_SERVER set but no APP_BASE_URL: refuse rather than guess
    sent = []
    real_deliver = mailer._deliver
    mailer._deliver = lambda settings, msg: sent.append(msg) or True
    try:
        cfg['MAIL_SERVER'] = 'smtp.synthetic.test'
        cfg['APP_BASE_URL'] = ''
        auth_routes._last_reset_email.clear()
        r = app.test_client().post(
            '/forgot-password',
            data={'email_address': 'syn_penro@synthetic.test'})
        admin.post('/admin/requests/%d/review' % req_id,
                   data={'status': 'Under Review', 'review_note': ''})
        check("links: nothing sent while APP_BASE_URL is missing",
              not sent and r.status_code == 302, [m['Subject'] for m in sent])

        # ---------------------------------------------------------------
        # SMTP: what the real server would receive
        # ---------------------------------------------------------------
        mailer._deliver = real_deliver
        calls = []

        class FakeSMTP:
            def __init__(self, host, port, timeout=None):
                calls.append(('connect', host, port))
            def starttls(self, context=None):
                calls.append(('starttls',))
            def login(self, user, password):
                calls.append(('login', user, password))
            def send_message(self, msg):
                calls.append(('send', msg))
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        real_smtp = mailer.smtplib.SMTP
        mailer.smtplib.SMTP = FakeSMTP
        cfg.update(APP_BASE_URL='https://punoobservation.app',
                   MAIL_USERNAME='smtp-user', MAIL_PASSWORD='smtp-key',
                   MAIL_SECURITY='starttls', MAIL_PORT=587)
        try:
            with app.test_request_context():
                ok = mailer.send_email('someone@synthetic.test', 'Hello',
                                       'Plain body', '<p>HTML body</p>')
        finally:
            mailer.smtplib.SMTP = real_smtp
        kinds = [c[0] for c in calls]
        msg = next((c[1] for c in calls if c[0] == 'send'), None)
        check("smtp: connects, STARTTLS, logs in, sends",
              ok and kinds == ['connect', 'starttls', 'login', 'send'], kinds)
        check("smtp: login uses the configured account",
              ('login', 'smtp-user', 'smtp-key') in calls)
        check("smtp: plain and HTML versions in one message",
              msg is not None and msg.is_multipart()
              and [p.get_content_type() for p in msg.iter_parts()]
              == ['text/plain', 'text/html'])
        check("smtp: From and Message-ID use the sender's domain",
              msg is not None and 'noreply@punoobservation.app' in msg['From']
              and msg['Message-ID'].endswith('@punoobservation.app>'))

        def broken(*a, **k):
            raise OSError("connection refused")
        mailer.smtplib.SMTP = broken
        try:
            with app.test_request_context():
                ok = mailer.send_email('someone@synthetic.test', 'Hi', 'Body')
        finally:
            mailer.smtplib.SMTP = real_smtp
        check("smtp: a server failure returns False instead of crashing",
              ok is False)
    finally:
        mailer._deliver = real_deliver
        cfg.update(MAIL_SERVER='', APP_BASE_URL='')


def print_results():
    print()
    print('EMAIL  (synthetic data, nothing sent)')
    print('-' * 74)
    for name, ok, detail in RESULTS:
        print('  [%s] %s' % ('PASS' if ok else 'FAIL', name))
        if detail and not ok:
            print('         %s' % (detail,))
    failed = sum(1 for _, ok, _ in RESULTS if not ok)
    print('-' * 74)
    print('SUMMARY:  %d checks   %d passed   %d failed'
          % (len(RESULTS), len(RESULTS) - failed, failed))
    print()
    return failed


def main():
    app = create_app()
    app.config['TESTING'] = True
    app.config['MAIL_SERVER'] = ''
    app.config['APP_BASE_URL'] = ''

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
