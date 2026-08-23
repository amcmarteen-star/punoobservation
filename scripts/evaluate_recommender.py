"""
Evaluate the recommendation engine using Precision@K and NDCG@K.

RUN FROM PROJECT ROOT:
    python scripts/evaluate_recommender.py

WHAT THESE METRICS NEED
-----------------------
Both metrics compare your ranked list against a list of species already
known to be correct for that site. That known-correct set is the
GROUND TRUTH, and without it neither metric can be computed at all.

This script uses two independent ground truth sources and reports both.

SOURCE A - Published ecological tolerance ranges
    A species is relevant for a barangay when the barangay's measured
    conditions fall inside that species' published limits.
    Covers all 478 barangays.

SOURCE B - DENR historical planting records
    A species is relevant for a barangay when DENR actually planted it
    there. This is what the capstone paper specifies.
    Covers only the barangays present in the imported DENR data.

Reporting both is deliberate. Source A tests whether the engine agrees
with published ecology. Source B tests whether it reproduces recorded
practice. A large gap between them is itself a finding.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Location, TreeSpecie, Site, ReforestationRecord
from app.services.recommender import (
    recommend_for_location,
    is_within_ranges,
)

K_VALUES = [1, 3, 5]


# ----------------------------------------------------------------------
# The metrics
# ----------------------------------------------------------------------

def precision_at_k(ranked_names, relevant_names, k):
    """
    Of the top K recommendations, what fraction are relevant?

        Precision@K = (relevant items in top K) / K

    Range 0 to 1. Higher is better.
    Order within the top K does not matter.
    """
    if k == 0:
        return 0.0
    top = ranked_names[:k]
    hits = sum(1 for name in top if name in relevant_names)
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


def ndcg_at_k(ranked_names, relevant_names, k):
    """
    Normalized Discounted Cumulative Gain.

        NDCG@K = DCG of your ranking / DCG of the perfect ranking

    The perfect ranking places every relevant species first. Dividing by
    it puts the score on a 0 to 1 scale regardless of how many relevant
    species exist, which makes results comparable across barangays.

    Binary relevance is used here: 1 if relevant, 0 otherwise.
    """
    gains = [1.0 if n in relevant_names else 0.0 for n in ranked_names[:k]]
    actual = dcg(gains)

    ideal_gains = [1.0] * min(len(relevant_names), k)
    ideal = dcg(ideal_gains)

    return actual / ideal if ideal > 0 else 0.0


# ----------------------------------------------------------------------
# Ground truth sets
# ----------------------------------------------------------------------

def ground_truth_from_ranges(location, species_list):
    """SOURCE A: relevant = barangay falls inside published tolerances."""
    return {
        sp.specie_name for sp in species_list
        if is_within_ranges(location, sp)
    }


def build_denr_ground_truth():
    """
    SOURCE B: relevant = DENR actually planted it in that barangay.

    Returns {(municipality_lower, barangay_lower): {species names}}

    The placeholder species is excluded. If every imported record points
    at the placeholder, this returns nothing, which is itself the finding.
    """
    truth = {}

    rows = (
        db.session.query(Location, TreeSpecie)
        .join(Site, Site.location_id == Location.location_id)
        .join(ReforestationRecord,
              ReforestationRecord.site_id == Site.site_id)
        .join(TreeSpecie,
              TreeSpecie.tree_id == ReforestationRecord.tree_id)
        .all()
    )

    for loc, sp in rows:
        if "unspecified" in sp.specie_name.lower():
            continue
        key = (loc.municipality.lower(), loc.barangay.lower())
        truth.setdefault(key, set()).add(sp.specie_name)

    return truth


# ----------------------------------------------------------------------
# Evaluation run
# ----------------------------------------------------------------------

def evaluate(label, locations, truth_fn, species_list):
    print()
    print("=" * 62)
    print(label)
    print("=" * 62)

    scores = {k: {"p": [], "n": []} for k in K_VALUES}
    skipped_no_truth = 0
    evaluated = 0

    for loc in locations:
        relevant = truth_fn(loc)

        if not relevant:
            skipped_no_truth += 1
            continue

        result = recommend_for_location(loc, top_k=len(species_list))
        if not result["found"]:
            continue

        ranked = [r["specie_name"] for r in result["all_scores"]]

        for k in K_VALUES:
            scores[k]["p"].append(precision_at_k(ranked, relevant, k))
            scores[k]["n"].append(ndcg_at_k(ranked, relevant, k))

        evaluated += 1

    print(f"Barangays evaluated       : {evaluated}")
    print(f"Skipped (no ground truth) : {skipped_no_truth}")

    if evaluated == 0:
        print()
        print("NO RESULTS.")
        print("No barangay had any relevant species under this ground truth.")
        print("The metrics cannot be computed. Report this as a finding,")
        print("not as a failure of the script.")
        return None

    print()
    print(f"{'K':<5}{'Precision@K':<16}{'NDCG@K':<16}")
    print("-" * 37)

    out = {}
    for k in K_VALUES:
        p = sum(scores[k]["p"]) / len(scores[k]["p"])
        n = sum(scores[k]["n"]) / len(scores[k]["n"])
        out[k] = (p, n)
        print(f"{k:<5}{p:<16.4f}{n:<16.4f}")

    return out


def relevance_summary(locations, species_list):
    """How many species are relevant per barangay under Source A."""
    counts = []
    per_species = {sp.specie_name: 0 for sp in species_list}

    for loc in locations:
        rel = ground_truth_from_ranges(loc, species_list)
        counts.append(len(rel))
        for name in rel:
            per_species[name] += 1

    print()
    print("=" * 62)
    print("GROUND TRUTH SUMMARY (Source A)")
    print("=" * 62)
    print(f"Barangays with 0 relevant species : "
          f"{sum(1 for c in counts if c == 0)}")
    print(f"Average relevant species per barangay : "
          f"{sum(counts) / len(counts):.2f}")
    print()
    print("Relevant in how many barangays:")
    for name, n in sorted(per_species.items(), key=lambda x: -x[1]):
        print(f"  {name:<14} {n:>4} / {len(locations)}")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():

        species_list = TreeSpecie.query.filter_by(is_reference=True).all()
        locations = Location.query.filter(
            Location.elevation_m.isnot(None)
        ).all()

        print(f"Species in reference dataset : {len(species_list)}")
        print(f"Barangays with characteristics : {len(locations)}")

        if not species_list:
            print()
            print("No reference species. Run seed_reference_data.py first.")
            sys.exit(1)

        relevance_summary(locations, species_list)

        # SOURCE A
        evaluate(
            "SOURCE A - Ground truth from published tolerance ranges",
            locations,
            lambda loc: ground_truth_from_ranges(loc, species_list),
            species_list,
        )

        # SOURCE B
        denr = build_denr_ground_truth()
        print()
        print(f"DENR records give ground truth for {len(denr)} barangays")

        if denr:
            subset = [
                loc for loc in locations
                if (loc.municipality.lower(), loc.barangay.lower()) in denr
            ]
            evaluate(
                "SOURCE B - Ground truth from DENR planting records",
                subset,
                lambda loc: denr.get(
                    (loc.municipality.lower(), loc.barangay.lower()), set()
                ),
                species_list,
            )
        else:
            print()
            print("=" * 62)
            print("SOURCE B - Ground truth from DENR planting records")
            print("=" * 62)
            print("NOT AVAILABLE.")
            print()
            print("Every imported reforestation record points at the")
            print("placeholder species 'Unspecified (Pending Match)'.")
            print()
            print("This is the lacking-historical-record problem, and this")
            print("output is the evidence for it. Bring this to the panel.")