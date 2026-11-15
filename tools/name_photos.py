#!/usr/bin/env python3
"""Pick each place's photograph by name, then rate the candidates and keep the best.

The geotag method asks "what was photographed nearest this point". On a Cretan
headland that is the beach. In Manhattan it is a taco shop, which is how Times
Square ended up illustrated by Tacos_Morelos.jpg.

So for places worth a real picture — a destination's lead photograph and its ten
best things — this asks Commons for the place BY NAME, downloads the candidates,
measures each one, and keeps the best. Measuring is the point: "most beautiful
sunny picture" becomes brightness and saturation I can show you, not an adjective.

    python3 tools/name_photos.py --heroes          # one lead picture per destination
    python3 tools/name_photos.py --topten          # the ten best things in each pack

Writes place.photo_title, caches the file into site/img/, and records every
reading in site/colours.json.
"""

import argparse, colorsys, hashlib, io, json, os, re, sqlite3, time
import urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
IMG = os.path.join(SITE, "img")
DB = os.path.join(ROOT, "data", "index.db")
UA = "hidden-water-index/1.0 (travel index; open data)"
API = "https://commons.wikimedia.org/w/api.php"
FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/"

# subjects that are never a destination's lead photograph, however bright
JUNK = re.compile(r"""(?ix) \b(
    map|plan|diagram|chart|logo|flag|coat.of.arms|seal|stamp|coin|banknote|
    plaque|sign|signpost|signage|notice|poster|billboard|menu|receipt|ticket|
    grave|tomb|tombstone|cemetery|memorial.stone|headstone|
    interior|bathroom|toilet|restroom|bedroom|kitchen|corridor|staircase|
    parking|car.park|roadworks|construction|scaffold|crane|
    bus|tram|train|locomotive|wagon|aircraft|airplane|airliner|ambulance|
    fire.engine|police.car|truck|lorry|
    portrait|selfie|mugshot|statue.of.a|bust.of|
    specimen|herbarium|skeleton|taxidermy|insect|beetle|moth|spider|
    screenshot|scan|document|letter|manuscript|invoice
  )\b""")

# a sunset is not "a sunny day"
DARK = re.compile(r"""(?ix) \b(
    sunset|sunrise|dusk|dawn|twilight|evening|night|nocturne|moon|stars|
    storm|rain|rainy|overcast|fog|mist|cloudy|snow|winter|lightning|eclipse
  )\b""")

WATER = re.compile(r"""(?ix) \b(
    beach|bay|cove|lagoon|lagoa|coast|coastline|seaside|sea|ocean|shore|
    spiaggia|playa|plage|praia|strand|cala|calanque|paralia|aerial|
    island|islet|cliff|cliffs|gorge|waterfall|cascade|lake|harbour|harbor|
    turquoise|snorkel|reef|sandbar|peninsula
  )\b""")


def local_name(title):
    return hashlib.sha1(title.encode("utf-8")).hexdigest()[:16] + ".jpg"


