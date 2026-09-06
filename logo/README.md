# Jacob — bar mitzvah logo

The wordmark reads **JACOB**, with the **O** replaced by a mirrored disco ball, under one
massive spotlight beam that washes over the whole logo. The light is thrown from a source
above and outside the frame — the beam is drawn, the fixture is not.

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
- The disco ball is a real orthographic sphere. Tiles are laid out in rows whose count
  follows the circumference at that latitude, so every mirror comes out roughly square
  the way a real ball is built, and back faces are culled.
- Tiles are shaded as mirrors, not as matte surfaces: the camera ray is reflected off
  each facet and that reflected ray samples the room (dark surroundings, a lit ceiling,
  two cool bounce lights, and the spotlight itself). Each facet's normal is jittered
  slightly, because no hand-glued mirror ball has perfectly aligned tiles. That is what
  produces the scattered high-contrast sparkle instead of a smooth gradient.
- The beam is drawn as three nested cones of decreasing spread plus airborne haze, so it
  has a hot core and soft edges. Its apex sits above the top of the frame, so the light
  enters the picture already spread and no lamp is visible.

## Rebuilding

```bash
cd logo
python3 generate_logo.py
node render.js jacob-bar-mitzvah-logo.svg jacob-bar-mitzvah-logo.png 1
node render.js jacob-bar-mitzvah-logo.svg jacob-bar-mitzvah-logo@3x.png 3
```

`render.js` needs Playwright (`npm i playwright`). Easy things to change in
`generate_logo.py`: `LAMP_X` / `LAMP_Y` (where the off-frame source sits), `SPREAD` (how
wide the beam opens), `KEY` (light direction on the ball), `BALL_R` (ball size), and the `bg` /
`silver` gradients (background and metal colours).
