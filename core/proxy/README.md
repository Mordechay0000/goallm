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
