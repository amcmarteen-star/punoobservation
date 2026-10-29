import math
import time
from collections import defaultdict
from datetime import timedelta

import hashlib

from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash,
    current_app, jsonify,
)
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from app.extensions import db
from app.models import User, Organization, Location, Site
from app.services.mailer import email_link, external_url, send_template
from app.utils.audit import log_action, log_login
from app.utils.security import password_problem
from app.utils.timeutil import manila_now

auth_bp = Blueprint('auth', __name__)

def _register_choices():
    """Places and organizations for the sign-up location picker.

    An organization has no address of its own. It belongs to the
    barangays where it has sites, so one with sites in two barangays
    is offered in both.
    """
    locations = [
        {"id": l.location_id, "province": l.province,
         "municipality": l.municipality, "barangay": l.barangay}
        for l in Location.query.order_by(
            Location.province, Location.municipality, Location.barangay
        )
    ]

    org_locations = defaultdict(set)
    for org_id, loc_id in db.session.query(
        Site.organization_id, Site.location_id
    ).distinct():
        org_locations[org_id].add(loc_id)

    organizations = [
        {"id": o.organization_id,
         "label": f"{o.organization_name} ({o.organization_type})",
         "locations": sorted(org_locations[o.organization_id])}
        for o in Organization.query.order_by(Organization.organization_name)
        if org_locations[o.organization_id]
    ]
    return locations, organizations


def _render_register(error=None):
    locations, organizations = _register_choices()
    return render_template(
        'Register.html', error=error, form=request.form,
        locations=locations, organizations=organizations,
    )


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        email_address = request.form.get('email_address', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirmPassword', '').strip()
        location_id = request.form.get('location_id', '')
        organization_id = request.form.get('organization_id', '')

        if not username or not password or not email_address:
            return _render_register("Please fill in all required fields!")

        if confirm_password != password:
            return _render_register("Passwords do not match!")

        problem = password_problem(password)
        if problem:
            return _render_register(problem)

        # Province, municipality and barangay come before the
        # organization, so a barangay is required even for individuals.
        location = (db.session.get(Location, int(location_id))
                    if location_id.isdigit() else None)
        if location is None:
            return _render_register(
                "Please choose your province, municipality and barangay."
            )

        # The organization must be one registered in that barangay.
        if organization_id:
            in_barangay = organization_id.isdigit() and db.session.query(
                Site.query.filter_by(
                    organization_id=int(organization_id),
                    location_id=location.location_id,
                ).exists()
            ).scalar()
            if not in_barangay:
                return _render_register(
                    "That organization is not registered in the barangay "
                    "you chose."
                )

        existing_user = User.query.filter(
            (User.username == username) | (User.email_address == email_address)
        ).first()

        if existing_user:
            return _render_register("Username or Email already exists!")

        new_user = User(
            username=username,
            email_address=email_address,
            role="normal_user",
            organization_id=int(organization_id) if organization_id else None
        )
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('auth.login'))

    return _render_register()


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()
        cfg = current_app.config
        now = manila_now()

        # Locked after too many wrong passwords. Checked before the
        # password, so guessing cannot continue while the lock lasts.
        if user and user.locked_until and user.locked_until > now:
            log_login(username, False, user_id=user.user_id,
                      detail='Blocked: login locked after wrong passwords')
            return render_template(
                'Log_in.html', error=_locked_message(user.locked_until, now))

        # Longer than any allowed password: refused without hashing it,
        # because hashing a huge string is slow.
        password_ok = (
            user is not None
            and len(password) <= cfg['PASSWORD_MAX_LENGTH']
            and user.check_password(password)
        )

        if user and not password_ok:
            user.failed_login_count = (user.failed_login_count or 0) + 1
            if user.failed_login_count >= cfg['LOGIN_MAX_ATTEMPTS']:
                user.locked_until = now + timedelta(
                    minutes=cfg['LOGIN_LOCK_MINUTES'])
                user.failed_login_count = 0
                db.session.commit()
                log_login(username, False, user_id=user.user_id,
                          detail=f"Locked for {cfg['LOGIN_LOCK_MINUTES']} "
                                 "minutes after "
                                 f"{cfg['LOGIN_MAX_ATTEMPTS']} wrong passwords")
                return render_template(
                    'Log_in.html',
                    error=_locked_message(user.locked_until, now))
            db.session.commit()

        # A deactivated account keeps every record it is attached to but
        # can no longer sign in. Checked after the password so a wrong
        # password on a deactivated account does not reveal that the
        # account exists.
        if password_ok and not user.is_active:
            log_login(username, False)
            return render_template(
                'Log_in.html',
                error="That account has been deactivated. "
                      "Contact a system administrator."
            )

        if password_ok:
            user.failed_login_count = 0
            user.locked_until = None
            db.session.commit()

            # Expires on the idle clock (PERMANENT_SESSION_LIFETIME);
            # last_seen drives the idle timeout in app/__init__.py.
            session.permanent = True
            session['last_seen'] = time.time()
            session['user_id'] = user.user_id
            session['username'] = user.username
            session['role'] = user.role
            session['cenro'] = user.cenro
            # read once at login; the before_request hook checks the
            # session rather than hitting the database on every request
            session['must_change_password'] = user.must_change_password
            log_login(user.username, True, user.role, user.user_id)             
            return redirect(_safe_next() or url_for('dashboard.index'))
        else:
            log_login(username, False)
            return render_template('Log_in.html', error="Incorrect Username or Password")

    if request.args.get('timeout') == '1':
        flash(f"You were signed out after "
              f"{current_app.config['SESSION_IDLE_MINUTES']} minutes without "
              "activity. Sign in again to continue.", "warning")
    return render_template("Log_in.html")


