"""
Move every barangay's point inside its official outline, and read the
elevation and soil again at the new point.

The points in data/generated were made from the old GADM outlines, which
put most barangays in the wrong place (see official_boundaries.py). The
map draws DENR-imported sites at these points, and the species
recommender reads the elevation and soil found there.

For each barangay the new point is barangay_point() of its outline in
app/static/geojson, the same point the app gives a new barangay. A point
that moves more than MOVE_M metres gets its elevation (OpenTopoData,
online, about a minute) and soil (the BSWM shapefile) looked up again.
Climate is kept: it comes from a weather grid about 28 km wide, so a
move of a kilometre or two does not change it.

Only the four CSV files are changed. The database takes them from:

RUN FROM PROJECT ROOT:
    python -m scripts.tools.move_barangay_points --dry-run
    python -m scripts.tools.move_barangay_points
    python -m scripts.pipeline.seed_reference_data

Run the last command on every database (your computer, the server).
Git can undo the CSV changes.
"""

if __package__ in (None, ""):
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(
        _os.path.abspath(__file__)))))
    import scripts  # noqa: F401

import argparse
import csv
import glob
import json
import math
import os
import re
import statistics
import time

import requests

from app.services.request_site import barangay_point
from app.utils.jurisdiction import place_key
from scripts.common import (
    CLIMATE_CSV, COORDS_CSV, ELEVATION_CSV, SOIL_CSV, SOIL_SHAPEFILE,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTLINES = os.path.join(ROOT, "app", "static", "geojson", "*", "*_barangay.geojson")
MOVE_M = 50            # a smaller move keeps its elevation and soil
BROKEN = chr(0xFFFD)   # the replacement character the map files have for ñ
DECIMALS = 6
ELEVATION_URL = "https://api.opentopodata.org/v1/srtm30m"


def metres(lat1, lon1, lat2, lon2):
    dx = (lon2 - lon1) * 111320 * math.cos(math.radians(lat1))
    dy = (lat2 - lat1) * 111132
    return math.hypot(dx, dy)


def load_outlines():
    """Outline geometry by place_key. The map files lost the ñ in a few
    names ("SantoNino" written with a broken character); the CSVs have it."""
    out = {}
    for path in glob.glob(OUTLINES):
        with open(path, encoding="utf-8") as fh:
            for f in json.load(fh)["features"]:
                p = f["properties"]
                town = str(p.get("NAME_2") or "").replace(BROKEN, "ñ")
                brgy = str(p.get("NAME_3") or "").replace(BROKEN, "ñ")
                # "ZoneIV" -> "Zone IV", so place_key reads the numeral
                brgy = re.sub(r"(?<=[a-z])(IX|IV|V?I{1,3}|V)$", r" \g<1>", brgy)
                out[place_key(town, brgy)] = f["geometry"]
    return out


def read(path):
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return reader.fieldnames, list(reader)


def write(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def fetch_elevation(points):
    """{key: metres} for [(key, lat, lon)], 100 per request."""
    out = {}
    for start in range(0, len(points), 100):
        batch = points[start:start + 100]
        resp = requests.get(ELEVATION_URL, timeout=90, params={
            "locations": "|".join(f"{lat},{lon}" for _, lat, lon in batch)})
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "OK":
            raise SystemExit(f"Elevation service said: {data}")
        for (key, _, _), res in zip(batch, data["results"]):
            out[key] = res["elevation"]
        print(f"  elevation {min(start + 100, len(points))}/{len(points)}")
        time.sleep(2)            # the service allows 1 call per second
    return out


def lookup_soil(points):
    """{key: (soil_desc, soil_series, aez)}, as get_soil.py reads them."""
    import geopandas as gpd
    from shapely.geometry import Point
    soil = gpd.read_file(SOIL_SHAPEFILE)
    if soil.crs and soil.crs.to_epsg() != 4326:
        soil = soil.to_crs(epsg=4326)
    out = {}
    for key, lat, lon in points:
        pt = Point(lon, lat)
        match = soil[soil.geometry.contains(pt)]
        if match.empty:          # on the coast: the nearest polygon
            match = soil.iloc[[soil.geometry.distance(pt).idxmin()]]
        hit = match.iloc[0]
        out[key] = (hit.get("SOILDESC"), hit.get("SoilSeries"), hit.get("AEZ"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = ap.parse_args()

    outlines = load_outlines()
    _, coords = read(COORDS_CSV)

    new_point, moved, no_outline = {}, [], []
    for r in coords:
        key = place_key(r["municipality"], r["barangay"])
        geom = outlines.get(key)
        pt = barangay_point(geom) if geom else None
        if pt is None:
            no_outline.append(f"{r['barangay']}, {r['municipality']}")
            continue
        lat, lon = round(pt[0], DECIMALS), round(pt[1], DECIMALS)
        new_point[key] = (lat, lon)
        d = metres(float(r["lat"]), float(r["lon"]), lat, lon)
        if d > MOVE_M:
            moved.append((key, lat, lon, d))

    dists = [m[3] for m in moved]
    print(f"barangays: {len(coords)} | new point found: {len(new_point)} | "
          f"moving more than {MOVE_M} m: {len(moved)}")
    if dists:
        print(f"  move: median {statistics.median(dists):.0f} m, largest {max(dists):.0f} m")
    for key, lat, lon, d in sorted(moved, key=lambda m: -m[3])[:6]:
        print(f"  biggest: {key} moves {d:.0f} m")
    if no_outline:
        print(f"  no outline, point kept: {no_outline}")
    if args.dry_run:
        return 0

    todo = [(k, lat, lon) for k, lat, lon, _ in moved]
    print("Looking up elevation...")
    elevation = fetch_elevation(todo)
    print("Looking up soil...")
    soil = lookup_soil(todo)

    for path in (COORDS_CSV, ELEVATION_CSV, CLIMATE_CSV, SOIL_CSV):
        fields, rows = read(path)
        for r in rows:
            key = place_key(r["municipality"], r["barangay"])
            if key not in new_point:
                continue
            r["lat"], r["lon"] = new_point[key]
            if key in elevation and "elevation_m" in r:
                r["elevation_m"] = elevation[key]
            if key in soil and "soil_desc" in r:
                r["soil_desc"], r["soil_series"], r["aez"] = soil[key]
        write(path, fields, rows)
        print(f"  {os.path.relpath(path, ROOT)}: written")
    print("Now run: python -m scripts.pipeline.seed_reference_data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
