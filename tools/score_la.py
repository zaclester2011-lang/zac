#!/usr/bin/env python3
"""Score Los Angeles and everything within two and a half hours of it.

Same two measures as Crete, and the same code behind them, so the numbers can
be set beside each other:

  Discovery  rate.discovery(), off how much else Overture has mapped within
             500 m and 2 km. Fitted on the eight places we stood in.
  Colour     measure_water.water_colour() on a Commons photograph OF the place,
             then rate.colour(). Median hue and saturation of the blue-green
             pixels in the lower frame.

A photograph is only used when its filename names the place — the rule the
travel index settled on after proximity alone gave a dive resort a number
plate. Several candidates are tried per place, because most photographs of a
beach are of the people on it, and a frame under 18% water cannot answer.

    python3 tools/score_la.py
    python3 tools/score_la.py --only "Catalina Casino Point"

Writes site/la_scores.json.
"""

import argparse, colorsys, io, json, math, os, re, sys, time, unicodedata
import urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import rate                       # discovery() and colour(), unchanged
import measure_water              # water_colour(), unchanged

UA = "hidden-adventures/1.0 (travel index; open data)"
COMMONS = "https://commons.wikimedia.org/w/api.php"
FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/"
OUT = os.path.join(ROOT, "site", "la_scores.json")

# name, lat, lon, is the water the point of it
PLACES = [
    ("Santa Cruz Island",          34.0490, -119.5580, True),
    ("Catalina Casino Point",      33.3480, -118.3280, True),
    ("Catalina Two Harbors",       33.4420, -118.5000, True),
    ("La Jolla Shores",            32.8570, -117.2570, True),
    ("Crystal Cove",               33.5730, -117.8410, True),
    ("Laguna Beach",               33.5150, -117.7670, True),
    ("Torrey Pines",               32.9330, -117.2530, True),
    ("El Matador Beach",           34.0380, -118.8740, True),
    ("Leo Carrillo Beach",         34.0450, -118.9340, True),
    ("Point Dume",                 34.0010, -118.8060, True),
    ("Santa Monica Beach",         34.0100, -118.4960, True),
    ("Carpinteria",                34.3910, -119.5190, True),
    ("Dana Point",                 33.4620, -117.7040, True),
    ("Huntington Beach",           33.6550, -118.0030, True),
    ("Newport Beach",              33.6080, -117.9290, True),
    ("San Clemente",               33.4220, -117.6120, True),
    ("Santa Barbara",              34.4140, -119.6670, True),
    ("Big Bear Lake",              34.2440, -116.9110, True),
    ("Lake Arrowhead",             34.2480, -117.1890, True),
    ("Switzer Falls",              34.2650, -118.1460, True),
    # the warm ones — the only water within range that reaches 25 degrees
    ("Castaic Lake",               34.5460, -118.6100, True),
    ("Lake Piru",                  34.4830, -118.7570, True),
    ("Lake Elsinore",              33.6570, -117.3570, True),
    ("Lake Perris",                33.8610, -117.1680, True),
    ("Silverwood Lake",            34.2860, -117.3370, True),
    ("Joshua Tree Hidden Valley",  34.0120, -116.1680, False),
    ("Palm Springs Mountain Station", 33.8140, -116.6130, False),
    ("Mount Baldy",                34.2620, -117.6240, False),
    ("Idyllwild",                  33.7470, -116.7190, False),
    ("Sandstone Peak",             34.1110, -118.9340, False),
    ("Vasquez Rocks",              34.4890, -118.3210, False),
    ("Salton Sea Bombay Beach",    33.3500, -115.7300, False),
    ("Ojai",                       34.4480, -119.2430, False),
    ("Solvang",                    34.5960, -120.1380, False),
    ("Disneyland",                 33.8120, -117.9190, False),
    ("Six Flags Magic Mountain",   34.4250, -118.5970, False),
]

