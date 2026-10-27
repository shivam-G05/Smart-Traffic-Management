"""Measure the two timings quoted in the paper: Haar-cascade detection time per
camera frame and the time of one control decision, in a single process on an
otherwise idle machine (vision_eval.py runs jobs in parallel, so its
ms_per_frame column is inflated by contention and is not used for this).

    python scripts/timing_check.py [--frames 400] [--out results/timing.json]
"""

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import experiment_common  # noqa: E402,F401  (puts the repo root on sys.path)

from decision_engine.adaptive_controller import AdaptiveController  # noqa: E402
from simulation.engine import SimulationEngine  # noqa: E402
from vision.camera import render_road_frame  # noqa: E402
from vision.detector import HaarVehicleDetector  # noqa: E402


def cpu_name():
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        return out or platform.processor()
    except Exception:
        return platform.processor()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=400)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "results" / "timing.json"))
    args = ap.parse_args()

    engine = SimulationEngine(seed=1, base_spawn_rate_per_s=0.12)
    roads = [r.value for r in engine.intersection.roads]
    frames = []
    step = 0
    while len(frames) < args.frames:
        engine.tick(0.05)
        step += 1
        if step * 0.05 < 60 or step % 10:
            continue
        state = engine.to_state()
        for road in roads:
            frames.append(render_road_frame(state["roads"][road], seed=roads.index(road)))

    detector = HaarVehicleDetector()
    for f in frames[:20]:  # warm-up
        detector.detect(f)
    times = []
    for f in frames[: args.frames]:
        t0 = time.perf_counter()
        detector.detect(f)
        times.append(1000 * (time.perf_counter() - t0))

    ctrl = AdaptiveController(hold_while_discharging=True)
    inter = engine.intersection
    n = 20000
    t0 = time.perf_counter()
    for _ in range(n):
        ctrl._green_ready_to_end(inter)
    decision_ms = 1000 * (time.perf_counter() - t0) / n

    result = {
        "cpu": cpu_name(), "python": platform.python_version(), "frames": len(times),
        "detect_ms_mean": statistics.mean(times), "detect_ms_median": statistics.median(times),
        "detect_ms_p95": sorted(times)[int(0.95 * len(times))],
        "decision_ms_mean": decision_ms, "decisions": n,
    }
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
