#!/usr/bin/env python3
"""Per-beach water-colour summary from Flickr user photos.

Rejects night, sunset and underwater frames, then reports across the
accepted daylight photos:
    TYPICAL  - median shade class
    PALEST   - the palest water seen (the shallow strip at its best)
    RANGE    - how far the beach swings between photos
"""
import sys, json, os, re, subprocess, colorsys, statistics
from collections import Counter
from PIL import Image

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
OUT = os.path.dirname(os.path.abspath(__file__)) + "/fl"
os.makedirs(OUT, exist_ok=True)


def cls(hue, s, v):
    if s < 0.12:
        return "grey"
    if hue < 145:
        return "green"
    if hue < 168:
        return "emerald"
    if hue < 194:
        return "TURQUOISE"
    if hue < 207:
        return "blue-green"
    if hue < 227:
        return "plain blue"
    return "deep blue"


RANK = {"grey": 0, "deep blue": 1, "plain blue": 2, "blue-green": 3,
        "TURQUOISE": 4, "emerald": 4, "green": 3}


def photo(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    im = im.resize((240, max(1, int(240 * h / w))))
    px = list(im.getdata())
    meanv = sum(max(p) for p in px) / len(px) / 255
    if meanv < 0.34:                       # night / deep sunset
        return None
    warm = sum(1 for p in px if p[0] > p[2] + 40) / len(px)
    if warm > 0.55:                        # orange sunset cast
        return None
    body = px[int(len(px) * 0.28):]        # drop sky band
    water = [p for p in body
             if p[2] >= p[0] and max(p) > 70
             and (max(p) - min(p)) / max(p) > 0.14]
    if len(water) < 200:
        return None
    hs = []
    for r, g, b in water:
        hh, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        hs.append((hh * 360, s, v, (r, g, b)))
    hs.sort(key=lambda t: -t[2])           # brightest first
    pal = hs[max(0, len(hs) // 20)]        # 5th percentile brightest = shore strip
    med_hue = statistics.median(t[0] for t in hs)
    med_s = statistics.median(t[1] for t in hs)
    med_v = statistics.median(t[2] for t in hs)
    return {"typ": cls(med_hue, med_s, med_v),
            "pal": pal[3], "pal_cls": cls(pal[0], pal[1], pal[2])}


def beach(label, tags, limit=8):
    url = ("https://api.flickr.com/services/feeds/photos_public.gne?tags="
           + tags + "&tag_mode=all&format=json&nojsoncallback=1")
    raw = subprocess.run(["curl", "-sL", "--max-time", "30", "-A", UA, url],
                         capture_output=True, text=True, errors="ignore").stdout
    try:
        items = json.loads(raw).get("items", [])
    except Exception:
        items = []
    if not items:
        print(f"{label:26s} —   no Flickr photos")
        return
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower())
    res = []
    for i, it in enumerate(items[:limit]):
        p = f"{OUT}/{slug}_{i}.jpg"
        subprocess.run(["curl", "-sL", "--max-time", "30", "-A", UA,
                        it["media"]["m"].replace("_m.jpg", "_b.jpg"), "-o", p],
                       capture_output=True)
        if not (os.path.exists(p) and os.path.getsize(p) > 25000):
            continue
        try:
            r = photo(p)
        except Exception:
            r = None
        if r:
            res.append(r)
    if not res:
        print(f"{label:26s} —   {len(items)} photo(s), none usable")
        return
    typs = [r["typ"] for r in res]
    best = max(res, key=lambda r: (RANK.get(r["pal_cls"], 0), sum(r["pal"])))
    common = Counter(typs).most_common(1)[0][0]
    rng = sorted(set(typs), key=lambda t: RANK.get(t, 0))
    print(f"{label:26s} n={len(res):<2d} typical={common:<11s} "
          f"palest=#%02X%02X%02X %-10s range: %s" %
          (best['pal'][0], best['pal'][1], best['pal'][2], best['pal_cls'],
           " → ".join(rng)))


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        lab, tags = arg.split("=", 1)
        beach(lab, tags)
