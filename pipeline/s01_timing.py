"""Step 01 — word timings → work/words.json

Order of preference (timing_source = "auto"):
  1. YouTube auto-captions of `youtube_url` (fast, no GPU, no tokens)
  2. faster-whisper on the local audio (slow on CPU: ~1x real time with 'medium')
If `audio` is missing and `youtube_url` is set, the audio is downloaded too.
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # allow `python -I`
import argparse
import json
from pathlib import Path

from common import load_config, work, step_done

ap = argparse.ArgumentParser()
ap.add_argument("config"); ap.add_argument("--force", action="store_true")
a = ap.parse_args()
cfg = load_config(a.config)
dst = work(cfg, "words.json")

need_audio = not cfg.get("audio") or not Path(cfg["audio"]).exists()
if step_done([dst], a.force) and not need_audio:
    print("01 timing: cached"); raise SystemExit

src = cfg["timing_source"]
url = cfg.get("youtube_url")
words = None
if url and src in ("auto", "youtube"):
    from youtube_captions import fetch
    audio_out = None
    if need_audio:
        audio_out = Path(cfg["work_dir"]) / "audio.mp3"
        cfg["audio"] = str(audio_out)
    try:
        words = fetch(url, audio_out=audio_out)
        print(f"01 timing: YouTube captions → {len(words)} words")
    except Exception as e:
        if src == "youtube":
            raise
        print("01 timing: YouTube captions unavailable:", e)

if words is None:
    if need_audio:
        raise SystemExit("01 timing: no audio file and no YouTube URL — set 'audio' in config")
    from faster_whisper import WhisperModel
    print(f"01 timing: faster-whisper '{cfg['whisper_model']}' on CPU (this takes a while)…")
    m = WhisperModel(cfg["whisper_model"], device="cpu", compute_type="int8")
    segs, _ = m.transcribe(cfg["audio"], language="ar", word_timestamps=True, beam_size=5,
                           vad_filter=True, condition_on_previous_text=False)
    words = []
    for s in segs:
        for w in s.words:
            words.append({"w": w.word.strip(), "s": w.start, "e": w.end, "p": w.probability})
        print(f"   {s.end:7.1f}s", flush=True)

dst.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
# remember a downloaded audio path for later steps
(work(cfg, "audio_path.txt")).write_text(cfg["audio"], encoding="utf-8")
print("01 timing: wrote", dst)
