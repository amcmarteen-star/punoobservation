# app/models.py
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
# from geoalchemy2 import Geometry
from app.extensions import db
from datetime import datetime
from zoneinfo import ZoneInfo

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

    # Relationships
    reports = db.relationship('MonitoringReport', backref='officer', lazy=True)
    requests = db.relationship('Request', backref='user', lazy=True)
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
    
    # Relationship
    reforestation_records = db.relationship('ReforestationRecord', backref='species', lazy=True)


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
    record_id = db.Column(db.Integer, db.ForeignKey('reforestation_record.record_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    monitoring_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    survival_rate = db.Column(db.Float, nullable=False)
    record_version = db.Column(db.Integer, nullable=False, default=1)
    approval_status = db.Column(db.String(30), nullable=False, default='Pending')  # 'Pending', 'Approved', 'Rejected'

    # Relationships
    photos = db.relationship('MonitoringPhoto', backref='report', lazy=True, cascade="all, delete-orphan")
    notifications = db.relationship('Notification', backref='report', lazy=True)


class MonitoringPhoto(db.Model):
    __tablename__ = 'monitoring_photo'
    
    photo_id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('monitoring_report.report_id'), nullable=False)
    photo_url = db.Column(db.String(255), nullable=False)
    # gps_point = db.Column(Geometry('POINT', srid=4326), nullable=True)
    date_time_taken = db.Column(db.DateTime, nullable=True)
    upload_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    inside_boundary = db.Column(db.Boolean, nullable=False, default=False)


class Request(db.Model):
    __tablename__ = 'request'
    
    request_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    request_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), nullable=False, default='Submitted')


class Notification(db.Model):
    __tablename__ = 'notification'
    
    notification_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    report_id = db.Column(db.Integer, db.ForeignKey('monitoring_report.report_id'), nullable=True)
    notification_type = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(
        db.DateTime,
        nullable = False,
        default = lambda: datetime.now(ZoneInfo("Asia/Manila"))
    )