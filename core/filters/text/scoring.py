"""
Hidden score – how the text filter decides without a language model.

Every hard or suspicious word / phrase has a weight (lexicon.py): a hard word weighs TEXT_HARD_WEIGHT, at least
twice any suspicious word. The score of a set of matches:
1. Diminishing returns per term: the first occurrence counts fully, each further one half, up to 2.5× the
   weight. A news story that says "הטרדה מינית" five times is not five suspicious words – immodest text
   uses MANY DIFFERENT such words.
2. Diversity: three or more different terms together multiply the score (TEXT_DIVERSITY_BONUS).
3. Context: on a page dense with Torah / halacha markers (פסוק, רש"י, Leviticus…) suspicious – not hard – words count
   TEXT_CONTEXT_FACTOR of their weight; with medical markers TEXT_MEDICAL_FACTOR (weaker, so a "sex-ed" page in
   medical dress still counts most). Hard words (להט"ב…) count fully in any context.
4. Titles and headings: TEXT_TITLE_FACTOR.

One rule at every level – a sentence, a component (heading, search result, teaser, comment, paragraph, list), a
section (a run of problem words, each within TEXT_SECTION_GAP_WORDS words of the next) and the page: a unit is HOT when its score per TEXT_DENSITY_WORDS
words reaches TEXT_DENSITY_SCORE. A unit shorter than TEXT_DENSITY_WORDS counts as that long – one mild word in a
three-word heading is not "dense" – and a long one is judged by its ratio, not by an absolute sum. In other words
the share of problem words a unit needs grows as the unit gets shorter. And a unit needs at least TEXT_MIN_MATCHES
problem words: one word alone never turns its heading / sentence / page into X's.
text_filter.py turns hot units into X's, smallest first, and blocks the page when what is left is still dense
or when most of it was X'd.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from core.filters.text.lexicon import HARD, SCORED, Match
from data.constants import (
    TEXT_CONTEXT_FACTOR,
    TEXT_CONTEXT_MIN_DENSITY,
    TEXT_CONTEXT_MIN_MARKERS,
    TEXT_DENSITY_SCORE,
    TEXT_DENSITY_WORDS,
    TEXT_DIVERSITY_BONUS,
    TEXT_MEDICAL_FACTOR,
    TEXT_MIN_MATCHES,
    TEXT_SECTION_GAP_WORDS,
)

_REPEAT_FACTOR = 0.5
_TERM_CAP = 2.5
DIVERSE_TERMS = 3  # this many different terms together are "many different words" (diversity bonus, page decision)


@dataclass
class Scored:
    """A match placed in the document: global token position, an extra factor (title / heading), and where it sits
    for X-ing (index of its text group and character offset in it)."""
    match: Match
    pos: int
    factor: float = 1.0
    group: int = -1
    off: int = 0
    own: bool = True  # the page's own text; False inside a link (text or image description): judged on the page it
    #                   leads to – X'd all the same, not counted for this page


def weighted(items: Sequence[Scored]) -> List[Scored]:
    return [it for it in items if it.match.term.kind in (HARD, SCORED) and it.match.term.weight > 0]


def _dense(markers: int, words: int) -> bool:
    return markers >= TEXT_CONTEXT_MIN_MARKERS and 1000.0 * markers / max(words, 1) >= TEXT_CONTEXT_MIN_DENSITY


def context_factor(markers: int, words: int, medical: int = 0) -> float:
    """Torah context (strong damping) or medical context (weaker); suspicious words only."""
    if _dense(markers, words):
        return TEXT_CONTEXT_FACTOR
    if _dense(medical, words):
        return TEXT_MEDICAL_FACTOR
    return 1.0


def set_score(items: Sequence[Scored], ctx: float) -> Tuple[float, Dict[str, float]]:
    """Score of a set of matches (diminishing returns per term, diversity bonus). Returns (score, per-term)."""
    per_term: Dict[str, float] = defaultdict(float)
    seen: Dict[str, int] = defaultdict(int)
    for it in items:
        term = it.match.term
        if term.kind not in (HARD, SCORED) or term.weight <= 0:
            continue
        w = term.weight * it.factor * (1.0 if term.kind == HARD else ctx)
        add = w if seen[term.key] == 0 else w * _REPEAT_FACTOR
        seen[term.key] += 1
        per_term[term.key] = min(per_term[term.key] + add, _TERM_CAP * w)
    score = sum(per_term.values())
    if len(per_term) >= DIVERSE_TERMS:
        score *= TEXT_DIVERSITY_BONUS
    return score, dict(per_term)


def density(score: float, words: int) -> float:
    """Score per TEXT_DENSITY_WORDS words; a unit shorter than that counts as that long."""
    return score * TEXT_DENSITY_WORDS / max(words, TEXT_DENSITY_WORDS)


def is_hot(score: float, words: int, matches: int) -> bool:
    return matches >= TEXT_MIN_MATCHES and density(score, words) >= TEXT_DENSITY_SCORE


def _window_end(items: Sequence[Scored], i: int, j: int) -> int:
    while j < len(items) and items[j].pos < items[i].pos + TEXT_DENSITY_WORDS:
        j += 1
    return j


def hot_sections(items: Sequence[Scored], ctx: float) -> List[Tuple[int, int]]:
    """[i, j) runs of position-sorted weighted items, each within TEXT_SECTION_GAP_WORDS words of the next, that are hot
    (a run longer than TEXT_DENSITY_WORDS words is judged by its density)."""
    out: List[Tuple[int, int]] = []
    i = 0
    while i < len(items):
        j = i + 1
        while j < len(items) and items[j].pos - items[j - 1].pos <= TEXT_SECTION_GAP_WORDS:
            j += 1
        if is_hot(set_score(items[i:j], ctx)[0], items[j - 1].pos - items[i].pos + 1, j - i):
            out.append((i, j))
        i = j
    return out


def best_window(items: Sequence[Scored], ctx: float) -> float:
    """Highest score of any TEXT_DENSITY_WORDS-word window (reporting)."""
    best, j = 0.0, 0
    for i in range(len(items)):
        j = _window_end(items, i, max(j, i))
        best = max(best, set_score(items[i:j], ctx)[0])
    return best
