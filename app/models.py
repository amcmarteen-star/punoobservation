# app/models.py
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
# from geoalchemy2 import Geometry
from app.extensions import db
from datetime import datetime
from zoneinfo import ZoneInfo
# Timestamps are stored as naive Manila time; see app/utils/timeutil.py
# for why an aware datetime must never be saved into these columns.
from app.utils.timeutil import manila_now

class Location(db.Model):
    __tablename__ = 'location'
    
    location_id = db.Column(db.Integer, primary_key=True)
    psgc_code = db.Column(db.String(20), unique=True, nullable=True)  # Standard Philippine PSGC Code
    region = db.Column(db.String(100), nullable=False)
    province = db.Column(db.String(100), nullable=False)
    municipality = db.Column(db.String(100), nullable=False)
    barangay = db.Column(db.String(100), nullable=False)
        # --- Site characteristics (Objective 1) ---
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    elevation_m = db.Column(db.Float, nullable=True)
    avg_temp_c = db.Column(db.Float, nullable=True)
    annual_rainfall_mm = db.Column(db.Float, nullable=True)
    soil_type = db.Column(db.String(100), nullable=True)
    soil_texture = db.Column(db.String(50), nullable=True)
    agro_ecological_zone = db.Column(db.String(50), nullable=True)
    coastal_exposure = db.Column(db.Integer, nullable=True)

    # Relationship to Site
    sites = db.relationship('Site', backref='location', lazy=True)


class Organization(db.Model):
    __tablename__ = 'organization'
    
    organization_id = db.Column(db.Integer, primary_key=True)
    organization_name = db.Column(db.String(150), nullable=False)
    organization_type = db.Column(db.String(100), nullable=False)

    # Relationships
    users = db.relationship('User', backref='organization', lazy=True)
    sites = db.relationship('Site', backref='organization', lazy=True)


