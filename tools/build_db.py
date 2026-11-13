#!/usr/bin/env python3
"""Build the index database — the thing that holds the world.

A JSON file sent to the browser stops working at about 100,000 places. This
builds SQLite instead: full-text search over names, a spatial grid for
bounding-box queries, photographs joined from the Commons dumps, and hotel
star ratings joined from OpenStreetMap extracts. It handles tens of millions
of rows on a machine that costs nothing.

    python3 tools/build_db.py init
    python3 tools/build_db.py import-places site/data.json
    python3 tools/build_db.py import-photos <geo_tags.sql.gz> <page.sql.gz>
    python3 tools/build_db.py import-stars  <stars_*.json> ...
    python3 tools/build_db.py match-photos --radius 150
    python3 tools/build_db.py stats
    python3 tools/build_db.py export-destination <id> <out.json>

The dumps are read as a stream, never loaded into memory: geo_tags is 733 MB
and page is 7 GB compressed.
"""

import argparse, gzip, json, os, re, sqlite3, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "index.db")

SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS destination (
  id INTEGER PRIMARY KEY, slug TEXT UNIQUE, name TEXT,
  south REAL, west REAL, north REAL, east REAL, indexed TEXT
);

CREATE TABLE IF NOT EXISTS place (
  id INTEGER PRIMARY KEY,
  dest INTEGER NOT NULL REFERENCES destination(id),
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  kind TEXT, locality TEXT, address TEXT, phone TEXT, website TEXT,
  lat REAL NOT NULL, lon REAL NOT NULL,
  confidence REAL,
  discovery_auto REAL,          -- drafted from place density
  discovery REAL, colour REAL, water REAL,   -- measured; NULL until somebody goes
  stars TEXT,                   -- hotel star rating, from OpenStreetMap
  photo TEXT,                   -- thumbnail URL
  photo_title TEXT,             -- Commons file, for attribution
  cell INTEGER                  -- spatial bucket, 0.1 degree
);
CREATE INDEX IF NOT EXISTS place_dest  ON place(dest, category);
CREATE INDEX IF NOT EXISTS place_cell  ON place(cell);
CREATE INDEX IF NOT EXISTS place_disc  ON place(dest, discovery_auto DESC);
CREATE INDEX IF NOT EXISTS place_name  ON place(name);

CREATE VIRTUAL TABLE IF NOT EXISTS place_fts
  USING fts5(name, kind, locality, content='place', content_rowid='id');

CREATE TABLE IF NOT EXISTS photo (
  page_id INTEGER PRIMARY KEY, title TEXT, lat REAL, lon REAL, cell INTEGER
);
CREATE INDEX IF NOT EXISTS photo_cell ON photo(cell);

CREATE TABLE IF NOT EXISTS review (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  place_id INTEGER REFERENCES place(id),
  discovery REAL, colour REAL, note TEXT, author TEXT, created TEXT
);
CREATE INDEX IF NOT EXISTS review_place ON review(place_id);
"""

CELL = 0.1
cell_of = lambda lat, lon: int((lat + 90) / CELL) * 4000 + int((lon + 180) / CELL)


def connect():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("PRAGMA synchronous = OFF")
    con.execute("PRAGMA cache_size = -200000")
    return con


# ------------------------------------------------------------------ commands

def cmd_init(args):
    con = connect()
    con.executescript(SCHEMA)
    con.commit()
    print("database ready at", DB)


def cmd_import_places(args):
    con = connect()
    con.executescript(SCHEMA)
    blob = json.load(open(args.data))
    rows = blob["r"]
    reg = json.load(open(os.path.join(ROOT, "site", "destinations.json")))
    for d in reg:
        con.execute("""INSERT OR REPLACE INTO destination
                       (id, slug, name, south, west, north, east, indexed)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (d["id"], d["slug"], d["name"], d["bbox"][0], d["bbox"][1],
                     d["bbox"][2], d["bbox"][3], d.get("indexed", "")))
    con.execute("DELETE FROM place")
    con.execute("DELETE FROM place_fts")
    batch = []
    for r in rows:
        batch.append((r[7], r[0], r[1], r[6], r[5], r[9], r[10], r[8],
                      r[2], r[3], r[4], r[11], None, None, None, None,
                      r[12] or None, None, cell_of(r[2], r[3])))
        if len(batch) >= 20000:
            insert_places(con, batch); batch = []
    insert_places(con, batch)
    con.execute("INSERT INTO place_fts(rowid, name, kind, locality) "
                "SELECT id, name, COALESCE(kind,''), COALESCE(locality,'') FROM place")
    con.commit()
    n = con.execute("SELECT count(*) FROM place").fetchone()[0]
    print("places imported:", format(n, ","))


