"""
Synthetic site areas for the GIS map.

WHY
---
The NGP sites imported from the DENR workbook carry a barangay and a
hectare figure, but no coordinates, so the map could only show them as a
group at the barangay centre. This module gives each such site its own
AREA of its real size inside its barangay, so the map can draw one shape
and one tree per site. The area's position and outline are made up; its
size is the site's recorded hectares. The map labels these areas as
approximate.

A site that already has a position needs none of this: a published GPS
boundary is drawn as it is, and a site made from a request keeps the
requester's pin and proposed area.

THE SHAPE
---------
An irregular polygon of AREA_VERTICES corners around a centre: the
corners at evenly spread angles (each nudged a little) and at radii that
vary by up to RADIUS_JITTER, then scaled so the area is exactly the
site's hectares. Every corner is at a different angle round the centre,
so the outline never crosses itself. The shape is fixed per site by the
seed; placing only moves it.

HOW AN AREA IS PLACED
---------------------
Candidate centres are drawn at random (seeded, so the same seed always
gives the same layout). A candidate is kept only when the area:
  - grown by the edge buffer, lies wholly inside the barangay: every
    corner inside, and no barangay edge crossing its outline
  - grown by the gap, touches no other site's area, published boundary or
    proposed area in that barangay
  - has every corner inside the area outline (Eastern Pangasinan)
Larger sites are placed first, so the small ones fill the gaps.

TWO SITES NEVER OVERLAP. When a barangay is crowded, first the gap
between sites narrows, then the edge buffer, and as a last resort the
area is drawn smaller than the site's hectares (stored with the shape and
reported). "Grown by" scales the shape about its centre so its narrowest
point moves out by that many metres; elsewhere it moves a little more.

No GeoPandas or Shapely. Inside tests use point_in_ring() from
app/services/monitoring.py, the ray casting the rest of the app uses.
Distances use a flat projection around the barangay's middle latitude,
the same approximation as polygon_area_ha(); at barangay scale it is off
by well under a metre.

Pure functions only: no Flask, no database. The script that stores the
areas is scripts/tools/make_synthetic_areas.py.
"""

import json
import math
import os
import random

from app.services.monitoring import point_in_geojson, point_in_ring
from app.utils.jurisdiction import CENRO_GEOJSON, barangay_geojson_names, place_key


# ----------------------------------------------------------------------
# settings
# ----------------------------------------------------------------------

AREA_VERTICES = 10          # corners of a synthetic area
RADIUS_JITTER = 0.25        # corner distance from the centre varies +-25%
ANGLE_JITTER = 0.3          # each corner's angle moves up to 30% of a step

TRIES = 2500                # candidate centres per attempt
SHRINK_STEP = 0.85          # side x this when nothing fits at full size
MAX_SHRINKS = 12            # 0.85^12 = about 14% of the size
DEFAULT_SEED = 20260601

# (gap between sites, edge buffer, words for the report), strict to loose.
# There is no step that lets two sites overlap.
STEPS = [
    (20.0, 30.0, None),
    (5.0, 30.0, "closer to a neighbouring site"),
    (5.0, 10.0, "closer to the barangay edge"),
    (2.0, 2.0, "at the barangay edge"),
]

# The study area. Areas must fall inside this CENRO's district outlines.
AREA_CENRO = "Urdaneta City"
AREA_NAME = "Eastern Pangasinan"

M_PER_DEG_LAT = 111132.0    # same constants as polygon_area_ha()
M_PER_DEG_LON = 111320.0


# ----------------------------------------------------------------------
# geometry helpers (metres, on a flat plane)
# ----------------------------------------------------------------------

