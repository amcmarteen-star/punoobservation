# app/routes/dashboard.py
from flask import Blueprint, render_template, session, jsonify, redirect, url_for
from app.utils.decorators import login_required
from app.models import Site, ReforestationRecord, MonitoringReport, Location, Notification
from app.extensions import db
from sqlalchemy import func

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def home():
    # landing page removed -- guests land straight on the GIS map
    return redirect(url_for('dashboard.gis_map'))

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
def gis_map():
    """Renders the full interactive GIS Map page. Open to guests."""
    return render_template('GIS_map.html')


@dashboard_bp.route('/api/municipality/<name>')
def municipality_info(name):
    """
    Called by GIS_map.html when a municipality shape is clicked.
    'name' comes from geojson property NAME_2 (e.g. 'Binalonan').
    Matches against Location.municipality (case-insensitive, exact match).
    """
    location = Location.query.filter(
        func.lower(Location.municipality) == name.lower()
    ).first()

    if not location:
        # No DB record yet for this town -- still return something usable
        return jsonify({
            "found": False,
            "municipality": name
        })

    site_count = len(location.sites)

    tree_total = db.session.query(
        func.sum(ReforestationRecord.target_quantity)
    ).join(
        Site, ReforestationRecord.record_id == Site.site_id
    ).filter(
        Site.location_id == location.location_id
    ).scalar() or 0

    return jsonify({
        "found": True,
        "municipality": location.municipality,
        "province": location.province,
        "region": location.region,
        "site_count": site_count,
        "tree_total": tree_total
    })

@dashboard_bp.route('/notifications')
@login_required
def notifications_page():
    """Full notifications list page, linked from sidebar."""
    user_id = session.get('user_id')
    notifications = (
        Notification.query
        .filter_by(user_id=user_id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return render_template('Notifications.html', notifications=notifications)


@dashboard_bp.route('/api/notifications')
@login_required
def api_notifications():
    """Used by the topbar bell dropdown. Returns latest 8 + unread count."""
    user_id = session.get('user_id')

    recent = (
        Notification.query
        .filter_by(user_id=user_id)
        .order_by(Notification.created_at.desc())
        .limit(8)
        .all()
    )
    unread_count = Notification.query.filter_by(user_id=user_id, is_read=False).count()

    return jsonify({
        "unread_count": unread_count,
        "notifications": [
            {
                "id": n.notification_id,
                "type": n.notification_type,
                "message": n.message,
                "is_read": n.is_read,
                "report_id": n.report_id,
                "created_at": n.created_at.strftime('%b %d, %I:%M %p')
            }
            for n in recent
        ]
    })


@dashboard_bp.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark a single notification as read (called on click, from dropdown or full page)."""
    user_id = session.get('user_id')
    notif = Notification.query.filter_by(
        notification_id=notification_id, user_id=user_id
    ).first()

    if not notif:
        return jsonify({"error": "not found"}), 404

    notif.is_read = True
    db.session.commit()
    return jsonify({"success": True})