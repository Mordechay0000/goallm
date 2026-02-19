# מערכת עיצוב ומיתוג — ניהול הסינון

מסמך זה מגדיר את שפת העיצוב והטון של האתר. **כל דף ורכיב חייבים לעמוד בו** כדי לשמור על מיתוג ברמת Apple — ממשק אחיד, סגנון כתיבה מנחה, והנעת המשתמש בלי בלבול.

---

## 1. צבעי מותג

| שימוש | צבע | הערות |
|------|-----|--------|
| אמינות, כותרות | Deep Blue `#1e3a5f` | primary.main |
| חדשנות, פרימיום | AI Violet `#5b21b6` | secondary.main |
| כפתורים ראשיים, הדגשה | Electric Blue `#2563eb` | action / כפתור contained |
| רקע | White / Light Gray `#f8fafc` | background.default |
| טקסט ראשי | `#0f172a` | text.primary |
| טקסט גוף | `#334155` | text.body |
| אייקונים | אפור כהה / כחול כהה | צבע רק בפעולות מרכזיות |

- **גרדיאנט עדין** (3–5% opacity): רק בכותרות מרכזיות ו-onboarding. קלאס: `brand-gradient-subtle`.

---

## 2. טיפוגרפיה

- **כותרות**: `Assistant` / `Rubik` — נקי, עגול-עדין.
- **גוף**: `Rubik` — קריא ויציב.
- **קלאסים**: `page-title-section`, `section-title`, `section-title-sm` (מ-index.css).

כל עמוד: **כותרת ברורה + תיאור בשורה אחת** (מהקבועים ב-`brand.ts` → `PAGE_DESCRIPTIONS`).

---

## 3. צורות וריווח

- **פינות**: 10–18px (בתמה: 12–16). כפתורים, כרטיסים, שדות — עגולים עדינים.
- **ריווח**: רשת 8px. שימוש ב-CSS variables: `--space-8` עד `--space-48`.
- **כרטיסים**: מלבניים מסודרים, צל עדין, hover מעלה shadow (`shadow-card`, `shadow-card-hover`).

---

## 4. אייקונים

- Outline (לא מלאים), עובי קו 2–2.5px.
- צבע: אפור כהה או כחול כהה; צבעוני רק בפעולות מרכזיות (למשל AI / CTA).

---

## 5. אנימציות

- **רק micro-interactions**: hover עדין, shadow עדין, fade בין טאבים.
- **טעינה**: קו דק כחול־סגול (קלאס `brand-loading-bar` או `MuiLinearProgress`).
- אסור: קפיצות, תזוזות גדולות, מחוונים בולטים.

---

## 6. טון ושפה מנחה

- **מטרה**: המשתמש מבין כל פעולה תוך 3 שניות. המערכת **מובילה** אותו.
- **טקסט**: ברור, אחיד, בלי עומס. שורות קצרות. הנחיות מרגיעות: "בחר", "הזן", "בדוק", "אשר".
- **מקורות**: `brand.ts` — `COPY_ACTIONS`, `PAGE_DESCRIPTIONS`, `EMPTY_STATE`, `PLACEHOLDERS`. לא לכתוב טקסטים אד־הוק בדפים.

---

## 7. מבנה דף (חובה)

כל מסך CRM:

1. **כותרת ברורה** — `page-title-section` + `h1` / `Typography` variant מתאים.
2. **תיאור בשורה אחת** — מתוך `PAGE_DESCRIPTIONS` או טקסט מקביל.
3. **אזור פעולה מסודר** — כפתורים עם תיאור ברור (מ-`COPY_ACTIONS` או משפט מנחה).
4. **ריווח קבוע** — `container-content`, `page-section`, `block-gap` / `section-gap`.

---

## 8. Empty states

כשאין נתונים: כותרת + תיאור עידוד עדין. שימוש ב-`EMPTY_STATE` מ-`brand.ts`. קלאסים: `empty-state-title`, `empty-state-description`.

---

## 9. נגישות

- ניגודיות גבוהה, גופנים בגודל קריא.
- אלמנטים לחיצה/אינטראקציה בגודל נוח (לא פינות חדות).
- RTL ו-`lang="he"` כבר מוגדרים.

---

## 10. קבצים מרכזיים

- **צבעים וטיפוגרפיה**: `src/theme.ts`, `src/index.css` (CSS variables).
- **טקסטים וטון**: `src/brand.ts` (BRAND, COPY_ACTIONS, PAGE_DESCRIPTIONS, EMPTY_STATE, PLACEHOLDERS).
- **לוגו**: `src/components/BrandLogo.tsx`.

כל שינוי מיתוג/טון — לעדכן כאן וב-`brand.ts`/`theme.ts`/`index.css`, ולוודא שכל הדפים ורכיבי ה-UI משתמשים בהם.
