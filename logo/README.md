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

- The lettering is a geometric display face with disco manners: the word leans on a nine
  degree italic pivoted at the baseline, the waists sit high (a small upper bowl on the B,
  a raised crossbar on the A), and a pair of hairline grooves is cut across the letters
  the way seventies wordmarks inline their strokes. Each groove is a dark cut with a lit
  lower lip, clipped to the letters, so it reads as milled into the metal rather than
  painted on. The glyphs are filled vector paths rather than type set in a font, so the
  SVG looks identical everywhere and needs no font files installed.
- The chrome gradient runs across the cap band in page coordinates, so the highlight and
  shadow bands line up across all four letters.
- The disco ball is a real orthographic sphere. Tiles are laid out in rows whose count
  follows the circumference at that latitude, so every mirror comes out roughly square
  the way a real ball is built, and back faces are culled.
- Tiles are shaded as mirrors, not as matte surfaces: the camera ray is reflected off
  each facet and that reflected ray samples the room (dark surroundings, a lit ceiling,
  two cool bounce lights, and the spotlight itself). Each facet's normal is jittered
  slightly, because no hand-glued mirror ball has perfectly aligned tiles. That is what
  produces the scattered high-contrast shine instead of a smooth gradient — the ball has
  no drawn-on star glints, every highlight on it is a mirror doing its job.
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
`silver` gradients (background and metal colours). The letterforms are the `LETTER_*` path
constants, the lean is `SLANT`, and the inline detail is the `GROOVES` list — each entry a
groove's top edge and thickness.
