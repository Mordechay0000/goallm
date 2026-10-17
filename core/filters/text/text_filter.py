"""
סינון מלל (text filtering) – סינון לחרדים.

- רמה אחת: מילה ברשימה = תוכן לא צנוע. חסימה לפי יחס על כל הדף/מסמך.
- החלפת מילה באיקסים (לפי אורך). תמיכה בעברית ובאנגלית (רשימות ב־word_lists/*/blocked.txt).
- התאמה דקדוקית: בעברית – צורות הנטייה של המילה שברשימה + אותיות שימוש (ו ה ב ל כ מ ש); באנגלית – stemming.
- כלל לרשימות: אין בהן מילה שמופיעה בהקשר מותר (תורה והלכה, חדשות חרדיות, רפואה, טפסים, משמעות יומיומית).
  בדיקה: python -m tools.check_word_list <קבצי טקסט מותר>.
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
from data.constants import TEXT_LLM_MAX_CHARS, TEXT_LLM_MIN_MATCHES, TEXT_LLM_REVIEW

logger = logging.getLogger(__name__)

# Optional stemmer for English (snowballstemmer has no Hebrew)
_stemmer_en = None
try:
    import snowballstemmer
    _stemmer_en = snowballstemmer.EnglishStemmer()
except ImportError:
    logger.debug("snowballstemmer not installed; using exact match only (pip install snowballstemmer for stemming)")

# Hebrew: a listed word matches only as itself or as one of its own inflections (suffix forms generated from
# the LISTED word), with up to three real prefix letters in front (ו ה ב ל כ מ ש). The old matcher stripped
# letters off every token instead, which made innocent words collide with listed ones: "אהבו" ("liked") →
# "אהב" ← "מאהב", "ישבנו" ("we sat") → "ישבנ" ← "ישבן". Measured on Torah and Haredi-news text (tools/check_word_list).
_HE_PREFIX_LETTERS = frozenset("והבלכמש")
_HE_SUFFIXES = ("ים", "ות", "ית", "יות", "י", "יים")
_HE_FINAL_SUFFIXES = ("ות", "ים", "ית", "יות")  # for words ending in ה / ת (replace the last letter)

# cache: lang -> {"forms": set, "exact": set, "stems": set}
_word_list_cache: Dict[str, Dict[str, set]] = {}


def _normalize_hebrew(word: str) -> str:
    """Strip niqqud / cantillation, unify geresh / gershayim, and final letters: ך→כ, ם→מ, ן→נ, ף→פ, ץ→צ."""
    s = re.sub(r"[\u0591-\u05C7\u05C0-\u05C3\u05C4-\u05C5]", "", word)
    s = s.replace("\u05F4", '"').replace("\u05F3", "'").replace("\u201D", '"').replace("\u2019", "'")
    final_to_regular = {"\u05da": "\u05db", "\u05dd": "\u05de", "\u05df": "\u05e0", "\u05e3": "\u05e4", "\u05e5": "\u05e6"}
    for fin, reg in final_to_regular.items():
        s = s.replace(fin, reg)
    return s


def _he_forms(word: str) -> set:
    forms = {word} | {word + suf for suf in _HE_SUFFIXES}
    if word[-1:] in ("ה", "ת"):
        forms |= {word[:-1] + suf for suf in _HE_FINAL_SUFFIXES}
    return {_normalize_hebrew(f) for f in forms}  # tokens are normalized too (final ם → מ in "ים")


def _load_blocked_words(lang: str) -> Dict[str, set]:
    """Load the list for lang (cached). A line "=word" matches exactly (no inflections / stemming)."""
    if lang in _word_list_cache:
        return _word_list_cache[lang]
    data: Dict[str, set] = {"forms": set(), "exact": set(), "stems": set()}
    path = WORD_LISTS_DIR / lang / BLOCKED_WORDS_FILENAME
    if path.exists():
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                w = line.split("#")[0].strip()
                if not w:
                    continue
                exact = w.startswith("=")
                w = w.lstrip("=").strip()
                n = w.lower() if lang == "en" else _normalize_hebrew(w)
                if exact:
                    data["exact"].add(n)
                elif lang == "he":
                    data["forms"] |= _he_forms(n)
                else:
                    data["forms"].add(n)
                    if _stemmer_en:
                        data["stems"].add(_stemmer_en.stemWord(n))
        except Exception as e:
            logger.warning("Failed to load word list %s: %s", path, e)
    _word_list_cache[lang] = data
    return data


def _is_listed_exact(word: str, lang: str) -> bool:
    data = _load_blocked_words(lang)
    if lang == "en":
        w = word.lower()
        if w in data["exact"] or w in data["forms"]:
            return True
        return bool(_stemmer_en) and _stemmer_en.stemWord(w) in data["stems"]
    w = _normalize_hebrew(word)
    for k in range(0, min(3, max(0, len(w) - 2)) + 1):
        if k and w[k - 1] not in _HE_PREFIX_LETTERS:
            break
        rest = w[k:]
        if rest in data["exact"] or rest in data["forms"]:
            return True
    return False


# --- evasion: s3x, $ex, seeexxx (a listed word written so a plain lookup misses it) ---
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b", "9": "g", "@": "a", "$": "s"})
_REPEATS = re.compile(r"(.)\1{2,}")


def _variants(word: str, lang: str) -> List[str]:
    out = [word]
    if _REPEATS.search(word):
        out += [_REPEATS.sub(r"\1", word), _REPEATS.sub(r"\1\1", word)]
    if lang == "en" and re.search(r"[0-9@$]", word) and re.search(r"[A-Za-z]", word):
        leet = word.lower().translate(_LEET)
        out += [leet, leet.replace("i", "l")]
    return out


def _is_listed(word: str, lang: str) -> bool:
    """Return True if word (or its stem, or an evasive spelling of it) is in blocked list for this language."""
    return any(_is_listed_exact(v, lang) for v in _variants(word, lang))


# --- evasion: invisible characters inside a word, and look-alike letters from other scripts ---
_INVISIBLE = set("\u00ad\u200b\u200c\u200d\u200e\u200f\u2060\u2061\u2062\u2063\u2064\ufeff\u034f\u180e")
_HOMOGLYPHS = str.maketrans({
    # Cyrillic
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y", "к": "k", "м": "m", "т": "t",
    "в": "b", "н": "h", "і": "i", "ј": "j", "ѕ": "s", "А": "A", "Е": "E", "О": "O", "Р": "P", "С": "C",
    "Х": "X", "У": "Y", "К": "K", "М": "M", "Т": "T", "В": "B", "Н": "H", "І": "I", "Ѕ": "S",
    # Greek
    "α": "a", "ε": "e", "ο": "o", "ρ": "p", "χ": "x", "ν": "v", "ι": "i", "κ": "k", "τ": "t",
    "Α": "A", "Ε": "E", "Ο": "O", "Ρ": "P", "Χ": "X", "Ι": "I", "Κ": "K", "Τ": "T", "Ν": "N",
})


def _normalize_for_matching(text: str) -> Tuple[str, List[int]]:
    """Text with invisible chars removed and look-alikes mapped (1:1), plus norm-index → original-index map."""
    chars: List[str] = []
    index: List[int] = []
    for i, c in enumerate(text):
        if c in _INVISIBLE:
            continue
        chars.append(c)
        index.append(i)
    return "".join(chars).translate(_HOMOGLYPHS), index


# "s e x", "s.e.x", "ס-ק-ס": single letters with one separator between them
_SPACED_RE = re.compile(r"(?<![\w\u0590-\u05FF])(?:[A-Za-z\u05D0-\u05EA][ .\-_*·•]){2,}[A-Za-z\u05D0-\u05EA](?![\w\u0590-\u05FF])")


def _spaced_matches(norm: str, langs: List[str]) -> List[Tuple[int, int]]:
    out = []
    for m in _SPACED_RE.finditer(norm):
        joined = "".join(c for c in m.group(0) if c.isalpha())
        if any(_is_listed(joined, lang) for lang in langs):
            out.append((m.start(), m.end()))
    return out


_HE_CH = "[\u05D0-\u05EA\u0591-\u05BD\u05BF\u05C1\u05C2\u05C4\u05C5\u05C7]"
_TOKEN_RE = re.compile(rf"{_HE_CH}+(?:[\"'\u05F3\u05F4]{_HE_CH}+)*|[a-zA-Z0-9@$]+")


def _tokenize_words(text: str) -> List[Tuple[str, int, int]]:
    """(word, start, end) for Hebrew and English words. A Hebrew word keeps an inner geresh / gershayim / quote
    (להט"ב, טרנסג'נדר); the maqaf of Tanakh text separates words. @ and $ count as letters in English ($ex)."""
    return [(m.group(0), m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]


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
    ranges = _find_matches(text, langs)
    if not ranges:
        return text, False
    arr = list(text)
    for start, end, _ in ranges:
        for i in range(start, end):
            arr[i] = "X"
    return "".join(arr), True


def _find_matches(text: str, langs: List[str]) -> List[Tuple[int, int, str]]:
    """Listed words in text as (start, end, original_text) in ORIGINAL positions – evasive spellings included."""
    norm, index = _normalize_for_matching(text)
    found: List[Tuple[int, int]] = []
    for word, start, end in _tokenize_words(norm):
        if any(_is_listed(word, lang) for lang in langs):
            found.append((start, end))
    for start, end in _spaced_matches(norm, langs):
        found.append((start, end))
    out = []
    for start, end in sorted(set(found)):
        o_start, o_end = index[start], index[end - 1] + 1
        if out and o_start < out[-1][1]:
            continue  # overlaps a match already taken
        out.append((o_start, o_end, text[o_start:o_end]))
    return out


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

    # Find all matched words (in original positions, so masking hits the right characters)
    total_words = len(_tokenize_words(text))
    matched_ranges: List[Tuple[int, int, str]] = _find_matches(text, langs)

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
        text, used_encoding = _decode_body(content, content_type)

        ct_lower = (content_type or "").lower()
        is_json = "application/json" in ct_lower or (
            text.strip().startswith("{") or text.strip().startswith("[")
        )
        if is_json:
            logger.debug("text_filter: treating as JSON (content_type=%s)", content_type)
            out_bytes, debug_info = _filter_json(text, url, content_type)
            if out_bytes == text.encode("utf-8"):
                out_bytes = content  # unchanged: original bytes, original charset
            elif used_encoding.lower().replace("_", "-") not in ("utf-8", "utf8"):
                out_bytes = _encode_like_source(out_bytes.decode("utf-8"), used_encoding, html=False)
            block_page = False
            block_reason = ""
        else:
            is_html = "<" in text and ">" in text and ("<html" in text.lower() or "<body" in text.lower() or "<div" in text.lower())
            logger.debug("text_filter: decoded len=%s is_html=%s", len(text), is_html)

            if is_html:
                out_bytes, block_page, block_reason, debug_info = _filter_html(text, url, content_type, used_encoding)
                logger.debug("text_filter: _filter_html done block_page=%s reason=%s", block_page, block_reason)
            else:
                filtered, block_page, block_reason, debug_info = _filter_plain_text(text)
                out_bytes = content if filtered == text else _encode_like_source(filtered, used_encoding, html=False)
                logger.debug("text_filter: _filter_plain_text done block_page=%s reason=%s", block_page, block_reason)

        if not is_json and not block_page:
            block_page, block_reason = _llm_second_opinion(
                debug_info, text if not is_html else None, block_page, block_reason
            )
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


def _llm_second_opinion(debug_info: Dict[str, Any], plain_text: Optional[str], block_page: bool, block_reason: str):
    """Borderline page (some listed words, not enough to block) → the language model judges it in context."""
    if not TEXT_LLM_REVIEW:
        return block_page, block_reason
    matched = (debug_info.get("counts") or {}).get("matched", 0)
    if matched < TEXT_LLM_MIN_MATCHES:
        return block_page, block_reason
    from core.filters.text.llm_review import review_text

    verdict = review_text(plain_text if plain_text is not None else debug_info.get("_excerpt", ""))
    if verdict:
        return True, f"llm_review: model judged the page inappropriate ({matched} listed words)"
    return block_page, block_reason


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


def _filter_html(html_text: str, url: str, content_type: str, encoding: str = "utf-8") -> Tuple[bytes, bool, str, Dict[str, Any]]:
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
    excerpt_parts: List[str] = []
    excerpt_len = 0

    from bs4 import NavigableString

    for node in soup.descendants:
        if isinstance(node, NavigableString) and node.strip():
            if _is_inside_skip_tag(node):
                continue
            total_components += 1
            s = str(node)
            if excerpt_len < TEXT_LLM_MAX_CHARS:
                excerpt_parts.append(s.strip())
                excerpt_len += len(s.strip()) + 1
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
        "_excerpt": " ".join(excerpt_parts),
    }
    logger.debug(
        "text_filter: _filter_html block_page=%s reason=%s components=%d/%d",
        block_page, block_reason, components_with_detection, total_components,
    )

    out = soup.decode(eventual_encoding=encoding)  # keeps <meta charset> consistent with the bytes we emit
    # Re-encode in the charset the page declared (windows-1255 Hebrew sites used to come back as UTF-8
    # under a windows-1255 header = garbled text). Characters the charset lacks become &#NNN; refs.
    return _encode_like_source(out, encoding, html=True), block_page, block_reason, out_debug
