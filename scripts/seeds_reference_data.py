"""
Load barangay site characteristics and tree species into the database.

RUN FROM PROJECT ROOT:
    python scripts/seed_reference_data.py

FILES NEEDED (all in scripts/):
    barangay_climate.csv
    barangay_soil.csv
    Urdaneta_All_Species_Biophysical_Limits.xlsx

SAFE TO RE-RUN. Updates existing rows instead of duplicating.
"""

import csv
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Location, TreeSpecie

HERE = os.path.dirname(os.path.abspath(__file__))
CLIMATE = os.path.join(HERE, "barangay_climate.csv")
SOIL = os.path.join(HERE, "barangay_soil.csv")
SPECIES = os.path.join(HERE, "Urdaneta_All_Species_Biophysical_Limits.xlsx")

REGION = "Region I"
PROVINCE = "Pangasinan"


# ======================================================================
# SOIL TEXTURE MAPPING
# ======================================================================
#
# READ THIS BEFORE YOUR DEFENSE.
#
# The ICRAF soil column is written as prose, not as texture classes.
# Example: "Grows in most soils but prefers well-drained deep alluvial
# soil." That sentence contains no texture name at all.
#
# Automatic keyword extraction fails on 8 of the 19 species. So the
# mapping below was written by hand, interpreting each description into
# the texture classes that actually occur in your study area.
#
# THIS IS AN INTERPRETATION, NOT A PUBLISHED FACT.
#
# Have your adviser or a CENRO forester review this table. If a panel
# member asks where these came from, the honest answer is that they were
# derived from the ICRAF descriptions by the proponents, and reviewed by
# an expert. Say that. Do not present them as published values.
#
# The five textures present in your 478 barangays:
#     sandy loam (157), silt loam (139), clay loam (82),
#     sand (68), silty clay loam (32)
#
# GENERALIST means the description explicitly says the species tolerates
# a wide range of soils. Those get all five textures.

ALL_TEXTURES = "sandy loam,silt loam,clay loam,sand,silty clay loam"

SOIL_MAP = {
    # explicit texture named in the source
    "Narra":                 "sandy loam,clay loam",
    "Eucalyptus":            "silt loam,clay loam",
    "Guyabano (Soursop)":    "sandy loam,clay loam,silty clay loam",
    "Batino":                "clay loam",

    # "loam" stated, no qualifier
    "Duhat (Java Plum)":     "silt loam,clay loam,sandy loam",
    "Coffee":                "silt loam,clay loam",
    "Ilang-ilang":           "silt loam,clay loam",

    # "alluvial, well-drained" -> lighter textures
    "Gmelina (Yemane)":      "sandy loam,silt loam",
    "Calumpit":              "silt loam,sandy loam,clay loam",
    "Alnus":                 "sand,sandy loam",

    # "heavy" or "clay" stated -> heavier textures
    "Mahogany":              "clay loam,silty clay loam",
    "Bayog (Bamboo)":        "clay loam,silty clay loam,silt loam",
    "Palosapis":             "clay loam,silty clay loam",

    # limestone-derived soils are typically clay loams
    "Molave":                "clay loam",

    # "well-drained rocky / drought resistant" -> lighter textures
    "Benguet Pine (B.Pine)": "sandy loam,sand",
    "Atis (Sugar Apple)":    "sandy loam,sand,silt loam",

    # source explicitly says wide range of soils
    "Tamarind (Sampalok)":   ALL_TEXTURES,
    "Rain tree (Acacia)":    ALL_TEXTURES,
    "Bignai":                ALL_TEXTURES,
}


# ======================================================================
# Parsing the ICRAF text ranges
# ======================================================================

