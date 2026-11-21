# Hidden Water Index — website

A scored index of every place in a destination. Colour is measured from photographs;
Discovery is measured on the ground, or auto-drafted from place density where nobody
has been yet. Nothing is invented.

## Run it

It is a static site. It must be served over HTTP — opening `index.html` from the file
system will not load `data.json`.

```bash
cd site
python3 -m http.server 8000
# open http://localhost:8000
```

## Deploy it free

**GitHub Pages.** Repository → Settings → Pages → Source: *Deploy from a branch*,
branch `main`, folder `/site`. The site is then live at
`https://<user>.github.io/<repo>/`. No build step, no server, no cost.

## What is in here

| file | what it is |
|---|---|
| `index.html` | the page |
| `style.css` | tokens and layout, light and dark |
| `app.js` | rendering, filters, search, reviews |
| `data.json` | 81,537 places across Crete, Zanzibar and Sulawesi |

## The data

| | Crete | Zanzibar | Sulawesi |
|---|---|---|---|
| Restaurants | 6,083 | 277 | 22,035 |
| Things to do | 3,038 | 245 | 18,594 |
| Hotels | 6,542 | 922 | 7,181 |
| Shops & markets | 5,453 | 187 | — |
| Bars & clubs | 1,403 | 101 | 2,493 |
| Indoor | 636 | 63 | 1,807 |
| Guides & operators | 536 | 300 | 1,420 |
| Beaches | 815 | 69 | 961 |
| Adventures | 196 | 50 | 130 |

**81,537 places in total.** Sulawesi's shops are left out to keep the file servable;
its full result was 174,718 places from a single query.

Sources: **Overture Maps** (ODbL / CDLA) for places, **Wikidata** (CC0) for landmarks
and photographs. Both are open-licensed and free. Attribution is in the page footer and
must stay there.

### Adding a destination — how to find everywhere in the world

**The whole planet is 11.9 GB**, sixteen parquet files on a public S3 bucket, free and
unauthenticated. You never download it: you query it by bounding box and take only what
you want.

Sulawesi was added by changing four numbers. One query returned **174,718 places in
ninety seconds**. Any destination on earth is the same four numbers.

```python
import duckdb, os
for k in ("AWS_ACCESS_KEY_ID","AWS_SECRET_ACCESS_KEY"): os.environ.pop(k, None)
c = duckdb.connect(); c.execute("INSTALL httpfs; LOAD httpfs;")
# list release/<date>/theme=places/type=place/ on the public S3 bucket, then:
c.execute("""SELECT names.primary, taxonomy.primary, bbox.xmin, bbox.ymin, confidence,
                    websites, addresses, phones
             FROM read_parquet([...])
             WHERE bbox.xmin BETWEEN ? AND ? AND bbox.ymin BETWEEN ? AND ?""")
```

OpenStreetMap's own Overpass servers refuse requests from datacentre addresses, so use
the Overture copy on S3 rather than Overpass.

## Scoring

**Discovery + Colour + Water, each out of 10.** Sea is always Water 10. **Weak link:
below 7 in any category and the entry is cut**, whatever the total.

- **Verified** — somebody went and measured it. Ten places.
- **Auto** — Discovery drafted from how many other places sit within 500 m and 2 km,
  minus a penalty for having a phone number and a website. Calibrated against the six
  measured places: **mean error 0.42**.
- **Unmeasured** — Colour, everywhere except the ten. Colour needs a photograph of the
  water and most places have none.

The automatic score measures **remoteness, not crowding**. Balos reads 8.0 against a
measured 6, because density sees empty land and cannot see four hundred people off the
Kissamos boats. Closing that gap is what a review is for.

## Reviews

Each place carries its own review form: Discovery, Colour, Water and notes.

**There is no backend yet**, so reviews save to the visitor's own browser and nobody
else sees them. To make them real, set `REVIEW_ENDPOINT` at the top of `app.js` to a URL
that accepts `GET` (returns an array of reviews) and `POST` (accepts one). Any small
serverless function will do.

Before opening reviews publicly: moderation, and age checks if under-18s can post.

## Photographs

**104 places of 26,916 have one.** Wikidata holds images of landmarks only — there is no
free source for an ordinary restaurant or hotel, and the paid ones charge per request.

The answer is the same as it is for Discovery: **the people who go supply them.** Photo
upload belongs with the review form.

## Known gaps

- **No hotel star ratings.** Overture carries no rating field; stars come from booking
  platforms and are paid.
- **Zanzibar is thinner than Crete** — 2,214 places against 24,702 — because Overture's
  coverage is thinner there, not because the island is.
- **Colour is unmeasured almost everywhere.** 10 of 26,916.
