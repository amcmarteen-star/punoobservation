"""
Draw an approximate area for every reforestation site that has no
position of its own, for the GIS map.

RUN FROM PROJECT ROOT:
    python -m scripts.tools.make_synthetic_areas --dry-run   # show, save nothing
    python -m scripts.tools.make_synthetic_areas             # save
    python -m scripts.tools.make_synthetic_areas --site 12 --site 15
    python -m scripts.tools.make_synthetic_areas --seed 7

WHAT IT DOES
- A site with a published GPS boundary, or made from a request with the
  requester's pin or drawn area: nothing to draw, the map already places
  it. Those shapes are kept clear of, so no area lands on them.
- Every other site in Eastern Pangasinan: an irregular area of the site's
  hectares inside its barangay, clear of the barangay's edge and of every
  other site. Two sites never overlap. See app/services/synthetic_areas.py
  for the rules and what eases when a barangay is crowded.
- Saves them in synthetic_site_area. Re-running replaces the areas of the
  sites it processes, and nothing else. A site that is skipped, or now
  has a position of its own, loses any area it had.
- With --site, the other sites' areas stay where they are and the new
  area avoids them.
- Never writes to site, location or the monitoring tables.
- Checks every area against its barangay, the Eastern Pangasinan outline
  and every other site in the barangay before saving, then reads them
  back and checks again. Exit status 1 if any area fails; nothing is
  saved then.

The areas' positions and outlines are made up. They are for the map only,
never for a location, an area check or a report.
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
import json
import sys
from collections import defaultdict

from app.extensions import db
from app.models import Site, SyntheticSiteArea
from app.services.request_site import site_position
from app.services.synthetic_areas import (
    AREA_CENRO, AREA_NAME, DEFAULT_SEED, area_outline, area_problems,
    barangay_index, place_areas,
)
from app.utils.jurisdiction import cenro_for_municipality, place_key
from scripts.common import STATIC_DIR, app_context


def _polygon(text):
    """A stored GeoJSON Polygon as a dict, or None."""
    if not text:
        return None
    try:
        g = json.loads(text)
    except ValueError:
        return None
    return g if isinstance(g, dict) and g.get("type") == "Polygon" else None


def real_shape(site):
    """
    The shape a site already has on the map, which areas must keep clear
    of: its published boundary, else the requester's drawn area.
    """
    if site.boundary_published:
        g = _polygon(site.boundary_geojson)
        if g:
            return g
    if site.source_request is not None:
        return _polygon(site.source_request.boundary_geojson)
    return None


def run(site_ids=None, seed=DEFAULT_SEED, dry_run=False,
        static_dir=STATIC_DIR, out=print):
    """
    Place, check and (unless dry_run) save the areas. Needs an app
    context. Returns a summary dict.
    """
    outline = area_outline(static_dir)
    barangays = barangay_index(static_dir)

    q = Site.query.order_by(Site.site_id)
    if site_ids:
        q = q.filter(Site.site_id.in_(site_ids))
    sites = q.all()
    chosen = {s.site_id for s in sites}

    skipped, positioned, failures = [], [], []
    groups = defaultdict(list)        # barangay key -> [site, ...]

    for site in sites:
        loc = site.location
        label = f"#{site.site_id} {site.site_name}"
        if loc is None:
            skipped.append((label, "no barangay recorded"))
            continue
        where = f"{loc.barangay}, {loc.municipality}"
        if cenro_for_municipality(loc.municipality) != AREA_CENRO:
            skipped.append((label, f"{where} is outside {AREA_NAME}"))
            continue
        position = site_position(site)
        if position is not None:
            positioned.append((label, position[2]))
            continue
        if not site.area_size_ha or site.area_size_ha <= 0:
            skipped.append((label, "no hectare figure (area is 0)"))
            continue
        key = place_key(loc.municipality, loc.barangay)
        if key not in barangays:
            skipped.append((label, f"no barangay outline matches {where}"))
            continue
        groups[key].append(site)

    made = {}             # site_id -> result
    processed = []
    group_shapes = {}     # barangay key -> (geometry, [every shape in it])
    for key, group in groups.items():
        barangay = barangays[key]

        # every shape already in the barangay that this run leaves alone:
        # real boundaries and proposed areas of any site, and the stored
        # areas of sites not being redrawn
        obstacles = []
        for other in Site.query.filter(
                Site.location_id == group[0].location_id).all():
            g = real_shape(other)
            if g is None and other.site_id not in chosen \
                    and other.synthetic_area is not None:
                g = _polygon(other.synthetic_area.geometry_geojson)
            if g is not None:
                obstacles.append(g)

        results = place_areas(
            barangay, [(s.site_id, s.area_size_ha) for s in group],
            seed, outline, obstacles)

        shapes = list(obstacles)
        for site in group:
            label = f"#{site.site_id} {site.site_name}"
            where = f"{site.location.barangay}, {site.location.municipality}"
            r = results.get(site.site_id)
            if r is None:
                skipped.append((label, f"no room for even a small area in {where}"))
                continue
            made[site.site_id] = r
            shapes.append(r["geojson"])
            processed.append({
                "site_id": site.site_id, "label": label, "where": where,
                "key": key, "ha": site.area_size_ha, "drawn": r["area_ha"],
                "note": "; ".join(r["eased"]),
            })
        group_shapes[key] = (barangay, shapes)

    # --- check every new area: inside, and touching no other site --------
    for p in processed:
        barangay, shapes = group_shapes[p["key"]]
        mine = made[p["site_id"]]["geojson"]
        problems = area_problems(mine, barangay, outline,
                                 [s for s in shapes if s is not mine])
        if problems:
            failures.append((p["label"], "; ".join(problems)))

    # --- save: replace only the chosen sites' areas ---------------------
    saved = False
    if not dry_run and not failures:
        if chosen:
            SyntheticSiteArea.query.filter(
                SyntheticSiteArea.site_id.in_(chosen)
            ).delete(synchronize_session=False)
        for site_id, r in made.items():
            db.session.add(SyntheticSiteArea(
                site_id=site_id,
                geometry_geojson=json.dumps(r["geojson"]),
                area_ha=r["area_ha"],
                placement_note=("; ".join(r["eased"]) or None),
                is_synthetic=True, seed=seed,
            ))
        db.session.commit()
        saved = True

        # --- read back and check what was stored ---
        for p in processed:
            barangay, shapes = group_shapes[p["key"]]
            row = SyntheticSiteArea.query.filter_by(site_id=p["site_id"]).first()
            if row is None:
                failures.append((f"{p['label']} (stored)", "not saved"))
                continue
            stored = json.loads(row.geometry_geojson)
            mine = made[p["site_id"]]["geojson"]
            problems = area_problems(stored, barangay, outline,
                                     [s for s in shapes if s is not mine])
            if problems:
                failures.append((f"{p['label']} (stored)", "; ".join(problems)))

    summary = {
        "processed": processed, "positioned": positioned, "skipped": skipped,
        "failures": failures, "saved": saved,
    }
    _print_summary(summary, seed, dry_run, out)
    return summary


def _print_summary(s, seed, dry_run, out):
    out("")
    out(f"{'SITE':<44}{'HA':>8}{'DRAWN':>8}  {'BARANGAY':<28}NOTE")
    for p in s["processed"]:
        out(f"{p['label'][:43]:<44}{p['ha']:>8.2f}{p['drawn']:>8.2f}  "
            f"{p['where'][:27]:<28}{p['note']}")

    eased = [p for p in s["processed"] if p["note"]]
    shrunk = [p for p in s["processed"] if "shrunk" in p["note"]]
    out("")
    out(f"Seed                          : {seed}")
    out(f"Approximate areas drawn       : {len(s['processed'])}")
    out(f"Already placed on the map     : {len(s['positioned'])}")
    for label, how in s["positioned"]:
        out(f"    {label}: {how}")
    out(f"Placed with eased rules       : {len(eased)}")
    if shrunk:
        out(f"Smaller than the site's area  : {len(shrunk)} (the barangay is too full or too small)")
        for p in shrunk:
            out(f"    {p['label']}: {p['drawn']:.2f} of {p['ha']:.2f} ha")
    out(f"Sites skipped                 : {len(s['skipped'])}")
    for label, reason in s["skipped"]:
        out(f"    {label}: {reason}")

    out("")
    if s["failures"]:
        out("CHECK FAILED:")
        for label, why in s["failures"]:
            out(f"    {label}: {why}")
    else:
        out(f"Check passed: every area is wholly inside its barangay and "
            f"{AREA_NAME}, and no two sites overlap.")
    if dry_run:
        out("Dry run. Nothing was saved.")
    elif s["saved"]:
        out("Saved." + (" Fix the failures above and run again."
                        if s["failures"] else ""))
    else:
        out("Nothing was saved.")


def main():
    ap = argparse.ArgumentParser(
        description="Draw approximate areas for sites with no position.")
    ap.add_argument("--dry-run", action="store_true",
                    help="place and check the areas, save nothing")
    ap.add_argument("--site", type=int, action="append", dest="sites",
                    help="only this site id (repeat for several)")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED,
                    help=f"random seed (default {DEFAULT_SEED})")
    args = ap.parse_args()

    with app_context():
        summary = run(site_ids=args.sites, seed=args.seed,
                      dry_run=args.dry_run)
    sys.exit(1 if summary["failures"] else 0)


if __name__ == "__main__":
    main()
