#!/usr/bin/env python3
"""Water colour split by lighting: sun vs cloud.

Each photo is classified from its sky band (top 20%):
    SUN    - saturated blue sky, or no sky but strong shadow contrast
    CLOUD  - desaturated white/grey sky, or flat low-contrast light
Water clusters are then reported separately for each class, so you can
see what a beach looks like on a good day and on a grey one.
"""
import sys, json, os, re, subprocess, colorsys, statistics
from PIL import Image

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
OUT = os.path.dirname(os.path.abspath(__file__)) + "/sc"
os.makedirs(OUT, exist_ok=True)


def cls(hue, s):
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


def sat(p):
    mx, mn = max(p), min(p)
    return 0 if mx == 0 else (mx - mn) / mx


def read(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    im = im.resize((240, max(1, int(240 * h / w))))
    px = list(im.getdata())
    W, H = im.size
    if sum(max(p) for p in px) / len(px) / 255 < 0.32:
        return None                                  # night

    sky = px[: int(len(px) * 0.20)]
    sky_s = sum(sat(p) for p in sky) / len(sky)
    sky_v = sum(max(p) for p in sky) / len(sky) / 255
    sky_blue = sum(1 for p in sky if p[2] > p[0] + 18) / len(sky)

    vs = [max(p) / 255 for p in px]
    contrast = statistics.pstdev(vs)

    if sky_blue > 0.55 and sky_s > 0.26:
        light = "SUN"
    elif sky_v > 0.72 and sky_s < 0.16:
        light = "CLOUD"
    elif sky_blue > 0.40 and sky_s > 0.20:
        light = "SUN"
    elif contrast > 0.20:
        light = "SUN"
    else:
        light = "CLOUD"

    body = px[int(len(px) * 0.28):]
    water = [p for p in body if p[2] >= p[0] and max(p) > 70 and sat(p) > 0.14]
    if len(water) < 200:
        return None
    hs = []
    for r, g, b in water:
        hh, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        hs.append((hh * 360, s, v, (r, g, b)))
    hs.sort(key=lambda t: -t[2])
    pal = hs[max(0, len(hs) // 20)]
    return {"light": light,
            "pal": pal[3], "pal_cls": cls(pal[0], pal[1]),
            "med_cls": cls(statistics.median(t[0] for t in hs),
                           statistics.median(t[1] for t in hs))}


RANK = {"grey": 0, "deep blue": 1, "plain blue": 2, "blue-green": 3,
        "green": 3, "TURQUOISE": 4, "emerald": 4}


def beach(label, tags, limit=10):
    url = ("https://api.flickr.com/services/feeds/photos_public.gne?tags="
           + tags + "&tag_mode=all&format=json&nojsoncallback=1")
    raw = subprocess.run(["curl", "-sL", "--max-time", "30", "-A", UA, url],
                         capture_output=True, text=True, errors="ignore").stdout
    try:
        items = json.loads(raw).get("items", [])
    except Exception:
        items = []
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
            r = read(p)
        except Exception:
            r = None
        if r:
            res.append(r)
    if not res:
        print(f"{label:24s}  no usable photos")
        return
    out = [label.ljust(24)]
    for L in ("SUN", "CLOUD"):
        g = [r for r in res if r["light"] == L]
        if not g:
            out.append(f"{L}: —".ljust(34))
            continue
        best = max(g, key=lambda r: (RANK.get(r["pal_cls"], 0), sum(r["pal"])))
        out.append(f"{L}(n={len(g)}): #%02X%02X%02X %s" %
                   (best['pal'][0], best['pal'][1], best['pal'][2], best['pal_cls']))
    print("   ".join(out))


if __name__ == "__main__":
    for a in sys.argv[1:]:
        lab, tags = a.split("=", 1)
        beach(lab, tags)
