"""
Load barangay site characteristics and tree species into the database.

RUN FROM PROJECT ROOT:
    python scripts/seed_reference_data.py

FILES NEEDED (all in scripts/):
    barangay_climate.csv
    barangay_soil.csv
    Philippine_Tree_main_species_Database.xlsx

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
SPECIES = os.path.join(HERE, "Philippine_Tree_main_species_Database.xlsx")

REGION = "Region I"
PROVINCE = "Pangasinan"


# ======================================================================
# COASTAL EXPOSURE - derived, not entered by hand
# ======================================================================
#
# Derived from the BSWM soil series already joined to each barangay,
# plus elevation. No new data collection needed.
#
# BSWM contains three soil types that indicate coastal or tidal
# conditions:
#     Hydrosol       - tidal / mangrove soil
#     Beach sand     - foreshore
#     Dune land      - coastal dunes
#
# For the current study area every barangay returns 0. That is correct:
# no Hydrosol, no Beach sand, lowest barangay 16 m, roughly 22 km inland
# from Lingayen Gulf.
#
# If coverage is extended to Districts 1-4, this same rule returns 2 and
# 3 for coastal barangays with NO CHANGE to the code.

def derive_coastal_exposure(soil_desc, elevation_m):
    s = (soil_desc or "").lower()

    if "hydrosol" in s:
        return 3                       # tidal / intertidal
    if "beach sand" in s or "dune" in s:
        return 2                       # coastal foreshore
    if elevation_m is not None and elevation_m < 10:
        return 1                       # low-lying, possible salt spray
    return 0                           # inland


# ======================================================================
# SALINITY REQUIREMENT - read from the ICRAF descriptions
# ======================================================================
#
# Each value was taken from that species' own Soil Type text in the
# source file. The quoted phrase is the justification.
#
# Species not listed default to 0 (inland, no salt tolerance).

SALINITY = {
    # 3 = requires tidal saltwater
    "Bakawan Babae":  3,   # "Intertidal mud flats, daily tidal inundation"
    "Bakawan Lalake": 3,   # "Silty estuarine deposits, high salt accumulation"
    "Api-api":        3,   # "Frontline tidal zones"
    "Nypa":           3,   # "Estuarine muddy banks, brackish moving waters"

    # 2 = coastal specialist
    "Agoho":          2,   # "Coastal dune sands, highly saline matrices"
    "Bitaog":         2,   # "Pure beach sand, littoral rocks, ocean spray"

    # 1 = tolerates coastal conditions
    "Ipil":           1,   # "Coastal soils, coralline sands, highly salt tolerant"
    "Talisay":        1,   # "Sandy coastlines, high wind and soil salinity"
    "Apitong":        1,   # "well-drained sedimentary clays or coastal edges"
}


# ======================================================================
# SOIL TEXTURE MAPPING
# ======================================================================
#
# READ THIS BEFORE YOUR DEFENSE.
#
# The species Soil Type column is prose, not texture classes. Example:
# "Deep, well-drained volcanic, clay loam or sandy loam matrices."
# Some entries name no texture at all.
#
# The mapping below was written by hand from those descriptions.
#
# THIS IS AN INTERPRETATION, NOT A PUBLISHED FACT.
# Have an adviser or CENRO forester review it.
#
# The five textures present in the 478 barangays:
#     sandy loam (157), silt loam (139), clay loam (82),
#     sand (68), silty clay loam (32)

ALL_TEX = "sandy loam,silt loam,clay loam,sand,silty clay loam"
LOAMS = "sandy loam,silt loam,clay loam"
HEAVY = "clay loam,silty clay loam"
LIGHT = "sandy loam,sand"

SOIL_MAP = {
    # --- dipterocarps: deep well-drained clay or loam ridges ---
    "Yakal-yamban":       "clay loam,sandy loam",
    "Yakal-gisok":        HEAVY,
    "Yakal-saplungan":    "clay loam",
    "Guijo":              HEAVY,
    "Tangile":            LOAMS,
    "Red Lauan":          "clay loam,sandy loam",
    "White Lauan":        LOAMS,
    "Almon":              "clay loam,sandy loam",
    "Bagtikan":           LOAMS,
    "Mayapis":            "clay loam,silt loam",
    "Apitong":            HEAVY,
    "Panau":              "clay loam,sandy loam",
    "Hagakhak":           "silt loam,clay loam",
    "Manggachapui":       "clay loam,sandy loam",
    "Narig":              "sandy loam,clay loam",
    "Palosapis":          HEAVY,
    "Dalingdingan":       "clay loam,sandy loam",

    # --- premium hardwoods ---
    "Narra":              "sandy loam,clay loam",
    "Ipil":               LIGHT,
    "Molave":             "clay loam",
    "Kamagong":           "clay loam,silt loam",
    "Tindalo":            "clay loam,sandy loam",
    "Acle":               "sandy loam,clay loam",
    "Supa":               "clay loam",
    "Mangkono":           "clay loam,sandy loam",
    "Lanete":             "sandy loam,clay loam",
    "Amugis":             "clay loam,sandy loam",
    "Toog":               "clay loam,silt loam",

    # --- conifers and montane ---
    "Almaciga":           "sandy loam,clay loam",
    "Benguet Pine":       LIGHT,
    "Mindoro Pine":       LIGHT,
    "Agoho del Monte":    LIGHT,
    "Alnus":              "sand,sandy loam",

    # --- coastal ---
    "Agoho":              "sand",
    "Bitaog":             "sand",
    "Bakawan Babae":      "silt loam,silty clay loam",
    "Bakawan Lalake":     "silt loam,silty clay loam",
    "Api-api":            "silt loam,silty clay loam",
    "Nypa":               "silt loam,silty clay loam",
    "Talisay":            "sand,sandy loam",

    # --- fruit and agroforestry ---
    "Pili":               "clay loam,sandy loam",
    "Mangga":             "sandy loam,silt loam,clay loam",
    "Lanka":              LOAMS,
    "Santol":             LOAMS,
    "Duhat":              "silt loam,clay loam,sandy loam",
    "Guyabano":           "sandy loam,clay loam,silty clay loam",
    "Atis":               "sandy loam,sand,silt loam",
    "Bignai":             ALL_TEX,
    "Kasuy":              LIGHT,
    "Banaba":             "silt loam,clay loam",
    "Katmon":             "clay loam,silt loam",

    # --- plantation and utility ---
    "Ilang-ilang":        "silt loam,clay loam",
    "Lumbang":            LOAMS,
    "Mahogany":           HEAVY,
    "Gmelina":            "sandy loam,silt loam",
    "Bagras":             "sandy loam,silt loam",
    "Rain Tree (Acacia)": ALL_TEX,
    "Kakawate":           ALL_TEX,
}


# ======================================================================
# Parsing helpers
# ======================================================================

def parse_range(text):
    """
    '0 - 800 m'       -> (0.0, 800.0)
    '22 - 32 deg C'   -> (22.0, 32.0)
    'From sea level'  -> (0.0, None)

    En-dashes normalised first; the source mixes them with hyphens.
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


