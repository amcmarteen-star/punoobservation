"""
Pipeline step 4. Soil type and AEZ for each barangay point, from the
BSWM Philippine Soil Series shapefile.

WHAT IT NEEDS:
  - data/generated/barangay_coords.csv   (step 1, make_coords)
  - data/source/soil/PhilSoilSeries.*    (.shp, .shx, .dbf, .prj; the
                                          soil names are in the .dbf)

WHAT IT MAKES:
  - data/generated/barangay_soil.csv

SAFE TO RE-RUN. Barangays already in barangay_soil.csv are kept exactly
as they are; only new ones are looked up. A fresh lookup can land on the
other side of a soil boundary, which would quietly change the species
recommended for a barangay that already had soil data.

HOW TO RUN (from the project root):
    pip install -r scripts/requirements.txt
    python -m scripts.pipeline.get_soil
"""

import csv
import os

import geopandas as gpd
from shapely.geometry import Point

from app.utils.jurisdiction import place_key
from scripts.common import (
    SOIL_SHAPEFILE as SHAPEFILE, COORDS_CSV as COORDS, SOIL_CSV as OUTPUT,
)

# column names in the BSWM shapefile
SOIL_COL = "SOILDESC"
AEZ_COL = "AEZ"
SERIES_COL = "SoilSeries"

FIELDS = ["municipality", "barangay", "district", "lat", "lon",
          "soil_desc", "soil_series", "aez"]


def load_done():
    """Rows already in the soil file, by place_key."""
    if not os.path.exists(OUTPUT):
        return {}
    with open(OUTPUT, newline="", encoding="utf-8") as fh:
        return {place_key(r["municipality"], r["barangay"]): r
                for r in csv.DictReader(fh) if r.get("soil_desc")}


def main():
    with open(COORDS, newline="", encoding="utf-8") as fh:
        coords = list(csv.DictReader(fh))
    done = load_done()
    todo = [r for r in coords
            if place_key(r["municipality"], r["barangay"]) not in done]

    print(f"Barangays        : {len(coords)}")
    print(f"Already have soil: {len(coords) - len(todo)}")
    print(f"To look up       : {len(todo)}")
    if not todo:
        return

    print("Loading shapefile...")
    soil = gpd.read_file(SHAPEFILE)
    # the BSWM file is in Luzon 1911 (EPSG:4253); the points are WGS84
    if soil.crs and soil.crs.to_epsg() != 4326:
        soil = soil.to_crs(epsg=4326)
    print(f"  {len(soil)} soil polygons loaded")

    found = {}
    no_match = 0
    for row in todo:
        pt = Point(float(row["lon"]), float(row["lat"]))   # (x, y) = (lon, lat)

        match = soil[soil.geometry.contains(pt)]
        if match.empty:
            # outside every polygon, nearly always on the coast: use the
            # nearest one instead
            match = soil.iloc[[soil.geometry.distance(pt).idxmin()]]
            no_match += 1

        hit = match.iloc[0]
        found[place_key(row["municipality"], row["barangay"])] = {
            "municipality": row["municipality"],
            "barangay": row["barangay"],
            "district": row.get("district", ""),
            "lat": row["lat"],
            "lon": row["lon"],
            "soil_desc": hit.get(SOIL_COL),
            "soil_series": hit.get(SERIES_COL),
            "aez": hit.get(AEZ_COL),
        }

    # same order as the coords file; kept rows unchanged
    rows = []
    for r in coords:
        key = place_key(r["municipality"], r["barangay"])
        rows.append(done.get(key) or found[key])

    with open(OUTPUT, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print("\nDone.")
    print(f"  {len(rows)} rows written to {OUTPUT}")
    print(f"  {len(found)} looked up, {no_match} of them outside every "
          "polygon (used the nearest)")


if __name__ == "__main__":
    main()
