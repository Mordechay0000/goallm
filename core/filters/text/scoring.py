"""
Hidden score of a page – how the text filter decides without a language model.

Every hard or suspicious word / phrase has a weight (lexicon.py). The decision is built from:
1. Diminishing returns per term: the first occurrence counts fully, each further one half, up to 2.5× the
   weight. A news story that says "הטרדה מינית" five times is not five suspicious words – immodest text
   uses MANY DIFFERENT such words.
2. Diversity: three or more different terms together multiply the score (TEXT_DIVERSITY_BONUS).
3. Locality: the highest score in any window of TEXT_WINDOW_WORDS words. A cluster in one article or one
   comment counts in full; the same words scattered across a long portal page do not add up to a block.
4. Context: on a page dense with Torah / halacha markers (פסוק, רש"י, Leviticus…) suspicious – not hard – words count
   TEXT_CONTEXT_FACTOR of their weight; with medical markers TEXT_MEDICAL_FACTOR (weaker, so a "sex-ed" page in
   medical dress still counts most). Hard words (להט"ב…) count fully in any context.
5. Titles and headings: TEXT_TITLE_FACTOR.

Decision: window score ≥ TEXT_WINDOW_BLOCK_SCORE, or whole-page score ≥ TEXT_PAGE_BLOCK_SCORE.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from core.filters.text.lexicon import HARD, MARKER, MEDICAL, SCORED, Match
from data.constants import (
    TEXT_CONTEXT_FACTOR,
    TEXT_CONTEXT_MIN_DENSITY,
    TEXT_CONTEXT_MIN_MARKERS,
    TEXT_DIVERSITY_BONUS,
    TEXT_MEDICAL_FACTOR,
    TEXT_PAGE_BLOCK_SCORE,
    TEXT_WINDOW_BLOCK_SCORE,
    TEXT_WINDOW_WORDS,
)

_REPEAT_FACTOR = 0.5
_TERM_CAP = 2.5


@dataclass
class Scored:
    """A match placed in the document: global token position and an extra factor (title / heading)."""
    match: Match
    pos: int
    factor: float = 1.0


@dataclass
class PageScore:
    total: float = 0.0
    window_max: float = 0.0
    window_start: int = 0
    context_factor: float = 1.0
    markers: int = 0
    words: int = 0
    top_terms: List[Tuple[str, float]] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return self.window_max >= TEXT_WINDOW_BLOCK_SCORE or self.total >= TEXT_PAGE_BLOCK_SCORE

    def reason(self) -> str:
        terms = ", ".join(f"{t} ({s:.1f})" for t, s in self.top_terms[:6])
        ctx = f", context ×{self.context_factor:g}" if self.context_factor != 1.0 else ""
        return f"score: window {self.window_max:.1f} / {TEXT_WINDOW_BLOCK_SCORE:g}, page {self.total:.1f} / {TEXT_PAGE_BLOCK_SCORE:g}{ctx} – {terms}"


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
    if len(per_term) >= 3:
        score *= TEXT_DIVERSITY_BONUS
    return score, dict(per_term)


def score_page(items: Sequence[Scored], words: int) -> PageScore:
    items = sorted(items, key=lambda it: it.pos)
    markers = sum(1 for it in items if it.match.term.kind == MARKER)
    ctx = context_factor(markers, words, sum(1 for it in items if it.match.term.kind == MEDICAL))
    weighted = [it for it in items if it.match.term.kind in (HARD, SCORED) and it.match.term.weight > 0]
    total, per_term = set_score(weighted, ctx)
    best, best_start = 0.0, 0
    j = 0
    for i, first in enumerate(weighted):  # windows that start at each match
        if j < i:
            j = i
        while j < len(weighted) and weighted[j].pos < first.pos + TEXT_WINDOW_WORDS:
            j += 1
        s, _ = set_score(weighted[i:j], ctx)
        if s > best:
            best, best_start = s, first.pos
    top = sorted(per_term.items(), key=lambda kv: -kv[1])
    return PageScore(total=total, window_max=best, window_start=best_start, context_factor=ctx,
                     markers=markers, words=words, top_terms=top)
