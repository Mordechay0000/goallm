"""
סינון מלל (text filtering) – סינון לחרדים.

- רמה אחת: מילה ברשימה = תוכן לא צנוע. חסימה לפי יחס על כל הדף/מסמך.
- החלפת מילה באיקסים (לפי אורך). תמיכה בעברית ובאנגלית (רשימות ב־word_lists/*/blocked.txt).
- התאמה דקדוקית: stemming לזיהוי צורות מילה (sexually, nudity, gays וכו').
"""
import base64
import json
import re
import logging
from typing import Optional, Tuple, Dict, List, Any
from pathlib import Path

from core.filters.text.text_filter_config import (
    WORD_LISTS_DIR,
    BLOCKED_WORDS_FILENAME,
    MIN_RATIO_WORDS_FOR_PAGE_BLOCK,
    MIN_MATCHES_FOR_PAGE_BLOCK,
    MIN_WORDS_FOR_RATIO_BLOCK,
    MIN_PERCENTAGE_COMPONENTS_FOR_PAGE_BLOCK,
    MIN_COMPONENTS_WITH_DETECTION_FOR_PAGE_BLOCK,
    SUPPORTED_LANGS,
)

logger = logging.getLogger(__name__)

# Optional stemmer for English (snowballstemmer has no Hebrew)
_stemmer_en = None
try:
    import snowballstemmer
    _stemmer_en = snowballstemmer.EnglishStemmer()
except ImportError:
    logger.debug("snowballstemmer not installed; using exact match only (pip install snowballstemmer for stemming)")

# Hebrew suffixes for morphological matching (order: longer first)
_HEBREW_SUFFIXES = ("יות", "ים", "ות", "ית", "י", "ה", "ת", "ו")
# Hebrew prefixes to strip – ה (the), ו (and), ב (in), ל (to), כ (as), מ (from), ש (that)
_HEBREW_PREFIXES = ("ש", "מ", "ל", "ב", "כ", "ה", "ו")


# cache: lang -> set of words/stems (normalized)
_word_list_cache: Dict[str, set] = {}


def _normalize_hebrew(word: str) -> str:
    """Strip niqqud and normalize final letters: ך→כ, ם→מ, ן→נ, ף→פ, ץ→צ."""
    s = re.sub(r"[\u0591-\u05C7\u05C0-\u05C3\u05C4-\u05C5]", "", word)
    # Final form to regular form (so ך matches כ, etc.)
    final_to_regular = {"\u05da": "\u05db", "\u05dd": "\u05de", "\u05df": "\u05e0", "\u05e3": "\u05e4", "\u05e5": "\u05e6"}
    for fin, reg in final_to_regular.items():
        s = s.replace(fin, reg)
    return s


def _strip_hebrew_prefix(word: str) -> str:
    """Strip common Hebrew prefixes (ה/ו/ב/ל/כ/מ/ש)."""
    for pre in _HEBREW_PREFIXES:
        if len(word) > len(pre) + 1 and word.startswith(pre):
            return word[len(pre):]
    return word


def _stem(word: str, lang: str) -> str:
    """Return stem of word for matching. EN: snowball; HE: prefix + suffix stripping."""
    if lang == "en" and _stemmer_en:
        return _stemmer_en.stemWord(word)
    if lang == "he" and len(word) > 1:
        w = _strip_hebrew_prefix(word)
        for suf in _HEBREW_SUFFIXES:
            if len(w) > len(suf) + 1 and w.endswith(suf):
                return w[: -len(suf)]
        return w
    return word


def _load_blocked_words(lang: str) -> set:
    """Load blocked word list for lang; cached. Includes stems when stemmer available."""
    if lang in _word_list_cache:
        return _word_list_cache[lang]
    path = WORD_LISTS_DIR / lang / BLOCKED_WORDS_FILENAME
    words = set()
    if path.exists():
        try:
            raw = path.read_text(encoding="utf-8")
            for line in raw.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                w = line.split("#")[0].strip()
                if w:
                    if lang == "en":
                        n = w.lower()
                    else:
                        n = _normalize_hebrew(w)
                    words.add(n)
                    # Add stem for morphological matching
                    stem = _stem(n, lang)
                    if stem and stem != n:
                        words.add(stem)
        except Exception as e:
            logger.warning("Failed to load word list %s: %s", path, e)
    _word_list_cache[lang] = words
    return words


def _is_listed(word: str, lang: str) -> bool:
    """Return True if word (or its stem) is in blocked list for this language."""
    w = word.lower() if lang == "en" else _normalize_hebrew(word)
    blocked = _load_blocked_words(lang)
    if w in blocked:
        return True
    stem_w = _stem(w, lang)
    return stem_w in blocked


