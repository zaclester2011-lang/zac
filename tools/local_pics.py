#!/usr/bin/env python3
"""Match every adventure to its own photograph, locally, with no searching.

Once resolve_titles.py has given the geotagged photographs their filenames this
is a join rather than a search. For each place, every Commons photograph within
three kilometres is a candidate; a candidate is accepted only when its filename
carries a word from the place's own name.

Both halves are needed, and each has failed on its own:

  proximity alone   gave a dive resort a number plate, a police station to 97
                    places and one corrupt file to 187 of them
  the name alone    gave "Cavo Bianco" in Capri a poplar tree on the river Po,
                    700 km away, because bianco is just Italian for white, and
                    gave Imbros Gorge in Crete a First World War prisoner camp
                    on Imbros in Turkey

Three kinds of word do not count as naming a place:

  generic words     beach, gorge, trail, national, park …
  the destination   Crete, Tenerife, Fiordland …
  local place names found in the data rather than listed: a word carried by
                    more than three places in the same destination is a valley
                    or a village, not an identity. A word carried by more than
                    sixty places across the whole index is an ordinary word of
                    some language.

Then every photograph is used once, and every place gets at most one, so no two
cards show the same picture. Where several places claim a file it goes to the
one whose name matches it best, nearest first on a tie.

    python3 tools/local_pics.py                  # report what it would attach
    python3 tools/local_pics.py --write          # attach and download

Writes place.photo_title and caches each picture into site/img/.
"""

import argparse, collections, hashlib, io, math, os, queue, re, sqlite3
import threading, time, unicodedata
import urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
IMG = os.path.join(SITE, "img")
DB = os.path.join(ROOT, "data", "index.db")
UA = "hidden-adventures/1.0 (travel index; open data)"
FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/"

RADIUS_KM = 3.0
# A hidden place is remote by definition, so the photographer stands further
# back and there is far less around to be confused with. Widening the circle
# only for those places buys pictures where they are scarcest without loosening
# anything: the filename must still name the place, and each file is still used
# once.
HIDDEN_RADIUS_KM = 6.0
HIDDEN_N2 = 10
LOCAL_NAME_AT = 3        # a word on more places than this, here, is a place name
GLOBAL_WORD_AT = 60      # a word on more places than this, anywhere, is a common word

GENERIC = set("""beach beaches strand playa platja praia spiaggia paralia plage cala cove bay
sandbar shingle seashore lido pantai coast shore seaside beachfront waterfront
trail trails path track route hiking hike walk walking trek trekking circuit loop
gorge gorges canyon ravine cave caves cavern grotto cliff cliffs crater volcano glacier
waterfall waterfalls falls cascade cascades lake lagoon cenote spring springs geyser river
mountain mountains peak summit ridge pass island islet archipelago reef point cape
national park nature reserve natural protected area forest valley viewpoint lookout
scenic panorama view vista diving dive scuba snorkel snorkelling surf surfing kayak canoe
rafting boat tour tours trip trips rental centre center club school company adventures
the and of de la le el los las il lo du des von der det een och
north south east west upper lower great little grande piccola nova velha new old
sankt saint santa san monte mount punta playa puerto cala costa parque parc parco
panoramio unsplash flickr wiki file image photo picture jpg jpeg png com www net org
http https wikimedia commons""".split())

# A filename can name the place and still not be a picture of it: the Hotel
# Martinique matched an architectural floor plan of itself, and "Afrata Beach"
# matched a photograph of the road to Afrata village.
JUNK = re.compile(r"""(?ix) \b(
    map|maps|plan|plans|floorplan|blueprint|elevation|cross.section|diagram|chart|
    schematic|graph|profile|logo|crest|coat.of.arms|flag|seal|stamp|coin|banknote|
    ticket|receipt|invoice|menu|poster|billboard|advert|advertisement|leaflet|brochure|
    # "signs" is not "sign": a photograph of the informational signs at Russian
    # Fort Elizabeth passed a filter that only knew the singular
    signs?|signpost|signage|plaques?|notices?|nameplate|number.plate|licence|license|
    # the subject is the business, not the place: a beach was illustrated by
    # "Techo de hotel Dusit Thani Laguna" — the roof of its hotel
    hotels?|resorts?|restaurants?|cafes?|taverna|bars?|pubs?|lodges?|
    portrait|selfie|mugshot|headshot|grave|tomb|tombstone|cemetery|memorial|statue|
    screenshot|scan|document|letter|manuscript|drawing|sketch|engraving|painting|
    postcard|newspaper|clipping|certificate|patent|
    train|railway|locomotive|tram|bus|coach|lorry|truck|aircraft|airplane|airport|
    helicopter|ferry|car|cars|bicycle|motorcycle|scooter|roundabout|car.park|parking|
    road|roads|street|highway|motorway|junction|bridge.over|construction|building.site|
    church|chapel|mosque|temple.of|museum|supermarket|petrol|gas.station|hospital
  )\b""")

