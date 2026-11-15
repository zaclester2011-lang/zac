#!/usr/bin/env python3
"""Turn the index into hidden adventures: five kinds of adventure, nothing else.

Overture's own categories are no use here. Its "adventure" is mostly businesses
that sell adventure — 1,030 dive centres, 998 boat-tour operators — while the
actual adventures, the gorge and the cave and the waterfall, sat in "todo"
alongside 39,000 places of worship and 6,500 municipal parks. So the category is
rebuilt from what a place IS:

    beach   sand and sea
    water   waterfalls, lakes, lagoons, hot springs, cenotes, rivers
    rock    gorges, canyons, caves, cliffs, peaks, volcanoes
    trail   hiking, climbing, walking routes, viewpoints
    sea     diving, snorkelling, surfing, kayaking, sailing — getting into it

Everything else goes: restaurants, hotels, bars, churches, museums, castles,
town parks, tour agencies. A castle is not an adventure.

    python3 tools/adventure_cats.py            # show what each becomes
    python3 tools/adventure_cats.py --write
"""

import argparse, collections, os, re, sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "index.db")

# order matters: the first that matches wins
RULES = [
    ("beach", r"""\b(beach|strand|playa|praia|spiaggia|plage|cala|cove|sandbar|
                  shingle|seashore|lido|pantai)\b"""),
    ("sea",   r"""\b(scuba|diving|dive|snorkel|snorkelling|snorkeling|surf|surfing|
                  kitesurf|windsurf|kayak|canoe|paddle|raft|rafting|sail|sailing|
                  boat\ tour|boat\ rental|water\ sports|freediv|spearfish|
                  parasail|jet\ ski|coasteering)\b"""),
    ("water", r"""\b(waterfall|falls|cascade|cataract|lake|lagoon|lagoa|laguna|
                  cenote|spring|springs|geyser|river|stream|creek|rapids|pool|
                  billabong|oasis|fjord|loch|tarn|wetland|delta|estuary)\b"""),
    ("rock",  r"""\b(gorge|canyon|ravine|gully|cave|cavern|grotto|cliff|crag|
                  escarpment|volcano|crater|caldera|lava|glacier|icefield|
                  mountain|peak|summit|ridge|massif|butte|mesa|arch|sinkhole|
                  rock\ formation|boulder|dune|desert|badland)\b"""),
    ("trail", r"""\b(trail|trailhead|hiking|hike|trek|trekking|footpath|
                  via\ ferrata|climbing|bouldering|mountaineering|scramble|
                  viewpoint|lookout|overlook|scenic|panorama|pass|saddle|
                  national\ park|nature\ reserve|marine\ park|wildlife\ refuge|
                  wildlife\ sanctuary|conservation\ area|nature\ park|
                  biosphere|wilderness|canyoning|zip\ line|bungee|paraglid|
                  caving|horseback|horse\ riding|equestrian|cycling|mountain\ bike|
                  bicycle\ rental|atv|quad|safari|island|islet|archipelago|
                  reef|atoll|cape|peninsula|headland|bay|inlet|sound)\b"""),
]
RULES = [(c, re.compile(p, re.I | re.X)) for c, p in RULES]

# never an adventure, whatever else the words say
NOT_ADVENTURE = re.compile(r"""(?ix) \b(
    restaurant|cafe|coffee|bakery|bar|pub|brewery|nightclub|club\ house|
    hotel|hostel|motel|resort|lodging|apartment|villa|guest|campground|
    church|chapel|cathedral|mosque|temple|synagogue|shrine|monaster|worship|
    religious|museum|gallery|theatre|theater|cinema|library|casino|
    castle|fort|fortress|palace|ruin|archaeolog|historic|monument|memorial|
    cemetery|graveyard|zoo|aquarium|amusement|theme\ park|water\ park|
    playground|skate|golf|stadium|gym|fitness|spa|salon|barber|
    shop|store|market|mall|boutique|supermarket|pharmacy|bank|
    tour\ operator|tour\ agency|travel\ agency|travel\ service|
    parking|office|school|clinic|hospital|notary|publisher|
    winery|vineyard|distillery|farm|ranch\ house
  )\b""")


def classify(kind, name):
    hay = ((kind or "") + " " + (name or "")).replace("_", " ")
    k = (kind or "").replace("_", " ")
    # the kind decides whether it is excluded; the name must not override that
    if NOT_ADVENTURE.search(k):
        return None
    for cat, rx in RULES:
        if rx.search(k):
            return cat
    # no kind to go on, or a kind that says nothing: fall back to the name
    if not k.strip() or k.strip() in ("land feature", "natural feature", "attraction"):
        if NOT_ADVENTURE.search(hay):
            return None
        for cat, rx in RULES:
            if rx.search(hay):
                return cat
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    rows = con.execute("SELECT id, category, kind, name FROM place").fetchall()
    new, drop = [], []
    moved = collections.Counter()
    from_to = collections.Counter()
    for pid, cat, kind, name in rows:
        c = classify(kind, name)
        if c is None:
            drop.append((pid,))
        else:
            new.append((c, pid))
            moved[c] += 1
            from_to[(cat, c)] += 1

    print("%s places in the index" % format(len(rows), ","))
    print("%s are adventures, %s are not" % (format(len(new), ","), format(len(drop), ",")))
    for c, n in moved.most_common():
        print("   %-6s %s" % (c, format(n, ",")))
    print("\nwhere they came from:")
    for (a, b), n in from_to.most_common(10):
        print("   %-10s -> %-6s %s" % (a, b, format(n, ",")))

    if args.write:
        con.executemany("UPDATE place SET category=? WHERE id=?", new)
        con.executemany("DELETE FROM place WHERE id=?", drop)
        con.commit()
        left = con.execute("SELECT count(*) FROM place").fetchone()[0]
        print("\n%s adventures left" % format(left, ","))
    else:
        print("\nsample of each:")
        for c, _ in RULES:
            ex = [(n, k) for pid, cat, k, n in rows if classify(k, n) == c][:4]
            for n, k in ex:
                print("   %-6s %-38s %s" % (c, (n or "")[:38], (k or "")[:26]))
        print("\n(dry run — pass --write to apply)")


if __name__ == "__main__":
    main()
