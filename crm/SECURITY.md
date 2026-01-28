# מדיניות אבטחה - CRM System

## ספריות אבטחה בשימוש

### 1. הצפנת סיסמאות
- **bcrypt** ישירות - תקן תעשייתי להצפנת סיסמאות
- לא משתמשים ב-SHA256 (לא בטוח לסיסמאות)
- כל סיסמה מוצפנת עם salt ייחודי שנוצר אוטומטית
- 12 rounds של hashing (מומלץ)

### 2. JWT Tokens
- **PyJWT** - ספרייה רשמית ל-JWT
- אלגוריתם: HS256
- תוקף: 7 ימים
- SECRET_KEY: צריך להיות מוגדר ב-environment variable

### 3. Rate Limiting
- **slowapi** - הגבלת קצב בקשות
- Login: 5 ניסיונות לדקה לכל IP
- Register: 3 הרשמות לשעה לכל IP
- API: 100 בקשות לדקה לכל IP

### 4. אימות סיסמאות
- מינימום 8 תווים
- מקסימום 128 תווים
- חייבת להכיל לפחות ספרה אחת
- חייבת להכיל לפחות אות אחת

## הגדרות סביבה

יצירת קובץ `.env`:
```bash
SECRET_KEY=your-very-secure-random-secret-key-here-minimum-32-characters
```

## שיטות עבודה מומלצות

1. **לעולם אל תאחסן סיסמאות בטקסט פשוט**
2. **השתמש ב-SECRET_KEY חזק וייחודי**
3. **הגבל קצב בקשות למניעת brute force**
4. **ודא שהסיסמאות חזקות מספיק**
5. **השתמש ב-HTTPS בפרודקשן**

## עדכונים עתידיים

- [ ] CSRF protection
- [ ] Session management
- [ ] Two-factor authentication (2FA)
- [ ] Password reset flow
- [ ] Account lockout after failed attempts
