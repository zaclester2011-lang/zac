#!/usr/bin/env python3
"""Find each place its own photograph by asking Commons for it by name.

The geotagged index cannot do this. Of 43 million geotagged files only 61,383
filenames were ever resolved, so 190,000 places were being illustrated from a
pool of 61,000 pictures — which is how one file ended up on 187 places and a
dive resort got a number plate.

Asking Commons for the place by name is the method that produced the hero
pictures, and it is the only one that establishes identity. A result is accepted
only when the filename carries a word from the place's own name that is not a
trade word and not a local place name, so "Hard Rock Cafe Phuket" may match but
"something photographed in Phuket" may not. Every file is used once.

    python3 tools/name_pics.py --category beach --per 20
    python3 tools/name_pics.py --category food,club,hotel --per 10

Writes place.photo_title and caches the picture into site/img/.
"""

import argparse, collections, hashlib, io, json, os, re, sqlite3, time, unicodedata
import urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
IMG = os.path.join(SITE, "img")
DB = os.path.join(ROOT, "data", "index.db")
UA = "hidden-water-index/1.0 (travel index; open data)"
API = "https://commons.wikimedia.org/w/api.php"
FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/"

GENERIC = set("""hotel hotels motel restaurant restaurante ristorante bar bars cafe caffe kafeneio
club pub tavern beach beaches playa platja praia spiaggia paralia plage strand coast shore
the and of de la le el los las il lo du des von der resort villa villas apartment apartments
rooms room suite suites studio studios guest house inn lodge lodging hostel camping taverna
pizzeria grill bistro lounge view sea seaside beachfront waterfront panorama north south
east west grande piccola nova velha new old""".split())

JUNK = re.compile(r"""(?ix) \b(
    map|plan|diagram|logo|sign|signpost|plaque|notice|poster|menu|coat.of.arms|flag|
    parking|car.park|bus|tram|train|aircraft|ambulance|plate|licence|license|
    portrait|selfie|mugshot|grave|tomb|cemetery|screenshot|scan|document|invoice
  )\b""")


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
            time.sleep(5 * (attempt + 1))
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")


def search(query, limit=8):
    url = (API + "?action=query&format=json&generator=search&gsrnamespace=6&gsrsearch="
           + urllib.parse.quote(query) + "&gsrlimit=%d&prop=imageinfo&iiprop=url|size" % limit)
    try:
        data = json.loads(get(url))
    except Exception:
        return []
    out = []
    for p in ((data.get("query") or {}).get("pages") or {}).values():
        t = p.get("title", "")
        if t.lower().startswith("file:") and t.lower().endswith((".jpg", ".jpeg", ".png")):
            out.append(t[5:])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", default="beach,water,rock,trail,sea")
    ap.add_argument("--per", type=int, default=20, help="places per destination")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--width", type=int, default=900)
    args = ap.parse_args()

    cats = [c.strip() for c in args.category.split(",") if c.strip()]
    os.makedirs(IMG, exist_ok=True)
    con = sqlite3.connect(DB)
    taken = set(r[0] for r in con.execute(
        "SELECT photo_title FROM place WHERE photo_title IS NOT NULL"))

    dests = con.execute("SELECT id, name FROM destination ORDER BY id").fetchall()
    # a word on more than three places in a destination is a place name
    df = collections.defaultdict(collections.Counter)
    for d, n in con.execute("SELECT dest, name FROM place WHERE category IN (%s)"
                            % ",".join("?" * len(cats)), cats):
        for w in set(words(n)):
            df[d][w] += 1

    targets = []
    for did, dname in dests:
        for cat in cats:
            rows = con.execute("""SELECT id, name FROM place
                                  WHERE dest=? AND category=? AND photo_title IS NULL
                                  ORDER BY confidence DESC LIMIT ?""",
                               (did, cat, args.per)).fetchall()
            for pid, nm in rows:
                targets.append((pid, did, dname, nm))
    print("%s places to look up" % format(len(targets), ","), flush=True)

    found = miss = 0
    t0 = time.time()
    for i, (pid, did, dname, nm) in enumerate(targets, 1):
        ident = {w for w in set(words(nm)) if df[did][w] <= 3}
        if not ident:
            miss += 1
            continue
        # A quoted phrase query returns nothing on Commons even for places it
        # holds pictures of, so the terms go in plain.
        hit = None
        for q in ("%s %s" % (nm, dname), nm):
            for title in search(q):
                if title in taken or JUNK.search(title.replace("_", " ")):
                    continue
                if ident & set(words(title)):
                    hit = title
                    break
            time.sleep(args.delay)
            if hit:
                break
        if not hit:
            miss += 1
        else:
            try:
                from PIL import Image
                url = FILEPATH + urllib.parse.quote(hit.replace(" ", "_")) + "?width=%d" % args.width
                im = Image.open(io.BytesIO(get(url))).convert("RGB")
                im.thumbnail((args.width, args.width))
                im.save(os.path.join(IMG, local_name(hit)), "JPEG", quality=80, optimize=True)
                con.execute("UPDATE place SET photo_title=? WHERE id=?", (hit, pid))
                con.commit()
                taken.add(hit)
                found += 1
                print("   %-32s <- %s" % (nm[:32], hit[:52]), flush=True)
            except Exception:
                miss += 1
            time.sleep(args.delay)
        if i % 25 == 0:
            rate = i / max(time.time() - t0, 1)
            print("   %d/%d  %d found  %d none  ~%.0f min left"
                  % (i, len(targets), found, miss, (len(targets) - i) / rate / 60), flush=True)
    print("NAMEPICSDONE %d found, %d without one, %.0f min"
          % (found, miss, (time.time() - t0) / 60), flush=True)


if __name__ == "__main__":
    main()
