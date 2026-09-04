"""
Evaluation metrics for the species recommendation engine.

This module holds the metric mathematics in ONE place. Both the offline
script (scripts/evaluate_recommender.py) and the species detail panel in
the web interface import from here, so the figure a panel member sees on
screen is produced by the same code that produced the figure in the
paper. They cannot drift apart.

TWO LEVELS OF EVALUATION
------------------------
The panel shows both, because they answer different questions.

1. PER-SPECIES  (precision, recall, F1, confusion matrix)

   Each species is treated as a binary classifier over every barangay in
   scope:

       predicted positive = the species lands in that barangay's top K
       actual positive    = the barangay falls inside that species'
                            published tolerance ranges

   This answers "when the engine offers Narra, is Narra actually
   appropriate, and does the engine find Narra everywhere it fits?"
   It is specific to the species that was clicked.

2. ENGINE-WIDE  (Precision@K, NDCG@K)

   The ranking metrics named in the capstone paper, averaged over every
   barangay. Identical for every species, shown as context: they say how
   trustworthy the ranking is as a whole. NDCG@K additionally rewards
   putting the relevant species nearer the top, which Precision@K does
   not.

GROUND TRUTH
------------
Both levels use SOURCE A - published ecological tolerance ranges - via
is_within_ranges(). Source B (DENR historical planting records) is not
computable here: every imported reforestation record points at the
placeholder species 'Unspecified (Pending Match)'. The offline script
reports that absence explicitly; the interface simply states which
ground truth it used.

A barangay with NO relevant species carries no ground truth, so it is
excluded from every metric rather than counted as a row of failures.
That is the same rule the offline script applies.
"""

import math
import time

from app.services.recommender import (
    FEATURES,
    SALINITY_LABELS,
    cosine_similarity,
    get_scale_bounds,
    is_within_ranges,
    site_vector,
    species_vector,
)

DEFAULT_TOP_K = 5
K_VALUES = (1, 3, 5)

# A corpus pass touches every barangay, so the result is memoised for
# this long. Short enough that editing a species profile shows up while
# a user is still on the page; long enough that clicking through several
# species costs one computation, not one per click.
CACHE_TTL_SECONDS = 300

_cache = {}


# ----------------------------------------------------------------------
# The metrics
# ----------------------------------------------------------------------

def precision_at_k(ranked, relevant, k):
    """
    Of the top K recommendations, what fraction are relevant?

        Precision@K = (relevant items in top K) / K

    Range 0 to 1. Higher is better.
    Order within the top K does not matter.
    """
    if k == 0:
        return 0.0
    top = ranked[:k]
    hits = sum(1 for item in top if item in relevant)
    return hits / k


def dcg(gains):
    """
    Discounted Cumulative Gain.

        DCG = sum over positions i of  gain_i / log2(i + 1)

    The divisor grows with position, so a relevant item ranked 1st
    contributes more than the same item ranked 5th. This is what makes
    NDCG sensitive to ordering, unlike Precision@K.
    """
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg_at_k(ranked, relevant, k):
    """
    Normalized Discounted Cumulative Gain.

        NDCG@K = DCG of your ranking / DCG of the perfect ranking

    The perfect ranking places every relevant species first. Dividing by
    it puts the score on a 0 to 1 scale regardless of how many relevant
    species exist, which makes results comparable across barangays.

    Binary relevance is used here: 1 if relevant, 0 otherwise.
    """
    gains = [1.0 if item in relevant else 0.0 for item in ranked[:k]]
    actual = dcg(gains)

    ideal = dcg([1.0] * min(len(relevant), k))

    return actual / ideal if ideal > 0 else 0.0


def precision_recall_f1(tp, fp, fn):
    """
    The three standard classification figures from a confusion matrix.

        precision = TP / (TP + FP)      of what was offered, how much fit
        recall    = TP / (TP + FN)      of what fits, how much was offered
        F1        = harmonic mean of the two

    None is returned rather than 0.0 when a denominator is zero, because
    "never recommended anywhere" is not the same as "recommended and
    always wrong", and showing 0.000 for it would misinform the reader.
    """
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None

    if precision is None or recall is None or (precision + recall) == 0:
        f1 = None
    else:
        f1 = 2 * precision * recall / (precision + recall)

    return precision, recall, f1


