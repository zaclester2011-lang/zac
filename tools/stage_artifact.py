#!/usr/bin/env python3
"""Stage the site for publishing as an Artifact.

Artifacts refuse images from other hosts, so every picture has to be published
alongside the page. They also take at most 255 files per publish, so the files
are listed here in batches and the caller publishes each batch to the same URL.

Pictures are copied to predictable names — pk/h<dest>.jpg for a destination's
lead photograph, pk/t<dest>_<n>.jpg for its ten best things — and a copy of
packs.json is rewritten to point at them.

    python3 tools/stage_artifact.py

Prints the batches to publish.
"""

import hashlib, json, os, shutil, sys

HI_HERO_W, HI_TOP_W = 1800, 900
TOP_W, TOP_H = 720, 540            # 4:3, the aspect the card draws at
TOP_COLS, TOP_ROWS = 2, 5          # ten best on one sheet

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
IMG = os.path.join(SITE, "img")
PK = os.path.join(SITE, "pk")
BATCH = 250                    # under the 255-file limit, leaving room for the page files
BATCH_BYTES = 58_000_000       # under the 64 MB a single publish accepts


def hi_path(title, width):
    """The big copy tools/hires.py fetched, if it got one.

    site/img holds 360-pixel thumbnails, downloaded to be measured rather than
    looked at. A pack hero is drawn 1,248 pixels wide, so those were being
    stretched almost three times, which is what made the page look blurry.
    """
    if not title:
        return None
    n = hashlib.sha1(("%s@%d" % (title, width)).encode("utf-8")).hexdigest()[:16] + ".jpg"
    p = os.path.join(SITE, "hi", n)
    return p if os.path.exists(p) else None


def main():
    # Clear only the pictures this script owns. The sprite sheets live here too
    # and are written by tools/sprites.py, which runs before this does.
    os.makedirs(PK, exist_ok=True)
    for f in os.listdir(PK):
        # h = destination hero, t = an older per-picture top ten, b = top-ten
        # sheet. The s* grid sheets belong to tools/sprites.py, which runs first.
        if f[0] in "htb" and f.endswith(".jpg"):
            os.remove(os.path.join(PK, f))
    packs = json.load(open(os.path.join(SITE, "packs.json")))
    # This rewrites packs.json to point at what it copies, so a second run would
    # look for "pk/h0.jpg" inside site/img and find nothing. Rebuild first.
    if any((p.get("hero") or "").startswith("pk/") for p in packs):
        sys.exit("packs.json is already staged — run build_packs.py and sprites.py first")

    from PIL import Image
    staged, missing, bigs = [], [], 0
    for p in packs:
        tops = []
        src = hi_path(p.get("hero_title"), HI_HERO_W)
        if src:
            bigs += 1
        else:
            src = os.path.join(IMG, p.get("hero") or "")
        if p.get("hero") and os.path.exists(src):
            name = "h%d.jpg" % p["id"]
            # Cropping a tall hero at its water was tried and reverted: on the
            # Tulum cenote the shallow rocky bottom beat the deep blue pool on
            # every measure I had, and the browser's own centre crop is better.
            shutil.copyfile(src, os.path.join(PK, name))
            p["hero"] = "pk/" + name
            staged.append("pk/" + name)
        else:
            missing.append("%s hero" % p["name"])
            p["hero"] = ""
        for i, t in enumerate(p.get("top", [])):
            s = hi_path(t.get("credit"), HI_TOP_W)
            if s:
                bigs += 1
            else:
                s = os.path.join(IMG, t.get("img") or "")
            if t.get("img") and os.path.exists(s):
                tops.append((i, s))
            else:
                missing.append("%s / %s" % (p["name"], t.get("n", "?")))
                t["img"] = ""
            # t["row"] stays: the page builds each paragraph from it

        # The ten best ride one sheet of big cells rather than ten files. Ten
        # files each for forty-four destinations is 440, and a version holds 511
        # in all, so individual files only fitted while there were twenty-four
        # destinations. The cells are 720x540: a card is drawn between 250 and
        # 400 CSS pixels wide at 4:3, so this is sharp even on a retina screen.
        if tops:
            sheet = Image.new("RGB", (TOP_COLS * TOP_W, TOP_ROWS * TOP_H), (238, 236, 231))
            for i, src in tops:
                try:
                    im = Image.open(src).convert("RGB")
                except Exception:
                    continue
                sw, sh = im.size
                scale = max(TOP_W / sw, TOP_H / sh)
                im = im.resize((max(1, int(sw * scale + 0.5)), max(1, int(sh * scale + 0.5))))
                left, top = (im.size[0] - TOP_W) // 2, (im.size[1] - TOP_H) // 2
                im = im.crop((left, top, left + TOP_W, top + TOP_H))
                sheet.paste(im, ((i % TOP_COLS) * TOP_W, (i // TOP_COLS) * TOP_H))
            name = "b%d.jpg" % p["id"]
            sheet.save(os.path.join(PK, name), "JPEG", quality=76, optimize=True)
            staged.append("pk/" + name)
            for i, src in tops:
                p["top"][i]["img"] = "pk/%s|%d|%d|%d" % (name, i, TOP_COLS, TOP_ROWS)

    out = os.path.join(SITE, "packs.json")
    json.dump(packs, open(out, "w"), ensure_ascii=False, separators=(",", ":"))

    total = sum(os.path.getsize(os.path.join(PK, f)) for f in os.listdir(PK))
    print("%d pictures staged into site/pk (%.1f MB), %d missing"
          % (len(staged), total / 1e6, len(missing)))
    print("%d of them are the big copies from site/hi" % bigs)
    if missing:
        print("   missing: " + ", ".join(missing[:8]) + (" …" if len(missing) > 8 else ""))

    page = ["index.html", "app.js", "style.css", "packs.json"]
    page += ["d/%s" % f for f in sorted(os.listdir(os.path.join(SITE, "d")))]
    sheets = sorted("pk/" + f for f in os.listdir(PK) if f.startswith("s") and f.endswith(".jpg"))
    files = page + staged + sheets
    sheet_mb = sum(os.path.getsize(os.path.join(SITE, f)) for f in sheets) / 1e6
    print("%d sprite sheets carrying the grid pictures (%.1f MB)" % (len(sheets), sheet_mb))
    # A publish takes at most 255 files AND at most 64 MB, so the sprite sheets
    # need the batches split by weight as well as by count.
    batches, cur, cur_bytes = [], [], 0
    for f in files:
        n = os.path.getsize(os.path.join(SITE, f))
        if cur and (len(cur) >= BATCH or cur_bytes + n > BATCH_BYTES):
            batches.append(cur); cur, cur_bytes = [], 0
        cur.append(f); cur_bytes += n
    if cur:
        batches.append(cur)

    print("\n%d files in all. Publish in %d batch(es) to the same url:"
          % (len(files), len(batches)))
    for i, chunk in enumerate(batches, 1):
        mb = sum(os.path.getsize(os.path.join(SITE, f)) for f in chunk) / 1e6
        print("   batch %d: %d files, %.1f MB (%s … %s)"
              % (i, len(chunk), mb, chunk[0], chunk[-1]))
        json.dump(chunk, open(os.path.join(SITE, "batch%d.json" % i), "w"), indent=0)
    for extra in range(len(batches) + 1, 12):      # clear stale lists from a bigger run
        old = os.path.join(SITE, "batch%d.json" % extra)
        if os.path.exists(old):
            os.remove(old)


if __name__ == "__main__":
    main()
