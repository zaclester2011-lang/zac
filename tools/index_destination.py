#!/usr/bin/env python3
"""Index a destination: every place in it, categorised, auto-scored, photographed.

    python3 tools/index_destination.py add "Cook Islands"
    python3 tools/index_destination.py add "Bali" --include-shops
    python3 tools/index_destination.py add "Crete" --bbox 34.78,23.40,35.75,26.40
    python3 tools/index_destination.py list
    python3 tools/index_destination.py remove "Bali"

Sources, both open and free:
  Overture Maps  - every POI on earth, 11.9 GB of parquet on a public S3 bucket.
                   Queried by bounding box; nothing is downloaded whole.
  Wikidata       - landmarks and freely licensed photographs (P18).

Writes site/data.json (what the website serves) and site/destinations.json
(the registry). Re-running a destination replaces it rather than duplicating it.

Needs: pip install duckdb
"""

import argparse, collections, json, math, os, re, sys, time, unicodedata
import urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
DATA = os.path.join(SITE, "data.json")
REG = os.path.join(SITE, "destinations.json")
UA = "hidden-water-index/1.0 (open-data indexing; contact via repository)"
BUCKET = "https://overturemaps-us-west-2.s3.amazonaws.com/"

FIELDS = ["n", "c", "lat", "lon", "q", "loc", "k", "d", "w", "a", "tel", "ad", "img"]

# ---------------------------------------------------------------- categories

ADVENTURE = {
    "boat_tour", "scuba_diving_center", "scuba_diving_instruction", "hiking_trail",
    "surfing", "fishing_charter", "atv_rental_tour", "equestrian_facility",
    "horseback_riding_service", "horse_boarding", "rock_climbing_spot", "snorkeling",
    "adventure_sports_center", "atv_recreation_park", "canoe_and_kayak_hire_service",
    "kayaking", "sailing", "windsurfing", "kitesurfing", "paragliding", "rafting",
    "canyoning", "bungee", "parasailing", "zip_line", "boat_rental", "water_sports",
    "jet_ski_rental", "bicycle_rental", "cycling",
}
CATEGORIES = ["beach", "adventure", "food", "club", "todo", "hotel", "indoor", "guide", "shop"]
TRAVEL = [c for c in CATEGORIES if c != "shop"]


def categorise(tax, basic, hierarchy, alternates):
    """Map an Overture taxonomy onto one of our categories, or None to drop it."""
    t = (tax or "").lower()
    alts = [a.lower() for a in (alternates or [])]
    blob = " ".join([t, (basic or "").lower(), " ".join(hierarchy or []).lower(), " ".join(alts)])

    if t in ADVENTURE or any(a in ADVENTURE for a in alts):
        return "adventure"
    if t == "music_venue":
        return "club"
    if t in ("performing_arts", "arts_and_entertainment", "night_market"):
        return "indoor"
    if "beach" in blob and "store" not in t and "bar" not in t:
        return "beach"
    if any(k in t for k in ("nightclub", "night_club", "bar", "pub", "brewery", "cocktail", "lounge")):
        return "club"
    if any(k in t for k in ("restaurant", "cafe", "coffee", "bakery", "taverna", "pizza",
                            "dining", "bistro", "grill", "food_stand", "ice_cream", "warung")):
        return "food"
    if any(k in t for k in ("hotel", "lodging", "resort", "hostel", "bed_and_breakfast",
                            "rental_home", "villa", "cabin", "lodge", "apartment", "cottage",
                            "campground", "guest")):
        return "hotel"
    if any(k in t for k in ("museum", "gallery", "theatre", "theater", "cinema", "aquarium",
                            "library", "spa", "bowling", "casino")):
        return "indoor"
    if any(k in t for k in ("tour_operator", "travel_service", "tour_agency", "travel_agency")):
        return "guide"
    if any(k in blob for k in ("historic", "landmark", "attraction", "viewpoint", "monument",
                               "archaeo", "castle", "church", "monaster", "park", "nature",
                               "natural", "cave", "waterfall", "scenic", "winery", "island",
                               "reef", "mountain", "hill", "peak", "gorge", "spring", "ancient",
                               "polis", "fort", "lighthouse", "ruin", "temple", "palace",
                               "lake", "land_feature")):
        return "todo"
    if any(k in t for k in ("store", "shop", "market", "retail", "boutique", "grocery")):
        return "shop"
    return None


def clean(s):
    if not isinstance(s, str):
        return s
    s = s.replace("�", "")
    s = "".join(c for c in s if unicodedata.category(c)[0] != "C")
    return re.sub(r"\s{2,}", " ", s).strip()


