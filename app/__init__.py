import time

import click
from flask import (
    Flask, session, request, flash, redirect, url_for, jsonify,
)
from werkzeug.exceptions import RequestEntityTooLarge
from app.config import Config
from app.extensions import db
from flask_migrate import Migrate

migrate = Migrate()  # no app yet

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    migrate.init_app(app,db)

    # One way of writing dates and times on every page, in Philippine time:
    #   {{ value|datetime_ph }}  ->  17 Sep 2026, 10:19 PM
    #   {{ value|date_ph }}      ->  17 Sep 2026
    from app.utils.timeutil import format_datetime, format_date
    app.jinja_env.filters['datetime_ph'] = format_datetime
    app.jinja_env.filters['date_ph'] = format_date

    # A report's survival rate: {{ r.survival_rate|survival }} -> 87.5%,
    # or "Unknown" when the site has no planted figure.
    from app.services.monitoring import survival_text
    app.jinja_env.filters['survival'] = (
        lambda rate: survival_text(rate).capitalize()
        if rate is None else survival_text(rate))

    # The current user's area in words, for page subtitles:
    #   {{ area_label() }}  ->  Districts 5 and 6, Eastern Pangasinan
    from app.utils.jurisdiction import area_label
    app.jinja_env.globals['area_label'] = area_label

    # Map tile sources, from app/config.py. Base.html hands them to every
    # page's JavaScript as MAP_TILES, so no template hard-codes a server.
    # sampling_rule / sampling_plan: the DENR survey rule (whole-site count
    # under 20 ha, otherwise 10% in 100 m plots), so no template
    # hard-codes it either.
    from app.services.monitoring import (
        FULL_COUNT_BELOW_HA, TARGET_INTENSITY, SAMPLE_PLOT_SQM, sampling_plan,
        DENR_THRESHOLD,
    )

    @app.context_processor
    def _map_tiles():
        cfg = app.config
        satellite = None
        if cfg['MAP_SATELLITE_TILES']:
            satellite = {
                "url": cfg['MAP_SATELLITE_TILES'],
                "attribution": cfg['MAP_SATELLITE_ATTRIBUTION'],
                "maxNativeZoom": cfg['MAP_SATELLITE_MAX_ZOOM'],
            }
        return {"app_limits": {
            "maxFileMb": cfg['MAX_UPLOAD_MB'],
            "maxRequestFiles": cfg['MAX_REQUEST_FILES'],
            "passwordMin": cfg['PASSWORD_MIN_LENGTH'],
            "passwordMax": cfg['PASSWORD_MAX_LENGTH'],
            "sessionIdleMinutes": cfg['SESSION_IDLE_MINUTES'],
        }, "map_tiles": {
            "street": {
                "url": cfg['MAP_STREET_TILES'],
                "attribution": cfg['MAP_STREET_ATTRIBUTION'],
            },
            "satellite": satellite,
        }, "sampling_rule": {
            "fullCountBelowHa": FULL_COUNT_BELOW_HA,
            "targetPct": TARGET_INTENSITY,
            "plotSqm": SAMPLE_PLOT_SQM,
            "survivalThreshold": DENR_THRESHOLD,
        }, "sampling_plan": sampling_plan}

    # Help panel: the FAQ for the page being shown. Base.html shows the
    # "?" button only when the page has one. To add a page, write its
    # partial in templates/partials/faq/ and list its endpoint here.
    page_faqs = {
        # everyone
        'dashboard.index': 'partials/faq/_dashboard.html',
        'dashboard.gis_map': 'partials/faq/_gis_map.html',
        'dashboard.Reforestation_sites': 'partials/faq/_sites.html',
        'dashboard.recommendations': 'partials/faq/_recommendations.html',
        'dashboard.notifications_page': 'partials/faq/_notifications.html',
        'dashboard.my_account': 'partials/faq/_my_account.html',
        'dashboard.requests_page': 'partials/faq/_requests.html',
        # field officers
        'dashboard.reports_page': 'partials/faq/_reports.html',
        'dashboard.my_reports_page': 'partials/faq/_my_reports.html',
        # one report: the partial adapts to which of these three it is
        'dashboard.my_report_detail': 'partials/faq/_report_detail.html',
        'dashboard.public_report_detail': 'partials/faq/_report_detail.html',
        'admin.review_report_detail': 'partials/faq/_report_detail.html',
        # site visits, for sites made from a request (staff)
        'visits.index': 'partials/faq/_site_visits.html',
        'visits.site_visits': 'partials/faq/_site_visits.html',
        'visits.new_visit': 'partials/faq/_site_visits.html',
        'visits.visit_detail': 'partials/faq/_site_visits.html',
        # CENRO and provincial administrators
        'admin.review_requests': 'partials/faq/_review_requests.html',
        'admin.review_request_detail': 'partials/faq/_request_detail.html',
        'admin.create_site_from_request': 'partials/faq/_create_site.html',
        'admin.review_reports': 'partials/faq/_review_reports.html',
        'admin.provincial_overview': 'partials/faq/_provincial_overview.html',
        'admin.publications': 'partials/faq/_publications.html',
        # system administrators
        'admin.user_management': 'partials/faq/_user_management.html',
        'admin.reference_dataset': 'partials/faq/_reference_dataset.html',
        'admin.audit_log': 'partials/faq/_audit_log.html',
    }

    @app.context_processor
    def _page_faq():
        return {"page_faq": page_faqs.get(request.endpoint)}

    # First-time tour (partials/_tour.html): True when the Dashboard should
    # start it by itself. Only the Dashboard asks the database, and never
    # while a temporary password is still waiting to be changed.
    @app.context_processor
    def _tour_due():
        due = False
        if (request.endpoint == 'dashboard.index'
                and session.get('user_id')
                and not session.get('must_change_password')):
            from app.models import User
            user = db.session.get(User, session['user_id'])
            due = user is not None and user.tour_completed_at is None
        return {"tour_due": due}

    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.admin import admin_bp
    from app.routes.visits import visits_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(visits_bp)

    with app.app_context():
        from app import models

    # Idle timeout. Registered before the password-change hook so an
    # expired session is cleared first. /session/status only reads the
    # clock, so the page's warning timer does not keep a session alive.
    @app.before_request
    def _idle_timeout():
        if not session.get('user_id') or request.endpoint == 'static':
            return
        now = time.time()
        idle = app.config['SESSION_IDLE_MINUTES'] * 60
        last = session.get('last_seen')
        if last is not None and now - last > idle:
            from app.utils.audit import log_action
            log_action('session_timeout', 'users', session.get('user_id'),
                       f"Signed out after {app.config['SESSION_IDLE_MINUTES']} "
                       "minutes without activity", commit=True)
            session.clear()
            if request.path.startswith(('/api/', '/session/')):
                return jsonify({"signed_in": False}), 401
            back = request.full_path.rstrip('?') if request.method == 'GET' else None
            return redirect(url_for('auth.login', timeout=1, next=back))
        if request.endpoint != 'auth.session_status':
            session['last_seen'] = now

    # MAX_CONTENT_LENGTH: the form is refused before any route runs.
    # Send the user back with a message instead of a bare error page.
    @app.errorhandler(RequestEntityTooLarge)
    def _upload_too_large(_error):
        total_mb = app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
        flash(f"The upload was too large. Each file can be up to "
              f"{app.config['MAX_UPLOAD_MB']} MB, and one form up to "
              f"{total_mb} MB in total.", "danger")
        return redirect(request.referrer or url_for('dashboard.index'))

    @app.before_request
    def _enforce_password_change():
        # A temporary password that is never changed is a permanent one.
        # Everything is blocked except the account page itself, logout,
        # and static files - otherwise the user cannot reach the form
        # that clears the flag.
        if not session.get('must_change_password'):
            return
        allowed = {'dashboard.my_account', 'auth.logout', 'static',
                   'auth.session_status', 'auth.session_keepalive'}
        if request.endpoint in allowed:
            return
        flash("Set your own password before continuing.", "warning")
        return redirect(url_for('dashboard.my_account'))

    # CLI Command to create privileged users
    @app.cli.command("create-user")
    @click.argument("username")
    @click.argument("email")
    @click.argument("password")
    @click.option("--role", default="admin", help="Role: admin, field_officer, normal_user")
    def create_user(username, email, password, role):
        """Creates a user account directly from terminal."""
        from app.models import User
        
        user = User.query.filter((User.username == username) | (User.email_address == email)).first()
        if user:
            click.echo(f"Error: User with username '{username}' or email '{email}' already exists.")
            return

        from app.utils.security import password_problem
        problem = password_problem(password)
        if problem:
            click.echo(f"Error: {problem}")
            return

        new_user = User(
            username=username.strip().lower(),
            email_address=email.strip().lower(),
            role=role
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        click.echo(f"Successfully created {role}: {username}")

    return app