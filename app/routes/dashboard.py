# app/routes/dashboard.py
from flask import Blueprint, render_template, session, jsonify, redirect, url_for, request, flash, current_app
from app.extensions import db
from app.utils.decorators import login_required
from app.models import (
    Site, ReforestationRecord, MonitoringReport, MonitoringPlot,
    MonitoringPhoto, Location, Notification, Request, RequestAttachment,
    User,
)
from app.utils.audit import log_action, log_login
from sqlalchemy import func
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
from app.services.recommender import recommend_for_location
import json, os, re
from app.services.monitoring import (
    extract_photo_metadata, check_timestamp, compute_survival,
    build_boundary, point_in_geojson, haversine_m, save_photo, save_request_file,
)
from app.utils.jurisdiction import (
    scope_sites, scope_locations, allowed_municipalities,
    can_see_municipality, current_cenro, is_superadmin, scope_label,
    CENRO_LIST, CENRO_MUNICIPALITIES,
)
from app.utils.decorators import login_required,field_officer_required

MANILA = ZoneInfo("Asia/Manila")


def _time_ago(dt):
    """'3 hours ago' style label.

    The DB column has no timezone, so SQLAlchemy hands back a naive
    datetime holding Manila wall-clock time (that's what the model's
    default writes). Compare against Manila "now" with its own tzinfo
    stripped so both sides are naive.
    """
    if not dt:
        return ""
    now = datetime.now(MANILA).replace(tzinfo=None)
    if dt.tzinfo is not None:
        dt = dt.astimezone(MANILA).replace(tzinfo=None)
    delta = now - dt
    seconds = delta.total_seconds()
    if seconds < 60:
        return "just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = int(seconds // 3600)
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(seconds // 86400)
    if days < 7:
        return f"{days} day{'s' if days != 1 else ''} ago"
    return dt.strftime('%b %d, %Y')


def _day_label(dt):
    """Section header for a notification's date: Today / Yesterday / date."""
    if not dt:
        return "Earlier"
    today = datetime.now(MANILA).date()
    if dt.tzinfo is not None:
        dt = dt.astimezone(MANILA)
    d = dt.date()
    if d == today:
        return "Today"
    if (today - d).days == 1:
        return "Yesterday"
    return dt.strftime('%B %d, %Y')


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
    if not can_see_municipality(name):
        return jsonify({
            "found": False,
            "municipality": name,
            "reason": "Outside your CENRO jurisdiction.",
        })   
    
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
                "lat": location.latitude,
                "lon": location.longitude,
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
    q = (
        Site.query
        .join(Location)
        .order_by(Location.municipality, Location.barangay, Site.site_name)
    )
    q = scope_sites(q)
    sites = q.all()

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

    return render_template('Sites.html', grouped=grouped, site_totals=site_totals, scope = scope_label(),)

@dashboard_bp.route('/notifications')
@login_required
def notifications_page():
    user_id = session.get('user_id')
    tab = request.args.get('tab', 'unread')

    REQUEST_TYPES = ['Request Update', 'New Request']

    query = Notification.query.filter_by(user_id=user_id)

    if tab == 'unread':
        query = query.filter(Notification.is_read.is_(False))
    elif tab == 'read':
        query = query.filter(Notification.is_read.is_(True))
    elif tab == 'requests':
        query = query.filter(Notification.notification_type.in_(REQUEST_TYPES))
    elif tab == 'reports':
        query = query.filter(Notification.notification_type == 'Report')

    notifications = query.order_by(Notification.created_at.desc()).all()

    # --- group by day, and add a relative time string ---
    now = datetime.now(ZoneInfo("Asia/Manila"))
    today = now.date()

    def time_ago(dt):
        if not dt:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("Asia/Manila"))
        secs = (now - dt).total_seconds()
        if secs < 60:
            return "just now"
        if secs < 3600:
            return f"{int(secs // 60)} min ago"
        if secs < 86400:
            return f"{int(secs // 3600)} hr ago"
        return dt.strftime('%d %b, %I:%M %p')

    groups = []
    current = None

    for n in notifications:
        n.time_ago = time_ago(n.created_at)          # attached for the template

        d = n.created_at.date() if n.created_at else today
        if d == today:
            label = "Today"
        elif (today - d).days == 1:
            label = "Yesterday"
        else:
            label = d.strftime('%d %B %Y')

        if current is None or current["label"] != label:
            current = {"label": label, "notifications": []}
            groups.append(current)
        current["notifications"].append(n)

    base = Notification.query.filter_by(user_id=user_id)
    counts = {
        'unread': base.filter(Notification.is_read.is_(False)).count(),
        'all': base.count(),
        'reports': base.filter(
            Notification.notification_type == 'Report').count(),
        'requests': base.filter(
            Notification.notification_type.in_(REQUEST_TYPES)).count(),
    }

    return render_template(
        'Notifications.html',
        active_page='notifications',
        grouped=groups,
        counts=counts,
        unread=counts['unread'],
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


@dashboard_bp.route('/api/notifications/<int:notification_id>/unread',
                    methods=['POST'])
@login_required
def mark_notification_unread(notification_id):
    """Mark one notification unread. Mirrors mark_notification_read."""
    user_id = session.get('user_id')
    notif = Notification.query.filter_by(
        notification_id=notification_id, user_id=user_id
    ).first()

    if not notif:
        return jsonify({"error": "not found"}), 404

    notif.is_read = False
    db.session.commit()
    return jsonify({"success": True})


@dashboard_bp.route('/api/notifications/<int:notification_id>/delete',
                    methods=['POST'])
@login_required
def delete_notification(notification_id):
    """Delete one notification. Only its owner may delete it."""
    user_id = session.get('user_id')
    notif = Notification.query.filter_by(
        notification_id=notification_id, user_id=user_id
    ).first()

    if not notif:
        return jsonify({"error": "not found"}), 404

    db.session.delete(notif)
    db.session.commit()
    return jsonify({"success": True})


@dashboard_bp.route('/api/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark every unread notification for this user as read. Called from
    the 'Mark all as read' action in the dropdown and the full page."""
    user_id = session.get('user_id')
    Notification.query.filter_by(user_id=user_id, is_read=False).update(
        {"is_read": True}
    )
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
    q = (
        db.session.query(Location.municipality)
        .filter(Location.elevation_m.isnot(None))
    )
    q = scope_locations(q)
    municipalities = [
        m[0] for m in q.distinct().order_by(Location.municipality).all()
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
    if not can_see_municipality(muni):
        return jsonify({
            "found": False,
            "reason": "Outside your CENRO jurisdiction.",
        }), 403
 
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
    q = (
        db.session.query(Location, Site)
        .join(Site, Site.location_id == Location.location_id)
        .filter(Location.latitude.isnot(None))
    )
    rows = scope_sites(q).all()

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

    q = (
        db.session.query(Location, Site)
        .join(Site, Site.location_id == Location.location_id)
    )
    rows = scope_sites(q).all()

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


""" 
REQUEST REFORESTATION SITE - routes

TWO BLOCKS. They go in different files.
Read the headers carefully.
"""


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
                # --- attachments ---
        saved = 0
        rejected = []

        for i, f in enumerate(request.files.getlist('attachments'), start=1):
            if not f or not f.filename:
                continue

            result = save_request_file(
                f, current_app.static_folder, new_request.request_id, i
            )

            if result is None:
                rejected.append(f.filename)
                continue

            rel, digest, mime = result
            db.session.add(RequestAttachment(
                request_id=new_request.request_id,
                file_url=rel,
                original_name=f.filename[:255],
                file_hash=digest,
                mime_type=mime,
            ))
            saved += 1

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

        log_action('submit_request', 'request', new_request.request_id,
                f"{request_type} for {barangay}, {municipality}")
            
        db.session.commit()

        flash(
            f"Request submitted for {barangay}, {municipality}. "
            "You will be notified when it is reviewed.",
            "success",
        )
        if saved:
            flash(f"{saved} document(s) attached.", "info")
        if rejected:
            flash(
                "Not attached (images and PDF only): "
                + ", ".join(rejected),
                "warning",
            )
        return redirect(url_for('dashboard.requests_page'))

    # --- GET ---
    q = (
        db.session.query(Location.municipality)
        .filter(Location.elevation_m.isnot(None))
    )
    q = scope_locations(q)
    municipalities = [
        m[0] for m in q.distinct().order_by(Location.municipality).all()
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
    if not can_see_municipality(municipality):
        return jsonify([])    
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

"""
FIELD MONITORING - routes
 
TWO BLOCKS, DIFFERENT FILES. Read the headers.
 
BLOCK 1 -> app/routes/dashboard.py   (field officer submits)
BLOCK 2 -> app/routes/admin.py       (admin reviews)
"""
 
@dashboard_bp.route('/reports')
@field_officer_required
def reports_page():
    """
    Field officer landing page: submit a new report, see past ones.
    """
    user_id = session.get('user_id')
    q = (
        db.session.query(Location.municipality)
        .join(Site, Site.location_id == Location.location_id)
    )
    q = scope_sites(q)
    municipalities = [
        m[0] for m in q.distinct().order_by(Location.municipality).all()
    ]
 
    my_reports = (
        MonitoringReport.query
        .filter_by(user_id=user_id)
        .order_by(MonitoringReport.submitted_at.desc())
        .all()
    )
 
    return render_template(
        'Reports.html',
        active_page='reports',
        municipalities=municipalities,
        my_reports=my_reports,
        # optional pre-selection, sent from the GIS map
        preset_municipality=request.args.get('municipality', ''),
        preset_barangay=request.args.get('barangay', ''),
        preset_site_id=request.args.get('site_id', ''),
    )
 
 
@dashboard_bp.route('/api/sites-in-barangay')
def api_sites_in_barangay():
    """
    Sites within one barangay, with the figures the officer needs.
 
    Feeds the site dropdown. Returns everything at once so choosing a
    site fills the panel with no second request.
    """
    muni = request.args.get('municipality', '')
    brgy = request.args.get('barangay', '')
 
    if not muni or not brgy:
        return jsonify([])
    if not can_see_municipality(muni):
        return jsonify([])
 
    rows = (
        db.session.query(Site, Location)
        .join(Location, Site.location_id == Location.location_id)
        .filter(Location.municipality == muni)
        .filter(Location.barangay == brgy)
        .all()
    )
 
    out = []
    for site, loc in rows:
        totals = db.session.query(
            func.sum(ReforestationRecord.target_quantity),
            func.sum(ReforestationRecord.actual_quantity_planted),
        ).filter(ReforestationRecord.site_id == site.site_id).first()
 
        out.append({
            "site_id": site.site_id,
            "site_name": site.site_name,
            "site_code": site.site_code,
            "area_size_ha": site.area_size_ha,
            "zone_type": site.zone_type,
            "year_contracted": site.year_contracted,
            "date_established": (
                site.date_established.strftime('%Y-%m-%d')
                if site.date_established else None
            ),
            "target_trees": int(totals[0] or 0),
            "actual_planted": int(totals[1] or 0),
            "has_boundary": bool(site.boundary_geojson),
            "boundary_area_ha": site.boundary_area_ha,
            "barangay": loc.barangay,
            "municipality": loc.municipality,
        })
 
    return jsonify(out)
 
 
@dashboard_bp.route('/api/preview-survival', methods=['POST'])
@field_officer_required
def api_preview_survival():
    """
    Live survival calculation while the officer types.
 
    Computes nothing that is not also computed on submit, so the number
    shown on screen is the number that gets stored.
    """
    data = request.get_json(silent=True) or {}
 
    counts = []
    for c in data.get('counts', []):
        try:
            counts.append(int(c))
        except (TypeError, ValueError):
            continue
 
    try:
        plot_size = float(data.get('plot_size_sqm') or 0)
        area = float(data.get('site_area_ha') or 0)
        planted = int(data.get('seedlings_planted') or 0)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "reason": "Invalid numbers."})
 
    return jsonify(compute_survival(counts, plot_size, area, planted))
 
 
@dashboard_bp.route('/reports/submit', methods=['POST'])
@field_officer_required
def submit_report():
    """
    Create a monitoring report.
 
    ORDER OF WORK
    -------------
    1. validate the site and the plot counts
    2. compute the survival rate from the counts
    3. create the report so photos have a report_id to attach to
    4. save photos, read their EXIF, flag anything odd
    5. build the site boundary from corner photos
    6. notify the admins
 
    Photos are never rejected for bad GPS. Every check is recorded as a
    flag and shown to the reviewing admin, who decides.
    """
    user_id = session.get('user_id')
 
    # ---------- 1. site ----------
    try:
        site_id = int(request.form.get('site_id') or 0)
    except ValueError:
        site_id = 0
 
    site = Site.query.get(site_id)
    if site is None:
        flash("Choose a site before submitting.", "danger")
        return redirect(url_for('dashboard.reports_page'))
 
    record = (
        ReforestationRecord.query
        .filter_by(site_id=site.site_id)
        .order_by(ReforestationRecord.date_planted.desc())
        .first()
    )
    if record is None:
        flash(
            "This site has no planting record, so a survival rate cannot "
            "be calculated against it.",
            "danger",
        )
        return redirect(url_for('dashboard.reports_page'))
 
    # ---------- monitoring date ----------
    raw_date = (request.form.get('monitoring_date') or '').strip()
    try:
        monitoring_date = datetime.strptime(raw_date, '%Y-%m-%d').date()
    except ValueError:
        flash("Enter a valid monitoring date.", "danger")
        return redirect(url_for('dashboard.reports_page'))
 
    if monitoring_date > datetime.now(ZoneInfo("Asia/Manila")).date():
        flash("The monitoring date cannot be in the future.", "danger")
        return redirect(url_for('dashboard.reports_page'))
 
    # ---------- 2. plots ----------
    try:
        plot_size = float(request.form.get('plot_size_sqm') or 0)
    except ValueError:
        plot_size = 0
 
    if plot_size <= 0:
        flash("Plot size must be greater than zero.", "danger")
        return redirect(url_for('dashboard.reports_page'))
 
    raw_counts = request.form.getlist('plot_count')
    raw_notes = request.form.getlist('plot_note')
 
    counts = []
    for c in raw_counts:
        c = (c or '').strip()
        if c == '':
            continue
        try:
            n = int(c)
        except ValueError:
            flash(f"'{c}' is not a whole number of seedlings.", "danger")
            return redirect(url_for('dashboard.reports_page'))
        if n < 0:
            flash("Seedling counts cannot be negative.", "danger")
            return redirect(url_for('dashboard.reports_page'))
        counts.append(n)
 
    if not counts:
        flash("Enter at least one plot count.", "danger")
        return redirect(url_for('dashboard.reports_page'))
 
    calc = compute_survival(
        counts, plot_size, site.area_size_ha, record.actual_quantity_planted
    )
 
    if not calc['ok']:
        flash(calc['reason'], "danger")
        return redirect(url_for('dashboard.reports_page'))
 
    # ---------- 3. create the report ----------
    report = MonitoringReport(
        record_id=record.record_id,
        site_id=site.site_id,
        user_id=user_id,
        monitoring_date=monitoring_date,
        survival_rate=calc['survival_rate'] or 0.0,
        plots_recorded=calc['plots_recorded'],
        plot_size_sqm=plot_size,
        total_counted=calc['total_counted'],
        mean_per_plot=calc['mean_per_plot'],
        stdev_per_plot=calc['stdev_per_plot'],
        density_per_ha=calc['density_per_ha'],
        estimated_survivors=calc['estimated_survivors'],
        sampling_intensity=calc['sampling_intensity'],
        remarks=(request.form.get('remarks') or '').strip() or None,
        approval_status='Pending',
    )
    db.session.add(report)
    db.session.flush()          # assigns report_id for the photos
 
    for i, n in enumerate(counts, start=1):
        note = raw_notes[i - 1].strip() if i - 1 < len(raw_notes) else ''
        db.session.add(MonitoringPlot(
            report_id=report.report_id,
            plot_number=i,
            seedlings_alive=n,
            plot_notes=note or None,
        ))
 
    # ---------- 4. photos ----------
    static_folder = current_app.static_folder
 
    # barangay outline, used to sanity-check where photos were taken
    barangay_geom = _load_barangay_geometry(
        site.location.municipality, site.location.barangay
    ) if site.location else None
 
    seen_hashes = set()
    photo_index = 0
 
    def handle_photos(files, photo_type):
        nonlocal photo_index
        saved = []
 
        for f in files:
            if not f or not f.filename:
                continue
 
            photo_index += 1
            meta = extract_photo_metadata(f)
            flags = list(meta['flags'])
 
            # duplicate within this submission
            if meta['file_hash'] in seen_hashes:
                flags.append('duplicate_in_report')
            seen_hashes.add(meta['file_hash'])
 
            # duplicate against every earlier report
            if meta['file_hash'] and MonitoringPhoto.query.filter_by(
                file_hash=meta['file_hash']
            ).first():
                flags.append('duplicate_of_earlier_photo')
 
            stale = check_timestamp(meta['date_time_taken'], monitoring_date)
            if stale:
                flags.append('stale_date')
 
            inside = False
            distance = None
 
            if meta['latitude'] is not None and barangay_geom:
                inside = point_in_geojson(
                    meta['longitude'], meta['latitude'], barangay_geom
                )
                if not inside:
                    flags.append('outside_barangay')
 
                if site.location and site.location.latitude:
                    distance = round(haversine_m(
                        meta['latitude'], meta['longitude'],
                        site.location.latitude, site.location.longitude,
                    ), 1)
 
            path = save_photo(f, static_folder, report.report_id, photo_index)
 
            photo = MonitoringPhoto(
                report_id=report.report_id,
                photo_url=path,
                file_hash=meta['file_hash'],
                photo_type=photo_type,
                latitude=meta['latitude'],
                longitude=meta['longitude'],
                date_time_taken=meta['date_time_taken'],
                inside_boundary=inside,
                distance_from_centroid_m=distance,
                flags=','.join(flags) if flags else None,
            )
            db.session.add(photo)
            saved.append((photo, meta))
 
        return saved
 
    handle_photos(request.files.getlist('plot_photos'), 'plot')
    corner_photos = handle_photos(
        request.files.getlist('boundary_photos'), 'boundary'
    )
 
    # ---------- 5. boundary ----------
    corner_points = [
        (m['longitude'], m['latitude'])
        for _, m in corner_photos
        if m['latitude'] is not None
    ]
 
    boundary_msg = None
 
    if corner_points:
        b = build_boundary(corner_points, site.area_size_ha)
 
        if b['ok']:
            report.boundary_geojson = b['geojson']
            report.captured_area_ha = b['area_ha']
            report.area_difference_pct = b['difference_pct']
 
            # only replace the stored site boundary if there is none yet.
            # An admin approving a later report can update it deliberately.
            if not site.boundary_geojson:
                site.boundary_geojson = b['geojson']
                site.boundary_area_ha = b['area_ha']
                site.boundary_captured_at = datetime.now(
                    ZoneInfo("Asia/Manila")
                )
                boundary_msg = (
                    f"Site boundary captured: {b['area_ha']} ha "
                    f"from {b['points_used']} corners."
                )
            else:
                boundary_msg = (
                    f"Boundary recorded on this report "
                    f"({b['area_ha']} ha). The site already has a stored "
                    f"boundary, which an admin can update on review."
                )
        else:
            boundary_msg = b['reason']
 
    # ---------- 6. notify admins ----------
    where = (
        f"{site.location.barangay}, {site.location.municipality}"
        if site.location else site.site_name
    )
 
    for admin in User.query.filter_by(role='admin').all():
        db.session.add(Notification(
            user_id=admin.user_id,
            notification_type='Report',
            message=(
                f"{session.get('username')} submitted a monitoring report "
                f"for {where}. Survival {report.survival_rate}%."
            ),
            report_id=report.report_id,
            is_read=False,
        ))

    log_action('submit_report', 'monitoring_report', report.report_id,
               f"Submitted for {site.site_name}: "
               f"{calc['plots_recorded']} plots, "
               f"survival {report.survival_rate}%") 
    db.session.commit()
 
    msg = (
        f"Report submitted. Survival {report.survival_rate}% "
        f"from {calc['plots_recorded']} plots. Awaiting review."
    )
    flash(msg, "success")
 
    if boundary_msg:
        flash(boundary_msg, "info")
 
    for w in calc['warnings']:
        flash(w, "warning")
 
    return redirect(url_for('dashboard.reports_page'))
 
 
def _load_barangay_geometry(municipality, barangay):
    """
    Pull one barangay's polygon out of barangay.geojson.
 
    Names are normalised on both sides because the geojson writes towns
    without spaces while the database does not.
    """
    path = os.path.join(
        current_app.static_folder, 'geojson', 'barangay.geojson'
    )
 
    def squash(s):
        return re.sub(r'[\s.\-]', '', str(s or '')).lower()
 
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
    except Exception:
        return None
 
    target = (squash(municipality), squash(barangay))
 
    for feat in data.get('features', []):
        p = feat.get('properties', {})
        if (squash(p.get('NAME_2')), squash(p.get('NAME_3'))) == target:
            return feat.get('geometry')
 
    return None

 
@dashboard_bp.route('/api/dashboard-analytics')
@login_required
def api_dashboard_analytics():
    """
    Every figure the dashboard charts need.
 
    Roughly one second on 478 barangays, most of it the suitability
    scoring in section 3. If that becomes a problem, cache the section 3
    block - the underlying data changes only when species or barangay
    characteristics are reseeded.
    """
    # ------------------------------------------------------------------
    # base pull: every site with its location and planting figures
    # ------------------------------------------------------------------
    q = (
        db.session.query(Site, Location)
        .join(Location, Site.location_id == Location.location_id)
    )
    rows = scope_sites(q).all()

    if not rows:
        return jsonify({
            "scope": scope_label(),
            "empty": True,
            "headline": {
                "sites": 0, "area_ha": 0, "target": 0, "actual": 0,
                "achievement": None,
                "barangays_covered": 0,
                "barangays_total": scope_locations(Location.query).count(),
                "coverage_pct": 0,
                "total_cost": 0, "cost_sites": 0, "avg_cost_per_ha": None,
            },
            "by_year": [], "by_municipality": [], "by_zone": [],
            "scatter": [], "unplanted_top": [], "species_rank": [],
            "correlation": None, "scatter_n": 0,
        })
 
    targets = dict(
        db.session.query(
            ReforestationRecord.site_id,
            func.sum(ReforestationRecord.target_quantity),
        ).group_by(ReforestationRecord.site_id).all()
    )
 
    actuals = dict(
        db.session.query(
            ReforestationRecord.site_id,
            func.sum(ReforestationRecord.actual_quantity_planted),
        ).group_by(ReforestationRecord.site_id).all()
    )
 
    survivals = dict(
        db.session.query(
            ReforestationRecord.site_id,
            func.avg(ReforestationRecord.survival_rate),
        ).filter(ReforestationRecord.survival_rate.isnot(None))
        .group_by(ReforestationRecord.site_id).all()
    )
 
    # ------------------------------------------------------------------
    # SECTION 1 - WHAT HAS BEEN DONE
    # ------------------------------------------------------------------
    total_sites = len(rows)
    total_area = 0.0
    total_target = 0
    total_actual = 0
    total_cost = 0.0
    cost_sites = 0
 
    by_year = {}
    by_muni = {}
    by_zone = {}
    barangays_with_sites = set()
 
    for site, loc in rows:
        area = float(site.area_size_ha or 0)
        tgt = int(targets.get(site.site_id) or 0)
        act = int(actuals.get(site.site_id) or 0)
 
        total_area += area
        total_target += tgt
        total_actual += act
        barangays_with_sites.add((loc.municipality, loc.barangay))
 
        if site.project_cost_3yr:
            total_cost += float(site.project_cost_3yr)
            cost_sites += 1
 
        # --- by year ---
        yr = site.year_contracted
        if yr:
            y = by_year.setdefault(int(yr), {"sites": 0, "area": 0.0,
                                             "target": 0, "actual": 0})
            y["sites"] += 1
            y["area"] += area
            y["target"] += tgt
            y["actual"] += act
 
        # --- by municipality ---
        m = by_muni.setdefault(loc.municipality, {
            "sites": 0, "area": 0.0, "target": 0, "actual": 0,
            "survival_sum": 0.0, "survival_n": 0, "cost": 0.0,
            "cost_area": 0.0,
        })
        m["sites"] += 1
        m["area"] += area
        m["target"] += tgt
        m["actual"] += act
 
        sv = survivals.get(site.site_id)
        if sv is not None:
            m["survival_sum"] += float(sv)
            m["survival_n"] += 1
 
        if site.project_cost_3yr and area > 0:
            m["cost"] += float(site.project_cost_3yr)
            m["cost_area"] += area
 
        # --- by zone ---
        z = site.zone_type or "Unspecified"
        by_zone[z] = by_zone.get(z, 0) + 1
 
    total_barangays = scope_locations(Location.query).count()
 
    # ------------------------------------------------------------------
    # SECTION 2 - HOW WELL WAS IT DONE
    # ------------------------------------------------------------------
    #
    # Achievement rate normalises away contract size. A small barangay
    # delivering 100% outranks a large one delivering 62%, which a raw
    # volume chart would hide.
 
    muni_rows = []
    for name, m in by_muni.items():
        achievement = (m["actual"] / m["target"] * 100) if m["target"] else None
        survival = (m["survival_sum"] / m["survival_n"]) if m["survival_n"] else None
        cost_per_ha = (m["cost"] / m["cost_area"]) if m["cost_area"] else None
 
        muni_rows.append({
            "municipality": name,
            "sites": m["sites"],
            "area": round(m["area"], 2),
            "target": m["target"],
            "actual": m["actual"],
            "achievement": round(achievement, 1) if achievement is not None else None,
            "survival": round(survival, 1) if survival is not None else None,
            "cost_per_ha": round(cost_per_ha, 0) if cost_per_ha else None,
        })
 
    # ------------------------------------------------------------------
    # SECTION 3 - WHAT SHOULD BE DONE NEXT
    # ------------------------------------------------------------------
    #
    # Suitability is summarised as the mean of a barangay's top 5
    # similarity scores. A single top score would be dominated by
    # whichever species happens to be a generalist; the top 5 describes
    # how well the site suits the reference set as a whole.
 
    q_loc = Location.query.filter(Location.elevation_m.isnot(None))
    all_locations = scope_locations(q_loc).all()
 
    planted_by_brgy = {}
    for site, loc in rows:
        key = (loc.municipality, loc.barangay)
        planted_by_brgy[key] = planted_by_brgy.get(key, 0) + int(
            actuals.get(site.site_id) or 0
        )
 
    scatter = []
    unplanted = []
 
    for loc in all_locations:
        result = recommend_for_location(loc, top_k=5)
        if not result["found"] or not result["recommendations"]:
            continue
 
        top5 = result["recommendations"]
        mean_sim = sum(r["similarity"] for r in top5) / len(top5)
 
        key = (loc.municipality, loc.barangay)
        planted = planted_by_brgy.get(key, 0)
 
        scatter.append({
            "municipality": loc.municipality,
            "barangay": loc.barangay,
            "suitability": round(mean_sim, 4),
            "planted": planted,
            "has_site": key in planted_by_brgy,
        })
 
        if key not in planted_by_brgy:
            unplanted.append({
                "municipality": loc.municipality,
                "barangay": loc.barangay,
                "suitability": round(mean_sim, 4),
                "top_species": top5[0]["specie_name"],
                "top_score": top5[0]["similarity"],
                "second_species": top5[1]["specie_name"] if len(top5) > 1 else None,
                "elevation_m": loc.elevation_m,
                "soil_texture": loc.soil_texture,
            })
 
    unplanted.sort(key=lambda x: -x["suitability"])
 
    # --- how often each species reaches a top 5 ---
    species_hits = {}
    for loc in all_locations:
        result = recommend_for_location(loc, top_k=5)
        if not result["found"]:
            continue
        for r in result["recommendations"]:
            species_hits[r["specie_name"]] = species_hits.get(
                r["specie_name"], 0
            ) + 1
 
    species_rank = sorted(
        [{"species": k, "count": v} for k, v in species_hits.items()],
        key=lambda x: -x["count"],
    )[:12]
 
    # --- does suitability predict planting? ---
    with_sites = [s for s in scatter if s["has_site"] and s["planted"] > 0]
    correlation = _pearson(
        [s["suitability"] for s in with_sites],
        [s["planted"] for s in with_sites],
    ) if len(with_sites) > 2 else None
 
    return jsonify({
        "scope": scope_label(),
        "headline": {
            "sites": total_sites,
            "area_ha": round(total_area, 1),
            "target": total_target,
            "actual": total_actual,
            "achievement": round(total_actual / total_target * 100, 1)
                           if total_target else None,
            "barangays_covered": len(barangays_with_sites),
            "barangays_total": total_barangays,
            "coverage_pct": round(
                len(barangays_with_sites) / total_barangays * 100, 1
            ) if total_barangays else 0,
            "total_cost": round(total_cost, 2),
            "cost_sites": cost_sites,
            "avg_cost_per_ha": round(total_cost / total_area, 0)
                               if total_area else None,
        },
        "by_year": [
            {"year": y, **v} for y, v in sorted(by_year.items())
        ],
        "by_municipality": sorted(muni_rows, key=lambda x: -x["area"]),
        "by_zone": [
            {"zone": k, "sites": v}
            for k, v in sorted(by_zone.items(), key=lambda x: -x[1])
        ],
        "scatter": scatter,
        "unplanted_top": unplanted[:15],
        "species_rank": species_rank,
        "correlation": round(correlation, 3) if correlation is not None else None,
        "scatter_n": len(with_sites),
    })
 
 
def _pearson(xs, ys):
    """
    Correlation between two lists, -1 to 1.
 
    Used to answer one question: are the most suitable barangays the ones
    being planted? A value near zero means site suitability is not
    driving where reforestation happens - which is the argument for a
    recommendation system.
    """
    n = len(xs)
    if n < 3:
        return None
 
    mx = sum(xs) / n
    my = sum(ys) / n
 
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
 
    if dx == 0 or dy == 0:
        return None
 
    return num / (dx * dy)
 
@dashboard_bp.route('/api/published-boundaries')
def api_published_boundaries():
    """
    Site boundaries approved by a CENRO and published by the province.

    Only published boundaries are served. A captured boundary that has
    not been through both stages is not an official record and does not
    appear here.
    """
    q = Site.query.filter(
        Site.boundary_published.is_(True),
        Site.boundary_geojson.isnot(None),
    )

    out = []
    for site in scope_sites(q).all():
        try:
            geom = json.loads(site.boundary_geojson)
        except Exception:
            continue

        out.append({
            "site_id": site.site_id,
            "site_name": site.site_name,
            "site_code": site.site_code,
            "municipality": site.location.municipality if site.location else None,
            "barangay": site.location.barangay if site.location else None,
            "contract_area_ha": site.area_size_ha,
            "captured_area_ha": site.boundary_area_ha,
            "captured_at": (site.boundary_captured_at.strftime('%Y-%m-%d')
                            if site.boundary_captured_at else None),
            "geometry": geom,
        })

    return jsonify({"count": len(out), "boundaries": out})

@dashboard_bp.route('/api/site-history/<int:site_id>')
def api_site_history(site_id):
    """
    Monitoring history for one site, newest visit first.

    ONLY APPROVED REPORTS ARE RETURNED.

    A pending report has not been validated by anyone. Showing it on a
    public map would present an unreviewed figure as though it were an
    official record. Rejected reports are excluded for the same reason.
    """
    site = Site.query.get(site_id)
    if site is None:
        return jsonify({"found": False, "reason": "Site not found."}), 404

    # jurisdiction still applies
    cenro = current_cenro()
    if cenro is not None and site.cenro != cenro:
        return jsonify({
            "found": False,
            "reason": "Outside your CENRO jurisdiction.",
        }), 403

    reports = (
        MonitoringReport.query
        .filter(MonitoringReport.site_id == site.site_id,
                MonitoringReport.approval_status == 'Approved')
        .order_by(MonitoringReport.monitoring_date.desc())
        .all()
    )

    planted = db.session.query(
        func.sum(ReforestationRecord.actual_quantity_planted)
    ).filter(ReforestationRecord.site_id == site.site_id).scalar() or 0

    history = []
    for r in reports:
        photos = [
            {
                "url": p.photo_url,
                "type": p.photo_type,
                "lat": p.latitude,
                "lon": p.longitude,
                "taken": (p.date_time_taken.strftime('%d %b %Y, %I:%M %p')
                          if p.date_time_taken else None),
                "flags": p.flags,
                "inside": p.inside_boundary,
            }
            for p in r.photos
        ]

        history.append({
            "report_id": r.report_id,
            "monitoring_date": r.monitoring_date.strftime('%Y-%m-%d'),
            "date_display": r.monitoring_date.strftime('%d %B %Y'),
            "officer": r.officer.username if r.officer else None,
            "survival_rate": r.survival_rate,
            "meets_threshold": r.survival_rate >= 85,
            "plots_recorded": r.plots_recorded,
            "total_counted": r.total_counted,
            "mean_per_plot": r.mean_per_plot,
            "stdev_per_plot": r.stdev_per_plot,
            "sampling_intensity": r.sampling_intensity,
            "estimated_survivors": r.estimated_survivors,
            "remarks": r.remarks,
            "reviewed_by": r.reviewer.username if r.reviewer else None,
            "date_reviewed": (r.date_reviewed.strftime('%d %b %Y')
                              if r.date_reviewed else None),
            "captured_area_ha": r.captured_area_ha,
            "photo_count": len(photos),
            "photos": photos,
            "plots": [
                {"n": p.plot_number, "alive": p.seedlings_alive,
                 "note": p.plot_notes}
                for p in sorted(r.plots, key=lambda x: x.plot_number)
            ],
        })

    # survival trend, oldest first, for the small chart
    trend = [
        {"date": h["monitoring_date"], "rate": h["survival_rate"]}
        for h in reversed(history)
    ]

    return jsonify({
        "found": True,
        "site_id": site.site_id,
        "site_name": site.site_name,
        "site_code": site.site_code,
        "municipality": site.location.municipality if site.location else None,
        "barangay": site.location.barangay if site.location else None,
        "area_size_ha": site.area_size_ha,
        "year_contracted": site.year_contracted,
        "seedlings_planted": int(planted),
        "report_count": len(history),
        "latest_survival": history[0]["survival_rate"] if history else None,
        "trend": trend,
        "history": history,
    })