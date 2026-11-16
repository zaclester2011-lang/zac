#!/usr/bin/env python3
"""Build the destination packs the front page is made of.

One row per destination: where it is, how many places it holds, a photograph
to lead with, its ten best things, and the counts that let a plain-English
question ("hidden water body") rank destinations against each other.

    python3 tools/build_packs.py

Writes site/packs.json and one site/d/<id>.json per destination.
"""

import json, os, re, sqlite3, collections, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "index.db")
SITE = os.path.join(ROOT, "site")
PFX = "https://commons.wikimedia.org/wiki/Special:FilePath/"
MAX_PER_DEST = 14000          # what the browser gets; the database keeps everything
QUIET_N2 = 10                 # hidden: at most this many other places within 2 km

# Continents by bounding box — crude, but it only has to sort forty-odd places,
# and it sorts them the way someone planning a trip would. The order matters:
# the first rule that matches wins, so the awkward cases come first.
#
# Four were wrong before the rules were put in this order. Wadi Rum came out
# African because Jordan sits inside the old Africa box. Costa Rica came out
# South American. Réunion came out Asian, having fallen past an Africa box that
# stopped short of it. Madeira and the Canaries came out African, which is true
# of the rock and useless to a traveller flying from Lisbon or Madrid.
def continent(lat, lon):
    # Macaronesia: Portuguese and Spanish islands off Africa, reached from Europe
    if 27 < lat < 40 and -32 < lon < -13: return "Europe"
    # the Middle East, which the old Africa box swallowed
    if 12 < lat < 42 and 34 < lon < 64: return "Asia"
    # Central America and the Caribbean belong to the north
    if 7 < lat < 33 and -118 < lon < -59: return "North America"
    if lat > 12 and -170 < lon < -50: return "North America"
    if -60 < lat <= 12 and -92 < lon < -30: return "South America"
    if 34 < lat < 72 and -32 < lon < 45: return "Europe"
    # Africa with its Indian Ocean islands: Réunion, Mauritius, the Seychelles
    if -36 < lat <= 38 and -20 < lon < 58: return "Africa"
    # The Asian rules stay ahead of Oceania: Bali, Sulawesi, Flores and Raja
    # Ampat are all south of the equator and all in Asia, and the Oceania box
    # would otherwise claim them.
    if lat > 0 and 25 < lon < 180: return "Asia"
    if -12 < lat <= 25 and 60 < lon < 150: return "Asia"
    if lat <= 0 and (110 < lon <= 180 or -180 <= lon < -120): return "Oceania"
    if lat < -50: return "Antarctic"
    return "Asia"

LANDMARK = {
    "New York": ["Times Square", "Central Park", "Brooklyn Bridge", "Statue of Liberty"],
    "Cape Town": ["Table Mountain"],
    "Santorini": ["Oia"],
    "Dubrovnik": ["Old Town", "Lovrijenac"],
    "Capri": ["Faraglioni", "Blue Grotto"],
}

CATS = ["beach", "water", "rock", "trail", "sea"]
# The ten best things are things you travel for. "shop" and "indoor" are out:
# once the barbers were moved out of the bar category into shops, they started
# turning up in Santorini's and Mallorca's top ten, and indoor now also holds
# the notaries and publishers that the same clean-up swept out.
TOP_SPREAD = ["beach", "rock", "water", "trail", "sea"]


def local_name(title):
    return hashlib.sha1(title.encode("utf-8")).hexdigest()[:16] + ".jpg"


COLOURS = {}
try:
    COLOURS = json.load(open(os.path.join(SITE, "colours.json")))
except Exception:
    pass

