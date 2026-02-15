# הפעלת הפרוקסי (mitmproxy)

מריצים **מתוך שורש הפרויקט** (`goallm/`), אחרי `bash setup.sh` או התקנה ידנית.

**אימות פרוקסי:** גלישה דרך הפרוקסי דורשת שם משתמש וסיסמה. ברירת מחדל: `filter` / `f123456Ab`.

## הפעלה מומלצת (עם אימות)

```bash
cd /path/to/goallm
bash core/proxy/run_proxy.sh
```

או: `bash core/proxy/run_proxy.sh mitmweb` | `bash core/proxy/run_proxy.sh mitmdump`

## אופציות הפעלה (ידנית)

### 1. mitmproxy (ממשק אינטראקטיבי בטרמינל)
```bash
mitmproxy -s core/proxy/mitmproxy_addon.py --set proxyauth=filter:f123456Ab
```
ברירת מחדל: `http://127.0.0.1:8080`. הגדירו בדפדפן/מערכת את הפרוקסי ל־`127.0.0.1:8080`.

### 2. mitmweb (ממשק ווב)
```bash
mitmweb -s core/proxy/mitmproxy_addon.py --set proxyauth=filter:f123456Ab
```
פותח דפדפן עם ממשק לצפייה ב־flows. הפרוקסי על פורט 8080.

### 3. mitmdump (ללא ממשק, לוג בלבד)
```bash
mitmdump -s core/proxy/mitmproxy_addon.py --set proxyauth=filter:f123456Ab
```

## פורט אחר
```bash
mitmproxy -s core/proxy/mitmproxy_addon.py --set proxyauth=filter:f123456Ab -p 8888
```

## שימוש
1. הפעילו את mitmproxy כאחד מהפקודות למעלה.
2. בדפדפן או במערכת ההפעלה הגדירו HTTP/HTTPS proxy ל־`127.0.0.1:8080` (או לפורט שבחרתם).
3. כשמופיעה בקשת אימות – הזינו שם משתמש `filter` וסיסמה `f123456Ab`.
4. גלשו לאתרים – התמונות יעברו דרך האדון (סינון/החלפה לפי policy ו־image status).

**שינוי פרטי אימות:** `PROXY_AUTH=user:pass ./run_proxy.sh` או `--set proxyauth=user:pass` בפקודה ידנית.  
**ביטול אימות:** `PROXY_AUTH= ./run_proxy.sh` או השמטת `--set proxyauth`.

**HTTPS:** mitmproxy יציג תעודת CA. בפעם הראשונה גלשו ל־`mitm.it` והתקינו את התעודה לפי ההנחיות.
