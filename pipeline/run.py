"""Run the whole pipeline (or a range of steps) for one config.

  python -I pipeline/run.py projects/kahf/config.json                 # steps 01-06 + 20 s preview + thumbnails
  python -I pipeline/run.py projects/kahf/config.json --full          # … + full render
  python -I pipeline/run.py projects/kahf/config.json --from 4 --force

Each step is cached: it skips itself when its outputs exist (use --force to redo
the steps you run). Steps: 0 check · 1 timing · 2 align · 3 tafsir · 4 layers ·
5 subs · 6 bgloop · 7 render · 8 thumbnails
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = {0: "s00_check.py", 1: "s01_timing.py", 2: "s02_align.py", 3: "s03_tafsir.py",
         4: "s04_layers.py", 5: "s05_subs.py", 6: "s06_bgloop.py", 7: "s07_render.py", 8: "s08_thumbs.py"}

ap = argparse.ArgumentParser()
ap.add_argument("config")
ap.add_argument("--from", dest="first", type=int, default=0)
ap.add_argument("--to", dest="last", type=int, default=8)
ap.add_argument("--force", action="store_true")
ap.add_argument("--full", action="store_true", help="full render instead of the 20 s preview")
ap.add_argument("--preview", type=float, default=20)
a = ap.parse_args()
a.config = str(Path(a.config).resolve())
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")

for n in range(a.first, a.last + 1):
    cmd = [sys.executable, "-I", str(HERE / STEPS[n]), a.config]
    if a.force and n not in (0, 7, 8):
        cmd.append("--force")
    if n == 7 and not a.full:
        cmd += ["--preview", str(a.preview)]
    print(f"\n=== step {n:02d}: {STEPS[n]} ===", flush=True)
    r = subprocess.run(cmd, cwd=HERE)
    if r.returncode != 0:
        sys.exit(f"step {n} failed — fix the message above, then rerun with --from {n}")
print("\nDONE. Outputs are in the config's out_dir.")
