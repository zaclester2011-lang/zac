#!/usr/bin/env python3
"""Choose a destination's lead picture from the photographs already indexed here.

tools/new_heroes.py asks Wikipedia for the picture its article leads with, which
is the best answer when there is an article. Some places have none: the Azores
lead with a 960-pixel lake photograph, too small to draw at 1,800, and Raja
Ampat leads with a figure from a journal paper.

This takes the other route. Every geotagged Commons photograph inside the
destination is already in the photo table with its filename, so the candidates
can be found locally by name, and one batched imageinfo call — fifty titles at
a time, which is all an anonymous caller may ask for — gives their real sizes.
The largest sunny landscape wins.

    python3 tools/local_hero.py Azores "Sete Cidades" Fogo Furnas
    python3 tools/local_hero.py Azores "Sete Cidades" --write

Writes site/heroes.json and caches the picture into site/img/.
"""

import argparse, hashlib, io, json, os, re, sqlite3, time
import urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
IMG = os.path.join(SITE, "img")
DB = os.path.join(ROOT, "data", "index.db")
UA = "hidden-adventures/1.0 (travel index; open data)"
API = "https://commons.wikimedia.org/w/api.php"
FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/"

NOTPHOTO = re.compile(r"""(?ix)\b(
    map|locator|topographic|relief|flag|coat.of.arms|seal|logo|diagram|chart|
    graph|profile|cross.section|plan|sign|plaque|portrait|statue|stamp|coin|
    panorama.of.the.map|satellite|aerial.map
  )\b""")
DATED = re.compile(r"\b(18|19)\d{2}\b")


def local_name(title):
    return hashlib.sha1(title.encode("utf-8")).hexdigest()[:16] + ".jpg"


def get(url, tries=4):
    for a in range(tries):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60).read()
        except Exception:
            if a == tries - 1:
                raise
            time.sleep(4 * (a + 1))


def sizes(titles):
    """Real pixel sizes for up to fifty files, in one request."""
    out = {}
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        url = (API + "?action=query&format=json&prop=imageinfo&iiprop=size&titles="
               + urllib.parse.quote("|".join("File:" + t for t in chunk)))
        try:
            data = json.loads(get(url))
        except Exception:
            continue
        for p in ((data.get("query") or {}).get("pages") or {}).values():
            ii = (p.get("imageinfo") or [{}])[0]
            t = p.get("title", "")[5:]
            if ii.get("width"):
                out[t] = (ii["width"], ii["height"])
        time.sleep(1.0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("destination")
    ap.add_argument("words", nargs="+", help="words the filename must contain")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--width", type=int, default=900)
    ap.add_argument("--max-candidates", type=int, default=50)
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    row = con.execute("SELECT south, west, north, east FROM destination WHERE name=?",
                      (args.destination,)).fetchone()
    if not row:
        raise SystemExit("no destination called %r" % args.destination)
    s, w, n, e = row

    pats = [re.compile(re.escape(x), re.I) for x in args.words]
    cands = []
    for (title,) in con.execute(
            """SELECT title FROM photo WHERE title IS NOT NULL
               AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?""", (s, n, w, e)):
        if not title.lower().endswith((".jpg", ".jpeg")):
            continue
        if NOTPHOTO.search(title) or DATED.search(title):
            continue
        if any(p.search(title) for p in pats):
            cands.append(title)
    cands = sorted(set(cands))[:args.max_candidates]
    print("%d candidate photographs named after %s inside %s"
          % (len(cands), " or ".join(args.words), args.destination))
    if not cands:
        return

    dims = sizes(cands)
    ranked = sorted(((w_ * h_, w_, h_, t) for t, (w_, h_) in dims.items()
                     if w_ >= 1600 and w_ > h_), reverse=True)
    for px, w_, h_, t in ranked[:10]:
        print("   %5dx%-5d %s" % (w_, h_, t[:62]))
    if not ranked:
        print("   none of them is a wide photograph of at least 1,600 pixels")
        return

    best = ranked[0][3]
    print("\nchosen: %s" % best)
    if not args.write:
        print("(dry run — pass --write to set it)")
        return

    from PIL import Image
    url = FILEPATH + urllib.parse.quote(best.replace(" ", "_")) + "?width=%d" % args.width
    im = Image.open(io.BytesIO(get(url))).convert("RGB")
    im.thumbnail((args.width, args.width))
    im.save(os.path.join(IMG, local_name(best)), "JPEG", quality=85, optimize=True)
    hpath = os.path.join(SITE, "heroes.json")
    heroes = json.load(open(hpath))
    heroes[args.destination] = best
    json.dump(heroes, open(hpath, "w"), ensure_ascii=False, indent=1)
    print("set as the hero for %s" % args.destination)


if __name__ == "__main__":
    main()