def polygons_of(geometry):
    """
    A GeoJSON Feature, Polygon or MultiPolygon as a list of polygons,
    each a list of rings (outer ring first), each a list of [lng, lat].
    """
    if not isinstance(geometry, dict):
        return []
    if geometry.get("type") == "Feature":
        geometry = geometry.get("geometry") or {}
    coords = geometry.get("coordinates") or []
    if geometry.get("type") == "Polygon":
        polys = [coords]
    elif geometry.get("type") == "MultiPolygon":
        polys = coords
    else:
        return []
    return [p for p in polys if p and len(p[0]) >= 4]


class _Flat:
    """Degrees <-> metres on a flat plane around one latitude."""

    def __init__(self, lat0, lng0):
        self.lat0, self.lng0 = lat0, lng0
        self.kx = M_PER_DEG_LON * math.cos(math.radians(lat0))
        self.ky = M_PER_DEG_LAT

    def to_m(self, lng, lat):
        return (lng - self.lng0) * self.kx, (lat - self.lat0) * self.ky

    def to_deg(self, x, y):
        return self.lng0 + x / self.kx, self.lat0 + y / self.ky


def _area_m2(pts):
    total = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def _bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _bbox_apart(a, b):
    return a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1]


def _orient(ax, ay, bx, by, cx, cy):
    v = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)


def _on_seg(ax, ay, bx, by, cx, cy):
    return (min(ax, bx) - 1e-9 <= cx <= max(ax, bx) + 1e-9 and
            min(ay, by) - 1e-9 <= cy <= max(ay, by) + 1e-9)


def _segs_cross(p1, p2, p3, p4):
    """True when segments p1p2 and p3p4 touch or cross."""
    o1 = _orient(*p1, *p2, *p3)
    o2 = _orient(*p1, *p2, *p4)
    o3 = _orient(*p3, *p4, *p1)
    o4 = _orient(*p3, *p4, *p2)
    if o1 != o2 and o3 != o4:
        return True
    return ((o1 == 0 and _on_seg(*p1, *p2, *p3)) or
            (o2 == 0 and _on_seg(*p1, *p2, *p4)) or
            (o3 == 0 and _on_seg(*p3, *p4, *p1)) or
            (o4 == 0 and _on_seg(*p3, *p4, *p2)))


def _edges(pts):
    return list(zip(pts, pts[1:] + pts[:1]))


def _polys_meet(a, b):
    """True when two simple polygons (lists of (x, y)) overlap or touch."""
    if _bbox_apart(_bbox(a), _bbox(b)):
        return False
    for e1 in _edges(a):
        for e2 in _edges(b):
            if _segs_cross(e1[0], e1[1], e2[0], e2[1]):
                return True
    return point_in_ring(a[0][0], a[0][1], b) or point_in_ring(b[0][0], b[0][1], a)


def _grow(pts, centre, metres):
    """The shape scaled about its centre so its nearest corner moves out
    by `metres`."""
    cx, cy = centre
    r_min = min(math.hypot(x - cx, y - cy) for x, y in pts)
    k = 1.0 + metres / r_min if r_min > 0 else 1.0
    return [(cx + (x - cx) * k, cy + (y - cy) * k) for x, y in pts]


def _blob(rng, area_m2):
    """An irregular polygon of the given area around (0, 0)."""
    step = 2 * math.pi / AREA_VERTICES
    turn = rng.uniform(0, 2 * math.pi)
    pts = []
    for i in range(AREA_VERTICES):
        a = turn + i * step + rng.uniform(-ANGLE_JITTER, ANGLE_JITTER) * step
        r = 1.0 + rng.uniform(-RADIUS_JITTER, RADIUS_JITTER)
        pts.append((r * math.cos(a), r * math.sin(a)))
    k = math.sqrt(area_m2 / _area_m2(pts))
    return [(x * k, y * k) for x, y in pts]


