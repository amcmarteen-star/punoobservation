import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-only-change-me')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- uploads ---------------------------------------------------------
    # Per file, checked by app/utils/security.py and in the browser.
    MAX_UPLOAD_MB = 10
    # Files on one request form (the Indicative Management Plan upload).
    MAX_REQUEST_FILES = 5
    # Whole form, all files together. A monitoring report carries many
    # photographs, so this is well above one file's limit. Flask refuses
    # anything bigger with 413 before the route runs.
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024

    # --- passwords -------------------------------------------------------
    PASSWORD_MIN_LENGTH = 8
    # Also the longest the password boxes accept. Hashing a very long
    # password is slow, so the login refuses longer ones unhashed.
    PASSWORD_MAX_LENGTH = 64
    # Wrong passwords in a row before the account's login is locked.
    LOGIN_MAX_ATTEMPTS = 5
    LOGIN_LOCK_MINUTES = 15

    # --- sessions --------------------------------------------------------
    # Signed out after this long with no activity. The page warns two
    # minutes before. app/__init__.py enforces it from session['last_seen'].
    SESSION_IDLE_MINUTES = 30
    # The cookie must outlive the idle limit. If it expired at the same
    # moment, the browser would throw it away first, and the server could
    # not tell a timed-out user from one who never signed in - so it could
    # not say "you were signed out for inactivity".
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)

    # --- email -----------------------------------------------------------
    # The live site sends through Brevo's SMTP relay; .env.example lists
    # where each value comes from. Plain SMTP, so another service is a
    # change to .env only. app/services/mailer.py does the sending. With
    # MAIL_SERVER empty nothing is sent: each email is written to the
    # server log instead, which is how development and the tests run.
    MAIL_SERVER = os.environ.get('MAIL_SERVER', '')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    # 'starttls' (usually port 587), 'ssl' (usually 465) or 'none'
    MAIL_SECURITY = os.environ.get('MAIL_SECURITY', 'starttls').lower()
    MAIL_FROM = os.environ.get(
        'MAIL_FROM', 'PuNoObservation <noreply@punoobservation.app>')
    # The site's public address, for links in emails, e.g.
    # https://punoobservation.app. Required once MAIL_SERVER is set: links
    # are never built from the request's Host header, which a visitor can
    # forge to point a password reset link at their own site.
    APP_BASE_URL = os.environ.get('APP_BASE_URL', '').rstrip('/')
    # How long a "forgot password" link works.
    PASSWORD_RESET_MINUTES = 60
    # The least time between two reset emails to one account, so the form
    # cannot be used to flood someone's inbox.
    PASSWORD_RESET_COOLDOWN_SECONDS = 120

    # --- map tiles -------------------------------------------------------
    # Where every map in the system gets its background pictures.
    #
    # The defaults are the public OpenStreetMap and Esri servers. They are
    # fine for development and demonstrations, but neither is meant for an
    # office using the system every day:
    #   - tile.openstreetmap.org asks heavy users to use another provider
    #     or host their own tiles (OSM Tile Usage Policy).
    #   - Esri expects production apps to use an ArcGIS account and key
    #     (ArcGIS Location Platform has a free monthly tile quota).
    # Before a CENRO or DENR office adopts the system, set these in .env
    # to a source it is licensed to use. See .env.example.
    #
    # {s} {z} {x} {y} are Leaflet placeholders. A key goes in the URL,
    # e.g. ...World_Imagery/MapServer/tile/{z}/{y}/{x}?token=YOUR_KEY
    MAP_STREET_TILES = os.environ.get(
        'MAP_STREET_TILES',
        'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png')
    MAP_STREET_ATTRIBUTION = os.environ.get(
        'MAP_STREET_ATTRIBUTION',
        '&copy; <a href="https://www.openstreetmap.org/copyright">'
        'OpenStreetMap</a> contributors')

    # Set MAP_SATELLITE_TILES to an empty value to turn satellite off.
    MAP_SATELLITE_TILES = os.environ.get(
        'MAP_SATELLITE_TILES',
        'https://server.arcgisonline.com/ArcGIS/rest/services/'
        'World_Imagery/MapServer/tile/{z}/{y}/{x}')
    MAP_SATELLITE_ATTRIBUTION = os.environ.get(
        'MAP_SATELLITE_ATTRIBUTION',
        'Imagery &copy; Esri, Maxar, Earthstar Geographics')
    # Deepest zoom the satellite source has real pictures for; past it
    # Leaflet stretches the last level instead of showing blank squares.
    MAP_SATELLITE_MAX_ZOOM = int(os.environ.get('MAP_SATELLITE_MAX_ZOOM', '18'))
