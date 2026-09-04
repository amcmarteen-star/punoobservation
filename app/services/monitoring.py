"""
Field monitoring calculations.

PUT THIS FILE AT:
    app/services/monitoring.py

Three jobs:
    1. Read GPS and timestamp out of a photo's EXIF metadata
    2. Compute survival rate from sampling plot counts
    3. Build a site boundary polygon from GPS-tagged corner photos

Nothing here touches the database or Flask. Pure functions, so each part
can be tested on its own.
"""

import hashlib
import json
import math
import os
import re
from datetime import datetime

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS


# ======================================================================
# 1. EXIF EXTRACTION
# ======================================================================
#
# GPS camera apps write coordinates and a timestamp into the image file
# itself. Reading them means the officer types nothing, and the values
# come from the device rather than from a person.
#
# EXIF stores coordinates as three rationals - degrees, minutes, seconds
# - plus a reference letter (N/S/E/W). They must be converted to signed
# decimal degrees before they are usable.


def _to_degrees(dms):
    """(deg, min, sec) rationals -> decimal degrees."""
    d, m, s = dms
    return float(d) + float(m) / 60.0 + float(s) / 3600.0


def extract_photo_metadata(file_storage):
    """
    Read GPS, timestamp and a file hash from an uploaded image.

    Returns a dict. Every field can be None - a photo stripped of EXIF
    by a messaging app still uploads fine, it is simply flagged.

    file_storage is a Werkzeug FileStorage from request.files.
    """
    result = {
        "latitude": None,
        "longitude": None,
        "date_time_taken": None,
        "file_hash": None,
        "camera": None,
        "flags": [],
    }

    # hash first, from the raw bytes, before PIL touches the stream
    file_storage.stream.seek(0)
    raw = file_storage.stream.read()
    result["file_hash"] = hashlib.sha256(raw).hexdigest()
    file_storage.stream.seek(0)

    try:
        img = Image.open(file_storage.stream)
        exif = img._getexif()
    except Exception:
        result["flags"].append("unreadable_exif")
        file_storage.stream.seek(0)
        return result

    file_storage.stream.seek(0)

    if not exif:
        result["flags"].append("no_exif")
        return result

    tags = {}
    for tag_id, value in exif.items():
        tags[TAGS.get(tag_id, tag_id)] = value

    # --- camera model, useful for spotting screenshots ---
    make = str(tags.get("Make", "")).strip()
    model = str(tags.get("Model", "")).strip()
    if make or model:
        result["camera"] = f"{make} {model}".strip()

    # --- timestamp ---
    raw_dt = tags.get("DateTimeOriginal") or tags.get("DateTime")
    if raw_dt:
        try:
            result["date_time_taken"] = datetime.strptime(
                str(raw_dt), "%Y:%m:%d %H:%M:%S"
            )
        except ValueError:
            result["flags"].append("bad_timestamp")
    else:
        result["flags"].append("no_timestamp")

    # --- GPS ---
    gps_raw = tags.get("GPSInfo")
    if not gps_raw:
        result["flags"].append("no_gps")
        return result

    gps = {GPSTAGS.get(k, k): v for k, v in gps_raw.items()}

    try:
        lat = _to_degrees(gps["GPSLatitude"])
        lon = _to_degrees(gps["GPSLongitude"])

        if str(gps.get("GPSLatitudeRef", "N")).upper() == "S":
            lat = -lat
        if str(gps.get("GPSLongitudeRef", "E")).upper() == "W":
            lon = -lon

        result["latitude"] = round(lat, 6)
        result["longitude"] = round(lon, 6)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        result["flags"].append("no_gps")

    return result


def check_timestamp(taken, monitoring_date, max_days=60):
    """
    Flag a photo taken long before the monitoring date.

    A recycled photograph from a previous visit is the obvious way to
    fake a report. This does not prove anything - it surfaces a gap for
    a human to judge.
    """
    if taken is None or monitoring_date is None:
        return None

    gap = (monitoring_date - taken.date()).days

    if gap > max_days:
        return f"photo is {gap} days older than the monitoring date"
    if gap < -1:
        return "photo is dated after the monitoring date"
    return None