class _Barangay:
    """One barangay projected to metres, ready for fast repeated tests."""

    def __init__(self, geometry):
        polys = polygons_of(geometry)
        lngs = [c[0] for p in polys for c in p[0]]
        lats = [c[1] for p in polys for c in p[0]]
        self.ok = bool(lngs)
        if not self.ok:
            return
        self.flat = _Flat((min(lats) + max(lats)) / 2, (min(lngs) + max(lngs)) / 2)
        self.polys = [
            [[self.flat.to_m(c[0], c[1]) for c in ring[:-1]] for ring in poly]
            for poly in polys
        ]
        # every edge with its bounding box, for the crossing test
        self.edges = []
        for poly in self.polys:
            for ring in poly:
                for a, b in _edges(ring):
                    self.edges.append((a, b, (min(a[0], b[0]), min(a[1], b[1]),
                                              max(a[0], b[0]), max(a[1], b[1]))))
        self.bbox = _bbox([pt for p in self.polys for pt in p[0]])

    def contains(self, x, y):
        for poly in self.polys:
            if point_in_ring(x, y, poly[0]) and not any(
                    point_in_ring(x, y, hole) for hole in poly[1:]):
                return True
        return False

    def holds(self, pts):
        """True when the whole polygon is inside the barangay."""
        if not all(self.contains(x, y) for x, y in pts):
            return False
        box = _bbox(pts)
        mine = _edges(pts)
        for a, b, ebox in self.edges:
            if _bbox_apart(box, ebox):
                continue
            for p, q in mine:
                if _segs_cross(p, q, a, b):
                    return False
        return True

    def ring_m(self, geojson):
        """A stored Polygon's outer ring in this barangay's metres."""
        ring = geojson["coordinates"][0]
        return [self.flat.to_m(c[0], c[1]) for c in ring[:-1]]


def inside_any(lng, lat, geometries):
    """True when the point is inside at least one of the geometries."""
    return any(point_in_geojson(lng, lat, g) for g in geometries)


def area_centre(geojson):
    """(lat, lng) of a stored area's centre: the mean of its corners."""
    ring = geojson["coordinates"][0][:-1]
    return (round(sum(c[1] for c in ring) / len(ring), 6),
            round(sum(c[0] for c in ring) / len(ring), 6))


# ----------------------------------------------------------------------
# placing areas
# ----------------------------------------------------------------------

def place_areas(barangay, sites, seed, area_outline=None, obstacles=None):
    """
    One area per site inside a barangay, none overlapping.

    barangay      the barangay's GeoJSON geometry (dict)
    sites         list of (site_id, hectares)
    seed          with the site id, fixes each site's shape and the layout
    area_outline  optional list of geometries every corner must be inside
    obstacles     optional list of GeoJSON Polygons already on the map in
                  this barangay (other sites' areas, published boundaries,
                  proposed areas) that no new area may touch

    Returns {site_id: result}. result is None when not even a small area
    fitted, else a dict:
        geojson    closed GeoJSON Polygon, corners rounded to 6 decimals
        area_ha    the area as drawn (smaller than asked when shrunk)
        eased      list of the rules that had to ease, in words
    """
    brgy = _Barangay(barangay)
    if not brgy.ok or not sites:
        return {sid: None for sid, _ in sites}

    order = sorted(sites, key=lambda s: (-s[1], s[0]))
    rng = random.Random(f"{seed}:{order[0][0]}:{len(order)}")
    placed = []
    for g in obstacles or []:
        try:
            placed.append(brgy.ring_m(g))
        except (KeyError, IndexError, TypeError):
            continue

    bx0, by0, bx1, by1 = brgy.bbox
    results = {}

    for site_id, ha in order:
        shape = _blob(random.Random(f"{seed}:shape:{site_id}"), ha * 10000.0)
        found = None
        eased = []
        for shrink in range(MAX_SHRINKS + 1):
            k = SHRINK_STEP ** shrink
            base = [(x * k, y * k) for x, y in shape]
            sx0, sy0, sx1, sy1 = _bbox(base)
            # full size tries every step; once even the loosest failed,
            # smaller sizes only need the loosest
            for gap, buf, why in (STEPS if shrink == 0 else STEPS[-1:]):
                lo_x, hi_x = bx0 - sx0 + buf, bx1 - sx1 - buf
                lo_y, hi_y = by0 - sy0 + buf, by1 - sy1 - buf
                if lo_x > hi_x or lo_y > hi_y:
                    continue
                for _ in range(TRIES):
                    cx = rng.uniform(lo_x, hi_x)
                    cy = rng.uniform(lo_y, hi_y)
                    if not brgy.contains(cx, cy):
                        continue
                    pts = [(cx + x, cy + y) for x, y in base]
                    if any(_polys_meet(_grow(pts, (cx, cy), gap), o)
                           for o in placed):
                        continue
                    if not brgy.holds(_grow(pts, (cx, cy), buf)):
                        continue
                    corners = [brgy.flat.to_deg(x, y) for x, y in pts]
                    if area_outline and not all(
                            inside_any(lng, lat, area_outline)
                            for lng, lat in corners):
                        continue
                    found = (pts, corners)
                    break
                if found:
                    if why:
                        eased.append(why)
                    break
            if found:
                if shrink:
                    eased.append(f"shrunk to {k * k:.0%} of its area to fit")
                break

        if found is None:
            results[site_id] = None
            continue

        pts, corners = found
        placed.append(pts)
        ring = [[round(lng, 6), round(lat, 6)] for lng, lat in corners]
        ring.append(list(ring[0]))
        results[site_id] = {
            "geojson": {"type": "Polygon", "coordinates": [ring]},
            "area_ha": round(_area_m2(pts) / 10000.0, 3),
            "eased": eased,
        }
    return results


