"""
Reload images that were served as "checking" placeholders once their analysis is done.

Flow: the injected script POSTs the page's image URLs to /__goallm__/image-status on the page's own
origin (the proxy answers it – the request never reaches the website). For every URL that is ready it
reloads the <img> with an extra "goallm_r" query parameter (so the browser cannot reuse the cached
placeholder); the proxy strips that parameter before forwarding, so signed URLs keep working.
"""
from __future__ import annotations

import json
import re

STATUS_PATH = "/__goallm__/image-status"
RELOAD_PARAM = "goallm_r"

REFRESH_SCRIPT = """<script>(function(){
var P=%(path)s,R=%(param)s,tries=0,MAX=40;
var RX=new RegExp('([?&])'+R+'=[0-9]+(&|$)');
function strip(u){try{var h=new URL(u,location.href).href;return h.replace(RX,function(m,a,b){return a==='?'?(b?'?':''):b;});}catch(e){return null;}}
function bust(u){var i=u.indexOf('#'),base=i>=0?u.slice(0,i):u,frag=i>=0?u.slice(i):'';return base+(base.indexOf('?')>=0?'&':'?')+R+'='+Date.now()+frag;}
function tick(){
 tries++; if(tries>MAX)return;
 var imgs=[].slice.call(document.images||[]),map={},urls=[];
 imgs.forEach(function(im){var s=im.currentSrc||im.src;if(!s||s.indexOf('data:')===0)return;var k=strip(s);if(!k)return;(map[k]=map[k]||[]).push(im);});
 urls=Object.keys(map).slice(0,300); if(!urls.length){setTimeout(tick,3000);return;}
 fetch(P,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({urls:urls}),credentials:'omit'})
 .then(function(r){return r.ok?r.json():{};}).then(function(st){
   var pending=false;
   Object.keys(st||{}).forEach(function(u){
     if(st[u]==='pending'){pending=true;return;}
     (map[u]||[]).forEach(function(im){try{if(im.srcset)im.removeAttribute('srcset');im.src=bust(u);}catch(e){}});
   });
   setTimeout(tick,pending?2500:5000);
 }).catch(function(){setTimeout(tick,5000);});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',function(){setTimeout(tick,1500);});else setTimeout(tick,1500);
})();</script>""" % {"path": json.dumps(STATUS_PATH), "param": json.dumps(RELOAD_PARAM)}


_RELOAD_RE = re.compile(r"([?&])" + RELOAD_PARAM + r"=\d+(&|$)")


def strip_reload_param(url: str) -> str:
    """Remove the parameter textually (re-encoding the query could break signed URLs)."""
    def _sub(m: re.Match) -> str:
        sep, tail = m.group(1), m.group(2)
        if sep == "?":
            return "?" if tail else ""
        return tail
    return _RELOAD_RE.sub(_sub, url, count=1)


def strip_reload_param_from_request(flow) -> None:
    """Remove the cache-busting parameter before the request goes upstream (and before policy checks)."""
    path = flow.request.path or ""
    if RELOAD_PARAM + "=" not in path:
        return
    flow.request.path = strip_reload_param(path)
