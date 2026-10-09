---
name: quran-recitation-video
description: يصنع فيديو تلاوة قرآن كامل 16:9 بالرسم العثماني (مصحف حفص – مجمع الملك فهد) متزامن مع صوت القارئ، مع «المختصر في التفسير» يُكتب حرفًا حرفًا من Tafsir MCP، وخلفية متحركة، وصورة القارئ واسمه بالخط، وثلاث صور مصغّرة (ثمنيل). Use when the user says "سو فيديو تلاوة"، "ركّب الآيات على التلاوة"، "ترجمة قرآن للتايم لاين"، "الرسم العثماني على الصوت"، "فيديو سورة"، "ثمنيل سورة", or sends a recitation audio / YouTube link of a sura.
---

# فيديو تلاوة بالرسم العثماني

المرجع الوحيد: `GUIDE.md` في جذر الحزمة `quran-video-kit`. اقرأه كاملًا قبل أي أمر.
مسار الحزمة على هذا الجهاز مكتوب في `KIT_PATH.txt` بجانب هذا الملف (يكتبه `setup/setup.ps1`). إن لم يوجد فاسأل المستخدم عن مكان المجلد.

ملخص التنفيذ:
1. اسأل المستخدم عن: رقم السورة، ملف الصوت أو رابط يوتيوب، صورة القارئ PNG مفرّغة، و**اسم القارئ بالخط (SVG)**. إن لم يتوفر الـSVG يُكتب الاسم بخط ثمانية (Sans Black) تلقائيًا.
2. أنشئ `projects/<slug>/config.json` من `examples/kahf-alhassan/config.json`.
3. `python -I pipeline/run.py projects/<slug>/config.json` → معاينة 20 ثانية + 3 ثمنيلات. اعرضها على المستخدم.
4. بعد موافقته: `python -I pipeline/run.py projects/<slug>/config.json --from 7 --to 7 --full`.

ممنوع: كتابة نص قرآني أو تفسير من الذاكرة. القرآن من `vendor/quran-data-kfgqpc` والتفسير من Tafsir MCP حرفيًا.
