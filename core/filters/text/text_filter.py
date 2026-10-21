"""
סינון מלל (text filtering) – סינון לחרדים, בלי מודל שפה.

שתי רמות:
- מילים קשות (word_lists/*/blocked.txt): מוחלפות ב-XXX בכל הקשר (כולל להט"ב), ומשקלן גבוה בניקוד.
- מילים חשודות (word_lists/*/scored.txt): לא מוסתרות – ניקוד נסתר שמצטבר (ליבידו, עירום, "בגד ים"…).
ההחלטה (scoring.py): ניקוד יורד לחזרות של אותה מילה, בונוס לכמה מילים שונות יחד, ניקוד מקומי (חלון מילים),
הקשר תורני מפחית מילים חשודות (לא קשות), כותרות שוקלות יותר.

בדף HTML (אתרים מעורבים שחייבים לפתוח): בלוק (כתבה / תגובה / פריט / כרטיס) שעבר את הסף מוסתר לבדו;
הדף כולו נחסם רק כשהניקוד גבוה בדף עצמו.
התאמה (lexicon.py): עברית – המילה ונטיותיה + אותיות שימוש; אנגלית – stemming; ביטויים; עקיפות (s.e.x, תווים נסתרים).
בדיקת רשימות מול טקסט מותר: python -m tools.check_word_list <קבצים>.
"""
import base64
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlsplit

from core.filters.text.lexicon import HARD, MARKER, MEDICAL, SCORED, Match, find_terms, normalize_hebrew as _normalize_hebrew  # noqa: F401
from core.filters.text.lexicon import tokenize as _tokenize_words
from core.filters.text.scoring import PageScore, Scored, context_factor, score_page, set_score
from data.constants import SUPPORTED_LANGS, TEXT_HIDE_MAX_SHARE, TEXT_HIDE_SCORE, TEXT_TITLE_FACTOR

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
    """PDF block / paragraph: hard words → X's. Returns (text, any_hard_word)."""
    if not text or not text.strip():
        return text, False
    langs = list(SUPPORTED_LANGS) if lang_hint is None else [lang_hint]
    ranges = _find_matches(text, langs)
    if not ranges:
        return text, False
    return _mask(text, ranges), True


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


def _debug(ps: PageScore, items: List[Scored], hidden: int = 0) -> Dict[str, Any]:
    weighted = [it for it in items if it.match.term.kind in (HARD, SCORED) and it.match.term.weight > 0]
    return {
        "matched": [{"w": it.match.text, "s": it.match.term.weight} for it in weighted[:30]],
        "counts": {"matched": len(weighted), "total": ps.words},
        "snippet": "",
        "score": {
            "window_max": round(ps.window_max, 2), "page": round(ps.total, 2), "context_factor": ps.context_factor,
            "markers": ps.markers, "top_terms": [[t, round(s, 2)] for t, s in ps.top_terms[:10]], "hidden_blocks": hidden,
        },
    }


