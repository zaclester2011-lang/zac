#!/usr/bin/env python3
"""Score any single place on the scale, anywhere on earth.

score_la.py can only score the thirty-six places hard-coded in its PLACES list.
This takes a name and a coordinate instead, so a place that never made it into
the index — because Overture does not map it, or because it falls outside a
destination's bounding box — can still be put on the same footing as Crete.

Everything that produces a number is imported, not reimplemented:

  Discovery  rate.discovery(), off how much Overture has mapped within 500 m
             and 2 km of the point.
  Colour     measure_water.water_colour() on a Commons photograph that names
             the place, then rate.colour(). The subject filters, the foliage
             guard and the one-third-water floor all come from score_la.
  Water      10 when you can swim in it, nothing when you cannot. Passed in,
             because no dataset answers it.

    python3 tools/score_place.py "Wayag" -0.17 130.02 --swimmable
    python3 tools/score_place.py "Wayag" -0.17 130.02 --swimmable --radius 12000

Prints the three columns and the total. Writes nothing.
"""

import argparse, math, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import rate
import score_la                   # measure(), km(), the filters, the guards


def density(lat, lon, pad=0.030):
    """Everything Overture has mapped in a small box round one point."""
    import index_destination as idx
    rel, urls = idx.overture_files()
    import duckdb
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        os.environ.pop(k, None)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    dx = pad / math.cos(math.radians(lat))
    sql = """
        SELECT ROUND(bbox.ymin, 5) AS lat, ROUND(bbox.xmin, 5) AS lon
        FROM read_parquet([%s])
        WHERE bbox.xmin BETWEEN %f AND %f
          AND bbox.ymin BETWEEN %f AND %f
          AND names.primary IS NOT NULL
    """ % (",".join("'%s'" % u for u in urls),
           lon - dx, lon + dx, lat - pad, lat + pad)
    print("   querying Overture %s…" % rel, flush=True)
    t0 = time.time()
    rows = con.execute(sql).fetchall()
    print("   %d mapped places in the box (%.0fs)" % (len(rows), time.time() - t0), flush=True)
    n500 = sum(1 for la, lo in rows if score_la.km(lat, lon, la, lo) <= 0.5)
    n2km = sum(1 for la, lo in rows if score_la.km(lat, lon, la, lo) <= 2.0)
    return n500, n2km


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("lat", type=float)
    ap.add_argument("lon", type=float)
    ap.add_argument("--swimmable", action="store_true",
                    help="is there enough water to swim in")
    ap.add_argument("--radius", type=int, default=4000,
                    help="metres to search Commons for a photograph (default 4000)")
    ap.add_argument("--tries", type=int, default=8)
    args = ap.parse_args()

    print("1. how much is mapped around it")
    n500, n2km = density(args.lat, args.lon)
    d = rate.discovery(n500, n2km, None, None)
    print("   %d within 500 m, %d within 2 km  ->  Discovery %.1f" % (n500, n2km, d))

    print("2. what the water looks like")
    old = score_la.geosearch
    score_la.geosearch = lambda la, lo, radius=args.radius, limit=200: old(la, lo, radius, limit)
    title, dist, c = score_la.measure(args.name, args.lat, args.lon, tries=args.tries)
    score_la.geosearch = old

    if c:
        col = rate.colour(c["hue"], c["sat"], c["share"])
        print("   %s  (%.1f km away)" % (title, dist))
        print("   hue %.1f  sat %.2f  water %d%%  ->  Colour %.1f"
              % (c["hue"], c["sat"], round(c["share"] * 100), col))
    else:
        col = None
        print("   no photograph of it shows enough water")

    w = 10.0 if args.swimmable else None
    print()
    print("%-28s Disc %4.1f   Colour %s   Water %s" % (
        args.name, d,
        "%4.1f" % col if col is not None else "   —",
        "%4.1f" % w if w is not None else "   —"))
    if col is not None and w is not None:
        total = d + col + w
        print("%-28s TOTAL %.1f / 30   %s" % (
            "", total, "clears 25" if total >= 25 else "below the bar"))


if __name__ == "__main__":
    main()
