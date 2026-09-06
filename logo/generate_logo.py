#!/usr/bin/env python3
"""
Generates the "JACOB" bar mitzvah logo:
  - the O of JACOB is a mirrored disco ball
  - one massive spotlight beam washing over the whole logo, thrown from a source
    above and outside the frame (the light only, no fixture)

Letterforms are drawn as vector paths (no font dependency), so the SVG renders
identically everywhere. Run:  python3 generate_logo.py
"""
import math
import random

W, H = 1600, 1000

# --- wordmark metrics -------------------------------------------------------
TOP, BOT = 380.0, 640.0          # cap band
BALL_CX, BALL_CY, BALL_R = 1045.0, 504.0, 160.0

# --- the one spotlight ------------------------------------------------------
# The source sits above the top edge and out of frame; only its light is drawn.
LAMP_X, LAMP_Y = 800.0, -120.0
SPREAD = 47.0                    # half-angle, wide enough to swallow the logo

random.seed(11)


# --- helpers ----------------------------------------------------------------
def fmt(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def pts(seq):
    return " ".join(f"{fmt(x)},{fmt(y)}" for x, y in seq)


def norm(v):
    m = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / m for c in v)


def dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def rgb(r, g, b):
    return "#%02x%02x%02x" % (int(clamp(r, 0, 255)), int(clamp(g, 0, 255)), int(clamp(b, 0, 255)))


def cone(apex_y, spread, length, x=LAMP_X):
    """The spotlight cone as a polygon, from the lens down to `length`."""
    hw = length * math.tan(math.radians(spread))
    return [(x - 26, apex_y), (x + 26, apex_y),
            (x + hw, apex_y + length), (x - hw, apex_y + length)]


# --- letters ----------------------------------------------------------------
# Party lettering: fat rounded strokes, each glyph tilted and bounced off the
# baseline so the word dances. Every glyph is drawn as a skeleton stroked with
# round caps and joins, in a local box (0,0)-(w,260); the skeleton is inset by
# half the stroke weight so the caps land exactly on the cap band.
STROKE = 58.0

GLYPHS = [
    # J
    {"w": 150, "x": 145, "dy": 9, "rot": -6,
     "d": "M121,29 V150 C121,236 55,254 29,196"},
    # A
    {"w": 230, "x": 335, "dy": -11, "rot": 4,
     "d": "M29,231 L115,29 L201,231 M47,188 L183,188"},
    # C
    {"w": 240, "x": 605, "dy": 6, "rot": -3,
     "d": "M176,50.4 A91,101 0 1 0 176,209.6"},
    # B
    {"w": 210, "x": 1245, "dy": -13, "rot": 5,
     "d": "M29,29 V231 M29,29 H115.5 A50.5,50.5 0 0 1 115.5,130 H29 "
          "M29,130 H130.5 A50.5,50.5 0 0 1 130.5,231 H29"},
]


def letters_svg():
    out = []
    for g in GLYPHS:
        t = (f'translate({fmt(g["x"])},{fmt(TOP + g["dy"])}) '
             f'rotate({g["rot"]},{fmt(g["w"] / 2)},130)')
        common = 'fill="none" stroke-linecap="round" stroke-linejoin="round"'
        out.append(
            f'<g transform="{t}">'
            f'<path d="{g["d"]}" {common} stroke="#070b16" stroke-opacity="0.5" '
            f'stroke-width="{fmt(STROKE + 13)}"/>'
            f'<path d="{g["d"]}" {common} stroke="url(#silver)" stroke-width="{fmt(STROKE)}"/>'
            f'</g>'
        )
    return "".join(out)


# =============================================================================
# disco ball
#
# Mirror tiles are not diffuse: each one is a little flat mirror, so it is shaded
# by reflecting the camera ray off the facet and sampling what that reflected ray
# hits in the room. That is what gives a real mirror ball its scattered, high
# contrast sparkle instead of a smooth gradient.
# =============================================================================
KEY = norm((-0.40, -0.72, 0.57))     # the big spotlight, above and in front
FILL_L = norm((-0.92, -0.16, 0.36))  # cool bounce, stage left
FILL_R = norm((0.88, -0.10, 0.45))   # cool bounce, stage right

DARK = (58, 70, 96)                  # what a mirror sees away from the light
LIT = (255, 255, 255)


