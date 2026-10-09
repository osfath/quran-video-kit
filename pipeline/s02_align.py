"""Step 02 — align recognised words to the KFGQPC Uthmani text → SRT files.

Outputs
  work/segments.srt   one line per display segment (split at waqf marks, ≤ segment_max_words)
  work/ayat.srt       one line per ayah (index 0 = basmala when the sura has one)
  out/<sura> - مقاطع.srt , out/<sura> - آيات.srt   (copies for editors / NLEs)
  work/align_debug.txt

The DP allows insertions (extra recognised words, e.g. isti'adha), deletions
(words the recogniser missed) and jumps back (the reciter repeating a phrase).
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # allow `python -I`
import argparse
import json
import re
import shutil
from difflib import SequenceMatcher

import numpy as np

from common import load_config, work, out, step_done, sura_info, ts_srt

ap = argparse.ArgumentParser()
ap.add_argument("config"); ap.add_argument("--force", action="store_true")
a = ap.parse_args()
cfg = load_config(a.config)
seg_srt, aya_srt = work(cfg, "segments.srt"), work(cfg, "ayat.srt")
if step_done([seg_srt, aya_srt], a.force):
    print("02 align: cached"); raise SystemExit

SURA = int(cfg["sura"])
info = sura_info(SURA, cfg["riwaya"])
WAQF = set("ۖۗۘۙۚۛۜ")
DIAC = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")


def norm(w):
    w = DIAC.sub("", w)
    w = re.sub("[أإآٱ]", "ا", w)
    w = w.replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي").replace("ء", "")
    return re.sub(r"[^ء-ي]", "", w)


# ---------------- reference words
ref = []
def add_aya(aya_no, uth, eml):
    u = uth.rsplit("\xa0", 1)[0].split()
    e = eml.split()
    while u and u[0] == "۞":                      # hizb mark glued to next word
        u = [u[0] + " " + u[1]] + u[2:]
    if len(u) != len(e):
        raise SystemExit(f"word count mismatch in aya {aya_no}: {len(u)} vs {len(e)}")
    for x, y in zip(u, e):
        ref.append({"u": x, "n": norm(y), "aya": aya_no})

data_rows = info["rows"]
if SURA not in (1, 9):
    from common import quran_data
    b = quran_data(cfg["riwaya"])[0]
    add_aya(0, b["aya_text"], b["aya_text_emlaey"])
for x in data_rows:
    add_aya(x["aya_no"], x["aya_text"], x["aya_text_emlaey"])
num = {x["aya_no"]: x["aya_text"].rsplit("\xa0", 1)[1] for x in data_rows}

# ---------------- display segments
MAXW = int(cfg["segment_max_words"])
seg_of = [0] * len(ref)
segs = []
i = 0
while i < len(ref):
    aya = ref[i]["aya"]
    idx = [k for k in range(i, len(ref)) if ref[k]["aya"] == aya]
    pieces, cur = [], []
    for k in idx:
        cur.append(k)
        if WAQF & set(ref[k]["u"]) and k != idx[-1]:
            pieces.append(cur); cur = []
    if cur:
        pieces.append(cur)
    merged = []
    for p in pieces:
        if merged and (len(p) < 3 or len(merged[-1]) < 3) and len(merged[-1]) + len(p) <= MAXW + 2:
            merged[-1] += p
        else:
            merged.append(p)
    for p in merged:
        n = -(-len(p) // MAXW)
        size = -(-len(p) // n)
        for s in range(0, len(p), size):
            segs.append(p[s:s + size])
    i = idx[-1] + 1
for si, p in enumerate(segs):
    for k in p:
        seg_of[k] = si

# ---------------- recognised words
rec = [w for w in json.loads(work(cfg, "words.json").read_text(encoding="utf-8")) if norm(w["w"])]
rn = [norm(w["w"]) for w in rec]
N, M = len(rec), len(ref)
if N == 0:
    raise SystemExit("words.json is empty")

uv = sorted(set(rn)); rv = sorted(set(r["n"] for r in ref))
ui = {w: k for k, w in enumerate(uv)}; ri = {w: k for k, w in enumerate(rv)}
simv = np.array([[SequenceMatcher(None, x, y).ratio() for y in rv] for x in uv], dtype=np.float32)
refidx = np.array([ri[r["n"]] for r in ref])

MATCH_T, INS, DEL, JUMP, NEG = 0.6, -0.7, -0.7, -4.0, -1e9
idxM = np.arange(M + 1)
score = idxM * (DEL * 0.3)                       # cheap late start
kind_bp = np.zeros((N + 1, M + 1), np.int8)     # 1 match 2 ins 3 del 4 jump
from_bp = np.zeros((N + 1, M + 1), np.int32)
kind_bp[0, 1:] = 3; from_bp[0, 1:] = idxM[:-1]

for i in range(1, N + 1):
    s = simv[ui[rn[i - 1]]][refidx]
    gain = np.where(s >= MATCH_T, 2 * s - 0.5, s - 1.2)
    new = score + INS; kind = np.full(M + 1, 2, np.int8); frm = idxM.astype(np.int32).copy()
    m = score[:M] + gain
    better = m > new[1:]
    new[1:][better] = m[better]; kind[1:][better] = 1; frm[1:][better] = idxM[:M][better]
    # jump back: best previous state at any j > j' then match ref j'
    rev = score[::-1]
    sm = np.maximum.accumulate(rev)[::-1]
    pos = np.where(rev == np.maximum.accumulate(rev), np.arange(M + 1), 0)
    arg = (M - np.maximum.accumulate(pos))[::-1]
    jv = np.full(M, NEG); ja = np.zeros(M, np.int64)
    jv[:M - 1] = sm[1:M] + JUMP; ja[:M - 1] = arg[1:M]
    jm = jv + gain
    better = jm > new[1:]
    new[1:][better] = jm[better]; kind[1:][better] = 4; frm[1:][better] = ja[better]
    # deletions forward, vectorised: new[j] = max_k<=j new[k] + DEL*(j-k)
    v = new - DEL * idxM
    cm = np.maximum.accumulate(v)
    src = np.maximum.accumulate(np.where(v >= cm, idxM, 0))
    moved = src != idxM
    new = cm + DEL * idxM
    kind[moved] = 3; frm[moved] = src[moved]
    score = new; kind_bp[i] = kind; from_bp[i] = frm

j = int(np.argmax(score - (M - idxM) * 0.3))
i = N
path = []
while i > 0 or j > 0:
    k, f = kind_bp[i, j], from_bp[i, j]
    if k in (1, 4):
        path.append((i - 1, j - 1)); i, j = i - 1, int(f)
    elif k == 2:
        i -= 1
    elif k == 3:
        j = int(f)
    else:
        break
path.reverse()
covered = len(set(p[1] for p in path))
print(f"02 align: recognised {N}, reference {M}, matched {len(path)}, covered {covered} ({covered / M:.1%})")
if covered / M < 0.85:
    print("   WARNING: low coverage — wrong sura/riwaya, or poor captions. See GUIDE.md §7 (troubleshooting).")


def build(seg_fn):
    runs = []
    for r_, fj in path:
        sg = seg_fn(fj); w = rec[r_]
        if runs and runs[-1][0] == sg and fj > runs[-1][3]:
            runs[-1][2] = w["e"]; runs[-1][3] = fj
        else:
            runs.append([sg, w["s"], w["e"], fj])
    seen = set(r[0] for r in runs)
    outl = []
    for r in runs:
        if outl:
            prev = outl[-1][0]
            if r[0] > prev + 1:
                miss = [s for s in range(prev + 1, r[0]) if s not in seen]
                if miss:
                    x, y = outl[-1][2], r[1]
                    st = (y - x) / len(miss) if y > x else 0
                    for n_, s in enumerate(miss):
                        outl.append([s, x + n_ * st, x + (n_ + 1) * st, -1]); seen.add(s)
        outl.append(r)
    for k in range(len(outl)):
        nxt = outl[k + 1][1] if k + 1 < len(outl) else outl[k][2] + 1.0
        outl[k][2] = nxt if nxt - outl[k][2] < 3.0 else min(outl[k][2] + 0.6, nxt)
        outl[k][2] = max(outl[k][2], outl[k][1] + 0.3)
    return outl


def text_seg(si):
    ks = segs[si]
    t = " ".join(ref[k]["u"] for k in ks)
    aya = ref[ks[-1]]["aya"]
    last_of_aya = ks[-1] + 1 >= len(ref) or ref[ks[-1] + 1]["aya"] != aya
    return t + ("\xa0" + num[aya] if aya and last_of_aya else "")


ayas = sorted(set(r["aya"] for r in ref))
aya_pos = {x: n for n, x in enumerate(ayas)}
def text_aya(ai):
    x = ayas[ai]
    return " ".join(r["u"] for r in ref if r["aya"] == x) + ("\xa0" + num[x] if x else "")


def write(fn, events, txt):
    with open(fn, "w", encoding="utf-8-sig", newline="\r\n") as f:
        for n_, (sg, s, e, _) in enumerate(events, 1):
            f.write(f"{n_}\n{ts_srt(s)} --> {ts_srt(e)}\n{txt(sg)}\n\n")


write(seg_srt, build(lambda k: seg_of[k]), text_seg)
aya_events = build(lambda k: aya_pos[ref[k]["aya"]])
write(aya_srt, aya_events, text_aya)
# first start / last end per ayah (robust to repeated passages) for the tafsir timing
times = {}
for sg, s, e, _ in aya_events:
    x = ayas[sg]
    if x not in times:
        times[x] = [s, e]
    times[x][1] = max(times[x][1], e)
work(cfg, "ayah_times.json").write_text(json.dumps(times), encoding="utf-8")
name = f"{SURA:03d} {info['name_en']}"
shutil.copy2(seg_srt, out(cfg, f"{name} - segments.srt"))
shutil.copy2(aya_srt, out(cfg, f"{name} - ayat.srt"))
with open(work(cfg, "align_debug.txt"), "w", encoding="utf-8") as f:
    for r_, fj in path:
        f.write(f"{rec[r_]['s']:8.2f} {rec[r_]['w']:>15} -> {ref[fj]['aya']:3} {ref[fj]['n']}\n")
print("02 align: wrote", seg_srt.name, aya_srt.name)
