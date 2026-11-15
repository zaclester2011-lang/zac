#!/usr/bin/env python3
"""Put bars and nightclubs back in the bar category, and throw the rest out.

The category was first assigned by looking for "bar" and "pub" inside the kind,
with no word boundaries, so it collected 6,550 barbers, 1,453 publishers, 1,496
public health clinics, 1,167 public schools and 959 notaries public. It also
took anything that merely serves drinks alongside food — barbecue restaurants,
salad bars, smoothie bars.

    python3 tools/recat.py            # show what would move
    python3 tools/recat.py --write    # move it

With word boundaries "barber" and "public" stop matching on their own, so what
is left to decide is the places that really are called a bar but are a
restaurant, a juice counter or an airport lounge.
"""

import argparse, re, sqlite3, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "index.db")

# a bar or a nightclub, and nothing else
CLUB_YES = re.compile(r"""(?ix) \b(
    bar|bars|pub|pubs|gastropub|brewpub|taproom|tavern|brewery|beer|ale\ house|
    wine\ bar|cocktail|speakeasy|nightclub|night\ club|disco|discotheque|
    club|lounge|music\ venue|live\ music|karaoke|cabaret|hookah|shisha
  )\b""")

# said "bar" but is not one
CLUB_NO = re.compile(r"""(?ix) \b(
    barber|barbecue|bbq|salad|juice|smoothie|snack|sushi|oyster|coffee|tea|
    tapas|restaurant|diner|grill|pizzeria|bakery|creamery|ice\ cream|
    airport|nail|hair|beauty|spa|tanning|sports\ club|country\ club|golf|
    health|fitness|gym|yacht|book|publisher|notary|school|clinic|plaza|
    fountain|transit|relations|library|chamber
  )\b""")

# where a rejected place belongs instead
ELSEWHERE = [
    (re.compile(r"(?i)\b(restaurant|diner|grill|barbecue|bbq|tapas|salad|juice|smoothie|"
                r"snack|sushi|oyster|coffee|tea|pizzeria|bakery|creamery|ice cream)\b"), "food"),
    (re.compile(r"(?i)\b(barber|nail|hair|beauty|book|shop|store|market)\b"), "shop"),
    (re.compile(r"(?i)\b(spa|gym|fitness|tanning|library|museum|clinic|health|school|"
                r"publisher|notary|relations|chamber|office)\b"), "indoor"),
    (re.compile(r"(?i)\b(plaza|fountain|park|golf|yacht|country club|sports club)\b"), "todo"),
]


def destination(kind):
    for rx, cat in ELSEWHERE:
        if rx.search(kind or ""):
            return cat
    return "indoor"          # a service, not somewhere you go on a trip


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    rows = con.execute("SELECT id, kind, name FROM place WHERE category='club'").fetchall()
    moves, keeps = [], 0
    by_kind = {}
    for pid, kind, name in rows:
        k = kind or ""
        if CLUB_YES.search(k) and not CLUB_NO.search(k):
            keeps += 1
            continue
        cat = destination(k)
        moves.append((cat, pid))
        by_kind.setdefault((k or "(none)", cat), 0)
        by_kind[(k, cat)] = by_kind.get((k, cat), 0) + 1

    print("%s places are in the bar category" % format(len(rows), ","))
    print("%s are really bars or nightclubs, %s are not"
          % (format(keeps, ","), format(len(moves), ",")))
    print("\nthe biggest things moving out:")
    for (k, cat), n in sorted(by_kind.items(), key=lambda kv: -kv[1])[:18]:
        print("   %-36s %6s  -> %s" % (k[:36], format(n, ","), cat))

    if args.write:
        con.executemany("UPDATE place SET category=? WHERE id=?", moves)
        con.commit()
        print("\nmoved %s places out of the bar category" % format(len(moves), ","))
    else:
        print("\n(dry run — pass --write to apply)")


if __name__ == "__main__":
    main()
