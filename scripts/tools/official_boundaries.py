"""
Replace the map's outline shapes with the official PSA/NAMRIA boundaries.

Keeps every file's features, names and other properties exactly as they
are (the app matches NAME_2 and NAME_3 against the database), and swaps
only the geometry for the official one with the same town and barangay
name. Shared borders are simplified together (shapely.coverage_simplify)
so neighbouring barangays still meet without gaps or overlaps.

Source: the Philippines administrative boundaries from OCHA HDX
(COD-AB, PSA/NAMRIA), the folder holding phl_admin2.shp to
phl_admin4.shp. It is large, so it is not kept in the project.

RUN FROM PROJECT ROOT:
    python -m scripts.tools.official_boundaries "C:/path/to/phl_admin_boundaries.shp" --dry-run
    python -m scripts.tools.official_boundaries "C:/path/to/phl_admin_boundaries.shp"

--dry-run only reports which names match. Without it, the files under
app/static/geojson are rewritten; check the result on the map, and git
can undo it.
"""

import argparse
import json
import os
import re
import sys
import unicodedata

import pyogrio
import shapely
from shapely.geometry import mapping, shape

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEO = os.path.join(ROOT, "app", "static", "geojson")
PROVINCE = "Pangasinan"

# barangay files and town files, by area
AREAS = {
    "western": ["district1"],
    "central": ["district2", "district3", "district4"],
    "eastern": ["district5", "district6"],
}

# Simplify tolerance in degrees (0.0001 is about 11 m). The official
# shapes are far more detailed than a web map needs, and every barangay
# file is downloaded by the map. --tolerance overrides it.
TOLERANCE = 0.0001
DECIMALS = 5          # about 1 m

# Islets smaller than this (square degrees; 0.0000004 is about 0.5 ha)
# are left out of a barangay with other land. Pangasinan's coast has
# hundreds of them, and they make up most of the western file.
MIN_PART = 0.0000004

# Town names written differently in the two sources, after town_key().
# Left: our files. Right: the official data.
TOWN_ALIASES = {"pozzorubio": "pozorrubio"}

# A barangay not matched by name is matched to the closest official name
# in the same town when the two are this similar (0 to 1). Every such
# pair is printed, so a wrong one can be spotted and fixed here.
FUZZY_CUTOFF = 0.8


def norm(name):
    """Fold a name for matching: no accents, case, spaces or dots, no
    bracketed alternative name ("Lambes (Lames)", "Lingayen (Capital)"),
    "Sta."/"Sto." spelled out, and no "City of"/"City"."""
    s = str(name or "").replace("�", "n")      # our files lost the ñ
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)", "", s)
    # "Sta. Rosa" and "Sta Rosa", but not "Station"
    s = re.sub(r"\bsta(\.\s*|\s+)", "santa ", s)
    s = re.sub(r"\bsto(\.\s*|\s+)", "santo ", s)
    s = re.sub(r"^city of ", "", s.strip())
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def town_key(name):
    k = re.sub(r"city$", "", norm(name))
    return TOWN_ALIASES.get(k, k)


def match_barangay(town, name, brgy_geo, taken):
    """The official key for one of our barangays, and how it was found."""
    key = (town, norm(name))
    if key in brgy_geo:
        return key, "name"
    import difflib
    pool = [k[1] for k in brgy_geo if k[0] == town and k not in taken]
    close = difflib.get_close_matches(key[1], pool, n=1, cutoff=FUZZY_CUTOFF)
    if close:
        return (town, close[0]), "near"
    return None, None


def load_official(folder):
    where = f"adm2_name = '{PROVINCE}'"
    towns = pyogrio.read_dataframe(os.path.join(folder, "phl_admin3.shp"), where=where)
    brgys = pyogrio.read_dataframe(os.path.join(folder, "phl_admin4.shp"), where=where)
    prov = pyogrio.read_dataframe(os.path.join(folder, "phl_admin2.shp"), where=where)
    town_geo = {town_key(r.adm3_name): r.geometry for r in towns.itertuples()}
    brgy_geo = {}
    for r in brgys.itertuples():
        k = (town_key(r.adm3_name), norm(r.adm4_name))
        if k in brgy_geo:            # a barangay in two parts
            brgy_geo[k] = shapely.union(brgy_geo[k], r.geometry)
        else:
            brgy_geo[k] = r.geometry
    return town_geo, brgy_geo, prov.geometry.iloc[0], towns, brgys


