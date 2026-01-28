# CRM - מערכת ניהול סינון

מערכת CRM מלאה לניהול פרופילי סינון, חוקים ותזמונים.

## מבנה המערכת

### Backend (FastAPI)
- `main.py` - FastAPI application עם כל ה-endpoints
- `database.py` - DB schema ו-management
- `models.py` - Pydantic models
- `services.py` - Business logic
- `auth.py` - Authentication utilities
- `resolver_integration.py` - אינטגרציה עם url_policy_resolver הקיים

### Frontend (React + TypeScript)
- `frontend/src/` - React application
- `frontend/src/pages/` - מסכים עיקריים
- `frontend/src/components/` - Components
- `frontend/src/api/` - API clients
- `frontend/src/store/` - Zustand stores

## התקנה והרצה

### Backend

```bash
# התקן תלויות
pip install -r requirements.txt

# הרץ את השרת
cd crm
./run_fastapi.sh
```

השרת יעלה על: http://127.0.0.1:8000
API docs: http://127.0.0.1:8000/docs

### Frontend

```bash
cd crm/frontend
npm install
npm run dev
```

האפליקציה תעלה על: http://localhost:5173

## תכונות עיקריות

1. **משתמשים** - הרשמה והתחברות
2. **פרופילים** - ניהול פרופילי סינון עם tabs
3. **חוקים** - הוספה/עריכה/מחיקה של חוקי סינון
4. **תזמונים** - הגדרת זמנים לפרופילים
5. **Realtime** - עדכונים בזמן אמת דרך WebSocket
6. **RTL** - תמיכה מלאה בעברית ו-RTL

## מודל URL

- הזנה: שדה אחד בלבד (URL מלא)
- הפרוטוקול (`http/https`) מוסר אוטומטית
- תמיכה ב-subdomain wildcard (`*.example.com`)
- Path prefix בלבד עם `*` לסגמנט אחד

## פילוסופיית סינון

- **רשימה לבנה**: כל האתרים פתוחים למעט אלו שחסומים
- **רשימה שחורה**: כל האתרים חסומים למעט אלו שפתוחים
- הכלל הכי ספציפי מנצח

## אינטגרציה

המערכת משולבת עם `url_policy_resolver` הקיים דרך:
- `/api/resolver/rules` - חוקים למשתמש מסוים
- `/api/resolver/rules/all` - כל החוקים הפעילים (לשימוש פנימי)
