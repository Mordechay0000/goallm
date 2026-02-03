# הוראות הרצה - CRM System

## ✅ המערכת מוכנה ופועלת!

### השרתים רצים על:
- **Backend (FastAPI)**: http://127.0.0.1:8000
- **Frontend (React)**: http://localhost:5173
- **API Docs**: http://127.0.0.1:8000/docs

---

## הרצה ידנית

> **התקנה ראשונית:** הרץ `bash setup.sh` משורש הפרויקט (`goallm/`).

### Backend:
```bash
cd crm
bash run_fastapi.sh
```

### Frontend:
```bash
cd crm/frontend
bash run_dev.sh
```

---

## בדיקות מהירות

### בדיקת Backend:
```bash
curl http://127.0.0.1:8000/api/resolver/rules/all
```

### בדיקת Frontend:
```bash
curl http://localhost:5173/
```

### בדיקת Authentication:
```bash
# הרשמה
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123456"}'

# התחברות
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123456"}'
```

---

## משתמש לבדיקה

- **Email**: test@example.com
- **Password**: test123456

---

## פתרון בעיות

אם השרתים לא רצים:

1. **בדוק שהפורטים פנויים:**
   ```bash
   lsof -i :8000 -i :5173
   ```

2. **הרוג תהליכים ישנים:**
   ```bash
   lsof -ti:8000 | xargs kill -9
   lsof -ti:5173 | xargs kill -9
   ```

3. **התקן תלויות:** (משורש הפרויקט `goallm/`)
   ```bash
   bash setup.sh
   ```

---

## מבנה המערכת

- `crm/main.py` - FastAPI application
- `crm/frontend/` - React application
- `crm/database.py` - Database schema
- `crm/services.py` - Business logic
- `.storage/crm.db` - SQLite database
