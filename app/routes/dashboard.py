# app/routes/dashboard.py
from flask import Blueprint, render_template, session, jsonify, redirect, url_for, request
from app.utils.decorators import login_required
from app.models import Site, ReforestationRecord, MonitoringReport, Location, Notification
from app.extensions import db
from sqlalchemy import func
from collections import defaultdict
from app.services.recommender import recommend_for_location


dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def home():
    if session.get('user_id'):
        return redirect(url_for('dashboard.index'))
    return render_template('Landing.html')

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
    locations = Location.query.filter(
        func.lower(Location.municipality) == name.lower()
    ).all()

    if not locations:
        return jsonify({"found": False, "municipality": name})

    sites_data = []
    for location in locations:
        for site in location.sites:
            totals = db.session.query(
                func.sum(ReforestationRecord.target_quantity),
                func.sum(ReforestationRecord.actual_quantity_planted)
            ).filter(ReforestationRecord.site_id == site.site_id).first()

            sites_data.append({
                "site_id": site.site_id,
                "site_name": site.site_name,
                "barangay": location.barangay,
                "municipality": location.municipality,
                "site_code": site.site_code,
                "area_size_ha": site.area_size_ha,
                "year_contracted": site.year_contracted,
                "date_established": site.date_established.strftime('%Y-%m-%d') if site.date_established else None,
                "target_trees": totals[0] or 0,
                "actual_trees": totals[1] or 0,
            })

    first = locations[0]
    return jsonify({
        "found": True,
        "municipality": first.municipality,
        "province": first.province,
        "region": first.region,
        "site_count": len(sites_data),
        "tree_total": sum(s["target_trees"] for s in sites_data),
        "sites": sites_data
    })

#Reforestation Sites
@dashboard_bp.route('/sites')
@login_required
def Reforestation_sites():
    sites = (
        Site.query
        .join(Location)
        .order_by(Location.municipality, Location.barangay, Site.site_name)
        .all()
    )

    grouped = defaultdict(lambda: defaultdict(list))
    for s in sites:
        grouped[s.location.municipality][s.location.barangay].append(s)

    # seedling totals per site
    totals = db.session.query(
        ReforestationRecord.site_id,
        func.sum(ReforestationRecord.target_quantity).label('target_total'),
        func.sum(ReforestationRecord.actual_quantity_planted).label('actual_total')
    ).group_by(ReforestationRecord.site_id).all()

    site_totals = {t.site_id: t for t in totals}

    return render_template('Sites.html', grouped=grouped, site_totals=site_totals)

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


@dashboard_bp.route('/recommendations')
def recommendations():
    """
    Species recommendation page.
 
    Shows a municipality/barangay picker. When a barangay is chosen,
    runs the engine and shows the ranked species.
 
    Open to guests, same as the GIS map, so the panel can see it
    without logging in.
    """
    municipalities = [
        m[0] for m in db.session.query(Location.municipality)
        .filter(Location.elevation_m.isnot(None))
        .distinct()
        .order_by(Location.municipality)
        .all()
    ]
 
    selected_muni = request.args.get('municipality', '')
    selected_brgy = request.args.get('barangay', '')
 
    barangays = []
    if selected_muni:
        barangays = (
            Location.query
            .filter(Location.municipality == selected_muni)
            .filter(Location.elevation_m.isnot(None))
            .order_by(Location.barangay)
            .all()
        )
 
    result = None
    if selected_muni and selected_brgy:
        location = (
            Location.query
            .filter(Location.municipality == selected_muni)
            .filter(Location.barangay == selected_brgy)
            .first()
        )
        if location:
            result = recommend_for_location(location, top_k=5)
 
    return render_template(
        'Recommendations.html',
        active_page='recommendations',
        municipalities=municipalities,
        barangays=barangays,
        selected_muni=selected_muni,
        selected_brgy=selected_brgy,
        result=result,
    )
 
 
@dashboard_bp.route('/api/recommend/<int:location_id>')
def api_recommend(location_id):
    """
    JSON recommendations for one barangay.
 
    Used by the GIS map info panel. Open to guests.
    """
    location = Location.query.get(location_id)
    if location is None:
        return jsonify({"found": False, "reason": "Barangay not found."}), 404
 
    return jsonify(recommend_for_location(location, top_k=5))
 
 
@dashboard_bp.route('/api/recommend')
def api_recommend_by_name():
    """
    JSON recommendations looked up by municipality and barangay name.
 
    Used by the GIS map, which knows names but not location ids.
    Matching is case-insensitive and ignores spaces, because
    barangay.geojson writes 'SanManuel' while the database may hold
    'San Manuel'.
    """
    muni = request.args.get('municipality', '')
    brgy = request.args.get('barangay', '')
 
    if not muni or not brgy:
        return jsonify({
            "found": False,
            "reason": "Provide both municipality and barangay."
        }), 400
 
    def squash(col):
        """Strip spaces, dots and dashes, then lowercase - in SQL."""
        expr = func.lower(col)
        for ch in (' ', '.', '-'):
            expr = func.replace(expr, ch, '')
        return expr
 
    def squash_py(s):
        return s.lower().replace(' ', '').replace('.', '').replace('-', '')
 
    location = (
        Location.query
        .filter(squash(Location.municipality) == squash_py(muni))
        .filter(squash(Location.barangay) == squash_py(brgy))
        .first()
    )
 
    if location is None:
        return jsonify({
            "found": False,
            "reason": f"No data for {brgy}, {muni}."
        }), 404
 
    return jsonify(recommend_for_location(location, top_k=5))
 