# app/routes/dashboard.py
from flask import Blueprint, render_template, session, jsonify, redirect, url_for, request, flash
from app.utils.decorators import login_required
from app.models import Site, ReforestationRecord, MonitoringReport, Location, Notification, Request, User
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
    user_id = session.get('user_id')
    tab = request.args.get('tab', 'all')

    # Two notification types belong to requests:
    #   'New Request'    -> sent to admins when a user submits
    #   'Request Update' -> sent to the user when an admin decides
    REQUEST_TYPES = ['Request Update', 'New Request']

    query = Notification.query.filter_by(user_id=user_id)

    if tab == 'requests':
        query = query.filter(Notification.notification_type.in_(REQUEST_TYPES))
    elif tab == 'reports':
        query = query.filter(Notification.notification_type == 'Report')

    notifications = query.order_by(Notification.created_at.desc()).all()

    base = Notification.query.filter_by(user_id=user_id)
    counts = {
        'all': base.count(),
        'reports': base.filter(
            Notification.notification_type == 'Report').count(),
        'requests': base.filter(
            Notification.notification_type.in_(REQUEST_TYPES)).count(),
    }

    unread = base.filter_by(is_read=False).count()

    return render_template(
        'Notifications.html',
        active_page='notifications',
        notifications=notifications,
        counts=counts,
        unread=unread,
        tab=tab,
    )

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
    unread_count = Notification.query.filter_by(
        user_id=user_id, is_read=False
    ).count()

    return jsonify({
        "unread_count": unread_count,
        "notifications": [
            {
                "id": n.notification_id,
                "type": n.notification_type,
                "message": n.message,
                "is_read": n.is_read,
                "report_id": n.report_id,
                "created_at": (
                    n.created_at.strftime('%b %d, %I:%M %p')
                    if n.created_at else ""
                ),
            }
            for n in recent
        ]
    })


