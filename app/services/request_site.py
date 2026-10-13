"""
Map input and planning figures for reforestation requests.

The request form lets a requester drop a pin on the site and, if they
want, click its corners to draw the area. This module checks what the
browser sends, measures the drawn area, and estimates how many
seedlings the area needs.

Everything here is a pure function.
"""

import json
import math
from app.services.monitoring import point_in_geojson, polygon_area_ha


# A pin is required for these, because an approved request of this kind
# is expected to become a reforestation site. Seedling Supply and
# Technical Assistance can be requested without one.
SITE_REQUEST_TYPES = ("New Planting Site",)

# Takes on a site that already exists, so it needs no pin and never
# creates a new site. The requester picks the site on the form.
ADOPTION_REQUEST_TYPE = "Adoption"

# Every type the request form offers, in the order it lists them.
REQUEST_TYPES = (
    "New Planting Site",
    ADOPTION_REQUEST_TYPE,
    "Seedling Supply",
    "Technical Assistance",
)

LAND_OWNERSHIP_CHOICES = (
    "Public land",
    "Private land",
    "Communal or ancestral domain",
    "Not sure",
)

LAND_COVER_CHOICES = (
    "Open grassland",
    "Brushland or shrubs",
    "Open forest",
    "Closed forest",
    "Idle or abandoned farmland",
    "Riverbank or easement",
    "Coastal or mangrove area",
    "Other",
)

# Headings the Description box starts with. The requester writes after
# each colon; headings left blank are dropped by tidy_description().
DESCRIPTION_BULLETS = (
    "Current land use",
    "Intended use of the land",
    "Access to the site",
    "Why it needs reforesting",
)
DESCRIPTION_TEMPLATE = "\n".join(f"\u2022 {b}: " for b in DESCRIPTION_BULLETS)


def tidy_description(text):
    """
    The description without bullets the requester left blank.
    None when nothing was written at all.
    """
    kept = []
    for line in (text or "").splitlines():
        bare = line.strip().lstrip("\u2022-* ").strip()
        heading, _, rest = bare.partition(":")
        if heading in DESCRIPTION_BULLETS and not rest.strip():
            continue
        if line.strip():
            kept.append(line.rstrip())
    return "\n".join(kept) or None


MIN_BOUNDARY_POINTS = 3
MAX_BOUNDARY_POINTS = 50

# Smaller than 100 m2 is almost always a stray double-click, not a site.
MIN_DRAWN_AREA_HA = 0.01

MIN_SPACING_M = 0.5
MAX_SPACING_M = 20.0

SQM_PER_HA = 10000.0

# Standard spacing for each kind of planting, as (row m, plant m).
# The request form offers these in this order, then Custom spacing.
PLANTING_TYPES = {
    "timber": {"label": "Timber", "row_m": 2, "plant_m": 3},
    "agroforestry": {"label": "Agroforestry (fruit trees and trees)",
                     "row_m": 4, "plant_m": 5},
    "bamboo": {"label": "Bamboo", "row_m": 4, "plant_m": 5},
    "fuelwood": {"label": "Fuel wood", "row_m": 2, "plant_m": 2},
}


# ----------------------------------------------------------------------
# pin and drawn area
# ----------------------------------------------------------------------

def _finite_lon_lat(lng, lat):
    return (math.isfinite(lng) and math.isfinite(lat)
            and -180 <= lng <= 180 and -90 <= lat <= 90)


def parse_pin(lat_raw, lng_raw):
    """
    (latitude, longitude) from the hidden form fields, or None when no
    pin was dropped. Raises ValueError with a message for the requester.
    """
    lat_raw = (lat_raw or "").strip()
    lng_raw = (lng_raw or "").strip()
    if not lat_raw and not lng_raw:
        return None

    unreadable = ValueError(
        "The map pin could not be read. Drop the pin again.")
    try:
        lat = float(lat_raw)
        lng = float(lng_raw)
    except ValueError:
        raise unreadable
    if not _finite_lon_lat(lng, lat):
        raise unreadable
    return round(lat, 6), round(lng, 6)