def fetch_json(url, timeout=120, tries=3):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                       "Accept": "application/json"})
            return json.load(urllib.request.urlopen(req, timeout=timeout))
        except Exception as exc:
            if attempt == tries - 1:
                raise
            print("   retrying (%s)" % type(exc).__name__, flush=True)
            time.sleep(6)


# ---------------------------------------------------------------- bounding box

def resolve_bbox(name):
    """Look a destination name up and return (south, west, north, east)."""
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": name, "format": "json", "limit": 1, "polygon_geojson": 0})
    hits = fetch_json(url, timeout=45)
    if not hits:
        raise SystemExit("Could not find '%s'. Pass --bbox south,west,north,east instead." % name)
    s, n, w, e = (float(x) for x in hits[0]["boundingbox"])
    print("   %s -> %.3f,%.3f to %.3f,%.3f" % (hits[0].get("display_name", name)[:60], s, w, n, e))
    return s, w, n, e


# ---------------------------------------------------------------- overture

def overture_files():
    """Newest Overture release, as a list of https URLs for the places theme."""
    import xml.etree.ElementTree as ET
    url = BUCKET + "?list-type=2&delimiter=/&prefix=release/"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    xml = urllib.request.urlopen(req, timeout=60).read().decode()
    releases = sorted(re.findall(r"<Prefix>release/([^<]+)/</Prefix>", xml))
    if not releases:
        raise SystemExit("Could not list Overture releases.")
    rel = releases[-1]
    url = BUCKET + "?list-type=2&prefix=" + urllib.parse.quote(
        "release/%s/theme=places/type=place/" % rel) + "&max-keys=400"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    xml = urllib.request.urlopen(req, timeout=60).read().decode()
    keys = [k for k in re.findall(r"<Key>([^<]+)</Key>", xml) if k.endswith(".parquet")]
    print("   Overture release %s, %d files" % (rel, len(keys)))
    return rel, [BUCKET + k for k in keys]


def overture_places(urls, bbox):
    import duckdb
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        os.environ.pop(key, None)  # the bucket is public; injected keys cause a 403
    s, w, n, e = bbox
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    listing = "[" + ",".join("'%s'" % u for u in urls) + "]"
    sql = """
        SELECT names.primary, taxonomy.primary, basic_category,
               taxonomy.hierarchy, taxonomy.alternates,
               ROUND(bbox.xmin, 5), ROUND(bbox.ymin, 5), confidence,
               CASE WHEN len(websites)  > 0 THEN websites[1]            ELSE '' END,
               CASE WHEN len(addresses) > 0 THEN addresses[1].locality  ELSE '' END,
               CASE WHEN len(addresses) > 0 THEN addresses[1].freeform  ELSE '' END,
               CASE WHEN len(phones)    > 0 THEN phones[1]              ELSE '' END
        FROM read_parquet({files})
        WHERE bbox.xmin BETWEEN {w} AND {e}
          AND bbox.ymin BETWEEN {s} AND {n}
          AND names.primary IS NOT NULL
    """.format(files=listing, w=w, e=e, s=s, n=n)
    return con.execute(sql).fetchall()


# ---------------------------------------------------------------- wikidata

def wikidata(bbox, tiles=3):
    """Landmarks and photographs (P18) inside the box, from Wikidata."""
    s, w, n, e = bbox
    endpoint = "https://query.wikidata.org/sparql"
    places, photos = [], []
    for i in range(tiles):
        for j in range(tiles):
            bs = s + (n - s) * j / tiles
            bn = s + (n - s) * (j + 1) / tiles
            bw = w + (e - w) * i / tiles
            be = w + (e - w) * (i + 1) / tiles
            q = """SELECT ?iLabel ?tLabel ?coord ?img WHERE {
  SERVICE wikibase:box { ?i wdt:P625 ?coord .
    bd:serviceParam wikibase:cornerSouthWest "Point(%f %f)"^^geo:wktLiteral .
    bd:serviceParam wikibase:cornerNorthEast "Point(%f %f)"^^geo:wktLiteral . }
  ?i wdt:P31 ?t .
  OPTIONAL { ?i wdt:P18 ?img }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,el,sw,id,fr,de". }
} LIMIT 2000""" % (bw, bs, be, bn)
            url = endpoint + "?" + urllib.parse.urlencode({"query": q, "format": "json"})
            try:
                res = fetch_json(url, timeout=120, tries=2)
            except Exception:
                print("   wikidata tile failed, continuing", flush=True)
                continue
            for b in res["results"]["bindings"]:
                label = b.get("iLabel", {}).get("value", "")
                if not label or re.fullmatch(r"Q\d+", label):
                    continue
                m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", b["coord"]["value"])
                if not m:
                    continue
                lon, lat = float(m.group(1)), float(m.group(2))
                kind = b.get("tLabel", {}).get("value", "")
                places.append((label, kind, lat, lon))
                if b.get("img"):
                    photos.append((label, lat, lon, b["img"]["value"]))
            time.sleep(1)
    return places, photos


