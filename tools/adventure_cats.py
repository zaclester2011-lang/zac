#!/usr/bin/env python3
"""Turn the index into hidden adventures: five kinds of adventure, nothing else.

Overture's own categories are no use here. Its "adventure" is mostly businesses
that sell adventure — 1,225 dive centres, 1,123 boat-tour operators — while the
actual adventures, the gorge and the cave and the waterfall, sat in "todo"
alongside 39,000 places of worship and 6,500 municipal parks.

    beach   sand and shingle
    water   waterfalls, lakes, hot springs, natural pools
    rock    peaks, gorges, caves, passes, desert
    trail   hiking routes, climbing spots, islands, parks, reserves, viewpoints
    sea     surf breaks, snorkelling, reefs

This used to guess from regular expressions over the kind, and guessing cost it
dearly: "scuba" matched both diving, which is an adventure, and "scuba diving
center", which is a shop, so 2,706 of the 3,019 places in the sea category were
operators rather than places. That is the real reason a dive resort was once
illustrated by a number plate — the resort should never have been in the index.

So the kind is now looked up, not matched. There are only 470 distinct kinds in
the whole index and they are listed here by hand, which is longer to read and
cannot be wrong about a word.

A kind alone is still not enough, because Overture files a business by where it
stands: an airport canteen, a fishing jetty and a municipal lido complex all
came through as kind "beach". So a name that announces a business is refused
even under a natural kind. "Marina" is deliberately not one of those words —
Marina Piccola and Marina Grande are two of the best beaches in Capri.

    python3 tools/adventure_cats.py            # show what each becomes
    python3 tools/adventure_cats.py --write
"""

import argparse, collections, os, re, sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "index.db")

KEEP = {
    # sand and shingle
    "beach": "beach", "white sand beach": "beach", "nude beach": "beach",
    "urban beach": "beach", "shingle beach": "beach", "sand beach": "beach",
    "black sand beach": "beach", "golden sand beach": "beach",

    # fresh water
    "lake": "water", "alpine lake": "water", "glacial lake": "water",
    "artificial lake": "water", "volcanic crater lake": "water",
    "group of lakes": "water", "waterfall": "water", "coastal waterfall": "water",
    "hot springs": "water", "hot spring": "water", "spring": "water",
    "natural pool": "water",

    # rock
    "mountain": "rock", "subpeak": "rock", "back of a mountain": "rock",
    "mountain range": "rock", "mountain ridge": "rock", "mountain pass": "rock",
    "mountain saddle": "rock", "mountain pasture": "rock", "mountain hut": "rock",
    "cave": "rock", "show cave": "rock", "sea cave": "rock",
    "canyon": "rock", "desert": "rock",

    # routes and wild places
    "hiking trail": "trail", "mountain bike trail": "trail",
    "mountain bike park": "trail", "rock climbing spot": "trail",
    "scenic viewpoint": "trail",
    "island": "trail", "island group": "trail", "tidal island": "trail",
    "artificial island": "trail", "former island": "trail",
    "section of an island": "trail",
    "national park": "trail", "national park of thailand": "trail",
    "national park of indonesia": "trail", "state park": "trail",
    "hawaii state park": "trail", "regional park": "trail", "county park": "trail",
    "rural park": "trail", "natural park": "trail", "nature park": "trail",
    "nature reserve": "trail", "regional nature reserve": "trail",
    "national nature reserve": "trail", "corsican nature reserve": "trail",
    "wildlife sanctuary": "trail", "forest": "trail",
    "geopark": "trail", "unesco global geopark": "trail",
    "natural landscape": "trail",

    # reefs. Overture's "surfing" and "snorkeling" are business categories, not
    # places: of the 352 they contributed, almost every one was a surf school or
    # a snorkelling trip — "iSurfBali", "hellosurf", "Школа серфинга", and
    # several whose name is a phone number. Only the reef is a feature.
    "reef": "sea", "coral reef": "sea", "reef island": "sea",
}

