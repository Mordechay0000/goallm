// image-monitor.js (Client-side script)
(async function() {
    // נסה לקחת את כתובת ה-WS מהמשתנה הגלובלי שהוגדר על ידי mitmproxy
    let WS_URL = typeof WS_URL_FROM_PROXY !== 'undefined' ? WS_URL_FROM_PROXY : "wss://127.0.0.1:8081"; // Fallback

    // ודא שיש Socket.IO זמין
    if (typeof io === 'undefined') {
        console.error("Socket.IO client library (io) not found. Make sure it's loaded before this script.");
        return;
    }

    const socket = io(WS_URL);
    const imageUrls = {}; // המילון שמכיל url -> [img_elements]

    console.log("Image monitor script running. Connecting to WS:", WS_URL);

    socket.on('connect', () => { console.log('WS Connected:', socket.id); });
    socket.on('connect_error', (err) => { console.error('WS Connection Error:', err); });
    socket.on('disconnect', (reason) => { console.log('WS Disconnected:', reason); });

    // --- הוסרה פונקציית fetchHash ---

    // --- פונקציה מעודכנת לרישום תמונות לפי URL ---
    function registerImageByUrl(img) {
        // הדפס את אלמנט התמונה שמעבדים
        // console.log(`>>> registerImageByUrl: Processing img element:`, img);
        // השתמש ב-img.src שהדפדפן כבר פתר לכתובת מלאה
        const url = img.src;

        if (!url) {
            console.warn(`>>> registerImageByUrl: Image has no src attribute, skipping registration:`, img);
            return;
        }

        // אתחל מערך אם זו הכתובת הראשונה, ואז הוסף את האלמנט
        imageUrls[url] = imageUrls[url] || [];

        // מנע הוספה כפולה של אותו אלמנט לאותו URL
        if (!imageUrls[url].includes(img)) {
            imageUrls[url].push(img);
            // console.log(`>>> registerImageByUrl: Registered img for URL ${url}. Total imgs for this URL: ${imageUrls[url].length}`);
        } else {
            // console.log(`>>> registerImageByUrl: Img element already registered for URL ${url}.`);
        }
    }

    // --- פונקציה לסריקת תמונות חדשות ---
    function scanImages() {
        console.log(">>> scanImages: Scanning for new images...");
        // !!! שימוש ב-data-monitored במקום data-hashed !!!
        document.querySelectorAll('img:not([data-monitored="true"])').forEach(img => {
             // ודא שלתמונה יש src לפני שמנסים לעבד
            if (img.src) {
                // סמן את התמונה כדי שלא נסרוק אותה שוב
                img.setAttribute('data-monitored', 'true');
                // קרא לרישום התמונה לפי URL (בלי hash)
                registerImageByUrl(img);
            } else if (!img.hasAttribute('data-monitored')) {
                // אם אין src ועדיין לא סומנה, סמן אותה כדי לא לבדוק שוב ושוב
                 img.setAttribute('data-monitored', 'true');
                 console.log(">>> scanImages: Found img without src, marked as monitored to prevent re-scanning:", img);
            }
        });
        console.log(">>> scanImages: Scan finished.");
    }

    // --- Handler for WebSocket messages (using URL) ---
    socket.on('image_update', async function(data) {
        console.log('>>> WS image_update received:', data);
        const updatedUrlFromServer = data.image_url;
        const statusFromServer = data.status; // "allowed" or "blocked"

        if (!updatedUrlFromServer) {
            console.error(">>> WS image_update: Received event without 'image_url'. Data:", data);
            return;
        }

        // חפש במילון את התמונות עם ה-URL שהתקבל
        const imgsToReload = imageUrls[updatedUrlFromServer] || [];
        console.log(`>>> WS image_update: Found ${imgsToReload.length} images in dictionary for URL ${updatedUrlFromServer}`);

        if (imgsToReload.length > 0) {
           console.log(`>>> WS image_update: Reloading ${imgsToReload.length} images for URL ${updatedUrlFromServer}`);
           imgsToReload.forEach(img => {
               // רק רענן את ה-src. הדפדפן יבקש את התמונה מחדש.
               // Mitmproxy יראה את הבקשה החדשה ויחזיר את התמונה המקורית (אם allowed)
               // או פלייסהולדר חדש (אם עדיין blocked, למרות שזה פחות סביר בתרחיש רגיל).
               try {
                   const currentSrc = img.src;
                   // טכניקה פשוטה לרענון: הוספת פרמטר query משתנה
                   const url = new URL(currentSrc); // Use currentSrc to handle potential previous reloads
                   url.searchParams.set('force_reload', Date.now()); // פרמטר למניעת מטמון
                   console.log(`>>> WS image_update: Reloading image src from: ${currentSrc} to ${url.toString()}`);
                   img.src = url.toString();
               } catch (e) {
                   // יכול לקרות אם ה-src המקורי לא היה URL תקין, למרות שבדרך כלל יהיה
                   console.error(">>> WS image_update: Error creating URL or setting src during reload for", img, e);
                   // אפשר לנסות רענון פשוט יותר במקרה של שגיאה
                   // img.src = img.src + (img.src.includes('?') ? '&' : '?') + 'force_reload=' + Date.now();
               }
           });
           // אפשר לנקות את הרישום של ה-URL הזה מהמילון אחרי הרענון אם רוצים,
           // או להשאיר אותו למקרה שיש עדכונים נוספים (פחות סביר)
           // delete imageUrls[updatedUrlFromServer];
        } else {
             console.warn(`>>> WS image_update: No images found in dictionary to reload for URL ${updatedUrlFromServer}`);
        }
    });
    // ------------------------------------

    // הרץ סריקה ראשונית כשה-DOM מוכן (או קצת אחרי)
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', scanImages);
    } else {
        // DOM כבר נטען
        scanImages();
    }

    // הגדר את ה-MutationObserver להפעלת scanImages כשנוספים אלמנטים לדף
    // ודא ש-document.body קיים לפני שמפעילים את ה-Observer
    const observerCallback = (mutationsList, observer) => {
        for(const mutation of mutationsList) {
            if (mutation.type === 'childList') {
                // מספיק לקרוא ל-scanImages פעם אחת לכל קבוצת שינויים
                 scanImages();
                 return; // צא אחרי ריצה אחת
            }
        }
    };

    const observer = new MutationObserver(observerCallback);

    // הפעלת ה-Observer רק אחרי שה-body נוצר בוודאות
    const startObserver = () => {
        if (document.body) {
            observer.observe(document.body, { childList: true, subtree: true });
            console.log("MutationObserver started on document.body.");
        } else {
             // אם ה-body עדיין לא קיים, נסה שוב עוד רגע
            console.log("Document.body not ready yet, delaying MutationObserver start.");
            setTimeout(startObserver, 100);
        }
    };

    startObserver();


    console.log("Image monitor initial scan requested and observer setup initiated.");

})();