"""
Fetch temperature and rainfall for all 478 barangays.

SAFE TO RE-RUN. If it stops, just run it again.
It saves progress after every barangay and skips ones already done.

WHAT IT NEEDS:
  - barangay_elevation.csv   (same folder)

WHAT IT MAKES:
  - barangay_climate.csv     (written as it goes, not at the end)

HOW TO RUN:
  cd scripts
  python get_climate.py

Source: ERA5 reanalysis via Open-Meteo Archive API. CC BY 4.0.
Takes about 40 minutes. Leave it running.
"""

import csv
import os
import time
import requests
from statistics import mean

HERE = os.path.dirname(os.path.abspath(__file__))
IN_FILE = os.path.join(HERE, "barangay_elevation.csv")
OUT_FILE = os.path.join(HERE, "barangay_climate.csv")

START = "2014-01-01"
END = "2023-12-31"

PAUSE = 12          # seconds between calls. Raise to 10 if 429s keep happening.
FIELDS = ["municipality", "barangay", "district", "lat", "lon",
          "elevation_m", "avg_temp_c", "annual_rainfall_mm"]


# --- 1. load the input --------------------------------------------------
with open(IN_FILE, newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

# --- 2. load anything already finished ---------------------------------
done = {}
if os.path.exists(OUT_FILE):
    with open(OUT_FILE, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("avg_temp_c"):
                done[(r["municipality"], r["barangay"])] = r

print(f"Total barangays : {len(rows)}")
print(f"Already done    : {len(done)}")
print(f"Remaining       : {len(rows) - len(done)}")
print()


def save():
    """Write everything finished so far. Called after every success."""
    out = []
    for r in rows:
        key = (r["municipality"], r["barangay"])
        out.append(done.get(key, r))
    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)


def fetch(lat, lon):
    """One API call, with backoff if rate limited."""
    wait = 30
    for attempt in range(6):
        resp = requests.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params={
                "latitude": lat,
                "longitude": lon,
                "start_date": START,
                "end_date": END,
                "daily": "temperature_2m_mean,precipitation_sum",
                "timezone": "Asia/Manila",
            },
            timeout=90,
        )

        if resp.status_code == 429:
            print(f"    rate limited, waiting {wait}s "
                  f"(attempt {attempt + 1} of 6)")
            time.sleep(wait)
            wait = min(wait * 2, 600)      # 30, 60, 120, 240, 480, 600
            continue

        resp.raise_for_status()
        return resp.json()["daily"]

    raise SystemExit(
        "Still rate limited after 6 tries.\n"
        "Progress is saved. Wait an hour, then run this script again."
    )


# --- 3. main loop -------------------------------------------------------
for i, r in enumerate(rows, start=1):
    key = (r["municipality"], r["barangay"])

    if key in done:
        continue

    try:
        d = fetch(r["lat"], r["lon"])
    except KeyboardInterrupt:
        save()
        print("\nStopped. Progress saved. Run again to continue.")
        raise
    except Exception as e:
        save()
        print(f"\nFAILED at row {i} ({r['barangay']}): {e}")
        print("Progress saved. Run the script again to continue.")
        raise

    # TEMPERATURE = mean of all daily mean values
    temps = [t for t in d["temperature_2m_mean"] if t is not None]
    r["avg_temp_c"] = round(mean(temps), 2)

    # RAINFALL = sum each year, then average the yearly totals
    yearly = {}
    for date, mm in zip(d["time"], d["precipitation_sum"]):
        if mm is None:
            continue
        yearly[date[:4]] = yearly.get(date[:4], 0) + mm
    r["annual_rainfall_mm"] = round(mean(yearly.values()), 1)

    done[key] = dict(r)
    save()

    print(f"{i}/{len(rows)}  {r['municipality']:<14} {r['barangay']:<20} "
          f"{r['avg_temp_c']}degC  {r['annual_rainfall_mm']}mm")

    time.sleep(PAUSE)


save()
print()
print(f"Saved {OUT_FILE}")

# --- 4. sanity check ----------------------------------------------------
temps = [float(v["avg_temp_c"]) for v in done.values()]
rains = [float(v["annual_rainfall_mm"]) for v in done.values()]

print()
print("=== CHECK THESE NUMBERS ===")
print(f"Temperature : {min(temps)} to {max(temps)} degC  "
      f"(average {mean(temps):.1f})")
print(f"Rainfall    : {min(rains)} to {max(rains)} mm  "
      f"(average {mean(rains):.0f})")
print()

if mean(temps) > 29:
    print("WARNING: average above 29 degC. Lowland Pangasinan should be 26-28.")
else:
    print("Temperature looks right (expect 26-28 degC).")

if mean(rains) < 1000 or mean(rains) > 4000:
    print("WARNING: rainfall outside expected 1800-2500 mm range.")
else:
    print("Rainfall looks right (expect 1800-2500 mm).")