def get(url, tries=5):
    """Commons rate-limits anonymous callers hard; back off rather than hammer."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=45).read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or attempt == tries - 1:
                raise
            time.sleep(5 * (attempt + 1))
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")


def wiki_lead(title):
    """The photograph Wikipedia leads its own article with.

    For a landmark this beats any relevance ranking: it is the picture editors
    chose to represent the place. Countries return a flag or a locator map, so
    anything but a photograph is dropped.
    """
    url = ("https://en.wikipedia.org/w/api.php?action=query&format=json&prop=pageimages"
           "&piprop=original&redirects=1&titles=" + urllib.parse.quote(title))
    try:
        data = json.loads(get(url))
    except Exception:
        return None
    for p in ((data.get("query") or {}).get("pages") or {}).values():
        src = (p.get("original") or {}).get("source")
        if not src:
            continue
        name = urllib.parse.unquote(src.rsplit("/", 1)[-1].split("?")[0])
        if not name.lower().endswith((".jpg", ".jpeg", ".png")):
            continue                      # a flag or locator map, not a photograph
        return {"title": name, "w": (p.get("original") or {}).get("width") or 0,
                "h": (p.get("original") or {}).get("height") or 0, "lead": True}
    return None


def search(query, limit=6):
    url = (API + "?action=query&format=json&generator=search&gsrnamespace=6"
           "&gsrsearch=" + urllib.parse.quote(query) +
           "&gsrlimit=%d&prop=imageinfo&iiprop=url|size&iiurlwidth=440" % limit)
    try:
        data = json.loads(get(url))
    except Exception:
        return []
    out = []
    for p in ((data.get("query") or {}).get("pages") or {}).values():
        title = p.get("title", "")
        if not title.lower().startswith("file:"):
            continue
        name = title[5:]
        if not name.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        ii = (p.get("imageinfo") or [{}])[0]
        out.append({"title": name, "w": ii.get("width") or 0, "h": ii.get("height") or 0})
    return out


def read_picture(title, width=440):
    from PIL import Image
    url = FILEPATH + urllib.parse.quote(title.replace(" ", "_")) + "?width=%d" % width
    raw = get(url)
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im.thumbnail((width, width))
    return im


def measure(im):
    """Water colour in the lower frame, plus how bright and sunny the whole frame is."""
    w, h = im.size
    small = im.resize((80, 54))
    px = list(small.getdata())
    vals, sats = [], []
    for r, g, b in px:
        _, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        vals.append(v); sats.append(s)
    vals.sort(); sats.sort()
    mid = len(vals) // 2
    scene = {"val": round(vals[mid], 3), "sat": round(sats[mid], 3),
             "bright": round(sum(1 for v in vals if v > 0.75) / len(vals), 3)}

    box = im.crop((int(w * 0.15), int(h * 0.45), int(w * 0.85), int(h * 0.95))).resize((60, 40))
    hs, ss, vs = [], [], []
    for r, g, b in box.getdata():
        hh, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        hue = hh * 360
        if 140 <= hue <= 250 and s > 0.12 and 0.15 < v < 0.97:
            hs.append(hue); ss.append(s); vs.append(v)
    water = None
    if len(hs) >= 150:
        hs.sort(); ss.sort(); vs.sort()
        m = len(hs) // 2
        water = {"hue": round(hs[m], 1), "sat": round(ss[m], 2), "val": round(vs[m], 2),
                 "share": round(len(hs) / 2400.0, 2)}
    return scene, water


def colour_score(hue, sat, share):
    """My Colour rating, stated so anyone can check it.

    Anchored on Zac's own ratings of measured photographs: Balos 9.5, Seitan 8.5,
    Preveli 8. Returns None when there is too little water in frame to judge.
    """
    if share is None or share < 0.18:
        return None
    s = 4.5 + 7.0 * sat
    if 168 <= hue <= 195:
        s += 1.0                     # the turquoise band
    elif 195 < hue <= 205:
        s += 0.3                     # blue, not turquoise
    elif hue > 215:
        s -= 0.5                     # flat navy
    return max(1.0, min(10.0, round(s * 2) / 2))


def rank(cand, want_water, require=None):
    """Score a candidate photograph. Higher is a better lead picture."""
    title, scene, water = cand["title"], cand["scene"], cand["water"]
    plain = title.replace("_", " ")
    s = 0.0
    if cand.get("lead"):
        s += 5.0                                    # Wikipedia leads its article with this
    if require and not require.search(plain):
        s -= 9.0                                    # not a picture of the thing asked for
    if JUNK.search(plain):
        s -= 8.0
    if WATER.search(plain):
        s += 2.0
    if DARK.search(plain):
        s -= 7.0                                    # a sunset is not a sunny day
    if cand["w"] > cand["h"]:
        s += 1.0                                    # landscape leads a page better
    if cand["w"] < 900:
        s -= 1.0

    # sunny, measured: how much of the frame is bright, and how bright the middle is
    s += 6.0 * scene["bright"]
    s += 2.0 * min(scene["val"], 0.9)
    if scene["bright"] < 0.25:
        s -= 6.0                                    # an overcast or night frame, whatever its title

    if want_water:
        c = colour_score(water["hue"], water["sat"], water["share"]) if water else None
        if c is None:
            s -= 4.0                                # asked for turquoise, got no water
        else:
            s += c + 3.0 * water["share"]
            hue = water["hue"]
            if 168 <= hue <= 195:
                s += 3.0                            # the turquoise band he asked for
            elif hue <= 205:
                s += 0.5
            else:
                s -= 2.0                            # deep blue or navy, not turquoise
    return round(s, 2)


def best_for(queries, want_water, seen, delay=1.0, per=10, keep=3,
             require=None, leads=()):
    """Search, download and measure; return the best-scoring candidate."""
    cands = []
    pool = []
    for article in leads:                           # Wikipedia's own lead photographs first
        hit = wiki_lead(article)
        if hit:
            pool.append(hit)
        time.sleep(0.6)
    for q in queries:
        pool.extend(search(q, per))
        for hit in pool:
            if hit["title"] in seen:
                continue
            seen.add(hit["title"])
            try:
                im = read_picture(hit["title"])
            except Exception:
                continue
            scene, water = measure(im)
            hit.update({"scene": scene, "water": water, "im": im})
            hit["score"] = rank(hit, want_water, require)
            cands.append(hit)
            time.sleep(delay)
        pool = []
        if len([c for c in cands if c["score"] > (14 if want_water else 6)]) >= keep:
            break
    if not cands:
        return None
    cands.sort(key=lambda c: -c["score"])
    return cands[0]


def save(cand, colours):
    path = os.path.join(IMG, local_name(cand["title"]))
    cand["im"].save(path, "JPEG", quality=72, optimize=True)
    if cand["water"]:
        colours[cand["title"]] = cand["water"]
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--heroes", action="store_true")
    ap.add_argument("--topten", action="store_true")
    ap.add_argument("--only", help="one destination name")
    ap.add_argument("--delay", type=float, default=1.2)
    args = ap.parse_args()

    os.makedirs(IMG, exist_ok=True)
    con = sqlite3.connect(DB)
    colours = {}
    if os.path.exists(os.path.join(SITE, "colours.json")):
        try:
            colours = json.load(open(os.path.join(SITE, "colours.json")))
        except Exception:
            colours = {}

    dests = con.execute("SELECT id, name FROM destination ORDER BY id").fetchall()
    if args.only:
        dests = [d for d in dests if d[1].lower() == args.only.lower()]

    # a destination whose lead picture is a city, not a sea
    CITY = {
        "New York": ("Times Square", [r"times\s*square"]),
        "Cape Town": ("Table Mountain", [r"table\s*mountain"]),
    }

    out = {}
    for did, name in dests:
        t0 = time.time()
        seen = set()
        require = None
        if name in CITY:
            landmark, pats = CITY[name]
            queries = ["%s %s" % (landmark, name), landmark]
            leads = [landmark]
            require = re.compile("|".join(pats), re.I)
            want_water = False
        else:
            beaches = [r[0] for r in con.execute(
                """SELECT name FROM place WHERE dest=? AND category='beach'
                   ORDER BY confidence DESC LIMIT 4""", (did,)).fetchall()]
            # Commons' own curated category beats relevance ranking for beaches
            queries = ['incategory:"Beaches of %s"' % name,
                       "%s beach" % name,
                       "%s beach turquoise sea" % name,
                       "%s beach aerial" % name,
                       "%s lagoon" % name]
            queries += ["%s %s" % (b, name) for b in beaches[:2]]
            leads = [("%s (%s)" % (b, name)) if len(b) < 14 else b for b in beaches[:2]]
            want_water = True
        pick = best_for(queries, want_water, seen, delay=args.delay,
                        require=require, leads=leads)
        if not pick:
            print("%-14s no candidate found" % name, flush=True)
            continue
        save(pick, colours)
        out[name] = pick["title"]
        w = pick["water"]
        print("%-14s %-52s score %5.2f  bright %.2f  %s  (%.0fs)"
              % (name, pick["title"][:52], pick["score"], pick["scene"]["bright"],
                 ("water hue %.0f sat %.2f share %.2f" % (w["hue"], w["sat"], w["share"]))
                 if w else "no water in frame", time.time() - t0), flush=True)

    json.dump(colours, open(os.path.join(SITE, "colours.json"), "w"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(out, open(os.path.join(SITE, "heroes.json"), "w"),
              ensure_ascii=False, indent=1)
    print("\nHEROESDONE %d" % len(out), flush=True)


if __name__ == "__main__":
    main()
