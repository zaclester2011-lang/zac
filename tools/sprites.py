#!/usr/bin/env python3
"""Pack the grid-card photographs into sprite sheets.

    Cards are drawn between 246 and 386 CSS pixels wide, so 192-pixel cells came
    out visibly soft. The cached sources are 360 pixels wide, which is the
    ceiling on real detail, so the cells are 352 and nothing is upscaled.

The index names 121,589 photographs, and 9,530 of them are actually cached on
disk. An artifact may publish at most 511 files in a version, so the pictures
can never go up one file per place: past the top ten every card fell back to a
grey "Photograph unavailable" panel.

A sheet of 256 thumbnails is one file. One or two sheets per destination covers
every cached photograph in that destination's grid, costs about a megabyte, and
only loads when that destination is opened.

    python3 tools/sprites.py

Rewrites site/d/<id>.json so each row points at its cell, and writes the sheets
to site/pk/. A row whose photograph was never downloaded is cleared, so the page
says so plainly instead of reaching for a file that is not there.
"""

import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
IMG = os.path.join(SITE, "img")
PK = os.path.join(SITE, "pk")

CELL_W, CELL_H = 352, 220          # 16:10, and as much detail as the 360px sources hold
COLS, ROWS = 12, 8                 # 96 a sheet: a 4224x1760 sheet decodes comfortably
PER_SHEET = COLS * ROWS
MAX_SHEETS = 8                     # a ceiling on weight: 768 pictures a destination
QUALITY = 62


def main():
    from PIL import Image
    os.makedirs(PK, exist_ok=True)
    have = set(os.listdir(IMG))

    total_cells = total_rows = cleared = 0
    sheets_written = []
    for did in range(24):
        path = os.path.join(SITE, "d", "%d.json" % did)
        if not os.path.exists(path):
            continue
        doc = json.load(open(path))
        rows = doc["r"]
        # Running twice would be destructive: the second pass would not find
        # "pk/s0_1.jpg|37" among the cached files and would clear every row.
        if any(len(r) > 9 and r[9] and "|" in r[9] for r in rows):
            print("   d/%-2d  already packed into sheets; rebuild packs first" % did)
            continue

        # one cell per distinct photograph, in the order the grid shows them
        cell_of, order = {}, []
        for r in rows:
            f = r[9] if len(r) > 9 else None
            if not f or f in cell_of or f not in have:
                continue
            if len(order) >= PER_SHEET * MAX_SHEETS:
                break
            cell_of[f] = len(order)
            order.append(f)

        # draw the sheets
        for s in range(0, len(order), PER_SHEET):
            chunk = order[s:s + PER_SHEET]
            sheet = Image.new("RGB", (COLS * CELL_W, ROWS * CELL_H), (238, 236, 231))
            for i, f in enumerate(chunk):
                try:
                    im = Image.open(os.path.join(IMG, f)).convert("RGB")
                except Exception:
                    continue
                # cover: fill the cell, crop the overflow, never squash the picture
                sw, sh = im.size
                scale = max(CELL_W / sw, CELL_H / sh)
                im = im.resize((max(1, int(sw * scale + 0.5)), max(1, int(sh * scale + 0.5))))
                left = (im.size[0] - CELL_W) // 2
                top = (im.size[1] - CELL_H) // 2
                im = im.crop((left, top, left + CELL_W, top + CELL_H))
                sheet.paste(im, ((i % COLS) * CELL_W, (i // COLS) * CELL_H))
            name = "s%d_%d.jpg" % (did, s // PER_SHEET)
            sheet.save(os.path.join(PK, name), "JPEG", quality=QUALITY, optimize=True)
            sheets_written.append("pk/" + name)

        # point each row at its cell, and clear the rows we hold no picture for
        for r in rows:
            if len(r) <= 9 or not r[9]:
                continue
            total_rows += 1
            c = cell_of.get(r[9])
            if c is None:
                r[9] = ""                      # named on Commons, not held here
                cleared += 1
            else:
                r[9] = "pk/s%d_%d.jpg|%d" % (did, c // PER_SHEET, c % PER_SHEET)
        total_cells += len(order)

        json.dump(doc, open(path, "w"), ensure_ascii=False, separators=(",", ":"))
        print("   d/%-2d  %5s rows  %4d pictures  %d sheet(s)"
              % (did, format(len(rows), ","), len(order),
                 (len(order) + PER_SHEET - 1) // PER_SHEET), flush=True)

    size = sum(os.path.getsize(os.path.join(SITE, f)) for f in sheets_written)
    print("\n%d sheets, %d pictures, %.1f MB in all (%.2f MB a destination)"
          % (len(sheets_written), total_cells, size / 1e6, size / 1e6 / 24))
    print("%s rows now show a picture, %s cleared because the file was never downloaded"
          % (format(total_rows - cleared, ","), format(cleared, ",")))
    json.dump(sheets_written, open(os.path.join(SITE, "sheets.json"), "w"), indent=0)


if __name__ == "__main__":
    main()
