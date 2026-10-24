"""How much does the controller depend on perfect sensing? (Reviewer
request: address the gap between the ideal simulator sensing used for
control and the low-performing vision pipeline.)

Every controller in the other experiments reads exact vehicle states. Here
the vehicle-reading controllers instead see the junction through a sensor
model (decision_engine/sensing.py), from a perfect camera down to the
measured Haar pipeline:
- camera view: only vehicles within 60 m of the stop line, refreshed at
  2 Hz, without vehicle classes (as a single Haar cascade);
- the same with 90 / 70 / 50 / 30% recall (independent misses per frame);
- the same with perfect recall plus 2 phantom detections per approach at
  fixed spots (the Haar cascade's static false positives);
- the measured Haar pipeline: recall and phantom count taken from
  results/vision_eval.json (scripts/vision_eval.py).
The fixed plan reads nothing and is the reference. Emergency preemption
keeps reading the true emergency flags; only density sensing is degraded.

Two demands: the paper's medium level (lambda = 0.12, Table II method) and
0.9x the fixed-time capacity (entry backlog and entry at speed, preemption
off, as scripts/oversaturation.py), where the discharge hold matters.

Usage (from the repo root):

    python scripts/sensing.py
    python scripts/sensing.py --seeds 3 --duration 900     # quick check
"""

import argparse
import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark import trial_metrics  # noqa: E402
from experiment_common import (  # noqa: E402
    CONTROLLER_LABELS,
    TrialSpec,
    fmt_ci,
    fmt_change,
    run_trials,
    use_utf8_stdout,
)
from oversaturation import over_metrics  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SENSED = ("actuated", "max_pressure", "adaptive", "adaptive_hold")
CAMERA = (("view_m", 60.0), ("refresh_s", 0.5), ("class_blind", True))
# 0.9 x the fixed plan's capacity of 10,008 veh/h (results/oversaturation_preemption_off.md)
NEAR_CAPACITY_RATE = 0.9 * 10008 / (4 * 3600)


def measured_haar_sensor(path: Path = ROOT / "results" / "vision_eval.json") -> tuple:
    """Recall and phantom detections per approach of the measured pipeline:
    false positives per frame = detections per frame x (1 - precision), and
    nearly all recur at fixed spots, so they are modelled as phantoms."""
    with path.open(encoding="utf-8") as f:
        d = next(iter(json.load(f)["detectors"].values()))
    phantoms = round(d["detections_per_frame"] * (1 - d["precision"] / 100))
    return CAMERA + (("recall", round(d["recall"] / 100, 3)), ("phantoms_per_approach", phantoms))


def profiles() -> dict[str, tuple | None]:
    out = {
        "Exact states": None,
        "Camera (60 m, 2 Hz, no classes)": CAMERA,
        "  recall 90%": CAMERA + (("recall", 0.9),),
        "  recall 70%": CAMERA + (("recall", 0.7),),
        "  recall 50%": CAMERA + (("recall", 0.5),),
        "  recall 30%": CAMERA + (("recall", 0.3),),
        "  2 phantoms per approach": CAMERA + (("phantoms_per_approach", 2),),
    }
    try:
        haar = measured_haar_sensor()
        d = dict(haar)
        out[f"Measured Haar (recall {100 * d['recall']:.0f}%, {d['phantoms_per_approach']} phantoms)"] = haar
    except FileNotFoundError:
        print("results/vision_eval.json not found; skipping the measured-Haar profile", file=sys.stderr)
    return out


CONDITIONS = {
    "medium demand (λ = 0.12)": dict(rate=0.12, over=False),
    "0.9× capacity": dict(rate=NEAR_CAPACITY_RATE, over=True),
}


def spec(controller, seed, condition, sensor, duration_s):
    c = CONDITIONS[condition]
    return TrialSpec(controller=controller, seed=seed, spawn_rate_per_s=c["rate"], duration_s=duration_s,
                     preemption=not c["over"], entry_backlog=c["over"], insert_at_speed=c["over"],
                     sensor=sensor or ())


def delay(result, condition):
    if CONDITIONS[condition]["over"]:
        return over_metrics(result).delay_all_lb_s
    return trial_metrics(result).mean_delay_s


def run(seeds, duration_s, jobs):
    profs = profiles()
    jobs_list = []
    for cond in CONDITIONS:
        jobs_list += [("fixed", None, cond, s) for s in seeds]
        jobs_list += [(c, name, cond, s) for name in profs for c in SENSED for s in seeds]
    results = run_trials([spec(c, s, cond, profs[name] if name else None, duration_s)
                          for c, name, cond, s in jobs_list], jobs=jobs)
    table: dict = {}
    for (c, name, cond, s), r in zip(jobs_list, results):
        table.setdefault(cond, {}).setdefault((c, name), []).append(delay(r, cond))
    violations = sum(sum(r.safety_violations.values()) for r in results)
    return profs, table, violations, len(results)


def format_report(profs, table, violations, runs, n_seeds, duration_s):
    lines = [f"Controllers under imperfect sensing: {n_seeds} paired seeds x {duration_s:g} s per cell.", ""]
    for cond, cells in table.items():
        fixed = cells[("fixed", None)]
        lines += [f"Delay (s), {cond}; fixed plan (no sensing needed): {fmt_ci(fixed)}", "",
                  "| Sensing | " + " | ".join(CONTROLLER_LABELS[c] for c in SENSED) + " |",
                  "|---|" + "---|" * len(SENSED)]
        for name in profs:
            row = []
            for c in SENSED:
                vals = cells[(c, name)]
                ref = cells[(c, "Exact states")]
                cell = fmt_ci(vals, 1)
                if name != "Exact states":
                    cell += f" ({fmt_change(ref, vals).split(' (')[0]})"
                row.append(cell)
            lines.append(f"| {name.strip()} | " + " | ".join(row) + " |")
        lines.append("")
    lines += ["Mean ± 95% CI; brackets: change relative to the same controller with exact states. Delay at 0.9× "
              "capacity includes time waiting to enter the road.",
              f"Signal safety audit over all {runs} runs: {violations} violations."]
    return "\n".join(lines)


def write_csv(path: Path, profs, table, seeds):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["condition", "sensing", "controller", "seed", "delay_s"])
        for cond, cells in table.items():
            for (c, name), vals in cells.items():
                for s, v in zip(seeds, vals):
                    w.writerow([cond, (name or "none").strip(), c, s, "" if math.isnan(v) else round(v, 4)])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--duration", type=float, default=1800.0)
    parser.add_argument("--jobs", type=int, default=None)
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args(argv)
    use_utf8_stdout()
    seeds = list(range(1, args.seeds + 1))
    profs, table, violations, runs = run(seeds, args.duration, args.jobs)
    print(format_report(profs, table, violations, runs, len(seeds), args.duration))
    if args.csv:
        write_csv(args.csv, profs, table, seeds)


if __name__ == "__main__":
    main()
