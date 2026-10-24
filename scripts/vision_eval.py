"""Evaluation of the vision pipeline (paper Sec. V-G and Table VII):
detection accuracy, failure cases, tracking quality and tracked-speed
error against ground truth, plus detector and tracker ablations.

Data and annotation protocol
- Frames: no real images are used. vision/camera.py renders, for each of
  the four approaches, a 200 x 240 px frame of the 60 m before the stop line
  (4 px/m) from the simulator state, at 2 Hz.
- Annotation: automatic and exact. The ground-truth box of every vehicle
  in view comes from the same simulator state
  (vision.camera.ground_truth_boxes), so no manual labelling is involved
  and every label is correct by construction.
- Correct detection: a detection whose centre lies inside a ground-truth
  box enlarged by 4 px (vision/config.py MATCH_PADDING_PX); each detection
  matches at most one vehicle (the nearest).
- Splits: nothing is trained. The detector is the pre-trained cars.xml
  cascade; its parameters and the tracker's were fixed during development
  in unseeded live runs. Seeds 1-4 below are used only for this evaluation.
- Demand: lambda = 0.12 arrivals/s per approach, fixed-time control; 300 s
  per seed after a 60 s warm-up -> 4 seeds x 4 cameras x 600 frames.

Kinematics against ground truth: for every confirmed track matched to a
vehicle, the tracker's Kalman velocity is converted to m/s and compared
with the vehicle's true speed (tracks with at least 3 matches, so the
velocity estimate has had updates to converge).

Usage (from the repo root):

    python scripts/vision_eval.py                  # ~5-15 min on all cores
    python scripts/vision_eval.py --seeds 1 --duration 60   # quick check
    python scripts/vision_eval.py --json results/vision_eval.json
"""

import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import experiment_common  # noqa: E402,F401  (puts the repo root on sys.path)
from experiment_common import use_utf8_stdout  # noqa: E402

from simulation.engine import SimulationEngine  # noqa: E402
from vision.camera import ground_truth_boxes, render_road_frame  # noqa: E402
from vision.config import MATCH_PADDING_PX, PX_PER_M, VIEW_DISTANCE_M  # noqa: E402
from vision.detector import HaarVehicleDetector  # noqa: E402
from vision.tracker import ByteTracker  # noqa: E402

DETECTOR_VARIANTS = {
    "Default (3x upscale, equalized)": {},
    "2x upscale": {"upscale_factor": 2},
    "No upscaling": {"upscale_factor": 1},
    "No histogram equalization": {"equalize": False},
}
TRACKER_VARIANTS = {
    "ByteTrack-style (two-stage, Kalman)": {},
    "Single stage (low-confidence dropped)": {"two_stage": False},
    "No motion model (last box)": {"predict_motion": False},
    "Confirm after 1 match": {"min_hits": 1},
}
DISTANCE_BINS = [(0, 20), (20, 40), (40, VIEW_DISTANCE_M + 1e-9)]
WARMUP_S = 60.0
FRAME_EVERY_S = 0.5
SPAWN_RATE = 0.12
MIN_HITS_FOR_SPEED = 3


def _contains(gt, cx, cy):
    return (gt["x"] - MATCH_PADDING_PX <= cx <= gt["x"] + gt["w"] + MATCH_PADDING_PX
            and gt["y"] - MATCH_PADDING_PX <= cy <= gt["y"] + gt["h"] + MATCH_PADDING_PX)


def _nearest_gt(gts, cx, cy):
    hits = [g for g in gts if _contains(g, cx, cy)]
    return min(hits, key=lambda g: (g["x"] + g["w"] / 2 - cx) ** 2 + (g["y"] + g["h"] / 2 - cy) ** 2, default=None)


