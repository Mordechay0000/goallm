# Goallm

פרוקסי סינון (mitmproxy) לסינון תמונות ומלל בהתאם למדיניות ופרופילים, עם ממשק CRM לניהול חוקים ופרופילי סינון.

## הרצה מאפס (אחרי git clone)

מסודר מפורט: **[SETUP.md](SETUP.md)**.

### התקנה מהירה

```bash
git clone <repo-url> goallm
cd goallm
bash setup.sh
```

### הרצה (3 טרמינלים)

| טרמינל | פקודה |
|--------|-------|
| 1 (פרוקסי) | `cd goallm && source venv/bin/activate && mitmproxy -s core/proxy/mitmproxy_addon.py` |
| 2 (Backend) | `cd goallm/crm && bash run_fastapi.sh` |
| 3 (Frontend) | `cd goallm/crm/frontend && bash run_dev.sh` |

**דרישות:** Python 3.10+, Node.js 18+. `setup.sh` מתקין הכל. `run_fastapi.sh` ו־`run_dev.sh` מטפלים ב־venv ו־npm אוטומטית.

- פרוקסי: http://127.0.0.1:8080 | Backend: http://127.0.0.1:8000 | CRM: http://localhost:5173

## מבנה הפרויקט

```
goallm/
├── config/          # תצורות LLM (פרומפטים, חוזים)
├── core/            # ליבת הפרוקסי והסינון
│   ├── http_processor/   # עיבוד תגובות HTTP, סינון מלל, חילוץ תמונות, דפי מדיניות
│   ├── image_processing/ # תור אנליזת תמונות, DB סטטוס, החלפת תמונות, אנליזרים
│   ├── policy_processor/ # DB מדיניות, טעינת חוקים, URL policy resolver
│   ├── proxy/            # אדון mitmproxy
│   └── logger/           # הגדרות לוג
├── crm/             # ממשק ניהול (FastAPI + React)
├── data/            # קבועים (תמונות placeholder וכו')
├── test/            # שרתי בדיקה וטסטים
└── requirements.txt
```

## דרישות מקדימות

- Python 3.10+
- Node.js (לממשק CRM)
- התקנת תלויות **משורש הפרויקט** (מומלץ: בתוך venv):

```bash
cd /path/to/goallm
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## הפעלת הפרוקסי

הפרוקסי מרכז את כל עיבוד התגובות: מדיניות אתר (חסימה/שליחה לבדיקה/העברה), סינון מלל (רשימות מילים), וסינון תמונות (אנליזה והחלפה לפי סטטוס).

| פקודה | תיאור |
|--------|--------|
| `mitmproxy -s core/proxy/mitmproxy_addon.py` | ממשק אינטראקטיבי בטרמינל |
| `mitmweb -s core/proxy/mitmproxy_addon.py` | ממשק ווב |
| `mitmdump -s core/proxy/mitmproxy_addon.py` | לוג בלבד, ללא ממשק |

ברירת מחדל: `http://127.0.0.1:8080`. להגדרת פורט אחר: `-p 8888`.

פרטים נוספים: [core/proxy/README.md](core/proxy/README.md).

## הפעלת ה-CRM

ממשק הניהול מאפשר ניהול משתמשים, פרופילי סינון, חוקים ותזמונים. החוקים מסונכרנים ל־core ומשמשים את הפרוקסי.

1. **Backend (FastAPI)** – אחרי `bash setup.sh` משורש הפרויקט:
   ```bash
   cd crm && bash run_fastapi.sh
   ```
   שרת: http://127.0.0.1:8000  
   תיעוד API: http://127.0.0.1:8000/docs

2. **Frontend (React + Vite)**:
   ```bash
   cd crm/frontend && bash run_dev.sh
   ```
   אפליקציה: http://localhost:5173

פרטים: [crm/README.md](crm/README.md), [crm/START.md](crm/START.md).

## תיעוד נוסף

- [SETUP.md](SETUP.md) – הוראות הרצה מפורטות מאפס (Node.js, venv, פתרון בעיות)
- [core/REFACTOR_SUMMARY.md](core/REFACTOR_SUMMARY.md) – סיכום רפקטור core וייבואים
- [core/http_processor/DESIGN_TEXT_FILTER.md](core/http_processor/DESIGN_TEXT_FILTER.md) – עיצוב סינון מלל (ספים, רמות חומרה, רשימות מילים)
- [crm/SECURITY.md](crm/SECURITY.md) – אבטחה ב-CRM

## רישיון

לפי רישיון הפרויקט.