def _tokenize_words(text: str) -> List[Tuple[str, int, int]]:
    """Return list of (word, start, end) for Hebrew+English word chars."""
    pattern = re.compile(r"[\u0590-\u05FFa-zA-Z0-9]+")
    return [(m.group(0), m.start(), m.end()) for m in pattern.finditer(text)]


def _mask_string(s: str, keep_spaces: bool = True) -> str:
    """Replace every character with X; optionally keep spaces."""
    if keep_spaces:
        return "".join(" " if c.isspace() else "X" for c in s)
    return "X" * len(s)


def filter_paragraph_for_pdf(text: str, lang_hint: Optional[str] = None) -> Tuple[str, bool]:
    """
    For PDF block/paragraph: if any word is in blocked list, return (text with matched words
    replaced by X's, True); otherwise (original_text, False).
    """
    if not text or not text.strip():
        return text, False
    langs = list(SUPPORTED_LANGS) if lang_hint is None else [lang_hint]
    arr = list(text)
    has_detection = False
    for word, start, end in _tokenize_words(text):
        for lang in langs:
            if _is_listed(word, lang):
                has_detection = True
                for i in range(start, end):
                    arr[i] = "X"
                break
    if has_detection:
        return "".join(arr), True
    return text, False


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


def _filter_plain_text(
    text: str,
    lang_hint: Optional[str] = None,
) -> Tuple[str, bool, str, Dict[str, Any]]:
    """
    Filter plain text. Returns (filtered_text, block_page, block_reason, debug_info).
    Block decision: ratio-based – matched_words/total_words >= MIN_RATIO and matched >= MIN_MATCHES.
    """
    empty_debug: Dict[str, Any] = {"matched": [], "counts": {"matched": 0, "total": 0}, "snippet": ""}
    if not text.strip():
        return text, False, "", empty_debug

    langs = list(SUPPORTED_LANGS) if lang_hint is None else [lang_hint]

    # Find all matched words
    matched_ranges: List[Tuple[int, int, str]] = []
    tokens = _tokenize_words(text)
    total_words = len(tokens)

    for word, start, end in tokens:
        for lang in langs:
            if _is_listed(word, lang):
                matched_ranges.append((start, end, text[start:end]))
                break

    count_matched = len(matched_ranges)
    counts = {"matched": count_matched, "total": total_words}
    matched = [{"w": w, "s": 1} for _, _, w in matched_ranges[:30]]
    debug_info: Dict[str, Any] = {"matched": matched, "counts": counts, "snippet": ""}

    logger.debug("text_filter: plain_text matches=%s total=%s", count_matched, total_words)

    # Block: short doc (≤80 words) → count only; long doc → ratio
    block_page = False
    block_reason = ""
    if total_words > 0 and count_matched >= MIN_MATCHES_FOR_PAGE_BLOCK:
        if total_words <= MIN_WORDS_FOR_RATIO_BLOCK:
            # Short document: block by count only
            block_page = True
            block_reason = "short_doc_count: %d matches in %d words" % (count_matched, total_words)
        else:
            # Long document: block by ratio
            ratio = count_matched / total_words
            if ratio >= MIN_RATIO_WORDS_FOR_PAGE_BLOCK:
                block_page = True
                block_reason = "ratio_words: %d/%d (%.1f%% >= %.1f%%)" % (
                    count_matched, total_words, ratio * 100, MIN_RATIO_WORDS_FOR_PAGE_BLOCK * 100,
                )
        if block_page and matched_ranges:
            s, e, _ = matched_ranges[0]
            debug_info["snippet"] = _snippet_around_match(text, s, e)
            logger.debug("text_filter: block_page=True %s", block_reason)

    # Replace matched words with X's
    arr = list(text)
    for start, end, _ in matched_ranges:
        for i in range(start, end):
            arr[i] = "X"

    return "".join(arr), block_page, block_reason, debug_info


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
    logger.debug("text_filter: filter_text_content url=%r content_type=%r len=%s text_filter_enabled=%s", url, content_type, len(content), text_filter_enabled)
    if not text_filter_enabled:
        logger.debug("text_filter: skipped (text_filter_enabled=False)")
        return content, False, "", empty_debug

    try:
        if "charset=" in (content_type or ""):
            for enc in ("utf-8", "windows-1255", "iso-8859-1"):
                try:
                    text = content.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                text = content.decode("utf-8", errors="replace")
        else:
            text = content.decode("utf-8", errors="replace")

        ct_lower = (content_type or "").lower()
        is_json = "application/json" in ct_lower or (
            text.strip().startswith("{") or text.strip().startswith("[")
        )
        if is_json:
            logger.debug("text_filter: treating as JSON (content_type=%s)", content_type)
            out_bytes, debug_info = _filter_json(text, url, content_type)
            block_page = False
            block_reason = ""
        else:
            is_html = "<" in text and ">" in text and ("<html" in text.lower() or "<body" in text.lower() or "<div" in text.lower())
            logger.debug("text_filter: decoded len=%s is_html=%s", len(text), is_html)

            if is_html:
                out_bytes, block_page, block_reason, debug_info = _filter_html(text, url, content_type)
                logger.debug("text_filter: _filter_html done block_page=%s reason=%s", block_page, block_reason)
            else:
                filtered, block_page, block_reason, debug_info = _filter_plain_text(text)
                out_bytes = filtered.encode("utf-8")
                logger.debug("text_filter: _filter_plain_text done block_page=%s reason=%s", block_page, block_reason)

        full_debug: Dict[str, Any] = {
            "url": url,
            "content_type": content_type or "",
            "content_length": len(content),
            "block_reason": block_reason,
            "matched": debug_info.get("matched", []),
            "counts": debug_info.get("counts", {}),
            "snippet": debug_info.get("snippet", ""),
        }
        if "blocks_with" in debug_info:
            full_debug["blocks_with"] = debug_info["blocks_with"]
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