# ---------------------------------------------------------------- scoring

def auto_discovery(rows):
    """Draft a Discovery score from how crowded a place's surroundings are.

    Calibrated against six measured Cretan beaches: mean error 0.42.
    It measures REMOTENESS, not crowding - Balos reads 8.0 against a measured 6,
    because density cannot see four hundred people off a tour boat.
    """
    near, wide = 0.0045, 0.018          # roughly 500 m and 2 km
    g_near, g_wide = collections.defaultdict(int), collections.defaultdict(int)
    for r in rows:
        g_near[(r[7], int(r[2] / near), int(r[3] / near))] += 1
        g_wide[(r[7], int(r[2] / wide), int(r[3] / wide))] += 1
    for r in rows:
        n5 = sum(g_near.get((r[7], int(r[2] / near) + i, int(r[3] / near) + j), 0)
                 for i in (-1, 0, 1) for j in (-1, 0, 1)) - 1
        n2 = sum(g_wide.get((r[7], int(r[2] / wide) + i, int(r[3] / wide) + j), 0)
                 for i in (-1, 0, 1) for j in (-1, 0, 1)) - 1
        score = 10 - 2.3 * math.log10(1 + max(n5, 0)) - 0.5 * math.log10(1 + max(n2, 0))
        if r[8]:                         # has a website
            score -= 0.5
        if r[10]:                        # has a phone number
            score -= 0.5
        r[11] = max(1, min(10, round(score * 2) / 2))


def attach_photos(rows, photos, dest_id):
    """Only landmarks get a photograph, and only on a confident name match.

    Loose matching put a photograph of a village on every taverna standing in it,
    which is worse than no photograph at all.
    """
    landmarks = {"beach", "todo", "indoor"}
    norm = lambda s: re.sub(r"[^a-z0-9]+", "", s.lower())
    cand = [(norm(nm), lat, lon, img) for nm, lat, lon, img in photos if norm(nm)]
    hits = 0
    for r in rows:
        if r[7] != dest_id or r[1] not in landmarks:
            continue
        rn, best = norm(r[0]), None
        for nn, lat, lon, img in cand:
            dist = math.hypot((lat - r[2]) * 111, (lon - r[3]) * 91)
            if dist > 0.35:
                continue
            exact = nn == rn
            if not (exact or (len(nn) >= 6 and (nn in rn or rn in nn))):
                continue
            rank = (0 if exact else 1, dist)
            if best is None or rank < best[0]:
                best = (rank, img)
        if best:
            r[12] = best[1]
            hits += 1
    return hits


# ---------------------------------------------------------------- registry

def load(path, default):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return default


def save_all(rows, registry):
    os.makedirs(SITE, exist_ok=True)
    with open(DATA, "w") as fh:
        json.dump({"f": FIELDS, "r": rows}, fh, ensure_ascii=False, separators=(",", ":"))
    with open(REG, "w") as fh:
        json.dump(registry, fh, ensure_ascii=False, indent=2)
    mb = os.path.getsize(DATA) / 1e6
    print("\n   site/data.json  %d places, %.1f MB" % (len(rows), mb))
    if mb > 15:
        print("   WARNING: over 15 MB. Re-run large destinations without --include-shops,")
        print("            or split data.json per destination.")


# ---------------------------------------------------------------- commands

