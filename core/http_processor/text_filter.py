"""
סינון מלל (text filtering) – סינון לחרדים.

- רמות חומרה: 1=קל (קללות), 2=בינוני, 3=חמור (תוכן מיני/כפירה וכו').
- החלפת מילה באיקסים (לפי אורך); ספים למשפט/פסקה/דף.
- תמיכה בעברית ובאנגלית (רשימות מילים ב־word_lists).
"""
import base64
import json
import re
import logging
from typing import Optional, Tuple, Dict, List, Any
from pathlib import Path

from core.http_processor.text_filter_config import (
    WORD_LISTS_DIR,
    SEVERITY_LIGHT,
    SEVERITY_MEDIUM,
    SEVERITY_SEVERE,
    THRESHOLD_SENTENCE_LIGHT,
    THRESHOLD_PARAGRAPH_LIGHT,
    THRESHOLD_PAGE_LIGHT,
    ANY_SEVERITY_3_BLOCKS_PAGE,
    THRESHOLD_PAGE_MEDIUM_BLOCK,
    MIN_BLOCKS_SEVERE_FOR_PAGE_BLOCK,
    MIN_BLOCKS_MEDIUM_FOR_PAGE_BLOCK,
    MIN_BLOCKS_LIGHT_FOR_PAGE_BLOCK,
    MIN_TOTAL_SEVERE_FOR_PAGE_BLOCK,
    SUPPORTED_LANGS,
)

logger = logging.getLogger(__name__)

# cache: (lang, severity) -> set of words (normalized)
_word_list_cache: Dict[Tuple[str, int], set] = {}


def _normalize_hebrew(word: str) -> str:
    """Strip optional niqqud for matching (keep base letters)."""
    # Remove Hebrew niqqud (U+0591–U+05C7) and other marks
    return re.sub(r"[\u0591-\u05C7\u05C0-\u05C3\u05C4-\u05C5]", "", word)


def _load_word_list(lang: str, severity: int) -> set:
    """Load word list for lang and severity; cached."""
    key = (lang, severity)
    if key in _word_list_cache:
        return _word_list_cache[key]
    path = WORD_LISTS_DIR / lang / f"severity_{severity}.txt"
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
                        words.add(w.lower())
                    else:
                        words.add(_normalize_hebrew(w))
        except Exception as e:
            logger.warning("Failed to load word list %s: %s", path, e)
    _word_list_cache[key] = words
    return words


def _get_word_severity(word: str, lang: str) -> int:
    """Return max severity (1–3) for word in this language, or 0 if not in lists."""
    w_lower = word.lower() if lang == "en" else _normalize_hebrew(word)
    for sev in (SEVERITY_SEVERE, SEVERITY_MEDIUM, SEVERITY_LIGHT):
        if w_lower in _load_word_list(lang, sev):
            return sev
    return 0


def _tokenize_words(text: str) -> List[Tuple[str, int, int]]:
    """Return list of (word, start, end) for Hebrew+English word chars."""
    # Hebrew block \u0590-\u05FF, English letters, digits
    pattern = re.compile(r"[\u0590-\u05FFa-zA-Z0-9]+")
    return [(m.group(0), m.start(), m.end()) for m in pattern.finditer(text)]


def _split_sentences(paragraph: str) -> List[Tuple[str, int, int]]:
    """Split paragraph into sentences; return list of (sentence, start, end) relative to paragraph."""
    # Sentence boundaries: . ! ? or newline (keep delimiter with previous sentence)
    pattern = re.compile(r"(?<=[.!?\n])\s*")
    parts = pattern.split(paragraph)
    sentences = []
    pos = 0
    for part in parts:
        if part.strip():
            start = pos
            end = pos + len(part)
            sentences.append((part, start, end))
        pos += len(part)
    return sentences if sentences else [(paragraph, 0, len(paragraph))]