TEXTURES = [
    "silty clay loam", "fine sandy loam", "sandy clay loam",
    "loamy sand", "sandy loam", "silt loam", "clay loam",
    "silty clay", "sandy clay", "clay", "loam", "sand", "silt",
]


def extract_texture(soil_desc):
    """
    'San Manuel fine sandy loam' -> 'sandy loam'
    'Pangasinan river sand'      -> 'sand'

    Leading words are the soil SERIES, a place name. Species tolerances
    describe TEXTURE. Longest patterns tested first so 'silty clay loam'
    is not truncated to 'clay loam'.
    """
    if not soil_desc:
        return None
    s = str(soil_desc).lower()
    for t in TEXTURES:
        if t in s:
            return "sandy loam" if t == "fine sandy loam" else t
    return None


def norm(s):
    """Lowercase, expand Sta./Sto., strip spaces, dots, dashes."""
    s = str(s).lower()
    s = s.replace("sta.", "santa").replace("sto.", "santo")
    return re.sub(r"[\s.\-]", "", s)


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

        soil_desc = s.get("soil_desc") if s else None
        if s:
            loc.soil_type = soil_desc
            loc.soil_texture = extract_texture(soil_desc)
            loc.agro_ecological_zone = s.get("aez")

        loc.coastal_exposure = derive_coastal_exposure(
            soil_desc, loc.elevation_m
        )

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
        # every species starts inactive; only ones in this file get reactivated
    TreeSpecie.query.update({TreeSpecie.is_reference: False})
    db.session.commit()
    print("  deactivated all species, reloading from file")

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

        sp.salinity_requirement = SALINITY.get(name, 0)

        sp.source = None if pd.isna(r["src"]) else str(r["src"]).strip()
        sp.is_reference = True

    db.session.commit()
    print(f"  added   : {added}")
    print(f"  updated : {updated}")
    if unmapped:
        print(f"  WARNING : {unmapped} species have no soil mapping")