# ----------------------------------------------------------------------
# One pass over the whole study area
# ----------------------------------------------------------------------

def evaluate_corpus(locations, species_list, top_k=DEFAULT_TOP_K,
                    k_values=K_VALUES):
    """
    Score every barangay against every species once, and accumulate both
    levels of evaluation from that single pass.

    Doing this in one pass matters. Calling recommend_for_location() per
    species would re-query the database and re-rank the full species set
    once per click; here the whole study area costs one pass.

    Returns a dict of per-species confusion counts keyed by tree_id, the
    engine-wide averages, and the corpus counts needed to describe them
    honestly.
    """
    bounds = get_scale_bounds()
    profiles = {sp.tree_id: species_vector(sp, bounds) for sp in species_list}

    per_species = {
        sp.tree_id: {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "recommended": 0,
                     "relevant": 0}
        for sp in species_list
    }
    at_k = {k: {"p": [], "n": []} for k in k_values}

    scored = 0            # barangays the engine could rank at all
    evaluated = 0         # barangays that also had ground truth
    skipped_no_truth = 0

    for loc in locations:
        sv = site_vector(loc, bounds)
        if all(v is None for v in sv.values()):
            continue
        scored += 1

        ranked = []
        relevant = set()
        for sp in species_list:
            score, _ = cosine_similarity(sv, profiles[sp.tree_id])
            ranked.append((score, sp.tree_id))
            if is_within_ranges(loc, sp):
                relevant.add(sp.tree_id)

        # A barangay no species fits carries no ground truth. Counting it
        # would add false positives for every species and reward nothing,
        # so it is excluded from both levels alike.
        if not relevant:
            skipped_no_truth += 1
            continue

        ranked.sort(key=lambda pair: -pair[0])
        ranked_ids = [tree_id for _, tree_id in ranked]
        predicted = set(ranked_ids[:top_k])

        for sp in species_list:
            cell = per_species[sp.tree_id]
            offered = sp.tree_id in predicted
            fits = sp.tree_id in relevant

            if offered:
                cell["recommended"] += 1
            if fits:
                cell["relevant"] += 1

            if offered and fits:
                cell["tp"] += 1
            elif offered and not fits:
                cell["fp"] += 1
            elif not offered and fits:
                cell["fn"] += 1
            else:
                cell["tn"] += 1

        for k in k_values:
            at_k[k]["p"].append(precision_at_k(ranked_ids, relevant, k))
            at_k[k]["n"].append(ndcg_at_k(ranked_ids, relevant, k))

        evaluated += 1

    engine_rows = []
    for k in k_values:
        samples_p = at_k[k]["p"]
        samples_n = at_k[k]["n"]
        engine_rows.append({
            "k": k,
            "precision_at_k": (round(sum(samples_p) / len(samples_p), 4)
                               if samples_p else None),
            "ndcg_at_k": (round(sum(samples_n) / len(samples_n), 4)
                          if samples_n else None),
        })

    return {
        "per_species": per_species,
        "engine_rows": engine_rows,
        "barangays_scored": scored,
        "barangays_evaluated": evaluated,
        "skipped_no_truth": skipped_no_truth,
        "species_count": len(species_list),
        "top_k": top_k,
    }


def corpus_cached(locations, species_list, top_k=DEFAULT_TOP_K,
                  k_values=K_VALUES):
    """
    evaluate_corpus() memoised for CACHE_TTL_SECONDS.

    The key includes the exact set of barangays and species, so a user
    limited to one CENRO and a superadmin seeing the province get their
    own entries rather than sharing one another's figures.
    """
    key = (
        frozenset(loc.location_id for loc in locations),
        frozenset(sp.tree_id for sp in species_list),
        top_k,
        tuple(k_values),
    )

    hit = _cache.get(key)
    now = time.time()
    if hit and now - hit[0] < CACHE_TTL_SECONDS:
        return hit[1]

    computed = evaluate_corpus(locations, species_list, top_k, k_values)
    _cache[key] = (now, computed)
    return computed


