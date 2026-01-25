# CRM - ניהול כללי סינון

מערכת ניהול מודרנית ומסודרת לניהול כללי הסינון של המערכת.

## תכונות

- ✅ ניהול מלא של כללי סינון (הוספה, עריכה, מחיקה)
- ✅ ממשק משתמש נקי ומודרני
- ✅ חיפוש וסינון כללים
- ✅ שמירה במסד נתונים SQLite
- ✅ אימות נתונים מלא
- ✅ תמיכה בעברית (RTL)

## התקנה

1. התקן את התלויות:
```bash
pip install -r requirements.txt
```

## הרצה

### שיטה 1: הרצה ישירה
```bash
python3 -m crm.app
```

### שיטה 2: שימוש בסקריפט
```bash
./crm/run_crm.sh
```

השרת יעלה על `http://127.0.0.1:5000`

## שימוש

1. פתח את הדפדפן ונווט ל-`http://127.0.0.1:5000`
2. לחץ על "הוסף כלל חדש" כדי ליצור כלל חדש
3. מלא את הפרטים:
   - **דומיין**: דומיין לחסימה (לדוגמה: `example.com` או `*.example.com`)
   - **נתיב** (אופציונלי): נתיב ספציפי (לדוגמה: `/api/images` או `/images/*`)
   - **סוג**: סוג התוכן (כל הסוגים, תמונות, HTML, וכו')
   - **פעולה**: חסום או אפשר
   - **תיאור** (אופציונלי): תיאור קצר של הכלל
4. לחץ על "שמור"

## מבנה הכללים

כל כלל כולל:
- **domain**: דומיין (חובה) - יכול להיות `example.com` או `*.example.com` לחסימת תת-דומיינים
- **path**: נתיב (אופציונלי) - נתיב ספציפי. ניתן להשתמש ב-`*` למיקום יחיד
- **type**: סוג התוכן - `*` (כל הסוגים), `image`, `html`, `script`, `css`
- **state**: פעולה - `block` (חסום) או `allow` (מותר)
- **description**: תיאור (אופציונלי)
- **enabled**: האם הכלל פעיל

## אינטגרציה עם המערכת

הכללים נשמרים במסד נתונים SQLite ב-`.storage/policies.db`.

כדי לטעון את הכללים במערכת הסינון, השתמש ב:

```python
from core.policy_processor.policy_loader import get_policy_resolver

resolver = get_policy_resolver()
rule = resolver.resolve("https://example.com/image.jpg", "image")
```

## API

המערכת מספקת REST API מלא:

- `GET /api/policies` - קבלת כל הכללים
- `POST /api/policies` - יצירת כלל חדש
- `GET /api/policies/<id>` - קבלת כלל ספציפי
- `PUT /api/policies/<id>` - עדכון כלל
- `DELETE /api/policies/<id>` - מחיקת כלל
- `POST /api/policies/validate` - אימות כלל

## מבנה הקבצים

```
crm/
├── app.py              # Flask backend
├── static/
│   ├── index.html      # דף הבית
│   ├── styles.css      # עיצוב
│   └── app.js          # לוגיקה frontend
└── README.md           # תיעוד זה
```