class User(db.Model):
    __tablename__ = 'users'
    
    user_id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.organization_id'), nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email_address = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='normal_user')  # 'normal_user', 'field_officer', 'admin'
    cenro = db.Column(db.String(100), nullable=True)

    # Accounts are deactivated, never deleted.
    #
    # Eight foreign keys point at users.user_id - the audit log, who
    # approved a report, who published a boundary, who submitted a
    # request. Deleting a row out from under those either destroys the
    # audit trail or orphans an official record. Deactivating keeps every
    # reference intact and simply stops the account logging in.
    is_active = db.Column(
        db.Boolean, nullable=False,
        default=True, server_default=db.true(),
    )

    # Set when an administrator creates the account or resets the
    # password. Cleared once the holder chooses their own.
    #
    # server_default is required: the table already has rows, and a NOT
    # NULL column added without one fails on an existing database.
    must_change_password = db.Column(
        db.Boolean, nullable=False, default=False,
        server_default=db.false()
    )
    password_changed_at = db.Column(db.DateTime, nullable=True)

    # Wrong passwords in a row. At LOGIN_MAX_ATTEMPTS the login is locked
    # until locked_until (Manila time) and the count starts again.
    failed_login_count = db.Column(
        db.Integer, nullable=False, default=0, server_default='0'
    )
    locked_until = db.Column(db.DateTime, nullable=True)

    # When the holder finished or skipped the first-time tour (Manila
    # time). None means the Dashboard starts it on their next visit.
    # Stored here, not in the browser, so it shows once per person
    # rather than once per device.
    tour_completed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    # reports = db.relationship('MonitoringReport', backref='officer', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Site(db.Model):
    __tablename__ = 'site'
    
    site_id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('location.location_id'), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.organization_id'), nullable=False)
    site_name = db.Column(db.String(150), nullable=False)
    area_size_ha = db.Column(db.Float, nullable=False)
    boundary_geojson = db.Column(db.Text, nullable=True)
    boundary_published = db.Column(db.Boolean, default=False,
                                   server_default=db.false(),
                                   nullable=False)
    boundary_published_by = db.Column(
        db.Integer, db.ForeignKey('users.user_id'), nullable=True
    )
    boundary_published_at = db.Column(db.DateTime, nullable=True)
    boundary_source_report_id = db.Column(db.Integer, nullable=True)
    # set instead when the published boundary came from a site visit
    boundary_source_visit_id = db.Column(db.Integer, nullable=True)
    boundary_area_ha = db.Column(db.Float, nullable=True)
    boundary_captured_at = db.Column(db.DateTime, nullable=True)
    # land_map_boundary = db.Column(Geometry('POLYGON', srid=4326), nullable=True)
    date_established = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    site_status = db.Column(db.String(50), nullable=False, default='Active')
    climate_zone = db.Column(db.String(100), nullable=True)
    soil_type = db.Column(db.String(100), nullable=True)
    site_code = db.Column(db.String(50), unique=True, nullable=True)
    zone_type = db.Column(db.String(50), nullable=True)
    loa_contract_code = db.Column(db.String(50), nullable=True)
    year_contracted = db.Column(db.Integer, nullable=True)
    area_contracted_ha = db.Column(db.Float, nullable=True)
    date_contract_executed = db.Column(db.Date, nullable=True)
    date_contract_expiry = db.Column(db.Date, nullable=True)
    project_cost_3yr = db.Column(db.Numeric(12, 2), nullable=True)
    retention_fee_amount_paid = db.Column(db.Numeric(12, 2), nullable=True)
    retention_fee_date_paid = db.Column(db.Date, nullable=True)
    amount_under_land_improvement = db.Column(db.Numeric(12, 2), nullable=True)
    amount_still_in_cip = db.Column(db.Numeric(12, 2), nullable=True)
    penro = db.Column(db.String(100), nullable=True)
    cenro = db.Column(db.String(100), nullable=True)
    congressional_district = db.Column(db.String(20), nullable=True)
    land_classification = db.Column(db.String(50), nullable=True)
    major_land_use = db.Column(db.String(200), nullable=True)
    contact_person = db.Column(db.String(120), nullable=True)
    component = db.Column(db.String(100), nullable=True)
    commodity = db.Column(db.String(200), nullable=True)

    # Relationship
    reforestation_records = db.relationship('ReforestationRecord', backref='site', lazy=True)

    # The request this site was created from, when it came through the
    # request process rather than the DENR import. Unique, so one request
    # can never produce two sites.
    #
    # The requester's drawn area is NOT copied into boundary_geojson. It
    # stays on the request and is shown as a temporary proposed area until
    # the province publishes a GPS boundary; see proposed_area_for_site().
    source_request_id = db.Column(
        db.Integer, db.ForeignKey('request.request_id'),
        nullable=True, unique=True,
    )
    source_request = db.relationship(
        'Request', foreign_keys=[source_request_id],
        backref=db.backref('created_site', uselist=False),
    )


class TreeSpecie(db.Model):
    __tablename__ = 'tree_specie'
    
    tree_id = db.Column(db.Integer, primary_key=True)
    specie_name = db.Column(db.String(100), nullable=False)
    scientific_name = db.Column(db.String(150), nullable=True)
    native_to = db.Column(db.String(100), nullable=True)
        # --- Ecological tolerance ranges (Objective 2) ---
    min_rainfall_mm = db.Column(db.Float, nullable=True)
    max_rainfall_mm = db.Column(db.Float, nullable=True)
    min_elevation_m = db.Column(db.Float, nullable=True)
    max_elevation_m = db.Column(db.Float, nullable=True)
    min_temp_c = db.Column(db.Float, nullable=True)
    max_temp_c = db.Column(db.Float, nullable=True)
    preferred_soil = db.Column(db.String(200), nullable=True)
    source = db.Column(db.String(300), nullable=True)
    is_reference = db.Column(db.Boolean, default=False, server_default=db.false(), nullable=False)
    salinity_requirement = db.Column(db.Integer, nullable=True)
    # Path under static/, e.g. "uploads/species/sp12_20260913101500.jpg".
    # NULL means no photo; the page shows a default image instead.
    photo_url = db.Column(db.String(300), nullable=True)

    # Saved Wikipedia summary for the species info panel. Fetched once,
    # then served from here. wiki_fetched_at set with wiki_extract NULL
    # means "Wikipedia was checked and had no article".
    wiki_title = db.Column(db.String(300), nullable=True)
    wiki_extract = db.Column(db.Text, nullable=True)
    wiki_url = db.Column(db.String(500), nullable=True)
    wiki_fetched_at = db.Column(db.DateTime, nullable=True)

    # Relationship
    reforestation_records = db.relationship('ReforestationRecord', backref='species', lazy=True)


