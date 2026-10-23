"""
סינון מלל (text filtering) – סינון לחרדים, בלי מודל שפה.

שתי רמות של מילים:
- מילים קשות (word_lists/*/blocked.txt): מוחלפות ב-XXX בכל הקשר (כולל להט"ב), ומשקלן לפחות כפול מכל מילה חשודה.
- מילים חשודות (word_lists/*/scored.txt): לא מוסתרות – ניקוד נסתר שמצטבר (ליבידו, עירום, "בגד ים"…).
ההחלטה (scoring.py) היא כלל צפיפות אחד בכל רמה, מהקטן לגדול:
- משפט חם → המשפט כולו הופך ל-X (כותרת עם מילה קשה אחת כבר חמה – כותרות שוקלות פי 1.5).
- רכיב חם (כותרת, תוצאת חיפוש, כרטיס כתבה, תגובה, פסקה, רשימת קישורים) → הרכיב כולו הופך ל-X.
- קטע חם (מילים בעייתיות קרובות זו לזו, גם כשהן חוצות כמה פסקאות) → הקטע הופך ל-X, גם כשהדף כולו נקי.
- הדף נחסם רק לפי יחס: מה שנשאר בו עדיין צפוף, או שרובו כבר הפך ל-X. כמה תוצאות או כתבות בעייתיות
  בדף חיפוש / דף בית לא חוסמות את הדף – רק הופכות ל-X.
התאמה (lexicon.py): עברית – המילה ונטיותיה + אותיות שימוש; אנגלית – stemming; ביטויים; עקיפות (s.e.x, תווים נסתרים).
בדיקת רשימות מול טקסט מותר: python -m tools.check_word_list <קבצים>.
"""
import base64
import json
import logging
import re
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlsplit

from core.filters.text.lexicon import HARD, MARKER, MEDICAL, SCORED, Match, find_terms, normalize_hebrew as _normalize_hebrew  # noqa: F401
from core.filters.text.lexicon import tokenize as _tokenize_words
from core.filters.text.scoring import (
    DIVERSE_TERMS, Scored, best_window, context_factor, density, hot_sections, is_hot, set_score, weighted,
)
from data.constants import (
    SUPPORTED_LANGS,
    TEXT_DENSITY_SCORE,
    TEXT_DENSITY_WORDS,
    TEXT_MIN_MATCHES,
    TEXT_PAGE_DENSITY_SCORE,
    TEXT_PAGE_HIDDEN_SHARE,
    TEXT_TITLE_FACTOR,
)

logger = logging.getLogger(__name__)


def _find_matches(text: str, langs: List[str]) -> List[Tuple[int, int, str]]:
    """Hard words in text as (start, end, original_text) – what gets masked."""
    return [(m.start, m.end, m.text) for m in find_terms(text, langs)[0] if m.term.kind == HARD]


def _mask(text: str, matches) -> str:
    arr = list(text)
    for m in matches:
        start, end = (m.start, m.end) if isinstance(m, Match) else (m[0], m[1])
        for i in range(start, end):
            arr[i] = "X"
    return "".join(arr)


def _mask_string(s: str, keep_spaces: bool = True) -> str:
    """Replace every character with X; optionally keep spaces."""
    if keep_spaces:
        return "".join(" " if c.isspace() else "X" for c in s)
    return "X" * len(s)


def filter_paragraph_for_pdf(text: str, lang_hint: Optional[str] = None) -> Tuple[str, bool]:
    """PDF block / paragraph: hard words → X's, and a hot sentence or the whole block → X's. Returns (text, changed)."""
    if not text or not text.strip():
        return text, False
    out = _filter_plain_text(text, lang_hint)[0]
    return out, out != text


def _snippet_around_match(text: str, start: int, end: int, max_before: int = 120, max_after: int = 120, max_total: int = 400) -> str:
    """Extract a short context around a match; replace the match with [M] for privacy."""
    before_start = max(0, start - max_before)
    after_end = min(len(text), end + max_after)
    s = text[before_start:after_end]
    rel_start = start - before_start
    rel_end = end - before_start
    s = s[:rel_start] + "[M]" + s[rel_end:]
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_total:
        s = s[: max_total - 3] + "..."
    return s


# ---------- the decision: hot units → X's, then the page (scoring.py) ----------


