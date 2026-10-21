# קנה מידה – כמה תהליכי פרוקסי ובודק סרטונים

## למה צריך יותר מתהליך אחד

`mitmdump` מעבד את כל החיבורים ב-event loop אחד עם GIL אחד, כך שתהליך אחד מנצל בערך ליבה אחת.
העבודה הכבדה (HTML, hash של תמונות, PDF) כבר רצה ב-threads, אבל פענוח TLS ו-HTTP/2 נשאר בתהליך הראשי.
כשיש יותר מכמה עשרות בתים גולשים בו-זמנית, מריצים כמה תהליכים מאחורי load balancer של **TCP**.

## הפעלה

```bash
bash core/proxy/run_cluster.sh start 4 8081   # 4 תהליכים: 127.0.0.1:8081-8084
bash core/proxy/run_cluster.sh status
bash core/proxy/run_cluster.sh stop
```

לוגים ו-PID: `.storage/run/mitm-<i>.log`. לפני העלייה: אותם משתנים כמו בתהליך יחיד (`IMAGE_ANALYZER=openai`, `VLM_API_BASE` ושאר המשתנים ב-`.env.example`).

## Load balancer

### nginx (`stream`, לא `http`)

```nginx
stream {
    upstream goallm_proxy {
        hash $remote_addr consistent;   # אותו בית → אותו תהליך (מטמון הזיכרון של התהליך עובד טוב יותר)
        server 127.0.0.1:8081;
        server 127.0.0.1:8082;
        server 127.0.0.1:8083;
        server 127.0.0.1:8084;
    }
    server {
        listen 8080;
        proxy_pass goallm_proxy;
        proxy_timeout 1h;               # חיבורי CONNECT ו-WebSocket ארוכים
    }
}
```

### HAProxy

```haproxy
frontend goallm_in
    mode tcp
    bind :8080
    timeout client 1h
    default_backend goallm_workers

backend goallm_workers
    mode tcp
    balance source
    timeout server 1h
    server w1 127.0.0.1:8081 check
    server w2 127.0.0.1:8082 check
    server w3 127.0.0.1:8083 check
    server w4 127.0.0.1:8084 check
```

## מה חשוב לדעת

| נושא | מה קורה | מה עושים |
| --- | --- | --- |
| **זהות** | מאחורי balancer של TCP הפרוקסי רואה את כתובת ה-balancer. ל-HTTPS אין `X-Forwarded-For`. | רק **פרטי התחברות אישיים**. הסקריפט מסרב לעלות עם `PROXY_REQUIRE_AUTH=0` או עם `PROXY_AUTH`, ומריץ את התהליכים עם `TRUSTED_PROXY_IPS=none`. אחרת לקוח היה יכול לזייף `X-Forwarded-For` בבקשת HTTP רגילה. |
| **תעודת CA** | כל התהליכים חייבים אותה תעודה, אחרת חלק מהאתרים ייראו "לא מאובטחים". | `confdir` משותף (`MITM_CONFDIR`, ברירת מחדל `~/.mitmproxy`). אם אין עדיין CA, הסקריפט מעלה תהליך אחד, מחכה שייצור אותה, ורק אז מעלה את השאר. |
| **מסד נתונים** | SQLite במצב WAL: כמה תהליכים **על אותה מכונה** – תקין. | |
| **יותר ממכונה אחת** | SQLite על NFS = השחתת נתונים. | **לא מומש:** מעבר ל-Postgres. עד אז – מכונה אחת חזקה (הרבה ליבות) + שרת GPU נפרד. |
| **תור תמונות** | לכל תהליך תור משלו בזיכרון. תמונה חדשה שמגיעה בו-זמנית לשני תהליכים תיבדק פעמיים (נדיר; התוצאה נשמרת לפי hash). | עומס על ה-VLM: N × `IMAGE_MAX_WORKERS` בקשות במקביל. להתאים ל-GPU. |
| **מטמון מדיניות** | בזיכרון של כל תהליך. מתרענן תוך שנייה מכל שינוי (`policy_version` במסד). | |

## בודק הסרטונים

```bash
python -m core.filters.video.review_worker
```

- דורש `ffmpeg` ו-`ffprobe` (`apt install ffmpeg`) ואותם משתני `IMAGE_ANALYZER` / `VLM_*` כמו הפרוקסי.
- אפשר להריץ כמה עותקים: כל אחד "תופס" סרטון בטרנזקציה (`UPDATE … RETURNING`), כך ששני עותקים לא בודקים אותו סרטון.
- סרטון שנתקע ב-`processing` (תהליך שנפל) חוזר לתור אחרי שעה.
- הגדרות: `VIDEO_FPS` (ברירת מחדל 1; 2 לסרטונים מהירים), `VIDEO_FORCE_ANALYZE_SEC` (בדיקה כפויה גם בלי שינוי, ברירת מחדל 15), `VIDEO_MAX_DURATION_SEC`, וספי זיהוי השינוי `VIDEO_CHANGE_*` (ב-`.env.example`).
- systemd: יחידה אחת לבודק (`Restart=always`), ויחידה ל-`run_cluster.sh start` (`Type=forking`) או יחידת template `mitm@.service` לכל פורט.
