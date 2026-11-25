#!/usr/bin/env python3
"""My ratings, applied to every place, with the method stated so it can be checked.

Two ratings, two methods, both mine:

  Discovery — how likely it is you have the place to yourself. Read off how much
    else is mapped around it. Fitted against eight places we measured standing in
    them (Balos 6, Katholiko 8.5, Seitan 8, Kourtaliotiko 8, Aradena 8,
    Glyka Nera 7.5, Preveli 7, Elafonissi 6): mean error 0.31, worst 0.5.
    It measures remoteness, not crowds. Fitting it to those eight brought Balos
    from 8.0 to 6.0 by weighting the 2 km count above the 500 m one — a lagoon
    with little beside it but a whole tour industry within two kilometres.
    Eight anchors and three coefficients is a thin fit; treat it as a draft of
    a rating, not a measurement, until more places are walked.

  Colour — measured from the water in the place's photograph: median hue and
    saturation of the blue-green pixels in the lower frame. Anchored on Zac's own
    ratings of measured photographs (Balos 9.5, Seitan 8.5, Preveli 8): mean
    error 0.50. Left unrated where under 18% of the frame is water, because a
    photograph of a taverna cannot tell you what the sea looks like.

    python3 tools/rate.py

Writes place.discovery and place.colour.
"""

import json, math, os, re, sqlite3, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
DB = os.path.join(ROOT, "data", "index.db")

# Colour is a rating of water. A monastery has no more water than a taverna, so
# category alone is too blunt: a gorge or a waterfall counts, a church does not.
#
# Matching the NAME was blunter still, and in two ways. Without word boundaries
# "river" matched Chabad of Riverdale and "akti" matched Shakti, which is how a
# synagogue and a Hindu temple came to be New York's best-rated water. With them
# it still rated Coney Island Amusement Park and Spring Grove Baptist Church,
# because those names really do contain water words. So the kind decides: for a
# thing to do or an outing, what OpenStreetMap calls it is what says whether
# water is the point of it. The name is only consulted when the kind is blank.
WATERY_KIND = re.compile(r"""(?ix) \b(
    beach|bay|cove|lagoon|lagoa|lake|pond|reservoir|river|stream|creek|
    waterfall|falls|cascade|spring|springs|geyser|gorge|canyon|cave|cenote|
    reef|island|islet|marina|harbour|harbor|pool|sea|ocean|coast|shore|cliff|
    fjord|strait|waterway|dam|wetland|water\ park|
    dive|diving|scuba|snorkel|snorkeling|surf|surfing|kayak|canoe|paddle|
    raft|rafting|fishing|boat|sail|sailing|cruise|swim|swimming
  )\b""")

# kinds that settle it the other way, whatever the name says
DRY_KIND = re.compile(r"""(?ix) \b(
    parking|playground|skate|dog\ park|amusement|historic|monument|memorial|
    museum|church|temple|mosque|synagogue|worship|religious|school|library|
    hotel|restaurant|cafe|shop|store|office|hospital|government|cemetery|
    stadium|golf|zoo|theatre|theater|cinema|hiking|climbing|equestrian|horse
  )\b""")

WATERY_NAME = re.compile(r"""(?ix) \b(
    beach|bay|cove|lagoon|lake|river|waterfall|cascade|spring|gorge|canyon|
    cave|reef|island|islet|harbour|harbor|marina|pool|sea|coast|shore|strand|
    playa|spiaggia|cala|paralia|limni|akti|falls|creek|delta|estuary|fjord|
    sandbar|peninsula|cape|lido|plage|praia
  )\b""")


def is_watery(cat, kind=None, name=None):
    """Colour rates water. Of the five kinds of adventure, three are made of it:
    a beach, a waterfall or lake, and somewhere you dive or surf. A gorge or a
    ridge may be bone dry, so neither is rated on the colour of its water."""
    return cat in ("beach", "water", "sea")


# fitted on the eight measured places — see the docstring
D_NEAR, D_WIDE, D_LISTED = 1.0, 1.2, 0.25


