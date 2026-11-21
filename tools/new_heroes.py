#!/usr/bin/env python3
"""A lead picture for each destination, taken from Wikipedia's own article.

For a famous landmark this beats any relevance ranking: the lead image is the
photograph Wikipedia's editors chose to represent the place. Relevance search
is what gave Madeira a Florida drawbridge and Dubrovnik the Copacabana in Rio.

Each destination gets a list of candidate articles, most iconic first, because
a destination is a region and a region's own article often leads with a map.
"Dolomites" leads with a range map; "Tre Cime di Lavaredo" leads with the peaks.

    python3 tools/new_heroes.py              # only destinations without a hero
    python3 tools/new_heroes.py --all        # every destination

Writes site/heroes.json and caches the picture into site/img/.
"""

import argparse, hashlib, io, json, os, re, sys, time
import urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
IMG = os.path.join(SITE, "img")
UA = "hidden-adventures/1.0 (travel index; open data)"
WIKI = "https://en.wikipedia.org/w/api.php"
FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/"

# Most iconic first. These are adventures, so the choice is the gorge, the peak
# or the water itself rather than a town square.
LEADS = {
    "Lofoten":        ["Reinebringen", "Reine, Norway", "Lofoten"],
    "Dolomites":      ["Tre Cime di Lavaredo", "Seceda", "Lago di Braies"],
    "Isle of Skye":   ["Old Man of Storr", "Quiraing", "Fairy Pools"],
    "Bernese Oberland": ["Oeschinen Lake", "Lauterbrunnen", "Eiger"],
    "Soca Valley":    ["Tolmin Gorges", "Soča", "Triglav National Park"],
    "Wadi Rum":       ["Wadi Rum"],
    "Atlas Mountains": ["Ouzoud Falls", "Toubkal", "Todgha Gorge"],
    "Arenal and Monteverde": ["Arenal Volcano", "Monteverde Cloud Forest Reserve",
                              "La Fortuna Waterfall"],
    "Tenerife":       ["Roque Cinchado", "Teide", "Masca, Tenerife"],
    "Faroe Islands":  ["Sørvágsvatn", "Gásadalur", "Múlafossur"],
    "Krabi":          ["Railay Beach", "Phra Nang Cave Beach", "Krabi Province"],
    "Phong Nha":      ["Hang Sơn Đoòng", "Phong Nha-Kẻ Bàng National Park"],
    "Kauai":          ["Nā Pali Coast State Park", "Waimea Canyon State Park",
                       "Hanakapiai Falls"],
    "Fiordland":      ["Milford Sound", "Doubtful Sound", "Fiordland National Park"],
    "Sacred Valley":  ["Machu Picchu", "Ollantaytambo", "Vinicunca"],
    "El Chalten":     ["Monte Fitz Roy", "Laguna de los Tres", "El Chaltén"],
    "Torres del Paine": ["Torres del Paine", "Torres del Paine National Park"],
    "Komodo and Flores": ["Padar Island", "Padar", "Kelimutu", "Komodo National Park"],
    "Raja Ampat":     ["Raja Ampat", "Piaynemo", "Wayag", "Misool", "Raja Ampat Islands"],
    # Réunion's own volcano article leads with a brown ash slope, which is the
    # least beautiful thing on the island. The cirques are what people walk.
    "Reunion":        ["Trou de Fer", "Cirque de Mafate", "Cirque of Mafate",
                       "Piton des Neiges", "Cirque de Salazie"],
    # Chosen when this was an index of beaches, and wrong for an adventure one:
    # the Azores led with a crowded town beach at Porto Formoso and Phuket with
    # an unnamed 2013 snapshot.
    "Azores":         ["Sete Cidades (Azores)", "Lagoa do Fogo", "Sete Cidades Massif"],
    "Phuket":         ["Phang Nga Bay", "Freedom Beach", "Kata Noi Beach"],
    "Ningaloo":       ["Turquoise Bay", "Ningaloo Reef", "Yardie Creek",
                       "Ningaloo Coast", "Cape Range National Park"],
}

# A signed 1952 print of a first ascent is a document, not a sunny landscape.
# El Chaltén's lead was "1952-01-31 - Lionel Terray, Fitzroy, dédicace - NB".
DATED = re.compile(r"\b(18|19)\d{2}\b")

# Chosen by hand where no article leads with a photograph. Wikipedia's Raja
# Ampat article leads with a figure from a PLoS Biology paper, and the islands
# it is named for have no articles of their own; this is the karst viewpoint
# the place is known for, and it is on the article already.
PINNED = {
    "Raja Ampat": "Pulau Piaynemo, Raja Ampat.jpg",
}

