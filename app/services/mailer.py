"""
Sending email.

One function sends every email the system writes: send_email(). It
speaks plain SMTP, which every email service offers (Brevo, Resend,
SendGrid, Mailgun, Gmail), so changing service is a change to .env only.
The settings are in app/config.py, under "email".

TWO MODES
---------
MAIL_SERVER set     the email is handed to that server, on a background
                    thread, so a slow service never holds up the page
MAIL_SERVER empty   nothing leaves the machine: the email is written to
                    the server log, and kept in outbox() for the tests

NEVER FATAL
-----------
An email is a courtesy on top of the record in the database: a request is
approved whether or not the requester's inbox hears about it. So
send_email() never raises. A failure is logged and the page carries on.

The email text lives in templates/email/, one .txt and one .html per kind
of email, rendered by send_template().
"""

import logging
import smtplib
import ssl
import threading
from email.message import EmailMessage
from email.utils import make_msgid

from flask import current_app, render_template, url_for

log = logging.getLogger(__name__)

# The newest emails written in log mode, newest last, for the tests.
_OUTBOX_LIMIT = 50


def outbox():
    """Emails written in log mode (MAIL_SERVER empty), oldest first."""
    return current_app.extensions.setdefault('mail_outbox', [])


def send_email(to, subject, text, html=None, cc=None):
    """
    Send one email. Returns True when it was handed over (or logged),
    False when it could not be. Never raises.

    to and cc are addresses or lists of them. text is the plain version
    every inbox can show; html, when given, is the formatted one.
    """
    to = _addresses(to)
    cc = [a for a in _addresses(cc) if a not in to]
    if not to:
        return False

    cfg = current_app.config
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = cfg['MAIL_FROM']
    msg['To'] = ', '.join(to)
    if cc:
        msg['Cc'] = ', '.join(cc)
    msg['Message-ID'] = make_msgid(domain=_sender_domain(cfg['MAIL_FROM']))
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype='html')

    if not cfg['MAIL_SERVER']:
        box = outbox()
        box.append({'to': to, 'cc': cc, 'subject': subject,
                    'text': text, 'html': html})
        del box[:-_OUTBOX_LIMIT]
        current_app.logger.info(
            "Email not sent (MAIL_SERVER is empty).\nTo: %s\nSubject: %s\n\n%s",
            msg['To'], subject, text)
        return True

    settings = {k: cfg[k] for k in (
        'MAIL_SERVER', 'MAIL_PORT', 'MAIL_USERNAME', 'MAIL_PASSWORD',
        'MAIL_SECURITY')}
    if cfg.get('TESTING'):
        return _deliver(settings, msg)
    threading.Thread(target=_deliver, args=(settings, msg), daemon=True).start()
    return True


def send_template(template, to, subject, cc=None, **context):
    """
    Render templates/email/<template>.txt and .html with context, then
    send. Every email also gets site_url, the link to the front page.
    """
    try:
        context.setdefault('site_url', external_url('dashboard.home'))
        text = render_template(f'email/{template}.txt', **context)
        html = render_template(f'email/{template}.html', **context)
    except Exception:
        log.exception("Could not write the %s email", template)
        return False
    return send_email(to, subject, text, html, cc=cc)


def external_url(endpoint, **values):
    """
    A full link to a page of this site, for an email.

    Built from APP_BASE_URL, never from the request: the Host header comes
    from the visitor, and a forged one would put their address into a
    password reset link sent to someone else. Without APP_BASE_URL the
    request's own address is used, which is safe only while nothing is
    really sent, so that case refuses once MAIL_SERVER is set.
    """
    cfg = current_app.config
    base = cfg['APP_BASE_URL']
    if base:
        return base + url_for(endpoint, **values)
    if cfg['MAIL_SERVER']:
        raise RuntimeError(
            "Set APP_BASE_URL (e.g. https://punoobservation.app) before "
            "sending email: links in emails are built from it.")
    return url_for(endpoint, _external=True, **values)


def email_link(endpoint, **values):
    """
    external_url() for a link inside an email's text. Without
    APP_BASE_URL it gives the bare path instead of raising: the email
    itself is then refused by send_template(), which logs why.
    """
    try:
        return external_url(endpoint, **values)
    except RuntimeError:
        return url_for(endpoint, **values)


def _deliver(settings, msg):
    """Hand one message to the SMTP server. Logs and returns False on any
    failure: wrong password, server down, address refused."""
    try:
        host, port = settings['MAIL_SERVER'], settings['MAIL_PORT']
        context = ssl.create_default_context()
        if settings['MAIL_SECURITY'] == 'ssl':
            server = smtplib.SMTP_SSL(host, port, timeout=20, context=context)
        else:
            server = smtplib.SMTP(host, port, timeout=20)
            if settings['MAIL_SECURITY'] == 'starttls':
                server.starttls(context=context)
        with server:
            if settings['MAIL_USERNAME']:
                server.login(settings['MAIL_USERNAME'], settings['MAIL_PASSWORD'])
            server.send_message(msg)
        return True
    except Exception:
        log.exception("Email to %s (%s) could not be sent", msg['To'], msg['Subject'])
        return False


def _addresses(value):
    if not value:
        return []
    if isinstance(value, str):
        value = [value]
    return [a.strip() for a in value if a and a.strip()]


def _sender_domain(sender):
    """'PuNoObservation <noreply@punoobservation.app>' -> the domain."""
    address = sender.rsplit('<', 1)[-1].rstrip('>')
    return address.rsplit('@', 1)[-1] or None
