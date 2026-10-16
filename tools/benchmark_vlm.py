"""
Throughput / latency of the VLM server – to compute cost per 1,000 images on YOUR hardware instead of guessing.

    VLM_API_BASE=http://127.0.0.1:8001/v1 VLM_MODEL=Qwen/Qwen3.5-9B python -m tools.benchmark_vlm images_dir 32

Sends every image in images_dir (prepared exactly like the proxy does) with N concurrent requests and prints
images/second, p50/p95 latency and the cost per 1,000 images for a given GPU price (GPU_PRICE_PER_HOUR, default 0.80).
"""
from __future__ import annotations

import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from core.filters.image.analyzers.openai_compat import OpenAICompatImageAnalyzer
from core.filters.image.image_extraction import detect_image_mime
from core.filters.image.image_preprocess import prepare_frames


def main(images_dir: str, concurrency: int) -> int:
    files = [p for p in sorted(Path(images_dir).iterdir()) if p.is_file()]
    frames = []
    for p in files:
        data = p.read_bytes()
        mime = detect_image_mime(data, "image/svg+xml" if p.suffix.lower() == ".svg" else "") or "image/jpeg"
        try:
            frames.append(prepare_frames(data, mime)[0])
        except Exception as e:
            print(f"skip {p.name}: {e}")
    analyzer = OpenAICompatImageAnalyzer()
    latencies = []

    def one(frame: bytes) -> None:
        t0 = time.perf_counter()
        analyzer.analyze_image(frame, "image/jpeg")
        latencies.append(time.perf_counter() - t0)

    t_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        list(pool.map(one, frames))
    wall = time.perf_counter() - t_start
    ips = len(frames) / wall
    price = float(os.environ.get("GPU_PRICE_PER_HOUR", "0.80"))
    print(f"images: {len(frames)}  concurrency: {concurrency}  wall: {wall:.1f}s")
    print(f"throughput: {ips:.2f} images/s   p50: {statistics.median(latencies):.2f}s   p95: {sorted(latencies)[int(len(latencies) * 0.95) - 1]:.2f}s")
    print(f"cost at 100% utilisation: ${price / (ips * 3600) * 1000:.4f} per 1,000 images (GPU ${price}/h)")
    print("real cost ≈ this ÷ average utilisation (peak hours need spare capacity; 30-40% utilisation is typical)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 16))
