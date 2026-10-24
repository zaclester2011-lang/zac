#!/usr/bin/env python3
"""Fetch a cretanbeaches beach page, pull its own photos, report water shades.

Usage:  water.py <label> <page-url>
Prints the top water-colour clusters as hex + a named shade, from palest
(shallow shore strip) to deepest (open-water body).
"""
import sys, re, os, subprocess, colorsys
from collections import Counter
from PIL import Image

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
OUT = os.path.dirname(os.path.abspath(__file__)) + "/pics"
os.makedirs(OUT, exist_ok=True)


def name(r, g, b):
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    hue, pre = h * 360, ""
    if s < 0.12:
        return "grey / colourless"
    if v < 0.40:
        pre = "dark "
    elif v > 0.78 and s < 0.55:
        pre = "pale "
    if hue < 145:
        base = "green"
    elif hue < 168:
        base = "emerald"
    elif hue < 194:
        base = "TURQUOISE"
    elif hue < 207:
        base = "blue-green  (γαλαζοπράσινο)"
    elif hue < 227:
        base = "plain blue  (γαλάζιο)"
    else:
        base = "deep blue  (βαθύ μπλε)"
    return pre + base


def water_pixels(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    im = im.crop((0, int(h * 0.30), w, h))
    im = im.resize((240, max(1, int(240 * im.size[1] / im.size[0]))))
    out = []
    for r, g, b in im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata():
        if b < r:                       # rock, sand, skin, vegetation
            continue
        mx, mn = max(r, g, b), min(r, g, b)
        s = 0 if mx == 0 else (mx - mn) / mx
        if s < 0.14:                    # grey
            continue
        if b < 60 and g < 60:           # near-black
            continue
        out.append((r, g, b))
    return out, im.size[0] * im.size[1]


def report(label, paths):
    allpx, tot = [], 0
    for p in paths:
        try:
            px, n = water_pixels(p)
        except Exception:
            continue
        allpx += px
        tot += n
    if len(allpx) < 150:
        print(f"{label:24s} no water detected in {len(paths)} photo(s)")
        return
    buckets = Counter((r // 18, g // 18, b // 18) for r, g, b in allpx)
    t = sum(buckets.values())
    rows = []
    for key, c in buckets.most_common(14):
        pct = 100 * c / t
        if pct < 5:
            continue
        sel = [p for p in allpx if (p[0] // 18, p[1] // 18, p[2] // 18) == key]
        cen = tuple(sum(x[i] for x in sel) // len(sel) for i in range(3))
        rows.append((cen, pct))
    rows.sort(key=lambda r: -sum(r[0]))          # palest first
    print(f"\n{label}   [{len(paths)} photo(s), water {100*len(allpx)/tot:.0f}% of frame]")
    for cen, pct in rows[:4]:
        print("    #%02X%02X%02X  %4.0f%%   %s" % (cen[0], cen[1], cen[2], pct, name(*cen)))


def fetch(label, url):
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower())
    html = subprocess.run(["curl", "-sL", "--max-time", "35", "-A", UA, url],
                          capture_output=True, text=True, errors="ignore").stdout
    urls = sorted(set(re.findall(r'/images/stories/beaches/[^"\'\s]+?\.(?:jpg|jpeg|JPG)', html)))
    paths = []
    for i, u in enumerate(urls[:4]):
        p = f"{OUT}/{slug}_{i}.jpg"
        subprocess.run(["curl", "-sL", "--max-time", "35", "-A", UA,
                        "https://www.cretanbeaches.com" + u, "-o", p], capture_output=True)
        if os.path.getsize(p) > 20000:
            paths.append(p)
    if not paths:
        print(f"{label:24s} NO PHOTOS FOUND on page")
        return []
    report(label, paths)
    return paths


if __name__ == "__main__":
    fetch(sys.argv[1], sys.argv[2])
