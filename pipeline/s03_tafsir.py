"""Step 03 — fetch the tafsir text for every ayah from the Tafsir MCP → work/tafsir.json

Source of truth: the `fetch_tafsir` tool of tafsircenter/tafsir-mcp
(hosted at https://mcp.tafsir.net/mcp, override with env TAFSIR_MCP_URL).
Default source id: "mukhtasar_ar" = المختصر في تفسير القرآن الكريم.

RULE: the text is used VERBATIM. The only transformation is removing the
`_..._` markers (they flag the explained Quranic words) and collapsing spaces.
Never summarise, rephrase or add text of your own.
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # allow `python -I`
import argparse
import json
import re

from common import load_config, work, step_done, sura_info, mcp_call

ap = argparse.ArgumentParser()
ap.add_argument("config"); ap.add_argument("--force", action="store_true")
a = ap.parse_args()
cfg = load_config(a.config)
dst = work(cfg, "tafsir.json")
if not cfg["tafsir"]:
    print("03 tafsir: disabled in config"); raise SystemExit
if step_done([dst], a.force):
    print("03 tafsir: cached"); raise SystemExit

SURA = int(cfg["sura"]); src = cfg["tafsir_source"]
n = sura_info(SURA, cfg["riwaya"])["ayat"]
cache = work(cfg, "tafsir_raw"); cache.mkdir(exist_ok=True)
result = {}
for aya in range(1, n + 1):
    f = cache / f"{aya}.json"
    if f.exists():
        d = json.loads(f.read_text(encoding="utf-8"))
    else:
        parts, part, total = [], 1, 1
        while part <= total:
            r = mcp_call("fetch_tafsir", {"surah": SURA, "ayah": aya, "sources": [src], "part": part})
            t = [x for x in r["tafsirs"] if x["source"] == src]
            if not t:
                raise SystemExit(f"source {src} missing for {SURA}:{aya}")
            parts.append(t[0]["text_raw"])
            total = int(r.get("total_parts") or t[0].get("total_parts") or 1)
            part += 1
        d = {"text": " ".join(parts), "attribution": t[0]["attribution"]}
        f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    clean = re.sub(r"\s+", " ", d["text"].replace("_", "")).strip()
    result[str(aya)] = clean
    if aya % 10 == 0 or aya == n:
        print(f"   {aya}/{n}", flush=True)
dst.write_text(json.dumps({"source": src, "attribution": d["attribution"], "ayat": result},
                          ensure_ascii=False, indent=1), encoding="utf-8")
print(f"03 tafsir: {len(result)} ayat → {dst.name} ({d['attribution']})")