def parse_boundary(raw):
    """
    (geojson_text, area_ha) for a drawn area, or (None, None) when no area
    was drawn. Raises ValueError with a message for the requester.

    Only a single GeoJSON Polygon ring is accepted, longitude first. The
    ring is rebuilt from the parsed numbers rather than stored as sent,
    so nothing but coordinates reaches the database.
    """
    raw = (raw or "").strip()
    if not raw:
        return None, None

    unreadable = ValueError(
        "The drawn area could not be read. Clear it and draw it again.")
    try:
        data = json.loads(raw)
        if data.get("type") != "Polygon":
            raise unreadable
        ring = data["coordinates"][0]
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        raise unreadable
    if not isinstance(ring, list):
        raise unreadable

    points = []
    for pt in ring:
        if not (isinstance(pt, (list, tuple)) and len(pt) == 2):
            raise unreadable
        try:
            lng, lat = float(pt[0]), float(pt[1])
        except (TypeError, ValueError):
            raise unreadable
        if not _finite_lon_lat(lng, lat):
            raise unreadable
        points.append((round(lng, 7), round(lat, 7)))

    # GeoJSON repeats the first corner at the end; count it once.
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()

    if len(set(points)) < MIN_BOUNDARY_POINTS:
        raise ValueError(
            f"An area needs at least {MIN_BOUNDARY_POINTS} corners. "
            "Add more corners, or clear the area.")
    if len(points) > MAX_BOUNDARY_POINTS:
        raise ValueError(
            f"An area can have at most {MAX_BOUNDARY_POINTS} corners.")

    area = polygon_area_ha(points)
    if area < MIN_DRAWN_AREA_HA:
        raise ValueError(
            "The drawn area is smaller than 0.01 ha (100 m²). "
            "Clear it and draw it again.")

    closed = [list(p) for p in points] + [list(points[0])]
    return json.dumps({"type": "Polygon", "coordinates": [closed]}), area


def boundary_dict(geojson_text):
    """The stored polygon as a dict, for templates. None when absent."""
    if not geojson_text:
        return None
    try:
        return json.loads(geojson_text)
    except ValueError:
        return None


def boundary_points(geojson_text):
    """Corners of a stored polygon as (lng, lat), closing corner dropped."""
    data = boundary_dict(geojson_text)
    if not data:
        return []
    ring = data["coordinates"][0]
    return [tuple(p) for p in ring[:-1]]


def boundary_centre(geojson_text):
    """
    (latitude, longitude) at the average of the corners.

    Stands in for a pin when only an area was drawn. Good enough for a
    marker; it is not a true centroid.
    """
    pts = boundary_points(geojson_text)
    if not pts:
        return None
    lng = sum(p[0] for p in pts) / len(pts)
    lat = sum(p[1] for p in pts) / len(pts)
    return round(lat, 6), round(lng, 6)


def proposed_area_for_site(site):
    """
    The requester's pin and drawn area, as a temporary stand-in on a site
    that was created from a request.

    Returns {"request_id", "area_ha", "geometry", "pin"}, or None when:
      - the site did not come from a request
      - the request marked nothing on the map
      - the province has published a GPS boundary for the site, which
        replaces the proposed area for good

    Display only. It is never written to Site.boundary_geojson, so the
    first GPS capture and the publish step behave exactly as before, and
    the GIS map (which serves published boundaries only) never shows it.
    """
    req = site.source_request
    if req is None or site.boundary_published:
        return None

    geometry = boundary_dict(req.boundary_geojson)
    pin = ([req.latitude, req.longitude]
           if req.latitude is not None and req.longitude is not None
           else None)
    if geometry is None and pin is None:
        return None

    return {
        "request_id": req.request_id,
        "area_ha": req.boundary_area_ha,
        "geometry": geometry,
        "pin": pin,
    }


