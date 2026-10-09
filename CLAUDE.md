# Agent entry point

This repository is a recipe + toolchain for Quran recitation videos.
**Before doing anything, read `GUIDE.md` from top to bottom.** It is written for agents:
every step has the exact command, the expected output, and what to do when it differs.

Hard rules (details in GUIDE.md §0):
1. Quran text comes only from `vendor/quran-data-kfgqpc` (KFGQPC Hafs v18). Never type ayat from memory.
2. Tafsir comes only from the Tafsir MCP (`fetch_tafsir`, source `mukhtasar_ar`), verbatim.
3. Always render the 20-second preview and show it to the user before the full render.
4. Never kill all browser/ffmpeg processes — only the PID you started.
5. Ask the user for the reciter-name calligraphy (SVG). Without it the name is typed in Thmanyah Sans Black.
