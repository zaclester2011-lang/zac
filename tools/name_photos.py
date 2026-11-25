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

# A filename like "1017-navagio-beach-728x474.jpg" is a web thumbnail someone
# re-uploaded. It is always small and usually somebody else's copyright.
STOCK = re.compile(r"(?i)\b\d{2,4}x\d{2,4}\b|\b(stock|wallpaper|thumb|download|hd|free)\b")

# An old slide is rarely the most beautiful sunny picture of a place.
DATED = re.compile(r"\b(18|19)\d{2}\b")

# Places whose name belongs to somewhere else as well. Commons' full-text search
# cannot tell them apart, so this says which one is not meant: the Madeira in
# Florida, the Copacabana in Rio. Found by looking at what the search returned.
# The spot a destination is actually known for, where the database's own beach
# list gives a beach bar instead. Used only to ask Wikipedia for its lead picture.
FAMOUS = {
    "Zakynthos": ["Navagio"],
    "Capri":     ["Faraglioni", "Blue Grotto (Capri)"],
    "Madeira":   ["Porto Moniz", "Ponta de São Lourenço"],
    "Dubrovnik": ["Lokrum", "Banje Beach"],
    "Sardinia":  ["Cala Goloritzé", "Cala Mariolu", "La Pelosa"],
    "Algarve":   ["Praia da Marinha", "Benagil"],
    "Mallorca":  ["Es Trenc", "Cala Mondragó", "Sa Calobra"],
    "Iceland":   ["Jökulsárlón", "Seljalandsfoss", "Reynisfjara"],
    "Maui":      ["Kaanapali Beach", "Wailea, Hawaii", "Molokini"],
    "Azores":    ["Sete Cidades (Azores)", "Lagoa do Fogo"],
    "Corsica":   ["Palombaggia", "Scandola Nature Reserve"],
    "Seychelles": ["Anse Source d'Argent", "Anse Lazio"],
    "Palawan":   ["El Nido, Palawan", "Coron, Palawan"],
    "Phuket":    ["Freedom Beach", "Phang Nga Bay"],
    "Bali":      ["Nusa Penida", "Padang Padang Beach"],
    "Tulum":     ["Gran Cenote", "Tulum"],
}

# Chosen by looking at the candidates rather than by score. Dubrovnik's ranking
# kept picking hazy distant views: bright, but the old town is a smudge in them.
# This is the one that actually shows the place, measured at bright 0.45, val 0.72.
PINNED = {
    "Dubrovnik": "Casco viejo de Dubrovnik, Croacia, 2014-04-14, DD 04.JPG",
    # Zac asked for the penguins on white sand; this is the one that shows them
    "Cape Town": "Penguins at Boulders Beach 04.jpg",
    # Zac asked for under the sea at Zanzibar, turquoise, with the yellow and
    # silver fish. Half over and half under at Mnemba: water fills the frame at
    # hue 184 and saturation 0.94, with sergeant majors and one yellow damselfish.
    "Zanzibar": "Mnemba Island - Zanzibar - Flickr - Jorge Lascar.jpg",
    # and a deep blue cenote. Every cenote photograph is dark, because a cenote
    # is a hole in the ground, so the brightness floor threw them all out and
    # left the Maya ruins standing. Measured hue 189, saturation 0.56, and
    # water fills 94% of the frame.
    "Tulum": "Gran cenote Tulum (21379178572).jpg",
}

CONFUSABLE = {
    "Madeira":   r"florida|john'?s\s*pass|intracoastal|ohio|illinois",
    # Dubrovnik has a Copacabana of its own, so only Rio's is ruled out
    "Dubrovnik": r"rio\s*de\s*janeiro|brasil|brazil",
    "Capri":     r"\bford\b|\bmk\s*[iv]+\b|capri\s*(i{1,3}|\d)\b",
    "Tulum":     r"\bflorida\b",
    "Maui":      r"\bcalifornia\b",
}


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


def rank(cand, want_water, require=None, reject=None, here=None, band=(168, 195)):
    """Score a candidate photograph. Higher is a better lead picture."""
    title, scene, water = cand["title"], cand["scene"], cand["water"]
    plain = title.replace("_", " ")
    s = 0.0
    if cand.get("lead"):
        s += 5.0                                    # Wikipedia leads its article with this
    if require and not require.search(plain):
        s -= 9.0                                    # not a picture of the thing asked for
    if reject and reject.search(plain):
        s -= 12.0                                   # a different place with the same name
    if here and here.search(plain):
        s += 3.0                                    # names this destination, so it is here
    if STOCK.search(plain):
        s -= 10.0                                   # a re-uploaded web thumbnail
    if DATED.search(plain):
        s -= 3.0
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
            # normally the turquoise band Zac asked for, but a destination can
            # ask for a different water: a cenote is meant to be deep blue
            if band[0] <= hue <= band[1]:
                s += 3.0
            elif abs(hue - band[0]) <= 10 or abs(hue - band[1]) <= 10:
                s += 0.5
            else:
                s -= 2.0
    return round(s, 2)