# A lead image can still be the wrong kind of picture: a flag, a locator map, a
# diagram, a portrait of the person a place is named after.
NOTPHOTO = re.compile(r"""(?ix)\b(
    map|locator|location|topographic|relief|flag|coat.of.arms|seal|logo|
    diagram|chart|graph|profile|cross.section|plan|
    portrait|bust|statue|monument|stamp|coin|banknote
  )\b""")


def local_name(title):
    return hashlib.sha1(title.encode("utf-8")).hexdigest()[:16] + ".jpg"


def get(url, tries=5):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or attempt == tries - 1:
                raise
            time.sleep(5 * (attempt + 1))
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")


def wiki_lead(article):
    """The photograph Wikipedia leads its article with, and its size."""
    url = (WIKI + "?action=query&format=json&prop=pageimages&piprop=original"
           "&redirects=1&titles=" + urllib.parse.quote(article))
    try:
        data = json.loads(get(url))
    except Exception:
        return None
    for p in ((data.get("query") or {}).get("pages") or {}).values():
        orig = p.get("original") or {}
        src = orig.get("source")
        if not src:
            continue
        name = urllib.parse.unquote(src.rsplit("/", 1)[-1].split("?")[0]).replace("_", " ")
        if not name.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        if NOTPHOTO.search(name) or DATED.search(name):
            continue
        w, h = orig.get("width") or 0, orig.get("height") or 0
        if w < 1500 or h < 900:
            continue                     # too small to draw at 1,800 without blur
        if w < h:
            continue                     # a portrait crops badly into a wide hero
        return {"title": name, "w": w, "h": h}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="redo destinations that have one")
    ap.add_argument("--only", default="", help="comma-separated destination names")
    ap.add_argument("--width", type=int, default=900)
    args = ap.parse_args()

    os.makedirs(IMG, exist_ok=True)
    hpath = os.path.join(SITE, "heroes.json")
    heroes = json.load(open(hpath)) if os.path.exists(hpath) else {}

    import sqlite3
    con = sqlite3.connect(os.path.join(ROOT, "data", "index.db"))
    live = [r[0] for r in con.execute("SELECT name FROM destination ORDER BY id")]

    # A destination that is no longer in the index keeps no hero. New York went
    # when this stopped being a city index.
    for gone in [k for k in heroes if k not in live]:
        del heroes[gone]
        print("dropped %s, no longer a destination" % gone)

    if args.only:
        pick = {s.strip() for s in args.only.split(",") if s.strip()}
        todo = [d for d in live if d in pick]
        missed = pick - set(todo)
        if missed:
            print("not a destination: %s" % ", ".join(sorted(missed)))
    else:
        todo = [d for d in live if args.all or d not in heroes]
    print("%d destinations need a hero\n" % len(todo), flush=True)

    from PIL import Image
    for name in todo:
        pick = None
        if name in PINNED:
            pick = {"title": PINNED[name], "w": 0, "h": 0, "via": "pinned by hand"}
        cands = LEADS.get(name) or [name]
        for article in cands if not pick else []:
            pick = wiki_lead(article)
            time.sleep(0.4)
            if pick:
                pick["via"] = article
                break
        if not pick:
            print("%-22s no lead picture found in %s" % (name, cands), flush=True)
            continue
        try:
            url = (FILEPATH + urllib.parse.quote(pick["title"].replace(" ", "_"))
                   + "?width=%d" % args.width)
            im = Image.open(io.BytesIO(get(url))).convert("RGB")
            im.thumbnail((args.width, args.width))
            im.save(os.path.join(IMG, local_name(pick["title"])), "JPEG",
                    quality=85, optimize=True)
        except Exception as e:
            print("%-22s could not fetch: %s" % (name, e), flush=True)
            continue
        heroes[name] = pick["title"]
        print("%-22s %-50s  %dx%d  via %s"
              % (name, pick["title"][:50], pick["w"], pick["h"], pick["via"]), flush=True)
        time.sleep(0.3)

    json.dump(heroes, open(hpath, "w"), ensure_ascii=False, indent=1)
    missing = [d for d in live if d not in heroes]
    print("\nNEWHEROESDONE %d of %d destinations have a hero" % (len(heroes), len(live)))
    if missing:
        print("still without one: %s" % ", ".join(missing))


if __name__ == "__main__":
    main()
