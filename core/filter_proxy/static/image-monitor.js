// image-monitor.js
(function () {
    "use strict";

    const WS_URL = "wss://127.0.0.1:8081/ws";

    console.log("[image-monitor] starting, WS:", WS_URL);

    /* -------------------------
       URL normalization
       ------------------------- */
    function normalizeUrl(raw) {
        try {
            const u = new URL(raw, location.href);
            return u.origin + u.pathname; // canonical form
        } catch {
            return null;
        }
    }

    /* -------------------------
       Storage (no memory leaks)
       ------------------------- */
    const urlToImages = new Map(); // normalizedUrl -> Set<img>

    function registerImage(img) {
        const src =
            img.currentSrc ||
            img.src ||
            img.getAttribute("data-src");

        if (!src) return;

        const key = normalizeUrl(src);
        if (!key) return;

        let set = urlToImages.get(key);
        if (!set) {
            set = new Set();
            urlToImages.set(key, set);
        }

        set.add(img);
    }

    /* -------------------------
       Scan logic
       ------------------------- */
    function scanImages() {
        document.querySelectorAll("img").forEach(img => {
            if (img.dataset.monitored === "true") return;

            img.dataset.monitored = "true";
            registerImage(img);

            // handle lazy-load updates
            img.addEventListener(
                "load",
                () => registerImage(img),
                { once: false }
            );
        });
    }

    /* -------------------------
       Reload logic
       ------------------------- */
    function reloadImage(img) {
        try {
            const u = new URL(img.currentSrc || img.src, location.href);
            u.searchParams.set("_reload", Date.now());
            img.src = u.toString();
        } catch {
            // fallback
            img.src = img.src + (img.src.includes("?") ? "&" : "?") + "_reload=" + Date.now();
        }
    }

    function reloadByUrl(normalizedUrl) {
        const set = urlToImages.get(normalizedUrl);
        if (!set || set.size === 0) return;

        for (const img of set) {
            reloadImage(img);
        }
    }

    /* -------------------------
       WebSocket
       ------------------------- */
    let ws;

    function connectWS() {
        ws = new WebSocket(WS_URL);

        ws.onopen = () => {
            console.log("[image-monitor] WS connected");
        };

        ws.onmessage = evt => {
            let data;
            try {
                data = JSON.parse(evt.data);
            } catch {
                return;
            }

            if (!data.image_url) return;

            const key = normalizeUrl(data.image_url);
            if (!key) return;

            reloadByUrl(key);
        };

        ws.onclose = () => {
            console.warn("[image-monitor] WS closed, retrying…");
            setTimeout(connectWS, 2000);
        };

        ws.onerror = () => {
            ws.close();
        };
    }

    /* -------------------------
       DOM readiness
       ------------------------- */
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", scanImages);
    } else {
        scanImages();
    }

    const observer = new MutationObserver(scanImages);
    observer.observe(document.documentElement, {
        childList: true,
        subtree: true
    });

    connectWS();

})();
