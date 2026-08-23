"""
Tree species recommendation engine.

Method: cosine similarity, as specified in the capstone paper.

PIPELINE (matches the paper, Chapter 2, page 19):
    1. Accept environmental site conditions as input
    2. Encode categorical variables into numerical representations
    3. Normalize feature values to a common scale
    4. Compute cosine similarity between the site vector and each
       reference profile vector
    5. Rank in descending order of similarity

PUT THIS FILE AT:
    app/services/recommender.py

You will need an empty file at:
    app/services/__init__.py

NOTE ON THE REFERENCE DATASET
-----------------------------
The paper specifies comparison against historical site profiles.
Those records do not exist in usable form: the available DENR data
covers 20 barangays, and species selection in it is determined by
program component rather than site conditions.

This implementation therefore builds reference profiles from published
species ecological tolerances instead. The mathematics is unchanged.
Only the source of the reference vectors differs.
"""

import math

from app.extensions import db
from app.models import Location, TreeSpecie


# ----------------------------------------------------------------------
# Step 2 — categorical encoding
# ----------------------------------------------------------------------
#
# Soil texture is a category. Cosine similarity needs numbers.
#
# We use ORDINAL encoding along the coarse-to-fine particle size scale,
# which is how soil texture is physically ordered:
#
#     sand  ->  loamy sand  ->  sandy loam  ->  loam  ->  silt loam
#           ->  clay loam  ->  silty clay loam  ->  clay
#
# Textures that sit close on this scale behave similarly for drainage
# and water retention, so a numeric scale is defensible here.
#
# STATE THIS IN YOUR PAPER. A panel will ask why these numbers.

SOIL_ENCODING = {
    "sand": 1,
    "loamy sand": 2,
    "sandy loam": 3,
    "loam": 4,
    "silt": 4,
    "silt loam": 5,
    "sandy clay loam": 5,
    "clay loam": 6,
    "silty clay loam": 7,
    "sandy clay": 7,
    "silty clay": 8,
    "clay": 8,
}

SOIL_MIN = 1
SOIL_MAX = 8

FEATURES = ["rainfall", "elevation", "temperature", "soil"]


def encode_soil(texture):
    """Soil texture string -> number. Returns None if unknown."""
    if not texture:
        return None
    return SOIL_ENCODING.get(str(texture).strip().lower())


# ----------------------------------------------------------------------
# Step 3 — normalization
# ----------------------------------------------------------------------

def get_scale_bounds():
    """
    Min and max of each feature across the whole study area.

    Computed from the data itself, not hardcoded, so the scale stays
    correct if barangays are added later.
    """
    row = db.session.query(
        db.func.min(Location.annual_rainfall_mm),
        db.func.max(Location.annual_rainfall_mm),
        db.func.min(Location.elevation_m),
        db.func.max(Location.elevation_m),
        db.func.min(Location.avg_temp_c),
        db.func.max(Location.avg_temp_c),
    ).filter(Location.elevation_m.isnot(None)).first()

    return {
        "rainfall": (row[0], row[1]),
        "elevation": (row[2], row[3]),
        "temperature": (row[4], row[5]),
        "soil": (SOIL_MIN, SOIL_MAX),
    }


def normalize(value, lo, hi):
    """
    Min-max normalization to the 0-1 range.

    Clamped, because a species tolerance midpoint can fall outside the
    range observed in the study area. Without clamping, cosine similarity
    receives negative components and returns uninterpretable results.
    """
    if value is None or lo is None or hi is None or hi == lo:
        return None
    scaled = (value - lo) / (hi - lo)
    return max(0.0, min(1.0, scaled))


# ----------------------------------------------------------------------
# Building vectors
# ----------------------------------------------------------------------

def site_vector(location, bounds):
    """A barangay becomes a 4-element vector. None marks a missing feature."""
    return {
        "rainfall": normalize(location.annual_rainfall_mm, *bounds["rainfall"]),
        "elevation": normalize(location.elevation_m, *bounds["elevation"]),
        "temperature": normalize(location.avg_temp_c, *bounds["temperature"]),
        "soil": normalize(encode_soil(location.soil_texture), *bounds["soil"]),
    }


def _midpoint(lo, hi, fallback_lo, fallback_hi):
    """
    Cosine similarity compares points, not ranges.

    A species tolerance of 900-2200 mm must therefore collapse to a single
    representative value: its midpoint, 1550 mm.

    LIMITATION: this discards the width of the range. A species tolerant
    of 750-4500 mm is treated the same as one tolerant of 2500-2600 mm,
    provided their midpoints coincide. Record this in your limitations.
    """
    if lo is None and hi is None:
        return None
    if lo is None:
        lo = fallback_lo
    if hi is None:
        hi = fallback_hi
    return (lo + hi) / 2.0


