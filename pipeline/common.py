"""Shared helpers for the Quran recitation video pipeline.

Every step script imports this module. Nothing here talks to the network
except `mcp_call` (tafsir) and nothing here reads the user's browser profile:
the headless browser always runs with an isolated, throw-away profile.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

KIT = Path(__file__).resolve().parents[1]          # quran-video-kit/
FONTS = KIT / "assets" / "fonts"
TEMPLATES = KIT / "templates"
VENDOR = KIT / "vendor"
BS = chr(92)                                       # backslash, for ASS override tags

# ---------------------------------------------------------------- config
def load_config(path: str | os.PathLike) -> dict:
    cfg_path = Path(path).resolve()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    base = cfg_path.parent
    defaults = {
        "riwaya": "hafs",
        "timing_source": "auto",            # auto | youtube | whisper
        "youtube_url": None,
        "reciter_name_svg": None,
        "reciter_photo": None,
        "tafsir": True,
        "tafsir_source": "mukhtasar_ar",
        "segment_max_words": 9,
        "fps": 25,
        "crf": 19,
        "work_dir": "work",
        "out_dir": "output",
        "thumb_tagline": "تلاوة كاملة",
        "thumb_verse": None,
        "whisper_model": "medium",
    }
    for k, v in defaults.items():
        cfg.setdefault(k, v)
    for key in ("audio", "reciter_name_svg", "reciter_photo", "work_dir", "out_dir"):
        if cfg.get(key):
            p = Path(cfg[key])
            cfg[key] = str(p if p.is_absolute() else (base / p).resolve())
    for key in ("sura", "reciter_name"):
        if not cfg.get(key):
            sys.exit(f"config: '{key}' is required")
    Path(cfg["work_dir"]).mkdir(parents=True, exist_ok=True)
    Path(cfg["out_dir"]).mkdir(parents=True, exist_ok=True)
    return cfg


def work(cfg, *parts) -> Path:
    return Path(cfg["work_dir"]).joinpath(*parts)


def out(cfg, *parts) -> Path:
    return Path(cfg["out_dir"]).joinpath(*parts)


def step_done(paths, force=False) -> bool:
    """True when every output already exists (and --force was not given)."""
    if force:
        return False
    return all(Path(p).exists() and Path(p).stat().st_size > 0 for p in paths)


# ---------------------------------------------------------------- Quran data
AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def ar_num(n: int) -> str:
    return str(n).translate(AR_DIGITS)


def quran_data(riwaya="hafs") -> list[dict]:
    data_dir = VENDOR / "quran-data-kfgqpc" / riwaya / "data"
    files = sorted(data_dir.glob("*Data_v*.json"))
    if not files:
        sys.exit(f"KFGQPC data not found in {data_dir} — see GUIDE.md §2")
    return json.loads(files[-1].read_text(encoding="utf-8-sig"))


def sura_info(sura: int, riwaya="hafs") -> dict:
    data = quran_data(riwaya)
    ayat = [x for x in data if x["sora"] == sura]
    if not ayat:
        sys.exit(f"sura {sura} not found")
    juz = sorted({x["jozz"] for x in ayat})
    return {
        "sura": sura,
        "name_ar": ayat[0]["sora_name_ar"],
        "name_en": ayat[0]["sora_name_en"],
        "ayat": len(ayat),
        "juz_first": juz[0],
        "juz_last": juz[-1],
        "basmala_text": data[0]["aya_text"].rsplit("\xa0", 1)[0],   # الفاتحة ١
        "rows": ayat,
    }


# ---------------------------------------------------------------- tools
def find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        sys.exit("ffmpeg not found on PATH — see GUIDE.md §1")
    return exe


def run(cmd, cwd=None, check=True):
    print("  $", " ".join(str(c) for c in cmd)[:220])
    r = subprocess.run(cmd, cwd=cwd)
    if check and r.returncode != 0:
        sys.exit(f"command failed ({r.returncode})")
    return r


def find_browser() -> str:
    cands = [
        os.environ.get("QVK_BROWSER"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        shutil.which("msedge"), shutil.which("google-chrome"), shutil.which("chromium"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for c in cands:
        if c and Path(c).exists():
            return c
    sys.exit("No Chromium browser (Edge/Chrome) found. Set QVK_BROWSER — see GUIDE.md §1")


def _kill_tree(proc: subprocess.Popen):
    """Kill ONLY the process tree we started (never every browser process)."""
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        proc.kill()


def browser(args: list[str], cfg, timeout=90) -> str:
    """Run headless Chromium with an isolated profile; returns stdout text."""
    profile = work(cfg, "browser-profile")
    profile.mkdir(parents=True, exist_ok=True)
    cmd = [find_browser(), "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--no-first-run", "--no-default-browser-check", "--disable-extensions",
           f"--user-data-dir={profile}", "--allow-file-access-from-files",
           "--force-device-scale-factor=1"] + args
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        so, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        so, _ = proc.communicate()
    _kill_tree(proc)
    return (so or b"").decode("utf-8", "replace")


def file_url(p: Path) -> str:
    return Path(p).resolve().as_uri()


def screenshot(html: Path, png: Path, cfg, size=(1920, 1080), hash_="", transparent=False):
    png.parent.mkdir(parents=True, exist_ok=True)
    if png.exists():
        png.unlink()
    args = [f"--window-size={size[0]},{size[1]}", "--virtual-time-budget=4000",
            f"--screenshot={png}"]
    if transparent:
        args.append("--default-background-color=00000000")
    browser(args + [file_url(html) + (f"#{hash_}" if hash_ else "")], cfg)
    if not png.exists():
        sys.exit(f"browser did not write {png}")


def dump_dom(html: Path, cfg, timeout=120) -> str:
    return browser(["--virtual-time-budget=8000", "--dump-dom", file_url(html)], cfg, timeout)


# ---------------------------------------------------------------- reciter name block
def reciter_name_block(cfg, css_class="name") -> str:
    """Inline SVG calligraphy if supplied, else the name typed in Thmanyah Sans Black."""
    svg_path = cfg.get("reciter_name_svg")
    if svg_path and Path(svg_path).exists():
        svg = Path(svg_path).read_text(encoding="utf-8")
        svg = re.sub(r"<\?xml[^>]*>", "", svg)
        m = re.search(r"<svg\b[^>]*>", svg)
        tag = m.group(0)
        w = re.search(r'\bwidth="([\d.]+)', tag)
        h = re.search(r'\bheight="([\d.]+)', tag)
        new = tag
        if "viewBox" not in tag and w and h:
            new = new.replace("<svg", f'<svg viewBox="0 0 {w.group(1)} {h.group(1)}"', 1)
        new = re.sub(r'\s(width|height)="[^"]*"', "", new)
        new = new.replace("<svg", f'<svg id="name" class="{css_class}-svg" preserveAspectRatio="xMidYMid meet"', 1)
        return svg.replace(tag, new, 1)
    name = cfg["reciter_name"]
    return f'<div class="{css_class}-text fit">{name}</div>'


def fill_template(src: Path, dst: Path, mapping: dict):
    html = src.read_text(encoding="utf-8")
    for k, v in mapping.items():
        html = html.replace("{{" + k + "}}", str(v))
    left = re.findall(r"\{\{[A-Z_]+\}\}", html)
    if left:
        sys.exit(f"template {src.name}: unfilled placeholders {left}")
    dst.write_text(html, encoding="utf-8")


def link_assets(cfg):
    """Copy fonts + reciter photo next to generated HTML (relative URLs, no colons)."""
    w = work(cfg)
    fdir = w / "fonts"
    fdir.mkdir(exist_ok=True)
    for f in FONTS.glob("*/*"):
        if f.suffix.lower() in (".ttf", ".otf"):
            t = fdir / f.name
            if not t.exists():
                shutil.copy2(f, t)
    photo = cfg.get("reciter_photo")
    if photo and Path(photo).exists():
        shutil.copy2(photo, w / "reciter.png")
    return fdir


# ---------------------------------------------------------------- tafsir MCP
MCP_URL = os.environ.get("TAFSIR_MCP_URL", "https://mcp.tafsir.net/mcp")


def mcp_call(tool: str, arguments: dict, retries=4) -> dict:
    import urllib.request
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": arguments}}).encode()
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(MCP_URL, data=body, headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"})
            raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
            payload = raw
            if raw.lstrip().startswith("event:") or "\ndata:" in raw or raw.startswith("data:"):
                payload = "".join(l[5:].strip() for l in raw.splitlines() if l.startswith("data:"))
            res = json.loads(payload)["result"]
            if res.get("isError"):
                raise RuntimeError(res["content"][0]["text"][:300])
            return json.loads(res["content"][0]["text"])
        except Exception as e:     # network hiccup → retry with backoff
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"MCP {tool}{arguments} failed: {last}")


# ---------------------------------------------------------------- time
def ts_srt(t: float) -> str:
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def ts_ass(t: float) -> str:
    cs = int(round(max(t, 0) * 100)); h, cs = divmod(cs, 360000); m, cs = divmod(cs, 6000); s, cs = divmod(cs, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


def read_srt(fn) -> list[tuple[float, float, str]]:
    def f(x):
        h, m, s = x.strip().split(":")
        return int(h) * 3600 + int(m) * 60 + float(s.replace(",", "."))
    ev = []
    for b in Path(fn).read_text(encoding="utf-8-sig").strip().split("\n\n"):
        L = b.strip().split("\n")
        a, c = L[1].split(" --> ")
        ev.append((f(a), f(c), " ".join(L[2:])))
    return ev


def audio_duration(path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(r.stdout.strip())