def parse_range(text):
    """
    '0-1500 m'         -> (0.0, 1500.0)
    '24-27 deg C.'     -> (24.0, 27.0)
    '900 to 2200 mm'   -> (900.0, 2200.0)
    'From sea level'   -> (0.0, None)     no published ceiling

    En-dashes and em-dashes are normalised to hyphens first, because the
    source file uses them inconsistently.
    """
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return None, None

    s = str(text).replace("\u2013", "-").replace("\u2014", "-").strip()

    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", s)
    if m:
        return float(m.group(1)), float(m.group(2))

    m = re.search(r"(\d+(?:\.\d+)?)\s*to\s*(\d+(?:\.\d+)?)", s, re.I)
    if m:
        return float(m.group(1)), float(m.group(2))

    if "sea level" in s.lower():
        return 0.0, None

    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if m:
        return float(m.group(1)), None

    return None, None


# ======================================================================
# Barangay soil texture
# ======================================================================

TEXTURES = [
    "silty clay loam", "fine sandy loam", "sandy clay loam",
    "loamy sand", "sandy loam", "silt loam", "clay loam",
    "silty clay", "sandy clay", "clay", "loam", "sand", "silt",
]


def extract_texture(soil_desc):
    """
    'San Manuel fine sandy loam' -> 'sandy loam'
    'Pangasinan river sand'      -> 'sand'

    The leading words are the soil SERIES, which is a place name.
    Species tolerances describe TEXTURE. Only texture can be matched.
    Longest patterns are tested first so 'silty clay loam' is not
    truncated to 'clay loam'.
    """
    if not soil_desc:
        return None
    s = str(soil_desc).lower()
    for t in TEXTURES:
        if t in s:
            return "sandy loam" if t == "fine sandy loam" else t
    return None


def norm(s):
    s = str(s).lower()
    s = s.replace("sta.", "santa").replace("sto.", "santo")
    return re.sub(r"[\s.\-]", "", s)


# ======================================================================
# Seeding
# ======================================================================

def seed_barangays():
    print("--- Barangay characteristics ---")

    for path in (CLIMATE, SOIL):
        if not os.path.exists(path):
            print("MISSING FILE:", path)
            return

    with open(CLIMATE, newline="", encoding="utf-8") as fh:
        climate = list(csv.DictReader(fh))

    with open(SOIL, newline="", encoding="utf-8") as fh:
        soil = {
            (norm(r["municipality"]), norm(r["barangay"])): r
            for r in csv.DictReader(fh)
        }

    existing = {}
    for loc in Location.query.all():
        existing[(norm(loc.municipality), norm(loc.barangay))] = loc

    updated = created = no_soil = 0

    for row in climate:
        key = (norm(row["municipality"]), norm(row["barangay"]))
        s = soil.get(key)
        if s is None:
            no_soil += 1

        loc = existing.get(key)
        if loc is None:
            loc = Location(
                region=REGION,
                province=PROVINCE,
                municipality=row["municipality"],
                barangay=row["barangay"],
            )
            db.session.add(loc)
            existing[key] = loc
            created += 1
        else:
            updated += 1

        loc.latitude = _f(row.get("lat"))
        loc.longitude = _f(row.get("lon"))
        loc.elevation_m = _f(row.get("elevation_m"))
        loc.avg_temp_c = _f(row.get("avg_temp_c"))
        loc.annual_rainfall_mm = _f(row.get("annual_rainfall_mm"))

        if s:
            loc.soil_type = s.get("soil_desc")
            loc.soil_texture = extract_texture(s.get("soil_desc"))
            loc.agro_ecological_zone = s.get("aez")

    db.session.commit()
    print(f"  updated : {updated}")
    print(f"  created : {created}")
    if no_soil:
        print(f"  WARNING : {no_soil} barangays had no soil match")


