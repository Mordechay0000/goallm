"""
"Send for review" button on top of every blocked video (like NetFree's button in the player).

The injected script finds candidate players (the YouTube player, <video> elements that failed or stalled while
playing) and asks the proxy – on the page's own origin, never forwarded to the site – whether they are blocked.
Only a confirmed block gets the overlay, so a slow or preload="none" video is never covered by mistake.
The button submits the video through the proxy, which already knows the user from the proxy credentials
(no CRM login, no new tab). The overlay then polls; once the video is approved, the page reloads.

Paths (answered by the proxy for any host, like the image-status path):
  POST /__goallm__/video-status  {"urls": [...], "page_url": "..."}
       → {"items": {url: {"blocked", "status", "reason"}}, "page_blocked": [{"url", "status", "reason"}]}
  POST /__goallm__/video-review  {"url": "...", "page_url": "..."} → {"status", "reason"} (rate-limited per user)

Built without innerHTML (YouTube enforces Trusted Types) inside a closed shadow root (site CSS cannot break it).
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from typing import Optional
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

VIDEO_STATUS_PATH = "/__goallm__/video-status"
VIDEO_REVIEW_PATH = "/__goallm__/video-review"
REVIEW_REQUESTS_PER_HOUR = 30
_RECENT_BLOCK_WINDOW_SEC = 15 * 60


def _origin(url: str) -> str:
    try:
        p = urlsplit(url or "")
        return f"{p.scheme}://{p.netloc}".lower() if p.scheme and p.netloc else ""
    except ValueError:
        return ""


def media_blocked_for_user(url: str, user_id: int) -> bool:
    """Would the proxy block this media URL for this user right now? (site rule, global switch, approval)"""
    from core.filters.video.video_filter import video_allowed_for_rule
    from core.policy.policy_cache import get_filter_switches, get_policy_resolver, is_media_approved

    from core.filters.video.video_filter import is_audio_response

    switches = get_filter_switches()
    switch = "audio_filter" if is_audio_response("", urlsplit(url).path) else "video_filter"
    try:
        rule = get_policy_resolver(user_id).resolve(url, "*") if switches.get("url_policy", True) else None
    except Exception:
        rule = None
    if video_allowed_for_rule(rule, switches.get(switch, True)):
        return False
    try:
        return not is_media_approved(url)
    except Exception:
        return True


def _review_info(url: str) -> dict:
    from core.policy.policy_database import canonical_media_key, get_video_review

    r = get_video_review(canonical_media_key(url))
    return {"status": r["status"] if r else None, "reason": (r or {}).get("reason")}


def video_status(payload: dict, user_id: int) -> dict:
    from core.policy.policy_database import list_recent_blocked_media

    urls = [u for u in (payload.get("urls") or []) if isinstance(u, str) and u.startswith(("http://", "https://"))][:50]
    items = {}
    for u in urls:
        blocked = media_blocked_for_user(u, user_id)
        items[u] = {"blocked": blocked, **(_review_info(u) if blocked else {"status": None, "reason": None})}
    page_blocked = []
    origin = _origin(payload.get("page_url") or "")
    if origin:
        now = time.time()
        for m in list_recent_blocked_media(user_id, limit=30):
            if now - (m.get("seen_at") or 0) > _RECENT_BLOCK_WINDOW_SEC:
                continue
            if _origin(m.get("page_url") or "") != origin:
                continue
            page_blocked.append({"url": m["media_url"], "status": m.get("review_status"),
                                 "reason": _review_info(m["media_url"]).get("reason")})
            if len(page_blocked) >= 5:
                break
    return {"items": items, "page_blocked": page_blocked}


class ReviewRateLimiter:
    def __init__(self, per_hour: int = REVIEW_REQUESTS_PER_HOUR) -> None:
        self.per_hour = per_hour
        self._lock = threading.Lock()
        self._hits: dict[int, deque] = {}

    def allow(self, user_id: int) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits.setdefault(user_id, deque())
            while q and now - q[0] > 3600:
                q.popleft()
            if len(q) >= self.per_hour:
                return False
            q.append(now)
            if len(self._hits) > 100000:
                self._hits.clear()
            return True


def request_review(payload: dict, user_id: int, limiter: ReviewRateLimiter) -> tuple[int, dict]:
    from core.policy.policy_database import request_video_review

    url = (payload.get("url") or "").strip()
    page_url = (payload.get("page_url") or "").strip() or None
    if not url.startswith(("http://", "https://")) or len(url) > 4000:
        return 400, {"error": "כתובת לא תקינה"}
    if not limiter.allow(user_id):
        return 429, {"error": "יותר מדי בקשות – נסו שוב מאוחר יותר"}
    r = request_video_review(url, page_url, user_id)
    logger.info("Video sent for review from the player overlay: %s (user_id=%s) → %s", url[:120], user_id, r.get("status"))
    return 200, {"status": r.get("status"), "reason": r.get("reason")}


# Readable here; json.dumps (ASCII escapes) keeps the injected script pure ASCII, so it survives any page charset.
TEXTS = {
    "title": "🚫 הסרטון חסום בסינון",
    "short": "🚫 חסום בסינון",
    "send": "שלח לבדיקה",
    "close": "✕",
    "none": "",
    "pending": "⏳ הסרטון בבדיקה…",
    "processing": "⏳ הסרטון בבדיקה…",
    "review": "⏳ ממתין לבודק",
    "blocked": "הסרטון נבדק ונמצא לא מתאים",
    "error": "הבדיקה נכשלה",
    "allowed": "✅ הסרטון אושר – טוען מחדש…",
    "failed": "שגיאה בשליחה",
}

OVERLAY_SCRIPT = """<script>(function(){
if(window.__goallmVideoOverlay)return;window.__goallmVideoOverlay=1;
var SP=%(status)s,RP=%(review)s,boxes=[],lastQuery='',lastAt=0;
var TXT=%(texts)s;
function post(p,body){return fetch(p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),credentials:'omit'}).then(function(r){return r.json().catch(function(){return {};}).then(function(j){j.__code=r.status;return j;});});}
function ytId(){var m=location.pathname.match(/^\\/(?:shorts|embed|live)\\/([A-Za-z0-9_-]{11})/);if(m)return m[1];if(location.pathname==='/watch'){var v=new URLSearchParams(location.search).get('v');if(v&&/^[A-Za-z0-9_-]{11}$/.test(v))return v;}return null;}
function isYt(){return /(^|\\.)(youtube\\.com|youtube-nocookie\\.com)$/.test(location.hostname);}
function srcOf(v){var s=v.currentSrc||v.src||'';if(!s){var e=v.querySelector('source[src]');if(e)s=e.src;}return s;}
function candidates(){
 var yt=isYt(),out=[],id=yt?ytId():null,pl=null;
 if(id){pl=document.querySelector('#movie_player')||document.querySelector('.html5-video-player')||document.querySelector('#shorts-player');if(pl&&pl.getBoundingClientRect().width>40)out.push({el:pl,url:'https://www.youtube.com/watch?v='+id});}
 [].forEach.call(document.querySelectorAll('video,audio'),function(v){
  if(pl&&pl.contains(v))return;
  if(!v.__gSeen)v.__gSeen=Date.now();
  var r=v.getBoundingClientRect(),au=v.tagName==='AUDIO';if(r.width<(au?120:80)||r.height<(au?20:45))return;
  var failed=!!v.error||v.networkState===3;
  var stalled=v.readyState===0&&(!v.paused||v.autoplay)&&Date.now()-v.__gSeen>5000;
  if(!failed&&!stalled)return;
  var s=srcOf(v),u=(s&&s.indexOf('blob:')!==0&&/^https?:/.test(s))?s:null;
  if(!u&&yt)return; // YouTube: only the identified player; a preview must never send a different video
  out.push({el:v,url:u});
 });
 return out;
}
function place(b){var r=b.el.getBoundingClientRect();var s=b.host.style;if(!b.el.isConnected||r.width<40){s.display='none';return;}s.display='block';s.left=r.left+'px';s.top=r.top+'px';s.width=r.width+'px';s.height=r.height+'px';}
function el(tag,css,text){var e=document.createElement(tag);if(css)e.setAttribute('style',css);if(text)e.textContent=text;return e;}
function make(c){
 var host=el('div','position:fixed;z-index:2147483646;display:none;pointer-events:none;');
 var root=host.attachShadow?host.attachShadow({mode:'closed'}):host;
 var small=c.el.getBoundingClientRect().height<110;
 var card=el('div','pointer-events:auto;position:absolute;inset:0;display:flex;flex-direction:'+(small?'row':'column')+';align-items:center;justify-content:center;gap:'+(small?'8px':'10px')+';background:rgba(18,18,18,.97);color:#fff;font:'+(small?'13px':'15px')+'/1.3 Arial,sans-serif;direction:rtl;text-align:center;padding:'+(small?'2px 28px 2px 6px':'12px')+';box-sizing:border-box;border-radius:4px;overflow:hidden;');
 var title=el('div','font-size:'+(small?'13px':'17px')+';font-weight:bold;white-space:nowrap;',small?TXT.short:TXT.title);
 var line=el('div','font-size:'+(small?'12px':'14px')+';opacity:.9;max-width:90%%;'+(small?'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;':''));
 var btn=el('button','cursor:pointer;background:#2e7d32;color:#fff;border:0;border-radius:6px;padding:'+(small?'3px 10px':'9px 18px')+';font:bold '+(small?'13px':'15px')+' Arial,sans-serif;white-space:nowrap;',TXT.send);
 var close=el('button','position:absolute;top:'+(small?'50%%;transform:translateY(-50%%)':'6px')+';left:8px;cursor:pointer;background:transparent;color:#fff;border:0;font:'+(small?'14px':'18px')+' Arial,sans-serif;opacity:.7;',TXT.close);
 card.appendChild(close);card.appendChild(title);card.appendChild(line);card.appendChild(btn);root.appendChild(card);
 (document.body||document.documentElement).appendChild(host);
 var b={el:c.el,url:c.url,host:host,line:line,btn:btn,status:null,closed:false,poll:null};
 btn.addEventListener('click',function(ev){ev.preventDefault();ev.stopPropagation();if(!b.url)return;btn.disabled=true;
  post(RP,{url:b.url,page_url:location.href}).then(function(j){btn.disabled=false;if(j.__code!==200){line.textContent=j.error||TXT.failed;return;}show(b,j.status,j.reason);}).catch(function(){btn.disabled=false;line.textContent=TXT.failed;});});
 close.addEventListener('click',function(ev){ev.preventDefault();ev.stopPropagation();b.closed=true;host.remove();});
 boxes.push(b);place(b);return b;
}
function show(b,status,reason){
 b.status=status||null;
 if(status==='allowed'){b.line.textContent=TXT.allowed;b.btn.style.display='none';setTimeout(function(){location.reload();},1200);return;}
 var t=TXT[status||'none']||'';if(status==='error'&&reason)t+=': '+reason;
 b.line.textContent=t;
 b.btn.style.display=(!status||status==='error')&&b.url?'inline-block':'none';
 if((status==='pending'||status==='processing'||status==='review')&&!b.poll){b.poll=setInterval(function(){
  post(SP,{urls:[b.url],page_url:location.href}).then(function(j){var it=(j.items||{})[b.url];if(!it)return;if(!it.blocked){clearInterval(b.poll);show(b,'allowed');}else if(it.status!==b.status)show(b,it.status,it.reason);});
 },10000);}
}
function find(elm){for(var i=0;i<boxes.length;i++)if(boxes[i].el===elm)return boxes[i];return null;}
function tick(){
 boxes=boxes.filter(function(b){if(b.closed)return false;if(!b.el.isConnected){b.host.remove();if(b.poll)clearInterval(b.poll);return false;}return true;});
 var cs=candidates(),fresh=cs.filter(function(c){var b=find(c.el);if(b&&b.url!==c.url&&c.url){b.host.remove();if(b.poll)clearInterval(b.poll);boxes.splice(boxes.indexOf(b),1);return true;}return !b;});
 boxes.forEach(place);
 if(!fresh.length)return;
 var urls=fresh.map(function(c){return c.url;}).filter(Boolean),q=JSON.stringify(urls)+fresh.length;
 if(q===lastQuery&&Date.now()-lastAt<15000)return;lastQuery=q;lastAt=Date.now();
 post(SP,{urls:urls,page_url:location.href}).then(function(j){
  var items=j.items||{},pb=j.page_blocked||[];
  fresh.forEach(function(c){
   if(find(c.el))return;
   if(c.url){var it=items[c.url];if(it&&it.blocked){var b=make(c);show(b,it.status,it.reason);}}
   else if(pb.length){c.url=pb[0].url;var b2=make(c);show(b2,pb[0].status,pb[0].reason);}
  });
 }).catch(function(){});
}
setInterval(tick,2000);window.addEventListener('scroll',function(){boxes.forEach(place);},true);window.addEventListener('resize',function(){boxes.forEach(place);});
document.addEventListener('error',function(e){if(e.target&&e.target.tagName==='VIDEO')setTimeout(tick,300);},true);
setTimeout(tick,1200);
})();</script>""" % {"status": json.dumps(VIDEO_STATUS_PATH), "review": json.dumps(VIDEO_REVIEW_PATH), "texts": json.dumps(TEXTS)}


def parse_payload(raw: Optional[str]) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}
