#!/usr/bin/env python3
"""Keep a photograph only where it is a photograph OF the place, and only once.

The photographs were attached by finding the nearest geotagged picture on
Commons. On a Cretan headland the nearest picture is the beach. In a town it is
a number plate, a police station or a shopping mall — which is how a dive resort
came to be illustrated by a car. 189,862 places were sharing 58,888 pictures,
one corrupt title was on 187 of them, and a photograph of Phuket Municipality
Police Station stood in for 97 places.

So proximity is thrown away and the name has to carry it: a picture is kept only
when its filename names the place. Three kinds of word do not count as naming it:

  generic trade words   hotel, restaurant, bar, beach, villa, rooms …
  the destination       Tulum, Zakynthos, Phuket …
  any local place name  found in the data rather than listed: a word carried by
                        more than three different places in the same destination
                        is a neighbourhood, not an identity. That is what ruled
                        out Patong, Ubud, Rawai and Chalong, each of which was
                        matching dozens of unrelated hotels.

Then every picture is used once. Where several places claim the same file it
goes to the one whose name matches it best.

    python3 tools/photo_check.py            # show what would go
    python3 tools/photo_check.py --write    # clear the rest
"""

import argparse, collections, os, re, sqlite3, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "index.db")

KEEP_CATS = ("beach", "food", "club", "hotel")
LOCAL_NAME_AT = 3          # a word on more than this many places here is a place name

GENERIC = set("""
hotel hotels motel restaurant restaurante ristorante restaurant bar bars cafe caffe kafeneio
club pub tavern beach beaches playa praia spiaggia paralia plage strand coast shore
the and of de la le el los las il lo du des von der det een
resort villa villas apartment apartments rooms room suite suites studio studios guest house
inn lodge lodging hostel camping taverna pizzeria grill bistro lounge brasserie
view sea seaside beachfront waterfront panorama panoramio unsplash flickr wiki file image photo
jpg jpeg png com www net org http https
""".split())


# A filename can name the place and still not be a picture of it. The Hotel
# Martinique matched an architectural floor plan of itself.
JUNK = re.compile(r"""(?ix) \b(
    plan|plans|floorplan|blueprint|elevation|section|map|diagram|chart|schematic|
    logo|crest|coat.of.arms|flag|seal|stamp|coin|banknote|ticket|receipt|invoice|
    menu|poster|billboard|advert|advertisement|leaflet|brochure|
    sign|signpost|signage|plaque|notice|nameplate|number.plate|licence|license|
    portrait|selfie|mugshot|headshot|grave|tomb|tombstone|cemetery|memorial|
    screenshot|scan|document|letter|manuscript|drawing|sketch|engraving|
    postcard|newspaper|clipping|certificate|patent|
    train|railway|locomotive|tram|bus|coach|lorry|truck|aircraft|airplane|
    helicopter|ferry|boat|ship|yacht|car|cars|bicycle|motorcycle|scooter
  )\b""")


def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def words(s):
    return [t for t in re.findall(r"[a-z0-9]+", norm(s)) if len(t) >= 4 and t not in GENERIC]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    dest_words = {}
    for did, name in con.execute("SELECT id, name FROM destination"):
        dest_words[did] = set(re.findall(r"[a-z0-9]+", norm(name)))

    rows = con.execute("""SELECT id, dest, name, category, locality, photo_title, confidence
                          FROM place WHERE category IN (%s)"""
                       % ",".join("?" * len(KEEP_CATS)), KEEP_CATS).fetchall()

    # how many different places in each destination carry each word
    df = collections.defaultdict(collections.Counter)
    for pid, d, name, cat, loc, title, conf in rows:
        for w in set(words(name)):
            df[d][w] += 1

    claims = collections.defaultdict(list)     # title -> [(score, pid, name)]
    had = 0
    for pid, d, name, cat, loc, title, conf in rows:
        if not title:
            continue
        had += 1
        if not title.lower().endswith((".jpg", ".jpeg", ".png")):
            continue                            # truncated or corrupt, e.g. "Port_d"
        if JUNK.search(title.replace("_", " ")):
            continue                            # names the place, is not a picture of it
        skip = dest_words[d] | set(re.findall(r"[a-z0-9]+", norm(loc)))
        ident = {w for w in set(words(name)) if df[d][w] <= LOCAL_NAME_AT and w not in skip}
        shared = ident & set(words(title))
        if not shared:
            continue
        # the longest shared word is the strongest evidence; confidence breaks ties
        score = (len(shared), max(len(w) for w in shared), conf or 0)
        claims[title].append((score, pid, name))

    keep = {}
    for title, cs in claims.items():
        cs.sort(reverse=True)
        keep[cs[0][1]] = title                  # one place per picture, best match wins

    clear = [(pid,) for pid, d, n, c, l, t, cf in rows if t and pid not in keep]
    print("places in the five categories : %s" % format(len(rows), ","))
    print("had a photograph attached     : %s" % format(had, ","))
    print("photograph actually names it  : %s" % format(sum(len(v) for v in claims.values()), ","))
    print("kept after one-picture-one-place: %s" % format(len(keep), ","))
    print("cleared                       : %s" % format(len(clear), ","))

    by = collections.Counter()
    for pid, d, n, c, l, t, cf in rows:
        if pid in keep:
            by[c] += 1
    print("  kept by category: " + "  ".join("%s %s" % (k, format(v, ",")) for k, v in by.most_common()))

    if args.write:
        con.executemany("UPDATE place SET photo_title=NULL, photo=NULL WHERE id=?", clear)
        con.commit()
        left = con.execute("SELECT count(*) FROM place WHERE photo_title IS NOT NULL").fetchone()[0]
        dist = con.execute("SELECT count(DISTINCT photo_title) FROM place "
                           "WHERE photo_title IS NOT NULL").fetchone()[0]
        print("\n%s places keep a photograph, %s distinct files" % (format(left, ","), format(dist, ",")))
    else:
        print("\n(dry run — pass --write to apply)")


if __name__ == "__main__":
    main()
