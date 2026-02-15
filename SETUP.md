# הרצת הפרויקט מאפס (אחרי git clone)

מדריך מפורט להפעלת goallm אחרי clone טרי. מסדי הנתונים נוצרים אוטומטית בפעם הראשונה.

---

## 1. דרישות מקדימות

| כלי | גרסה מינימלית | הערות |
|-----|----------------|-------|
| Python | 3.10+ | `python3 --version` |
| Node.js | 18+ | לממשק CRM |
| npm | מגיע עם Node | `npm --version` |

### התקנת Node.js (אם חסר)

**macOS (Homebrew):**
```bash
brew install node
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install nodejs npm
```

**Windows:** הורד מ־https://nodejs.org/

---

## 2. התקנה מהירה (אחרי clone)

```bash
git clone <repo-url> goallm
cd goallm
bash setup.sh
```

הסקריפט `setup.sh` יוצר venv, מתקין את כל תלויות Python ו־npm. אחרי שזה מסתיים, הרץ בשלושה טרמינלים:

| טרמינל | פקודה |
|--------|-------|
| 1 (פרוקסי) | `cd goallm && bash core/proxy/run_proxy.sh` |
| 2 (Backend) | `cd goallm/crm && bash run_fastapi.sh` |
| 3 (Frontend) | `cd goallm/crm/frontend && bash run_dev.sh` |

> `run_fastapi.sh` מפעיל אוטומטית את ה־venv. `run_dev.sh` מריץ `npm install` אוטומטית אם `node_modules` חסר.

---

## 3. התקנה ידנית

```bash
git clone <repo-url> goallm
cd goallm

# Python
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd crm/frontend && npm install && cd ../..
```

**הרצה (3 טרמינלים):**

| טרמינל | פקודה |
|--------|-------|
| 1 | `cd goallm && bash core/proxy/run_proxy.sh` |
| 2 | `cd goallm/crm && bash run_fastapi.sh` |
| 3 | `cd goallm/crm/frontend && bash run_dev.sh` |

---

## 4. פירוט שלבים

### 4.1 הרצת setup.sh

לאחר clone, הרץ משורש הפרויקט:

```bash
cd goallm
bash setup.sh
```

הסקריפט יוצר venv, מתקין תלויות Python ו־npm.

### 4.2 הרצת הפרוקסי

**חשוב:** מריצים **משורש הפרויקט** (`goallm/`). הפרוקסי דורש אימות (ברירת מחדל: `filter` / `f123456Ab`).

```bash
cd /path/to/goallm
bash core/proxy/run_proxy.sh
```

אלטרנטיבות:
- `bash core/proxy/run_proxy.sh mitmweb` – ממשק ווב
- `bash core/proxy/run_proxy.sh mitmdump` – לוג בלבד

בהגדרת הפרוקסי בדפדפן – הזינו את שם המשתמש והסיסמה כשמופיעה בקשת אימות.

### 4.3 הרצת Backend CRM

```bash
cd /path/to/goallm/crm
bash run_fastapi.sh
```

הסקריפט מפעיל אוטומטית את ה־venv. אם מופיעה שגיאת `uvicorn not found`, הרץ קודם `bash setup.sh` משורש הפרויקט.

### 4.4 הרצת Frontend CRM

```bash
cd /path/to/goallm/crm/frontend
bash run_dev.sh
```

הסקריפט מריץ `npm install` אוטומטית אם `node_modules` חסר. אם מופיעה שגיאת `vite not found`, ודא ש־Node.js מותקן ורשת `npm install` ידנית.

---

## 5. מסדי נתונים (אוטומטי)

הפרויקט משתמש ב־3 מסדי SQLite בתיקיית `.storage/` (נוצרת אוטומטית):

| קובץ | ייעוד | מתי נוצר |
|------|-------|----------|
| `crm.db` | משתמשים, פרופילים, חוקים | בהפעלת Backend CRM |
| `policies.db` | חוקי URL ל־core | בהפעלת Backend (sync מהמשתמשים) |
| `image_status.db` | סטטוס תמונות | בהפעלת הפרוקסי (בפעם הראשונה שמעבירים תמונה) |

**אין צורך ביצירה ידנית** – הכל נוצר ומוגדר אוטומטית.

---

## 6. כתובות שירותים

| שירות | כתובת (מהמכונה) | כתובת מרשת (ממחשב אחר) |
|-------|------------------|--------------------------|
| פרוקסי | http://127.0.0.1:8080 | http://\<IP-המכונה\>:8080 |
| Backend API | http://127.0.0.1:8000 | http://\<IP\>:8000 |
| ממשק CRM | http://localhost:5173 | http://\<IP\>:5173 |

Backend ו־Frontend מאזינים על `0.0.0.0` – נגישים ממחשבים אחרים ברשת.

---

## 7. HTTPS

בפעם הראשונה גלוש ל־https://mitm.it והתקן את תעודת ה־CA של mitmproxy לפי ההנחיות.

---

## 8. הרצה על שרת (SSH)

אותם פקודות. ודא ש־Python 3.10+ ו־Node.js מותקנים:

```bash
# Ubuntu
sudo apt update
sudo apt install python3 python3-venv python3-pip nodejs npm
```

אחרי clone והתקנה:

```bash
cd ~/goallm
bash setup.sh
# טרמינל 2:
cd ~/goallm/crm && bash run_fastapi.sh
# טרמינל 3:
cd ~/goallm/crm/frontend && bash run_dev.sh
```

---

## 9. פתרון בעיות

**"uvicorn: command not found"**  
הרץ `bash setup.sh` משורש הפרויקט, או ידנית:
```bash
cd goallm && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

**"vite: not found"**  
ודא ש־Node.js מותקן. הרץ `bash run_dev.sh` (מריץ npm install אוטומטית) או ידנית:
```bash
cd goallm/crm/frontend && npm install
```

**"command not found: mitmproxy"**  
ודא ש־venv מופעל ורצת `pip install -r requirements.txt`. הפעל את הפרוקסי משורש הפרויקט.

**"Port already in use"**  
בדוק מי תופס את הפורט:
```bash
lsof -i :8080   # פרוקסי
lsof -i :8000   # Backend
lsof -i :5173   # Frontend
```

**"ModuleNotFoundError"**  
ודא שמריצים את Backend עם `run_fastapi.sh` (מגדיר PYTHONPATH נכון).

**"unable to open database file"**  
בעיית הרשאות על תיקיית `.storage`. נסה:
```bash
mkdir -p ~/goallm/.storage
chmod 755 ~/goallm/.storage
chown -R $USER:$USER ~/goallm/.storage
```
או ציין נתיב ידני:
```bash
export GOALLM_STORAGE_DIR="$HOME/.goallm/storage"
cd crm && bash run_fastapi.sh
```
