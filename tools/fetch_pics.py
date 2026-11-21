#!/usr/bin/env python3
"""Download the pictures the index kept but never had a copy of.

tools/photo_check.py keeps a photograph only where the filename names the place.
Most of those files were never downloaded, because the old run only fetched what
it wanted to measure. Without the file the card falls back to a blank panel.

    python3 tools/fetch_pics.py --workers 3

Writes site/img/<sha1>.jpg for every place.photo_title that has no local copy.
"""

import argparse, hashlib, io, os, queue, random, sqlite3, threading, time
import urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
IMG = os.path.join(SITE, "img")
DB = os.path.join(ROOT, "data", "index.db")
UA = "hidden-water-index/1.0 (travel index; open data)"
FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/"

lock = threading.Lock()
done = {"got": 0, "fail": 0, "throttled": 0}


def local_name(title):
    return hashlib.sha1(title.encode("utf-8")).hexdigest()[:16] + ".jpg"


def fetch(url, tries=6):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=50).read()
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


def worker(q, width, delay):
    from PIL import Image
    while True:
        try:
            title = q.get_nowait()
        except queue.Empty:
            return
        try:
            url = FILEPATH + urllib.parse.quote(title.replace(" ", "_")) + "?width=%d" % width
            im = Image.open(io.BytesIO(fetch(url))).convert("RGB")
            im.thumbnail((width, width))
            im.save(os.path.join(IMG, local_name(title)), "JPEG", quality=80, optimize=True)
            with lock:
                done["got"] += 1
            time.sleep(delay)
        except Exception:
            with lock:
                done["fail"] += 1
        finally:
            q.task_done()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--width", type=int, default=900)
    ap.add_argument("--delay", type=float, default=0.3)
    args = ap.parse_args()

    os.makedirs(IMG, exist_ok=True)
    have = set(os.listdir(IMG))
    con = sqlite3.connect(DB)
    titles = [r[0] for r in con.execute(
        "SELECT DISTINCT photo_title FROM place WHERE photo_title IS NOT NULL")]
    want = [t for t in titles if local_name(t) not in have]
    print("%s pictures kept, %s already on disk, %s to fetch"
          % (format(len(titles), ","), format(len(titles) - len(want), ","),
             format(len(want), ",")), flush=True)

    q = queue.Queue()
    for t in want:
        q.put(t)
    t0 = time.time()
    ths = [threading.Thread(target=worker, args=(q, args.width, args.delay), daemon=True)
           for _ in range(args.workers)]
    for t in ths:
        t.start()
    while any(t.is_alive() for t in ths):
        time.sleep(10)
        print("   %d/%d  %d failed  %d throttled"
              % (done["got"] + done["fail"], len(want), done["fail"], done["throttled"]), flush=True)
    print("FETCHDONE %d fetched, %d failed, %.0f min"
          % (done["got"], done["fail"], (time.time() - t0) / 60), flush=True)


if __name__ == "__main__":
    main()