# ======================================================================
# 2. SURVIVAL RATE FROM SAMPLING PLOTS
# ======================================================================
#
# DENR assesses survival by laying out fixed-size plots across a site,
# counting surviving seedlings in each, and extrapolating the density to
# the full area. The 85 percent threshold governs whether a contractor
# is paid.
#
# Worked example:
#     site 25 ha, 400 sqm plots, 31 plots, 1,178 counted alive
#     area sampled   31 x 0.04 ha            = 1.24 ha
#     intensity      1.24 / 25               = 4.96 %
#     mean per plot  1178 / 31               = 38.0
#     density        38.0 / 0.04             = 950 per ha
#     survivors      950 x 25                = 23,750
#     planted                                  27,500
#     survival       23750 / 27500            = 86.4 %


SQM_PER_HA = 10000.0
DENR_THRESHOLD = 85.0
TARGET_INTENSITY = 5.0


def compute_survival(plot_counts, plot_size_sqm, site_area_ha,
                     seedlings_planted):
    """
    Turn raw plot counts into a survival rate.

    plot_counts        list of ints, one per plot
    plot_size_sqm      area of a single plot
    site_area_ha       contracted area of the site
    seedlings_planted  actual planted, from the reforestation record

    Returns a dict of every intermediate value, so the form can show its
    working and an admin can recompute the result by hand.
    """
    out = {
        "ok": False,
        "reason": None,
        "plots_recorded": 0,
        "total_counted": 0,
        "mean_per_plot": None,
        "stdev_per_plot": None,
        "plot_size_ha": None,
        "area_sampled_ha": None,
        "sampling_intensity": None,
        "density_per_ha": None,
        "estimated_survivors": None,
        "survival_rate": None,
        "meets_threshold": None,
        "warnings": [],
    }

    counts = [c for c in plot_counts if c is not None]

    if not counts:
        out["reason"] = "No plot counts entered."
        return out

    if not plot_size_sqm or plot_size_sqm <= 0:
        out["reason"] = "Plot size must be greater than zero."
        return out

    if not site_area_ha or site_area_ha <= 0:
        out["reason"] = "This site has no recorded area."
        return out

    n = len(counts)
    total = sum(counts)
    mean = total / n

    # population standard deviation. Sample sd is undefined for n = 1,
    # and these plots are the whole set that was measured, not a sample
    # drawn from a larger set of plots.
    variance = sum((c - mean) ** 2 for c in counts) / n
    stdev = math.sqrt(variance)

    plot_ha = plot_size_sqm / SQM_PER_HA
    sampled_ha = plot_ha * n
    intensity = (sampled_ha / site_area_ha) * 100.0

    density = mean / plot_ha
    survivors = density * site_area_ha

    out.update({
        "ok": True,
        "plots_recorded": n,
        "total_counted": total,
        "mean_per_plot": round(mean, 2),
        "stdev_per_plot": round(stdev, 2),
        "plot_size_ha": round(plot_ha, 4),
        "area_sampled_ha": round(sampled_ha, 3),
        "sampling_intensity": round(intensity, 2),
        "density_per_ha": round(density, 1),
        "estimated_survivors": int(round(survivors)),
    })

    if seedlings_planted and seedlings_planted > 0:
        rate = (survivors / seedlings_planted) * 100.0
        out["survival_rate"] = round(rate, 2)
        out["meets_threshold"] = rate >= DENR_THRESHOLD
    else:
        out["warnings"].append(
            "No planted quantity on record for this site, so a survival "
            "rate cannot be computed. The estimated number of survivors "
            "is still shown."
        )

    # --- quality warnings. None of these block a submission. ---

    if intensity < TARGET_INTENSITY:
        out["warnings"].append(
            f"Sampling intensity is {intensity:.2f}%, below the 5% DENR "
            f"reference. Roughly "
            f"{math.ceil((site_area_ha * TARGET_INTENSITY / 100) / plot_ha)} "
            f"plots of this size would be needed to reach 5%."
        )

    if n < 3:
        out["warnings"].append(
            "Fewer than 3 plots. Variation between plots cannot be "
            "assessed meaningfully."
        )

    if mean > 0 and stdev / mean > 0.5:
        out["warnings"].append(
            f"Counts vary widely between plots (mean {mean:.1f}, "
            f"standard deviation {stdev:.1f}). Survival may not be even "
            f"across the site."
        )

    if out["survival_rate"] is not None and out["survival_rate"] > 100:
        out["warnings"].append(
            "Estimated survivors exceed the recorded planted quantity. "
            "Check the plot size, the plot count, or the planting record."
        )

    return out


