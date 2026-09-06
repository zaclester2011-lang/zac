#!/usr/bin/env python3
"""
Generates the "JACOB" bar mitzvah logo:
  - the O of JACOB is a mirrored disco ball (faceted, shaded from a single light)
  - four silver spotlights, one in each corner, beaming in on the ball

Letterforms are drawn as vector paths (no font dependency), so the SVG renders
identically everywhere. Run:  python3 generate_logo.py
"""
import math
import random

W, H = 1600, 1000

# --- wordmark metrics -------------------------------------------------------
TOP, BOT = 380.0, 640.0          # cap band
BALL_CX, BALL_CY, BALL_R = 1049.0, 510.0, 160.0

random.seed(7)


# --- helpers ----------------------------------------------------------------
def fmt(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def pts(seq):
    return " ".join(f"{fmt(x)},{fmt(y)}" for x, y in seq)


def norm(v):
    m = math.sqrt(sum(c * c for c in v))
    return tuple(c / m for c in v)


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def rgb(r, g, b):
    return "#%02x%02x%02x" % (int(clamp(r, 0, 255)), int(clamp(g, 0, 255)), int(clamp(b, 0, 255)))


# --- letters ----------------------------------------------------------------
# J : stem + hook.  x 137..317
LETTER_J = "M257,380 H317 V550 A90,90 0 0 1 137,550 H197 A30,30 0 0 0 257,550 Z"

# A : two legs, crossbar, triangular counter.  x 351..581
LETTER_A = (
    "M351,640 L436,380 L496,380 L581,640 L521,640 L508,600 L424,600 L411,640 Z "
    "M442,545 L490,545 L466,472 Z"
)

# C : open ring with angled terminals.  x 615..855
LETTER_C = (
    "M826.9,426.4 A120,130 0 1 0 826.9,593.6 L781,555 A60,70 0 1 1 781,465 Z"
)

# B : stem + two bowls.  x 1243..1463
LETTER_B = (
    "M1243,380 H1373 A62,65 0 0 1 1373,510 H1398 A65,65 0 0 1 1398,640 H1243 Z "
    "M1305,425 H1357.5 A32.5,32.5 0 0 1 1357.5,490 H1305 Z "
    "M1305,530 H1385.5 A32.5,32.5 0 0 1 1385.5,595 H1305 Z"
)

LETTERS = [LETTER_J, LETTER_A, LETTER_C, LETTER_B]


# --- disco ball -------------------------------------------------------------
LIGHT = norm((-0.46, -0.66, 0.60))       # key light: upper-left, slightly front
TINT = (226, 234, 249)                    # cool silver


def sphere_point(lat, lon):
    """lat/lon in degrees -> (screen_x, screen_y, z) for an orthographic sphere."""
    a, b = math.radians(lat), math.radians(lon)
    x = math.cos(a) * math.sin(b)
    y = -math.sin(a)
    z = math.cos(a) * math.cos(b)
    return (BALL_CX + BALL_R * x, BALL_CY + BALL_R * y, z), (x, y, z)


def facets():
    """Facet tiles of the mirror ball, back faces culled, each shaded."""
    out = []
    d_lat, d_lon = 15, 15
    lat = -90
    while lat < 90:
        lon = -180
        while lon < 180:
            corners = [
                sphere_point(lat, lon),
                sphere_point(lat, lon + d_lon),
                sphere_point(lat + d_lat, lon + d_lon),
                sphere_point(lat + d_lat, lon),
            ]
            if min(c[1][2] for c in corners) <= 0.06:
                lon += d_lon
                continue
            screen = [c[0][:2] for c in corners]
            cx = sum(p[0] for p in screen) / 4.0
            cy = sum(p[1] for p in screen) / 4.0
            inset = [(cx + (p[0] - cx) * 0.86, cy + (p[1] - cy) * 0.88) for p in screen]

            n = norm(tuple(sum(c[1][i] for c in corners) / 4.0 for i in range(3)))
            diff = max(0.0, sum(n[i] * LIGHT[i] for i in range(3)))
            rim = (1.0 - n[2]) ** 2.2                   # cool bounce around the limb
            v = 0.34 + 0.66 * (diff ** 1.05) + 0.16 * rim
            v *= random.uniform(0.80, 1.18)             # mirror tiles never match
            spec = diff ** 12
            r = TINT[0] * v + 255 * spec * 1.0
            g = TINT[1] * v + 255 * spec * 1.0
            b = TINT[2] * v + 255 * spec * 1.0
            if random.random() < 0.12:                  # tiles catching the room lights
                r, g, b = r * 1.16, g * 1.16, b * 1.20
            out.append((inset, rgb(r, g, b)))
            lon += d_lon
        lat += d_lat
    return out


def sparkle(x, y, s, o):
    """Four-point glint."""
    d = s * 0.22
    return (
        f'<path d="M{fmt(x)},{fmt(y - s)} Q{fmt(x + d)},{fmt(y - d)} {fmt(x + s)},{fmt(y)} '
        f'Q{fmt(x + d)},{fmt(y + d)} {fmt(x)},{fmt(y + s)} Q{fmt(x - d)},{fmt(y + d)} '
        f'{fmt(x - s)},{fmt(y)} Q{fmt(x - d)},{fmt(y - d)} {fmt(x)},{fmt(y - s)} Z" '
        f'fill="url(#glint)" opacity="{o}"/>'
    )


# --- spotlights -------------------------------------------------------------
LAMPS = [(96, 92), (1504, 92), (96, 908), (1504, 908)]


def spotlight(i, lx, ly):
    """A silver can light in the corner plus the beam it throws at the ball."""
    dx, dy = BALL_CX - lx, BALL_CY - ly
    ang = math.degrees(math.atan2(dy, dx))
    dist = math.hypot(dx, dy) + 120
    ux, uy = dx / math.hypot(dx, dy), dy / math.hypot(dx, dy)
    px, py = -uy, ux                                   # perpendicular

    def beam(spread, length, grad, blur):
        ex, ey = lx + ux * length, ly + uy * length
        hw = length * math.tan(math.radians(spread))
        poly = [(lx + px * 16, ly + py * 16),
                (ex + px * hw, ey + py * hw),
                (ex - px * hw, ey - py * hw),
                (lx - px * 16, ly - py * 16)]
        return (f'<polygon points="{pts(poly)}" fill="url(#{grad}{i})" '
                f'filter="url(#{blur})"/>')

    beams = beam(7.5, dist, "beam", "softBeam") + beam(2.6, dist * 0.92, "beamCore", "coreBeam")

    body = (
        f'<g transform="translate({fmt(lx)},{fmt(ly)}) rotate({fmt(ang)})">'
        f'<rect x="-64" y="-16" width="34" height="32" rx="7" fill="url(#steel)"/>'
        f'<path d="M-34,-30 L6,-40 L6,40 L-34,30 Z" fill="url(#steel)" stroke="#e9eef7" '
        f'stroke-opacity="0.45" stroke-width="2"/>'
        f'<path d="M-34,-30 L6,-40 L6,-22 L-34,-16 Z" fill="#ffffff" opacity="0.30"/>'
        f'<ellipse cx="6" cy="0" rx="9" ry="40" fill="url(#lens)"/>'
        f'<ellipse cx="6" cy="0" rx="5" ry="30" fill="#ffffff" opacity="0.85"/>'
        f'<rect x="-78" y="-7" width="20" height="14" rx="5" fill="url(#steel)"/>'
        f'</g>'
    )
    return beams, body


# --- assemble ---------------------------------------------------------------
def build():
    beams, bodies = [], []
    for i, (lx, ly) in enumerate(LAMPS):
        b, f = spotlight(i, lx, ly)
        beams.append(b)
        bodies.append(f)

    beam_grads = []
    for i, (lx, ly) in enumerate(LAMPS):
        dx, dy = BALL_CX - lx, BALL_CY - ly
        m = math.hypot(dx, dy)
        ex, ey = lx + dx / m * (m + 120), ly + dy / m * (m + 120)
        for name, a0, a1 in (("beam", 0.46, 0.0), ("beamCore", 0.62, 0.0)):
            beam_grads.append(
                f'<linearGradient id="{name}{i}" gradientUnits="userSpaceOnUse" '
                f'x1="{fmt(lx)}" y1="{fmt(ly)}" x2="{fmt(ex)}" y2="{fmt(ey)}">'
                f'<stop offset="0" stop-color="#ffffff" stop-opacity="{a0}"/>'
                f'<stop offset="0.6" stop-color="#dfe8ff" stop-opacity="{a0 * 0.42:.3f}"/>'
                f'<stop offset="1" stop-color="#c8d6ff" stop-opacity="{a1}"/>'
                f'</linearGradient>'
            )

    tiles = "".join(
        f'<polygon points="{pts(p)}" fill="{c}"/>' for p, c in facets()
    )

    # dance-floor specks thrown off the ball
    specks = []
    for _ in range(120):
        a = random.uniform(0, math.tau)
        rad = random.uniform(BALL_R * 1.35, 900)
        x = BALL_CX + math.cos(a) * rad * random.uniform(0.6, 1.0)
        y = BALL_CY + math.sin(a) * rad * random.uniform(0.35, 0.7)
        if not (10 < x < W - 10 and 10 < y < H - 10):
            continue
        s = random.uniform(2.0, 6.5)
        o = random.uniform(0.10, 0.42)
        specks.append(
            f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(s)}" height="{fmt(s)}" '
            f'transform="rotate({fmt(random.uniform(0, 90))} {fmt(x)} {fmt(y)})" '
            f'fill="#dce6ff" opacity="{o:.2f}"/>'
        )

    glints = "".join([
        sparkle(BALL_CX - 74, BALL_CY - 82, 46, 0.95),
        sparkle(BALL_CX + 96, BALL_CY + 58, 26, 0.55),
        sparkle(BALL_CX + 34, BALL_CY - 128, 22, 0.6),
        sparkle(316, 402, 20, 0.5),
        sparkle(1460, 616, 18, 0.45),
    ])

    letters = "".join(
        f'<path d="{d}" fill="url(#silver)" fill-rule="evenodd" stroke="url(#edge)" '
        f'stroke-width="2.5" stroke-linejoin="round"/>'
        for d in LETTERS
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Jacob — bar mitzvah logo, the O is a disco ball lit by four silver spotlights">
  <title>JACOB</title>
  <defs>
    <radialGradient id="bg" cx="0.5" cy="0.5" r="0.72">
      <stop offset="0" stop-color="#1d2748"/>
      <stop offset="0.55" stop-color="#101733"/>
      <stop offset="1" stop-color="#05070f"/>
    </radialGradient>
    <linearGradient id="silver" x1="0" y1="{TOP}" x2="0" y2="{BOT}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#ffffff"/>
      <stop offset="0.18" stop-color="#e8eef8"/>
      <stop offset="0.42" stop-color="#9aa5b8"/>
      <stop offset="0.5" stop-color="#727d92"/>
      <stop offset="0.58" stop-color="#f4f7fc"/>
      <stop offset="0.82" stop-color="#c3cddd"/>
      <stop offset="1" stop-color="#7a8598"/>
    </linearGradient>
    <linearGradient id="edge" x1="0" y1="{TOP}" x2="0" y2="{BOT}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.9"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0.25"/>
    </linearGradient>
    <linearGradient id="steel" x1="0" y1="-40" x2="0" y2="40" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#f6f9ff"/>
      <stop offset="0.35" stop-color="#c4cddd"/>
      <stop offset="0.6" stop-color="#6d7688"/>
      <stop offset="1" stop-color="#aab4c6"/>
    </linearGradient>
    <radialGradient id="lens" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#ffffff"/>
      <stop offset="0.6" stop-color="#e6eeff"/>
      <stop offset="1" stop-color="#9fb0d0"/>
    </radialGradient>
    <radialGradient id="halo" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#cfe0ff" stop-opacity="0.55"/>
      <stop offset="0.55" stop-color="#8fa8e0" stop-opacity="0.18"/>
      <stop offset="1" stop-color="#6a80c0" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glint" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#ffffff"/>
      <stop offset="0.45" stop-color="#eaf1ff" stop-opacity="0.75"/>
      <stop offset="1" stop-color="#c9d9ff" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="bloom" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.55"/>
      <stop offset="0.5" stop-color="#e8f0ff" stop-opacity="0.18"/>
      <stop offset="1" stop-color="#dce8ff" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="ballShade" cx="0.36" cy="0.32" r="0.78">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.30"/>
      <stop offset="0.45" stop-color="#ffffff" stop-opacity="0"/>
      <stop offset="0.86" stop-color="#050914" stop-opacity="0.22"/>
      <stop offset="1" stop-color="#03060e" stop-opacity="0.5"/>
    </radialGradient>
    {"".join(beam_grads)}
    <filter id="softBeam" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="14"/>
    </filter>
    <filter id="coreBeam" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="5"/>
    </filter>
    <filter id="textGlow" x="-25%" y="-40%" width="150%" height="180%">
      <feDropShadow dx="0" dy="0" stdDeviation="16" flood-color="#9fc0ff" flood-opacity="0.45"/>
      <feDropShadow dx="0" dy="8" stdDeviation="14" flood-color="#000000" flood-opacity="0.55"/>
    </filter>
    <clipPath id="ballClip">
      <circle cx="{fmt(BALL_CX)}" cy="{fmt(BALL_CY)}" r="{fmt(BALL_R)}"/>
    </clipPath>
  </defs>

  <rect width="{W}" height="{H}" fill="url(#bg)"/>
  <g>{"".join(specks)}</g>
  <g>{"".join(beams)}</g>

  <ellipse cx="{fmt(BALL_CX)}" cy="{fmt(BALL_CY)}" rx="{fmt(BALL_R * 2.1)}" ry="{fmt(BALL_R * 2.1)}" fill="url(#halo)"/>

  <g filter="url(#textGlow)">{letters}</g>

  <g clip-path="url(#ballClip)">
    <circle cx="{fmt(BALL_CX)}" cy="{fmt(BALL_CY)}" r="{fmt(BALL_R)}" fill="#0b1020"/>
    {tiles}
    <ellipse cx="{fmt(BALL_CX - BALL_R * 0.36)}" cy="{fmt(BALL_CY - BALL_R * 0.40)}" rx="{fmt(BALL_R * 0.62)}" ry="{fmt(BALL_R * 0.54)}" fill="url(#bloom)" filter="url(#coreBeam)"/>
    <circle cx="{fmt(BALL_CX)}" cy="{fmt(BALL_CY)}" r="{fmt(BALL_R)}" fill="url(#ballShade)"/>
  </g>
  <circle cx="{fmt(BALL_CX)}" cy="{fmt(BALL_CY)}" r="{fmt(BALL_R)}" fill="none" stroke="#ffffff" stroke-opacity="0.35" stroke-width="3"/>

  <g>{glints}</g>
  <g>{"".join(bodies)}</g>
</svg>
'''


if __name__ == "__main__":
    open("jacob-bar-mitzvah-logo.svg", "w").write(build())
    print("wrote jacob-bar-mitzvah-logo.svg")
