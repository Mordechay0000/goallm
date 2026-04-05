# Goallm

**פרוקסי חכם לסינון תוכן בזמן אמת** — הדפדפן גולש דרך [mitmproxy](https://mitmproxy.org/), והמערכת מנתחת תגובות HTTP: טקסט, תמונות, ומסמכי PDF, לפי **מדיניות אתר**, **פרופילי משתמש** ו**חוקים** שמנוהלים מממשק CRM מודרני.

זהו פרויקט למי שרוצה להבין או לבנות **שכבת בקרה** בין המשתמש לאינטרנט: לא חוסם רק לפי דומיין, אלא יכול להחליט **לכל כתובת** אם לאפשר, לחסום, לשלוח לבדיקה, ולהחיל סינון מלל ותמונות עם מעקב סטטוס ותורים לעיבוד כבד.

---

## מה הפרויקט עושה — בקצרה

| רכיב | תפקיד |
|------|--------|
| **פרוקסי (mitmproxy)** | יושב בין המשתמש לאתרים; רואה תעבורה HTTPS (אחרי התקנת CA); מפעיל את לוגיקת הסינון על כל תגובה רלוונטית. |
| **Core** | מחבר מדיניות URL, סינון טקסט, סינון תמונות (כולל תמונות מוטמעות ב-HTML), PDF, דפי “חסום / שלח לבדיקה”, ויומן תעבורה למשתמשים מקושרים. |
| **CRM (FastAPI + React)** | משתמשים, מנהלים, פרופילים, חוקים, תזמונים, תמיכה, כלי ניהול; ה-API מסנכרן חוקים למסדי הנתונים שהפרוקסי קורא. |

התוצאה: ארגון או הורה יכולים להגדיר **מי רואה מה**, מתי לאתר נדרש אישור, ואיך מטופלות תמונות ומלל — הכל נשלט מממשק אחד, והפרוקסי מיישם בפועל.

---

## איך זה עובד — זרימה וחלקים

### 1. שכבת הפרוקסי (`core/proxy/`)

- **`mitmproxy_addon.py`** — נקודת הכניסה של mitmproxy: מזהה את כתובת ה-IP של הגולש, בודק אם היא **מקושרת למשתמש** ב-CRM, מפנה לא מקושרים לדף קישור (אם מופעל) או חוסם, ומעביר תגובות HTTP לעיבוד.
- **`run_proxy.sh`** — מריץ את הכלי עם האדון ועם **אימות פרוקסי** (ברירת מחדל: משתמש `filter`, סיסמה `f123456Ab`) — כדי שרק מי שמכיר את הפרטים יוכל לגלוש דרך הפרוקסי.
- **`surf_widget.py`** — ווידג’ט “גלישה” למנהלים: טוקן חתום (סוד משותף עם ה-CRM) מאפשר פעולות כמו חסימת אתר ישירות מהדף.

**חשוב:** גלישת HTTPS דורשת התקנת **תעודת CA** של mitmproxy בפעם הראשונה (ראו [הפעלה — HTTPS](#הפעלה--https-ורישיון-ca)).

### 2. עיבוד תגובות (`core/flow/`)

- **`http_flow_processor.py`** — אורקסטרציה: לפי מדיניות האתר והפרופיל — האם לעבור סינון, להחזיר דף חסימה/בדיקה, או להעביר הלאה; משלב סינון טקסט, תמונות (כולל מוטמעות), ו-PDF לפי הצורך.
- **`site_policy_pages.py`** — דפי HTML מותאמים (חסום, שלח לבדיקה וכו’) במקום התוכן המקורי כשהמדיניות כך קובעת.
- **`traffic_utils.py`** — עזרי לוגיקה לתעבורה (למשל סטטוסים לרישום).

### 3. מדיניות ומסדי נתונים (`core/policy/`)

- **`policy_database.py`** — SQLite: חוקי URL, פרופילים, שיוך IP למשתמש, הקלטות תעבורה, מפתחות “מפסקים” לסינונים, ועוד — מה שהפרוקסי וה-CRM חולקים.
- **`policy_loader.py` / `url_policy_resolver.py`** — טעינת כללים ופתרון “מה המדיניות לכתובת הזו?” (אפשר, חסום, בדיקה, היקף דומיין וכו’).

### 4. מסנני תוכן (`core/filters/`)

- **`filters/text/`** — סינון מלל לפי רשימות מילים, ספים וחומרה (`word_lists/` לעברית ואנגלית).
- **`filters/image/`** — חילוץ תמונות מהתגובה, תור עיבוד, סטטוסים (מאושר / חסום / ממתין), החלפה ב-placeholder כשצריך, אנליזרים (סימולציה או LLM אופציונלי).
- **`filters/pdf/`** — חילוץ וסינון בתוך PDF.
- **`filters/search/`** — הוקים לסינון הקשר חיפוש (למשל Google).

### 5. CRM (`crm/`)

- **Backend (`crm/main.py` ושכבת שירותים)** — REST API: אימות (JWT), משתמשים, חוקים, פרופילים, תזמונים, תמיכה, נקודות קצה פנימיות לפרוקסי (סוד משותף, עדכון שיוך IP).
- **Frontend (React + Vite + MUI)** — ממשק בעברית (RTL): לוח בקרה, ניהול חוקים, כלי אדמין, הקלטת תעבורה לניפוי וכו’.
- **`data/constants.py`** — נקודת אמת לכתובות CRM, סוד פרוקסי, אחסון, דגלי LLM — ניתן לדריסה במלואה או בחלקה דרך **משתני סביבה** (בייצור: `SECRET_KEY`, `CRM_PROXY_SECRET`, `PROXY_AUTH` וכו’).

### 6. נתונים ואחסון

- תיקיית **`.storage/`** (או `GOALLM_STORAGE_DIR`) — נוצרת אוטומטית; כוללת מסדי SQLite (CRM, מדיניות, סטטוס תמונות) והעלאות. **לא לפרסם** את התיקייה הזו — היא מקומית לסביבה.

פירוט מבנה הליבה: [`core/README.md`](core/README.md).

---

## דרישות מקדימות

| כלי | גרסה מינימלית | בדיקה |
|-----|----------------|--------|
| Python | 3.10+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm | מגיע עם Node | `npm --version` |
| Git | לשכפול הריפו | `git --version` |

ב-macOS אפשר להתקין Node עם Homebrew: `brew install node`. ב-Ubuntu/Debian: `sudo apt install nodejs npm`.

---

## התקנה — צעד אחר צעד

כל הפקודות below מניחות שאתה בתיקיית הפרויקט אחרי שכפול.

### אופן א׳: התקנה אוטומטית (מומלץ)

```bash
git clone <repo-url> goallm
cd goallm
bash setup.sh
```

**מה `setup.sh` עושה:**

1. יוצר סביבה וירטואלית Python בשם **`venv/`** בשורש הפרויקט.
2. מתקין תלויות מ־`requirements.txt`.
3. מריץ `npm install` בתוך `crm/frontend/`.
4. יוצר את תיקיית **`.storage/`** לאחסון מסדים והעלאות.

### אופן ב׳: התקנה ידנית

```bash
git clone <repo-url> goallm
cd goallm

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
deactivate                        # אופציונלי

cd crm/frontend
npm install
cd ../..
mkdir -p .storage && chmod 755 .storage
```

> **הערה:** סקריפטי ההרצה מחפשים קודם `venv/` ואז `.venv/` בשורש (רק `run_fastapi.sh` תומך ב־`.venv`). `setup.sh` יוצר תמיד `venv/`.

---

## הפעלה — שלושה טרמינלים

יש להריץ **משלושה חלונות טרמינל נפרדים**, בסדר כלשהו (בדרך כלל: קודם Backend כדי שמסדי הנתונים יאותחלו, אחר כך פרוקסי ופרונט).

| # | שירות | תיקיית עבודה | פקודה |
|---|--------|----------------|--------|
| 1 | **פרוקסי** | שורש `goallm/` | `bash core/proxy/run_proxy.sh` |
| 2 | **Backend (FastAPI)** | `goallm/crm/` | `bash run_fastapi.sh` |
| 3 | **Frontend (Vite)** | `goallm/crm/frontend/` | `bash run_dev.sh` |

**דוגמה מלאה (החלף את הנתיב):**

```bash
# טרמינל 1 — פרוקסי
cd /path/to/goallm
bash core/proxy/run_proxy.sh
```

```bash
# טרמינל 2 — API
cd /path/to/goallm/crm
bash run_fastapi.sh
```

```bash
# טרמינל 3 — ממשק
cd /path/to/goallm/crm/frontend
bash run_dev.sh
```

### כתובות ברירת מחדל

| שירות | כתובת מקומית | הערות |
|--------|----------------|--------|
| פרוקסי | http://127.0.0.1:8080 | הגדר בדפדפן/מערכת: HTTP(S) proxy → `127.0.0.1:8080` |
| Backend | http://127.0.0.1:8000 | Swagger/OpenAPI: http://127.0.0.1:8000/docs |
| CRM (פיתוח) | http://localhost:5173 | הפרוקסי מאזין על 8080; ה-Vite על 5173 |

ה-Backend מוגדר להאזין על `0.0.0.0` — גישה אפשרית גם ממכונות אחרות ברשת (אחריות אבטחה עליך).

### מצבי פרוקסי (אופציונלי)

אותו סקריפט, ארגומנט שני:

```bash
bash core/proxy/run_proxy.sh          # mitmproxy טרמינלי (ברירת מחדל)
bash core/proxy/run_proxy.sh mitmweb  # ממשק דפדפן
bash core/proxy/run_proxy.sh mitmdump # לוג בלבד
```

פורט אחר (דוגמה): הוסף בסוף את ארגומנטי mitmproxy, למשל `-p 8888`.

**שינוי אימות פרוקסי:**  
`PROXY_AUTH=משתמש:סיסמה bash core/proxy/run_proxy.sh`  
**ביטול אימות (לא מומלץ בייצור):**  
`PROXY_AUTH= bash core/proxy/run_proxy.sh`

פרטים נוספים: [`core/proxy/README.md`](core/proxy/README.md).

---

## הפעלה — HTTPS ורישיון CA

בפעם הראשונה שגולשים דרך הפרוקסי לאתרי HTTPS, יש להתקין את **תעודת ה-CA** של mitmproxy. גלוש ל-**https://mitm.it** דרך הפרוקסי ובחר התקנה לפי מערכת ההפעלה.

---

## מסדי נתונים (אוטומטי)

אין צורך ליצור קבצים ידנית. בפעם הראשונה שמריצים את השירותים, נוצרים קבצים תחת `.storage/` (למשל `crm.db`, `policies.db`, `image_status.db`). ראה גם [SETUP.md](SETUP.md) סעיף מסדי נתונים.

---

## משתני סביבה (תקציר)

הגדרות מרוכזות ב-[`data/constants.py`](data/constants.py) עם תיעוד inline. לייצון חובה לדרוס לפחות:

- `SECRET_KEY` — חתימת JWT  
- `CRM_PROXY_SECRET` — אימות בין פרוקסי ל-CRM  
- `PROXY_AUTH` — אימות גלישה בפרוקסי (פורמט `user:pass`)

אופציונלי: `CRM_BASE_URL`, `GOALLM_STORAGE_DIR`, `USE_LLM_IMAGE_ANALYZER`, ועוד — ראה קובץ הקבועים.

---

## מבנה התיקיות (מעודכן)

```
goallm/
├── config/                 # תצורות LLM (פרומפטים, חוזים) — אופציונלי לניתוח תמונות
├── core/
│   ├── flow/               # עיבוד תגובות HTTP, דפי מדיניות
│   ├── filters/            # טקסט, תמונה, PDF, חיפוש
│   ├── policy/             # מסד מדיניות, טעינת חוקים, resolver לכתובות
│   ├── proxy/              # אדון mitmproxy, Surf widget, סקריפט הרצה
│   └── logger/             # הגדרות לוג
├── crm/                    # FastAPI + React (ממשק ניהול)
├── data/                   # קבועים גלובליים (constants, דפי נחיתה וכו')
├── test/                   # בדיקות ושרתי עזר
├── requirements.txt
├── setup.sh
└── SETUP.md                # מדריך מפורט, פתרון בעיות, שרת SSH
```

---

## בדיקות

עם ה-venv מופעל משורש הפרויקט:

```bash
source venv/bin/activate
pip install pytest   # אם חסר
pytest test/ -q
```

בניית פרודקשן של הפרונט:

```bash
cd crm/frontend && npm run build
```

---

## תיעוד נוסף

| מסמך | תוכן |
|------|------|
| [SETUP.md](SETUP.md) | הרצה מאפס, התקנה ידנית, מסדי נתונים, רשת, פתרון בעיות |
| [core/README.md](core/README.md) | מבנה הליבה ודוגמאות ייבוא |
| [core/REFACTOR_SUMMARY.md](core/REFACTOR_SUMMARY.md) | היסטוריית רפקטור |
| [core/filters/text/word_lists/README.md](core/filters/text/word_lists/README.md) | רשימות מילים |
| [crm/README.md](crm/README.md), [crm/START.md](crm/START.md) | CRM |
| [crm/SECURITY.md](crm/SECURITY.md) | אבטחה |

---

## רישיון

לפי רישיון הפרויקט בקובץ הרישיון בשורש (אם קיים).