def geometry_centre(geojson_text):
    """
    (latitude, longitude) at the average of a polygon's outer corners.

    Accepts a GeoJSON Feature, Polygon or MultiPolygon, as stored on
    Site.boundary_geojson. For a MultiPolygon the largest ring is used.
    Returns None when nothing usable is there. A marker position, not a
    true centroid.
    """
    data = boundary_dict(geojson_text)
    if not isinstance(data, dict):
        return None
    if data.get("type") == "Feature":
        data = data.get("geometry") or {}

    coords = data.get("coordinates") or []
    if data.get("type") == "Polygon":
        rings = [coords[0]] if coords else []
    elif data.get("type") == "MultiPolygon":
        rings = [poly[0] for poly in coords if poly]
    else:
        return None
    if not rings:
        return None

    ring = max(rings, key=len)
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    if not ring:
        return None

    lng = sum(p[0] for p in ring) / len(ring)
    lat = sum(p[1] for p in ring) / len(ring)
    return round(lat, 6), round(lng, 6)


def geometry_bbox(geojson_text):
    """
    [south, west, north, east] around every corner of a stored boundary.

    Accepts a Feature, Polygon or MultiPolygon. None when there is no
    usable geometry. The map uses it to hide a site's tree once the
    boundary is big enough on screen to show the site by itself.
    """
    data = boundary_dict(geojson_text)
    if not isinstance(data, dict):
        return None
    if data.get("type") == "Feature":
        data = data.get("geometry") or {}

    coords = data.get("coordinates") or []
    if data.get("type") == "Polygon":
        rings = coords
    elif data.get("type") == "MultiPolygon":
        rings = [ring for poly in coords for ring in poly]
    else:
        return None

    points = [p for ring in rings for p in ring
              if isinstance(p, (list, tuple)) and len(p) >= 2]
    if not points:
        return None

    lngs = [p[0] for p in points]
    lats = [p[1] for p in points]
    return [min(lats), min(lngs), max(lats), max(lngs)]


def site_position(site):
    """
    Where a site's own map marker goes, as (lat, lon, placed_by), or None.

    Priority matches the boundaries themselves:
      1. a published GPS boundary: its centre
      2. a site made from a request: the requester's pin
    None means the site has no position of its own. DENR-imported sites
    record no coordinates, so they stay grouped at the barangay centroid.
    """
    if site.boundary_published and site.boundary_geojson:
        centre = geometry_centre(site.boundary_geojson)
        if centre:
            return centre[0], centre[1], "published boundary"

    req = site.source_request
    if req is not None and req.latitude is not None and req.longitude is not None:
        return req.latitude, req.longitude, "requester's pin"

    return None


def points_outside(points, geometry):
    """How many (lng, lat) points fall outside a GeoJSON geometry."""
    return sum(1 for lng, lat in points
               if not point_in_geojson(lng, lat, geometry))


# ----------------------------------------------------------------------
# seedlings
# ----------------------------------------------------------------------

def parse_spacing(row_raw, plant_raw):
    """
    (row_m, plant_m) from the custom spacing fields.
    Raises ValueError with a message for the requester.
    """
    message = ValueError(
        f"Enter both spacings in metres, between {MIN_SPACING_M:g} "
        f"and {MAX_SPACING_M:g}.")
    try:
        row = float((row_raw or "").strip())
        plant = float((plant_raw or "").strip())
    except ValueError:
        raise message
    for v in (row, plant):
        if not (math.isfinite(v) and MIN_SPACING_M <= v <= MAX_SPACING_M):
            raise message
    return row, plant


def density_from_spacing(row_m, plant_m):
    """
    Seedlings per hectare for a planting grid.

    Rounded down, the way planting plans quote it: a 2 m x 3 m grid gives
    each seedling 6 m2, and 10,000 / 6 is written as 1,666 per hectare.
    """
    return math.floor(SQM_PER_HA / (row_m * plant_m) + 1e-9)


def estimate_seedlings(area_ha, row_m, plant_m):
    """
    Seedlings needed for an area: area / spacing, rounded up.
    None when either is missing.

    Worked from the area itself, not from a rounded per-hectare
    density: 2 ha at 2 m x 3 m is 20,000 m2 / 6 m2 = 3,334 seedlings.

    A planning figure only. It does not add extra seedlings for
    replanting losses.
    """
    if not area_ha or not row_m or not plant_m:
        return None
    # The inner round stops float noise like 3333.0000000001 becoming 3334.
    return math.ceil(round(area_ha * SQM_PER_HA / (row_m * plant_m), 6))
