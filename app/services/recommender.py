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

You also need an empty file at:
    app/services/__init__.py

NOTE ON THE REFERENCE DATASET
-----------------------------
The paper specifies comparison against historical site profiles. Those
records do not exist in usable form: the available DENR data covers 20
barangays, and species selection in it is determined by program
component rather than site conditions.

This implementation therefore builds reference profiles from published
species ecological tolerances instead. The mathematics is unchanged.
Only the source of the reference vectors differs.
"""

import math

from app.extensions import db
from app.models import Location, TreeSpecie


# ----------------------------------------------------------------------
# Step 2 - categorical encoding
# ----------------------------------------------------------------------
#
# SOIL TEXTURE
#
# Ordinal encoding along the coarse-to-fine particle size scale, which
# is how soil texture is physically ordered:
#
#   sand -> loamy sand -> sandy loam -> loam -> silt loam
#        -> clay loam -> silty clay loam -> clay
#
# Textures close on this scale behave similarly for drainage and water
# retention, so a numeric scale is defensible.
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

SOIL_MIN, SOIL_MAX = 1, 8

# COASTAL EXPOSURE / SALINITY
#
# Both sides use the same 0-3 ordinal scale. The site reports how saline
# it is; the species reports how saline it needs to be.
#
#   0 inland      1 low-lying      2 coastal      3 tidal
#
# This is what keeps mangroves out of inland recommendations without any
# hard-coded exclusion. An inland barangay scores 0; a mangrove scores 3;
# the distance between them lowers the similarity on its own.
#
# It also means the engine needs NO CHANGE if coverage is extended to
# coastal municipalities. Those barangays will score 2 or 3 and the same
# species will rank correctly there.

SALINITY_MIN, SALINITY_MAX = 0, 3

FEATURES = ["rainfall", "elevation", "temperature", "soil", "salinity"]


def encode_soil(texture):
    """Soil texture string -> number. None if unknown."""
    if not texture:
        return None
    return SOIL_ENCODING.get(str(texture).strip().lower())


# ----------------------------------------------------------------------
# Step 3 - normalization
# ----------------------------------------------------------------------

def get_scale_bounds():
    """
    Min and max of each feature across the whole study area.

    Computed from the data, not hardcoded, so the scale stays correct if
    barangays are added later.

    Salinity uses its fixed 0-3 definition rather than the observed
    range. In an inland-only study area every barangay is 0, so an
    observed range would collapse to zero width and the feature would be
    silently dropped.
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
        "salinity": (SALINITY_MIN, SALINITY_MAX),
    }


def normalize(value, lo, hi):
    """
    Min-max normalization to the 0-1 range.

    Clamped, because a species tolerance midpoint can fall outside the
    range observed in the study area. Without clamping, cosine receives
    negative components and returns uninterpretable results.
    """
    if value is None or lo is None or hi is None or hi == lo:
        return None
    scaled = (value - lo) / (hi - lo)
    return max(0.0, min(1.0, scaled))


# ----------------------------------------------------------------------
# Building vectors
# ----------------------------------------------------------------------

def site_vector(location, bounds):
    """A barangay becomes a 5-element vector. None marks a missing feature."""
    return {
        "rainfall": normalize(location.annual_rainfall_mm, *bounds["rainfall"]),
        "elevation": normalize(location.elevation_m, *bounds["elevation"]),
        "temperature": normalize(location.avg_temp_c, *bounds["temperature"]),
        "soil": normalize(encode_soil(location.soil_texture), *bounds["soil"]),
        "salinity": normalize(location.coastal_exposure, *bounds["salinity"]),
    }


def _midpoint(lo, hi, fallback_lo, fallback_hi):
    """
    Cosine similarity compares points, not ranges.

    A tolerance of 900-2200 mm must therefore collapse to its midpoint,
    1550 mm.

    LIMITATION: this discards range width. A species tolerant of
    750-4500 mm is treated the same as one tolerant of 2500-2600 mm if
    their midpoints coincide. Record this in your limitations section.
    """
    if lo is None and hi is None:
        return None
    if lo is None:
        lo = fallback_lo
    if hi is None:
        hi = fallback_hi
    return (lo + hi) / 2.0


