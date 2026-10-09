"""Fetch YouTube auto-captions (word-level timings) as a compact words list.

Used by step 01 and by tools/captions_proxy.py. Output format (same as Whisper step):
    [{"w": "الحمد", "s": 0.76, "e": 1.28, "p": 1.0}, ...]
The agent never needs to read the transcript itself — it only passes the file on.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


def json3_to_words(d: dict) -> list[dict]:
    words = []
    for ev in d.get("events", []):
        segs = ev.get("segs")
        if not segs:
            continue
        t0 = ev.get("tStartMs", 0)
        dur = ev.get("dDurationMs", 0)
        for sg in segs:
            txt = (sg.get("utf8") or "").strip()
            if not txt:
                continue
            s = (t0 + sg.get("tOffsetMs", 0)) / 1000
            words.append({"w": txt, "s": s, "e": (t0 + dur) / 1000, "p": 1.0})
    words.sort(key=lambda w: w["s"])
    for a, b in zip(words, words[1:]):      # end = next word start (bounded)
        a["e"] = min(a["e"], b["s"]) if b["s"] > a["s"] else a["e"]
    return words


def fetch(url: str, lang="ar", audio_out: Path | None = None) -> list[dict]:
    import yt_dlp
    with tempfile.TemporaryDirectory() as td:
        opts = {"skip_download": audio_out is None, "writeautomaticsub": True,
                "writesubtitles": True, "subtitleslangs": [lang], "subtitlesformat": "json3",
                "outtmpl": str(Path(td) / "v.%(ext)s"), "quiet": True, "no_warnings": True}
        if audio_out is not None:
            opts.update({"format": "bestaudio/best",
                         "postprocessors": [{"key": "FFmpegExtractAudio",
                                             "preferredcodec": "mp3", "preferredquality": "192"}]})
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        subs = list(Path(td).glob("*.json3"))
        if not subs:
            raise RuntimeError(f"no '{lang}' captions on this video (manual or auto)")
        words = json3_to_words(json.loads(subs[0].read_text(encoding="utf-8")))
        if audio_out is not None:
            mp3 = next(Path(td).glob("*.mp3"))
            Path(audio_out).parent.mkdir(parents=True, exist_ok=True)
            Path(audio_out).write_bytes(mp3.read_bytes())
    return words


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("usage: youtube_captions.py URL words.json [audio.mp3]")
    w = fetch(sys.argv[1], audio_out=Path(sys.argv[3]) if len(sys.argv) > 3 else None)
    Path(sys.argv[2]).write_text(json.dumps(w, ensure_ascii=False), encoding="utf-8")
    print("words:", len(w))
