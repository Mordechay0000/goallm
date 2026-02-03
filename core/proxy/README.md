# הפעלת הפרוקסי (mitmproxy)

מריצים **מתוך שורש הפרויקט** (`goallm/`), אחרי `bash setup.sh` או התקנה ידנית:

```bash
cd /path/to/goallm
source venv/bin/activate
mitmproxy -s core/proxy/mitmproxy_addon.py
```

## אופציות הפעלה

### 1. mitmproxy (ממשק אינטראקטיבי בטרמינל)
```bash
mitmproxy -s core/proxy/mitmproxy_addon.py
```
ברירת מחדל: `http://127.0.0.1:8080`. הגדירו בדפדפן/מערכת את הפרוקסי ל־`127.0.0.1:8080`.

### 2. mitmweb (ממשק ווב)
```bash
mitmweb -s core/proxy/mitmproxy_addon.py
```
פותח דפדפן עם ממשק לצפייה ב־flows. הפרוקסי על פורט 8080.

### 3. mitmdump (ללא ממשק, לוג בלבד)
```bash
mitmdump -s core/proxy/mitmproxy_addon.py
```

## פורט אחר
```bash
mitmproxy -s core/proxy/mitmproxy_addon.py -p 8888
```

## שימוש
1. הפעילו את mitmproxy כאחד מהפקודות למעלה.
2. בדפדפן או במערכת ההפעלה הגדירו HTTP/HTTPS proxy ל־`127.0.0.1:8080` (או לפורט שבחרתם).
3. גלשו לאתרים – התמונות יעברו דרך האדון (סינון/החלפה לפי policy ו־image status).

**HTTPS:** mitmproxy יציג תעודת CA. בפעם הראשונה גלשו ל־`mitm.it` והתקינו את התעודה לפי ההנחיות.