def _mask_string(s: str, keep_spaces: bool = True) -> str:
    """Replace every character with X; optionally keep spaces."""
    if keep_spaces:
        return "".join(" " if c.isspace() else "X" for c in s)
    return "X" * len(s)


def _snippet_around_match(text: str, start: int, end: int, max_before: int = 120, max_after: int = 120, max_total: int = 400) -> str:
    """Extract a short context around a match; replace the match with [M] for privacy."""
    before_start = max(0, start - max_before)
    after_end = min(len(text), end + max_after)
    s = text[before_start:after_end]
    # Replace the matched word with [M]
    rel_start = start - before_start
    rel_end = end - before_start
    s = s[:rel_start] + "[M]" + s[rel_end:]
    # Collapse newlines and limit
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
    debug_info: matched (list of {w, s}), counts, snippet (when block_page).
    """
    empty_debug: Dict[str, Any] = {"matched": [], "counts": {"light": 0, "medium": 0, "severe": 0}, "snippet": ""}
    if not text.strip():
        return text, False, "", empty_debug

    # Use both languages for matching (page may be mixed)
    langs = list(SUPPORTED_LANGS) if lang_hint is None else [lang_hint]

    # Build severity per character range: (start, end, severity)
    word_severities: List[Tuple[int, int, int]] = []
    for word, start, end in _tokenize_words(text):
        max_sev = 0
        for lang in langs:
            sev = _get_word_severity(word, lang)
            if sev > max_sev:
                max_sev = sev
        if max_sev:
            word_severities.append((start, end, max_sev))

    block_page = False
    block_reason = ""
    count_light_page = sum(1 for _, _, sev in word_severities if sev == SEVERITY_LIGHT)
    count_medium_page = sum(1 for _, _, sev in word_severities if sev == SEVERITY_MEDIUM)
    count_severe_page = sum(1 for _, _, sev in word_severities if sev == SEVERITY_SEVERE)
    counts = {"light": count_light_page, "medium": count_medium_page, "severe": count_severe_page}
    matched = [{"w": text[s:e], "s": sev} for s, e, sev in word_severities[:30]]
    debug_info: Dict[str, Any] = {"matched": matched, "counts": counts, "snippet": ""}

    logger.debug(
        "text_filter: plain_text matches len=%s light=%s medium=%s severe=%s",
        len(word_severities), count_light_page, count_medium_page, count_severe_page,
    )
    if ANY_SEVERITY_3_BLOCKS_PAGE and count_severe_page > 0:
        block_page = True
        words_sev3 = list(dict.fromkeys([text[s:e] for s, e, sev in word_severities if sev == SEVERITY_SEVERE]))[:15]
        block_reason = "severity_3: " + ", ".join(words_sev3)
        first = next(( (s, e) for s, e, sev in word_severities if sev == SEVERITY_SEVERE ), (0, 0))
        if first != (0, 0):
            debug_info["snippet"] = _snippet_around_match(text, first[0], first[1])
        logger.debug("text_filter: block_page=True (severity 3 present): %s", block_reason)
    elif count_light_page >= THRESHOLD_PAGE_LIGHT:
        block_page = True
        block_reason = "too_many_light_in_page (%d >= %d)" % (count_light_page, THRESHOLD_PAGE_LIGHT)
        first = next(( (s, e) for s, e, sev in word_severities if sev == SEVERITY_LIGHT ), (0, 0))
        if first != (0, 0):
            debug_info["snippet"] = _snippet_around_match(text, first[0], first[1])
        logger.debug("text_filter: block_page=True (light count %s >= %s)", count_light_page, THRESHOLD_PAGE_LIGHT)
    elif count_medium_page >= THRESHOLD_PAGE_MEDIUM_BLOCK:
        block_page = True
        block_reason = "too_many_medium_in_page (%d >= %d)" % (count_medium_page, THRESHOLD_PAGE_MEDIUM_BLOCK)
        first = next(( (s, e) for s, e, sev in word_severities if sev == SEVERITY_MEDIUM ), (0, 0))
        if first != (0, 0):
            debug_info["snippet"] = _snippet_around_match(text, first[0], first[1])
        logger.debug("text_filter: block_page=True (medium count %s >= %s)", count_medium_page, THRESHOLD_PAGE_MEDIUM_BLOCK)

    # Replace words with X's (by length)
    arr = list(text)
    for start, end, _ in word_severities:
        for i in range(start, end):
            arr[i] = "X"
    text_replaced = "".join(arr)

    # Paragraph boundaries (keep separator so positions match text_replaced)
    parts = re.split(r"(\n\s*\n)", text_replaced)
    para_boundaries: List[Tuple[int, int]] = []
    pos = 0
    for i, part in enumerate(parts):
        if i % 2 == 0 and part:
            para_boundaries.append((pos, pos + len(part)))
        pos += len(part)

    # Per-sentence: count light words; if >= THRESHOLD_SENTENCE_LIGHT, mask whole sentence
    result = list(text_replaced)
    for pstart, pend in para_boundaries:
        para_text = text_replaced[pstart:pend]
        sentences = _split_sentences(para_text)
        light_in_para = 0
        for sent, sstart, send in sentences:
            abs_start = pstart + sstart
            abs_end = pstart + send
            count_light = sum(
                1 for ws, we, sev in word_severities
                if sev == SEVERITY_LIGHT and ws >= abs_start and we <= abs_end
            )
            light_in_para += count_light
            if count_light >= THRESHOLD_SENTENCE_LIGHT:
                masked = _mask_string(para_text[sstart:send])
                for j, c in enumerate(masked):
                    if abs_start + j < len(result):
                        result[abs_start + j] = c

        if light_in_para >= THRESHOLD_PARAGRAPH_LIGHT:
            masked = _mask_string(para_text)
            for j, c in enumerate(masked):
                if pstart + j < len(result):
                    result[pstart + j] = c

    return "".join(result), block_page, block_reason, debug_info


def _encode_debug_b64(debug: Dict[str, Any]) -> str:
    """Encode full debug dict to base64 for display on blocked page (decode for full debugging)."""
    try:
        js = json.dumps(debug, ensure_ascii=False)
        return base64.b64encode(js.encode("utf-8")).decode("ascii")
    except Exception:
        return ""


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
        debug_info: url, content_type, block_reason, matched, counts, snippet (for full debug / base64).
    """
    empty_debug: Dict[str, Any] = {"url": url, "content_type": content_type, "block_reason": "", "matched": [], "counts": {}, "snippet": ""}
    logger.debug("text_filter: filter_text_content url=%r content_type=%r len=%s text_filter_enabled=%s", url, content_type, len(content), text_filter_enabled)
    if not text_filter_enabled:
        logger.debug("text_filter: skipped (text_filter_enabled=False)")
        return content, False, "", empty_debug

    try:
        # Decode
        if "charset=" in (content_type or ""):
            # Simple: try common encodings
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