# heroes chosen by name and then rated — see tools/name_photos.py
HEROES = {}
try:
    HEROES = json.load(open(os.path.join(SITE, "heroes.json")))
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
                      discovery_auto, photo, stars, photo_title, colour,
                      n500, n2km, ncat2km, discovery
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
                        [col["hue"], col["sat"], r[12]] if col else ([None, None, r[12]] if r[12] else None),
                        title, r[13] or 0, r[14] or 0, r[15] or 0, r[16]])
        with open(os.path.join(SITE, "d", "%d.json" % did), "w") as fh:
            json.dump({"f": ["n", "c", "lat", "lon", "q", "loc", "k", "w", "ad",
                             "img", "stars", "col", "credit", "n5", "n2", "nc", "d"],
                       "r": out}, fh, ensure_ascii=False, separators=(",", ":"))

        counts = collections.Counter(r[1] for r in out)
        # Discovery is gone, so "quiet" is counted from what is mapped around a
        # place rather than from a rating of it.
        quiet = collections.Counter(r[1] for r in out if (r[14] or 0) <= QUIET_N2)
        # "Hidden beaches" is a category on the page but not in the data: it is
        # the beaches with almost nothing mapped around them.
        # "Hidden" is the whole point now: any adventure with almost nothing
        # else mapped around it, not just a beach.
        hidden = sum(1 for r in out if (r[14] or 0) <= QUIET_N2)
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
                                   "credit": r[12], "w": r[7], "row": r})
                    seen.add(r[0])
            if len(picked) >= 10:
                break
        hero = hero_title = ""
        if HEROES.get(name):                   # picked by name, measured, best of its candidates
            hero_title = HEROES[name]
            hero = local_name(hero_title)
        wanted = [] if hero else LANDMARK.get(name, [])
        for want in wanted:                    # a destination's signature sight comes first
            for r in withpic:
                if want.lower() in r[0].lower():
                    hero, hero_title = r[9], r[12]; break
            if hero: break
        if not hero:                           # otherwise the brightest water on the books
            best = None
            for r in withpic:
                if r[1] not in ("beach", "todo"): continue
                sc = r[11][2] if (r[11] and r[11][2] is not None) else -1
                if best is None or sc > best[0]: best = (sc, r)
            if best and best[0] > 0: hero, hero_title = best[1][9], best[1][12]
        if not hero and withpic:
            hero, hero_title = withpic[0][9], withpic[0][12]

        # The best-rated water in the destination, so the card can say something
        # real. A beach wins over a dive shop or a boat tour even when the boat
        # tour's photograph scores higher: the claim is about water you can swim
        # in, and a company's photograph need not have been taken at its own door.
        best_col = None
        for prefer_beach in (True, False):
            for r in out:
                if r[1] != "beach" and prefer_beach:
                    continue
                if r[11] and r[11][2] is not None:
                    if best_col is None or r[11][2] > best_col[1]:
                        best_col = (r[0], r[11][2])
            if best_col:
                break
        rated = sum(1 for r in out if r[11] and r[11][2] is not None)

        # What the "what are you looking for" box searches when a word is not a
        # category: the destination, and the names and kinds of the places in it.
        # Without this, typing "navagio" or "cenote" matched nothing and the box
        # quietly ignored it.
        # Distinct WORDS, not whole names: deduplicating the vocabulary fits every
        # place in the destination into the space that 1,200 full names took, which
        # is why "navagio" found nothing before — it sat past the cut.
        toks = {}
        for r in out:
            for piece in (r[0], r[6], r[5]):
                for t in re.findall(r"\w+", (piece or "").lower(), re.UNICODE):
                    if len(t) >= 3:
                        toks[t] = toks.get(t, 0) + 1
        # the hero's own subject counts too: "penguin" is in Cape Town's picture,
        # not in any place name
        for t in re.findall(r"\w+", (hero_title or "").lower().replace("_", " "), re.UNICODE):
            if len(t) >= 3:
                toks[t] = toks.get(t, 0) + 999
        for t in re.findall(r"\w+", name.lower(), re.UNICODE):
            toks[t] = toks.get(t, 0) + 9999
        blob = " ".join(sorted(toks, key=lambda t: -toks[t])[:7000])

        packs.append({
            "id": did, "slug": slug, "name": name,
            "bestcol": list(best_col) if best_col else None,
            "rated": rated,
            "continent": continent((s + n) / 2, (w + e) / 2),
            "bbox": [s, w, n, e],
            "places": con.execute("SELECT count(*) FROM place WHERE dest=?", (did,)).fetchone()[0],
            "shown": len(out),
            "photos": len(withpic),
            "hero": hero, "hero_title": hero_title,
            "counts": {c: counts.get(c, 0) for c in CATS},
            "quiet": {c: quiet.get(c, 0) for c in CATS},
            "hidden": hidden,
            "blob": blob,
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
