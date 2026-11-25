#!/usr/bin/env python3
"""Index the adventure destinations, one after another.

index_destination.py resolves a bounding box from the name when it can, but it
put Lofoten at 60.5 degrees north, about nine hundred kilometres south of
Lofoten, so every box here is given explicitly. south, west, north, east.

    python3 tools/adventure_dests.py            # list them
    python3 tools/adventure_dests.py --run
"""

import argparse, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DESTS = [
    # name,                      south,   west,   north,   east
    ("Dolomites",                46.20,   11.00,  46.90,   12.40),
    ("Fiordland",               -45.60,  166.80, -44.40,  168.60),
    ("Isle of Skye",             57.05,   -6.90,  57.75,   -5.75),
    ("Bernese Oberland",         46.40,    7.55,  46.80,    8.35),
    ("Soca Valley",              46.08,   13.35,  46.48,   13.95),
    ("Wadi Rum",                 29.35,   35.25,  29.85,   35.65),
    ("Atlas Mountains",          30.85,   -8.25,  31.45,   -7.60),
    ("Arenal and Monteverde",    10.15,  -85.15,  10.85,  -84.35),
    ("Sacred Valley",           -13.65,  -72.65, -12.95,  -71.55),
    ("El Chalten",              -49.60,  -73.35, -48.95,  -72.55),
    ("Torres del Paine",        -51.60,  -73.55, -50.60,  -72.35),
    ("Tenerife",                 27.95,  -16.95,  28.65,  -16.05),
    ("Faroe Islands",            61.35,   -7.75,  62.42,   -6.20),
    ("Krabi",                     7.75,   98.55,   8.45,   99.15),
    ("Phong Nha",                17.35,  106.05,  17.75,  106.45),
    ("Komodo and Flores",        -8.95,  119.25,  -8.15,  120.30),
    ("Raja Ampat",               -1.25,  129.65,  -0.15,  131.25),
    ("Reunion",                 -21.42,   55.18, -20.82,   55.90),
    ("Kauai",                    21.84, -159.82,  22.27, -159.26),
    ("Ningaloo",                -23.65,  113.35, -21.75,  114.35),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--only", help="comma-separated names, for a re-run")
    args = ap.parse_args()

    if not args.run:
        for n, s, w, nn, e in DESTS:
            print("   %-24s %7.2f,%8.2f to %7.2f,%8.2f" % (n, s, w, nn, e))
        print("\n%d destinations — pass --run" % len(DESTS))
        return

    todo = DESTS
    if args.only:
        want = {x.strip().lower() for x in args.only.split(",")}
        todo = [d for d in DESTS if d[0].lower() in want]
    t0 = time.time()
    done = fail = 0
    for i, (name, s, w, n, e) in enumerate(todo, 1):
        print("\n=== %d/%d  %s ===" % (i, len(todo), name), flush=True)
        cmd = [sys.executable, "-I", os.path.join(ROOT, "tools", "index_destination.py"),
               "add", name, "--bbox=%s,%s,%s,%s" % (s, w, n, e)]
        try:
            out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1800)
            tail = [l for l in out.stdout.splitlines() if ": " in l and "places" in l]
            print("   " + (tail[-1].strip() if tail else "no summary line"), flush=True)
            if out.returncode != 0:
                fail += 1
                print("   FAILED rc=%d %s" % (out.returncode, out.stderr[-200:]), flush=True)
            else:
                done += 1
        except subprocess.TimeoutExpired:
            fail += 1
            print("   TIMED OUT", flush=True)
    print("\nADVDESTSDONE %d added, %d failed, %.0f min"
          % (done, fail, (time.time() - t0) / 60), flush=True)


if __name__ == "__main__":
    main()
