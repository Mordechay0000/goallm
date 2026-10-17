"""
Calibrate the video change detector (VIDEO_CHANGE_* / VIDEO_FPS) on real, labelled videos.

The thresholds were set on synthetic frames. Before trusting them: take 20–30 real videos, write down the
seconds at which something new enters the frame (a person walking in, a cut to a new scene, a picture on a
wall coming into view), and run:

    python -m tools.calibrate_video_change labels.csv [--fps 1,2] [--tolerance 1.0] [--out report.csv]

labels.csv:
    video,events
    /data/v1.mp4,12.5;40;71
    https://cdn.example/v2.mp4,
    https://www.youtube.com/watch?v=XXXXXXXXXXX,3;8

(empty events = unlabelled: only the "frames sent to the model" ratio is measured for it)

For every parameter combination it reports:
- sent: frames analyzed = model calls – the cost (sent% = sent / sampled, for reference);
- missed: labelled events with no analyzed frame within [t, t + 1/fps + tolerance] – the risk.
The detector only decides which frames the model sees; a "caught" event still depends on the model.
Choose the cheapest row with missed = 0, then set the matching environment variables.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image

from core.filters.video import review_worker
from core.filters.video.frame_change import FrameChangeDetector
from data import constants as C

GRID = {
    "pixel_delta": (20, 28, 36),
    "tile_fraction": (0.02, 0.03, 0.05),
    "tile_mean": (8.0, 10.0, 14.0),
    "tile_px": (16,),
    "force_every_sec": (C.VIDEO_FORCE_ANALYZE_SEC,),
}


@dataclass
class Video:
    source: str
    events: List[float]
    frames: List[Tuple[float, Image.Image]] = field(default_factory=list)  # at max fps, reduced to detector width


def parse_labels(path: str) -> List[Video]:
    videos = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            src = (row.get("video") or "").strip()
            if not src:
                continue
            events = [float(x) for x in (row.get("events") or "").replace(",", ";").split(";") if x.strip()]
            videos.append(Video(src, sorted(events)))
    return videos


def load_frames(video: Video, fps: float, width: int) -> None:
    protocols = None
    if "://" not in video.source:
        protocols = review_worker.PROTOCOL_WHITELIST + ",file"  # operator tool reading local files (this call only)
        src = review_worker.MediaSource(url=video.source)
    else:
        src = review_worker.resolve_source({"source_url": video.source})
    duration = (src.duration or review_worker.probe_duration(src.url, src.referer, headers=src.headers, protocols=protocols)
                or C.VIDEO_MAX_DURATION_SEC)
    for t, frame in review_worker.iter_frames(src.url, src.referer, fps, C.VIDEO_FRAME_MAX_SIDE, duration, src.headers, protocols):
        h = max(1, round(frame.height * width / frame.width))
        video.frames.append((t, frame.convert("RGB").resize((width, h), Image.Resampling.BILINEAR)))


def run_detector(frames: Sequence[Tuple[float, Image.Image]], params: Dict, width: int) -> List[float]:
    det = FrameChangeDetector(width=width, **params)
    return [t for t, frame in frames if det.should_analyze(frame, t).analyze]


def missed_events(events: Sequence[float], analyzed: Sequence[float], window: float) -> List[float]:
    return [e for e in events if not any(e <= t <= e + window for t in analyzed)]


def evaluate(videos: List[Video], fps_list: Sequence[float], max_fps: float, tolerance: float, width: int,
             grid: Optional[Dict] = None) -> List[Dict]:
    grid = grid or GRID
    keys = list(grid)
    rows = []
    for fps in fps_list:
        step = max(1, round(max_fps / fps))
        for combo in itertools.product(*(grid[k] for k in keys)):
            params = dict(zip(keys, combo))
            sampled = sent = 0
            missed: List[str] = []
            for v in videos:
                frames = v.frames[::step]
                analyzed = run_detector(frames, params, width)
                sampled += len(frames)
                sent += len(analyzed)
                missed += [f"{v.source}@{e:g}" for e in missed_events(v.events, analyzed, 1.0 / fps + tolerance)]
            rows.append({"fps": fps, **params, "sampled": sampled, "sent": sent,
                         "sent_pct": round(100.0 * sent / sampled, 1) if sampled else 0.0,
                         "missed": len(missed), "missed_events": " ".join(missed[:20])})
    rows.sort(key=lambda r: (r["missed"], r["sent"], -r["fps"]))  # cost = model calls (absolute), not a percentage
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("labels")
    ap.add_argument("--fps", default="1,2", help="comma-separated sampling rates to compare")
    ap.add_argument("--tolerance", type=float, default=1.0, help="seconds after an event (beyond one frame) that still count")
    ap.add_argument("--width", type=int, default=C.VIDEO_CHANGE_WIDTH)
    ap.add_argument("--out", help="write the full table as CSV")
    args = ap.parse_args(argv)

    fps_list = [float(x) for x in args.fps.split(",") if x.strip()]
    max_fps = max(fps_list)
    videos = parse_labels(args.labels)
    if not videos:
        print("no videos in", args.labels, file=sys.stderr)
        return 2
    for v in videos:
        print(f"reading {v.source} …", file=sys.stderr)
        load_frames(v, max_fps, args.width)
    rows = evaluate(videos, fps_list, max_fps, args.tolerance, args.width)
    labelled = sum(len(v.events) for v in videos)
    print(f"\n{len(videos)} videos, {labelled} labelled events. Best first (fewest missed, then fewest model calls):\n")
    print(f"{'fps':>4} {'delta':>5} {'frac':>5} {'mean':>5} {'sent':>6} {'sent%':>6} {'missed':>6}  missed events")
    for r in rows[:15]:
        print(f"{r['fps']:>4g} {r['pixel_delta']:>5} {r['tile_fraction']:>5} {r['tile_mean']:>5g} {r['sent']:>6} {r['sent_pct']:>6} {r['missed']:>6}  {r['missed_events'][:80]}")
    best = rows[0]
    print("\nSuggested settings:")
    print(f"  VIDEO_FPS={best['fps']:g} VIDEO_CHANGE_PIXEL_DELTA={best['pixel_delta']} "
          f"VIDEO_CHANGE_TILE_FRACTION={best['tile_fraction']} VIDEO_CHANGE_TILE_MEAN={best['tile_mean']:g}")
    if best["missed"]:
        print("  WARNING: even the best combination misses events – lower the thresholds or raise VIDEO_FPS.")
    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"\nfull table: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