def simplify_together(geoms, tolerance):
    """Simplify a set of neighbouring shapes so shared edges stay shared."""
    arr = shapely.coverage_simplify(shapely.make_valid(list(geoms)), tolerance)
    return list(arr)


def drop_islets(geom):
    """Leave out tiny islets, but never a barangay's largest part."""
    if geom.geom_type != "MultiPolygon":
        return geom
    parts = sorted(geom.geoms, key=lambda g: g.area, reverse=True)
    keep = [parts[0]] + [g for g in parts[1:] if g.area >= MIN_PART]
    return keep[0] if len(keep) == 1 else shapely.MultiPolygon(keep)


def rounded(geom):
    geom = drop_islets(geom)
    g = mapping(shapely.set_precision(geom, 10 ** -DECIMALS))
    return json.loads(json.dumps(g))


def write(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="folder holding phl_admin2.shp to phl_admin4.shp")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tolerance", type=float, default=TOLERANCE,
                    help="simplify tolerance in degrees (default %(default)s)")
    args = ap.parse_args()

    town_geo, brgy_geo, prov_geom, towns_df, brgys_df = load_official(args.folder)
    print(f"official: {len(town_geo)} towns, {len(brgy_geo)} barangays in {PROVINCE}")

    used_towns, used_brgys = set(), set()
    problems = 0
    for area, districts in AREAS.items():
        for d in districts:
            for kind in ("town", "barangay"):
                name = d + ("_barangay" if kind == "barangay" else "")
                path = os.path.join(GEO, area, name + ".geojson")
                data = json.load(open(path, encoding="utf-8"))
                found, missing, near = [], [], []
                # exact names first, so a near match never takes a
                # barangay that has its own exact match
                feats = sorted(data["features"], key=lambda f: (
                    kind == "barangay"
                    and (town_key(f["properties"].get("NAME_2")),
                         norm(f["properties"].get("NAME_3"))) not in brgy_geo))
                for f in feats:
                    p = f["properties"]
                    t = town_key(p.get("NAME_2"))
                    if kind == "town":
                        key, how = (t, "name") if t in town_geo else (None, None)
                        g = town_geo.get(t)
                    else:
                        key, how = match_barangay(t, p.get("NAME_3"), brgy_geo, used_brgys)
                        g = brgy_geo.get(key) if key else None
                    if g is None:
                        missing.append(p.get("NAME_3") and f"{p['NAME_3']}, {p['NAME_2']}" or p.get("NAME_2"))
                        continue
                    if how == "near":
                        near.append(f"{p['NAME_3']} -> {key[1]} ({p['NAME_2']})")
                    found.append((f, g))
                    (used_towns if kind == "town" else used_brgys).add(key)
                print(f"{area}/{name}: {len(found)} matched, {len(missing)} not found"
                      + (f" -> {missing}" if missing else ""))
                for n_ in near:
                    print("     near match:", n_)
                problems += len(missing)
                if args.dry_run or not found:
                    continue
                simple = simplify_together((g for _, g in found), args.tolerance)
                for (f, _), g in zip(found, simple):
                    f["geometry"] = rounded(g)
                write(path, data)

    ours = {town_key(t) for t in used_towns} if used_towns else set()
    extra_b = sorted(k for k in brgy_geo if k[0] in {k2[0] for k2 in used_brgys} and k not in used_brgys)
    if extra_b:
        print(f"official barangays in our towns but not in our files: {len(extra_b)} -> {extra_b[:15]}")

    if not args.dry_run:
        prov_path = os.path.join(GEO, "pangasinan.geojson")
        data = json.load(open(prov_path, encoding="utf-8"))
        data["features"][0]["geometry"] = rounded(
            shapely.simplify(prov_geom, args.tolerance * 4, preserve_topology=True))
        write(prov_path, data)
        print("pangasinan.geojson: province outline replaced")
    print("not found in total:", problems)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
