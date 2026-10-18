"""
Pipeline step 1. One point per barangay, for every barangay the map
outline files cover.

HOW TO RUN (from the project root):
    python -m scripts.pipeline.make_coords --dry-run   # show, write nothing
    python -m scripts.pipeline.make_coords             # write the file

WHAT IT MAKES
-------------
data/generated/barangay_coords.csv: municipality, barangay, district,
lat, lon. The input to get_elevation, get_soil and (through the
elevation file) get_climate.

WHERE THE ROWS COME FROM
------------------------
Rows that already have climate data: copied from barangay_climate.csv.
Those are the original 478 eastern centroids, with the names
tools/fix_names.py cleaned. Keeping them exactly means get_climate
recognises them as done and does not fetch them again, and the
coordinates already in the database stay put.

Every other barangay: from the barangay outline files listed in
CENRO_GEOJSON (app/utils/jurisdiction.py). The point is barangay_point(),
the same one the dataset import gives a barangay, so it always lies
inside the barangay. Names are cleaned the way fix_names does it
("BacayaoNorte" -> "Bacayao Norte"), and towns take the database
spelling ("DagupanCity" -> "Dagupan City").

Adding a CENRO later: add its outline files, then run this again. Rows
already in the file are never moved or renamed.
"""

# Lets the file run with VS Code's Run button (python path/to/file.py)
# as well as with python -m scripts....: puts the project root on the
# path, and imports `scripts` so .env is loaded before the app is.
if __package__ in (None, ""):
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(
        _os.path.abspath(__file__)))))
    import scripts  # noqa: F401

import argparse
import csv
import json
import os

from app.services.request_site import barangay_point
from app.utils.jurisdiction import (
    CENRO_GEOJSON, barangay_geojson_names, canonical_municipality, place_key,
)
from scripts.common import CLIMATE_CSV as CLIMATE, COORDS_CSV as OUTPUT, STATIC_DIR as STATIC
from scripts.tools.fix_names import fix

FIELDS = ["municipality", "barangay", "district", "lat", "lon"]


def main(dry_run):
    rows, seen = [], set()

    # 1. the rows that already have climate data, unchanged
    if os.path.exists(CLIMATE):
        with open(CLIMATE, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                rows.append({k: r[k] for k in FIELDS})
                seen.add(place_key(r["municipality"], r["barangay"]))
    print(f"Kept from {os.path.basename(CLIMATE)}: {len(rows)}")

    # 2. every other barangay in the outline files
    added, no_point = {}, []
    for cenro in CENRO_GEOJSON:
        for name in barangay_geojson_names(cenro):
            path = os.path.join(STATIC, name)
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as fh:
                features = json.load(fh)["features"]
            for f in features:
                p = f["properties"]
                key = place_key(p["NAME_2"], p["NAME_3"])
                if key in seen:
                    continue
                point = barangay_point(f["geometry"])
                if point is None:
                    no_point.append(f"{p['NAME_3']}, {p['NAME_2']}")
                    continue
                rows.append({
                    "municipality": canonical_municipality(p["NAME_2"]) or fix(p["NAME_2"]),
                    "barangay": fix(p["NAME_3"]),
                    "district": p.get("DISTRICT") or "",
                    "lat": point[0],
                    "lon": point[1],
                })
                seen.add(key)
                added[cenro] = added.get(cenro, 0) + 1

    for cenro, n in added.items():
        print(f"Added for CENRO {cenro}: {n}")
    if no_point:
        print(f"No usable outline, left out: {no_point}")
    print(f"Total: {len(rows)}")

    if dry_run:
        print("\nDry run. Nothing written. A few added rows:")
        for r in rows[-len(added) * 2 or None:][:6]:
            print("  ", r)
        return

    with open(OUTPUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"Written to {OUTPUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    main(ap.parse_args().dry_run)