class SpeciesCategory(db.Model):
    """
    One CENRO use category for one species (Timber, Agroforestry, ...).

    A row per pair, so a species can be in several. The allowed names
    are SPECIES_CATEGORIES in app/services/recommender.py; rows are
    loaded by scripts/tools/load_species_categories.py.
    """
    __tablename__ = 'species_category'

    id = db.Column(db.Integer, primary_key=True)
    species_id = db.Column(
        db.Integer,
        db.ForeignKey('tree_specie.tree_id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    category = db.Column(db.String(50), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('species_id', 'category',
                            name='uq_species_category'),
    )


class ReforestationRecord(db.Model):
    __tablename__ = 'reforestation_record'
    
    record_id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('site.site_id'), nullable=False)
    tree_id = db.Column(db.Integer, db.ForeignKey('tree_specie.tree_id'), nullable=False)
    date_planted = db.Column(db.Date, nullable=False)
    target_quantity = db.Column(db.Integer, nullable=False)
    actual_quantity_planted = db.Column(db.Integer, nullable=True)
    survival_rate = db.Column(db.Float, nullable=True)
    date_validated = db.Column(db.Date, nullable=True)

    # Relationship
    reports = db.relationship('MonitoringReport', backref='reforestation_record', lazy=True)


class MonitoringReport(db.Model):
    __tablename__ = 'monitoring_report'

    report_id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(
        db.Integer,
        db.ForeignKey('reforestation_record.record_id'),
        nullable=False
    )
    site_id = db.Column(
        db.Integer, db.ForeignKey('site.site_id'), nullable=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey('users.user_id'), nullable=False
    )

    monitoring_date = db.Column(db.Date, nullable=False,
                                default=datetime.utcnow)

    # --- computed from the sampling plots, never typed by the officer ---
    # None means unknown: the site has no "seedlings actually planted" on
    # record (sites made from a request start without one), so survivors
    # cannot be turned into a rate. Never stored as 0, which would read as
    # every seedling dead and pull down every average it joins.
    survival_rate = db.Column(db.Float, nullable=True)
    plots_recorded = db.Column(db.Integer, nullable=True)
    plot_size_sqm = db.Column(db.Float, nullable=True)
    total_counted = db.Column(db.Integer, nullable=True)
    mean_per_plot = db.Column(db.Float, nullable=True)
    stdev_per_plot = db.Column(db.Float, nullable=True)
    density_per_ha = db.Column(db.Float, nullable=True)
    estimated_survivors = db.Column(db.Integer, nullable=True)
    sampling_intensity = db.Column(db.Float, nullable=True)

    # --- boundary reconstructed from GPS corner photos ---
    captured_area_ha = db.Column(db.Float, nullable=True)
    area_difference_pct = db.Column(db.Float, nullable=True)
    boundary_geojson = db.Column(db.Text, nullable=True)

    remarks = db.Column(db.Text, nullable=True)

    record_version = db.Column(db.Integer, nullable=False, default=1)
    approval_status = db.Column(db.String(30), nullable=False,
                                default='Pending')
    review_note = db.Column(db.Text, nullable=True)
    reviewed_by = db.Column(
        db.Integer, db.ForeignKey('users.user_id'), nullable=True
    )
    date_reviewed = db.Column(db.DateTime, nullable=True)
    # Not Applicable | Pending Publication | Published | Declined
    #
    # Separate from approval_status on purpose. A CENRO admin decides
    # whether the field work is sound; the provincial administrator
    # decides whether it becomes the official boundary of record.
    publication_status = db.Column(db.String(30), nullable=False,
                                   default='Not Applicable',
                                   server_default='Not Applicable')
    published_by = db.Column(
        db.Integer, db.ForeignKey('users.user_id'), nullable=True
    )
    published_at = db.Column(db.DateTime, nullable=True)
    publication_note = db.Column(db.Text, nullable=True)

    submitted_at = db.Column(
        db.DateTime,
        nullable=False,
        default=manila_now
    )

    # relationships
    photos = db.relationship('MonitoringPhoto', backref='report',
                             lazy=True, cascade="all, delete-orphan")
    plots = db.relationship('MonitoringPlot', backref='report',
                            lazy=True, cascade="all, delete-orphan")
    notifications = db.relationship('Notification', backref='report',
                                    lazy=True)

    site = db.relationship('Site', backref='monitoring_reports')
    officer = db.relationship(
        'User',
        foreign_keys=[user_id],
        backref=db.backref('submitted_reports', foreign_keys=[user_id])
    )
    reviewer = db.relationship(
        'User',
        foreign_keys=[reviewed_by],
        backref=db.backref('reviewed_reports', foreign_keys=[reviewed_by])
    )
    publisher = db.relationship(
        'User',
        foreign_keys=[published_by],
        backref=db.backref('published_reports', foreign_keys=[published_by])
    )

    @property
    def field_date(self):
        """The day of the field work, under the name a site visit uses too."""
        return self.monitoring_date

