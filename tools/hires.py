#!/usr/bin/env python3
"""Fetch the showcase pictures again, big enough for the size they are drawn at.

Everything in site/img was downloaded at 360 or 440 pixels wide, because it was
downloaded to be measured, not to be looked at. The pack hero is drawn 1,248
pixels wide on a desktop, so a 440-pixel file was being stretched 2.8 times —
5.7 times on a retina screen. That is the blur.

    python3 tools/hires.py                 # heroes at 1800, top tens at 900

Reads site/packs.json for the Commons title behind each picture and writes
site/hi/<sha1>.jpg. stage_artifact.py prefers these over the small copies.
"""

import argparse, hashlib, io, json, os, queue, random, threading, time
import urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
HI = os.path.join(SITE, "hi")
UA = "hidden-water-index/1.0 (travel index; open data)"
FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/"

lock = threading.Lock()
done = {"got": 0, "cached": 0, "fail": 0, "throttled": 0}

# Keep only part of a picture, as fractions of its height (top, bottom).
# Zac asked for Zanzibar under the sea with no beach in sight. Commons has
# almost no fully-underwater Zanzibar photographs, and the ones it has are
# single-species portraits on a plain blue backdrop. This one is Mnemba, it is
# the right water and the right fish, and its top four tenths are the island —
# so the island goes.
CROP = {
    "Mnemba Island - Zanzibar - Flickr - Jorge Lascar.jpg": (0.40, 1.0),
}


def local_name(title, width):
    return hashlib.sha1(("%s@%d" % (title, width)).encode("utf-8")).hexdigest()[:16] + ".jpg"


def fetch(url, tries=6):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=60).read()
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


def worker(q, delay):
    from PIL import Image
    while True:
        try:
            title, width = q.get_nowait()
        except queue.Empty:
            return
        path = os.path.join(HI, local_name(title, width))
        try:
            if os.path.exists(path):
                with lock:
                    done["cached"] += 1
            else:
                url = (FILEPATH + urllib.parse.quote(title.replace(" ", "_"))
                       + "?width=%d" % width)
                im = Image.open(io.BytesIO(fetch(url))).convert("RGB")
                if title in CROP:
                    top, bot = CROP[title]
                    w0, h0 = im.size
                    im = im.crop((0, int(h0 * top), w0, int(h0 * bot)))
                im.thumbnail((width, width))
                im.save(path, "JPEG", quality=84, optimize=True, progressive=True)
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
    ap.add_argument("--hero-width", type=int, default=1800)
    ap.add_argument("--top-width", type=int, default=900)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--delay", type=float, default=0.3)
    args = ap.parse_args()

    os.makedirs(HI, exist_ok=True)
    packs = json.load(open(os.path.join(SITE, "packs.json")))
    if any((p.get("hero") or "").startswith("pk/") for p in packs):
        raise SystemExit("packs.json is staged — run build_packs.py first")

    jobs, seen = [], set()
    for p in packs:
        if p.get("hero_title"):
            jobs.append((p["hero_title"], args.hero_width))
        for t in p.get("top", []):
            c = t.get("credit")
            if c and (c, args.top_width) not in seen:
                seen.add((c, args.top_width))
                jobs.append((c, args.top_width))
    print("%s pictures to fetch (%d heroes at %dpx, %d top-ten at %dpx)"
          % (format(len(jobs), ","), len(packs), args.hero_width,
             len(jobs) - len(packs), args.top_width), flush=True)

    q = queue.Queue()
    for j in jobs:
        q.put(j)
    t0 = time.time()
    threads = [threading.Thread(target=worker, args=(q, args.delay), daemon=True)
               for _ in range(args.workers)]
    for t in threads:
        t.start()
    while any(t.is_alive() for t in threads):
        time.sleep(10)
        with lock:
            seen_n = done["got"] + done["cached"] + done["fail"]
        print("   %s/%s  %s new  %s cached  %s throttled  %s failed"
              % (format(seen_n, ","), format(len(jobs), ","), done["got"],
                 done["cached"], done["throttled"], done["fail"]), flush=True)

    size = sum(os.path.getsize(os.path.join(HI, f)) for f in os.listdir(HI))
    print("HIRESDONE %s files in site/hi, %.1f MB, %.0f min"
          % (format(len(os.listdir(HI)), ","), size / 1e6, (time.time() - t0) / 60), flush=True)


if __name__ == "__main__":
    main()
