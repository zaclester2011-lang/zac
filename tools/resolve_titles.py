#!/usr/bin/env python3
"""Give the geotagged photographs their filenames, from the Commons page dump.

The photo table holds 43,274,245 geotagged Commons files with coordinates but
almost no titles, because the coordinates come from the geo_tags dump and the
titles live in the page dump, which was never read. Without a title a row is
useless: a title is the only evidence that a picture is OF a place rather than
merely near one.

That is what made picture-finding slow and poor. Asking Commons for every place
one at a time means one throttled request per place — 7,460 requests, six hours,
and the API answers 429 long before that. With the titles resolved it becomes a
local join: every candidate picture within three kilometres of every place, with
no network at all.

Only the photographs inside the destinations are resolved. Worldwide is 43
million rows; inside the 44 bounding boxes it is about half a million, so the
set of wanted page ids fits in memory and the dump is read once.

    python3 tools/resolve_titles.py data/page.sql.gz

The dump is streamed through zcat, so decompression runs on another core and
nothing but the matched titles is ever held.
"""

import argparse, os, re, sqlite3, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "index.db")
MARGIN = 0.06          # degrees of slack around each bounding box

# A page tuple is (page_id, page_namespace, 'page_title', ...). Namespace 6 is
# the file namespace. Matching the namespace inside the pattern means the regex
# engine rejects every other page without Python seeing it.
ROW = re.compile(rb"\((\d+),6,'((?:[^'\\]|\\.){1,255}?)'")
CHUNK = 1 << 23        # 8 MB
OVERLAP = 2048         # a tuple is far shorter than this, so none is cut in two


def wanted_ids(con):
    """page ids of geotagged photographs inside any destination, with slack."""
    boxes = con.execute("SELECT south, west, north, east FROM destination").fetchall()
    ids = set()
    for s, w, n, e in boxes:
        for (pid,) in con.execute(
                "SELECT page_id FROM photo WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?",
                (s - MARGIN, n + MARGIN, w - MARGIN, e + MARGIN)):
            ids.add(pid)
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump", help="commonswiki-latest-page.sql.gz")
    args = ap.parse_args()
    if not os.path.exists(args.dump):
        sys.exit("no such dump: %s" % args.dump)

    con = sqlite3.connect(DB)
    print("1. which photographs matter")
    want = wanted_ids(con)
    print("   %s geotagged pages inside the 44 destinations" % format(len(want), ","),
          flush=True)

    # whatever an earlier pass already resolved
    found = {}
    for pid, title in con.execute("SELECT page_id, title FROM pagetitle"):
        if pid in want and title:
            found[pid] = title.replace("_", " ")
    print("   %s already known from an earlier pass" % format(len(found), ","), flush=True)

    print("2. reading the page dump")
    size = os.path.getsize(args.dump)
    proc = subprocess.Popen(["zcat", args.dump], stdout=subprocess.PIPE,
                            bufsize=CHUNK)
    t0 = time.time()
    tail = b""
    read = rows = 0
    try:
        while True:
            chunk = proc.stdout.read(CHUNK)
            if not chunk:
                break
            read += len(chunk)
            buf = tail + chunk
            for m in ROW.finditer(buf):
                rows += 1
                pid = int(m.group(1))
                if pid in want and pid not in found:
                    # the dump escapes quotes and backslashes, and writes spaces
                    # as underscores
                    raw = m.group(2).replace(b"\\'", b"'").replace(b'\\"', b'"') \
                                    .replace(b"\\\\", b"\\")
                    title = raw.decode("utf-8", "replace").replace("_", " ")
                    if title.lower().endswith((".jpg", ".jpeg", ".png")):
                        found[pid] = title
            tail = buf[-OVERLAP:]
            if read % (CHUNK * 64) < CHUNK:
                el = time.time() - t0
                print("   %5.1f GB decompressed  %s file pages seen  %s titles found"
                      "  (%.0fs)"
                      % (read / 1e9, format(rows, ","), format(len(found), ","), el),
                      flush=True)
    finally:
        proc.stdout.close()
        proc.wait()

    print("   %s file pages read in %.0f min" % (format(rows, ","), (time.time() - t0) / 60))

    print("3. writing them back")
    items = list(found.items())
    for i in range(0, len(items), 20000):
        batch = [(t, p) for p, t in items[i:i + 20000]]
        con.executemany("UPDATE photo SET title=? WHERE page_id=?", batch)
    con.commit()
    # keep them, so a rerun of this costs nothing
    con.executemany("INSERT OR REPLACE INTO pagetitle VALUES (?,?)",
                    [(p, t) for p, t in items])
    con.commit()
    have = con.execute("SELECT count(*) FROM photo WHERE title IS NOT NULL").fetchone()[0]
    print("\nTITLESDONE %s of %s wanted photographs now have a filename "
          "(%s titled in all)"
          % (format(len(found), ","), format(len(want), ","), format(have, ",")))


if __name__ == "__main__":
    main()
