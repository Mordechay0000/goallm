"""
Check the text-filter word lists against texts that must stay OPEN.

Rule for the lists: no listed word may appear in a permitted context (Torah / halacha, Haredi news, medical,
forms, everyday meaning). The way to keep that rule honest is to measure it: collect permitted texts
(text files, one or many) and run

    python -m tools.check_word_list corpus/*.txt [--context 40]

It reports two things:
1. Hard-word matches (masked text) with their context. In permitted text each one is a word to fix – except
   LGBTQ+ terms, which are hard in every context by decision.
2. The hidden score of every document (a file, or each part after a line starting with "### "): which documents
   would be BLOCKED, which would get sentences / paragraphs turned into X's, and the highest scores. In permitted
   text both are false positives to fix.
Exit code 1 when a document would be blocked or X'd.
Run it after every edit of core/filters/text/word_lists/*.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

from core.filters.text.text_filter import _filter_plain_text, _find_matches
from data.constants import SUPPORTED_LANGS


def scan(text: str) -> List[tuple]:
    return _find_matches(text, list(SUPPORTED_LANGS))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--context", type=int, default=40)
    ap.add_argument("--max-per-word", type=int, default=3)
    ap.add_argument("--top", type=int, default=12, help="how many of the highest-scoring documents to list")
    args = ap.parse_args(argv)

    counts: Counter = Counter()
    examples: Dict[str, List[str]] = defaultdict(list)
    total_chars = 0
    for name in args.files:
        text = Path(name).read_text(encoding="utf-8", errors="replace")
        total_chars += len(text)
        for start, end, word in scan(text):
            key = word.lower()
            counts[key] += 1
            if len(examples[key]) < args.max_per_word:
                ctx = text[max(0, start - args.context): end + args.context].replace("\n", " ")
                examples[key].append(f"{Path(name).name}: …{ctx}…")
    print(f"{len(args.files)} files, {total_chars:,} characters of permitted text")
    if not counts:
        print("Hard words: none matched.")
    else:
        print(f"Hard words: {sum(counts.values())} matches of {len(counts)} distinct words:\n")
        for word, n in counts.most_common():
            print(f"{word}  ×{n}")
            for ex in examples[word]:
                print(f"    {ex}")

    docs = []
    for name in args.files:
        text = Path(name).read_text(encoding="utf-8", errors="replace")
        parts = text.split("\n### ")
        for k, part in enumerate(parts):
            title = part.split("\n", 1)[0][:70] if k else Path(name).name
            _out, blocked, _reason, debug = _filter_plain_text(part)
            score = debug.get("score") or {}
            docs.append((blocked, score.get("window_max", 0), score.get("page", 0), score.get("context_factor", 1),
                         f"{Path(name).name}: {title}", score.get("top_terms", []), score.get("hidden_blocks", 0)))
    blocked_docs = [d for d in docs if d[0]]
    xd_docs = [d for d in docs if d[6] and not d[0]]
    print(f"\nScore: {len(docs)} documents, {len(blocked_docs)} would be BLOCKED, {len(xd_docs)} would get parts X'd")
    for d in sorted(docs, key=lambda d: (-bool(d[0] or d[6]), -d[1]))[: args.top]:
        flag = "BLOCK" if d[0] else (f"X×{d[6]:<3}" if d[6] else "     ")
        terms = ", ".join(f"{t} {v}" for t, v in d[5][:5])
        print(f"  {flag} window {d[1]:5.1f} page {d[2]:5.1f} ctx×{d[3]:<3g} {d[4]}  [{terms}]")
    return 1 if blocked_docs or xd_docs else 0


if __name__ == "__main__":
    sys.exit(main())