def clear_cache():
    """Drop memoised corpus results, e.g. after species data is edited."""
    _cache.clear()


# ----------------------------------------------------------------------
# Why THIS barangay scored the way it did
# ----------------------------------------------------------------------

MATCH_STRONG, MATCH_MODERATE, MATCH_WEAK = "strong", "moderate", "weak"

FEATURE_LABELS = {
    "rainfall": "Rainfall",
    "elevation": "Elevation",
    "temperature": "Temperature",
    "soil": "Soil texture",
    "salinity": "Salinity / exposure",
}


def _match_strength(gap):
    """
    How close two normalised feature values are, in words.

    The thresholds are on the 0-1 normalised scale, so they mean the same
    thing for rainfall as for elevation. They label the gap for a reader;
    nothing in the ranking depends on them.
    """
    if gap is None:
        return None
    if gap <= 0.10:
        return MATCH_STRONG
    if gap <= 0.25:
        return MATCH_MODERATE
    return MATCH_WEAK


def _fits_range(value, lo, hi):
    """True/False if the range can be tested, None if it is not published."""
    if value is None or (lo is None and hi is None):
        return None
    if lo is not None and value < lo:
        return False
    if hi is not None and value > hi:
        return False
    return True


def feature_breakdown(location, species, bounds=None):
    """
    The five feature comparisons behind one similarity score.

    Cosine similarity is a single number, which makes it easy to trust
    and impossible to argue with. This decomposes it: for each feature,
    the site's own value, what the species wants, the normalised pair the
    mathematics actually used, and whether the site sits inside the
    published range.

    Features missing from either side are marked used=False. Those are
    skipped by cosine_similarity() rather than guessed, and showing them
    as skipped is the honest presentation.
    """
    if bounds is None:
        bounds = get_scale_bounds()

    sv = site_vector(location, bounds)
    pv = species_vector(species, bounds)

    raw = {
        "rainfall": (
            location.annual_rainfall_mm,
            species.min_rainfall_mm, species.max_rainfall_mm, "mm",
        ),
        "elevation": (
            location.elevation_m,
            species.min_elevation_m, species.max_elevation_m, "m",
        ),
        "temperature": (
            location.avg_temp_c,
            species.min_temp_c, species.max_temp_c, "°C",
        ),
    }

    rows = []
    for key in FEATURES:
        a, b = sv.get(key), pv.get(key)
        used = a is not None and b is not None
        gap = abs(a - b) if used else None

        row = {
            "key": key,
            "label": FEATURE_LABELS[key],
            "site_norm": round(a, 4) if a is not None else None,
            "species_norm": round(b, 4) if b is not None else None,
            "gap": round(gap, 4) if gap is not None else None,
            "match": _match_strength(gap),
            "used": used,
        }

        if key in raw:
            value, lo, hi, unit = raw[key]
            row["site_value"] = (f"{value:g} {unit}" if value is not None
                                 else "not recorded")
            if lo is None and hi is None:
                row["species_value"] = "not published"
            else:
                a_txt = "?" if lo is None else f"{lo:g}"
                b_txt = "?" if hi is None else f"{hi:g}"
                row["species_value"] = f"{a_txt} – {b_txt} {unit}"
            row["in_range"] = _fits_range(value, lo, hi)

        elif key == "soil":
            row["site_value"] = location.soil_texture or "not recorded"
            row["species_value"] = species.preferred_soil or "not published"
            if species.preferred_soil and location.soil_texture:
                accepted = [s.strip().lower()
                            for s in species.preferred_soil.split(",")]
                row["in_range"] = (
                    location.soil_texture.strip().lower() in accepted
                )
            else:
                row["in_range"] = None

        else:  # salinity
            row["site_value"] = SALINITY_LABELS.get(
                location.coastal_exposure, "not recorded"
            )
            row["species_value"] = SALINITY_LABELS.get(
                species.salinity_requirement, "not published"
            )
            if (species.salinity_requirement is not None
                    and location.coastal_exposure is not None):
                # a species needing salt cannot grow where there is none
                row["in_range"] = (
                    species.salinity_requirement <= location.coastal_exposure
                )
            else:
                row["in_range"] = None

        rows.append(row)

    return rows


