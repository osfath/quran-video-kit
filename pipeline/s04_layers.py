"""Step 04 — render the design layers (PNG) and measure text → work/layout.json

Layers (rendered by headless Edge/Chrome from templates/video/design.html):
  L_bg.png   1920x1080 opaque  base gradient
  L_pat.png  2060x1080 RGBA    Islamic star pattern (drifts horizontally, period 140px)
  L_rays.png 1600x1600 RGBA    light rays behind the mihrab (sways)
  L_fg.png   1920x1080 RGBA    mihrab, reciter photo, verse band, tafsir panel, names

Measurement (same browser, same fonts):
  * tafsir lines wrapped at 860px with Thmanyah Sans Medium 38px
  * verse segment widths in KFGQPC Hafs 112px (to shrink over-long segments)
  * calibration probes so libass sizes match the browser exactly
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # allow `python -I`
import argparse
import html
import json
import subprocess

from common import (load_config, work, step_done, sura_info, ar_num, TEMPLATES, read_srt,
                    reciter_name_block, fill_template, link_assets, screenshot, dump_dom, find_ffmpeg)

ap = argparse.ArgumentParser()
ap.add_argument("config"); ap.add_argument("--force", action="store_true")
a = ap.parse_args()
cfg = load_config(a.config)
W = work(cfg)
outs = [W / "L_bg.png", W / "L_pat.png", W / "L_rays.png", W / "L_fg.png", W / "layout.json"]
if step_done(outs, a.force):
    print("04 layers: cached"); raise SystemExit

info = sura_info(int(cfg["sura"]), cfg["riwaya"])
link_assets(cfg)
if not (W / "reciter.png").exists():
    raise SystemExit("reciter_photo missing — a transparent PNG cut-out of the reciter is required (GUIDE.md §3)")

TAFSIR_TITLES = {"mukhtasar_ar": "المختصر في التفسير", "moyassar": "التفسير الميسر", "saadi": "تفسير السعدي"}
juz = ar_num(info["juz_first"]) if info["juz_first"] == info["juz_last"] else \
    f"{ar_num(info['juz_first'])} – {ar_num(info['juz_last'])}"
mapping = {
    "LAYOUT": "tafsir" if cfg["tafsir"] else "classic",
    "SURA_TITLE": f"سُورَةُ {info['name_ar']}",
    "META": f"آياتها {ar_num(info['ayat'])} · الجزء {juz}",
    "TAGLINE": cfg["thumb_tagline"],
    "TAFSIR_TITLE": TAFSIR_TITLES.get(cfg["tafsir_source"], cfg["tafsir_source"]),
    "RECITER_NAME": reciter_name_block(cfg),
}
design = W / "design.html"
fill_template(TEMPLATES / "video" / "design.html", design, mapping)

print("04 layers: rendering PNG layers…")
screenshot(design, W / "L_bg.png", cfg, hash_="bg")
screenshot(design, W / "L_pat.png", cfg, size=(2060, 1080), hash_="pat", transparent=True)
screenshot(design, W / "L_rays.png", cfg, size=(1600, 1600), hash_="rays", transparent=True)
screenshot(design, W / "L_fg.png", cfg, hash_="fg", transparent=True)

# ---------------- measurement in the browser
PROBE = "الحمد لله الذي أنزل على عبده الكتاب"
items = [{"id": "probe_taf", "text": PROBE, "font": "ThSans", "size": 38},
         {"id": "probe_hafs", "text": PROBE, "font": "Hafs", "size": 112}]
segs = read_srt(W / "segments.srt")
for n, (_, _, t) in enumerate(segs):
    items.append({"id": f"seg{n}", "text": t, "font": "Hafs", "size": 112})
taf = {}
if cfg["tafsir"]:
    taf = json.loads((W / "tafsir.json").read_text(encoding="utf-8"))["ayat"]
    for k, t in taf.items():
        items.append({"id": f"taf{k}", "text": t, "font": "ThSans", "size": 38, "width": 860})
(W / "items.js").write_text("const ITEMS=" + json.dumps(items, ensure_ascii=False) + ";", encoding="utf-8")
m_html = W / "measure.html"
m_html.write_text((TEMPLATES / "video" / "measure.html").read_text(encoding="utf-8"), encoding="utf-8")
dom = dump_dom(m_html, cfg)
if "JSONSTART" not in dom:
    raise SystemExit("measurement failed (browser returned no result) — rerun step 04 with --force")
meas = json.loads(html.unescape(dom.split("JSONSTART")[1].split("JSONEND")[0]))

# ---------------- libass calibration: ink width of the probe at ASS size 100
def libass_width(font, size=100):
    ass = W / "probe.ass"
    ass.write_text(f"""[Script Info]
ScriptType: v4.00+
PlayResX: 3840
PlayResY: 1080
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: P,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,178

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.00,P,,0,0,0,,{PROBE}
""", encoding="utf-8-sig")
    subprocess.run([find_ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=3840x1080:d=1",
                    "-vf", "ass=probe.ass:fontsdir=fonts", "-frames:v", "1", "probe.png"], cwd=W, check=True)
    from PIL import Image
    box = Image.open(W / "probe.png").convert("L").point(lambda v: 255 if v > 40 else 0).getbbox()
    if not box:
        raise SystemExit(f"libass could not render font '{font}' — check fonts in {W / 'fonts'}")
    return box[2] - box[0]

lw_taf = libass_width("Thmanyah sans 1.2 Med")
lw_hafs = libass_width("KFGQPC HAFS Uthmanic Script")
taf_ass_size = round(meas["probe_taf"] / (lw_taf / 100), 1)     # ASS size == 38 css px
hafs_ratio = (lw_hafs * 1.12) / meas["probe_hafs"]               # libass(112)/browser(112)
MAX_VERSE_W = 1540
verse_scale = []
for n in range(len(segs)):
    est = meas[f"seg{n}"] * hafs_ratio
    verse_scale.append(100 if est <= MAX_VERSE_W else int(100 * MAX_VERSE_W / est))
layout = {
    "taf_ass_size": taf_ass_size,
    "tafsir_lines": {k[3:]: v for k, v in meas.items() if k.startswith("taf")},
    "verse_scale": verse_scale,
}
(W / "layout.json").write_text(json.dumps(layout, ensure_ascii=False), encoding="utf-8")
shrunk = sum(1 for s in verse_scale if s < 100)
print(f"04 layers: tafsir ASS size {taf_ass_size}, verse segments shrunk to fit: {shrunk}")
