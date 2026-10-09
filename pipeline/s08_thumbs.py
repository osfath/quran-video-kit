"""Step 08 — thumbnails from templates/thumbnails/*.html → output/thumbnails/

Approved designs: 1-blue (original), 2-ivory (mic fully visible), 3-green-cave
(reciter centred in the glowing cave). extra/ holds sura-specific variants that
are rendered only on request (--extra).

The verse on 3-green-cave is ALWAYS taken from the KFGQPC data, never typed:
  "thumb_verse": {"aya": 10, "words": [1, 5]}   (1-based, inclusive)
Default: the first words of ayah 1 up to the first waqf mark (max 6 words).
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # allow `python -I`
import argparse
import subprocess
from pathlib import Path

from common import (load_config, work, out, sura_info, TEMPLATES, reciter_name_block,
                    fill_template, link_assets, screenshot, find_ffmpeg)

ap = argparse.ArgumentParser()
ap.add_argument("config"); ap.add_argument("--extra", action="store_true")
a = ap.parse_args()
cfg = load_config(a.config)
W = work(cfg)
info = sura_info(int(cfg["sura"]), cfg["riwaya"])
link_assets(cfg)

WAQF = set("ۖۗۘۙۚۛۜ")
rows = {x["aya_no"]: x["aya_text"].rsplit("\xa0", 1)[0].replace("۞ ", "").split() for x in info["rows"]}
tv = cfg.get("thumb_verse")
if tv:
    words = rows[tv["aya"]][tv["words"][0] - 1: tv["words"][1]]
else:
    words = []
    for w in rows[1][:6]:
        words.append(w)
        if WAQF & set(w):
            break
verse = " ".join(words)
for ch in WAQF:                       # waqf marks look odd on a thumbnail
    verse = verse.replace(ch, "")

mapping = {"SURA_NAME": info["name_ar"], "TAGLINE": cfg["thumb_tagline"], "VERSE": verse,
           "RECITER_NAME": reciter_name_block(cfg)}
tpls = sorted((TEMPLATES / "thumbnails").glob("*.html"))
if a.extra:
    tpls += sorted((TEMPLATES / "thumbnails" / "extra").glob("*.html"))
dst = out(cfg, "thumbnails"); dst.mkdir(exist_ok=True)
for t in tpls:
    html = W / f"thumb_{t.stem}.html"
    fill_template(t, html, {k: v for k, v in mapping.items()})
    png = dst / f"{t.stem}.png"
    screenshot(html, png, cfg)
    subprocess.run([find_ffmpeg(), "-v", "error", "-y", "-i", str(png), "-vf", "scale=1280:720",
                    "-q:v", "2", str(dst / f"{t.stem}.jpg")], check=True)
    print("08 thumbs:", t.stem, "→ jpg 1280x720 + png 1920x1080")