# Water asks one question: is there enough of it to swim in. Ten if yes. The
# app's tooltip says "Sea is Water 10 always" because the sea always is, not
# because only the sea counts — a lake you can swim in scores the same, and a
# gorge with a trickle down it scores nothing. That is why Kourtaliotiko and
# Aradena carry no Water in the Crete table and the six beaches all carry 10.
SWIMMABLE = {"Santa Cruz Island", "Catalina Casino Point", "Catalina Two Harbors",
             "La Jolla Shores", "Crystal Cove", "Laguna Beach", "Torrey Pines",
             "El Matador Beach", "Leo Carrillo Beach", "Point Dume",
             "Santa Monica Beach", "Carpinteria", "Dana Point", "Huntington Beach",
             "Newport Beach", "San Clemente", "Santa Barbara",
             "Big Bear Lake", "Castaic Lake", "Lake Piru", "Lake Elsinore",
             "Lake Perris", "Silverwood Lake"}

GENERIC = set("""beach beaches state park national monument point cove bay island islands
lake falls creek canyon rocks mountain peak harbor harbour shores city town the and of
california usa united states america view aerial panorama sunset sunrise""".split())

JUNK = re.compile(r"""(?ix)\b(
    map|plan|diagram|logo|sign|signs|signpost|plaque|poster|menu|coat.of.arms|flag|
    portrait|selfie|grave|cemetery|screenshot|scan|document|drawing|sketch|
    train|railway|tram|bus|aircraft|airplane|helicopter|car|cars|bicycle|
    male|female|juvenile|nest|specimen|closeup|close.up|macro|
    hotel|restaurant|museum|church|parking
  )\b""")
BINOMIAL = re.compile(r"^[A-Z][a-z]{3,}\s+[a-z]{3,}\s*(?:,|\.(?:jpe?g|png)$)")


def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def words(s):
    return [t for t in re.findall(r"[a-z0-9]+", norm(s)) if len(t) >= 4 and t not in GENERIC]


def get(url, tries=5):
    for a in range(tries):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or a == tries - 1:
                raise
            time.sleep(6 * (a + 1))
        except Exception:
            if a == tries - 1:
                raise
            time.sleep(3 * (a + 1))


def km(a, b, c, d):
    return math.hypot((c - a) * 111.0, (d - b) * 111.0 * math.cos(math.radians(a)))


# ------------------------------------------------------------ discovery

def density():
    """Everything Overture has mapped within 3 km of each place.

    One query with a small box per place rather than one box over the whole
    region: greater Los Angeles holds the better part of a million points and
    only the ones near these thirty matter.
    """
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import index_destination as idx
    rel, urls = idx.overture_files()
    import duckdb
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        os.environ.pop(k, None)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    pad = 0.030
    where = " OR ".join(
        "(bbox.xmin BETWEEN %f AND %f AND bbox.ymin BETWEEN %f AND %f)"
        % (lon - pad / math.cos(math.radians(lat)), lon + pad / math.cos(math.radians(lat)),
           lat - pad, lat + pad)
        for _, lat, lon, _ in PLACES)
    sql = """
        SELECT ROUND(bbox.ymin, 5) AS lat, ROUND(bbox.xmin, 5) AS lon
        FROM read_parquet([%s])
        WHERE (%s) AND names.primary IS NOT NULL
    """ % (",".join("'%s'" % u for u in urls), where)
    print("   querying Overture %s for thirty neighbourhoods…" % rel, flush=True)
    t0 = time.time()
    rows = con.execute(sql).fetchall()
    print("   %s mapped places came back (%.0fs)" % (format(len(rows), ","), time.time() - t0),
          flush=True)
    out = {}
    for name, lat, lon, _ in PLACES:
        n500 = sum(1 for la, lo in rows if km(lat, lon, la, lo) <= 0.5)
        n2km = sum(1 for la, lo in rows if km(lat, lon, la, lo) <= 2.0)
        out[name] = (max(n500 - 1, 0), max(n2km - 1, 0))
    return out


# ------------------------------------------------------------ colour

def geosearch(lat, lon, radius=4000, limit=120):
    url = (COMMONS + "?action=query&format=json&list=geosearch&gsnamespace=6"
           "&gsradius=%d&gscoord=%s|%s&gslimit=%d" % (radius, lat, lon, limit))
    try:
        data = json.loads(get(url))
    except Exception:
        return []
    out = []
    for f in data.get("query", {}).get("geosearch", []):
        t = f.get("title", "")
        if t.lower().startswith("file:") and t.lower().endswith((".jpg", ".jpeg", ".png")):
            out.append((t[5:], f.get("dist", 0) / 1000.0))
    return out