def _safe_next():
    """
    The page to return to after signing in, from ?next=. Only a path on
    this site is accepted, so the link cannot send someone elsewhere.
    """
    target = request.args.get('next') or ''
    if target.startswith('/') and not target.startswith('//') and '\\' not in target:
        return target
    return None


def _locked_message(locked_until, now):
    minutes = max(1, math.ceil((locked_until - now).total_seconds() / 60))
    return (f"Too many wrong passwords. Try again in {minutes} "
            f"minute{'s' if minutes != 1 else ''}, or ask an administrator "
            "to reset your password.")


# ----------------------------------------------------------------------
# forgot password
# ----------------------------------------------------------------------
#
# The reset link carries a signed token, not a database row: the user id
# and a fingerprint of the current password hash, signed with SECRET_KEY
# and timed. That makes the link
#   - impossible to forge without SECRET_KEY,
#   - expire after PASSWORD_RESET_MINUTES (itsdangerous checks the time),
#   - single-use: saving a new password changes the hash, so the
#     fingerprint no longer matches and the same link is refused.
#
# The form never says whether an email address has an account. It shows
# the same message either way, so it cannot be used to find out who uses
# the system.

RESET_SALT = 'password-reset'

# user_id -> time of the last reset email. In memory, so it resets with
# the server and is per worker; it only has to stop a flood, not count.
_last_reset_email = {}


def _reset_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'],
                                  salt=RESET_SALT)


def _password_fingerprint(user):
    return hashlib.sha256(user.password_hash.encode()).hexdigest()[:16]


def make_reset_token(user):
    return _reset_serializer().dumps(
        {'u': user.user_id, 'p': _password_fingerprint(user)})


def user_from_reset_token(token):
    """The User a reset token is for, or (None, reason) when it is not
    usable: expired, altered, already used, or the account is off."""
    max_age = current_app.config['PASSWORD_RESET_MINUTES'] * 60
    try:
        data = _reset_serializer().loads(token, max_age=max_age)
    except SignatureExpired:
        return None, "This reset link has expired."
    except BadSignature:
        return None, "This reset link is not valid."
    user = db.session.get(User, data.get('u')) if isinstance(data, dict) else None
    if user is None or not user.is_active:
        return None, "This reset link is not valid."
    if data.get('p') != _password_fingerprint(user):
        return None, "This reset link was already used."
    return user, None


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = (request.form.get('email_address') or '').strip().lower()
        user = User.query.filter_by(email_address=email).first() if email else None

        if user is not None and user.is_active:
            now = time.time()
            cooldown = current_app.config['PASSWORD_RESET_COOLDOWN_SECONDS']
            if now - _last_reset_email.get(user.user_id, 0) >= cooldown:
                _last_reset_email[user.user_id] = now
                try:
                    reset_url = external_url('auth.reset_password',
                                             token=make_reset_token(user))
                except RuntimeError:
                    current_app.logger.error(
                        "Password reset email not sent: APP_BASE_URL is not set.")
                    reset_url = None
                if reset_url:
                    send_template(
                        'password_reset', to=user.email_address,
                        subject="Reset your PuNoObservation password",
                        name=user.username, username=user.username,
                        reset_url=reset_url,
                        minutes=current_app.config['PASSWORD_RESET_MINUTES'],
                    )
                    log_action('password_reset_requested', 'users',
                               user.user_id, "Reset link emailed",
                               commit=True)

        # The same answer whether or not the address has an account.
        flash("If that email address belongs to an account, a link to reset "
              "the password is on its way. Check your inbox and spam folder.",
              "success")
        return redirect(url_for('auth.login'))

    return render_template('Forgotpassword.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user, problem = user_from_reset_token(token)
    if user is None:
        return render_template('Resetpassword.html', invalid=problem)

    if request.method == 'POST':
        password = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')
        error = password_problem(password)
        if not error and password != confirm:
            error = "The two passwords do not match."
        if error:
            return render_template('Resetpassword.html', token=token,
                                   username=user.username, error=error)

        user.set_password(password)
        user.must_change_password = False
        user.password_changed_at = manila_now()
        # a reset also lifts a lock from too many wrong passwords
        user.failed_login_count = 0
        user.locked_until = None
        log_action('password_reset', 'users', user.user_id,
                   "Password changed with an emailed reset link")
        db.session.commit()

        send_template(
            'password_changed', to=user.email_address,
            subject="Your PuNoObservation password was changed",
            name=user.username, username=user.username,
            login_url=email_link('auth.login'),
        )

        session.clear()
        flash("Your password was changed. Sign in with the new one.", "success")
        return redirect(url_for('auth.login'))

    return render_template('Resetpassword.html', token=token,
                           username=user.username)


@auth_bp.route('/session/status')
def session_status():
    """
    Seconds left before the idle sign-out. Does not count as activity
    (app/__init__.py skips it), so the page can ask without resetting
    the clock. 401 once signed out.
    """
    if not session.get('user_id'):
        return jsonify({"signed_in": False}), 401
    idle = current_app.config['SESSION_IDLE_MINUTES'] * 60
    left = idle - (time.time() - session.get('last_seen', time.time()))
    return jsonify({"signed_in": True, "remaining": max(0, int(left))})


@auth_bp.route('/session/keepalive', methods=['POST'])
def session_keepalive():
    """"Stay signed in". The request itself resets the idle clock."""
    if not session.get('user_id'):
        return jsonify({"signed_in": False}), 401
    return jsonify({
        "signed_in": True,
        "remaining": current_app.config['SESSION_IDLE_MINUTES'] * 60,
    })


@auth_bp.route('/logout')
def logout():
    log_action('logout', 'users', session.get('user_id'), commit=True)
    session.clear()
    return redirect(url_for('auth.login'))