def run_job(args):
    """One seed with one detector variant. The default detector also feeds
    every tracker variant, so tracking is compared on identical detections."""
    seed, detector_name, duration_s = args
    detector = HaarVehicleDetector(**DETECTOR_VARIANTS[detector_name])
    track_all = detector_name == next(iter(DETECTOR_VARIANTS))
    engine = SimulationEngine(seed=seed, base_spawn_rate_per_s=SPAWN_RATE)
    dt = 0.05
    frame_every = int(round(FRAME_EVERY_S / dt))
    steps = int(round((WARMUP_S + duration_s) / dt))
    road_names = [r.value for r in engine.intersection.roads]
    trackers = {name: {road: ByteTracker(**opts) for road in road_names}
                for name, opts in TRACKER_VARIANTS.items()} if track_all else {}

    acc = {
        "frames": 0, "gt": 0, "detections": 0, "tp": 0, "gt_found": 0, "detect_s": 0.0,
        "gt_by_class": Counter(), "found_by_class": Counter(),
        "gt_by_dist": Counter(), "found_by_dist": Counter(),
        "fp_keys": Counter(), "fp_total": 0, "frames_per_road": Counter(),
        "tracking": {name: {"confirmed": 0, "confirmed_matched": 0, "gt_covered": 0, "id_switches": 0,
                            "speed_errors": [], "true_speeds": [], "vehicles_seen": set(),
                            "vehicles_confirmed": set(), "tracks_created": 0}
                     for name in TRACKER_VARIANTS} if track_all else {},
    }
    last_track_of = {name: {} for name in TRACKER_VARIANTS}

    for step in range(1, steps + 1):
        engine.tick(dt)
        if step * dt <= WARMUP_S or step % frame_every:
            continue
        state = engine.to_state()
        for road in road_names:
            road_state = state["roads"][road]
            speed_of = {v["id"]: v["speed"] for lane in road_state["lanes"] for v in lane["vehicles"]}
            # A fixed background per camera, as vision_runner.py uses: only
            # vehicles change between frames.
            frame = render_road_frame(road_state, seed=road_names.index(road))
            gts = ground_truth_boxes(road_state)
            t0 = time.perf_counter()
            dets = detector.detect(frame)
            acc["detect_s"] += time.perf_counter() - t0
            acc["frames"] += 1
            acc["frames_per_road"][road] += 1
            acc["gt"] += len(gts)
            acc["detections"] += len(dets)

            found = set()
            for det in dets:
                cx, cy = det.x + det.w / 2, det.y + det.h / 2
                gt = _nearest_gt(gts, cx, cy)
                if gt is None:
                    acc["fp_total"] += 1
                    acc["fp_keys"][(road, int(cx // 5), int(cy // 5))] += 1
                else:
                    acc["tp"] += 1
                    found.add(gt["id"])
            for gt in gts:
                dist = (gt["y"] + gt["h"] / 2) / PX_PER_M
                bin_ = next(i for i, (lo, hi) in enumerate(DISTANCE_BINS) if lo <= dist < hi)
                acc["gt_by_class"][gt["type"]] += 1
                acc["gt_by_dist"][bin_] += 1
                if gt["id"] in found:
                    acc["gt_found"] += 1
                    acc["found_by_class"][gt["type"]] += 1
                    acc["found_by_dist"][bin_] += 1

            for name in acc["tracking"]:
                tracker = trackers[name][road]
                t = acc["tracking"][name]
                visible = tracker.update(dets, dt=FRAME_EVERY_S)
                covered = set()
                for track in visible:
                    t["confirmed"] += 1
                    x, y, w, h = track.bbox
                    gt = _nearest_gt(gts, x + w / 2, y + h / 2)
                    if gt is None:
                        continue
                    t["confirmed_matched"] += 1
                    covered.add(gt["id"])
                    t["vehicles_confirmed"].add((road, gt["id"]))
                    previous = last_track_of[name].get((road, gt["id"]))
                    if previous is not None and previous != track.id:
                        t["id_switches"] += 1
                    last_track_of[name][(road, gt["id"])] = track.id
                    if TRACKER_VARIANTS[name].get("predict_motion", True) and track.hits >= MIN_HITS_FOR_SPEED:
                        # The camera looks back from the stop line: an approaching
                        # vehicle's box moves toward y = 0, so vy < 0 when moving.
                        estimate = -float(track.kf.x[3]) / PX_PER_M
                        t["speed_errors"].append(abs(estimate - speed_of[gt["id"]]))
                        t["true_speeds"].append(speed_of[gt["id"]])
                t["gt_covered"] += len(covered)
                t["vehicles_seen"].update((road, g["id"]) for g in gts)
        for name in acc["tracking"]:
            acc["tracking"][name]["tracks_created"] = sum(tr.total_tracks_created for tr in trackers[name].values())
    # sets are fine to pickle; convert to counts here to keep the payload small
    for t in acc["tracking"].values():
        t["vehicles_seen"] = len(t["vehicles_seen"])
        t["vehicles_confirmed"] = len(t["vehicles_confirmed"])
    return seed, detector_name, acc


def summarize(results, seeds):
    by_detector = defaultdict(list)
    for seed, name, acc in results:
        by_detector[name].append(acc)

    def pooled(accs, num, den):
        n = sum(a[num] for a in accs)
        d = sum(a[den] for a in accs)
        return 100 * n / d if d else float("nan")

    def per_seed(accs, num, den):
        vals = [100 * a[num] / a[den] for a in accs if a[den]]
        return (min(vals), max(vals)) if vals else (float("nan"), float("nan"))

    summary = {"seeds": seeds, "detectors": {}, "by_class": {}, "by_distance": {}, "tracking": {}, "failure": {}}
    for name, accs in by_detector.items():
        frames = sum(a["frames"] for a in accs)
        summary["detectors"][name] = {
            "frames": frames,
            "gt_instances": sum(a["gt"] for a in accs),
            "precision": pooled(accs, "tp", "detections"),
            "precision_range": per_seed(accs, "tp", "detections"),
            "recall": pooled(accs, "gt_found", "gt"),
            "recall_range": per_seed(accs, "gt_found", "gt"),
            "detections_per_frame": sum(a["detections"] for a in accs) / frames,
            "ms_per_frame": 1000 * sum(a["detect_s"] for a in accs) / frames,
        }
    default = by_detector[next(iter(DETECTOR_VARIANTS))]
    gt_class, found_class = Counter(), Counter()
    gt_dist, found_dist = Counter(), Counter()
    fp_keys, frames_per_road = Counter(), Counter()
    for a in default:
        gt_class.update(a["gt_by_class"]); found_class.update(a["found_by_class"])
        gt_dist.update(a["gt_by_dist"]); found_dist.update(a["found_by_dist"])
        frames_per_road.update(a["frames_per_road"])
    # False positives that recur at the same spot are the static background,
    # not missed vehicles: count those whose 5 px cell fires in >= 10% of
    # that camera's frames (per seed, then pooled).
    persistent, fp_total = 0, 0
    for a in default:
        fp_total += a["fp_total"]
        for (road, *_), count in a["fp_keys"].items():
            if count >= 0.1 * a["frames_per_road"][road]:
                persistent += count
    summary["by_class"] = {c: {"instances": gt_class[c], "recall": 100 * found_class[c] / gt_class[c]}
                           for c in sorted(gt_class, key=lambda c: -gt_class[c])}
    summary["by_distance"] = {f"{lo:g}-{min(hi, VIEW_DISTANCE_M):g} m": {
        "instances": gt_dist[i], "recall": 100 * found_dist[i] / gt_dist[i] if gt_dist[i] else float("nan")}
        for i, (lo, hi) in enumerate(DISTANCE_BINS)}
    summary["failure"] = {"false_positives": fp_total,
                          "persistent_background_share": 100 * persistent / fp_total if fp_total else float("nan")}
    for name in TRACKER_VARIANTS:
        ts = [a["tracking"][name] for a in default]
        gt = sum(a["gt"] for a in default)
        errors = [e for t in ts for e in t["speed_errors"]]
        speeds = [s for t in ts for s in t["true_speeds"]]
        seen = sum(t["vehicles_seen"] for t in ts)
        summary["tracking"][name] = {
            "coverage": 100 * sum(t["gt_covered"] for t in ts) / gt,
            "track_precision": 100 * sum(t["confirmed_matched"] for t in ts) / max(1, sum(t["confirmed"] for t in ts)),
            "vehicles_confirmed": 100 * sum(t["vehicles_confirmed"] for t in ts) / seen if seen else float("nan"),
            "id_switches_per_100_vehicles": 100 * sum(t["id_switches"] for t in ts) / seen if seen else float("nan"),
            "tracks_created": sum(t["tracks_created"] for t in ts),
            "speed_mae": statistics.mean(errors) if errors else None,
            "speed_n": len(errors),
            "true_speed_mean": statistics.mean(speeds) if speeds else None,
        }
    return summary


def format_report(s):
    d0 = next(iter(s["detectors"].values()))
    lines = [
        f"Vision pipeline on synthetic frames: seeds {s['seeds']}, {d0['frames']} frames, "
        f"{d0['gt_instances']} vehicle instances in view (default detector).",
        "",
        "| Detector variant | Precision (%) | Recall (%) | Detections/frame | ms/frame |",
        "|---|---|---|---|---|",
    ]
    for name, d in s["detectors"].items():
        lines.append(f"| {name} | {d['precision']:.1f} ({d['precision_range'][0]:.1f}–{d['precision_range'][1]:.1f}) "
                     f"| {d['recall']:.1f} ({d['recall_range'][0]:.1f}–{d['recall_range'][1]:.1f}) "
                     f"| {d['detections_per_frame']:.2f} | {d['ms_per_frame']:.0f} |")
    lines += ["", "Recall by vehicle class (default detector):", "",
              "| Class | Instances | Recall (%) |", "|---|---|---|"]
    lines += [f"| {c} | {v['instances']} | {v['recall']:.1f} |" for c, v in s["by_class"].items()]
    lines += ["", "Recall by distance from the stop line:", "", "| Distance | Instances | Recall (%) |", "|---|---|---|"]
    lines += [f"| {k} | {v['instances']} | {v['recall']:.1f} |" for k, v in s["by_distance"].items()]
    f = s["failure"]
    lines += ["", f"False positives: {f['false_positives']}; {f['persistent_background_share']:.1f}% recur at the "
              "same spot in >= 10% of a camera's frames (static background, not vehicles).", "",
              "| Tracker variant | Coverage (%) | Track precision (%) | Vehicles ever confirmed (%) "
              "| ID switches /100 veh. | Speed MAE (m/s) |", "|---|---|---|---|---|---|"]
    for name, t in s["tracking"].items():
        mae = f"{t['speed_mae']:.2f} (n={t['speed_n']})" if t["speed_mae"] is not None else "n/a"
        lines.append(f"| {name} | {t['coverage']:.1f} | {t['track_precision']:.1f} | {t['vehicles_confirmed']:.1f} "
                     f"| {t['id_switches_per_100_vehicles']:.1f} | {mae} |")
    t0 = next(iter(s["tracking"].values()))
    if t0["true_speed_mean"] is not None:
        lines.append(f"\nMean true speed of the vehicles behind those speed estimates: {t0['true_speed_mean']:.2f} m/s.")
    lines.append("Coverage: share of vehicle instances in view with a confirmed track on them. "
                 "Precision ranges in brackets: lowest-highest seed.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seeds", type=int, default=4, help="evaluation seeds 1..N (default: 4)")
    parser.add_argument("--duration", type=float, default=300.0, help="seconds per seed after warm-up (default: 300)")
    parser.add_argument("--jobs", type=int, default=None, help="parallel processes (default: all CPU cores)")
    parser.add_argument("--json", type=Path, help="also write the summary to this JSON file")
    args = parser.parse_args(argv)

    use_utf8_stdout()
    seeds = list(range(1, args.seeds + 1))
    jobs = [(s, name, args.duration) for s in seeds for name in DETECTOR_VARIANTS]
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(run_job, jobs))
    summary = summarize(results, seeds)
    print(format_report(summary))
    if args.json:
        args.json.write_text(json.dumps(summary, indent=1), encoding="utf-8")
        print(f"\nSummary written to {args.json}", file=sys.stderr)


if __name__ == "__main__":
    main()
