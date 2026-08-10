# app/routes/dashboard.py
from flask import Blueprint, render_template, session
from app.utils.decorators import login_required
from app.models import Site, ReforestationRecord, MonitoringReport
from app.extensions import db
from sqlalchemy import func

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def home():
    return render_template("Home.html")

@dashboard_bp.route('/dashboard')
@login_required
def index():
    total_sites = db.session.query(func.count(Site.site_id)).scalar() or 0
    total_trees = db.session.query(func.sum(ReforestationRecord.target_quantity)).scalar() or 0
    total_reports = db.session.query(func.count(MonitoringReport.report_id)).scalar() or 0

    return render_template(
        'Dashboard.html',
        total_sites=total_sites,
        total_trees=total_trees,
        total_reports=total_reports
    )

@dashboard_bp.route('/gis-map')
@login_required
def gis_map():
    """Renders the full interactive GIS Map page."""
    return render_template('GIS_map.html')