def area_problems(geojson, barangay, area_outline=None, others=()):
    """
    What is wrong with a stored area, as a list of words; empty when it is
    wholly inside the barangay, its corners inside the study area, and it
    touches none of `others` (GeoJSON Polygons in the same barangay).
    Uses the app's own point_in_geojson on the stored (rounded) corners.
    """
    problems = []
    corners = [tuple(c) for c in geojson["coordinates"][0][:-1]]
    if not all(point_in_geojson(lng, lat, barangay) for lng, lat in corners):
        problems.append("a corner is outside the barangay")
    brgy = _Barangay(barangay)
    if brgy.ok:
        pts = brgy.ring_m(geojson)
        if not brgy.holds(pts):
            problems.append("the barangay edge crosses the area")
        for other in others:
            if _polys_meet(pts, brgy.ring_m(other)):
                problems.append("it overlaps another site")
                break
    if area_outline and not all(inside_any(lng, lat, area_outline)
                                for lng, lat in corners):
        problems.append(f"a corner is outside {AREA_NAME}")
    return problems


# ----------------------------------------------------------------------
# outline files
# ----------------------------------------------------------------------

def _read(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def area_outline(static_dir, cenro=AREA_CENRO):
    """The district outlines of one CENRO's area, as a list of geometries."""
    entry = CENRO_GEOJSON[cenro]
    out = []
    for n in entry["districts"]:
        path = os.path.join(static_dir, "geojson", entry["folder"],
                            f"district{n}.geojson")
        out.extend(f["geometry"] for f in _read(path)["features"])
    return out


def barangay_index(static_dir, cenro=AREA_CENRO):
    """
    {place_key(municipality, barangay): geometry} for one CENRO's barangay
    outline files. place_key() folds the spelling differences between the
    files and the database ("UrdanetaCity", "Sta.", "Pozzorubio").
    """
    index = {}
    for name in barangay_geojson_names(cenro):
        path = os.path.join(static_dir, name)
        if not os.path.exists(path):
            continue
        for f in _read(path)["features"]:
            p = f.get("properties") or {}
            index.setdefault(place_key(p.get("NAME_2"), p.get("NAME_3")),
                             f.get("geometry"))
    return index