class MonitoringPhoto(db.Model):
    __tablename__ = 'monitoring_photo'

    photo_id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(
        db.Integer,
        db.ForeignKey('monitoring_report.report_id'),
        nullable=False
    )
    plot_id = db.Column(
        db.Integer,
        db.ForeignKey('monitoring_plot.plot_id'),
        nullable=True
    )

    photo_url = db.Column(db.String(255), nullable=False)
    file_hash = db.Column(db.String(64), nullable=True)

    # 'plot'     - evidence for one sampling plot
    # 'boundary' - a site corner, used to build the polygon
    photo_type = db.Column(db.String(20), nullable=False, default='plot')

    # read from EXIF. Plain floats: no PostGIS needed for a single point.
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    date_time_taken = db.Column(db.DateTime, nullable=True)
    upload_time = db.Column(
        db.DateTime,
        nullable=False,
        default=manila_now
    )

    # validation results. Recorded, never used to block an upload.
    inside_boundary = db.Column(db.Boolean, nullable=False, default=False)
    distance_from_centroid_m = db.Column(db.Float, nullable=True)
    flags = db.Column(db.String(300), nullable=True)

class SiteVisit(db.Model):
    """
    A field officer's visit to a site made from a request, before or at
    planting (app/routes/visits.py).

    A monitoring report counts surviving seedlings, which a new site does
    not have yet. A visit checks the land instead: does it match the
    request, is ownership confirmed, can it be reached. It can also walk
    the corners for a GPS boundary, and record the seedlings actually
    planted, which later monitoring reports need for a survival rate.

    A site can have several visits (a pre-planting check, then a planting
    confirmation). Each one is reviewed by the site's CENRO. An approved
    boundary goes to the same provincial publication queue as a report's;
    a "Not suitable" finding comes with the CENRO's suggested new site.
    """
    __tablename__ = 'site_visit'

    visit_id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('site.site_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    visit_date = db.Column(db.Date, nullable=False)
    # VISIT_TYPES in app/routes/visits.py
    visit_type = db.Column(db.String(40), nullable=False)

    # the land check; None = not answered
    land_matches = db.Column(db.Boolean, nullable=True)
    ownership_confirmed = db.Column(db.Boolean, nullable=True)
    accessible = db.Column(db.Boolean, nullable=True)
    # 'Suitable' | 'Not suitable'
    finding = db.Column(db.String(20), nullable=False)

    # at a planting confirmation
    seedlings_planted = db.Column(db.Integer, nullable=True)
    date_planted = db.Column(db.Date, nullable=True)
    remarks = db.Column(db.Text, nullable=True)

    # boundary from GPS corner photos, as on a monitoring report
    boundary_geojson = db.Column(db.Text, nullable=True)
    captured_area_ha = db.Column(db.Float, nullable=True)
    area_difference_pct = db.Column(db.Float, nullable=True)

    # Pending | Approved | Rejected, set by the site's CENRO
    status = db.Column(db.String(30), nullable=False, default='Pending')
    review_note = db.Column(db.Text, nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    date_reviewed = db.Column(db.DateTime, nullable=True)

    # A "Not suitable" visit, once approved: where the CENRO suggests
    # planting instead. Passed on to the requester.
    suggested_location_id = db.Column(
        db.Integer, db.ForeignKey('location.location_id'), nullable=True)
    suggestion_note = db.Column(db.Text, nullable=True)

    # Not Applicable | Pending Publication | Published | Declined, the same
    # values and the same queue as MonitoringReport.publication_status
    publication_status = db.Column(db.String(30), nullable=False,
                                   default='Not Applicable',
                                   server_default='Not Applicable')
    published_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    published_at = db.Column(db.DateTime, nullable=True)
    publication_note = db.Column(db.Text, nullable=True)

    submitted_at = db.Column(db.DateTime, nullable=False, default=manila_now)

    site = db.relationship('Site', backref=db.backref(
        'site_visits', order_by='SiteVisit.visit_date.desc()'))
    photos = db.relationship('SiteVisitPhoto', backref='visit', lazy=True,
                             cascade="all, delete-orphan")
    suggested_location = db.relationship('Location')
    officer = db.relationship('User', foreign_keys=[user_id])
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])
    publisher = db.relationship('User', foreign_keys=[published_by])

    @property
    def field_date(self):
        """The day of the field work, under the name a report uses too."""
        return self.visit_date