# Refused even under a natural kind, because the name says it is a business.
# Deliberately absent: marina, port, grande, piccola — all of them turn up in
# the real names of real beaches.
NOT_PLACE = re.compile(r"""(?ix) \b(
    hotels?|hostels?|motels?|resorts?|villas?|apartments?|apartamento|
    rooms?|suites?|studios?|guesthouses?|guest\ house|homestays?|bungalows?|
    lodges?|lodging|retreat|camping|campgrounds?|campsites?|caravan|
    # built heritage, which arrives filed as a park: "Russian Fort Elizabeth
    # State Historical Park" came through as kind "national park"
    fort|fortress|citadel|castle|historical|heritage\ site|
    # working water, which arrives filed as a beach: "Kukuiula Small Boat
    # Harbor" came through as kind "beach"
    harbour|harbor|boatyard|shipyard|slipway|
    restaurants?|restoran|ristorante|trattoria|pizzeria|taverna|warung|kantin|
    canteens?|cafes?|caffe|bistro|grill|bars?|pubs?|brewery|lounge|clubs?|disco|
    bagni|bagno|chiringuito|
    shops?|stores?|toko|markets?|supermarkets?|boutique|pharmacy|bank|atm|
    rentals?|rent|hire|charter|tours?|touring|excursions?|agency|
    agencia|travel|transfer|taxi|shuttle|
    offices?|kantor|bureau|company|ltd|llc|
    schools?|sekolah|academy|academia|college|university|kindergarten|
    society|association|federation|foundation|institute|committee|
    terminals?|bandara|airport|airstrip|heliport|dermaga|jetty|piers?|wharf|
    visitors?|information|reception|ticket|entrance|
    patung|statues?|monuments?|memorials?|museums?|gallery|
    churches?|church|chapels?|gereja|temples?|pura|masjid|mosques?|synagogue|
    shrine|monastery|
    parking|toilets?|restroom|clinic|hospital|police|
    spa|salon|barbers?|massage|gym|fitness|yoga|
    complexo|balnear|piscina|swimming\ pool|waterpark|water\ park|aquapark|
    factory|warehouse|workshop|garage|petrol|gas\ station|laundry
  )\b""")


# Word boundaries miss a business that runs its words together, which is how
# "Ripzsurfschool" survived a deny-list containing "school" — the same hole the
# barbershops used with handles like "mrdeebarber". So the activity and the
# trade word are allowed to touch.
TRADE_RUN = re.compile(r"""(?ix)
    (surf|dive|diving|scuba|snorkel|kite|wind|sup|kayak|canoe|raft|boat|quad|atv|
     jeep|horse|yoga|bike|cycle)
    \s*
    (school|schule|camp|centre|center|academy|academia|club|rental|rentals|
     hire|shop|tours?|trips?|lessons?|guide|guides|safari|experience)
  """)


def classify(kind, name):
    cat = KEEP.get((kind or "").replace("_", " ").strip().lower())
    if not cat:
        return None
    plain = (name or "").replace("_", " ")
    if NOT_PLACE.search(plain) or TRADE_RUN.search(plain):
        return None
    return cat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    rows = con.execute("SELECT id, category, kind, name FROM place").fetchall()
    new, drop = [], []
    moved = collections.Counter()
    why_kind, why_name = collections.Counter(), collections.Counter()
    for pid, cat, kind, name in rows:
        c = classify(kind, name)
        if c is None:
            drop.append((pid,))
            k = (kind or "").replace("_", " ").strip().lower()
            if k not in KEEP:
                why_kind[k or "(no kind)"] += 1
            else:
                why_name[k] += 1
        else:
            new.append((c, pid))
            moved[c] += 1

    print("%s places in the index" % format(len(rows), ","))
    print("%s are adventures, %s are not" % (format(len(new), ","), format(len(drop), ",")))
    for c, n in moved.most_common():
        print("   %-6s %s" % (c, format(n, ",")))
    print("\ndropped because the kind is not an adventure:")
    for k, n in why_kind.most_common(12):
        print("   %-30s %s" % (k[:30], format(n, ",")))
    print("\ndropped because the name says it is a business, under a natural kind:")
    for k, n in why_name.most_common(8):
        print("   %-30s %s" % (k[:30], format(n, ",")))

    if args.write:
        con.executemany("UPDATE place SET category=? WHERE id=?", new)
        con.executemany("DELETE FROM place WHERE id=?", drop)
        con.commit()
        left = con.execute("SELECT count(*) FROM place").fetchone()[0]
        print("\n%s adventures left" % format(left, ","))
    else:
        print("\nsample of each:")
        for c in ("beach", "water", "rock", "trail", "sea"):
            ex = [(n, k) for pid, cat, k, n in rows if classify(k, n) == c][:3]
            for n, k in ex:
                print("   %-6s %-40s %s" % (c, (n or "")[:40], (k or "")[:24]))
        print("\n(dry run — pass --write to apply)")


if __name__ == "__main__":
    main()
