#!/usr/bin/env python3
"""Drop places nobody travels for.

A barbershop is not a destination. They were in the index at all because the
bar category was matched by substring, so "barber" read as "bar"; moving them
to shops only moved the problem, and they started turning up in Santorini's
ten best things. Zac's instruction was no barbershops anywhere, so they go.

The same substring match dragged in a tail of offices — publishers, notaries
public, public relations firms, public schools, health clinics — which are no
more a thing to do on a trip than a barber is. They go with it.

    python3 tools/cull.py             # show what would go
    python3 tools/cull.py --write     # delete it
"""

import argparse, os, re, sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "index.db")

# Barbers and the hair trade, matched on what a place IS, not what it is called:
# matching the name deleted a pub, two cafes and a dozen coffee shops that merely
# had "Barber" in their name, and swept up day spas along with them.
BARBER = re.compile(r"""(?ix) \b(
    barber|barbershop|barbers|barbearia|barberia|barbiere|
    hairdresser|hairdressing|hair\ salon|hair\ studio|hair\ stylist
  )\b""")

# kinds loose enough that the name is the better evidence
SALONISH = re.compile(r"(?ix) \b(spa|salon|beauty|grooming|barber|stylist|tools)\b")
BARBER_LOOSE = re.compile(r"(?i)barber|hairdress|haircut|hairstyl")

# Not one of the categories the index offers. A car park is not a thing to do,
# a coworking desk is not somewhere to go indoors, and a cabinet sales service
# is not a hotel — they were only ever in the index because the source data
# maps everything.
NONPLACE = re.compile(r"""(?ix) \b(
    parking|parking\ garage|parking\ lot|car\ park|motorcycle\ parking|bike\ parking|
    playground|dog\ park|coworking|shared\ office|bartender|bartending\ school|
    public\ restroom|restroom|toilet|newspaper|home\ theater\ systems|
    cabinet\ sales|supply\ service|apartment\ agent|immigration|naturalization|
    school|academy|university|college|kindergarten|preschool|b2b
  )\b""")

# offices and services, not places to go
OFFICE = re.compile(r"""(?ix) \b(
    publisher|publishing|notary|notaries|public\ relations|advertising\ agency|
    public\ school|public\ health|health\ clinic|medical\ clinic|dental|
    public\ utility|public\ transit|insurance|accountant|law\ firm|
    recruiter|staffing|call\ centre|call\ center|warehouse|wholesaler
  )\b""")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    rows = con.execute("SELECT id, kind, name, category FROM place").fetchall()
    doomed, why = [], {}
    for pid, kind, name, cat in rows:
        k = kind or ""
        # A barbershop the source filed under "spa" is still a barbershop. The
        # name decides where the kind is a salon kind or missing; everywhere else
        # the kind decides, so a pub called The Barber survives.
        # Inside a salon kind the match is loose, because these are social-media
        # handles: "mrdeebarber" and "twinsz_barbershop" have no word boundary
        # in front of barber for the strict pattern to catch.
        nm = name or ""
        named = (SALONISH.search(k) and BARBER_LOOSE.search(nm)) \
            or (not k.strip() and BARBER.search(nm))
        if BARBER.search(k) or named:
            tag = "barber"
        elif OFFICE.search(k):
            tag = "office"
        elif cat != "guide" and NONPLACE.search(k):
            tag = "not a category"
        else:
            continue
        doomed.append((pid,))
        key = (tag, (kind or "(none)"))
        why[key] = why.get(key, 0) + 1

    total = len(rows)
    print("%s places in the index" % format(total, ","))
    print("%s to remove (%s barbers and the hair trade, %s offices)"
          % (format(len(doomed), ","),
             format(sum(n for (t, _), n in why.items() if t == "barber"), ","),
             format(sum(n for (t, _), n in why.items() if t != "barber"), ",")))
    for (tag, kind), n in sorted(why.items(), key=lambda kv: -kv[1])[:16]:
        print("   %-8s %-36s %s" % (tag, kind[:36], format(n, ",")))

    if args.write:
        con.executemany("DELETE FROM place WHERE id=?", doomed)
        con.commit()
        left = con.execute("SELECT count(*) FROM place").fetchone()[0]
        print("\nremoved %s; %s places left" % (format(len(doomed), ","), format(left, ",")))
    else:
        print("\n(dry run — pass --write to apply)")


if __name__ == "__main__":
    main()
