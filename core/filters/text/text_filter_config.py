"""
תצורת סינון מלל – נתיב רשימות מילים. ספים ורמות חומרה ב־data.constants.
"""
from pathlib import Path

from data.constants import (
    SEVERITY_LIGHT,
    SEVERITY_MEDIUM,
    SEVERITY_SEVERE,
    THRESHOLD_SENTENCE_LIGHT,
    THRESHOLD_PARAGRAPH_LIGHT,
    THRESHOLD_PAGE_LIGHT,
    ANY_SEVERITY_3_BLOCKS_PAGE,
    THRESHOLD_PAGE_MEDIUM_BLOCK,
    MIN_PERCENTAGE_COMPONENTS_FOR_PAGE_BLOCK,
    MIN_COMPONENTS_WITH_DETECTION_FOR_PAGE_BLOCK,
    SUPPORTED_LANGS,
)

_BASE = Path(__file__).resolve().parent
WORD_LISTS_DIR = _BASE / "word_lists"