def environment(r):
    """Rough radiance seen along reflected ray r: dark room, bright key light."""
    up = max(0.0, -r[1])                                   # y is down on screen
    v = 0.17 + 0.30 * up ** 1.3                            # lit ceiling / haze
    v += 1.90 * max(0.0, dot(r, KEY)) ** 22                # the spotlight itself
    v += 0.52 * max(0.0, dot(r, KEY)) ** 3                 # its broad falloff
    v += 0.42 * max(0.0, dot(r, FILL_L)) ** 5
    v += 0.36 * max(0.0, dot(r, FILL_R)) ** 5
    return v


def sphere_point(lat, lon):
    """lat/lon in degrees -> (screen point, unit normal) for an orthographic sphere."""
    a, b = math.radians(lat), math.radians(lon)
    n = (math.cos(a) * math.sin(b), -math.sin(a), math.cos(a) * math.cos(b))
    return (BALL_CX + BALL_R * n[0], BALL_CY + BALL_R * n[1]), n


def facets():
    """Square-ish mirror tiles, back faces culled, each shaded as a mirror."""
    out = []
    bands = 17
    tile = math.pi * BALL_R / bands                 # keep tiles roughly square
    for i in range(bands):
        lat0 = -90.0 + 180.0 * i / bands
        lat1 = -90.0 + 180.0 * (i + 1) / bands
        latm = (lat0 + lat1) / 2.0
        count = max(4, int(round(2 * math.pi * BALL_R * math.cos(math.radians(latm)) / tile)))
        for j in range(count):
            lon0 = -180.0 + 360.0 * j / count
            lon1 = -180.0 + 360.0 * (j + 1) / count
            corners = [sphere_point(lat0, lon0), sphere_point(lat0, lon1),
                       sphere_point(lat1, lon1), sphere_point(lat1, lon0)]
            if min(c[1][2] for c in corners) <= 0.04:       # facing away
                continue

            screen = [c[0] for c in corners]
            cx = sum(p[0] for p in screen) / 4.0
            cy = sum(p[1] for p in screen) / 4.0
            quad = [(cx + (p[0] - cx) * 0.90, cy + (p[1] - cy) * 0.90) for p in screen]

            # facet normal, jittered: real mirror balls are glued on by hand and
            # no two tiles sit at quite the same angle
            n = norm(tuple(sum(c[1][k] for c in corners) / 4.0 + random.uniform(-0.075, 0.075)
                           for k in range(3)))
            # reflect the camera ray (0,0,-1) about the facet
            r = norm((2 * n[2] * n[0], 2 * n[2] * n[1], 2 * n[2] * n[2] - 1))

            v = environment(r)
            v *= 0.62 + 0.38 * n[2] ** 0.45          # grazing tiles see the dark room
            v *= random.uniform(0.74, 1.26)          # tile-to-tile variation
            if random.random() < 0.07:               # the odd tile catching a light
                v += random.uniform(0.35, 0.95)

            t = clamp(v)
            col = tuple(DARK[k] + (LIT[k] - DARK[k]) * t for k in range(3))
            if v > 1.0:                              # blown-out highlight
                col = tuple(min(255, c + (v - 1.0) * 90) for c in col)
            out.append((quad, rgb(col[0] * 0.99, col[1] * 1.0, col[2] * 1.03), v))
    return out


def sparkle(x, y, s, o):
    """Four-point glint."""
    d = s * 0.2
    return (
        f'<path d="M{fmt(x)},{fmt(y - s)} Q{fmt(x + d)},{fmt(y - d)} {fmt(x + s)},{fmt(y)} '
        f'Q{fmt(x + d)},{fmt(y + d)} {fmt(x)},{fmt(y + s)} Q{fmt(x - d)},{fmt(y + d)} '
        f'{fmt(x - s)},{fmt(y)} Q{fmt(x - d)},{fmt(y - d)} {fmt(x)},{fmt(y - s)} Z" '
        f'fill="url(#glint)" opacity="{o}"/>'
    )


