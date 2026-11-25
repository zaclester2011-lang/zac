# CLAUDE.md

## Zac's scoring scale

Three columns, each out of 10, totalling 30. This is Zac's own scale. Do not
redefine it, rename the columns, or silently change what they measure.

### How to score a place — read this first

**Research it and judge it.** Look the place up against several independent
sources, check the date on every one of them, then set the three numbers against
the anchors below. That is how Crete, Zanzibar, Sardinia, Baja and Indonesia
were all scored, and it is what Zac means when he asks for a place to be scored.

The automated pipeline (`rate.py`, `score_la.py`, `score_place.py`) exists to
put a number on 20,332 places at once. **It is not the method for a single place
somebody asked about.** Running it instead of doing the research produces a worse
answer slowly: it saw nothing at Wayag because Overture maps nothing there and
Commons has its four geotagged photographs pinned 100 km away.

Use a measurement as evidence inside the judgement, never as a substitute for it,
and say so when the two disagree.

Two failure modes, both already paid for:

- **Inferring instead of checking.** Vundwe was given 27 because it is a Menai
  Bay island. Researched, it is 20 — coral rag and mangrove, no swimmable water.
- **Trusting an undated source.** Bawe sat at 27 on pages describing it as
  uninhabited. Those pages predate the 70-villa resort that opened there in 2024.
  It is 22.

### Discovery /10 — how likely you are to have it to yourself

Read off how much else is mapped around the place (Overture Maps feature counts
within 500 m and 2 km).

```
s = 10 − 1.0·log10(1 + n500) − 1.2·log10(1 + n2km)
    − 0.25 if the place has a website      (somebody is selling it)
    − 0.25 if the place has a phone number
clamped to 1–10, rounded to the nearest 0.5
```

`tools/rate.py:discovery()`. The 2 km count is deliberately weighted above the
500 m one.

It measures **remoteness, not crowds**. Balos has little built beside it but a
whole tour industry within 2 km, which is why it fits at 6 rather than 8.

Fitted against eight places measured standing in them (Balos 6, Katholiko 8.5,
Seitan 8, Kourtaliotiko 8, Aradena 8, Glyka Nera 7.5, Preveli 7, Elafonissi 6):
mean error 0.31, worst 0.5. Eight anchors and three coefficients is a thin fit —
treat it as a draft of a rating, not a measurement, until more places are walked.

### Colour /10 — what the water actually looks like

Measured off the place's photograph: median hue and saturation of the blue-green
pixels in the lower frame. Not an opinion.

```
s = 4.5 + 7.0·sat
    + 1.0  if 168 ≤ hue ≤ 195     (the turquoise band)
    + 0.3  if 195 < hue ≤ 205     (blue, not turquoise)
    − 0.5  if hue > 215           (flat navy)
clamped to 1–10, rounded to the nearest 0.5
None if water is under 18% of the frame
```

`tools/rate.py:colour()`. Anchored on Zac's own ratings of measured photographs
(Balos 9.5, Seitan 8.5, Preveli 8): mean error 0.50.

Left unrated rather than guessed when the frame cannot answer — a photograph of
a taverna cannot tell you what the sea looks like.

### Water /10 — is there enough of it to swim in

**10 if there is enough water to swim in. Nothing if there isn't.**

Sea and lake both count: a reservoir scores 10. This is not stored in the
database; it is applied at scoring time from an explicit list (`SWIMMABLE` in
`tools/score_la.py`).

### The bar is 25

All six places Zac rated by hand in Crete clear 25, which is where the bar comes
from. Because Water is 10 whenever it applies, the bar is in practice
**Discovery + Colour ≥ 15**.

### Weak-link rule

Anything scoring below 7 in a single column is cut, whatever its total. Used on
the Zanzibar itinerary: Mnemba Atoll totalled 24 and was cut on Discovery 4.

### The anchors — Crete, rated by hand

| Place | Disc | Colour | Water | /30 |
|---|---|---|---|---|
| Seitan Limania | 8 | 8.5 | 10 | 26.5 |
| Katholiko | 8.5 | 7.5 | 10 | 26 |
| Balos | 6 | 9.5 | 10 | 25.5 |
| Glyka Nera | 7.5 | 8 | 10 | 25.5 |
| Elafonissi | 6 | 9 | 10 | 25 |
| Preveli | 7 | 8 | 10 | 25 |

**Do not move these.** They live in `SCORED` in `site/app.js`. Changing the
shared scoring functions shifts them and breaks comparability with everything
measured since.

### Known holes — read before trusting a number

1. **Colour only works on water.** Of 20,332 indexed places only 884 have a
   measured colour, and every one is a beach, lake or reef. Gorges, caves and
   peaks get a Discovery number and nothing else. The scale cannot rank them.

2. **Foliage reads as turquoise.** The hue window in `measure_water.water_colour()`
   admits sunlit grass — Carpinteria once scored a perfect 10 off a hedge.
   Guarded in `tools/score_la.py` only (`is_foliage()`: hue < 178 and sat > 0.55,
   with `MIN_SHARE` raised to 0.33), **not fixed at source**, because changing the
   shared function would move the Crete anchors above.

3. **Discovery is a density measure**, so "crowded places score badly" is true by
   construction. Do not present it as a finding.

4. **A photograph is not proof of place.** Proximity never establishes identity
   and a name alone never establishes place. A picture is kept only if taken
   within the radius *and* its filename carries a distinctive word from the
   place's own name. Even so, misfires survive: a village office scored 18, a
   painted spiny lobster stood in for a Maldives beach.

## Where things are

| | |
|---|---|
| `data/index.db` | 20,332 adventures, 44 destinations, 43.3M geotagged Commons rows |
| `tools/rate.py` | `discovery()` and `colour()` — the scale itself |
| `tools/score_la.py` | Scores an arbitrary region; `--skip-overture` reuses stored density |
| `site/app.js` | `SCORED` holds the six hand-rated Crete anchors |
| `site/la_scores.json` | 36 places within 2.5 h of Los Angeles, 17 with a measured colour |
| `expeditions/` | Hand-built itineraries, scored on the same scale |

## Pictures

All photographs come from Wikimedia Commons and are freely licensed. Most are
CC BY-SA or CC BY and **require the photographer to be credited**; a small number
are CC0 or public domain and require nothing. Do not source copyrighted images
from elsewhere.