# ======================================================================
# 3. SITE BOUNDARY FROM CORNER PHOTOS
# ======================================================================
#
# The officer photographs each corner of the site with a GPS camera. The
# coordinates are joined into a polygon.
#
# A CONVEX HULL is used - the shape a rubber band would make around all
# the points.
#
# LIMITATION: a convex hull cannot represent a concave shape. An L-shaped
# parcel, or one bending around a stream, will have its notch filled in,
# so the captured area comes out larger than the real parcel. The
# comparison against contracted area below is what makes such cases
# visible.


MIN_BOUNDARY_POINTS = 4


def _cross(o, a, b):
    """Cross product of OA and OB. Positive means a counter-clockwise turn."""
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def convex_hull(points):
    """
    Andrew's monotone chain. Returns the hull in counter-clockwise order.

    Sort the points, sweep once for the lower boundary and once for the
    upper, discarding any point that would make a clockwise turn.
    """
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    lower = []
    for p in pts:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    return lower[:-1] + upper[:-1]


def polygon_area_ha(coords):
    """
    Area of a lat/lon polygon in hectares.

    Uses the shoelace formula on coordinates projected to metres with an
    equirectangular approximation, scaled by cos(latitude) so that a
    degree of longitude shrinks correctly away from the equator.

    Accurate enough at the scale of a single parcel. For areas spanning
    hundreds of kilometres a proper projection would be required.
    """
    if len(coords) < 3:
        return 0.0

    mean_lat = sum(c[1] for c in coords) / len(coords)
    m_per_deg_lat = 111132.0
    m_per_deg_lon = 111320.0 * math.cos(math.radians(mean_lat))

    pts = [
        (c[0] * m_per_deg_lon, c[1] * m_per_deg_lat)
        for c in coords
    ]

    total = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        total += x1 * y2 - x2 * y1

    return abs(total) / 2.0 / SQM_PER_HA


def build_boundary(points, contract_area_ha=None):
    """
    Convex hull of GPS corner points, as GeoJSON, with an area check.

    points is a list of (longitude, latitude) tuples - GeoJSON order,
    longitude first.
    """
    out = {
        "ok": False,
        "reason": None,
        "geojson": None,
        "area_ha": None,
        "contract_area_ha": contract_area_ha,
        "difference_pct": None,
        "points_used": 0,
        "warnings": [],
    }

    valid = [p for p in points if p and p[0] is not None and p[1] is not None]

    if len(valid) < MIN_BOUNDARY_POINTS:
        out["reason"] = (
            f"{len(valid)} corner photo(s) carried GPS data. "
            f"At least {MIN_BOUNDARY_POINTS} are needed to form a boundary."
        )
        return out

    unique = set(valid)
    if len(unique) < MIN_BOUNDARY_POINTS:
        out["reason"] = (
            f"{len(valid)} corner photo(s) had GPS, but only "
            f"{len(unique)} distinct location(s). Corner photographs must "
            f"be taken at different points around the site."
        )
        return out

    hull = convex_hull(valid)

    if len(hull) < 3:
        out["reason"] = (
            "The corner points fall on a straight line and cannot form "
            "an area."
        )
        return out

    ring = hull + [hull[0]]        # GeoJSON polygons must close
    area = polygon_area_ha(hull)

    out.update({
        "ok": True,
        "points_used": len(hull),
        "area_ha": round(area, 3),
        "geojson": json.dumps({
            "type": "Polygon",
            "coordinates": [[[round(x, 6), round(y, 6)] for x, y in ring]],
        }),
    })

    if len(hull) < len(valid):
        out["warnings"].append(
            f"{len(valid) - len(hull)} point(s) fell inside the boundary "
            f"and were not used as corners."
        )

    if contract_area_ha and contract_area_ha > 0:
        diff = ((area - contract_area_ha) / contract_area_ha) * 100.0
        out["difference_pct"] = round(diff, 1)

        if diff > 10:
            out["warnings"].append(
                f"Captured area is {diff:.1f}% larger than the contracted "
                f"{contract_area_ha} ha. Either the parcel is not convex, "
                f"or a corner photo was taken outside the site."
            )
        elif diff < -10:
            out["warnings"].append(
                f"Captured area is {abs(diff):.1f}% smaller than the "
                f"contracted {contract_area_ha} ha. The corners may not "
                f"cover the whole parcel."
            )

    return out


