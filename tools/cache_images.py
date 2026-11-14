#!/usr/bin/env python3
"""Download the photographs the page needs and store them beside it.

Artifacts refuse images from other hosts, so a page that points at
commons.wikimedia.org shows nothing at all. These are fetched once, scaled
down, and written to site/img/ so the page serves its own pictures.

    python3 tools/cache_images.py --packs            # heroes and the ten best things
    python3 tools/cache_images.py --all --limit 4000 # as many grid photographs as fit

Also measures each photograph's water colour while it has the pixels open,
so Colour stops being a guess: hue and saturation, the same reading used on
the beaches we stood in.
"""

import argparse, colorsys, hashlib, io, json, os, sqlite3, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
IMG = os.path.join(SITE, "img")
DB = os.path.join(ROOT, "data", "index.db")
UA = "hidden-water-index/1.0 (open-data indexing; contact via repository)"
COMMONS = "https://commons.wikimedia.org/wiki/Special:FilePath/"


def local_name(title):
    return hashlib.sha1(title.encode("utf-8")).hexdigest()[:16] + ".jpg"


def water_colour(im):
    """Hue and saturation of the dominant water-like band, or None.

    Looks at the lower-middle of the frame, where sea sits in a beach photo,
    and keeps pixels in the blue-green range. Returns the median reading.
    """
    w, h = im.size
    box = im.crop((int(w * 0.15), int(h * 0.45), int(w * 0.85), int(h * 0.95)))
    box = box.resize((60, 40))
    hs, ss, vs = [], [], []
    for r, g, b in box.getdata():
        hh, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        hue = hh * 360
        if 140 <= hue <= 250 and s > 0.12 and 0.15 < v < 0.97:
            hs.append(hue); ss.append(s); vs.append(v)
    if len(hs) < 150:                      # not enough water in frame to call it
        return None
    hs.sort(); ss.sort(); vs.sort()
    mid = len(hs) // 2
    return {"hue": round(hs[mid], 1), "sat": round(ss[mid], 2), "val": round(vs[mid], 2),
            "share": round(len(hs) / 2400.0, 2)}


def fetch(title, width=420):
    url = COMMONS + urllib.parse.quote(title.replace(" ", "_")) + "?width=%d" % width
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=45).read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--packs", action="store_true", help="only heroes and top-ten pictures")
    ap.add_argument("--all", action="store_true", help="every place that has a photograph")
    ap.add_argument("--limit", type=int, default=100000)
    ap.add_argument("--delay", type=float, default=0.35)
    ap.add_argument("--width", type=int, default=420)
    args = ap.parse_args()
    from PIL import Image

    os.makedirs(IMG, exist_ok=True)
    con = sqlite3.connect(DB)

    titles = []
    if args.packs:
        packs = json.load(open(os.path.join(SITE, "packs.json")))
        for p in packs:
            if p.get("hero"):
                titles.append(p["hero"])
            for t in p.get("top", []):
                if t.get("img"):
                    titles.append(t["img"])
    if args.all:
        for (t,) in con.execute(
                """SELECT photo_title FROM place WHERE photo_title IS NOT NULL
                   ORDER BY (category IN ('beach','todo','adventure')) DESC, confidence DESC
                   LIMIT ?""", (args.limit,)):
            titles.append(t)
    seen, ordered = set(), []
    for t in titles:
        if t and t not in seen:
            seen.add(t); ordered.append(t)
    print("%s photographs to cache" % format(len(ordered), ","), flush=True)

    colours = {}
    got = skipped = failed = 0
    t0 = time.time()
    for i, title in enumerate(ordered, 1):
        path = os.path.join(IMG, local_name(title))
        if os.path.exists(path):
            skipped += 1
        else:
            try:
                raw = fetch(title, args.width)
                im = Image.open(io.BytesIO(raw)).convert("RGB")
                im.thumbnail((args.width, args.width))
                im.save(path, "JPEG", quality=72, optimize=True)
                c = water_colour(im)
                if c:
                    colours[title] = c
                got += 1
            except Exception:
                failed += 1
            time.sleep(args.delay)
        if i % 100 == 0:
            print("   %s/%s | %s new | %s cached already | %s failed | %.0fs"
                  % (format(i, ","), format(len(ordered), ","), format(got, ","),
                     format(skipped, ","), failed, time.time() - t0), flush=True)
    if colours:
        out = os.path.join(SITE, "colours.json")
        old = {}
        if os.path.exists(out):
            try: old = json.load(open(out))
            except Exception: old = {}
        old.update(colours)
        json.dump(old, open(out, "w"), ensure_ascii=False, separators=(",", ":"))
        print("   water colour measured on %s photographs" % format(len(colours), ","))
    total = sum(os.path.getsize(os.path.join(IMG, f)) for f in os.listdir(IMG))
    print("CACHEDONE %s new, %s already there, %s failed, %.1f MB on disk"
          % (format(got, ","), format(skipped, ","), failed, total / 1e6), flush=True)


if __name__ == "__main__":
    main()