# --- assemble ---------------------------------------------------------------
def build():
    tiles = facets()
    tile_svg = "".join(f'<polygon points="{pts(p)}" fill="{c}"/>' for p, c, _ in tiles)

    # star glints on the handful of tiles that blew out
    brightest = sorted(tiles, key=lambda t: -t[2])[:26]
    random.shuffle(brightest)
    glints = "".join(
        sparkle(sum(p[0] for p in q) / 4.0, sum(p[1] for p in q) / 4.0,
                random.uniform(18, 40), round(random.uniform(0.45, 0.95), 2))
        for q, _, _ in brightest[:7]
    )

    # haze inside the beam, and the specks the ball throws around the room
    haze = []
    for _ in range(150):
        y = random.uniform(0, H)
        hw = (y - LAMP_Y) * math.tan(math.radians(SPREAD)) * 0.97
        x = LAMP_X + random.uniform(-hw, hw)
        if not (6 < x < W - 6):
            continue
        s = random.uniform(1.4, 3.6)
        haze.append(f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="{fmt(s)}" fill="#eef4ff" '
                    f'opacity="{random.uniform(0.05, 0.22):.2f}"/>')

    specks = []
    for _ in range(150):
        a = random.uniform(0, math.tau)
        rad = random.uniform(BALL_R * 1.4, 940)
        x = BALL_CX + math.cos(a) * rad * random.uniform(0.55, 1.0)
        y = BALL_CY + math.sin(a) * rad * random.uniform(0.3, 0.72)
        if not (10 < x < W - 10 and 10 < y < H - 10):
            continue
        s = random.uniform(2.0, 7.0)
        specks.append(
            f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(s)}" height="{fmt(s)}" '
            f'transform="rotate({fmt(random.uniform(0, 90))} {fmt(x)} {fmt(y)})" '
            f'fill="#dce6ff" opacity="{random.uniform(0.10, 0.45):.2f}"/>'
        )

    letters = letters_svg()

    beam_outer = pts(cone(LAMP_Y, SPREAD, H - LAMP_Y))
    beam_mid = pts(cone(LAMP_Y, SPREAD * 0.66, H - LAMP_Y))
    beam_core = pts(cone(LAMP_Y, SPREAD * 0.3, H - LAMP_Y))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Jacob — bar mitzvah logo, the O is a disco ball under one large silver spotlight">
  <title>JACOB</title>
  <defs>
    <radialGradient id="bg" cx="0.5" cy="0.42" r="0.78">
      <stop offset="0" stop-color="#1d2748"/>
      <stop offset="0.55" stop-color="#0f1630"/>
      <stop offset="1" stop-color="#04060d"/>
    </radialGradient>
    <linearGradient id="silver" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffffff"/>
      <stop offset="0.16" stop-color="#e4ebf6"/>
      <stop offset="0.38" stop-color="#93a0b6"/>
      <stop offset="0.47" stop-color="#5f6b80"/>
      <stop offset="0.54" stop-color="#eef3fa"/>
      <stop offset="0.72" stop-color="#ffffff"/>
      <stop offset="0.88" stop-color="#aab5c8"/>
      <stop offset="1" stop-color="#7c8798"/>
    </linearGradient>
    <linearGradient id="beamGrad" gradientUnits="userSpaceOnUse" x1="0" y1="{LAMP_Y}" x2="0" y2="{H}">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.58"/>
      <stop offset="0.35" stop-color="#e6eeff" stop-opacity="0.28"/>
      <stop offset="0.75" stop-color="#cfdcff" stop-opacity="0.15"/>
      <stop offset="1" stop-color="#bccfff" stop-opacity="0.06"/>
    </linearGradient>
    <linearGradient id="beamCoreGrad" gradientUnits="userSpaceOnUse" x1="0" y1="{LAMP_Y}" x2="0" y2="{H}">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.6"/>
      <stop offset="0.5" stop-color="#f0f5ff" stop-opacity="0.2"/>
      <stop offset="1" stop-color="#dfe9ff" stop-opacity="0"/>
    </linearGradient>
    <radialGradient id="lens" cx="0.5" cy="0.42" r="0.6">
      <stop offset="0" stop-color="#ffffff"/>
      <stop offset="0.55" stop-color="#eef4ff"/>
      <stop offset="1" stop-color="#9db0d4"/>
    </radialGradient>
    <radialGradient id="flare" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.95"/>
      <stop offset="0.4" stop-color="#dfeaff" stop-opacity="0.35"/>
      <stop offset="1" stop-color="#b9cdff" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="pool" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#e9f1ff" stop-opacity="0.3"/>
      <stop offset="0.6" stop-color="#c3d4ff" stop-opacity="0.09"/>
      <stop offset="1" stop-color="#a8bdf5" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="halo" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#d5e4ff" stop-opacity="0.5"/>
      <stop offset="0.55" stop-color="#8fa8e0" stop-opacity="0.16"/>
      <stop offset="1" stop-color="#6a80c0" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glint" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#ffffff"/>
      <stop offset="0.45" stop-color="#eaf1ff" stop-opacity="0.7"/>
      <stop offset="1" stop-color="#c9d9ff" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="bloom" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.5"/>
      <stop offset="0.5" stop-color="#e8f0ff" stop-opacity="0.15"/>
      <stop offset="1" stop-color="#dce8ff" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="ballShade" cx="0.34" cy="0.28" r="0.82">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.16"/>
      <stop offset="0.5" stop-color="#ffffff" stop-opacity="0"/>
      <stop offset="0.84" stop-color="#050914" stop-opacity="0.28"/>
      <stop offset="1" stop-color="#03060e" stop-opacity="0.62"/>
    </radialGradient>
    <filter id="softBeam" x="-25%" y="-15%" width="150%" height="140%">
      <feGaussianBlur stdDeviation="18"/>
    </filter>
    <filter id="wideBeam" x="-25%" y="-15%" width="150%" height="140%">
      <feGaussianBlur stdDeviation="34"/>
    </filter>
    <filter id="coreBeam" x="-25%" y="-15%" width="150%" height="140%">
      <feGaussianBlur stdDeviation="7"/>
    </filter>
    <filter id="textGlow" x="-25%" y="-40%" width="150%" height="180%">
      <feDropShadow dx="0" dy="0" stdDeviation="16" flood-color="#9fc0ff" flood-opacity="0.4"/>
      <feDropShadow dx="0" dy="10" stdDeviation="16" flood-color="#000000" flood-opacity="0.6"/>
    </filter>
    <clipPath id="ballClip">
      <circle cx="{fmt(BALL_CX)}" cy="{fmt(BALL_CY)}" r="{fmt(BALL_R)}"/>
    </clipPath>
  </defs>

  <rect width="{W}" height="{H}" fill="url(#bg)"/>
  <g>{"".join(specks)}</g>

  <!-- the one big spotlight beam -->
  <g>
    <polygon points="{beam_outer}" fill="url(#beamGrad)" filter="url(#softBeam)"/>
    <polygon points="{beam_mid}" fill="url(#beamGrad)" filter="url(#wideBeam)"/>
    <polygon points="{beam_core}" fill="url(#beamCoreGrad)" filter="url(#coreBeam)"/>
    <ellipse cx="{fmt(LAMP_X)}" cy="{H - 40}" rx="880" ry="170" fill="url(#pool)"/>
    <g>{"".join(haze)}</g>
  </g>

  <ellipse cx="{fmt(BALL_CX)}" cy="{fmt(BALL_CY)}" rx="{fmt(BALL_R * 2.1)}" ry="{fmt(BALL_R * 2.1)}" fill="url(#halo)"/>

  <g filter="url(#textGlow)">{letters}</g>

  <!-- mirror ball -->
  <g clip-path="url(#ballClip)">
    <circle cx="{fmt(BALL_CX)}" cy="{fmt(BALL_CY)}" r="{fmt(BALL_R)}" fill="#05070f"/>
    {tile_svg}
    <ellipse cx="{fmt(BALL_CX - BALL_R * 0.34)}" cy="{fmt(BALL_CY - BALL_R * 0.44)}" rx="{fmt(BALL_R * 0.6)}" ry="{fmt(BALL_R * 0.5)}" fill="url(#bloom)" filter="url(#coreBeam)"/>
    <circle cx="{fmt(BALL_CX)}" cy="{fmt(BALL_CY)}" r="{fmt(BALL_R)}" fill="url(#ballShade)"/>
  </g>
  <circle cx="{fmt(BALL_CX)}" cy="{fmt(BALL_CY)}" r="{fmt(BALL_R)}" fill="none" stroke="#ffffff" stroke-opacity="0.28" stroke-width="2.5"/>
  <g>{glints}</g>

  <!-- where the beam enters the frame -->
  <ellipse cx="{fmt(LAMP_X)}" cy="0" rx="330" ry="140" fill="url(#flare)"/>

</svg>
'''


if __name__ == "__main__":
    open("jacob-bar-mitzvah-logo.svg", "w").write(build())
    print("wrote jacob-bar-mitzvah-logo.svg")
