# הפעלת הפרוקסי (mitmproxy)

מריצים **מתוך שורש הפרויקט** (`goallm/`), אחרי `bash setup.sh` או התקנה ידנית.

## אימות וזיהוי המשתמש

ה-addon עצמו מאמת כל חיבור (לא `--set proxyauth` של mitmproxy). **אין סיסמת ברירת מחדל קבועה.**

| דרך | איך | זיהוי |
| --- | --- | --- |
| **פרטי התחברות אישיים (מומלץ)** | כל משתמש יוצר אותם ב-CRM → "חיבורים" (שם משתמש `u<id>` + סיסמה שמוצגת פעם אחת) | לפי המשתמש – עובד גם כשכמה בתים חולקים IP (סלולר / CGNAT) |
| סיסמה משותפת (legacy) | `PROXY_AUTH=user:pass` | לפי שיוך IP (דף bind) |
| בלי סיסמה | `PROXY_REQUIRE_AUTH=0` – רק לפיתוח / רשת סגורה | לפי שיוך IP |

`X-Forwarded-For` / `X-Real-IP` נלקחים בחשבון **רק** כשהחיבור מגיע מכתובת שב-`TRUSTED_PROXY_IPS` (ברירת מחדל `127.0.0.1,::1`).
אחרת כל גולש יכול היה "להתחזות" ל-IP של בית אחר.

## הפעלה

```bash
cd /path/to/goallm
bash core/proxy/run_proxy.sh            # mitmproxy (ממשק טרמינל)
bash core/proxy/run_proxy.sh mitmdump   # בלי ממשק – לשרת
bash core/proxy/run_proxy.sh mitmweb    # ממשק ווב
bash core/proxy/run_proxy.sh mitmdump -p 8888   # פורט אחר
```

ידנית: `mitmdump -s core/proxy/mitmproxy_addon.py`.

כמה תהליכים מאחורי load balancer (יותר מכמה עשרות בתים בו-זמנית): `bash core/proxy/run_cluster.sh start 4` –
פירוט, דוגמאות nginx/HAProxy ומגבלות: [`docs/deploy/SCALE.he.md`](../../docs/deploy/SCALE.he.md).
טלפונים ואפליקציות: [`docs/deploy/ANDROID.he.md`](../../docs/deploy/ANDROID.he.md).

## בדיקת סרטון בודד

וידאו חסום כברירת מחדל. גולש שולח סרטון לבדיקה (כפתור בסרגל / דף "סרטונים בדף"), תהליך נפרד בודק אותו,
וסרטון שאושר נפתח **לכל המשתמשים** (כולל המקטעים של HLS):

```bash
apt install ffmpeg                       # ffmpeg + ffprobe
IMAGE_ANALYZER=openai VLM_API_BASE=http://127.0.0.1:8001/v1 python -m core.filters.video.review_worker
```

- נדגמים `VIDEO_FPS` פריימים לשנייה (ברירת מחדל 1).
- פריים נשלח למודל רק אם **משהו השתנה** מאז הפריים האחרון שנבדק. ההשוואה מקומית, לפי אריחים: דמות קטנה שנכנסת לפינה מספיקה. צילום סטטי לא נשלח שוב.
- בנוסף, בדיקה כפויה כל `VIDEO_FORCE_ANALYZE_SEC` שניות.
- "כן" ראשון → הסרטון נחסם והבדיקה נעצרת. פריים שהמודל לא בטוח בו → תור בדיקה אנושית (מסך "תור בדיקה" למנהל).
- שידור חי וסרטון ארוך מ-`VIDEO_MAX_DURATION_SEC` לא נבדקים אוטומטית.
- **מעל כל סרטון חסום** (כולל נגן יוטיוב) מופיע לחצן "שלח לבדיקה". השליחה עוברת דרך הפרוקסי, בלי כניסה ל-CRM. כשהסרטון מאושר, הדף נטען מחדש.
- **יוטיוב:** אישור לפי videoId. פירוט, ומה לאשר ברשימה הלבנה: [`docs/deploy/YOUTUBE.he.md`](../../docs/deploy/YOUTUBE.he.md).
- **תיאור הסרטון נבדק ראשון:** מודל השפה קורא כותרת, תיאור, ערוץ ותגיות לפני שמורידים פריים. כך נחסם למשל קליפ של זמרת, גם כשהיא לא נראית. התיאור יכול רק לחסום. השמע עצמו לא מסונן.

## תמונות בתוך הדף (base64) וב-WebSocket

תמונות `data:image/...;base64` נבדקות בכל מקום בגוף התגובה: HTML (כולל `<script>`/`<style>`), JSON, JavaScript,
והודעות WebSocket מהשרת. הודעת WebSocket בינארית שהיא תמונה נבדקת כמו תמונה רגילה.

## מנתח התמונות

| `IMAGE_ANALYZER` | מתי |
| --- | --- |
| `simulated` (ברירת מחדל) | פיתוח בלבד – **התוצאה לא תלויה בתוכן התמונה** |
| `llama_cpp` | מודל GGUF מקומי תחת `models/`; בקשה אחת בכל רגע |
| `openai` | **ייצור**: שרת תואם OpenAI (vLLM / SGLang / llama-server). `VLM_API_BASE`, `VLM_MODEL` (ברירת מחדל `Qwen/Qwen3.5-9B`) |

דוגמה עם vLLM:

```bash
vllm serve Qwen/Qwen3.5-9B --port 8001 --max-model-len 16384
IMAGE_ANALYZER=openai VLM_API_BASE=http://127.0.0.1:8001/v1 bash core/proxy/run_proxy.sh mitmdump
```

מדידה לפני בחירת מודל: `python -m tools.eval_golden_set <dir>` (דיוק מול סט מתויג) ו-`python -m tools.benchmark_vlm <dir> 32` (תפוקה ועלות).

## שימוש

1. הגדירו במכשיר HTTP/HTTPS proxy לכתובת השרת והפורט (ברירת מחדל 8080).
2. כשהדפדפן מבקש אימות – שם המשתמש והסיסמה האישיים מעמוד "חיבורים" ב-CRM.
3. **HTTPS:** בפעם הראשונה התקינו את תעודת ה-CA (דרך `mitm.it` או דף האבחון ב-CRM).

אתרים רגישים (בנקים, קופות חולים, gov.il – `SENSITIVE_PASSTHROUGH_DOMAINS`) עוברים בלי פתיחת ההצפנה, אם הם מותרים ברשימה.
