#!/usr/bin/env python3
"""Count what stands around every place, so each one can be described truthfully.

A paragraph that says "one of 214 places to eat within 2 km" is worth reading.
A paragraph that says "a restaurant" is not. These counts are also the only
evidence behind the Discovery figure, so storing them makes that figure
checkable instead of magic.

    python3 tools/neighbours.py

Adds n500, n2km and ncat2km to the place table.
"""

import collections, math, os, sqlite3, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "index.db")

NEAR = 0.0045          # ~500 m in degrees of latitude
WIDE = 0.018           # ~2 km


def main():
    con = sqlite3.connect(DB)
    for col in ("n500", "n2km", "ncat2km"):
        try:
            con.execute("ALTER TABLE place ADD COLUMN %s INTEGER" % col)
        except sqlite3.OperationalError:
            pass                        # already there
    con.commit()

    dests = con.execute("SELECT id, name FROM destination ORDER BY id").fetchall()
    t0 = time.time()
    total = 0
    for did, name in dests:
        rows = con.execute("SELECT id, lat, lon, category FROM place WHERE dest=?",
                           (did,)).fetchall()
        if not rows:
            continue
        near = collections.Counter()
        wide = collections.Counter()
        catw = collections.Counter()
        for _, lat, lon, cat in rows:
            near[(int(lat / NEAR), int(lon / NEAR))] += 1
            wide[(int(lat / WIDE), int(lon / WIDE))] += 1
            catw[(cat, int(lat / WIDE), int(lon / WIDE))] += 1

        upd = []
        for pid, lat, lon, cat in rows:
            a, b = int(lat / NEAR), int(lon / NEAR)
            c, d = int(lat / WIDE), int(lon / WIDE)
            n5 = sum(near.get((a + i, b + j), 0) for i in (-1, 0, 1) for j in (-1, 0, 1)) - 1
            n2 = sum(wide.get((c + i, d + j), 0) for i in (-1, 0, 1) for j in (-1, 0, 1)) - 1
            nc = sum(catw.get((cat, c + i, d + j), 0) for i in (-1, 0, 1) for j in (-1, 0, 1)) - 1
            upd.append((max(n5, 0), max(n2, 0), max(nc, 0), pid))
        con.executemany("UPDATE place SET n500=?, n2km=?, ncat2km=? WHERE id=?", upd)
        con.commit()
        total += len(upd)
        print("%-16s %8s places  (%.0fs)" % (name, format(len(upd), ","), time.time() - t0),
              flush=True)
    print("\nNEIGHBOURSDONE %s places counted in %.0fs" % (format(total, ","), time.time() - t0))


if __name__ == "__main__":
    main()