def _filter_plain_text(
    text: str,
    lang_hint: Optional[str] = None,
) -> Tuple[str, bool, str, Dict[str, Any]]:
    """Filter plain text. Returns (filtered_text, block_page, block_reason, debug_info).
    Hard words are masked; the block decision is the hidden score (scoring.py)."""
    if not text.strip():
        return text, False, "", {"matched": [], "counts": {"matched": 0, "total": 0}, "snippet": ""}
    langs = list(SUPPORTED_LANGS) if lang_hint is None else [lang_hint]
    matches, words = find_terms(text, langs)
    items = [Scored(m, m.token) for m in matches]
    ps = score_page(items, words)
    debug_info = _debug(ps, items)
    block_page = ps.blocked
    block_reason = ps.reason() if block_page else ""
    if block_page:
        first = next((it.match for it in items if it.pos >= ps.window_start and it.match.term.kind in (HARD, SCORED)), None)
        if first is not None:
            debug_info["snippet"] = _snippet_around_match(text, first.start, first.end)
        logger.debug("text_filter: block_page=True %s", block_reason)
    hard = [m for m in matches if m.term.kind == HARD]
    return (_mask(text, hard) if hard else text), block_page, block_reason, debug_info


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
        parts.append("ניקוד: חלון %s, דף %s%s" % (
            score.get("window_max"), score.get("page"),
            "" if score.get("context_factor", 1) == 1 else ", הקשר תורני ×%s" % score.get("context_factor"),
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


# Elements a reader sees as a unit. Scores add up the tree, and the SMALLEST element whose accumulated score
# passes TEXT_HIDE_SCORE is hidden – a comment, a teaser card, a whole list of links (a navigation box whose items
# each hold one word) – unless it is the bulk of the page.
_BLOCK_TAGS = frozenset((
    "div", "section", "article", "aside", "nav", "header", "footer", "ul", "ol", "li", "table", "tbody", "thead",
    "tr", "td", "th", "p", "blockquote", "figure", "figcaption", "dl", "dt", "dd", "details", "form",
))
_HEADING_TAGS = frozenset(("title", "h1", "h2", "h3"))
HIDDEN_PLACEHOLDER = "⊘ תוכן הוסתר בסינון"


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
    Mask hard words in every visible text node and image alt/title; score the page.
    A block (post / comment / item / card) whose own score passes TEXT_HIDE_SCORE is hidden by itself, if it is not
    the bulk of the page; the page is blocked only if what remains still scores high.
    Returns None instead of bytes when nothing was masked or hidden.
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
    items: List[Scored] = []
    blocks: Dict[int, list] = {}  # id(element) → [element, depth (bigger = smaller element), [Scored]]
    pos = 0

    slug = _url_words(url)
    if slug:
        ms, n = find_terms(slug, langs)
        items += [Scored(m, pos + m.token) for m in ms]
        pos += n

    skip_types = (Comment, Declaration, Doctype, ProcessingInstruction)
    masked = False
    for node in [n for n in soup.descendants if isinstance(n, NavigableString)]:
        if isinstance(node, skip_types) or not node.strip() or _is_inside_skip_tag(node):
            continue
        s = str(node)
        ms, n = find_terms(s, langs)
        if ms:
            factor = TEXT_TITLE_FACTOR if _in_heading(node) else 1.0
            placed = [Scored(m, pos + m.token, factor) for m in ms]
            items.extend(placed)
            chain = _block_chain(node)
            for k, el in enumerate(chain):
                blocks.setdefault(id(el), [el, len(chain) - k, []])[2].extend(placed)
            hard = [m for m in ms if m.term.kind == HARD]
            if hard:
                node.replace_with(_mask(s, hard))
                masked = True
        pos += n

    for img in soup.find_all("img"):
        for attr in ("alt", "title"):
            val = img.get(attr)
            if not val or not isinstance(val, str):
                continue
            ms, n = find_terms(val, langs)
            items += [Scored(m, pos + m.token) for m in ms]
            hard = [m for m in ms if m.term.kind == HARD]
            if hard:
                img[attr] = _mask(val, hard)
                masked = True
            pos += n

    words = pos
    ctx = context_factor(sum(1 for it in items if it.match.term.kind == MARKER), words,
                         sum(1 for it in items if it.match.term.kind == MEDICAL))
    removed: set = set()
    hidden = 0
    hidden_words = 0
    # smallest elements first: hide the minimal unit that carries the score
    for el, _depth, bitems in sorted(blocks.values(), key=lambda b: -b[1]):
        live = [it for it in bitems if id(it) not in removed]
        if not live or set_score(live, ctx)[0] < TEXT_HIDE_SCORE:
            continue
        el_words = len(_tokenize_words(el.get_text(" ")))
        if el_words > TEXT_HIDE_MAX_SHARE * max(words, 1):
            continue  # the main content itself – the page decision handles it
        removed.update(id(it) for it in live)
        el.clear()
        el.append(HIDDEN_PLACEHOLDER)
        hidden += 1
        hidden_words += el_words
    if hidden:  # an element hidden first may sit inside a bigger one hidden later – count what the reader sees
        hidden = len(soup.find_all(string=HIDDEN_PLACEHOLDER))
    remaining = [it for it in items if id(it) not in removed]
    ps = score_page(remaining, words)
    block_page = ps.blocked
    block_reason = ps.reason() if block_page else ""
    if not block_page and hidden_words > TEXT_HIDE_MAX_SHARE * max(words, 1):
        # paragraph after paragraph was hidden: the page itself is the problem, not a block on it
        block_page = True
        block_reason = f"score: {hidden} hidden blocks = {100 * hidden_words // max(words, 1)}% of the page"
    debug_info = _debug(ps, remaining, hidden)
    if hidden:
        logger.info("text_filter: %d block(s) hidden on %s", hidden, url[:100])
    if not masked and not hidden:
        return None, block_page, block_reason, debug_info  # nothing changed: the caller keeps the original bytes
    out = soup.decode(eventual_encoding=encoding)  # keeps <meta charset> consistent with the bytes we emit
    # Re-encode in the charset the page declared (windows-1255 Hebrew sites used to come back as UTF-8
    # under a windows-1255 header = garbled text). Characters the charset lacks become &#NNN; refs.
    return _encode_like_source(out, encoding, html=True), block_page, block_reason, debug_info