def best_for(queries, want_water, seen, delay=1.0, per=10, keep=3,
             require=None, leads=(), reject=None, here=None, band=(168, 195)):
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
            hit["score"] = rank(hit, want_water, require, reject, here, band)
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
    ap.add_argument("--only", help="destination name, or several separated by commas")
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
    all_names = [d[1] for d in dests]
    if args.only:
        want = {s.strip().lower() for s in args.only.split(",")}
        dests = [d for d in dests if d[1].lower() in want]
        if not dests:
            raise SystemExit("no destination matches %r" % args.only)

    # A destination known for one particular sight rather than for its coastline.
    # The third field says whether the water still counts: Times Square has none,
    # the Faraglioni stand in it.
    # The fourth field is the hue band the water should fall in, where the
    # default turquoise is not what was asked for.
    CITY = {
        "New York":  ("Times Square", [r"times\s*square"], False),
        # Zac asked for the penguins on white sand, not the mountain
        "Cape Town": ("Boulders Beach", [r"boulders|penguin"], True),
        # and for Iceland, the black beach rather than the glacier lagoon
        "Iceland":   ("Reynisfjara", [r"reynisfjara|reynisdrangar|black\s*sand|v[íi]k\b"], True),
        # a cenote is deep blue, so the turquoise preference is moved
        "Tulum":     ("Gran Cenote", [r"cenote"], True, (198, 224)),
        "Dubrovnik": ("Dubrovnik Old Town", [r"dubrovnik"], True),
        # Santorini's beaches are black volcanic sand; the caldera is the picture
        "Santorini": ("Oia", [r"\boia\b|caldera|ammoudi|thira|fira"], True),
        "Capri":     ("Faraglioni", [r"faraglioni|marina\s*piccola|grotta\s*azzurra|"
                                     r"blue\s*grotto|via\s*krupp"], True),
    }

    # keep the heroes already chosen, so a run for one destination does not
    # throw away the other twenty-three
    out = {}
    hpath = os.path.join(SITE, "heroes.json")
    if os.path.exists(hpath):
        try:
            out = json.load(open(hpath))
        except Exception:
            out = {}

    for did, name in dests:
        t0 = time.time()
        if name in PINNED:
            title = PINNED[name]
            try:
                im = read_picture(title)
            except Exception as e:
                print("%-14s pinned picture would not load: %s" % (name, e), flush=True)
                continue
            scene, water = measure(im)
            save({"title": title, "im": im, "water": water}, colours)
            out[name] = title
            print("%-14s %-52s pinned by hand  bright %.2f  (%.0fs)"
                  % (name, title[:52], scene["bright"], time.time() - t0), flush=True)
            continue
        seen = set()
        require = None
        # a picture that names a different destination is a picture of that one
        others = [re.escape(n) for n in all_names if n != name]
        bad = [CONFUSABLE[name]] if name in CONFUSABLE else []
        bad.append(r"\b(?:%s)\b" % "|".join(others))
        reject = re.compile("|".join(bad), re.I)
        here = re.compile(r"\b%s\b" % re.escape(name), re.I)
        band = (168, 195)
        if name in CITY:
            entry = CITY[name]
            landmark, pats, want_water = entry[0], entry[1], entry[2]
            if len(entry) > 3:
                band = entry[3]
            queries = ["%s %s" % (landmark, name), landmark,
                       "%s %s sea" % (landmark, name)]
            leads = [landmark] + FAMOUS.get(name, [])
            require = re.compile("|".join(pats), re.I)
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
            # Wikipedia's lead for the place itself, plus its best-known spot:
            # a database beach name is often a beach bar, which leads nothing
            leads = [name] + FAMOUS.get(name, [])
            leads += [("%s (%s)" % (b, name)) if len(b) < 14 else b for b in beaches[:2]]
            want_water = True
        pick = best_for(queries, want_water, seen, delay=args.delay,
                        require=require, leads=leads, reject=reject, here=here, band=band)
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
