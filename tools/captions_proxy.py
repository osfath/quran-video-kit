"""Tiny local HTTP proxy: YouTube auto-captions → compact word timings (JSON).

Purpose: let an agent (or any app) get the timing data with ONE small call,
without pasting transcripts into the conversation (saves tokens) and without
running Whisper.

  python -I tools/captions_proxy.py --port 8765
  GET http://127.0.0.1:8765/captions?v=<youtube id or url>&lang=ar
      → {"video": "...", "lang": "ar", "count": 1593, "words": [{"w","s","e","p"}, ...]}
  GET http://127.0.0.1:8765/captions?v=...&save=D:/path/words.json
      → writes the file and returns only {"saved": "...", "count": N}   (cheapest)
  GET /health → ok

Binds to 127.0.0.1 only. Results are cached in memory per (video, lang).
"""
import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from youtube_captions import fetch  # noqa: E402

CACHE = {}
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            self._get()
        except Exception as e:  # never drop the connection silently
            self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def _get(self):
        # http.server decodes the request line as latin-1; recover raw UTF-8 (Arabic paths)
        try:
            raw = self.path.encode("latin-1").decode("utf-8")
        except UnicodeError:
            raw = self.path
        u = urlparse(raw)
        if u.path == "/health":
            return self._send(200, {"ok": True})
        if u.path != "/captions":
            return self._send(404, {"error": "use /captions?v=ID&lang=ar"})
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        v, lang = q.get("v"), q.get("lang", "ar")
        if not v:
            return self._send(400, {"error": "missing v"})
        url = v if v.startswith("http") else f"https://www.youtube.com/watch?v={v}"
        try:
            key = (url, lang)
            if key not in CACHE:
                CACHE[key] = fetch(url, lang=lang)
            words = CACHE[key]
        except Exception as e:
            return self._send(502, {"error": str(e)})
        if q.get("save"):
            Path(q["save"]).write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
            return self._send(200, {"saved": q["save"], "count": len(words)})
        self._send(200, {"video": url, "lang": lang, "count": len(words), "words": words})

    def log_message(self, fmt, *args):
        sys.stderr.write("proxy: " + fmt % args + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    print(f"captions proxy on http://127.0.0.1:{a.port}/captions?v=VIDEO_ID&lang=ar")
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