lock = threading.Lock()
got = {"ok": 0, "cached": 0, "fail": 0, "throttled": 0}


def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def words(s):
    return [t for t in re.findall(r"[a-z0-9]+", norm(s)) if len(t) >= 4 and t not in GENERIC]


def local_name(title):
    return hashlib.sha1(title.encode("utf-8")).hexdigest()[:16] + ".jpg"


def km(a, b, c, d):
    return math.hypot((c - a) * 111.0, (d - b) * 111.0 * math.cos(math.radians(a)))


def fetch(url, tries=6):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or attempt == tries - 1:
                raise
            with lock:
                got["throttled"] += 1
            time.sleep(4 * (attempt + 1))
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def downloader(q, width, delay):
    from PIL import Image
    while True:
        try:
            title = q.get_nowait()
        except queue.Empty:
            return
        try:
            path = os.path.join(IMG, local_name(title))
            if os.path.exists(path) and os.path.getsize(path) > 2000:
                with lock:
                    got["cached"] += 1
                continue
            url = FILEPATH + urllib.parse.quote(title.replace(" ", "_")) + "?width=%d" % width
            im = Image.open(io.BytesIO(fetch(url))).convert("RGB")
            im.thumbnail((width, width))
            im.save(path, "JPEG", quality=82, optimize=True)
            with lock:
                got["ok"] += 1
            time.sleep(delay)
        except Exception:
            with lock:
                got["fail"] += 1
        finally:
            q.task_done()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--width", type=int, default=900)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--delay", type=float, default=0.15)
    ap.add_argument("--keep", action="store_true",
                    help="keep photographs already attached instead of rematching")
    args = ap.parse_args()

    os.makedirs(IMG, exist_ok=True)
    con = sqlite3.connect(DB)

    print("1. the places")
    places = con.execute("""SELECT id, dest, name, category, locality, lat, lon, n2km
                            FROM place""").fetchall()
    dest_words, boxes = {}, {}
    for did, dname, s, w, n, e in con.execute(
            "SELECT id, name, south, west, north, east FROM destination"):
        dest_words[did] = set(re.findall(r"[a-z0-9]+", norm(dname)))
        boxes[did] = (s, w, n, e)

    df = collections.defaultdict(collections.Counter)
    GLOBAL = collections.Counter()
    for pid, did, name, cat, loc, lat, lon, n2 in places:
        for w in set(words(name)):
            df[did][w] += 1
            GLOBAL[w] += 1

    ident = {}
    for pid, did, name, cat, loc, lat, lon, n2 in places:
        skip = dest_words[did] | set(re.findall(r"[a-z0-9]+", norm(loc)))
        ident[pid] = {w for w in set(words(name))
                      if df[did][w] <= LOCAL_NAME_AT and GLOBAL[w] <= GLOBAL_WORD_AT
                      and w not in skip}
    nameable = sum(1 for v in ident.values() if v)
    print("   %s adventures, %s with a distinctive name"
          % (format(len(places), ","), format(nameable, ",")), flush=True)

    print("2. the photographs near them")
    G = 0.03
    grid = collections.defaultdict(list)
    nph = 0
    for did, (s, w, n, e) in boxes.items():
        for title, lat, lon in con.execute(
                """SELECT title, lat, lon FROM photo
                   WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ? AND title IS NOT NULL""",
                (s - 0.06, n + 0.06, w - 0.06, e + 0.06)):
            grid[(int(lat / G), int(lon / G))].append((title, lat, lon))
            nph += 1
    print("   %s titled photographs inside the destinations" % format(nph, ","), flush=True)

    print("3. matching")
    # word-count cache, so a title near many places is split into words once
    wcache = {}
    cands = []
    t0 = time.time()
    for k, (pid, did, name, cat, loc, lat, lon, n2) in enumerate(places):
        mine = ident[pid]
        if not mine:
            continue
        reach = HIDDEN_RADIUS_KM if (n2 or 0) <= HIDDEN_N2 else RADIUS_KM
        i = int(lat / G)
        span = 111.0 * G * max(math.cos(math.radians(lat)), 0.05)
        jr = int(math.ceil(reach / span))
        ir = int(math.ceil(reach / (111.0 * G)))
        best = []
        for di in range(-ir, ir + 1):
            for dj in range(-jr, jr + 1):
                for title, plat, plon in grid.get((i + di, int(lon / G) + dj), ()):
                    d = km(lat, lon, plat, plon)
                    if d > reach:
                        continue
                    tw = wcache.get(title)
                    if tw is None:
                        tw = wcache[title] = set(words(title))
                    shared = mine & tw
                    if not shared:
                        continue
                    if JUNK.search(title.replace("_", " ")):
                        continue
                    best.append((len(shared), max(len(w) for w in shared), -d, title))
        if best:
            best.sort(reverse=True)
            for b in best[:6]:
                cands.append((b[0], b[1], b[2], pid, b[3]))
        if (k + 1) % 5000 == 0:
            print("   %s/%s places  %s candidate pairs  (%.0fs)"
                  % (format(k + 1, ","), format(len(places), ","),
                     format(len(cands), ","), time.time() - t0), flush=True)

    print("   %s candidate pairs from %s places"
          % (format(len(cands), ","), format(len({c[3] for c in cands}), ",")))

    print("4. one photograph per place, one place per photograph")
    cands.sort(reverse=True)
    keep, used_title, used_place = {}, set(), set()
    if args.keep:
        for pid, t in con.execute("SELECT id, photo_title FROM place WHERE photo_title IS NOT NULL"):
            keep[pid] = t
            used_title.add(t)
            used_place.add(pid)
    for nshared, longest, negd, pid, title in cands:
        if pid in used_place or title in used_title:
            continue
        keep[pid] = title
        used_place.add(pid)
        used_title.add(title)

    by = collections.Counter()
    hidden = 0
    pmap = {p[0]: p for p in places}
    for pid in keep:
        by[pmap[pid][3]] += 1
        if (pmap[pid][7] or 0) <= 10:
            hidden += 1
    print("   %s adventures get a photograph, all different files"
          % format(len(keep), ","))
    print("   by category: " + "  ".join("%s %s" % (k, format(v, ","))
                                         for k, v in by.most_common()))
    print("   of them hidden: %s" % format(hidden, ","))
    perd = collections.Counter()
    for pid in keep:
        perd[pmap[pid][1]] += 1
    names = dict(con.execute("SELECT id, name FROM destination"))
    print("   by destination: " + "  ".join(
        "%s %d" % (names[d], c) for d, c in sorted(perd.items(), key=lambda x: -x[1])))

    print("\n   a sample of what it chose:")
    for pid in list(keep)[:14]:
        print("     %-34s <- %s" % (pmap[pid][2][:34], keep[pid][:58]))

    if not args.write:
        print("\n(dry run — pass --write to attach and download)")
        return

    print("\n5. writing")
    con.execute("UPDATE place SET photo_title=NULL, photo=NULL")
    con.executemany("UPDATE place SET photo_title=? WHERE id=?",
                    [(t, p) for p, t in keep.items()])
    con.commit()

    print("6. downloading %s pictures at %dpx" % (format(len(set(keep.values())), ","), args.width))
    q = queue.Queue()
    for t in set(keep.values()):
        q.put(t)
    total = q.qsize()
    ths = [threading.Thread(target=downloader, args=(q, args.width, args.delay),
                            daemon=True) for _ in range(args.workers)]
    t0 = time.time()
    for t in ths:
        t.start()
    while any(t.is_alive() for t in ths):
        time.sleep(20)
        with lock:
            seen = got["ok"] + got["cached"] + got["fail"]
            rate = seen / max(time.time() - t0, 1)
            print("   %d/%d  %d new  %d cached  %d failed  ~%.0f min left"
                  % (seen, total, got["ok"], got["cached"], got["fail"],
                     (total - seen) / rate / 60 if rate else 0), flush=True)
    print("\nLOCALPICSDONE %s attached, %d downloaded, %d already cached, %d failed, %.0f min"
          % (format(len(keep), ","), got["ok"], got["cached"], got["fail"],
             (time.time() - t0) / 60))


if __name__ == "__main__":
    main()
