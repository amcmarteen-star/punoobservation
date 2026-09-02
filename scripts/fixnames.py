"""
Normalise barangay and municipality names.

RUN FROM PROJECT ROOT:
    python scripts/fix_names.py --dry-run     # show what would change
    python scripts/fix_names.py               # apply

WHAT IT FIXES
-------------
GADM writes names without spaces: "SanFelipeWest", "PoblacionII",
"SanAurelio1st". The DENR Excel writes them with spaces. Both end up in
the database, so dropdowns show a mix.

This is cosmetic - nothing is broken, because every lookup goes through
a normalising function that strips spaces. But the mix looks careless on
screen, and this will be on a projector at defense.

WHAT IT CHANGES
---------------
1. location.municipality      6 names
2. location.barangay          about 134 names
3. scripts/barangay_climate.csv
4. scripts/barangay_soil.csv

The CSVs matter. Without them, the next seed run recreates the old
names.

IT DOES NOT TOUCH barangay.geojson. The map matches through
normalizeName() in JavaScript, which strips spaces on both sides, so the
geojson can keep GADM's spelling safely.

SAFETY
------
Names are display values only. Every join in this project matches on
location_id, and every name lookup normalises first. Renaming cannot
orphan a site or a report.

Still, back up first:
    pg_dump -U postgres punoobservation > backup_before_names.sql
"""

import argparse
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Location

HERE = os.path.dirname(os.path.abspath(__file__))
CLIMATE = os.path.join(HERE, "barangay_climate.csv")
SOIL = os.path.join(HERE, "barangay_soil.csv")


# ======================================================================
# Splitting
# ======================================================================
#
# Four rules, applied in order. Order matters: the digit rule has to run
# before the case rules, or "SanAurelio1st" loses its split point.

def split_name(s):
    if not s:
        return s

    t = str(s)

    # 1. letter followed by a digit:  SanAurelio1st -> SanAurelio 1st
    t = re.sub(r'(?<=[a-zA-Z])(?=\d)', ' ', t)

    # 2. lowercase followed by uppercase:  SanAurelio -> San Aurelio
    t = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', t)

    # 3. uppercase run followed by a capitalised word:  ABCDef -> ABC Def
    #    keeps Roman numerals intact: PoblacionII stays "Poblacion II",
    #    not "Poblacion I I"
    t = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', t)

    # 4. full stop followed by a letter:  Dr.Pedro -> Dr. Pedro
    t = re.sub(r'(?<=\.)(?=[A-Za-z])', ' ', t)

    return re.sub(r'\s+', ' ', t).strip()


# Names the splitter cannot work out, and one real misspelling.
# Pozzorubio is how GADM writes it. The municipality is Pozorrubio.
OVERRIDES = {
    "Pozzorubio": "Pozorrubio",
}


def fix(name):
    if name in OVERRIDES:
        return OVERRIDES[name]
    return split_name(name)


# ======================================================================
# Database
# ======================================================================

def fix_database(dry_run):
    print("=== DATABASE ===")

    locations = Location.query.order_by(
        Location.municipality, Location.barangay
    ).all()

    muni_changes = {}
    brgy_changes = 0

    for loc in locations:
        new_muni = fix(loc.municipality)
        new_brgy = fix(loc.barangay)

        if new_muni != loc.municipality:
            muni_changes[loc.municipality] = new_muni
            if not dry_run:
                loc.municipality = new_muni

        if new_brgy != loc.barangay:
            brgy_changes += 1
            if dry_run and brgy_changes <= 25:
                print(f"  {loc.barangay:<26} -> {new_brgy}")
            if not dry_run:
                loc.barangay = new_brgy

    if dry_run and brgy_changes > 25:
        print(f"  ... and {brgy_changes - 25} more")

    print()
    print("  Municipalities:")
    for old, new in sorted(muni_changes.items()):
        print(f"    {old:<18} -> {new}")

    print()
    print(f"  Barangays to change : {brgy_changes}")
    print(f"  Rows total          : {len(locations)}")

    if not dry_run:
        db.session.commit()
        print("  Committed.")


# ======================================================================
# CSVs
# ======================================================================
#
# These feed the seed script. Leaving them unchanged means the next
# `python scripts/seed_reference_data.py` writes the old names back.

def fix_csv(path, dry_run):
    if not os.path.exists(path):
        print(f"  MISSING: {path}")
        return

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fields = reader.fieldnames
        rows = list(reader)

    changed = 0
    for r in rows:
        for col in ("municipality", "barangay"):
            if col in r:
                new = fix(r[col])
                if new != r[col]:
                    changed += 1
                    r[col] = new

    name = os.path.basename(path)
    print(f"  {name:<26} {changed} value(s) to change")

    if not dry_run and changed:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)


# ======================================================================
# Verification
# ======================================================================

def verify():
    print()
    print("=== CHECK ===")

    total = Location.query.count()
    no_elev = Location.query.filter(Location.elevation_m.is_(None)).count()

    print(f"  Locations              : {total}")
    print(f"  Missing characteristics: {no_elev}")

    # any remaining squashed names
    left = [
        loc.barangay for loc in Location.query.all()
        if re.search(r'[a-z][A-Z]', loc.barangay or '')
    ]
    print(f"  Still squashed         : {len(left)}")
    if left:
        print("   ", left[:10])

    print()
    print("  Municipalities now:")
    munis = [
        m[0] for m in
        db.session.query(Location.municipality).distinct()
        .order_by(Location.municipality).all()
    ]
    for m in munis:
        print(f"    {m}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="show changes without applying them")
    args = ap.parse_args()

    if args.dry_run:
        print("DRY RUN - nothing will be written")
        print()

    app = create_app()
    with app.app_context():
        fix_database(args.dry_run)
        print()
        print("=== CSV FILES ===")
        fix_csv(CLIMATE, args.dry_run)
        fix_csv(SOIL, args.dry_run)

        if not args.dry_run:
            verify()
        else:
            print()
            print("Run without --dry-run to apply.")