"""
Measure an image analyzer against a hand-labelled "golden set" BEFORE choosing or changing a model/prompt.

Layout:  <golden_dir>/labels.csv   with columns: file,blocked   (blocked = 1 if the image must be blocked)
         <golden_dir>/<file>       the images (any format: jpg/png/webp/avif/gif/svg)

Run (uses the analyzer configured by IMAGE_ANALYZER / VLM_* env vars, exactly as the proxy does):
    IMAGE_ANALYZER=openai VLM_API_BASE=http://127.0.0.1:8001/v1 python -m tools.eval_golden_set path/to/golden

Reports recall on must-block images (the number that matters: every miss is an immodest image shown to a user),
false-block rate on clean images, and lists every miss so you can see what the model fails on.
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

from core.filters.image.analysis import CONDITION_KEYS, analyze_image_frames
from core.filters.image.image_extraction import detect_image_mime
from core.filters.image.image_status_manager import _create_image_analyzer


def main(golden_dir: str) -> int:
    root = Path(golden_dir)
    rows = list(csv.DictReader((root / "labels.csv").open(encoding="utf-8")))
    analyzer = _create_image_analyzer()
    tp = fn = fp = tn = errors = 0
    misses, false_blocks = [], []
    started = time.time()
    for row in rows:
        path = root / row["file"]
        data = path.read_bytes()
        mime = detect_image_mime(data, "image/svg+xml" if path.suffix.lower() == ".svg" else "") or "image/jpeg"
        try:
            result = analyze_image_frames(analyzer, data, mime)
        except Exception as e:  # an error is a block in production (fail-closed), but report it
            errors += 1
            print(f"ERROR {row['file']}: {e}")
            continue
        predicted = any(result.get(k) == "Yes" for k in CONDITION_KEYS)
        expected = str(row["blocked"]).strip() in ("1", "true", "yes", "Yes")
        if expected and predicted:
            tp += 1
        elif expected:
            fn += 1
            misses.append(row["file"])
        elif predicted:
            fp += 1
            false_blocks.append(row["file"])
        else:
            tn += 1
    elapsed = time.time() - started
    must_block = tp + fn
    clean = fp + tn
    print(f"\nimages: {len(rows)}  errors: {errors}  time: {elapsed:.1f}s ({elapsed / max(1, len(rows)):.2f}s/image)")
    print(f"RECALL on must-block: {tp}/{must_block} = {tp / max(1, must_block):.2%}   <- target ≥ 99.5%")
    print(f"false-block rate:     {fp}/{clean} = {fp / max(1, clean):.2%}")
    if misses:
        print("\nMISSED (shown to users!):\n  " + "\n  ".join(misses))
    if false_blocks:
        print("\nFalse blocks:\n  " + "\n  ".join(false_blocks[:50]))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