def _filter_html(html_text: str, url: str, content_type: str) -> Tuple[bytes, bool, str, Dict[str, Any]]:
    """
    Parse HTML, filter each text node. Replace only matched words with X's (not entire component).
    Block page when ratio of components with detection >= MIN_PERCENTAGE and count >= MIN_COMPONENTS.
    """
    empty_debug: Dict[str, Any] = {"matched": [], "counts": {"matched": 0, "total": 0}, "snippet": ""}
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("BeautifulSoup4 not available; filtering as plain text")
        filtered, block_page, block_reason, debug_info = _filter_plain_text(html_text)
        return filtered.encode("utf-8"), block_page, block_reason, debug_info

    soup = BeautifulSoup(html_text, "html.parser")
    merged_matched: List[Dict[str, Any]] = []
    total_matched = 0
    total_words = 0
    first_snippet = ""
    components_with_detection = 0
    total_components = 0

    from bs4 import NavigableString

    for node in soup.descendants:
        if isinstance(node, NavigableString) and node.strip():
            if _is_inside_skip_tag(node):
                continue
            total_components += 1
            s = str(node)
            filtered, _block_ignored, _reason, debug_info = _filter_plain_text(s)
            count_matched = debug_info.get("counts", {}).get("matched", 0)
            count_total = debug_info.get("counts", {}).get("total", 0)
            total_words += count_total
            has_detection = count_matched > 0
            if has_detection:
                components_with_detection += 1
                total_matched += count_matched
                for m in debug_info.get("matched", [])[:20]:
                    merged_matched.append(m)
                if debug_info.get("snippet") and not first_snippet:
                    first_snippet = debug_info["snippet"]
                node.replace_with(filtered)
            # No match: keep original

    # Block if (components ratio) OR (words ratio) passes threshold
    block_page = False
    block_reason = ""
    if total_components > 0 and components_with_detection > 0:
        comp_pct = components_with_detection / total_components
        comp_ok = components_with_detection >= MIN_COMPONENTS_WITH_DETECTION_FOR_PAGE_BLOCK and comp_pct >= MIN_PERCENTAGE_COMPONENTS_FOR_PAGE_BLOCK
        if comp_ok:
            block_page = True
            block_reason = "components_with_detection: %d/%d (%.0f%% >= %.0f%%)" % (
                components_with_detection, total_components,
                comp_pct * 100, MIN_PERCENTAGE_COMPONENTS_FOR_PAGE_BLOCK * 100,
            )
    if not block_page and total_words > 0 and total_matched >= MIN_MATCHES_FOR_PAGE_BLOCK:
        if total_words <= MIN_WORDS_FOR_RATIO_BLOCK:
            block_page = True
            block_reason = "short_page_count: %d matches in %d words" % (total_matched, total_words)
        else:
            word_ratio = total_matched / total_words
            if word_ratio >= MIN_RATIO_WORDS_FOR_PAGE_BLOCK:
                block_page = True
                block_reason = "words_ratio: %d/%d (%.1f%% >= %.1f%%)" % (
                    total_matched, total_words, word_ratio * 100, MIN_RATIO_WORDS_FOR_PAGE_BLOCK * 100,
                )

    out_debug: Dict[str, Any] = {
        "matched": merged_matched[:50],
        "counts": {"matched": total_matched, "total": total_words},
        "snippet": first_snippet,
        "blocks_with": {"components_with_detection": components_with_detection, "total_components": total_components},
    }
    logger.debug(
        "text_filter: _filter_html block_page=%s reason=%s components=%d/%d",
        block_page, block_reason, components_with_detection, total_components,
    )

    out = str(soup)
    if soup.original_encoding:
        return out.encode(soup.original_encoding), block_page, block_reason, out_debug
    return out.encode("utf-8"), block_page, block_reason, out_debug