class SiteVisitPhoto(db.Model):
    """A photo from a site visit. Same checks as MonitoringPhoto."""
    __tablename__ = 'site_visit_photo'

    photo_id = db.Column(db.Integer, primary_key=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('site_visit.visit_id'), nullable=False)
    photo_url = db.Column(db.String(255), nullable=False)
    file_hash = db.Column(db.String(64), nullable=True)
    # 'site'     - the land as found
    # 'boundary' - a site corner, used to build the polygon
    photo_type = db.Column(db.String(20), nullable=False, default='site')
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    date_time_taken = db.Column(db.DateTime, nullable=True)
    upload_time = db.Column(db.DateTime, nullable=False, default=manila_now)
    inside_boundary = db.Column(db.Boolean, nullable=False, default=False)
    distance_from_centroid_m = db.Column(db.Float, nullable=True)
    flags = db.Column(db.String(300), nullable=True)


class MonitoringPlot(db.Model):
    """
    One sampling plot within a monitoring report.

    DENR assesses survival by laying out fixed-size plots across a site,
    counting surviving seedlings in each, then extrapolating to the full
    area. Storing each plot separately means the survival rate can be
    recomputed from the raw counts, and that variation between plots is
    visible rather than averaged away.
    """
    __tablename__ = 'monitoring_plot'

    plot_id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(
        db.Integer,
        db.ForeignKey('monitoring_report.report_id'),
        nullable=False
    )

    plot_number = db.Column(db.Integer, nullable=False)
    seedlings_alive = db.Column(db.Integer, nullable=False)
    plot_notes = db.Column(db.String(300), nullable=True)

    # optional GPS for the plot itself, taken from its photo
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    photos = db.relationship(
        'MonitoringPhoto',
        backref='plot',
        lazy=True,
        foreign_keys='MonitoringPhoto.plot_id'
    )

