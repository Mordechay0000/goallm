"""
Decide which sampled video frames must go to the model.

Goal: skip frames whose details did not change, but never skip a frame into which something new has
entered – even when the frame as a whole still looks "similar".

How:
- Each sampled frame is reduced to a small, slightly blurred RGB image (blur removes compression noise).
- It is compared with the LAST ANALYZED frame – not with the previous sampled frame. Comparing with the
  previous frame would let a slow change (a figure walking in step by step, a slow pan) pass in tiny steps
  that are each below the threshold; against the last analyzed frame the difference accumulates until it
  triggers.
- The comparison is LOCAL: the frame is split into small tiles, and ONE changed tile is enough. A global
  similarity score (average difference, perceptual hash, SSIM) would stay "similar" when a small figure
  appears in a corner – exactly the case that must not be missed.
- A tile counts as changed when enough of its pixels changed by more than a noise threshold, or its mean
  difference is high (gradual / low-contrast change).
- Safety net: a frame is analyzed at least every VIDEO_FORCE_ANALYZE_SEC seconds even if nothing seemed to change.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from PIL import Image, ImageChops, ImageFilter

from data.constants import (
    VIDEO_CHANGE_PIXEL_DELTA,
    VIDEO_CHANGE_TILE_FRACTION,
    VIDEO_CHANGE_TILE_MEAN,
    VIDEO_CHANGE_TILE_PX,
    VIDEO_CHANGE_WIDTH,
    VIDEO_FORCE_ANALYZE_SEC,
)


@dataclass
class ChangeDecision:
    analyze: bool
    reason: str
    changed_tiles: int = 0


class FrameChangeDetector:
    def __init__(
        self,
        width: int = VIDEO_CHANGE_WIDTH,
        tile_px: int = VIDEO_CHANGE_TILE_PX,
        pixel_delta: int = VIDEO_CHANGE_PIXEL_DELTA,
        tile_fraction: float = VIDEO_CHANGE_TILE_FRACTION,
        tile_mean: float = VIDEO_CHANGE_TILE_MEAN,
        force_every_sec: float = VIDEO_FORCE_ANALYZE_SEC,
    ) -> None:
        self.width = max(32, int(width))
        self.tile_px = max(4, int(tile_px))
        self.pixel_delta = max(1, min(255, int(pixel_delta)))
        self.tile_fraction = float(tile_fraction)
        self.tile_mean = float(tile_mean)
        self.force_every_sec = float(force_every_sec)
        self._ref: Optional[Image.Image] = None
        self._ref_t: float = 0.0
        # histogram bins at or above pixel_delta = "changed" pixels
        self._lut = [0] * self.pixel_delta + [255] * (256 - self.pixel_delta)

    def _reduce(self, frame: Image.Image) -> Image.Image:
        rgb = frame.convert("RGB")
        w, h = rgb.size
        height = max(1, round(h * self.width / max(1, w)))
        small = rgb.resize((self.width, height), Image.Resampling.BILINEAR)
        return small.filter(ImageFilter.GaussianBlur(radius=1))

    def _diff(self, small: Image.Image) -> Image.Image:
        """Per-pixel max difference over R, G, B (a colour change at equal brightness still counts)."""
        r, g, b = ImageChops.difference(small, self._ref).split()
        return ImageChops.lighter(ImageChops.lighter(r, g), b)

    def _changed_tiles(self, diff: Image.Image) -> Tuple[int, str]:
        w, h = diff.size
        mask = diff.point(self._lut)  # 255 where a pixel changed more than the noise threshold
        changed = 0
        first = ""
        for top in range(0, h, self.tile_px):
            for left in range(0, w, self.tile_px):
                box = (left, top, min(w, left + self.tile_px), min(h, top + self.tile_px))
                area = (box[2] - box[0]) * (box[3] - box[1])
                if area <= 0:
                    continue
                hist = diff.crop(box).histogram()
                mean = sum(i * c for i, c in enumerate(hist)) / area
                frac = mask.crop(box).histogram()[255] / area
                if frac >= self.tile_fraction or mean >= self.tile_mean:
                    changed += 1
                    if not first:
                        first = f"tile@{left},{top} frac={frac:.2f} mean={mean:.1f}"
        return changed, first

    def should_analyze(self, frame: Image.Image, t_sec: float) -> ChangeDecision:
        small = self._reduce(frame)
        if self._ref is None or self._ref.size != small.size:
            decision = ChangeDecision(True, "first frame")
        elif t_sec - self._ref_t >= self.force_every_sec:
            decision = ChangeDecision(True, f"periodic check ({self.force_every_sec:.0f}s)")
        else:
            changed, where = self._changed_tiles(self._diff(small))
            decision = ChangeDecision(changed > 0, where or "no change", changed)
        if decision.analyze:
            # The reference moves only when a frame is actually analyzed.
            self._ref = small
            self._ref_t = t_sec
        return decision
