# סיכום רפקטור Core

## שינויים שבוצעו

### 1. Proxy (`core/proxy/`)

- **`mitmproxy_addon.py`**: 
  - `FilterAddon` כעת מחלקה מסודרת; הוסר `normalize_domain` מתוך המחלקה (לא היה בשימוש).
  - פירוק טיפול בשגיאות ל־`format_flow_error` ו־`format_response_error` ב־`utils.py`.
  - לוגים עוברים ל־`%s` style.
- **`utils.py`** (חדש):
  - `normalize_domain(url)` – נורמליזציה של דומיין (הועבר מהאדון, לשימוש עתידי).
  - `format_flow_error(flow)`, `format_response_error(url, exc)` – בניית הודעות שגיאה.

### 2. HTTP Processor (`core/http_processor/`)

- **`image_extraction.py`** (חדש):
  - `extract_image_content(flow)` – זיהוי תמונה מפי תגובה (magic bytes) ומחזיר `(bytes, mime) | None`.
  - חתימות פורמטים מרוכזות ב־`_SIGNATURES`.
- **`http_flow_processor.py`**:
  - משתמש ב־`extract_image_content` מ־`image_extraction`.
  - הוסר קוד מת: `extract_images_from_html`, `is_video` (לא נקראו).
  - הוסרה תלות ב־BeautifulSoup.

### 3. Image Processing (`core/image_processing/`)

- **`analyzers/base.py`** (חדש):
  - מחלקה אבסטרקטית `ImageAnalyzer` עם `analyze_image(image_content, mime) -> dict`.
- **`simulated_image_analyzer.py`** ו־**`llm_image_analyzer.py`**:
  - יורשים מ־`ImageAnalyzer`.
  - תיקון טיפוסים (`mime: str | None`), העברת `import os` לראש הקובץ.
  - ב־LLM: `NMPROJ_MODEL_PATH` → `MMPROJ_MODEL_PATH`, יישור הזחות.
- **`image_status_db.py`** (חדש):
  - סכמת DB, `get_image_status`, `save_analysis_result`, `mark_pending`.
  - חיבור DB מקומי ב־מודול.
- **`image_replacement.py`** (חדש):
  - `create_image_content(svg, mime, size)` – המרת SVG לתמונה.
  - `get_checking_image`, `get_blocked_image`, `get_error_image` – placeholder לפי סטטוס.
  - ייבוא `cairosvg` lazy בתוך הפונקציה.
- **`image_status_manager.py`**:
  - משמש רק כ־orchestrator: משתמש ב־DB, תור, ו־replacement.
  - `get_image_with_status` נשמר; הקריאה ל־DB ו־replacement עוברת למודולים החדשים.
- **`image_processing_queue.py`**:
  - `enqueue(..., image_details=dict())` → `image_details: dict | None = None` (תיקון mutable default).
  - הוסר `_image_hash` שלא היה בשימוש; הוספת `_hash_prefix` ללוגים.
  - לוגים ב־`%s` style.

### 4. Policy Processor (`core/policy_processor/`)

- **`__init__.py`** (חדש):
  - ייצוא פונקציות מ־`policy_database`, `policy_loader`, ו־`URLPolicyResolver` / `URLPolicyResolverError`.
- **`policy_loader.py`**:
  - עדכון טיפוסים וניסוח.

### 5. Logger (`core/logger/`)

- **`logging_config.py`**:
  - `STORAGE_DIR`, `LOG_FILE` כקבועים; `setup_logging()` עם type hint.
  - פישוט ו־`%s` בלוגים.
- **`__init__.py`**: ייצוא `setup_logging`.

### 6. __init__ exports

- **`http_processor`**: `process_http_response`, `extract_image_content`.
- **`image_processing`**: `get_image_with_status`, `ImageProcessingQueue`, `ImageTask`, `TaskStatus`, `ImageAnalyzer`, `SimulatedImageAnalyzer`.
- **`proxy`**: `FilterAddon`, `addons`, `normalize_domain`.

---

## איך להמשיך לעבוד

- **ייבואים**: אפשר להמשיך לייבא מנתיבים הישנים (למשל `core.http_processor.http_flow_processor`, `core.image_processing.image_status_manager`). בנוסף, אפשר לייבא מ־`core.http_processor`, `core.image_processing`, `core.proxy`, `core.logger`, `core.policy_processor` לפי ה־`__all__` ב־`__init__.py`.
- **DB תמונות**: הלוגיקה ב־`image_status_db`; שינוי סכמה או שדות שם.
- **תמונות החלפה**: הלוגיקה ב־`image_replacement`; שינוי פורמט/גודל או הוספת placeholder חדש שם.
- **אנליזרים**: הוספת אנליזר חדש = מחלקה שיורשת מ־`ImageAnalyzer` ומממשת `analyze_image`.

---

## המלצות לוגיקה (לא יושמו)

1. **`state` ב־URLPolicyResolver**: כרגע ה־resolver מקבל policies בלי `state`. אם צד הלקוח (למשל CRM) צריך allow/block מה־resolver, כדאי להעביר `state` ב־`policy_loader` ל־`resolver_policies` ולוודא שה־resolver מחזיר rules שכוללים `state`.
2. **בחירת אנליזר**: ב־`image_status_manager` תמיד משתמשים ב־`SimulatedImageAnalyzer`. אם רוצים LLM ב־production, לשקול בחירה לפי env או config (למשל `USE_LLM_ANALYZER=1`).
3. **base64 ב־LLM analyzer**: ב־`analyze_image` יש TODO לטיפול במחרוזת base64; כרגע לא ממומש. להשלים אם נדרש קלט base64.
4. **תור אנליזת תמונות**: לשקול retries או exponential backoff ב־worker כש־`analyze_image` נכשל בשגיאות חולפות (רשת, מודל).
5. **חילוץ תמונות מ־HTML**: `extract_images_from_html` הוסר (לא היה בשימוש). אם בעתיד צריך לסרוק HTML ולהחיל פילטר על תמונות מקושרות, יש להחזיר פונקציונליות דומה (למשל מודול נפרד שמשתמש ב־BeautifulSoup או ב־parser אחר).