# Tag names whose text content must not be filtered (would break page: JS, CSS, etc.)
_SKIP_FILTER_TAGS = frozenset(("script", "style", "noscript", "template", "xmp", "iframe"))

def _is_inside_skip_tag(node) -> bool:
    """True if this node is inside script, style, etc. – do not filter so we don't break the page."""
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
    Parse HTML, filter each text node (point-wise: replace words with X's per node).
    Skips text inside script, style, noscript, template, etc. so the page structure and behavior are preserved.
    Block page only when content is spread (trend): many separate HTML elements have matches.
    If matches are in one or few elements → only those nodes are filtered; page not blocked.
    """
    empty_debug: Dict[str, Any] = {"matched": [], "counts": {"light": 0, "medium": 0, "severe": 0}, "snippet": ""}
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("BeautifulSoup4 not available; filtering as plain text")
        filtered, block_page, block_reason, debug_info = _filter_plain_text(html_text)
        return filtered.encode("utf-8"), block_page, block_reason, debug_info

    soup = BeautifulSoup(html_text, "html.parser")
    merged_matched: List[Dict[str, Any]] = []
    merged_counts = {"light": 0, "medium": 0, "severe": 0}
    first_snippet = ""
    # Per-node counts: how many nodes (HTML elements) have at least one match of each severity
    per_node_counts: List[Dict[str, int]] = []

    from bs4 import NavigableString

    for node in soup.descendants:
        if isinstance(node, NavigableString) and node.strip():
            if _is_inside_skip_tag(node):
                continue
            s = str(node)
            filtered, _block_ignored, reason, debug_info = _filter_plain_text(s)
            c = debug_info.get("counts", {})
            light = c.get("light", 0)
            medium = c.get("medium", 0)
            severe = c.get("severe", 0)
            if light or medium or severe:
                per_node_counts.append({"light": light, "medium": medium, "severe": severe})
                for m in debug_info.get("matched", [])[:20]:
                    merged_matched.append(m)
                merged_counts["light"] += light
                merged_counts["medium"] += medium
                merged_counts["severe"] += severe
                if debug_info.get("snippet") and not first_snippet:
                    first_snippet = debug_info["snippet"]
            if filtered != s:
                node.replace_with(filtered)

    # Spread logic: block page only when matches are in many separate elements (trend)
    total_s1 = merged_counts.get("light", 0)
    total_s2 = merged_counts.get("medium", 0)
    total_s3 = merged_counts.get("severe", 0)
    blocks_with_s1 = sum(1 for c in per_node_counts if c.get("light", 0) > 0)
    blocks_with_s2 = sum(1 for c in per_node_counts if c.get("medium", 0) > 0)
    blocks_with_s3 = sum(1 for c in per_node_counts if c.get("severe", 0) > 0)

    block_page = False
    block_reason = ""
    if total_s3 >= 1:
        if blocks_with_s3 >= MIN_BLOCKS_SEVERE_FOR_PAGE_BLOCK or total_s3 >= MIN_TOTAL_SEVERE_FOR_PAGE_BLOCK:
            block_page = True
            block_reason = "severity_3_spread: %d blocks, %d total" % (blocks_with_s3, total_s3)
    if not block_page and total_s2 >= THRESHOLD_PAGE_MEDIUM_BLOCK and blocks_with_s2 >= MIN_BLOCKS_MEDIUM_FOR_PAGE_BLOCK:
        block_page = True
        block_reason = "too_many_medium_spread: %d blocks, %d total (>= %d)" % (
            blocks_with_s2, total_s2, THRESHOLD_PAGE_MEDIUM_BLOCK,
        )
    if not block_page and total_s1 >= THRESHOLD_PAGE_LIGHT and blocks_with_s1 >= MIN_BLOCKS_LIGHT_FOR_PAGE_BLOCK:
        block_page = True
        block_reason = "too_many_light_spread: %d blocks, %d total (>= %d)" % (
            blocks_with_s1, total_s1, THRESHOLD_PAGE_LIGHT,
        )

    out_debug: Dict[str, Any] = {
        "matched": merged_matched[:50],
        "counts": merged_counts,
        "snippet": first_snippet,
        "blocks_with": {"light": blocks_with_s1, "medium": blocks_with_s2, "severe": blocks_with_s3},
    }
    logger.debug(
        "text_filter: _filter_html block_page=%s reason=%s blocks_s1=%s s2=%s s3=%s",
        block_page, block_reason, blocks_with_s1, blocks_with_s2, blocks_with_s3,
    )

    out = str(soup)
    if soup.original_encoding:
        return out.encode(soup.original_encoding), block_page, block_reason, out_debug
    return out.encode("utf-8"), block_page, block_reason, out_debug
