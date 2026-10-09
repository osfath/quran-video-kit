"""Step 07 — final render: bgloop (looped) + L_fg.png + full.ass + audio → output/*.mp4

  --preview N   render only the first N seconds (always do a 20 s preview first
                and show it to the user before the full render).
Memory: ~0.9 GB, speed ~1.9x real time on an 8-core CPU (25 min sura ≈ 13 min).
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # allow `python -I`
import argparse
from pathlib import Path

from common import load_config, work, out, sura_info, find_ffmpeg, run, audio_duration

ap = argparse.ArgumentParser()
ap.add_argument("config")
ap.add_argument("--preview", type=float, default=0)
a = ap.parse_args()
cfg = load_config(a.config)
W = work(cfg)
info = sura_info(int(cfg["sura"]), cfg["riwaya"])
audio = (W / "audio_path.txt").read_text(encoding="utf-8") if (W / "audio_path.txt").exists() else cfg["audio"]
dur = a.preview or audio_duration(audio)
base = f"{int(cfg['sura']):03d} {info['name_en']} - {cfg['reciter_name']}"
dst = out(cfg, f"{base} - preview {int(dur)}s.mp4" if a.preview else f"{base}.mp4")

run([find_ffmpeg(), "-v", "error", "-stats", "-y",
     "-stream_loop", "-1", "-i", "bgloop.mp4",
     "-loop", "1", "-framerate", str(cfg["fps"]), "-i", "L_fg.png",
     "-i", str(Path(audio).resolve()),
     "-filter_complex", "[0:v][1:v]overlay=0:0:shortest=0,ass=full.ass:fontsdir=fonts,format=yuv420p[v]",
     "-map", "[v]", "-map", "2:a", "-t", f"{dur:.3f}", "-r", str(cfg["fps"]),
     "-c:v", "libx264", "-preset", "medium", "-crf", str(cfg["crf"]),
     "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(dst)], cwd=W)
print("07 render: wrote", dst)