def species_vector(species, bounds):
    """A species becomes a 4-element vector from its tolerance midpoints."""
    r = _midpoint(species.min_rainfall_mm, species.max_rainfall_mm,
                  *bounds["rainfall"])
    e = _midpoint(species.min_elevation_m, species.max_elevation_m,
                  *bounds["elevation"])
    t = _midpoint(species.min_temp_c, species.max_temp_c,
                  *bounds["temperature"])

    # soil: average the encoded values of every texture the species accepts
    s = None
    if species.preferred_soil:
        codes = [
            encode_soil(x) for x in species.preferred_soil.split(",")
        ]
        codes = [c for c in codes if c is not None]
        if codes:
            s = sum(codes) / len(codes)

    return {
        "rainfall": normalize(r, *bounds["rainfall"]),
        "elevation": normalize(e, *bounds["elevation"]),
        "temperature": normalize(t, *bounds["temperature"]),
        "soil": normalize(s, *bounds["soil"]),
    }


# ----------------------------------------------------------------------
# Step 4 — cosine similarity
# ----------------------------------------------------------------------

def cosine_similarity(vec_a, vec_b):
    """
    Cosine of the angle between two vectors.

        cos(A,B) = (A . B) / (|A| * |B|)

    Only features present in BOTH vectors are used. If a species has no
    published elevation range, elevation is skipped for that comparison
    rather than being guessed.

    Returns (similarity, number_of_features_used).
    """
    keys = [
        k for k in FEATURES
        if vec_a.get(k) is not None and vec_b.get(k) is not None
    ]

    if not keys:
        return 0.0, 0

    dot = sum(vec_a[k] * vec_b[k] for k in keys)
    mag_a = math.sqrt(sum(vec_a[k] ** 2 for k in keys))
    mag_b = math.sqrt(sum(vec_b[k] ** 2 for k in keys))

    if mag_a == 0 or mag_b == 0:
        return 0.0, len(keys)

    return dot / (mag_a * mag_b), len(keys)


# ----------------------------------------------------------------------
# Step 5 — rank
# ----------------------------------------------------------------------

def recommend_for_location(location, top_k=5):
    """
    Ranked species recommendations for one barangay.

    Returns a dict. 'found' is False when the barangay has no
    characteristic data loaded.
    """
    bounds = get_scale_bounds()
    sv = site_vector(location, bounds)

    if all(v is None for v in sv.values()):
        return {
            "found": False,
            "reason": "No site characteristic data for this barangay.",
            "municipality": location.municipality,
            "barangay": location.barangay,
        }

    species_list = TreeSpecie.query.filter_by(is_reference=True).all()

    results = []
    for sp in species_list:
        pv = species_vector(sp, bounds)
        score, used = cosine_similarity(sv, pv)

        results.append({
            "tree_id": sp.tree_id,
            "specie_name": sp.specie_name,
            "scientific_name": sp.scientific_name,
            "similarity": round(score, 4),
            "features_used": used,
            "within_all_ranges": is_within_ranges(location, sp),
            "rainfall_range": _fmt(sp.min_rainfall_mm, sp.max_rainfall_mm, "mm"),
            "elevation_range": _fmt(sp.min_elevation_m, sp.max_elevation_m, "m"),
            "temperature_range": _fmt(sp.min_temp_c, sp.max_temp_c, "C"),
            "preferred_soil": sp.preferred_soil,
            "source": sp.source,
        })

    results.sort(key=lambda x: x["similarity"], reverse=True)

    return {
        "found": True,
        "municipality": location.municipality,
        "barangay": location.barangay,
        "site_profile": {
            "elevation_m": location.elevation_m,
            "avg_temp_c": location.avg_temp_c,
            "annual_rainfall_mm": location.annual_rainfall_mm,
            "soil_type": location.soil_type,
            "soil_texture": location.soil_texture,
            "agro_ecological_zone": location.agro_ecological_zone,
        },
        "site_vector": {k: (round(v, 4) if v is not None else None)
                        for k, v in sv.items()},
        "method": "cosine similarity",
        "total_species": len(results),
        "recommendations": results[:top_k],
        "all_scores": results,
    }


# ----------------------------------------------------------------------
# Ground truth helper — needed for Precision@K and NDCG@K
# ----------------------------------------------------------------------

def is_within_ranges(location, species):
    """
    True when the barangay falls inside every published tolerance range
    the species has.

    This is the RELEVANCE LABEL used by the evaluation metrics. A species
    is treated as relevant for a barangay when the barangay's measured
    conditions sit inside that species' published ecological limits.

    Ranges that are not published are skipped rather than failed, so a
    species is not penalised for incomplete source data.
    """
    checks = [
        (location.annual_rainfall_mm, species.min_rainfall_mm, species.max_rainfall_mm),
        (location.elevation_m, species.min_elevation_m, species.max_elevation_m),
        (location.avg_temp_c, species.min_temp_c, species.max_temp_c),
    ]

    tested = 0
    for value, lo, hi in checks:
        if value is None:
            continue
        if lo is not None:
            tested += 1
            if value < lo:
                return False
        if hi is not None:
            tested += 1
            if value > hi:
                return False

    if species.preferred_soil and location.soil_texture:
        tested += 1
        accepted = [s.strip().lower() for s in species.preferred_soil.split(",")]
        if location.soil_texture.strip().lower() not in accepted:
            return False

    # a species with no published limits at all is not "relevant"
    return tested > 0


def _fmt(lo, hi, unit):
    if lo is None and hi is None:
        return "not published"
    a = "?" if lo is None else f"{lo:g}"
    b = "?" if hi is None else f"{hi:g}"
    return f"{a} - {b} {unit}"