def species_vector(species, bounds):
    """A species becomes a 5-element vector from its published profile."""
    r = _midpoint(species.min_rainfall_mm, species.max_rainfall_mm,
                  *bounds["rainfall"])
    e = _midpoint(species.min_elevation_m, species.max_elevation_m,
                  *bounds["elevation"])
    t = _midpoint(species.min_temp_c, species.max_temp_c,
                  *bounds["temperature"])

    # soil: average the encoded values of every texture the species accepts
    s = None
    if species.preferred_soil:
        codes = [encode_soil(x) for x in species.preferred_soil.split(",")]
        codes = [c for c in codes if c is not None]
        if codes:
            s = sum(codes) / len(codes)

    return {
        "rainfall": normalize(r, *bounds["rainfall"]),
        "elevation": normalize(e, *bounds["elevation"]),
        "temperature": normalize(t, *bounds["temperature"]),
        "soil": normalize(s, *bounds["soil"]),
        "salinity": normalize(species.salinity_requirement, *bounds["salinity"]),
    }


# ----------------------------------------------------------------------
# Step 4 - cosine similarity
# ----------------------------------------------------------------------

def cosine_similarity(vec_a, vec_b):
    """
    Cosine of the angle between two vectors.

        cos(A,B) = (A . B) / (|A| * |B|)

    Only features present in BOTH vectors are used. A species with no
    published elevation range has elevation skipped rather than guessed.

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
# Step 5 - rank
# ----------------------------------------------------------------------

def recommend_for_location(location, top_k=5):
    """
    Ranked species recommendations for one barangay.

    'found' is False when the barangay has no characteristic data.
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

        # The full-precision score is carried alongside the row so the
        # ranking can sort on it. Sorting on the rounded 'similarity'
        # instead would make two species that differ in the 6th decimal
        # tie, and the tie would then be broken by database insertion
        # order - which changed the top 5 in 3 of 478 barangays and made
        # the interface disagree with the evaluation script.
        results.append((score, {
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
            "salinity_requirement": sp.salinity_requirement,
            "habitat": SALINITY_LABELS.get(sp.salinity_requirement, "unknown"),
            "source": sp.source,
        }))

    results.sort(key=lambda pair: -pair[0])
    results = [row for _, row in results]

    return {
        "found": True,
        "location_id": location.location_id,
        "municipality": location.municipality,
        "barangay": location.barangay,
        "site_profile": {
            "elevation_m": location.elevation_m,
            "avg_temp_c": location.avg_temp_c,
            "annual_rainfall_mm": location.annual_rainfall_mm,
            "soil_type": location.soil_type,
            "soil_texture": location.soil_texture,
            "agro_ecological_zone": location.agro_ecological_zone,
            "coastal_exposure": location.coastal_exposure,
            "habitat": SALINITY_LABELS.get(location.coastal_exposure, "unknown"),
        },
        "site_vector": {k: (round(v, 4) if v is not None else None)
                        for k, v in sv.items()},
        "method": "cosine similarity",
        "total_species": len(results),
        "recommendations": results[:top_k],
        "all_scores": results,
    }


SALINITY_LABELS = {
    0: "inland",
    1: "low-lying",
    2: "coastal",
    3: "tidal",
}


# ----------------------------------------------------------------------
# Ground truth helper - used by Precision@K and NDCG@K
# ----------------------------------------------------------------------

def is_within_ranges(location, species):
    """
    True when the barangay falls inside every published tolerance range
    the species has.

    This is the RELEVANCE LABEL used by the evaluation metrics.

    Ranges that are not published are skipped rather than failed, so a
    species is not penalised for incomplete source data.

    Salinity is treated as a hard mismatch: a species requiring tidal
    saltwater is never 'within range' for an inland barangay, regardless
    of how well its climate ranges fit.
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

    if (species.salinity_requirement is not None
            and location.coastal_exposure is not None):
        tested += 1
        # a species needing salt cannot grow where there is none
        if species.salinity_requirement > location.coastal_exposure:
            return False

    return tested > 0


def _fmt(lo, hi, unit):
    if lo is None and hi is None:
        return "not published"
    a = "?" if lo is None else f"{lo:g}"
    b = "?" if hi is None else f"{hi:g}"
    return f"{a} - {b} {unit}"