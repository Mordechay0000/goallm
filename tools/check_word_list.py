"""
Check the text-filter word lists against texts that must stay OPEN.

Rule for the lists: no listed word may appear in a permitted context (Torah / halacha, Haredi news, medical,
forms, everyday meaning). The way to keep that rule honest is to measure it: collect permitted texts
(text files, one or many) and run

    python -m tools.check_word_list corpus/*.txt [--context 40]

Every match is printed with its context – each one is a word (or a matching rule) to fix.
Exit code 1 when anything matched, so it can guard a change to the lists.
Run it after every edit of core/filters/text/word_lists/*/blocked.txt.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

from core.filters.text.text_filter import _find_matches
from data.constants import SUPPORTED_LANGS


def scan(text: str) -> List[tuple]:
    return _find_matches(text, list(SUPPORTED_LANGS))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--context", type=int, default=40)
    ap.add_argument("--max-per-word", type=int, default=3)
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
        print("OK – no listed word matched.")
        return 0
    print(f"{sum(counts.values())} matches of {len(counts)} distinct words – each is a permitted context:\n")
    for word, n in counts.most_common():
        print(f"{word}  ×{n}")
        for ex in examples[word]:
            print(f"    {ex}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
