"""
Tag tree species with CENRO use categories, from a CSV filled in by hand.

RUN FROM PROJECT ROOT:
    python -m scripts.tools.load_species_categories
    python -m scripts.tools.load_species_categories --csv path/to/other.csv

THE CSV (scripts/data/source/species_categories.csv):
    scientific_name,category
    Pterocarpus indicus,Timber
    Pterocarpus indicus,Agroforestry     <- a second category is a second row
    Gmelina arborea,                     <- empty category: skipped

RULES
- A row with an empty category is skipped.
- A category not in SPECIES_CATEGORIES (app/services/recommender.py) is
  rejected and printed. Add a new category there first.
- A scientific_name not in the species table is rejected and printed.
- A pair already in the table is skipped, so running it twice is safe.
- Names match ignoring case and spaces at the ends. A scientific name held
  by more than one species (an older copy and the reference one) tags all
  of them, so the tag holds whichever row the recommender scores.
- Valid rows are saved even when other rows are rejected. The script
  exits with status 1 if anything was rejected.
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
import sys

from app.extensions import db
from app.models import SpeciesCategory, TreeSpecie
from app.services.recommender import SPECIES_CATEGORIES
from scripts.common import SPECIES_CATEGORIES_CSV, app_context


def key(name):
    return (name or "").strip().lower()


def load(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))

    species_by_name = {}
    for sp in TreeSpecie.query.all():
        if sp.scientific_name:
            species_by_name.setdefault(key(sp.scientific_name), []).append(sp)

    existing = {(sc.species_id, sc.category)
                for sc in SpeciesCategory.query.all()}

    added = skipped = empty = 0
    errors = []

    # header is line 1, so the first data row is line 2
    for line, row in enumerate(rows, start=2):
        name = (row.get("scientific_name") or "").strip()
        category = (row.get("category") or "").strip()

        if not category:
            empty += 1
            continue
        if category not in SPECIES_CATEGORIES:
            errors.append(f"line {line}: unknown category '{category}' "
                          f"for '{name}' (allowed: "
                          f"{', '.join(SPECIES_CATEGORIES)})")
            continue
        matches = species_by_name.get(key(name))
        if not matches:
            errors.append(f"line {line}: no species with scientific name "
                          f"'{name}'")
            continue

        for sp in matches:
            if (sp.tree_id, category) in existing:
                skipped += 1
                continue
            db.session.add(SpeciesCategory(species_id=sp.tree_id,
                                           category=category))
            existing.add((sp.tree_id, category))
            added += 1

    db.session.commit()

    for e in errors:
        print("REJECTED", e)
    print()
    for label, n in (("Rows read", len(rows)), ("Added", added),
                     ("Skipped (existing)", skipped),
                     ("Skipped (no category)", empty),
                     ("Errors", len(errors))):
        print(f"{label:<22}: {n}")
    return len(errors)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=SPECIES_CATEGORIES_CSV,
                    help="CSV to read (default: %(default)s)")
    args = ap.parse_args()

    with app_context():
        failed = load(args.csv)
    sys.exit(1 if failed else 0)
