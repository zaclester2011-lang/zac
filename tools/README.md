# tools

## `index_destination.py`

Indexes a destination: every place in it, categorised, auto-scored, photographed.
One command. No manual data work.

```bash
pip install duckdb

python3 tools/index_destination.py add "Cook Islands"
python3 tools/index_destination.py add "Bali" --include-shops
python3 tools/index_destination.py add "Crete" --bbox 34.78,23.40,35.75,26.40
python3 tools/index_destination.py list
python3 tools/index_destination.py remove "Bali"
```

### What one `add` does

1. **Finds the destination.** Looks the name up and takes its bounding box, or uses
   `--bbox` if you have one.
2. **Queries Overture Maps.** Every POI inside the box, read straight off the public
   parquet on S3. The newest release is detected automatically. Nothing is downloaded
   whole: the planet is 11.9 GB and the query reads only the rows it needs.
3. **Categorises.** Into beaches, adventures, restaurants, bars and clubs, things to do,
   hotels, indoor, guides, and optionally shops. Anything that is not travel-relevant —
   accountants, car repair, schools — is dropped and counted.
4. **Adds Wikidata landmarks and photographs.** Archaeological sites, monasteries,
   mountains, caves, plus freely licensed images.
5. **Scores every place.** Discovery is drafted from how crowded its surroundings are:
   neighbours within 500 m and 2 km, less a penalty for having a website and a phone.
   Calibrated against six measured Cretan beaches at **mean error 0.42**.
6. **Attaches photographs** — landmarks only, confident name matches only.
7. **Writes** `site/data.json` and `site/destinations.json`.

The website builds its destination list from `destinations.json`, so **a newly indexed
destination appears on the site with no code change**.

Re-running a destination replaces it rather than duplicating it.

### What it will not do

- **Invent a score.** Colour needs a photograph of the water; Water needs to know the
  place is swimmable. Both stay unmeasured until somebody goes.
- **Attach a loose photograph.** An early version put a photo of a village on every
  taverna standing in it. Matching is deliberately strict, which is why coverage is low.
- **Find hotel stars.** Overture carries no rating field anywhere.

### Known behaviour

- Wikidata rate-limits bursts from shared addresses. Failed tiles are skipped and the
  run continues; re-run later to pick up the rest.
- OpenStreetMap's own Overpass servers refuse datacentre addresses entirely. That is why
  this reads Overture's copy on S3 instead.
- Keep `site/data.json` under about 15 MB. Past that, drop `--include-shops` on large
  destinations or split the file per destination.