# ======================================================================
# 4. LOCATION CHECKS
# ======================================================================


def point_in_ring(x, y, ring):
    """
    Ray casting. Count how many times a ray from the point crosses the
    boundary. Odd means inside.
    """
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-300) + xi
        ):
            inside = not inside
        j = i
    return inside


def point_in_geojson(lon, lat, geojson_obj):
    """True if the point lies inside a GeoJSON Polygon or MultiPolygon."""
    if not geojson_obj:
        return False

    geom = geojson_obj
    if geom.get("type") == "Feature":
        geom = geom.get("geometry", {})

    coords = geom.get("coordinates", [])
    gtype = geom.get("type")

    if gtype == "Polygon":
        polygons = [coords]
    elif gtype == "MultiPolygon":
        polygons = coords
    else:
        return False

    for poly in polygons:
        if poly and point_in_ring(lon, lat, poly[0]):
            return True
    return False


def haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


# ======================================================================
# 5. FILE SAVING
# ======================================================================

UPLOAD_SUBDIR = os.path.join("uploads", "monitoring")
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".heic"}


def safe_filename(original, report_id, index):
    """
    Predictable filename. The original is never trusted - it can contain
    path separators or characters the filesystem will not accept.
    """
    ext = os.path.splitext(original or "")[1].lower()
    if ext not in ALLOWED_EXT:
        ext = ".jpg"
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"r{report_id}_{index}_{stamp}{ext}"


def save_photo(file_storage, static_folder, report_id, index):
    """
    Write the upload under app/static/uploads/monitoring/.

    Returns the path relative to static/, which is what photo_url stores
    and what url_for('static', filename=...) expects.

    NOTE: local disk does not survive a Railway redeploy. Moving to
    Supabase Storage means replacing this function only.
    """
    folder = os.path.join(static_folder, UPLOAD_SUBDIR)
    os.makedirs(folder, exist_ok=True)

    name = safe_filename(file_storage.filename, report_id, index)
    path = os.path.join(folder, name)

    file_storage.stream.seek(0)
    file_storage.save(path)

    return f"{UPLOAD_SUBDIR}/{name}".replace("\\", "/")

REQUEST_SUBDIR = os.path.join("uploads", "requests")
ALLOWED_DOC_EXT = {".jpg", ".jpeg", ".png", ".heic", ".pdf"}


def save_request_file(file_storage, static_folder, request_id, index):
    """
    Save one request attachment.

    Returns (relative_path, sha256, mime_type) or None if the extension
    is not allowed.

    PDFs are permitted here but not for monitoring photographs, because
    a request letter is a document while a plot photograph is evidence
    that must carry EXIF.
    """
    ext = os.path.splitext(file_storage.filename or "")[1].lower()
    if ext not in ALLOWED_DOC_EXT:
        return None

    folder = os.path.join(static_folder, REQUEST_SUBDIR)
    os.makedirs(folder, exist_ok=True)

    file_storage.stream.seek(0)
    raw = file_storage.stream.read()
    digest = hashlib.sha256(raw).hexdigest()
    file_storage.stream.seek(0)

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    name = f"req{request_id}_{index}_{stamp}{ext}"
    file_storage.save(os.path.join(folder, name))

    mime = "application/pdf" if ext == ".pdf" else f"image/{ext.lstrip('.')}"
    rel = f"{REQUEST_SUBDIR}/{name}".replace("\\", "/")

    return rel, digest, mime