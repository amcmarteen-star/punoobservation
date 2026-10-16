"""
Pipeline step 2. Fetch elevation for every barangay.

WHAT IT NEEDS:
  - data/generated/barangay_coords.csv   (step 1, make_coords)

WHAT IT MAKES:
  - data/generated/barangay_elevation.csv

HOW TO RUN (from the project root):
  python -m scripts.pipeline.get_elevation

Source: SRTM 30m DEM via OpenTopoData public API.
Limits: 100 locations per request, 1 call per second, 1000 calls per day.
1,365 barangays = 14 requests. Well inside the limit.
"""

import csv
import time

import requests

from scripts.common import COORDS_CSV as IN_FILE, ELEVATION_CSV as OUT_FILE

BATCH = 100
# --- 1. read the coordinates -------------------------------------------
with open(IN_FILE, newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

print(f"Loaded {len(rows)} barangays from {IN_FILE}")

# --- 2. ask the API, 100 at a time -------------------------------------
for start in range(0, len(rows), BATCH):
    batch = rows[start:start + BATCH]
    locs = "|".join(f"{r['lat']},{r['lon']}" for r in batch)

    url = "https://api.opentopodata.org/v1/srtm30m"

    try:
        resp = requests.get(url, params={"locations": locs}, timeout=90)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  BATCH FAILED at row {start}: {e}")
        print("  Wait 60 seconds, then run the script again.")
        raise

    if data.get("status") != "OK":
        print("  API said:", data)
        raise SystemExit("Stopping. Check the message above.")

    for r, res in zip(batch, data["results"]):
        r["elevation_m"] = res["elevation"]

    done = min(start + BATCH, len(rows))
    print(f"  {done}/{len(rows)} done")
    time.sleep(2)          # stay under 1 call/second

# --- 3. flag anything suspicious ---------------------------------------
missing = [r for r in rows if r.get("elevation_m") is None]
weird = [r for r in rows
         if r.get("elevation_m") is not None
         and (r["elevation_m"] < 0 or r["elevation_m"] > 2000)]

if missing:
    print(f"\nWARNING: {len(missing)} barangays got no elevation:")
    for r in missing[:10]:
        print("   ", r["municipality"], "-", r["barangay"])

if weird:
    print(f"\nWARNING: {len(weird)} look wrong (below 0m or above 2000m):")
    for r in weird[:10]:
        print("   ", r["municipality"], "-", r["barangay"], r["elevation_m"], "m")

# --- 4. save ------------------------------------------------------------
fields = ["municipality", "barangay", "district", "lat", "lon", "elevation_m"]
with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)

print(f"\nSaved {OUT_FILE}")

# --- 5. quick summary ---------------------------------------------------
vals = [r["elevation_m"] for r in rows if r.get("elevation_m") is not None]
if vals:
    print(f"Lowest:  {min(vals)} m")
    print(f"Highest: {max(vals)} m")
    print(f"Average: {sum(vals) / len(vals):.1f} m")