@dashboard_bp.route('/api/notifications/<int:notification_id>/read',
                    methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark one notification read. Called from the dropdown or full page."""
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

"""
ADD THIS ROUTE TO: app/routes/dashboard.py

Paste at the BOTTOM, after api_recommend_by_name().

Serves reforestation sites for the map, GROUPED BY BARANGAY.

WHY GROUPED
-----------
Site has no coordinates of its own. Sites are located through their
Location, which carries the barangay centroid. Several sites in one
barangay therefore share an identical coordinate.

Plotting them individually stacks every marker on the same pixel, so a
barangay with five sites looks like one. Grouping gives one marker per
barangay carrying its site count, which is both accurate and readable.
"""

# ======================================================================
# PASTE FROM HERE
# ======================================================================


@dashboard_bp.route('/api/sites-geo')
def api_sites_geo():
    """
    Reforestation sites for the map, one entry per barangay.

    Open to guests, same as the rest of the map.
    """
    rows = (
        db.session.query(Location, Site)
        .join(Site, Site.location_id == Location.location_id)
        .filter(Location.latitude.isnot(None))
        .all()
    )

    # sum planting figures per site in one query rather than per row
    totals = dict(
        db.session.query(
            ReforestationRecord.site_id,
            func.sum(ReforestationRecord.target_quantity),
        )
        .group_by(ReforestationRecord.site_id)
        .all()
    )

    actuals = dict(
        db.session.query(
            ReforestationRecord.site_id,
            func.sum(ReforestationRecord.actual_quantity_planted),
        )
        .group_by(ReforestationRecord.site_id)
        .all()
    )

    grouped = {}

    for loc, site in rows:
        key = loc.location_id

        if key not in grouped:
            grouped[key] = {
                "location_id": loc.location_id,
                "municipality": loc.municipality,
                "barangay": loc.barangay,
                "lat": loc.latitude,
                "lon": loc.longitude,
                "site_count": 0,
                "total_area_ha": 0.0,
                "total_target": 0,
                "total_actual": 0,
                "sites": [],
            }

        g = grouped[key]
        target = int(totals.get(site.site_id) or 0)
        actual = int(actuals.get(site.site_id) or 0)

        g["site_count"] += 1
        g["total_area_ha"] += float(site.area_size_ha or 0)
        g["total_target"] += target
        g["total_actual"] += actual

        g["sites"].append({
            "site_id": site.site_id,
            "site_name": site.site_name,
            "site_code": site.site_code,
            "area_size_ha": site.area_size_ha,
            "year_contracted": site.year_contracted,
            "zone_type": site.zone_type,
            "target_trees": target,
            "actual_trees": actual,
        })

    out = list(grouped.values())
    for g in out:
        g["total_area_ha"] = round(g["total_area_ha"], 2)

    return jsonify({
        "count": len(out),
        "total_sites": sum(g["site_count"] for g in out),
        "barangays": out,
    })


# ======================================================================
# PASTE TO HERE
# ======================================================================
#
# IMPORTS NEEDED at the top of dashboard.py:
#
#     from app.models import Location, Site, ReforestationRecord
#     from sqlalchemy import func
#
# Site and ReforestationRecord are probably already imported for
# municipality_info(). Check before adding duplicates.

"""
HEATMAP ROUTE

PASTE AT THE BOTTOM OF: app/routes/dashboard.py

Returns a value per barangay for one metric, plus the colour breaks the
legend needs.

WHY BREAKS ARE COMPUTED SERVER-SIDE
-----------------------------------
The legend must show the same thresholds the map uses. Computing them in
two places invites drift. The API returns both the values and the breaks,
so the JavaScript never decides anything numeric.

Quantile breaks are used rather than equal intervals. Reforestation data
is heavily skewed - a handful of barangays hold most of the seedlings -
so equal intervals would put nearly everything in the lowest band and
the map would look empty.
"""

# ======================================================================
# PASTE FROM HERE
# ======================================================================


@dashboard_bp.route('/api/heatmap')
def api_heatmap():
    """
    Per-barangay values for the map shading.

    ?metric=sites      number of reforestation sites
    ?metric=seedlings  total seedlings actually planted
    ?metric=target     total target seedlings
    ?metric=area       total hectares under contract
    """
    metric = request.args.get('metric', 'sites')

    valid = {'sites', 'seedlings', 'target', 'area'}
    if metric not in valid:
        return jsonify({
            "error": f"Unknown metric. Use one of: {', '.join(sorted(valid))}"
        }), 400

    rows = (
        db.session.query(Location, Site)
        .join(Site, Site.location_id == Location.location_id)
        .all()
    )

    planted = dict(
        db.session.query(
            ReforestationRecord.site_id,
            func.sum(ReforestationRecord.actual_quantity_planted),
        )
        .group_by(ReforestationRecord.site_id)
        .all()
    )

    targets = dict(
        db.session.query(
            ReforestationRecord.site_id,
            func.sum(ReforestationRecord.target_quantity),
        )
        .group_by(ReforestationRecord.site_id)
        .all()
    )

    # accumulate per barangay
    values = {}
    for loc, site in rows:
        key = (loc.municipality, loc.barangay)

        if key not in values:
            values[key] = {
                "municipality": loc.municipality,
                "barangay": loc.barangay,
                "sites": 0,
                "seedlings": 0,
                "target": 0,
                "area": 0.0,
            }

        v = values[key]
        v["sites"] += 1
        v["seedlings"] += int(planted.get(site.site_id) or 0)
        v["target"] += int(targets.get(site.site_id) or 0)
        v["area"] += float(site.area_size_ha or 0)

    out = []
    for v in values.values():
        out.append({
            "municipality": v["municipality"],
            "barangay": v["barangay"],
            "value": round(v[metric], 2),
            "sites": v["sites"],
            "seedlings": v["seedlings"],
            "target": v["target"],
            "area": round(v["area"], 2),
        })

    breaks = _quantile_breaks([o["value"] for o in out if o["value"] > 0])

    labels = {
        "sites": "Reforestation sites",
        "seedlings": "Seedlings planted",
        "target": "Target seedlings",
        "area": "Area under contract (ha)",
    }

    units = {
        "sites": "sites",
        "seedlings": "seedlings",
        "target": "seedlings",
        "area": "ha",
    }

    return jsonify({
        "metric": metric,
        "label": labels[metric],
        "unit": units[metric],
        "breaks": breaks,
        "with_data": len(out),
        "barangays": out,
    })


def _quantile_breaks(values, bands=5):
    """
    Four thresholds splitting the data into five bands of roughly equal
    membership.

    Quantiles rather than equal intervals: one barangay with 80,000
    seedlings would otherwise dominate the scale and flatten everything
    else into the bottom band.

    Duplicate thresholds are removed. With few distinct values you get
    fewer bands, which is honest - inventing thresholds the data cannot
    support would mislead the legend.
    """
    if not values:
        return []

    s = sorted(values)
    n = len(s)

    cuts = []
    for i in range(1, bands):
        idx = int(round(i * n / bands)) - 1
        idx = max(0, min(n - 1, idx))
        cuts.append(s[idx])

    seen = []
    for c in cuts:
        if c not in seen:
            seen.append(c)

    return seen


# ======================================================================
# PASTE TO HERE
#
# Imports needed at the top of dashboard.py (probably already present):
#     from app.models import Location, Site, ReforestationRecord
#     from sqlalchemy import func
# ======================================================================
 
""" 
REQUEST REFORESTATION SITE - routes

TWO BLOCKS. They go in different files.
Read the headers carefully.
"""

# ======================================================================
# BLOCK 1
# PASTE AT THE BOTTOM OF: app/routes/dashboard.py
#
# Imports needed at the top of dashboard.py:
#     from app.models import Request
#     from datetime import datetime
#     from zoneinfo import ZoneInfo
# ======================================================================


@dashboard_bp.route('/requests', methods=['GET', 'POST'])
@login_required
def requests_page():
    """
    Where a user submits a reforestation site request and sees their own.

    Any logged-in user may submit. Admins and field officers review them
    on a separate page.
    """
    user_id = session.get('user_id')

    if request.method == 'POST':
        municipality = (request.form.get('municipality') or '').strip()
        barangay = (request.form.get('barangay') or '').strip()
        request_type = (request.form.get('request_type') or '').strip()
        description = (request.form.get('description') or '').strip()
        area_raw = (request.form.get('proposed_area_ha') or '').strip()
        contact = (request.form.get('contact_number') or '').strip()

        # --- validate before touching the database ---
        if not municipality or not barangay:
            flash("Choose a municipality and barangay.", "danger")
            return redirect(url_for('dashboard.requests_page'))

        if not request_type:
            flash("Choose a request type.", "danger")
            return redirect(url_for('dashboard.requests_page'))

        area = None
        if area_raw:
            try:
                area = float(area_raw)
            except ValueError:
                flash("Proposed area must be a number.", "danger")
                return redirect(url_for('dashboard.requests_page'))

            if area <= 0:
                flash("Proposed area must be greater than zero.", "danger")
                return redirect(url_for('dashboard.requests_page'))

        location = (
            Location.query
            .filter(Location.municipality == municipality)
            .filter(Location.barangay == barangay)
            .first()
        )

        if location is None:
            flash("That barangay was not found.", "danger")
            return redirect(url_for('dashboard.requests_page'))

        new_request = Request(
            user_id=user_id,
            location_id=location.location_id,
            request_type=request_type,
            description=description or None,
            proposed_area_ha=area,
            contact_number=contact or None,
            status='Submitted',
        )
        db.session.add(new_request)
        db.session.flush()          # assigns request_id before commit

        # tell every admin a request came in
        admins = User.query.filter_by(role='admin').all()
        for admin in admins:
            db.session.add(Notification(
                user_id=admin.user_id,
                notification_type='New Request',
                message=(
                    f"{session.get('username')} requested "
                    f"{request_type} for {barangay}, {municipality}."
                ),
                is_read=False,
            ))

        db.session.commit()

        flash(
            f"Request submitted for {barangay}, {municipality}. "
            "You will be notified when it is reviewed.",
            "success",
        )
        return redirect(url_for('dashboard.requests_page'))

    # --- GET ---
    municipalities = [
        m[0] for m in db.session.query(Location.municipality)
        .filter(Location.elevation_m.isnot(None))
        .distinct()
        .order_by(Location.municipality)
        .all()
    ]

    my_requests = (
        Request.query
        .filter_by(user_id=user_id)
        .order_by(Request.date_submitted.desc())
        .all()
    )

    return render_template(
        'Requests.html',
        active_page='requests',
        municipalities=municipalities,
        my_requests=my_requests,
    )


@dashboard_bp.route('/api/barangays/<municipality>')
def api_barangays(municipality):
    """
    Barangay names for one municipality.

    Feeds the dependent dropdown on the request form, so choosing a
    municipality does not require a page reload.
    """
    rows = (
        Location.query
        .filter(Location.municipality == municipality)
        .filter(Location.elevation_m.isnot(None))
        .order_by(Location.barangay)
        .all()
    )
    return jsonify([r.barangay for r in rows])