# ----------------------------------------------------------------------
# Plain-language readings
# ----------------------------------------------------------------------

def _pct(value):
    return f"{value * 100:.0f}%"


def interpret_similarity(species_name, similarity, within_ranges, rows):
    """What the clicked species' score means for the clicked barangay."""
    if similarity >= 0.98:
        closeness = "an almost exact match for"
    elif similarity >= 0.90:
        closeness = "a close match for"
    elif similarity >= 0.75:
        closeness = "a moderate match for"
    else:
        closeness = "a poor match for"

    text = (
        f"A cosine similarity of {similarity:.4f} makes this barangay's "
        f"conditions {closeness} the profile published for {species_name}."
    )

    weak = [r["label"].lower() for r in rows
            if r["used"] and r["match"] == MATCH_WEAK]
    if weak:
        text += (
            " The largest disagreement is on "
            + ", ".join(weak) + "."
        )

    skipped = [r["label"].lower() for r in rows if not r["used"]]
    if skipped:
        text += (
            " " + ", ".join(skipped).capitalize()
            + (" was" if len(skipped) == 1 else " were")
            + " left out of the calculation because the value is missing "
            "on one side; it was skipped rather than guessed."
        )

    outside = [r["label"].lower() for r in rows if r.get("in_range") is False]
    if within_ranges:
        text += (
            " The barangay also falls inside every tolerance range "
            "published for this species."
        )
    elif outside:
        text += (
            " Note that the barangay sits outside the published "
            + ", ".join(outside)
            + " range, so a high similarity here reflects the midpoint of "
            "that range rather than the range itself."
        )

    return text


def interpret_species(species_name, precision, recall, f1, cell, top_k,
                      evaluated):
    """What the per-species confusion matrix means, in words."""
    if precision is None:
        return (
            f"{species_name} never reaches the top {top_k} in any of the "
            f"{evaluated} barangays evaluated, so precision is undefined. "
            "Nothing was offered, so nothing can be right or wrong. Recall "
            "of "
            + (f"{recall:.3f}" if recall is not None else "0")
            + " reflects that: the species fits "
            f"{cell['relevant']} barangay(s) the engine never surfaces."
        )

    parts = [
        f"Of the {cell['recommended']} barangays where {species_name} "
        f"reaches the top {top_k}, {_pct(precision)} are inside its "
        f"published tolerance ranges. That is precision: it describes how "
        f"much a user can trust this species when the engine offers it."
    ]

    if recall is not None:
        parts.append(
            f"Recall of {recall:.3f} means the engine surfaces "
            f"{_pct(recall)} of the {cell['relevant']} barangays the "
            f"species would in fact suit; the remaining {cell['fn']} are "
            f"missed because other species outrank it there."
        )

    if f1 is not None:
        if precision is not None and recall is not None and precision > recall + 0.15:
            balance = (
                "The gap between them means this species is offered "
                "conservatively: what it recommends is sound, but it is "
                "crowded out of sites it would suit."
            )
        elif precision is not None and recall is not None and recall > precision + 0.15:
            balance = (
                "The gap between them means this species is offered "
                "broadly: it is rarely missed, but a share of what it "
                "recommends falls outside its published ranges."
            )
        else:
            balance = "Precision and recall are balanced for this species."
        parts.append(f"F1 of {f1:.3f} combines the two. {balance}")

    return " ".join(parts)