def seed_species():
    print("--- Tree species ---")

    if not os.path.exists(SPECIES):
        print("MISSING FILE:", SPECIES)
        return

    df = pd.read_excel(SPECIES, header=0)
    df.columns = ["name", "sci", "alt", "temp", "rain", "soil", "src"]

    added = updated = unmapped = 0

    for _, r in df.iterrows():
        name = str(r["name"]).strip()
        if not name or name.lower() == "nan":
            continue

        sp = TreeSpecie.query.filter(
            db.func.lower(TreeSpecie.specie_name) == name.lower()
        ).first()

        if sp is None:
            sp = TreeSpecie(specie_name=name)
            db.session.add(sp)
            added += 1
        else:
            updated += 1

        a_lo, a_hi = parse_range(r["alt"])
        t_lo, t_hi = parse_range(r["temp"])
        p_lo, p_hi = parse_range(r["rain"])

        sp.scientific_name = (
            None if pd.isna(r["sci"]) else str(r["sci"]).strip()
        )
        sp.min_elevation_m = a_lo
        sp.max_elevation_m = a_hi
        sp.min_temp_c = t_lo
        sp.max_temp_c = t_hi
        sp.min_rainfall_mm = p_lo
        sp.max_rainfall_mm = p_hi

        mapped = SOIL_MAP.get(name)
        if mapped is None:
            unmapped += 1
            print(f"  NO SOIL MAPPING for '{name}' - add it to SOIL_MAP")
        sp.preferred_soil = mapped

        sp.source = (
            None if pd.isna(r["src"]) else str(r["src"]).strip()
        )
        sp.is_reference = True

    db.session.commit()
    print(f"  added   : {added}")
    print(f"  updated : {updated}")
    if unmapped:
        print(f"  WARNING : {unmapped} species have no soil mapping")


def report():
    print()
    print("=" * 66)
    print("CHECK THESE NUMBERS")
    print("=" * 66)

    total = Location.query.count()
    with_elev = Location.query.filter(Location.elevation_m.isnot(None)).count()
    with_soil = Location.query.filter(Location.soil_texture.isnot(None)).count()

    print(f"Locations           : {total}")
    print(f"  with elevation    : {with_elev}")
    print(f"  with soil texture : {with_soil}")

    print()
    print("Barangay soil textures:")
    rows = (
        db.session.query(Location.soil_texture, db.func.count())
        .filter(Location.soil_texture.isnot(None))
        .group_by(Location.soil_texture)
        .all()
    )
    for tex, n in sorted(rows, key=lambda x: -x[1]):
        print(f"  {tex:<20} {n}")

    print()
    print("Species loaded:")
    print(f"  {'NAME':<24}{'ELEV':<14}{'TEMP':<12}{'RAIN':<16}SOIL")
    for sp in TreeSpecie.query.filter_by(is_reference=True).order_by(
        TreeSpecie.specie_name
    ).all():
        print(
            f"  {sp.specie_name:<24}"
            f"{_r(sp.min_elevation_m, sp.max_elevation_m):<14}"
            f"{_r(sp.min_temp_c, sp.max_temp_c):<12}"
            f"{_r(sp.min_rainfall_mm, sp.max_rainfall_mm):<16}"
            f"{sp.preferred_soil}"
        )

    # incomplete data warning
    print()
    gaps = []
    for sp in TreeSpecie.query.filter_by(is_reference=True).all():
        missing = []
        if sp.max_elevation_m is None:
            missing.append("max elevation")
        if sp.min_temp_c is None or sp.max_temp_c is None:
            missing.append("temperature")
        if sp.min_rainfall_mm is None or sp.max_rainfall_mm is None:
            missing.append("rainfall")
        if not sp.preferred_soil:
            missing.append("soil")
        if missing:
            gaps.append((sp.specie_name, missing))

    if gaps:
        print("INCOMPLETE SPECIES DATA:")
        for name, missing in gaps:
            print(f"  {name:<24} missing: {', '.join(missing)}")
        print()
        print("  These are scored on fewer features than the others.")
        print("  Record this in your limitations section.")
    else:
        print("All species have complete tolerance data.")

    print()
    print("REMINDER: the SOIL_MAP table in this script is an")
    print("interpretation of the ICRAF prose descriptions, made by the")
    print("proponents. Have an adviser or CENRO forester review it")
    print("before defense.")


def _f(v):
    if v is None or v == "":
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _r(lo, hi):
    a = "?" if lo is None else f"{lo:g}"
    b = "?" if hi is None else f"{hi:g}"
    return f"{a}-{b}"


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed_barangays()
        seed_species()
        report()