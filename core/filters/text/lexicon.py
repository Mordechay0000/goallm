"""
Word lists and matching for the text filter – no language model.

Three lists per language (core/filters/text/word_lists/<lang>/):
- blocked.txt  hard words / phrases: masked (XXX) wherever they appear, and weigh heavily in the page score.
- scored.txt   suspicious words / phrases with a weight: never masked – a hidden score that only counts in sum
               (scoring.py). Weight 0 = a neutral phrase that absorbs its words ("מין העובר", "carbon dating").
- context.txt  Torah / halacha markers: when a page is full of them, scored (not hard) words count less
               ("ויהיו שניהם ערומים" in a parsha sheet is not an immodest page).
- medical.txt  medical markers: the same, with a weaker factor (a breast-cancer article, not a "sex-ed" page).

Line format: `word` or `several words`, optionally followed by a number (the weight). "=word" = exact (no
inflections / stemming). Lines starting with # are comments.

Matching:
- Hebrew: the listed word or one of its own inflections (ים / ות / ית / יות / י, built from the LISTED word), behind
  up to three prefix letters (ו ה ב ל כ מ ש). Tokens are never trimmed, so "אהבו" cannot collide with "מאהב".
- English: the word, or the same Snowball stem.
- Phrases: consecutive tokens; the first may carry prefix letters, the last may be inflected.
- Evasions: invisible characters inside a word, look-alike letters from other scripts, "s.e.x" / "ס-ק-ס",
  leetspeak (p0rn, $exy), stretched letters (poooorn).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from data.constants import TEXT_HARD_WEIGHT

logger = logging.getLogger(__name__)

WORD_LISTS_DIR = Path(__file__).resolve().parent / "word_lists"
LANGS = ("he", "en")

try:
    import snowballstemmer

    _stemmer_en = snowballstemmer.EnglishStemmer()
except ImportError:  # pragma: no cover
    _stemmer_en = None
    logger.warning("snowballstemmer not installed – English words match exactly only")

HARD, SCORED, NEUTRAL, MARKER, MEDICAL = "hard", "scored", "neutral", "marker", "medical"


@dataclass(frozen=True)
class Term:
    key: str       # the listed text (reporting, and per-term diminishing returns in scoring)
    weight: float
    kind: str      # hard | scored | neutral | marker
    lang: str


@dataclass
class Match:
    start: int     # positions in the ORIGINAL text
    end: int
    text: str
    term: Term
    token: int     # index of the first token (for windows)


@dataclass
class _Lexicon:
    single: Dict[str, Term] = field(default_factory=dict)   # normalized form → term
    stems: Dict[str, Term] = field(default_factory=dict)    # English stem → term
    phrases: Dict[str, List[Tuple[Tuple[str, ...], Term]]] = field(default_factory=dict)  # first word → phrases


# ---------- normalization ----------

_HE_PREFIX_LETTERS = frozenset("והבלכמש")
_HE_SUFFIXES = ("ים", "ות", "ית", "יות", "י", "יים")
_HE_FINAL_SUFFIXES = ("ות", "ים", "ית", "יות")  # for words ending in ה / ת (replace the last letter)
_FINALS = str.maketrans({"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"})
_NIQQUD = re.compile(r"[֑-ׇ]")


def normalize_hebrew(word: str) -> str:
    """No niqqud / cantillation, one geresh / gershayim form, final letters as regular ones."""
    s = _NIQQUD.sub("", word)
    s = s.replace("״", '"').replace("׳", "'").replace("”", '"').replace("’", "'")
    return s.translate(_FINALS)


def _is_hebrew(word: str) -> bool:
    return any("א" <= c <= "ת" for c in word)


def _norm(word: str) -> str:
    return normalize_hebrew(word) if _is_hebrew(word) else word.lower()


def _he_forms(word: str) -> set:
    forms = {word} | {word + suf for suf in _HE_SUFFIXES}
    if word[-1:] in ("ה", "ת"):
        forms |= {word[:-1] + suf for suf in _HE_FINAL_SUFFIXES}
    return {normalize_hebrew(f) for f in forms}


def _stem(word: str) -> str:
    return _stemmer_en.stemWord(word) if _stemmer_en else word


# ---------- loading ----------

_cache: Dict[str, _Lexicon] = {}
_KIND_BY_FILE = (("medical.txt", MEDICAL), ("context.txt", MARKER), ("scored.txt", SCORED), ("blocked.txt", HARD))  # later win


def _parse_line(line: str, default_weight: float) -> Optional[Tuple[List[str], bool, float]]:
    text = line.split("#")[0].strip()
    if not text:
        return None
    parts = text.split()
    weight = default_weight
    try:
        weight = float(parts[-1])
        parts = parts[:-1]
    except ValueError:
        pass
    if not parts:
        return None
    exact = parts[0].startswith("=")
    parts[0] = parts[0].lstrip("=")
    return [p for p in parts if p], exact, weight


def _add(lex: _Lexicon, lang: str, words: List[str], exact: bool, weight: float, kind: str) -> None:
    if weight == 0 and kind == SCORED:
        kind = NEUTRAL
    term = Term(" ".join(words), weight if kind in (HARD, SCORED) else 0.0, kind, lang)
    normed = [_norm(w) for w in words]
    if len(normed) > 1:
        lex.phrases.setdefault(normed[0], []).append((tuple(normed), term))
        lex.phrases[normed[0]].sort(key=lambda p: -len(p[0]))  # longest phrase first
        return
    w = normed[0]
    if lang == "he" and not exact:
        for f in _he_forms(w):
            lex.single[f] = term
    else:
        lex.single[w] = term
        if lang == "en" and not exact:
            lex.stems[_stem(w)] = term


def load(lang: str) -> _Lexicon:
    if lang in _cache:
        return _cache[lang]
    lex = _Lexicon()
    for filename, kind in _KIND_BY_FILE:
        path = WORD_LISTS_DIR / lang / filename
        if not path.exists():
            continue
        default = TEXT_HARD_WEIGHT if kind == HARD else (1.0 if kind == SCORED else 0.0)
        for line in path.read_text(encoding="utf-8").splitlines():
            parsed = _parse_line(line, default)
            if parsed:
                _add(lex, lang, parsed[0], parsed[1], parsed[2], kind)
    _cache[lang] = lex
    return lex


def reload() -> None:
    _cache.clear()


# ---------- single words ----------

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


def _lookup_he(lex: _Lexicon, w: str) -> Optional[Term]:
    for k in range(0, min(3, max(0, len(w) - 2)) + 1):
        if k and w[k - 1] not in _HE_PREFIX_LETTERS:
            break
        term = lex.single.get(w[k:])
        if term is not None:
            return term
    return None


def lookup_word(word: str, lang: str) -> Optional[Term]:
    lex = load(lang)
    for v in _variants(word, lang):
        if lang == "he":
            term = _lookup_he(lex, normalize_hebrew(v))
        else:
            w = v.lower()
            term = lex.single.get(w) or lex.stems.get(_stem(w))
        if term is not None:
            return term
    return None


# ---------- tokens ----------

_INVISIBLE = set("­​‌‍‎‏⁠⁡⁢⁣⁤﻿͏᠎")
_HOMOGLYPHS = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y", "к": "k", "м": "m", "т": "t",
    "в": "b", "н": "h", "і": "i", "ј": "j", "ѕ": "s", "А": "A", "Е": "E", "О": "O", "Р": "P", "С": "C",
    "Х": "X", "У": "Y", "К": "K", "М": "M", "Т": "T", "В": "B", "Н": "H", "І": "I", "Ѕ": "S",
    "α": "a", "ε": "e", "ο": "o", "ρ": "p", "χ": "x", "ν": "v", "ι": "i", "κ": "k", "τ": "t",
    "Α": "A", "Ε": "E", "Ο": "O", "Ρ": "P", "Χ": "X", "Ι": "I", "Κ": "K", "Τ": "T", "Ν": "N",
})
_HE_CH = "[א-ת֑-ׇֽֿׁׂׅׄ]"
_TOKEN_RE = re.compile(rf"{_HE_CH}+(?:[\"'׳״]{_HE_CH}+)*|[a-zA-Z0-9@$]+")
_SPACED_RE = re.compile(r"(?<![\w֐-׿])(?:[A-Za-zא-ת][ .\-_*·•]){2,}[A-Za-zא-ת](?![\w֐-׿])")


def tokenize(text: str) -> List[Tuple[str, int, int]]:
    """(word, start, end). A Hebrew word keeps an inner geresh / gershayim / quote (להט"ב, טרנסג'נדר); the maqaf
    of Tanakh text separates words; @ and $ count as letters in English ($ex)."""
    return [(m.group(0), m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]


def _normalize_for_matching(text: str) -> Tuple[str, List[int]]:
    chars: List[str] = []
    index: List[int] = []
    for i, c in enumerate(text):
        if c in _INVISIBLE:
            continue
        chars.append(c)
        index.append(i)
    return "".join(chars).translate(_HOMOGLYPHS), index


def _phrase_at(tokens: List[Tuple[str, int, int]], i: int, langs: Sequence[str]) -> Optional[Tuple[int, Term]]:
    """Longest phrase starting at token i → (index of its last token, term)."""
    first = tokens[i][0]
    for lang in langs:
        lex = load(lang)
        if not lex.phrases:
            continue
        if lang == "he":
            if not _is_hebrew(first):
                continue
            w = normalize_hebrew(first)
            bases = [w[k:] for k in range(0, min(3, max(0, len(w) - 1)) + 1) if k == 0 or all(c in _HE_PREFIX_LETTERS for c in w[:k])]
        else:
            if _is_hebrew(first):
                continue
            bases = [first.lower()]
        for base in bases:
            for words, term in lex.phrases.get(base, ()):
                n = len(words)
                if i + n > len(tokens):
                    continue
                ok = True
                for j in range(1, n):
                    tok = _norm(tokens[i + j][0])
                    want = words[j]
                    if tok == want:
                        continue
                    last = j == n - 1
                    if lang == "he" and tok.startswith("ה") and len(tok) > 2:
                        bare = tok[1:]  # definite article on an agreeing word: "הרומן האסור", "ההלבשה התחתונה"
                        if bare == want or (last and bare in _he_forms(want)):
                            continue
                    if last and lang == "he" and tok in _he_forms(want):
                        continue
                    if last and lang == "en" and _stem(tok) == _stem(want):
                        continue
                    ok = False
                    break
                if ok:
                    return i + n - 1, term
    return None


def find_terms(text: str, langs: Sequence[str] = LANGS) -> Tuple[List[Match], int]:
    """All listed words / phrases / markers in text (non-overlapping, in order) and the number of tokens."""
    norm, index = _normalize_for_matching(text)
    tokens = tokenize(norm)
    found: List[Tuple[int, int, Term, int]] = []
    i = 0
    while i < len(tokens):
        phrase = _phrase_at(tokens, i, langs)
        if phrase is not None:
            j, term = phrase
            found.append((tokens[i][1], tokens[j][2], term, i))
            i = j + 1
            continue
        word, s, e = tokens[i]
        lang_order = [lang for lang in langs if (lang == "he") == _is_hebrew(word)]
        for lang in lang_order:
            term = lookup_word(word, lang)
            if term is not None:
                found.append((s, e, term, i))
                break
        i += 1
    # "s e x" / "ס-ק-ס": single letters with separators
    taken = [(s, e) for s, e, _, _ in found]
    for m in _SPACED_RE.finditer(norm):
        joined = "".join(c for c in m.group(0) if c.isalpha())
        lang = "he" if _is_hebrew(joined) else "en"
        if lang not in langs:
            continue
        term = lookup_word(joined, lang)
        if term is None or any(not (m.end() <= s or m.start() >= e) for s, e in taken):
            continue
        tok = sum(1 for _, ts, _ in tokens if ts < m.start())
        found.append((m.start(), m.end(), term, tok))
    found.sort(key=lambda f: f[0])
    out: List[Match] = []
    for s, e, term, tok in found:
        o_start, o_end = index[s], index[e - 1] + 1
        if out and o_start < out[-1].end:
            continue
        out.append(Match(o_start, o_end, text[o_start:o_end], term, tok))
    return out, len(tokens)


def hard_matches(text: str, langs: Sequence[str] = LANGS) -> List[Match]:
    return [m for m in find_terms(text, langs)[0] if m.term.kind == HARD]
