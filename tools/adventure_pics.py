#!/usr/bin/env python3
"""Find each adventure its own photograph, by name.

Commons geosearch, one request per place: every geotagged file within three
kilometres, each with its distance. Then the filename has to carry a word from
the place's own name.

Both halves are needed. Proximity alone gave a dive resort a number plate.
The name alone gave "Cavo Bianco" in Capri a poplar tree on the river Po, 700
kilometres away, because bianco is just Italian for white, and gave Imbros
Gorge in Crete a First World War prisoner camp on Imbros in Turkey. Together
they are strict: the file was taken here AND it is named after this.

Searching by name alone also cost four requests a place and would have taken
three hours; this takes one.

Natural features are far better served by this than restaurants were: people
photograph a named gorge on purpose, and nobody photographs a named bar.

    python3 tools/adventure_pics.py --per 40 --workers 2

Writes place.photo_title, caches into site/img/, one file to one place.
"""

import argparse, collections, hashlib, io, json, math, os, queue, re, sqlite3
import threading, time, unicodedata
import urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
IMG = os.path.join(SITE, "img")
DB = os.path.join(ROOT, "data", "index.db")
UA = "hidden-adventures/1.0 (travel index; open data)"
COMMONS = "https://commons.wikimedia.org/w/api.php"
WIKI = "https://en.wikipedia.org/w/api.php"
FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/"

GENERIC = set("""beach beaches playa platja praia spiaggia paralia plage strand cala cove bay
trail trails path track route hiking hike walk gorge canyon cave caves waterfall falls
lake lagoon spring springs river mountain peak summit ridge cliff island islet reef point
national park nature reserve natural area the and of de la le el los las il lo du des von der
north south east west upper lower great little grande piccola nova velha new old sankt saint
centre center viewpoint lookout scenic diving dive scuba snorkel surf surfing kayak canoe
boat tour rental centre club school company tours adventures""".split())

JUNK = re.compile(r"""(?ix) \b(
    map|plan|floorplan|blueprint|diagram|chart|schematic|logo|crest|coat.of.arms|flag|
    seal|stamp|coin|banknote|ticket|receipt|menu|poster|advert|leaflet|brochure|
    sign|signpost|signage|plaque|notice|nameplate|plate|licence|license|
    portrait|selfie|mugshot|grave|tomb|cemetery|screenshot|scan|document|
    drawing|sketch|engraving|postcard|newspaper|certificate|
    train|railway|locomotive|tram|bus|lorry|truck|aircraft|airplane|helicopter|
    car|cars|bicycle|motorcycle|scooter|restaurant|hotel|shop|museum|church
  )\b""")

lock = threading.Lock()
tally = {"wiki": 0, "commons": 0, "none": 0, "fail": 0, "throttled": 0}


def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def words(s):
    return [t for t in re.findall(r"[a-z0-9]+", norm(s)) if len(t) >= 4 and t not in GENERIC]


def local_name(title):
    return hashlib.sha1(title.encode("utf-8")).hexdigest()[:16] + ".jpg"


def get(url, tries=5):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=45).read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or attempt == tries - 1:
                raise
            with lock:
                tally["throttled"] += 1
            time.sleep(4 * (attempt + 1))
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def km(a, b, c, d):
    return math.hypot((c - a) * 111.0, (d - b) * 111.0 * math.cos(math.radians(a)))


def geosearch(lat, lon, radius=3000, limit=80):
    """Every geotagged file within radius metres, nearest first."""
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


def worker(q, taken, width, delay, results):
    from PIL import Image
    while True:
        try:
            pid, dname, nm, ident, lat, lon = q.get_nowait()
        except queue.Empty:
            return
        try:
            hit = None
            for title, dist in geosearch(lat, lon):
                if JUNK.search(title.replace("_", " ")):
                    continue
                if ident & set(words(title)):
                    hit = title
                    break                      # nearest first, so the first is the best
            time.sleep(delay)
            if not hit:
                with lock:
                    tally["none"] += 1
                continue
            with lock:
                if hit in taken:
                    tally["none"] += 1
                    continue
                taken.add(hit)
            url = FILEPATH + urllib.parse.quote(hit.replace(" ", "_")) + "?width=%d" % width
            im = Image.open(io.BytesIO(get(url))).convert("RGB")
            im.thumbnail((width, width))
            im.save(os.path.join(IMG, local_name(hit)), "JPEG", quality=82, optimize=True)
            with lock:
                results.append((hit, pid))
                tally["commons"] += 1
                print("   %-34s <- %s" % (nm[:34], hit[:52]), flush=True)
        except Exception:
            with lock:
                tally["fail"] += 1
        finally:
            q.task_done()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per", type=int, default=40, help="places per destination")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--delay", type=float, default=0.4)
    ap.add_argument("--width", type=int, default=900)
    ap.add_argument("--hidden-only", action="store_true",
                    help="only the hidden ones, which is what the app opens on")
    args = ap.parse_args()

    os.makedirs(IMG, exist_ok=True)
    con = sqlite3.connect(DB)
    taken = set(r[0] for r in con.execute(
        "SELECT photo_title FROM place WHERE photo_title IS NOT NULL"))

    # a word common across the whole index is an ordinary word of some language,
    # not the name of anything: bianco, grande, playa, piccola
    df = collections.defaultdict(collections.Counter)
    GLOBAL = collections.Counter()
    for d, n in con.execute("SELECT dest, name FROM place"):
        for w in set(words(n)):
            df[d][w] += 1
            GLOBAL[w] += 1

    where = "AND n2km <= 25" if args.hidden_only else ""
    jobs = []
    for did, dname in con.execute("SELECT id, name FROM destination ORDER BY id"):
        rows = con.execute("""SELECT id, name, lat, lon FROM place
                              WHERE dest=? AND photo_title IS NULL %s
                              ORDER BY confidence DESC LIMIT ?""" % where,
                           (did, args.per)).fetchall()
        for pid, nm, lat, lon in rows:
            ident = {w for w in set(words(nm)) if df[did][w] <= 3 and GLOBAL[w] <= 60}
            if ident:
                jobs.append((pid, dname, nm, ident, lat, lon))
    print("%s adventures to look up across %s destinations"
          % (format(len(jobs), ","),
             format(con.execute("SELECT count(*) FROM destination").fetchone()[0], ",")), flush=True)

    q = queue.Queue()
    for j in jobs:
        q.put(j)
    results = []
    t0 = time.time()
    ths = [threading.Thread(target=worker, args=(q, taken, args.width, args.delay, results),
                            daemon=True) for _ in range(args.workers)]
    for t in ths:
        t.start()
    while any(t.is_alive() for t in ths):
        time.sleep(20)
        with lock:
            seen = sum(tally.values()) - tally["throttled"]
            if results:
                con.executemany("UPDATE place SET photo_title=? WHERE id=?", results)
                con.commit()
                results.clear()
        rate = seen / max(time.time() - t0, 1)
        print("   %d/%d  %d wiki  %d commons  %d none  %d failed  ~%.0f min left"
              % (seen, len(jobs), tally["wiki"], tally["commons"], tally["none"],
                 tally["fail"], (len(jobs) - seen) / rate / 60 if rate else 0), flush=True)
    with lock:
        if results:
            con.executemany("UPDATE place SET photo_title=? WHERE id=?", results)
            con.commit()
    print("ADVPICSDONE %d from Wikipedia, %d from Commons, %d without one, %.0f min"
          % (tally["wiki"], tally["commons"], tally["none"], (time.time() - t0) / 60), flush=True)


if __name__ == "__main__":
    main()