def measure(name, lat, lon, tries=8):
    """The first nearby photograph that names the place AND shows enough water."""
    from PIL import Image
    mine = set(words(name))
    cands = []
    for title, dist in geosearch(lat, lon):
        plain = title.replace("_", " ")
        if JUNK.search(plain) or BINOMIAL.match(plain):
            continue
        if mine & set(words(title)):
            cands.append((dist, title))
    cands.sort()
    for dist, title in cands[:tries]:
        try:
            url = FILEPATH + urllib.parse.quote(title.replace(" ", "_")) + "?width=600"
            im = Image.open(io.BytesIO(get(url))).convert("RGB")
            c = measure_water.water_colour(im)
            time.sleep(0.5)
        except Exception:
            continue
        if c and c["share"] >= 0.18:
            return title, dist, c
    return None, None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--skip-overture", action="store_true")
    args = ap.parse_args()

    picked = [p for p in PLACES if not args.only or p[0] == args.only]

    print("1. how much is mapped around each one")
    dens = {} if args.skip_overture else density()

    print("\n2. the colour of the water, measured")
    out = []
    for name, lat, lon, watery in picked:
        n5, n2 = dens.get(name, (None, None))
        d = rate.discovery(n5, n2, None, None) if n5 is not None else None
        rec = {"name": name, "lat": lat, "lon": lon, "n500": n5, "n2km": n2,
               "discovery": d, "colour": None, "photo": None}
        if watery:
            title, dist, c = measure(name, lat, lon)
            if c:
                rec["colour"] = rate.colour(c["hue"], c["sat"], c["share"])
                rec["photo"] = title
                rec["hue"], rec["sat"], rec["share"] = c["hue"], c["sat"], c["share"]
                print("   %-30s hue %5.1f  sat %.2f  water %2.0f%%  ->  Colour %s"
                      % (name[:30], c["hue"], c["sat"], c["share"] * 100, rec["colour"]),
                      flush=True)
            else:
                print("   %-30s no photograph of it shows enough water" % name[:30], flush=True)
        out.append(rec)

    # Water is not a quality in this scale. The app says so itself: "Sea is
    # Water 10 always". So the total out of thirty is only ever D + C + 10 for
    # somewhere in the sea, and the 25 bar is really D + C >= 15. Every place
    # we stood in in Crete clears it — Seitan 26.5, Katholiko 26, Balos and
    # Glyka Nera 25.5, Preveli and Elafonissi 25 — which is what makes 25 the
    # line worth drawing.
    for r in out:
        r["water"] = 10 if r["name"] in SWIMMABLE else None
        if r["discovery"] is not None and r["colour"] is not None and r["water"]:
            r["total"] = r["discovery"] + r["colour"] + r["water"]
        else:
            r["total"] = None

    json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1)
    print("\n%-32s %5s %6s %5s %7s   %s"
          % ("", "Disc", "Colour", "Water", "TOTAL", "mapped 500m / 2km"))
    rank = sorted(out, key=lambda r: -(r["total"] if r["total"] is not None
                                       else (r["discovery"] or 0)))
    for r in rank:
        f = lambda v: "%.1f" % v if v is not None else "—"
        print("%-32s %5s %6s %5s %7s %s  %s / %s"
              % (r["name"][:32], f(r["discovery"]), f(r["colour"]), f(r["water"]),
                 f(r["total"]), "<= 25+" if (r["total"] or 0) >= 25 else "      ",
                 r["n500"], r["n2km"]))
    clears = [r for r in out if (r["total"] or 0) >= 25]
    print("\n%d of %d clear 25. In Crete all six did."
          % (len(clears), len(out)))
    for r in clears:
        print("   %s  %.1f" % (r["name"], r["total"]))
    print("\nSCORELADONE %d places, %d with a measured colour"
          % (len(out), sum(1 for r in out if r["colour"] is not None)))


if __name__ == "__main__":
    main()