class Request(db.Model):
    __tablename__ = 'request'

    request_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey('users.user_id'), nullable=False
    )
    location_id = db.Column(
        db.Integer, db.ForeignKey('location.location_id'), nullable=True
    )

    request_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    proposed_area_ha = db.Column(db.Float, nullable=True)
    contact_number = db.Column(db.String(30), nullable=True)
    # Required on the form since October 2026. Older requests have none,
    # so the columns stay nullable.
    contact_name = db.Column(db.String(120), nullable=True)
    contact_email = db.Column(db.String(120), nullable=True)

    # Submitted | Under Review | Approved | Rejected
    status = db.Column(db.String(30), nullable=False, default='Submitted')

    date_submitted = db.Column(
        db.DateTime,
        nullable=False,
        default=manila_now
    )
    date_reviewed = db.Column(db.DateTime, nullable=True)
    reviewed_by = db.Column(
        db.Integer, db.ForeignKey('users.user_id'), nullable=True
    )
    review_note = db.Column(db.Text, nullable=True)

    # --- where, marked on the form map ---
    # A pin near the centre of the site, and an optional area drawn by
    # clicking its corners. boundary_geojson is a GeoJSON Polygon string,
    # longitude first. boundary_area_ha is measured from that polygon.
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    boundary_geojson = db.Column(db.Text, nullable=True)
    boundary_area_ha = db.Column(db.Float, nullable=True)

    # --- about the land ---
    land_ownership = db.Column(db.String(60), nullable=True)
    land_cover = db.Column(db.String(60), nullable=True)

    # --- seedlings needed (planning estimate) ---
    planting_density_per_ha = db.Column(db.Integer, nullable=True)
    estimated_seedlings = db.Column(db.Integer, nullable=True)

    # --- adoption ---
    # The existing site an Adoption request asks to take on. Empty for
    # every other request type. Not to be confused with Site.source_request,
    # which links a NEW site back to the request that created it.
    adopted_site_id = db.Column(
        db.Integer, db.ForeignKey('site.site_id'), nullable=True
    )
    adopted_site = db.relationship(
        'Site', foreign_keys=[adopted_site_id],
        backref=db.backref('adoption_requests', lazy=True),
    )

    location = db.relationship('Location', backref='requests')

    requester = db.relationship(
        'User',
        foreign_keys=[user_id],
        backref=db.backref('submitted_requests', foreign_keys=[user_id])
    )

    reviewer = db.relationship(
        'User',
        foreign_keys=[reviewed_by],
        backref=db.backref('reviewed_requests', foreign_keys=[reviewed_by])
    )

    attachments = db.relationship(
        'RequestAttachment', backref='request', lazy=True,
        cascade="all, delete-orphan"
    )

class Notification(db.Model):
    __tablename__ = 'notification'
    
    notification_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    report_id = db.Column(db.Integer, db.ForeignKey('monitoring_report.report_id'), nullable=True)
    # set on 'Site Visit' notifications, so the row links to the visit
    visit_id = db.Column(db.Integer, db.ForeignKey('site_visit.visit_id'), nullable=True)
    notification_type = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(
        db.DateTime,
        nullable = False,
        default = manila_now
    )

class AuditLog(db.Model):
    """
    An immutable record of consequential actions.

    Rows are written, never updated or deleted. A log that can be edited
    is not evidence of anything.

    user_id is nullable so a failed login attempt - where no user is
    established - can still be recorded.
    """
    __tablename__ = 'audit_log'

    log_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey('users.user_id'), nullable=True
    )
    username = db.Column(db.String(80), nullable=True)
    role = db.Column(db.String(20), nullable=True)
    cenro = db.Column(db.String(100), nullable=True)

    # 'login' | 'login_failed' | 'logout' | 'create_user' | 'delete_user'
    # | 'import_dataset' | 'review_request' | 'review_report'
    # | 'publish_boundary' | 'submit_report' | 'submit_request'
    # | 'cancel_request'
    action = db.Column(db.String(50), nullable=False)

    # 'users' | 'site' | 'request' | 'monitoring_report' | 'dataset'
    entity_type = db.Column(db.String(50), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)

    detail = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=manila_now
    )

    actor = db.relationship('User', foreign_keys=[user_id])

class RequestAttachment(db.Model):
    """
    A document attached to a reforestation request.

    Usually a photographed or scanned letter - a barangay endorsement,
    a landowner's consent, an organisation's formal request.
    """
    __tablename__ = 'request_attachment'

    attachment_id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(
        db.Integer, db.ForeignKey('request.request_id'), nullable=False
    )

    file_url = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=True)
    file_hash = db.Column(db.String(64), nullable=True)
    mime_type = db.Column(db.String(60), nullable=True)
    caption = db.Column(db.String(200), nullable=True)

    uploaded_at = db.Column(
        db.DateTime,
        nullable=False,
        default=manila_now
    )