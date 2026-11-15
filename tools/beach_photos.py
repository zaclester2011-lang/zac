#!/usr/bin/env python3
"""Give each beach a photograph of that beach, found by name across all of Commons.

Proximity does not establish identity. Attaching the nearest beach photograph
gave Damnoni a picture of Ammoudaki and Balos a picture of a taverna, which is
the same failure as the dive resort illustrated by a number plate — the subject
was merely nearby.

So the beach's own distinctive word has to appear in the filename, and the file
has to be a beach photograph, and it has to sit within the destination. The 43
million geotagged titles are scanned once for anything whose name says beach in
any of the languages these destinations use, and those are indexed by word; a
beach then looks itself up.

    python3 tools/beach_photos.py            # show what it would attach
    python3 tools/beach_photos.py --write
"""

import argparse, collections, math, os, re, sqlite3, time, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "index.db")

BEACHWORD = re.compile(r"""(?ix) (
    beach|strand|seashore|seaside|shoreline|coastline|
    playa|platja|praia|plage|spiaggia|cala|calanque|caleta|
    paralia|akti|lagoon|lagoa|laguna|cove|bay|baie|bahia|baia|
    sandbar|dunes|shingle|pantai|pwani
  )""")

JUNK = re.compile(r"""(?ix) \b(
    map|plan|diagram|chart|logo|sign|signpost|plaque|notice|poster|menu|
    parking|car.park|roundabout|bus|tram|train|aircraft|airport|
    museum|church|interior|bathroom|
    plate|licence|license|portrait|selfie|statue|grave|cemetery
  )\b""")

GENERIC = set("""beach beaches playa platja praia spiaggia paralia plage strand cala cove bay baia
coast shore the and of de la le el los las il lo du des von der sand sandy sea seaside
beachfront north south east west grande piccola nova velha new old view panorama panoramio
aerial island islands resort hotel club taverna""".split())

# a word on more than this many beaches in a destination is a place name, not a beach
LOCAL_AT = 3


def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def words(s):
    return [t for t in re.findall(r"[a-z0-9]+", norm(s)) if len(t) >= 4 and t not in GENERIC]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--max-km", type=float, default=60.0)
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    t0 = time.time()

    # one pass over the titles that could be a beach photograph
    like = " OR ".join("title LIKE ?" for _ in range(12))
    pats = ["%each%", "%laya%", "%latja%", "%raia%", "%piaggia%", "%aralia%",
            "%lage%", "%trand%", "%ala %", "%ove%", "%agoon%", "%antai%"]
    by_word = collections.defaultdict(list)
    seen = 0
    for title, plat, plon in con.execute(
            "SELECT title, lat, lon FROM photo WHERE %s" % like, pats):
        if not title or not title.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        plain = title.replace("_", " ")
        if not BEACHWORD.search(plain) or JUNK.search(plain):
            continue
        seen += 1
        ws = set(words(plain))
        for w in ws:
            by_word[w].append((title, plat, plon))
    print("%s beach photographs on Commons, %s distinct words in their names (%.0fs)"
          % (format(seen, ","), format(len(by_word), ","), time.time() - t0), flush=True)

    beaches = con.execute("""SELECT id, dest, name, lat, lon, photo_title
                             FROM place WHERE category='beach'""").fetchall()
    df = collections.defaultdict(collections.Counter)
    for pid, d, name, lat, lon, cur in beaches:
        for w in set(words(name)):
            df[d][w] += 1

    claims = {}
    for pid, d, name, lat, lon, cur in beaches:
        if cur:
            continue                       # already keeps a picture that names it
        ident = {w for w in set(words(name)) if df[d][w] <= LOCAL_AT}
        pick = None
        for w in ident:
            for title, plat, plon in by_word.get(w, ()):
                if plat is None:
                    continue
                dy = (plat - lat) * 111.0
                dx = (plon - lon) * 111.0 * math.cos(math.radians(lat))
                km = math.hypot(dy, dx)
                if km > args.max_km:
                    continue               # same name, wrong country
                score = (len(w), -km)
                if pick is None or score > pick[0]:
                    pick = (score, title, km)
        if pick:
            claims[pid] = pick

    # one file, one beach
    best_for_title = {}
    for pid, (score, title, km) in claims.items():
        cur = best_for_title.get(title)
        if cur is None or score > cur[0]:
            best_for_title[title] = (score, pid, km)
    final = {pid: (title, km) for title, (sc, pid, km) in best_for_title.items()}

    print("beaches needing a picture : %s" % format(sum(1 for b in beaches if not b[5]), ","))
    print("found one that names them : %s" % format(len(claims), ","))
    print("after one-picture-one-beach: %s" % format(len(final), ","))

    if args.write:
        con.executemany("UPDATE place SET photo_title=? WHERE id=?",
                        [(t, pid) for pid, (t, km) in final.items()])
        con.commit()
        n = con.execute("SELECT count(*) FROM place WHERE category='beach' "
                        "AND photo_title IS NOT NULL").fetchone()[0]
        print("\n%s beaches carry a photograph" % format(n, ","))
    else:
        names = dict((r[0], r[2]) for r in beaches)
        for pid, (t, km) in list(final.items())[:14]:
            print("   %-32s <- %-46s %.1f km" % (names[pid][:32], t[:46], km))
        print("\n(dry run — pass --write to apply)")


if __name__ == "__main__":
    main()
