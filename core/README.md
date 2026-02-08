# Core – מבנה הפרויקט

הליבה מאורגנת כתת-פרויקטים לפי סוג הסינון והתפקיד:

## `filters/` – סינון תוכן

- **`filters/image/`** – סינון תמונות  
  תור עיבוד, אנליזרים (סימולציה / LLM), סטטוס במסד, החלפת תמונות (block/checking/error), תמונות מוטמעות ב-HTML, חילוץ תמונה מתגובת HTTP.

- **`filters/text/`** – סינון טקסט  
  סינון מלל (רשימות מילים, ספים, חומרות), תצורה, רשימות מילים (`word_lists/`).

## `flow/` – זרימת עיבוד HTTP

- **`flow/`** – אורקסטרציה של התגובה  
  `http_flow_processor` – מחבר מדיניות אתר, סינון טקסט, סינון תמונות (ישיר ומוטמע).  
  `site_policy_pages` – דפי HTML להחלפה (חסום, שלח לבדיקה, וכו').

## `policy/` – מדיניות וכללים

- **`policy/`** – מדיניות URL ופרופיל  
  מסד מדיניות, טעינת כללים, רזולבר כתובות (block/allow/review), מתגי סינון גלובליים, sessions ו-traffic log.

## `proxy/` – שכבת הפרוקסי

- **`proxy/`** – תוסף mitmproxy, Surf widget, כלי עזר.

## `logger/` – לוגים

- **`logger/`** – הגדרות לוגים.

---

**ייבוא:**  
כל הקוד שמשתמש בליבה צריך לייבא מהנתיבים החדשים, למשל:

- `from core.filters.image.image_status_manager import get_image_with_status`
- `from core.filters.text.text_filter import filter_text_content`
- `from core.flow.http_flow_processor import process_http_response`
- `from core.policy.policy_database import get_filter_switches`