def cmd_add(args):
    existing = load(DATA, {"r": []})["r"]
    registry = load(REG, [])

    bbox = tuple(float(x) for x in args.bbox.split(",")) if args.bbox else None
    print("1. Locating %s" % args.name)
    if bbox is None:
        bbox = resolve_bbox(args.name)
    else:
        print("   bbox given: %.3f,%.3f to %.3f,%.3f" % bbox)

    slug = re.sub(r"[^a-z0-9]+", "-", args.name.lower()).strip("-")
    known = [d for d in registry if d["slug"] == slug]
    dest_id = known[0]["id"] if known else (max([d["id"] for d in registry], default=-1) + 1)
    rows = [r for r in existing if r[7] != dest_id]
    if known:
        print("   replacing the existing entry for %s (id %d)" % (args.name, dest_id))

    print("2. Querying Overture")
    rel, urls = overture_files()
    raw = overture_places(urls, bbox)
    print("   %s places in the box" % format(len(raw), ","))

    print("3. Categorising")
    keep = set(CATEGORIES if args.include_shops else TRAVEL)
    seen = {(r[7], r[0].lower(), round(r[2], 3), round(r[3], 3)) for r in rows}
    added, dropped, dupes = 0, 0, 0
    for p in raw:
        cat = categorise(p[1], p[2], p[3], p[4])
        if cat not in keep:
            dropped += 1
            continue
        name = clean(p[0])
        if len(name) < 2:
            dropped += 1
            continue
        key = (dest_id, name.lower(), round(p[6], 3), round(p[5], 3))
        if key in seen:
            dupes += 1
            continue
        seen.add(key)
        rows.append([name, cat, round(p[6], 5), round(p[5], 5),
                     round(p[7], 2) if p[7] else 0.0, clean(p[9]),
                     clean(p[1] or p[2]).replace("_", " "), dest_id,
                     clean(p[8]), clean(p[10]), clean(p[11]), 0, ""])
        added += 1
    print("   kept %s | dropped %s (wrong category) | %s duplicates"
          % (format(added, ","), format(dropped, ","), format(dupes, ",")))

    print("4. Wikidata landmarks and photographs")
    wd_places, wd_photos = wikidata(bbox)
    wd_added = 0
    for label, kind, lat, lon in wd_places:
        cat = categorise("", "", [kind], [])
        if cat is None and any(k in kind.lower() for k in
                               ("archaeolog", "ancient", "monaster", "island", "reef",
                                "mountain", "hill", "cave", "gorge", "beach", "church",
                                "castle", "village", "settlement")):
            cat = "beach" if "beach" in kind.lower() else "todo"
        if cat not in keep:
            continue
        name = clean(label)
        key = (dest_id, name.lower(), round(lat, 3), round(lon, 3))
        if len(name) < 2 or key in seen:
            continue
        seen.add(key)
        rows.append([name, cat, round(lat, 5), round(lon, 5), 0.0, "",
                     clean(kind), dest_id, "", "", "", 0, ""])
        wd_added += 1
    print("   %s landmarks added | %s photographs found"
          % (format(wd_added, ","), format(len(wd_photos), ",")))

    print("5. Scoring and matching photographs")
    auto_discovery(rows)
    pics = attach_photos(rows, wd_photos, dest_id)
    print("   auto-Discovery written for every place")
    print("   %s photographs attached (landmarks only, confident matches only)" % format(pics, ","))

    mine = [r for r in rows if r[7] == dest_id]
    counts = collections.Counter(r[1] for r in mine)
    registry = [d for d in registry if d["id"] != dest_id]
    registry.append({"id": dest_id, "slug": slug, "name": args.name,
                     "bbox": list(bbox), "places": len(mine), "photos": pics,
                     "source": "overture %s + wikidata" % rel,
                     "indexed": time.strftime("%Y-%m-%d"),
                     "counts": dict(counts)})
    registry.sort(key=lambda d: d["id"])
    save_all(rows, registry)

    print("\n   %s: %s places" % (args.name, format(len(mine), ",")))
    for cat, n in counts.most_common():
        print("      %-10s %s" % (cat, format(n, ",")))
    print("\n   Add it to the site: DESTS and MIDLAT in site/app.js")
    print('      [%d,"%s"]   midlat %.2f' % (dest_id, args.name, (bbox[0] + bbox[2]) / 2))


def cmd_list(args):
    registry = load(REG, [])
    if not registry:
        print("No destinations indexed yet.")
        return
    print("%-3s %-22s %9s %7s  %s" % ("id", "destination", "places", "photos", "indexed"))
    for d in registry:
        print("%-3d %-22s %9s %7s  %s"
              % (d["id"], d["name"][:22], format(d["places"], ","),
                 format(d.get("photos", 0), ","), d.get("indexed", "?")))
    total = sum(d["places"] for d in registry)
    print("%-26s %9s" % ("total", format(total, ",")))


def cmd_remove(args):
    registry = load(REG, [])
    target = [d for d in registry if d["name"].lower() == args.name.lower()
              or d["slug"] == args.name.lower()]
    if not target:
        raise SystemExit("'%s' is not indexed." % args.name)
    dest_id = target[0]["id"]
    rows = [r for r in load(DATA, {"r": []})["r"] if r[7] != dest_id]
    registry = [d for d in registry if d["id"] != dest_id]
    save_all(rows, registry)
    print("   removed %s" % target[0]["name"])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="index a destination")
    a.add_argument("name")
    a.add_argument("--bbox", help="south,west,north,east (skips the name lookup)")
    a.add_argument("--include-shops", action="store_true",
                   help="keep shops and markets as well as the travel categories")
    a.set_defaults(func=cmd_add)

    b = sub.add_parser("list", help="show what is indexed")
    b.set_defaults(func=cmd_list)

    c = sub.add_parser("remove", help="drop a destination")
    c.add_argument("name")
    c.set_defaults(func=cmd_remove)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