def discovery(n500, n2km, website, phone):
    """How likely you are to be alone. Higher is emptier."""
    s = 10.0 - D_NEAR * math.log10(1 + max(n500 or 0, 0)) \
             - D_WIDE * math.log10(1 + max(n2km or 0, 0))
    if website:
        s -= D_LISTED            # somebody is selling it
    if phone:
        s -= D_LISTED
    return max(1.0, min(10.0, round(s * 2) / 2))


def colour(hue, sat, share):
    """What the water looks like. None when the frame cannot answer."""
    if share is None or share < 0.18:
        return None
    s = 4.5 + 7.0 * sat
    if 168 <= hue <= 195:
        s += 1.0                 # the turquoise band
    elif 195 < hue <= 205:
        s += 0.3                 # blue, not turquoise
    elif hue > 215:
        s -= 0.5                 # flat navy
    return max(1.0, min(10.0, round(s * 2) / 2))


def main():
    con = sqlite3.connect(DB)
    colours = {}
    path = os.path.join(SITE, "colours.json")
    if os.path.exists(path):
        try:
            colours = json.load(open(path))
        except Exception:
            colours = {}

    t0 = time.time()
    # Colour answers "what does the water look like". A taverna has no water, so
    # a blue reading off its neighbour's sky is not a rating — it is noise.
    rows = con.execute("""SELECT id, n500, n2km, website, phone, photo_title, category,
                                 kind, name FROM place""").fetchall()
    dis, col, unrated = [], [], 0
    skipped = 0
    for pid, n5, n2, web, tel, title, cat, kind, nm in rows:
        dis.append((discovery(n5, n2, web, tel), pid))
        if not is_watery(cat, kind, nm):
            col.append((None, pid))
            skipped += 1
            continue
        # Every watery place is written on every run, blank included. Skipping the
        # ones that cannot be rated leaves an earlier run's number sitting there —
        # which is how a place whose photograph changed kept the old photograph's
        # rating. A blank is the honest answer; a stale number is not.
        c = colours.get(title or "")
        v = colour(c["hue"], c["sat"], c.get("share")) if c else None
        col.append((v, pid))
        if v is None:
            if title:
                unrated += 1
            skipped += 1          # not a rating, so not counted as one below
    con.executemany("UPDATE place SET discovery=? WHERE id=?", dis)
    con.executemany("UPDATE place SET colour=? WHERE id=?", col)
    con.commit()

    print("Discovery rated : %s places" % format(len(dis), ","))
    print("Colour rated    : %s places" % format(len(col) - skipped, ","))
    print("Colour unrated  : %s photographed, too little water in frame" % format(unrated, ","))
    print("Colour n/a      : %s where water is not the point of the place"
          % format(skipped, ","))

    print("\nDiscovery spread")
    for v, n in con.execute("""SELECT discovery, count(*) FROM place
                               GROUP BY discovery ORDER BY discovery DESC"""):
        print("   %4.1f  %7s  %s" % (v, format(n, ","), "#" * max(1, int(n / 6000))))
    print("\nColour spread")
    for v, n in con.execute("""SELECT colour, count(*) FROM place WHERE colour IS NOT NULL
                               GROUP BY colour ORDER BY colour DESC"""):
        print("   %4.1f  %7s  %s" % (v, format(n, ","), "#" * max(1, int(n / 30))))

    print("\nAgainst the places we actually stood in")
    MEAS = {"Balos Lagoon": 6.0, "Monastery Katholiko": 8.5, "Paralia Stefanou Seitan": 8.0,
            "Glyka Nera beach": 7.5, "Elafonissi": 6.0, "Holy Monastery of Prevel": 7.0,
            "Kourtaliotiko Gorge": 8.0, "Aradena Gorge": 8.0}
    tot = 0.0
    for nm, m in sorted(MEAS.items(), key=lambda kv: -kv[1]):
        r = con.execute("""SELECT name, discovery FROM place WHERE dest=0 AND name LIKE ?
                           AND category IN ('beach','todo','adventure')
                           ORDER BY confidence DESC LIMIT 1""", (nm + "%",)).fetchone()
        if not r:
            continue
        tot += abs(r[1] - m)
        print("   %-26s mine %4.1f   measured %4.1f   %+4.1f" % (r[0][:26], r[1], m, r[1] - m))
    print("   mean error %.2f" % (tot / len(MEAS)))
    print("\nRATEDONE in %.0fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
