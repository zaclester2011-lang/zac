#!/usr/bin/env python3
"""Find a photograph OF a place, by name, on Wikimedia Commons.

The geotag join gives each place the nearest photograph within 200 metres,
which is a picture of the area. This asks Commons for pictures of the place
itself, by name, and only keeps one whose file title actually contains a
distinctive word from that name - the standing rule that a photograph is
never accepted without checking the subject.

    python3 tools/fetch_named_photos.py --categories beach adventure
    python3 tools/fetch_named_photos.py --categories todo --limit 2000

Commons rate-limits hard from shared addresses, so this is slow and
resumable: results are written to the database as they arrive.

MEASURED RESULT, 14 Nov 2026: this does not work at scale, and the reason
is not the code. Commons holds photographs of landmarks, not of dive
centres, beach clubs or unnamed coves. Searching the best-known
photograph-less places returned zero usable hits, because the places
still missing a picture are exactly the ones nobody uploads: ordinary
businesses, and beaches too small to have been photographed. Keep the
tool for landmark gaps; it will not fill a directory.
"""
import argparse, json, os, re, sqlite3, sys, time, urllib.parse, urllib.request

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "index.db")
UA = "hidden-water-index/1.0 (open-data indexing; contact via repository)"
STOP = {"beach","bay","the","of","and","cove","paralia","plage","playa","spiaggia",
        "pantai","island","hotel","resort","restaurant","bar","cafe","tour","tours",
        "centre","center","club","villa","apartments","rooms","studios","sea","blue"}

def tokens(name):
    return [w for w in re.split(r"[^A-Za-zͰ-Ͽ]+", name.lower())
            if len(w) >= 4 and w not in STOP]

def search(query):
    url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json"
           "&generator=search&gsrsearch=" + urllib.parse.quote(query + " filetype:bitmap")
           + "&gsrnamespace=6&gsrlimit=5&prop=imageinfo&iiprop=url|extmetadata&iiurlwidth=640")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = json.load(urllib.request.urlopen(req, timeout=40))
    return list((data.get("query", {}).get("pages", {}) or {}).values())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--categories", nargs="+", default=["beach", "adventure"])
    ap.add_argument("--limit", type=int, default=100000)
    ap.add_argument("--delay", type=float, default=3.0)
    ap.add_argument("--replace", action="store_true",
                    help="also re-do places that already have a nearby photograph")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    con.execute("PRAGMA synchronous=OFF")
    where = "category IN (%s)" % ",".join("?" * len(args.categories))
    if not args.replace:
        where += " AND photo IS NULL"
    rows = con.execute(
        "SELECT id, name, locality, dest FROM place WHERE " + where
        + " ORDER BY discovery_auto DESC LIMIT ?",
        (*args.categories, args.limit)).fetchall()
    names = {d[0]: d[1] for d in con.execute("SELECT id, name FROM destination")}
    print("%s places to look up" % format(len(rows), ","), flush=True)

    found = skipped = failed = done = 0
    t0 = time.time()
    for pid, name, locality, dest in rows:
        toks = tokens(name)
        if not toks:
            skipped += 1
            continue
        query = (name + " " + names.get(dest, "")).strip()   # locality names are admin districts and only pollute the query
        hits = None
        for attempt in range(3):
            try:
                hits = search(query); break
            except Exception:
                time.sleep(8 * (attempt + 1))
        done += 1
        if hits is None:
            failed += 1
        else:
            for page in hits:
                title = page.get("title", "").replace("File:", "")
                low = title.lower()
                if not any(t in low for t in toks):
                    continue                      # subject check: the title must name the place
                info = (page.get("imageinfo") or [{}])[0]
                thumb = info.get("thumburl")
                if not thumb:
                    continue
                con.execute("UPDATE place SET photo=?, photo_title=? WHERE id=?",
                            (thumb, title, pid))
                found += 1
                break
        if done % 25 == 0:
            con.commit()
            rate = (time.time() - t0) / done
            print("   %s/%s | %s found | %s failed | %.1fs each | eta %.0f min"
                  % (format(done, ","), format(len(rows), ","), format(found, ","),
                     failed, rate, (len(rows) - done) * rate / 60), flush=True)
        time.sleep(args.delay)
    con.commit()
    print("NAMEDDONE %s found, %s failed, %s skipped" % (found, failed, skipped), flush=True)

if __name__ == "__main__":
    main()
