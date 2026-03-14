"""
תצורת סינון מלל – נתיב רשימות מילים. ספים ב־data.constants.
"""
from pathlib import Path

from data.constants import (
    MIN_RATIO_WORDS_FOR_PAGE_BLOCK,
    MIN_MATCHES_FOR_PAGE_BLOCK,
    MIN_WORDS_FOR_RATIO_BLOCK,
    MIN_PERCENTAGE_COMPONENTS_FOR_PAGE_BLOCK,
    MIN_COMPONENTS_WITH_DETECTION_FOR_PAGE_BLOCK,
    SUPPORTED_LANGS,
)

_BASE = Path(__file__).resolve().parent
WORD_LISTS_DIR = _BASE / "word_lists"
BLOCKED_WORDS_FILENAME = "blocked.txt"
