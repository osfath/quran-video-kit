"""Step 06 — bake the animated background into a seamless 24-second loop → work/bgloop.mp4

Why a baked loop: compositing 4 moving layers for a whole sura made ffmpeg grow
past 1.2 GB RAM and run at 0.6x. Baking once and looping runs at ~1.9x with <1 GB.
Every motion has a 24 s period so the loop has no visible seam:
  pattern drift 140px / 24s · rays sway 0.12*sin(2πt/24) · particles loop 24s.
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # allow `python -I`
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from common import load_config, work, step_done, find_ffmpeg, run

ap = argparse.ArgumentParser()
ap.add_argument("config"); ap.add_argument("--force", action="store_true")
a = ap.parse_args()
cfg = load_config(a.config)
W = work(cfg)
dst = W / "bgloop.mp4"
if step_done([dst], a.force):
    print("06 bgloop: cached"); raise SystemExit

frames = W / "pframes"
if a.force and frames.exists():
    shutil.rmtree(frames)
if not (frames / "p0599.png").exists():
    print("06 bgloop: drawing particles (600 frames)…")
    subprocess.run([sys.executable, str(Path(__file__).with_name("particles.py")), str(frames)], check=True)

ff = find_ffmpeg()
run([ff, "-v", "error", "-stats", "-y",
     "-loop", "1", "-framerate", "25", "-i", "L_bg.png",
     "-loop", "1", "-framerate", "25", "-i", "L_pat.png",
     "-loop", "1", "-framerate", "25", "-i", "L_rays.png",
     "-framerate", "25", "-i", "pframes/p%04d.png",
     "-filter_complex",
     "[1:v]format=rgba[pat];[0:v][pat]overlay=x='-mod(t*140/24,140)':y=0[b1];"
     "[2:v]format=rgba,rotate=a='0.12*sin(2*PI*t/24)':c=none:ow=1600:oh=1600[r];"
     "[b1][r]overlay=x=730:y=-420[b2];"
     "[3:v]scale=1920:1080,format=rgba[pt];[b2][pt]overlay=0:0,format=yuv420p[v]",
     "-map", "[v]", "-t", "24", "-r", "25", "-c:v", "libx264", "-preset", "slow", "-crf", "14",
     "bgloop.mp4"], cwd=W)
print("06 bgloop: wrote", dst.name)
