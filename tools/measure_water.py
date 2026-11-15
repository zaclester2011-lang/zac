#!/usr/bin/env python3
"""Download and measure every photograph attached to a water-relevant place.

Colour cannot be rated without looking at the water, and there are 27,000
photographs to look at. Special:FilePath is served from Wikimedia's image CDN,
not the API, so it tolerates a handful of parallel fetches; the API does not,
which is why nothing here touches it.

    python3 tools/measure_water.py --workers 6
    python3 tools/measure_water.py --workers 6 --limit 2000

Appends to site/colours.json every 200 photographs, so a run that is cut off
loses at most 200 readings rather than all of them.
"""

import argparse, colorsys, hashlib, io, json, os, queue, random, threading, time
import urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
IMG = os.path.join(SITE, "img")
DB = os.path.join(ROOT, "data", "index.db")
OUT = os.path.join(SITE, "colours.json")
UA = "hidden-water-index/1.0 (travel index; open data)"
FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/"

lock = threading.Lock()
done = {"got": 0, "fail": 0, "cached": 0, "nowater": 0, "throttled": 0}


def local_name(title):
    return hashlib.sha1(title.encode("utf-8")).hexdigest()[:16] + ".jpg"


def water_colour(im):
    """Median hue, saturation and value of the blue-green water in the lower frame."""
    w, h = im.size
    box = im.crop((int(w * 0.15), int(h * 0.45), int(w * 0.85), int(h * 0.95))).resize((60, 40))
    hs, ss, vs = [], [], []
    for r, g, b in box.getdata():
        hh, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        hue = hh * 360
        if 140 <= hue <= 250 and s > 0.12 and 0.15 < v < 0.97:
            hs.append(hue); ss.append(s); vs.append(v)
    if len(hs) < 150:
        return None
    hs.sort(); ss.sort(); vs.sort()
    m = len(hs) // 2
    return {"hue": round(hs[m], 1), "sat": round(ss[m], 2), "val": round(vs[m], 2),
            "share": round(len(hs) / 2400.0, 2)}


def fetch(url, tries=6):
    """Wikimedia answers 429 when pushed. Back off and come back rather than
    counting a rate limit as a missing photograph — that lost a third of a run."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=40).read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or attempt == tries - 1:
                raise
            with lock:
                done["throttled"] += 1
            time.sleep(4 * (attempt + 1) + random.random() * 2)
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def worker(q, results, width, delay):
    from PIL import Image
    while True:
        try:
            title = q.get_nowait()
        except queue.Empty:
            return
        path = os.path.join(IMG, local_name(title))
        try:
            if os.path.exists(path):
                im = Image.open(path).convert("RGB")
                with lock:
                    done["cached"] += 1
            else:
                url = FILEPATH + urllib.parse.quote(title.replace(" ", "_")) + "?width=%d" % width
                raw = fetch(url)
                im = Image.open(io.BytesIO(raw)).convert("RGB")
                im.thumbnail((width, width))
                im.save(path, "JPEG", quality=70, optimize=True)
                with lock:
                    done["got"] += 1
                time.sleep(delay)
            c = water_colour(im)
            with lock:
                if c:
                    results[title] = c
                else:
                    done["nowater"] += 1
        except Exception:
            with lock:
                done["fail"] += 1
        finally:
            q.task_done()


def flush(results):
    old = {}
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT))
        except Exception:
            old = {}
    old.update(results)
    tmp = OUT + ".tmp"
    json.dump(old, open(tmp, "w"), ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUT)
    return len(old)


def main():
    import sqlite3
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=100000)
    ap.add_argument("--width", type=int, default=360)
    ap.add_argument("--delay", type=float, default=0.3)
    args = ap.parse_args()

    os.makedirs(IMG, exist_ok=True)
    con = sqlite3.connect(DB)
    have = set()
    if os.path.exists(OUT):
        try:
            have = set(json.load(open(OUT)))
        except Exception:
            have = set()
    # only places whose Colour rating would mean something — the same test rate.py uses
    import re as _re
    WORD = _re.compile(r"""(?ix) (
        beach|bay|cove|lagoon|lake|river|waterfall|cascade|spring|gorge|canyon|
        cave|reef|island|islet|harbour|harbor|marina|pool|sea|coast|shore|strand|
        playa|spiaggia|cala|paralia|limni|akti|falls|creek|delta|estuary|fjord|
        sandbar|peninsula|cape|lido|plage|praia
      )""")
    rows = con.execute("""SELECT DISTINCT photo_title, category, kind, name FROM place
                          WHERE photo_title IS NOT NULL
                            AND category IN ('beach','adventure','todo')
                          ORDER BY (category='beach') DESC""").fetchall()
    titles, seen_t = [], set()
    for t, cat, kind, nm in rows:
        if t in have or t in seen_t:
            continue
        if cat in ("beach", "adventure") or WORD.search((kind or "") + " " + (nm or "")):
            seen_t.add(t)
            titles.append(t)
    titles = titles[:args.limit]
    print("%s photographs to measure (%s already read)"
          % (format(len(titles), ","), format(len(have), ",")), flush=True)

    q = queue.Queue()
    for t in titles:
        q.put(t)
    results = {}
    t0 = time.time()
    threads = [threading.Thread(target=worker, args=(q, results, args.width, args.delay),
                                daemon=True) for _ in range(args.workers)]
    for th in threads:
        th.start()

    last = 0
    while any(th.is_alive() for th in threads):
        time.sleep(10)
        with lock:
            seen = done["got"] + done["cached"] + done["fail"]
            if len(results) - last >= 200:
                last = len(results)
                flush(dict(results))
        if seen:
            rate = seen / max(time.time() - t0, 1)
            left = (len(titles) - seen) / rate if rate else 0
            print("   %s/%s  %s new  %s no water  %s throttled  %s failed  %.1f/s  ~%.0f min left"
                  % (format(seen, ","), format(len(titles), ","), format(done["got"], ","),
                     format(done["nowater"], ","), format(done["throttled"], ","),
                     format(done["fail"], ","), rate, left / 60), flush=True)
    total = flush(results)
    print("MEASUREDONE %s readings in colours.json, %s new downloads, %s failed, %.0f min"
          % (format(total, ","), format(done["got"], ","), format(done["fail"], ","),
             (time.time() - t0) / 60), flush=True)


if __name__ == "__main__":
    main()