def insert_places(con, batch):
    if not batch:
        return
    con.executemany("""INSERT INTO place
        (dest,name,category,kind,locality,address,phone,website,lat,lon,confidence,
         discovery_auto,discovery,colour,water,stars,photo,photo_title,cell)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", batch)


# ---- Commons dumps -------------------------------------------------------

def sql_rows(path, columns):
    """Stream tuples out of a MediaWiki INSERT dump without loading it."""
    value = re.compile(r"\(((?:[^()']|'(?:\\.|[^'\\])*')*)\)")
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.startswith("INSERT INTO"):
                continue
            for m in value.finditer(line):
                parts, cur, quoted, esc = [], [], False, False
                for ch in m.group(1):
                    if esc:
                        cur.append(ch); esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == "'":
                        quoted = not quoted
                    elif ch == "," and not quoted:
                        parts.append("".join(cur)); cur = []
                    else:
                        cur.append(ch)
                parts.append("".join(cur))
                if len(parts) >= columns:
                    yield parts


def cmd_import_photos(args):
    """geo_tags gives coordinates per page; page gives the file name."""
    con = connect()
    con.executescript(SCHEMA)
    con.execute("DELETE FROM photo")

    print("1. geo_tags")
    seen, batch, n = set(), [], 0
    t0 = time.time()
    for p in sql_rows(args.geo_tags, 8):
        # gt_id, gt_page_id, gt_globe, gt_primary, gt_lat, gt_lon, ...
        try:
            pid = int(p[1]); lat = float(p[4]); lon = float(p[5])
        except (ValueError, IndexError):
            continue
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180) or pid in seen:
            continue
        seen.add(pid)
        batch.append((pid, None, lat, lon, cell_of(lat, lon)))
        if len(batch) >= 50000:
            con.executemany("INSERT OR IGNORE INTO photo VALUES (?,?,?,?,?)", batch)
            n += len(batch); batch = []
            print("   %s coordinates (%.0fs)" % (format(n, ","), time.time() - t0), flush=True)
    con.executemany("INSERT OR IGNORE INTO photo VALUES (?,?,?,?,?)", batch)
    n += len(batch)
    con.commit()
    print("   %s geotagged pages" % format(n, ","))

    print("2. page titles (file namespace only)")
    hit, batch, t0 = 0, [], time.time()
    for p in sql_rows(args.page, 3):
        # page_id, page_namespace, page_title, ...
        try:
            pid = int(p[0]); ns = int(p[1])
        except (ValueError, IndexError):
            continue
        if ns != 6 or pid not in seen:
            continue
        batch.append((p[2], pid))
        if len(batch) >= 50000:
            con.executemany("UPDATE photo SET title=? WHERE page_id=?", batch)
            hit += len(batch); batch = []
            print("   %s titles (%.0fs)" % (format(hit, ","), time.time() - t0), flush=True)
    con.executemany("UPDATE photo SET title=? WHERE page_id=?", batch)
    hit += len(batch)
    con.execute("DELETE FROM photo WHERE title IS NULL")
    con.commit()
    kept = con.execute("SELECT count(*) FROM photo").fetchone()[0]
    print("   %s geotagged photographs, worldwide" % format(kept, ","))


def cmd_match_photos(args):
    """Give each place the nearest geotagged photograph within a radius."""
    con = connect()
    radius_km = args.radius / 1000.0
    con.execute("UPDATE place SET photo=NULL, photo_title=NULL")
    places = con.execute("SELECT id, lat, lon, cell FROM place").fetchall()
    print("matching %s places against %s photographs"
          % (format(len(places), ","), format(
              con.execute("SELECT count(*) FROM photo").fetchone()[0], ",")))
    cur, out, done = con.cursor(), [], 0
    for pid, lat, lon, cell in places:
        best = None
        for dc in (-4001, -4000, -3999, -1, 0, 1, 3999, 4000, 4001):
            for ph_title, plat, plon in cur.execute(
                    "SELECT title, lat, lon FROM photo WHERE cell=?", (cell + dc,)):
                d = ((plat - lat) * 111.0) ** 2 + ((plon - lon) * 111.0 * 0.8) ** 2
                if best is None or d < best[0]:
                    best = (d, ph_title)
        if best and best[0] <= radius_km ** 2:
            url = ("https://commons.wikimedia.org/wiki/Special:FilePath/"
                   + best[1].replace(" ", "_") + "?width=480")
            out.append((url, best[1], pid))
        done += 1
        if done % 20000 == 0:
            print("   %s / %s" % (format(done, ","), format(len(places), ",")), flush=True)
    con.executemany("UPDATE place SET photo=?, photo_title=? WHERE id=?", out)
    con.commit()
    print("   %s places now have a photograph (%.1f%%)"
          % (format(len(out), ","), 100.0 * len(out) / max(len(places), 1)))


def cmd_import_stars(args):
    con = connect()
    total = 0
    for path in args.files:
        hotels = json.load(open(path))
        done = 0
        for h in hotels:
            row = con.execute(
                """SELECT id FROM place
                   WHERE category='hotel'
                     AND abs(lat-?)<0.004 AND abs(lon-?)<0.004
                   ORDER BY abs(lat-?)+abs(lon-?) LIMIT 1""",
                (h["lat"], h["lon"], h["lat"], h["lon"])).fetchone()
            if row:
                con.execute("UPDATE place SET stars=? WHERE id=?", (h["stars"], row[0]))
                done += 1
        con.commit()
        print("%-26s %s of %s matched to a hotel"
              % (os.path.basename(path), done, len(hotels)))
        total += done
    print("hotels with a star rating:", total)


def cmd_stats(args):
    con = connect()
    q = lambda s: con.execute(s).fetchall()
    print("destinations")
    for d in q("""SELECT d.name, count(p.id), sum(p.photo IS NOT NULL),
                         sum(p.stars IS NOT NULL)
                  FROM destination d LEFT JOIN place p ON p.dest=d.id
                  GROUP BY d.id ORDER BY d.id"""):
        print("   %-18s %9s places  %7s photos  %5s starred"
              % (d[0], format(d[1], ","), format(d[2] or 0, ","), d[3] or 0))
    print("\nby category")
    for c in q("""SELECT category, count(*), sum(photo IS NOT NULL)
                  FROM place GROUP BY category ORDER BY count(*) DESC"""):
        print("   %-12s %9s  %7s with a photo" % (c[0], format(c[1], ","), format(c[2] or 0, ",")))
    tot = q("SELECT count(*) FROM place")[0][0]
    ph = q("SELECT count(*) FROM photo")[0][0]
    rv = q("SELECT count(*) FROM review")[0][0]
    print("\n   %s places | %s photographs on file | %s reviews | %.0f MB"
          % (format(tot, ","), format(ph, ","), format(rv, ","),
             os.path.getsize(DB) / 1e6))


def cmd_export(args):
    """Write one destination back out as the JSON the static site reads."""
    con = connect()
    rows = con.execute(
        """SELECT name, category, lat, lon, confidence, locality, kind, dest,
                  website, address, phone, discovery_auto, photo, stars
           FROM place WHERE dest=? ORDER BY discovery_auto DESC""",
        (args.dest,)).fetchall()
    out = [[r[0], r[1], r[2], r[3], r[4], r[5] or "", r[6] or "", r[7],
            r[8] or "", r[9] or "", r[10] or "", r[11], r[12] or "", r[13] or ""]
           for r in rows]
    json.dump({"f": ["n","c","lat","lon","q","loc","k","d","w","a","tel","ad","img","stars"],
               "r": out}, open(args.out, "w"), ensure_ascii=False, separators=(",", ":"))
    print("%s places written to %s (%.1f MB)"
          % (format(len(out), ","), args.out, os.path.getsize(args.out) / 1e6))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(func=cmd_init)
    a = sub.add_parser("import-places"); a.add_argument("data"); a.set_defaults(func=cmd_import_places)
    b = sub.add_parser("import-photos"); b.add_argument("geo_tags"); b.add_argument("page")
    b.set_defaults(func=cmd_import_photos)
    c = sub.add_parser("import-stars"); c.add_argument("files", nargs="+"); c.set_defaults(func=cmd_import_stars)
    d = sub.add_parser("match-photos"); d.add_argument("--radius", type=float, default=150.0,
                                                       help="metres; default 150")
    d.set_defaults(func=cmd_match_photos)
    sub.add_parser("stats").set_defaults(func=cmd_stats)
    e = sub.add_parser("export-destination"); e.add_argument("dest", type=int); e.add_argument("out")
    e.set_defaults(func=cmd_export)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
