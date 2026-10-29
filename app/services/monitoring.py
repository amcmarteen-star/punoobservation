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
import io
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


def photo_used_before(file_hash):
    """True when the same photo is already on a report or a site visit."""
    from app.models import MonitoringPhoto, SiteVisitPhoto
    return bool(
        MonitoringPhoto.query.filter_by(file_hash=file_hash).first()
        or SiteVisitPhoto.query.filter_by(file_hash=file_hash).first()
    )


def inspect_photo(file_storage, field_date, barangay_geom, site_location,
                  seen_hashes):
    """
    Read one uploaded photo and run every check on it. Shared by
    monitoring reports and site visits, so both flag the same things.

    seen_hashes is a set the caller keeps for one submission, to spot the
    same photo uploaded twice in it. Nothing is ever rejected: each
    problem becomes a flag for the reviewing CENRO.

    Returns (meta, flags, inside_barangay, metres_from_barangay_centre).
    """
    meta = extract_photo_metadata(file_storage)
    flags = list(meta['flags'])

    if meta['file_hash'] in seen_hashes:
        flags.append('duplicate_in_report')
    seen_hashes.add(meta['file_hash'])
    if meta['file_hash'] and photo_used_before(meta['file_hash']):
        flags.append('duplicate_of_earlier_photo')

    if check_timestamp(meta['date_time_taken'], field_date):
        flags.append('stale_date')

    inside = False
    distance = None
    if meta['latitude'] is not None and barangay_geom:
        inside = point_in_geojson(meta['longitude'], meta['latitude'],
                                  barangay_geom)
        if not inside:
            flags.append('outside_barangay')
        if site_location and site_location.latitude:
            distance = round(haversine_m(
                meta['latitude'], meta['longitude'],
                site_location.latitude, site_location.longitude,
            ), 1)

    return meta, flags, inside, distance


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
# The DENR rule depends on the size of the site:
#
#   under 20 ha       the whole site is counted: every surviving seedling.
#                     Nothing is extrapolated. Sampling intensity 100%.
#   20 ha and over    100 m x 100 m plots (1 ha each) covering 10% of the
#                     site. The density in the plots is extrapolated to
#                     the whole area.
#
# The 85 percent threshold governs whether a contractor is paid.
#
# Worked example, plots:
#     site 25 ha -> 10% = 2.5 ha -> 3 plots of 1 ha
#     counted alive  1,020 + 980 + 1,100      = 3,100
#     area sampled   3 x 1 ha                 = 3 ha
#     intensity      3 / 25                   = 12 %
#     mean per plot  3100 / 3                 = 1,033.3
#     density        1,033.3 / 1 ha           = 1,033.3 per ha
#     survivors      1,033.3 x 25             = 25,833
#     planted                                   27,500
#     survival       25833 / 27500            = 93.9 %
#
# Worked example, whole site:
#     site 12 ha, counted in 2 sections: 6,400 + 5,100 = 11,500 alive
#     survivors      11,500 (no extrapolation)
#     planted        13,200
#     survival       11500 / 13200            = 87.1 %


SQM_PER_HA = 10000.0
DENR_THRESHOLD = 85.0

# The sampling rule. Templates read these too (app/__init__.py), so the
# numbers are written here only.
FULL_COUNT_BELOW_HA = 20.0   # under this area, the whole site is counted
TARGET_INTENSITY = 10.0      # from that area up: plots cover 10% of it
SAMPLE_PLOT_SQM = SQM_PER_HA  # each plot 100 m x 100 m


def survival_text(rate):
    """
    A survival rate for messages: "87.5%", or "unknown" when there is no
    rate because the site has no planted figure (see compute_survival).
    Templates use it as {{ rate|survival }}, which capitalises "Unknown".
    """
    if rate is None:
        return "unknown"
    return f"{rate:g}%"


def sampling_plan(site_area_ha):
    """
    How a site of this size is surveyed.

    Returns {"method": "full" | "plots", "target_pct": 100 | 10,
    "plot_size_sqm": None | 10000, "plots_needed": n}, or None when the
    site has no usable area.
    """
    if not site_area_ha or site_area_ha <= 0:
        return None
    if site_area_ha < FULL_COUNT_BELOW_HA:
        return {"method": "full", "target_pct": 100.0,
                "plot_size_sqm": None, "plots_needed": 1}
    needed_ha = site_area_ha * TARGET_INTENSITY / 100.0
    plot_ha = SAMPLE_PLOT_SQM / SQM_PER_HA
    return {"method": "plots", "target_pct": TARGET_INTENSITY,
            "plot_size_sqm": SAMPLE_PLOT_SQM,
            # tolerance: 2.0000001 plots is 2 plots, not 3
            "plots_needed": max(1, math.ceil(needed_ha / plot_ha - 1e-9))}


