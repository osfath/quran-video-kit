"""Step 05 — build work/full.ass : verse band + typewriter tafsir panel + ayah badge.

Typewriter rules (tested; do not "simplify"):
  * Each LINE is its own Dialogue event, positioned with \\an9\\pos(right, y).
    Never put override tags inside a line of Arabic text: libass then splits
    bidi runs and the word order breaks (and per-letter \\k karaoke breaks shaping).
  * Typing = a sequence of events showing a growing prefix of the line
    (~25 states/second). Line breaks come from the browser measurement (step 04),
    so the text never re-wraps while it is being typed.
  * Speed: ≥18 chars/s, faster when the ayah is short; max 55 chars/s.
    The text may lag its ayah slightly but never drifts: a new ayah's tafsir
    starts at max(ayah start, previous tafsir finished + 0.6s).
  * Long tafsir is paged (7 lines per page, 1.6s hold between pages).
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # allow `python -I`
import argparse
import json
import unicodedata

from common import (load_config, work, step_done, sura_info, read_srt, ts_ass, audio_duration, BS)

ap = argparse.ArgumentParser()
ap.add_argument("config"); ap.add_argument("--force", action="store_true")
a = ap.parse_args()
cfg = load_config(a.config)
W = work(cfg)
dst = W / "full.ass"
if step_done([dst], a.force):
    print("05 subs: cached"); raise SystemExit

info = sura_info(int(cfg["sura"]), cfg["riwaya"])
layout = json.loads((W / "layout.json").read_text(encoding="utf-8"))
segs = read_srt(W / "segments.srt")
ayas = read_srt(W / "ayat.srt")
audio = (W / "audio_path.txt").read_text(encoding="utf-8") if (W / "audio_path.txt").exists() else cfg["audio"]
END_T = audio_duration(audio)
num = {x["aya_no"]: x["aya_text"].rsplit("\xa0", 1)[1] for x in info["rows"]}
has_basmala = int(cfg["sura"]) not in (1, 9)
n_ayat = info["ayat"]

events = []
# ---------------- verse band
for (s, e, txt), sc in zip(segs, layout["verse_scale"]):
    scale = f"{BS}fscx{sc}{BS}fscy{sc}" if sc < 100 else ""
    events.append((s, f"Dialogue: 2,{ts_ass(s)},{ts_ass(e)},Aya,,0,0,0,,{{{BS}pos(960,778){BS}fad(200,200){scale}}}{txt}"))

# ---------------- tafsir typewriter
if cfg["tafsir"]:
    lines = layout["tafsir_lines"]
    times = {int(k): v for k, v in json.loads((W / "ayah_times.json").read_text()).items()}
    start = {k: times[k][0] for k in range(1, n_ayat + 1)}
    start[n_ayat + 1] = max(v[1] for v in times.values())
    for k in range(2, n_ayat + 2):          # keep monotonic even if alignment is odd
        start[k] = max(start[k], start[k - 1])
    RIGHT_X, TOP_Y, LH, PAGE = 976, 172, 62, 7
    CPS_MIN, CPS_MAX, HOLD, GAP = 18, 55, 1.6, 0.6

    def units(s):
        u = []
        for ch in s:
            if u and unicodedata.combining(ch):
                u[-1] += ch
            else:
                u.append(ch)
        return u

    sched, prev_done = {}, 0.0
    for k in range(1, n_ayat + 1):
        L = lines[str(k)]
        pages = [L[i:i + PAGE] for i in range(0, len(L), PAGE)]
        n = sum(len(units(" ".join(p))) for p in pages)
        t0 = max(start[k], prev_done + GAP)
        deadline = max(start[k + 1] + 2.0, t0 + 1)
        avail = deadline - t0 - HOLD * (len(pages) - 1)
        cps = min(CPS_MAX, max(CPS_MIN, n / max(avail, 0.1)))
        sched[k] = (t0, cps, pages)
        prev_done = t0 + n / cps + HOLD * (len(pages) - 1)

    lag = max((sched[k][0] - start[k], k) for k in sched)
    print(f"05 subs: max tafsir lag {lag[0]:.1f}s (ayah {lag[1]}), max speed {max(v[1] for v in sched.values()):.0f} chars/s")
    for k in range(1, n_ayat + 1):
        t0, cps, pages = sched[k]
        t_end = sched[k + 1][0] - 0.05 if k < n_ayat else min(END_T, start[n_ayat + 1] + 3)
        events.append((t0, f"Dialogue: 1,{ts_ass(t0)},{ts_ass(t_end)},Num,,0,0,0,,{{{BS}an7{BS}pos(96,92){BS}fad(150,150)}}{num[k]}"))
        t = t0
        for pi, page in enumerate(pages):
            u_lines = [units(l) for l in page]
            total = sum(len(x) for x in u_lines)
            p_end = t_end if pi == len(pages) - 1 else t + total / cps + HOLD
            for li, ul in enumerate(u_lines):
                y = TOP_Y + li * LH
                ls = t + sum(len(x) for x in u_lines[:li]) / cps
                le = ls + len(ul) / cps
                step = max(1, round(cps / 25))
                for c in range(step, len(ul), step):
                    a_ = ls + c / cps; b_ = ls + min(c + step, len(ul)) / cps
                    txt = "".join(ul[:c]).rstrip()
                    if txt:
                        events.append((a_, f"Dialogue: 0,{ts_ass(a_)},{ts_ass(b_)},Taf,,0,0,0,,{{{BS}an9{BS}pos({RIGHT_X},{y})}}{txt}"))
                events.append((le, f"Dialogue: 0,{ts_ass(le)},{ts_ass(p_end)},Taf,,0,0,0,,{{{BS}an9{BS}pos({RIGHT_X},{y}){BS}fad(0,150)}}{''.join(ul)}"))
            t = p_end

events.sort(key=lambda e: e[0])
hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Aya,KFGQPC HAFS Uthmanic Script,112,&H00FFFFFF,&H00FFFFFF,&H00301000,&H90000000,0,0,0,0,100,100,0,0,1,1.2,3,5,200,200,0,178
Style: Taf,Thmanyah sans 1.2 Med,{layout['taf_ass_size']},&H00FFF4EA,&H00FFF4EA,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,9,0,0,0,178
Style: Num,KFGQPC HAFS Uthmanic Script,120,&H007ACFF1,&H007ACFF1,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,178

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
dst.write_text(hdr + "\n".join(e[1] for e in events) + "\n", encoding="utf-8-sig")
print(f"05 subs: {len(events)} events → {dst.name}")
