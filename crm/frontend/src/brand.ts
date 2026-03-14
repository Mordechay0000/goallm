/**
 * מיתוג מרכזי – מקור אמת יחיד לשם המוצר וטון המותג.
 * שפת עיצוב: Deep Blue + AI Violet | מקצועי, חדשני, מסודר, נגיש.
 * טון: ברור, אחיד, בלי עומס — הנחיות שמרגיעות ומקדמות את המשתמש (בחר, הזן, בדוק, אשר).
 */

export const BRAND = {
  appName: 'ניהול הסינון',
  tagline: 'ההגדרות שלי',
  welcomeTitle: 'ברוך הבא',
  welcomeSubtitle: 'סיכום ההגדרות והמספרים שלך',
} as const;

/** הוראות פעולה מנחות — כל כפתור/שדה מוביל את המשתמש צעד־אחר־צעד */
export const COPY_ACTIONS = {
  choose: 'בחר',
  enter: 'הזן',
  check: 'בדוק',
  confirm: 'אשר',
  save: 'שמור',
  cancel: 'ביטול',
  next: 'המשך',
  back: 'חזרה',
  send: 'שלח',
  add: 'הוסף',
  edit: 'ערוך',
  delete: 'מחק',
  search: 'חפש',
  filter: 'סנן',
  create: 'צור',
  open: 'פתח',
  close: 'סגור',
} as const;

/** תיאורי דף — שורה אחת ברורה שמסבירה מה עושים כאן */
export const PAGE_DESCRIPTIONS = {
  home: BRAND.welcomeSubtitle,
  login: 'הזן טלפון וסיסמה כדי להתחבר',
  register: 'מלא את הפרטים כדי ליצור חשבון',
  setup: 'אין עדיין משתמשים במערכת. הרשם כמנהל – החשבון הראשון יוגדר כמנהל.',
  profile: 'עדכן את פרטי החשבון והסיסמה',
  profiles: 'נהל פרופילי סינון – בחר אילו אתרים לחסום או לפתוח',
  schedules: 'הגדר מתי הסינון פעיל לפי שעות וימים',
  requests: 'בקשות ששלחתי – עקוב אחרי סטטוס ואישורים',
  support: 'פניות ששלחתי ותשובות',
  connections: 'המכשירים המחוברים לחשבון שלך',
  tools: 'כלים נוספים למערכת',
  adminUsers: 'ניהול משתמשים והרשאות',
  adminRequests: 'בקשות שהתקבלו – אשר או דחה',
  adminGlobalRules: 'רשימת האתרים הגלובלית – חסום או פתח לכולם',
  adminGlobalFiles: 'רשימת הקבצים המותרים גלובלית',
  adminSiteInjections: 'הזרקת קוד ל־head/body והסתרת רכיבים לפי אתר',
  adminFilterSwitches: 'הפעלה וכיבוי של סינונים',
  adminSupport: 'פניות שהתקבלו – צפה והגב',
} as const;

/** Empty state — טקסט עידוד עדין כשאין נתונים */
export const EMPTY_STATE = {
  noProfiles: 'עדיין אין פרופילים. בחר "צור פרופיל" כדי להתחיל.',
  noRequests: 'עדיין לא שלחת בקשות. בחר "בקשה חדשה" כדי לשלוח.',
  noSupport: 'אין פניות. בחר "פנייה חדשה" כשתצטרך עזרה.',
  noConnections: 'אין מכשירים מחוברים. חבר מכשיר מההגדרות שלו.',
  noResults: 'לא נמצאו תוצאות. נסה לשנות את החיפוש או הסינון.',
  noUsers: 'אין משתמשים במערכת.',
  noData: 'אין נתונים להצגה.',
} as const;

/** placeholders לשדות — מנחים ולא מקצרים */
export const PLACEHOLDERS = {
  phone: '050-1234567',
  email: 'דוגמה@דומיין.co.il',
  search: 'חפש כאן...',
  name: 'הזן שם',
  url: 'https://example.com',
  code: '123456',
} as const;

export const DOCUMENT_TITLE = `${BRAND.appName} – CRM`;
