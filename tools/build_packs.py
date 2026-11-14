#!/usr/bin/env python3
"""Build the destination packs the front page is made of.

One row per destination: where it is, how many places it holds, a photograph
to lead with, its ten best things, and the counts that let a plain-English
question ("hidden water body") rank destinations against each other.

    python3 tools/build_packs.py

Writes site/packs.json and one site/d/<id>.json per destination.
"""

import json, os, sqlite3, collections, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "index.db")
SITE = os.path.join(ROOT, "site")
PFX = "https://commons.wikimedia.org/wiki/Special:FilePath/"
MAX_PER_DEST = 14000          # what the browser gets; the database keeps everything
HIDDEN = 7.0                  # the Discovery floor that counts as "hidden"

# continents by bounding box — crude but it only has to sort twenty-odd places
def continent(lat, lon):
    if lat > 12 and -170 < lon < -50: return "North America"
    if lat <= 12 and -92 < lon < -34: return "South America"
    if -60 < lat < 12 and -92 < lon < -30: return "South America"
    if 34 < lat < 72 and -32 < lon < 45: return "Europe"
    if -36 < lat <= 38 and -20 < lon < 52: return "Africa"
    if lat > 0 and 25 < lon < 180: return "Asia"
    if -12 < lat <= 25 and 60 < lon < 150: return "Asia"
    if lat <= 0 and (110 < lon <= 180 or -180 <= lon < -120): return "Oceania"
    if lat < -50: return "Antarctic"
    return "Asia"

CATS = ["beach", "adventure", "food", "club", "todo", "hotel", "indoor", "shop", "guide"]
TOP_SPREAD = ["beach", "todo", "food", "adventure", "club", "indoor", "hotel", "shop"]


def local_name(title):
    return hashlib.sha1(title.encode("utf-8")).hexdigest()[:16] + ".jpg"


COLOURS = {}
try:
    COLOURS = json.load(open(os.path.join(SITE, "colours.json")))
except Exception:
    pass


def strip(url):
    if not url:
        return ""
    if url.startswith(PFX):
        return url[len(PFX):].replace("?width=480", "")
    return "" if not url.startswith("http") else url


def main():
    con = sqlite3.connect(DB)
    dests = con.execute("""SELECT id, slug, name, south, west, north, east
                           FROM destination ORDER BY id""").fetchall()
    os.makedirs(os.path.join(SITE, "d"), exist_ok=True)
    packs = []
    for did, slug, name, s, w, n, e in dests:
        rows = con.execute(
            """SELECT name, category, lat, lon, confidence, locality, kind, website,
                      discovery_auto, photo, stars, photo_title
               FROM place WHERE dest=?
               ORDER BY (photo IS NULL OR photo NOT LIKE 'http%'), confidence DESC
               LIMIT ?""", (did, MAX_PER_DEST)).fetchall()
        if not rows:
            continue
        out = []
        for r in rows:
            title = r[11] or ""
            col = COLOURS.get(title)
            out.append([r[0], r[1], round(r[2], 4), round(r[3], 4), round(r[4] or 0, 2),
                        r[5] or "", r[6] or "", r[7] or "", r[8],
                        local_name(title) if title else "", r[10] or "",
                        [col["hue"], col["sat"]] if col else None, title])
        with open(os.path.join(SITE, "d", "%d.json" % did), "w") as fh:
            json.dump({"f": ["n", "c", "lat", "lon", "q", "loc", "k", "w", "ad",
                             "img", "stars", "col", "credit"],
                       "r": out}, fh, ensure_ascii=False, separators=(",", ":"))

        counts = collections.Counter(r[1] for r in out)
        hidden = collections.Counter(r[1] for r in out if (r[8] or 0) >= HIDDEN)
        withpic = [r for r in out if r[9]]

        # ten best things: a spread across categories, best known first, always with a picture
        picked, seen = [], set()
        for rounds in range(4):
            for c in TOP_SPREAD:
                if len(picked) >= 10:
                    break
                pool = [r for r in withpic if r[1] == c and r[0] not in seen]
                if len(pool) > rounds:
                    r = pool[rounds]
                    picked.append({"n": r[0], "c": r[1], "img": r[9], "ad": r[8],
                                   "k": r[6], "loc": r[5], "col": r[11],
                                   "credit": r[12], "w": r[7]})
                    seen.add(r[0])
            if len(picked) >= 10:
                break
        hero = hero_title = ""
        for r in withpic:
            if r[1] in ("beach", "todo"):
                hero, hero_title = r[9], r[12]; break
        if not hero and withpic:
            hero, hero_title = withpic[0][9], withpic[0][12]

        packs.append({
            "id": did, "slug": slug, "name": name,
            "continent": continent((s + n) / 2, (w + e) / 2),
            "bbox": [s, w, n, e],
            "places": con.execute("SELECT count(*) FROM place WHERE dest=?", (did,)).fetchone()[0],
            "shown": len(out),
            "photos": len(withpic),
            "hero": hero, "hero_title": hero_title,
            "counts": {c: counts.get(c, 0) for c in CATS},
            "hidden": {c: hidden.get(c, 0) for c in CATS},
            "top": picked,
        })
        print("%-16s %-14s %7s places  %6s photos  top %d"
              % (name, packs[-1]["continent"], format(packs[-1]["places"], ","),
                 format(len(withpic), ","), len(picked)))

    with open(os.path.join(SITE, "packs.json"), "w") as fh:
        json.dump(packs, fh, ensure_ascii=False, separators=(",", ":"))
    size = os.path.getsize(os.path.join(SITE, "packs.json")) / 1e6
    print("\n%d packs, packs.json %.2f MB" % (len(packs), size))


if __name__ == "__main__":
    main()
