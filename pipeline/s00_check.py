"""Step 00 — environment + input check. Fails loudly with the exact fix."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # allow `python -I`
import argparse
import importlib
import shutil
import subprocess
import sys
from pathlib import Path

from common import load_config, find_browser, FONTS, VENDOR, sura_info

ap = argparse.ArgumentParser()
ap.add_argument("config")
a = ap.parse_args()
problems = []

def need(ok, msg):
    print(("  OK   " if ok else "  FAIL ") + msg)
    if not ok:
        problems.append(msg)

need(sys.version_info >= (3, 10), f"Python ≥ 3.10 (found {sys.version.split()[0]})")
for exe in ("ffmpeg", "ffprobe"):
    need(shutil.which(exe) is not None, f"{exe} on PATH")
if shutil.which("ffmpeg"):
    f = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    need(" ass " in f, "ffmpeg built with libass (filter 'ass')")
for mod in ("numpy", "PIL"):
    try:
        importlib.import_module(mod); need(True, f"python module {mod}")
    except ImportError:
        need(False, f"python module {mod}  →  pip install -r setup/requirements.txt")
try:
    need(bool(find_browser()), "Edge/Chrome for headless rendering")
except SystemExit as e:
    need(False, str(e))
need((VENDOR / "quran-data-kfgqpc" / "hafs" / "data").exists(), "vendor/quran-data-kfgqpc present")
need((FONTS / "hafs" / "hafs.18.ttf").exists(), "font assets/fonts/hafs/hafs.18.ttf")
for f in ("thmanyahsans12_medium.otf", "thmanyahsans12_bold.otf", "thmanyahsans12_black.otf"):
    ok = (FONTS / "thmanyah" / f).exists()
    need(ok, f"font assets/fonts/thmanyah/{f}" + ("" if ok else
         "  →  run setup.ps1, or download Thmanyah (free, not redistributable) — GUIDE.md §8"))

cfg = load_config(a.config)
info = sura_info(int(cfg["sura"]), cfg["riwaya"])
print(f"  INFO sura {cfg['sura']} = {info['name_ar']} ({info['ayat']} ayat)")
has_audio = cfg.get("audio") and Path(cfg["audio"]).exists()
need(has_audio or cfg.get("youtube_url"), "audio file exists, or youtube_url is set")
if cfg.get("youtube_url") or cfg["timing_source"] == "youtube":
    try:
        importlib.import_module("yt_dlp"); need(True, "python module yt_dlp")
    except ImportError:
        need(False, "python module yt_dlp  →  pip install yt-dlp")
if cfg["timing_source"] == "whisper" or not cfg.get("youtube_url"):
    try:
        importlib.import_module("faster_whisper"); need(True, "python module faster_whisper")
    except ImportError:
        need(False, "python module faster_whisper  →  pip install faster-whisper")
photo = cfg.get("reciter_photo")
need(bool(photo) and Path(photo).exists(), "reciter_photo (transparent PNG cut-out) exists")
if photo and Path(photo).exists():
    from PIL import Image
    im = Image.open(photo)
    need(im.mode in ("RGBA", "LA", "P"), f"reciter_photo has transparency (mode {im.mode})")
svg = cfg.get("reciter_name_svg")
if svg:
    need(Path(svg).exists(), f"reciter_name_svg exists ({svg})")
else:
    print("  INFO no reciter_name_svg → the name will be typed in Thmanyah Sans Black")

if problems:
    sys.exit(f"\n{len(problems)} problem(s). Fix them (GUIDE.md §1–§3) and run again.")
print("\nEnvironment OK.")
