# Jacob — bar mitzvah logo

The wordmark reads **JACOB**, with the **O** replaced by a mirrored disco ball and a
silver spotlight in each of the four corners, all four beams converging on the ball.

## Files

| File | Use |
| --- | --- |
| `jacob-bar-mitzvah-logo.svg` | Master artwork. Vector — scales to any size, best for print (invitations, signage, banners). |
| `jacob-bar-mitzvah-logo.png` | 1600 × 1000 — screens, social, email. |
| `jacob-bar-mitzvah-logo@3x.png` | 4800 × 3000 — large print / anything that needs real resolution. |
| `generate_logo.py` | Rebuilds the SVG. |
| `render.js` | Renders the SVG to PNG at a given scale. |

## Notes on the artwork

- The letters are drawn as vector paths, not set in a font, so the SVG looks identical
  everywhere and needs no font files installed.
- The disco ball is a real orthographic sphere: each mirror tile is projected from a
  lat/lon grid, back faces are culled, and every tile is shaded from a single key light
  in the upper left, with a cool rim light around the edge so the ball separates from
  the background.
- The spotlight beams are aimed at the ball, so if the ball moves the beams follow.

## Rebuilding

```bash
cd logo
python3 generate_logo.py
node render.js jacob-bar-mitzvah-logo.svg jacob-bar-mitzvah-logo.png 1
node render.js jacob-bar-mitzvah-logo.svg jacob-bar-mitzvah-logo@3x.png 3
```

`render.js` needs Playwright (`npm i playwright`). Easy things to change in
`generate_logo.py`: `LIGHT` (light direction), `LAMPS` (spotlight positions),
`BALL_R` (ball size), and the `bg` / `silver` gradients (background and metal colours).