LABELS = {0: "inland", 1: "low-lying", 2: "coastal", 3: "tidal"}


def report():
    print()
    print("=" * 72)
    print("CHECK THESE NUMBERS")
    print("=" * 72)

    total = Location.query.count()
    with_elev = Location.query.filter(Location.elevation_m.isnot(None)).count()
    with_soil = Location.query.filter(Location.soil_texture.isnot(None)).count()

    print(f"Locations           : {total}")
    print(f"  with elevation    : {with_elev}")
    print(f"  with soil texture : {with_soil}")

    print()
    print("Coastal exposure across barangays:")
    rows = (
        db.session.query(Location.coastal_exposure, db.func.count())
        .group_by(Location.coastal_exposure)
        .all()
    )
    for val, n in sorted(rows, key=lambda x: (x[0] is None, x[0])):
        print(f"  {val} ({LABELS.get(val, 'unset')}){'':<10} {n}")
    print("  All 0 is expected. Districts 5 and 6 are inland.")

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
    print("Species by salinity requirement:")
    for level in (3, 2, 1, 0):
        names = [
            sp.specie_name for sp in
            TreeSpecie.query.filter_by(
                is_reference=True, salinity_requirement=level
            ).order_by(TreeSpecie.specie_name).all()
        ]
        print(f"  {level} ({LABELS.get(level)}) : {len(names)} species")
        if level > 0:
            for n in names:
                print(f"        {n}")

    print()
    print(f"{'SPECIES':<22}{'ELEV':<14}{'TEMP':<12}{'RAIN':<16}{'SAL':<5}SOIL")
    for sp in TreeSpecie.query.filter_by(is_reference=True).order_by(
        TreeSpecie.specie_name
    ).all():
        print(
            f"{sp.specie_name:<22}"
            f"{_r(sp.min_elevation_m, sp.max_elevation_m):<14}"
            f"{_r(sp.min_temp_c, sp.max_temp_c):<12}"
            f"{_r(sp.min_rainfall_mm, sp.max_rainfall_mm):<16}"
            f"{sp.salinity_requirement if sp.salinity_requirement is not None else '-':<5}"
            f"{sp.preferred_soil}"
        )

    print()
    gaps = []
    for sp in TreeSpecie.query.filter_by(is_reference=True).all():
        missing = []
        if sp.min_elevation_m is None or sp.max_elevation_m is None:
            missing.append("elevation")
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
            print(f"  {name:<22} missing: {', '.join(missing)}")
    else:
        print("All species have complete tolerance data.")

    print()
    print("REMINDER: SOIL_MAP and SALINITY in this script interpret the")
    print("ICRAF prose descriptions. Have an adviser or CENRO forester")
    print("review both tables before defense.")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed_barangays()
        seed_species()
        report()