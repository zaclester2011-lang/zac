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

import json, os, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
IMG = os.path.join(SITE, "img")
PK = os.path.join(SITE, "pk")
BATCH = 250                    # under the 255-file limit, leaving room for the page files


def main():
    if os.path.isdir(PK):
        shutil.rmtree(PK)
    os.makedirs(PK)
    packs = json.load(open(os.path.join(SITE, "packs.json")))

    staged, missing = [], []
    for p in packs:
        src = os.path.join(IMG, p.get("hero") or "")
        if p.get("hero") and os.path.exists(src):
            name = "h%d.jpg" % p["id"]
            shutil.copyfile(src, os.path.join(PK, name))
            p["hero"] = "pk/" + name
            staged.append("pk/" + name)
        else:
            missing.append("%s hero" % p["name"])
            p["hero"] = ""
        for i, t in enumerate(p.get("top", [])):
            s = os.path.join(IMG, t.get("img") or "")
            if t.get("img") and os.path.exists(s):
                name = "t%d_%d.jpg" % (p["id"], i)
                shutil.copyfile(s, os.path.join(PK, name))
                t["img"] = "pk/" + name
                staged.append("pk/" + name)
            else:
                missing.append("%s / %s" % (p["name"], t.get("n", "?")))
                t["img"] = ""
            # t["row"] stays: the page builds each paragraph from it

    out = os.path.join(SITE, "packs.json")
    json.dump(packs, open(out, "w"), ensure_ascii=False, separators=(",", ":"))

    total = sum(os.path.getsize(os.path.join(PK, f)) for f in os.listdir(PK))
    print("%d pictures staged into site/pk (%.1f MB), %d missing"
          % (len(staged), total / 1e6, len(missing)))
    if missing:
        print("   missing: " + ", ".join(missing[:8]) + (" …" if len(missing) > 8 else ""))

    page = ["index.html", "app.js", "style.css", "packs.json"]
    page += ["d/%s" % f for f in sorted(os.listdir(os.path.join(SITE, "d")))]
    files = page + staged
    print("\n%d files in all. Publish in %d batch(es) to the same url:"
          % (len(files), (len(files) + BATCH - 1) // BATCH))
    for i in range(0, len(files), BATCH):
        chunk = files[i:i + BATCH]
        print("   batch %d: %d files (%s … %s)"
              % (i // BATCH + 1, len(chunk), chunk[0], chunk[-1]))
        json.dump(chunk, open(os.path.join(SITE, "batch%d.json" % (i // BATCH + 1)), "w"), indent=0)


if __name__ == "__main__":
    main()