@dataclass
class _Group:
    """Text read as one run: a plain-text paragraph, or the consecutive text nodes of one HTML block."""
    text: str
    comps: Tuple[Any, ...]                                         # enclosing components, smallest first
    key: Any = None
    items: List[Scored] = field(default_factory=list)              # it.off = character offset in text
    segs: List[Tuple[Any, int, list]] = field(default_factory=list)  # HTML: (text node, offset in text, hard matches)
    xs: List[Tuple[int, int]] = field(default_factory=list)        # ranges that become X's


_SENTENCE_END_RE = re.compile(r"[.!?…]+(?=\s|$)|\n")


def _sentences(text: str) -> List[Tuple[int, int]]:
    spans, start = [], 0
    for m in _SENTENCE_END_RE.finditer(text):
        if text[start:m.end()].strip():
            spans.append((start, m.end()))
        start = m.end()
    if text[start:].strip():
        spans.append((start, len(text)))
    return spans or [(0, len(text))]


def _sentence_at(spans: List[Tuple[int, int]], off: int) -> Tuple[int, int]:
    return spans[max(0, bisect_right([s for s, _ in spans], off) - 1)]


def _merge(ranges: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    for s, e in sorted(ranges):
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def _x_into(chars: List[str], start: int, end: int) -> None:
    for i in range(start, end):
        if not chars[i].isspace():
            chars[i] = "X"


def _decide(groups: List[_Group], comp_words: Callable[[Any], int], extra: List[Scored], words: int,
            content_words: Optional[int] = None) -> Tuple[bool, str, Dict[str, Any], List[Any]]:
    """Mark hot sentences, then hot components (smallest first), then hot sections as X ranges on the groups, each
    unit counting only what a smaller one did not take; then decide the page by ratio: what was X'd, and the density
    of what is left in the page's own text (content_words: words outside links).
    Returns (block_page, block_reason, debug_info, hot components)."""
    all_items = [it for g in groups for it in g.items] + extra
    markers = sum(1 for it in all_items if it.match.term.kind == MARKER)
    ctx = context_factor(markers, words, sum(1 for it in all_items if it.match.term.kind == MEDICAL))
    live = {id(it) for it in weighted(all_items)}
    units = sections = 0
    sentence_cache: Dict[int, List[Tuple[int, int]]] = {}

    def sentences(gi: int) -> List[Tuple[int, int]]:
        if gi not in sentence_cache:
            sentence_cache[gi] = _sentences(groups[gi].text)
        return sentence_cache[gi]

    def take(items: List[Scored]) -> Tuple[float, List[Scored]]:
        sub = [it for it in items if id(it) in live]
        return (set_score(sub, ctx)[0] if sub else 0.0), sub

    # 1. sentences
    for gi, g in enumerate(groups):
        w = weighted(g.items)
        for s, e in (sentences(gi) if w else ()):
            score, sub = take([it for it in w if s <= it.off < e])
            if score >= TEXT_DENSITY_SCORE and is_hot(score, len(_tokenize_words(g.text[s:e])), len(sub)):
                g.xs.append((s, e))
                live.difference_update(map(id, sub))
                units += 1

    # 2. components, smallest first
    comp_items: Dict[Any, List[Scored]] = defaultdict(list)
    depth: Dict[Any, int] = {}
    for g in groups:
        w = weighted(g.items)
        for k, c in enumerate(g.comps if w else ()):
            depth[c] = len(g.comps) - k
            comp_items[c].extend(w)
    hot_comps: List[Any] = []
    for c in sorted(comp_items, key=lambda c: -depth[c]):
        score, sub = take(comp_items[c])
        if score >= TEXT_DENSITY_SCORE and is_hot(score, comp_words(c), len(sub)):
            hot_comps.append(c)
            live.difference_update(map(id, sub))
            units += 1
    if hot_comps:
        hot = set(hot_comps)
        for g in groups:
            if hot.intersection(g.comps):
                g.xs.append((0, len(g.text)))

    # 3. sections: problem words close together, also across components
    rest = sorted((it for g in groups for it in weighted(g.items) if id(it) in live), key=lambda it: it.pos)
    for i, j in hot_sections(rest, ctx):
        a, b = rest[i], rest[j - 1]
        start = _sentence_at(sentences(a.group), a.off)[0]
        end = _sentence_at(sentences(b.group), b.off)[1]
        if a.group == b.group:
            groups[a.group].xs.append((start, end))
        else:
            groups[a.group].xs.append((start, len(groups[a.group].text)))
            for gi in range(a.group + 1, b.group):
                groups[gi].xs.append((0, len(groups[gi].text)))
            groups[b.group].xs.append((0, end))
        live.difference_update(map(id, rest[i:j]))
        units += 1
        sections += 1

    # 4. the page – by ratio
    x_words = 0
    for g in groups:
        g.xs = _merge(g.xs)
        x_words += sum(len(_tokenize_words(g.text[s:e])) for s, e in g.xs)
    share = x_words / max(words, 1)
    left, left_items = take([it for it in all_items if it.own])
    left_terms = len({it.match.term.key for it in left_items})
    dens = density(left, words if content_words is None else content_words)
    w_all = weighted(all_items)
    total, per_term = set_score(w_all, ctx)
    terms = ", ".join(f"{t} ({v:.1f})" for t, v in sorted(per_term.items(), key=lambda kv: -kv[1])[:6])
    block_page, block_reason = False, ""
    if x_words and share >= TEXT_PAGE_HIDDEN_SHARE:
        block_page, block_reason = True, f"score: {100 * share:.0f}% of the text turned into X's ({units} units) – {terms}"
    elif dens >= TEXT_PAGE_DENSITY_SCORE and left >= TEXT_DENSITY_SCORE and left_terms >= DIVERSE_TERMS:
        # many different words spread through the page's own text, adding up to a hot unit
        ctx_txt = f", context ×{ctx:g}" if ctx != 1.0 else ""
        block_page, block_reason = True, f"score: density {dens:.1f} / {TEXT_PAGE_DENSITY_SCORE:g} per {TEXT_DENSITY_WORDS} words{ctx_txt} – {terms}"
    snippet = ""
    first = next((it for it in w_all if it.group >= 0), None)
    if block_page and first is not None:
        snippet = _snippet_around_match(groups[first.group].text, first.off, first.off + first.match.end - first.match.start)
    debug_info = {
        "matched": [{"w": it.match.text, "s": it.match.term.weight} for it in w_all[:30]],
        "counts": {"matched": len(w_all), "total": words},
        "snippet": snippet,
        "score": {
            "page": round(total, 2), "window_max": round(best_window(sorted(w_all, key=lambda it: it.pos), ctx), 2),
            "density": round(dens, 2), "left": round(left, 2), "hidden_share": round(share, 3), "hidden_blocks": units, "sections": sections,
            "context_factor": ctx, "markers": markers,
            "top_terms": [[t, round(v, 2)] for t, v in sorted(per_term.items(), key=lambda kv: -kv[1])[:10]],
        },
    }
    return block_page, block_reason, debug_info, hot_comps


def _paragraph_spans(text: str) -> List[Tuple[int, int]]:
    spans, start = [], 0
    for m in re.finditer(r"\n[ \t\r]*\n", text):
        if text[start:m.start()].strip():
            spans.append((start, m.start()))
        start = m.end()
    if text[start:].strip():
        spans.append((start, len(text)))
    return spans


def _filter_plain_text(
    text: str,
    lang_hint: Optional[str] = None,
) -> Tuple[str, bool, str, Dict[str, Any]]:
    """Filter plain text. Returns (filtered_text, block_page, block_reason, debug_info).
    Hard words are masked; hot sentences / paragraphs / sections become X's; the page decision is by ratio."""
    if not text.strip():
        return text, False, "", {"matched": [], "counts": {"matched": 0, "total": 0}, "snippet": ""}
    langs = list(SUPPORTED_LANGS) if lang_hint is None else [lang_hint]
    spans = _paragraph_spans(text)
    groups: List[_Group] = []
    para_words: List[int] = []
    hard: List[Tuple[int, int]] = []
    pos = 0
    for k, (start, end) in enumerate(spans):
        ms, n = find_terms(text[start:end], langs)
        groups.append(_Group(text[start:end], (k,), items=[Scored(m, pos + m.token, group=k, off=m.start) for m in ms]))
        hard.extend((start + m.start, start + m.end) for m in ms if m.term.kind == HARD)
        para_words.append(n)
        pos += n
    block_page, block_reason, debug_info, _hot = _decide(groups, lambda k: para_words[k], [], pos)
    if block_page:
        logger.debug("text_filter: block_page=True %s", block_reason)
    if not hard and not any(g.xs for g in groups):
        return text, block_page, block_reason, debug_info
    chars = list(text)
    for start, end in hard:
        chars[start:end] = "X" * (end - start)
    for (start, _end), g in zip(spans, groups):
        for s, e in g.xs:
            _x_into(chars, start + s, start + e)
    return "".join(chars), block_page, block_reason, debug_info


_META_CHARSET_RE = re.compile(rb"""<meta[^>]+charset=["']?\s*([A-Za-z0-9_\-]+)""", re.IGNORECASE)


def _declared_charset(content: bytes, content_type: str) -> Optional[str]:
    ct = content_type or ""
    if "charset=" in ct.lower():
        for part in ct.split(";"):
            part = part.strip()
            if part.lower().startswith("charset="):
                return part.split("=", 1)[1].strip().strip("\"'") or None
    m = _META_CHARSET_RE.search(content[:4096])
    if m:
        return m.group(1).decode("ascii", errors="ignore") or None
    return None


def _decode_body(content: bytes, content_type: str) -> Tuple[str, str]:
    """Decode with the declared charset (header, then <meta>), falling back to UTF-8. Returns (text, encoding)."""
    declared = _declared_charset(content, content_type)
    for enc in ([declared] if declared else []) + ["utf-8"]:
        try:
            return content.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue
    return content.decode("utf-8", errors="replace"), "utf-8"


def _encode_like_source(text: str, encoding: str, html: bool) -> bytes:
    try:
        return text.encode(encoding, errors="xmlcharrefreplace" if html else "replace")
    except LookupError:
        return text.encode("utf-8", errors="replace")


def _filter_json_value(value: Any) -> Any:
    """Recursively walk JSON; filter only string values."""
    if isinstance(value, str):
        filtered, _block, _reason, _debug = _filter_plain_text(value)
        return filtered
    if isinstance(value, dict):
        return {k: _filter_json_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_filter_json_value(item) for item in value]
    return value


def _filter_json(text: str, url: str, content_type: str) -> Tuple[bytes, Dict[str, Any]]:
    """Parse JSON, filter string values, re-serialize. Never blocks – only replaces text."""
    try:
        data = json.loads(text)
    except Exception as e:
        logger.warning("JSON parse failed for text filter %s: %s", url or content_type, e)
        return text.encode("utf-8"), {"url": url, "content_type": content_type, "block_reason": "", "matched": [], "counts": {}, "snippet": ""}
    filtered_data = _filter_json_value(data)
    if filtered_data == data:
        # Nothing masked: return the original bytes untouched (re-serializing changes escapes/number
        # formatting and can break clients that sign or diff the payload).
        return text.encode("utf-8"), {"url": url, "content_type": content_type or "", "block_reason": "", "matched": [], "counts": {}, "snippet": ""}
    try:
        out = json.dumps(filtered_data, ensure_ascii=False)
        return out.encode("utf-8"), {"url": url, "content_type": content_type or "", "block_reason": "", "matched": [], "counts": {}, "snippet": ""}
    except Exception as e:
        logger.warning("JSON serialize failed after filter %s: %s", url or content_type, e)
        return text.encode("utf-8"), {"url": url, "content_type": content_type or "", "block_reason": "", "matched": [], "counts": {}, "snippet": ""}


def _encode_debug_b64(debug: Dict[str, Any]) -> str:
    """Encode full debug dict to base64 for display on blocked page."""
    try:
        js = json.dumps(debug, ensure_ascii=False)
        return base64.b64encode(js.encode("utf-8")).decode("ascii")
    except Exception:
        return ""


def format_text_filter_debug_readable(block_reason: str, debug_info: Dict[str, Any]) -> str:
    """Build a short Hebrew readable debug string for the blocked page."""
    parts = []
    if block_reason:
        parts.append("סיבת חסימה: " + block_reason)
    score = debug_info.get("score") or {}
    if score:
        parts.append("ניקוד: צפיפות %s ל-%d מילים, %s%% הפך ל-X (%s יחידות), חלון %s, דף %s%s" % (
            score.get("density"), TEXT_DENSITY_WORDS, round(100 * (score.get("hidden_share") or 0)), score.get("hidden_blocks", 0),
            score.get("window_max"), score.get("page"),
            "" if score.get("context_factor", 1) == 1 else ", הקשר ×%s" % score.get("context_factor"),
        ))
    counts = debug_info.get("counts") or {}
    matched_count = counts.get("matched", 0)
    total = counts.get("total", 0)
    if matched_count or total:
        parts.append("ספירה: %d מילים מתוך %d" % (matched_count, total))
    matched = debug_info.get("matched") or []
    if matched:
        words = [m.get("w", "") for m in matched[:15] if m.get("w")]
        if words:
            parts.append("מילים שנמצאו (דוגמה): " + ", ".join(words))
    snippet = (debug_info.get("snippet") or "").strip()
    if snippet:
        parts.append("הקשר: " + snippet[:300] + ("..." if len(snippet) > 300 else ""))
    return "\n".join(parts)


def filter_text_content(
    content: bytes,
    *,
    url: str = "",
    content_type: str = "",
    text_filter_enabled: bool = True,
    rule_context: Optional[dict] = None,
) -> Tuple[bytes, bool, str, Dict[str, Any]]:
    """
    מסנן תוכן טקסטואלי (HTML או טקסט גולמי).

    Returns:
        (filtered_content_bytes, block_page, block_reason, debug_info).
    """
    empty_debug: Dict[str, Any] = {"url": url, "content_type": content_type, "block_reason": "", "matched": [], "counts": {}, "snippet": ""}
    if not text_filter_enabled:
        return content, False, "", empty_debug
    try:
        text, used_encoding = _decode_body(content, content_type)
        ct_lower = (content_type or "").lower()
        is_json = "application/json" in ct_lower or (text.strip().startswith("{") or text.strip().startswith("["))
        if is_json:
            out_bytes, debug_info = _filter_json(text, url, content_type)
            if out_bytes == text.encode("utf-8"):
                out_bytes = content  # unchanged: original bytes, original charset
            elif used_encoding.lower().replace("_", "-") not in ("utf-8", "utf8"):
                out_bytes = _encode_like_source(out_bytes.decode("utf-8"), used_encoding, html=False)
            block_page, block_reason = False, ""
        else:
            is_html = "<" in text and ">" in text and ("<html" in text.lower() or "<body" in text.lower() or "<div" in text.lower())
            if is_html:
                out_bytes, block_page, block_reason, debug_info = _filter_html(text, url, content_type, used_encoding)
                if out_bytes is None:
                    out_bytes = content  # unchanged: no re-serialization of the page
            else:
                filtered, block_page, block_reason, debug_info = _filter_plain_text(text)
                out_bytes = content if filtered == text else _encode_like_source(filtered, used_encoding, html=False)
        full_debug: Dict[str, Any] = {
            "url": url,
            "content_type": content_type or "",
            "content_length": len(content),
            "block_reason": block_reason,
            "matched": debug_info.get("matched", []),
            "counts": debug_info.get("counts", {}),
            "snippet": debug_info.get("snippet", ""),
        }
        if "score" in debug_info:
            full_debug["score"] = debug_info["score"]
        return out_bytes, block_page, block_reason, full_debug
    except Exception as e:
        logger.warning("Text filter failed for %s: %s", url or content_type, e)
        return content, False, "", {"url": url, "content_type": content_type or "", "block_reason": "", "matched": [], "counts": {}, "snippet": ""}


_SKIP_FILTER_TAGS = frozenset(("script", "style", "noscript", "template", "xmp", "iframe"))


def _is_inside_skip_tag(node) -> bool:
    """True if node is inside script, style, etc."""
    from bs4 import NavigableString
    if not isinstance(node, NavigableString):
        return False
    parent = node.parent
    while parent is not None:
        if getattr(parent, "name", None) and parent.name in _SKIP_FILTER_TAGS:
            return True
        parent = getattr(parent, "parent", None)
    return False


# Elements a reader sees as a unit (components). Scores add up the tree, and the SMALLEST hot element turns into X's –
# a heading, a search result, a teaser card, a comment, a whole list of links (a navigation box whose items each hold
# one word).
_BLOCK_TAGS = frozenset((
    "div", "section", "article", "aside", "nav", "header", "footer", "ul", "ol", "li", "table", "tbody", "thead",
    "tr", "td", "th", "p", "blockquote", "figure", "figcaption", "dl", "dt", "dd", "details", "form",
    "title", "h1", "h2", "h3", "h4", "h5", "h6", "main", "caption",
))
_HEADING_TAGS = frozenset(("title", "h1", "h2", "h3"))


def _block_chain(node) -> list:
    """Block-level ancestors of a text node, nearest first (body / html excluded)."""
    chain = []
    el = node.parent
    while el is not None and getattr(el, "name", None) not in (None, "body", "html", "[document]"):
        if el.name in _BLOCK_TAGS:
            chain.append(el)
        el = el.parent
    return chain


def _in_heading(node) -> bool:
    el = node.parent
    while el is not None:
        if getattr(el, "name", None) in _HEADING_TAGS:
            return True
        el = el.parent
    return False


def _url_words(url: str) -> str:
    try:
        path = unquote(urlsplit(url or "").path)
    except ValueError:
        return ""
    return re.sub(r"[/_\-.+]+", " ", path).strip()


def _filter_html(html_text: str, url: str, content_type: str, encoding: str = "utf-8") -> Tuple[Optional[bytes], bool, str, Dict[str, Any]]:
    """
    Mask hard words in every visible text node and image alt/title; turn hot sentences, components and sections into
    X's (_decide); block the page by ratio. Returns None instead of bytes when nothing changed.
    """
    try:
        from bs4 import BeautifulSoup
        from bs4.element import Comment, Declaration, Doctype, NavigableString, ProcessingInstruction
    except ImportError:
        logger.warning("BeautifulSoup4 not available; filtering as plain text")
        filtered, block_page, block_reason, debug_info = _filter_plain_text(html_text)
        return filtered.encode("utf-8"), block_page, block_reason, debug_info

    soup = BeautifulSoup(html_text, "html.parser")
    langs = list(SUPPORTED_LANGS)
    extra: List[Scored] = []  # URL words and image texts: no sentence to X
    groups: List[_Group] = []
    elements: Dict[int, Any] = {}
    pos = content_words = 0
    changed = False

    slug = _url_words(url)
    if slug:
        ms, n = find_terms(slug, langs)
        extra += [Scored(m, pos + m.token) for m in ms]
        pos += n

    skip_types = (Comment, Declaration, Doctype, ProcessingInstruction)
    for node in [n for n in soup.descendants if isinstance(n, NavigableString)]:
        if isinstance(node, skip_types) or not node.strip() or _is_inside_skip_tag(node):
            continue
        s = str(node)
        chain = _block_chain(node)
        in_link = node.find_parent("a") is not None
        leaf = id(chain[0]) if chain else None
        if not groups or groups[-1].key != leaf:
            elements.update((id(el), el) for el in chain)
            groups.append(_Group("", tuple(id(el) for el in chain), key=leaf))
        g = groups[-1]
        ms, n = find_terms(s, langs)
        if ms:
            factor = TEXT_TITLE_FACTOR if _in_heading(node) else 1.0
            g.items.extend(Scored(m, pos + m.token, factor, len(groups) - 1, len(g.text) + m.start, not in_link) for m in ms)
        g.segs.append((node, len(g.text), [m for m in ms if m.term.kind == HARD]))
        g.text += s
        pos += n
        content_words += 0 if in_link else n

    for img in soup.find_all("img"):
        own = img.find_parent("a") is None  # a teaser image is judged with the page it links to
        for attr in ("alt", "title"):
            val = img.get(attr)
            if not val or not isinstance(val, str):
                continue
            ms, n = find_terms(val, langs)
            extra += [Scored(m, pos + m.token, own=own) for m in ms]
            hard = [m for m in ms if m.term.kind == HARD]
            if hard:
                img[attr] = _mask(val, hard)
                changed = True
            pos += n

    block_page, block_reason, debug_info, hot_comps = _decide(
        groups, lambda c: len(_tokenize_words(elements[c].get_text(" "))), extra, pos, content_words)

    for c in hot_comps:
        for img in elements[c].find_all("img"):
            for attr in ("alt", "title"):
                if isinstance(img.get(attr), str) and img[attr].strip():
                    img[attr] = _mask_string(img[attr])
                    changed = True
    for g in groups:
        for node, base, hard in g.segs:
            s = str(node)
            xs = [(max(a, base) - base, min(b, base + len(s)) - base) for a, b in g.xs if a < base + len(s) and b > base]
            if not hard and not xs:
                continue
            chars = list(s)
            for m in hard:
                chars[m.start:m.end] = "X" * (m.end - m.start)
            for a, b in xs:
                _x_into(chars, a, b)
            node.replace_with("".join(chars))
            changed = True
    units = debug_info["score"]["hidden_blocks"]
    if units:
        logger.info("text_filter: %d unit(s) turned into X's on %s", units, url[:100])
    if not changed:
        return None, block_page, block_reason, debug_info  # nothing changed: the caller keeps the original bytes
    out = soup.decode(eventual_encoding=encoding)  # keeps <meta charset> consistent with the bytes we emit
    # Re-encode in the charset the page declared (windows-1255 Hebrew sites used to come back as UTF-8
    # under a windows-1255 header = garbled text). Characters the charset lacks become &#NNN; refs.
    return _encode_like_source(out, encoding, html=True), block_page, block_reason, debug_info