def interpret_engine(engine_rows, evaluated, top_k):
    """What the engine-wide ranking metrics mean, in words."""
    row = next((r for r in engine_rows if r["k"] == top_k), None)
    if row is None or row["precision_at_k"] is None:
        return (
            "Engine-wide metrics could not be computed: no barangay in "
            "scope had any species inside its published ranges."
        )

    text = (
        f"Averaged over {evaluated} barangays, {_pct(row['precision_at_k'])} "
        f"of the top {top_k} species the engine returns are inside their "
        f"published tolerance ranges for that site."
    )

    if row["ndcg_at_k"] is not None:
        text += (
            f" NDCG@{top_k} of {row['ndcg_at_k']:.4f} additionally rewards "
            "placing the suitable species nearer the top of the list; a "
            "value above Precision@"
            f"{top_k} means the ranking order is working, not just the "
            "membership of the list."
        )

    text += (
        " These figures describe the engine as a whole and are the same "
        "whichever species is opened."
    )

    return text


CAVEAT = (
    "Ground truth here is published ecological tolerance ranges, not "
    "recorded planting outcomes. Every imported DENR reforestation record "
    "points at the placeholder species 'Unspecified (Pending Match)', so "
    "survival-based ground truth cannot be computed yet. These metrics "
    "therefore test whether the engine agrees with published ecology, not "
    "whether it reproduces field results. Recommendations remain "
    "decision-support and do not replace professional field assessment."
)


# ----------------------------------------------------------------------
# The payload the detail panel consumes
# ----------------------------------------------------------------------

def species_evaluation(species, location, locations, species_list,
                       top_k=DEFAULT_TOP_K, k_values=K_VALUES):
    """
    Everything the species detail panel shows, for one species opened
    from one barangay.
    """
    bounds = get_scale_bounds()
    sv = site_vector(location, bounds)
    pv = species_vector(species, bounds)
    similarity, features_used = cosine_similarity(sv, pv)
    within = is_within_ranges(location, species)

    rows = feature_breakdown(location, species, bounds)
    corpus = corpus_cached(locations, species_list, top_k, k_values)

    cell = corpus["per_species"].get(
        species.tree_id,
        {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "recommended": 0, "relevant": 0},
    )
    precision, recall, f1 = precision_recall_f1(
        cell["tp"], cell["fp"], cell["fn"]
    )

    total = cell["tp"] + cell["fp"] + cell["fn"] + cell["tn"]
    accuracy = (cell["tp"] + cell["tn"]) / total if total else None

    return {
        "found": True,
        "species": {
            "tree_id": species.tree_id,
            "specie_name": species.specie_name,
            "scientific_name": species.scientific_name,
            "native_to": species.native_to,
            "source": species.source,
        },
        "site": {
            "location_id": location.location_id,
            "municipality": location.municipality,
            "barangay": location.barangay,
            "similarity": round(similarity, 4),
            "features_used": features_used,
            "features_total": len(FEATURES),
            "within_all_ranges": within,
        },
        "features": rows,
        "species_metrics": {
            "tp": cell["tp"],
            "fp": cell["fp"],
            "fn": cell["fn"],
            "tn": cell["tn"],
            "recommended": cell["recommended"],
            "relevant": cell["relevant"],
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
            "f1": round(f1, 4) if f1 is not None else None,
            "accuracy": round(accuracy, 4) if accuracy is not None else None,
        },
        "engine_metrics": {
            "rows": corpus["engine_rows"],
            "top_k": corpus["top_k"],
        },
        "corpus": {
            "barangays_scored": corpus["barangays_scored"],
            "barangays_evaluated": corpus["barangays_evaluated"],
            "skipped_no_truth": corpus["skipped_no_truth"],
            "species_count": corpus["species_count"],
            "top_k": corpus["top_k"],
            "ground_truth": "Published ecological tolerance ranges (Source A)",
        },
        "interpretation": {
            "similarity": interpret_similarity(
                species.specie_name, similarity, within, rows
            ),
            "species": interpret_species(
                species.specie_name, precision, recall, f1, cell,
                corpus["top_k"], corpus["barangays_evaluated"]
            ),
            "engine": interpret_engine(
                corpus["engine_rows"], corpus["barangays_evaluated"],
                corpus["top_k"]
            ),
            "caveat": CAVEAT,
        },
    }