def compute_survival(plot_counts, site_area_ha, seedlings_planted):
    """
    Turn raw counts into a survival rate, by the rule for the site's size.

    plot_counts        list of ints. Under 20 ha: one per section of the
                       site counted (summed). Otherwise one per plot.
    site_area_ha       contracted area of the site
    seedlings_planted  actual planted, from the reforestation record

    The plot size is not an input: sampling_plan() fixes it from the site
    area. Returns a dict of every intermediate value, so the form can show
    its working and an admin can recompute the result by hand.
    """
    out = {
        "ok": False,
        "reason": None,
        "method": None,
        "target_pct": None,
        "plots_needed": None,
        "plot_size_sqm": None,
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
        out["reason"] = "No counts entered."
        return out

    plan = sampling_plan(site_area_ha)
    if plan is None:
        out["reason"] = "This site has no recorded area."
        return out

    n = len(counts)
    total = sum(counts)
    out.update({
        "method": plan["method"],
        "target_pct": plan["target_pct"],
        "plots_needed": plan["plots_needed"],
        "plot_size_sqm": plan["plot_size_sqm"],
    })

    if plan["method"] == "full":
        # Every seedling on the site was counted, in one or more
        # sections. The count is the number of survivors.
        intensity = 100.0
        survivors = total
        out.update({
            "ok": True,
            "plots_recorded": n,
            "total_counted": total,
            "area_sampled_ha": round(site_area_ha, 3),
            "sampling_intensity": intensity,
            "density_per_ha": round(total / site_area_ha, 1),
            "estimated_survivors": total,
        })
    else:
        mean = total / n
        # population standard deviation. Sample sd is undefined for
        # n = 1, and these plots are the whole set that was measured,
        # not a sample drawn from a larger set of plots.
        stdev = math.sqrt(sum((c - mean) ** 2 for c in counts) / n)

        plot_ha = plan["plot_size_sqm"] / SQM_PER_HA
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

    if plan["method"] == "plots":
        if n < plan["plots_needed"]:
            out["warnings"].append(
                f"{n} of {plan['plots_needed']} plots recorded. A site of "
                f"{site_area_ha:g} ha needs {plan['plots_needed']} plots of "
                f"100 m x 100 m to reach the {TARGET_INTENSITY:g}% DENR "
                f"sampling intensity (now {intensity:.2f}%)."
            )

        if n < 2:
            out["warnings"].append(
                "Only one plot. Variation between plots cannot be "
                "assessed."
            )
        elif mean > 0 and stdev / mean > 0.5:
            out["warnings"].append(
                f"Counts vary widely between plots (mean {mean:.1f}, "
                f"standard deviation {stdev:.1f}). Survival may not be "
                f"even across the site."
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


SPECIES_SUBDIR = "uploads/species"
SPECIES_PHOTO_MAX_BYTES = 5 * 1024 * 1024

# Formats a browser can display. HEIC is left out on purpose: it is fine
# as field evidence, but an <img> tag cannot show it.
SPECIES_PHOTO_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


def save_species_photo(file_storage, static_folder, tree_id):
    """
    Save a species thumbnail under app/static/uploads/species/.

    Returns (relative_path, None) on success, or (None, reason).

    The file is opened with Pillow, and the extension comes from the
    format Pillow detects, not from the uploaded filename. A renamed
    non-image is refused instead of being served from static/.
    """
    file_storage.stream.seek(0)
    raw = file_storage.stream.read()
    if not raw:
        return None, "The file is empty."
    if len(raw) > SPECIES_PHOTO_MAX_BYTES:
        return None, "The photo is larger than 5 MB."

    try:
        with Image.open(io.BytesIO(raw)) as img:
            fmt = img.format
            img.verify()
    except Exception:
        return None, "That file is not a readable image."

    ext = SPECIES_PHOTO_FORMATS.get(fmt)
    if ext is None:
        return None, "Use a JPG, PNG or WebP photo."

    folder = os.path.join(static_folder, SPECIES_SUBDIR)
    os.makedirs(folder, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    name = f"sp{tree_id}_{stamp}{ext}"
    with open(os.path.join(folder, name), "wb") as fh:
        fh.write(raw)

    return f"{SPECIES_SUBDIR}/{name}", None


def delete_species_photo(static_folder, rel_path):
    """
    Remove a replaced species photo from disk.

    Only files inside uploads/species/ are touched, so a bad value in
    photo_url can never delete anything else under static/. A missing
    file is not an error.
    """
    if not rel_path or not rel_path.startswith(SPECIES_SUBDIR + "/"):
        return
    name = os.path.basename(rel_path)
    try:
        os.remove(os.path.join(static_folder, SPECIES_SUBDIR, name))
    except OSError:
        pass