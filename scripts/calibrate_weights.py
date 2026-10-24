"""Data-driven calibration of the density score (reviewer request: validate
or calibrate the heuristic density weights).

The paper's class weights and queued/moving multipliers were set by hand.
This script fits them to the simulation instead, with the evaluation kept
honest by a train/test split of seeds:

1. Tuning: random search over the score parameters of the final controller
   (adaptive + discharge hold) on tuning seeds 1001-1005, which no other
   experiment uses. Objective: mean stopped delay relative to the hand-set
   weights, averaged over three demands (medium and high of Table II, and
   0.9x capacity).
2. Testing: the best setting, the hand-set weights and a plain vehicle count
   are compared on the held-out evaluation seeds 1-10 with paired t-tests.

Searched parameters: the weights of motorcycle, auto-rickshaw, bus and truck
(log-uniform 0.25-4) and of emergency vehicles (1-10), the queued/moving
ratio (1-12, moving fixed at 0.5) and the switching ratio theta (1.0-1.6).
The car weight stays 1: the switching rule D_A <= theta * D_W compares
ratios, so the overall scale of the weights does not matter.

Usage (from the repo root):

    python scripts/calibrate_weights.py                  # ~20-40 min
    python scripts/calibrate_weights.py --candidates 8 --tune-seeds 2 --test-seeds 3 --duration 900
"""

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark import trial_metrics  # noqa: E402
from experiment_common import TrialSpec, fmt_ci, mean_ci, paired_change, run_trials, use_utf8_stdout  # noqa: E402
from oversaturation import over_metrics  # noqa: E402

from decision_engine.density import DENSITY_WEIGHTS, MOVING_MULTIPLIER, QUEUED_MULTIPLIER  # noqa: E402
from simulation.config import VehicleType  # noqa: E402

CONTROLLER = "adaptive_hold"
NEAR_CAPACITY_RATE = 0.9 * 10008 / (4 * 3600)
CONDITIONS = {
    "medium": dict(rate=0.12, over=False),
    "high": dict(rate=0.18, over=False),
    "0.9x capacity": dict(rate=NEAR_CAPACITY_RATE, over=True),
}
TUNE_SEEDS_START = 1001


def options_for(params: dict) -> tuple:
    weights = {
        VehicleType.CAR: 1.0,
        VehicleType.MOTORCYCLE: params["motorcycle"],
        VehicleType.AUTO: params["auto"],
        VehicleType.BUS: params["bus"],
        VehicleType.TRUCK: params["truck"],
        VehicleType.AMBULANCE: params["emergency"],
        VehicleType.FIRE_TRUCK: params["emergency"],
    }
    return (("class_weights", weights), ("queued_multiplier", params["queued_ratio"] * MOVING_MULTIPLIER),
            ("moving_multiplier", MOVING_MULTIPLIER), ("extension_threshold", params["theta"]))


HAND_SET = {"motorcycle": DENSITY_WEIGHTS[VehicleType.MOTORCYCLE], "auto": DENSITY_WEIGHTS[VehicleType.AUTO],
            "bus": DENSITY_WEIGHTS[VehicleType.BUS], "truck": DENSITY_WEIGHTS[VehicleType.TRUCK],
            "emergency": DENSITY_WEIGHTS[VehicleType.AMBULANCE], "queued_ratio": QUEUED_MULTIPLIER / MOVING_MULTIPLIER,
            "theta": 1.1}
COUNT = {"motorcycle": 1.0, "auto": 1.0, "bus": 1.0, "truck": 1.0, "emergency": 1.0, "queued_ratio": 1.0, "theta": 1.1}


def random_params(rng: random.Random) -> dict:
    logu = lambda lo, hi: math.exp(rng.uniform(math.log(lo), math.log(hi)))  # noqa: E731
    return {"motorcycle": logu(0.25, 4), "auto": logu(0.25, 4), "bus": logu(0.25, 4), "truck": logu(0.25, 4),
            "emergency": rng.uniform(1, 10), "queued_ratio": logu(1, 12), "theta": rng.uniform(1.0, 1.6)}


def spec(params, condition, seed, duration_s):
    c = CONDITIONS[condition]
    return TrialSpec(controller=CONTROLLER, seed=seed, spawn_rate_per_s=c["rate"], duration_s=duration_s,
                     preemption=not c["over"], entry_backlog=c["over"], insert_at_speed=c["over"],
                     options=options_for(params))


def delay(result, condition):
    return over_metrics(result).delay_all_lb_s if CONDITIONS[condition]["over"] else trial_metrics(result).mean_delay_s


def evaluate(candidates, seeds, duration_s, jobs):
    """{candidate index: {condition: [delay per seed]}}"""
    keys = [(i, cond, s) for i in range(len(candidates)) for cond in CONDITIONS for s in seeds]
    results = run_trials([spec(candidates[i], cond, s, duration_s) for i, cond, s in keys], jobs=jobs)
    out: dict = {}
    for (i, cond, _), r in zip(keys, results):
        out.setdefault(i, {}).setdefault(cond, []).append(delay(r, cond))
    return out, sum(sum(r.safety_violations.values()) for r in results), len(results)


def objective(delays, reference):
    """Mean over conditions of (mean delay / reference mean delay)."""
    return statistics.mean(statistics.mean(delays[c]) / statistics.mean(reference[c]) for c in CONDITIONS)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--candidates", type=int, default=48, help="random candidates besides the two references")
    parser.add_argument("--tune-seeds", type=int, default=5)
    parser.add_argument("--test-seeds", type=int, default=10)
    parser.add_argument("--duration", type=float, default=1800.0)
    parser.add_argument("--jobs", type=int, default=None)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    use_utf8_stdout()

    rng = random.Random(0)
    candidates = [HAND_SET, COUNT] + [random_params(rng) for _ in range(args.candidates)]
    tune_seeds = list(range(TUNE_SEEDS_START, TUNE_SEEDS_START + args.tune_seeds))
    tuned, tune_violations, tune_runs = evaluate(candidates, tune_seeds, args.duration, args.jobs)
    scores = [objective(tuned[i], tuned[0]) for i in range(len(candidates))]
    best = min(range(len(candidates)), key=lambda i: scores[i])

    test_seeds = list(range(1, args.test_seeds + 1))
    finalists = {"Hand-set (paper)": candidates[0], "Plain count": candidates[1], "Calibrated": candidates[best]}
    tested, test_violations, test_runs = evaluate(list(finalists.values()), test_seeds, args.duration, args.jobs)

    lines = [f"Calibration of the density score for {CONTROLLER}: {len(candidates)} candidates on tuning seeds "
             f"{tune_seeds[0]}-{tune_seeds[-1]}, finalists on held-out seeds 1-{test_seeds[-1]}.", "",
             "Best candidate on the tuning seeds (objective = mean delay relative to hand-set, averaged over conditions): "
             f"{scores[best]:.3f} (hand-set 1.000, plain count {scores[1]:.3f}).", "",
             "| Parameter | Hand-set | Calibrated |", "|---|---|---|"]
    for k in HAND_SET:
        lines.append(f"| {k} | {HAND_SET[k]:.2f} | {candidates[best][k]:.2f} |")
    lines += ["", "Held-out evaluation (mean delay, s):", "",
              "| Score | " + " | ".join(CONDITIONS) + " |", "|---|" + "---|" * len(CONDITIONS)]
    summary = {"best_params": candidates[best], "hand_set": HAND_SET, "tuning_scores": {
        "calibrated": scores[best], "plain_count": scores[1]}, "held_out": {}}
    ref = tested[0]
    for j, name in enumerate(finalists):
        cells = []
        summary["held_out"][name] = {}
        for cond in CONDITIONS:
            vals = tested[j][cond]
            change, p = paired_change(ref[cond], vals)
            m, h = mean_ci(vals)
            summary["held_out"][name][cond] = {"mean": m, "ci": h, "change_pct": change, "p": p}
            cells.append(fmt_ci(vals) + ("" if j == 0 else f" ({change:+.1f}%, p {'< 0.001' if p < 0.001 else f'{p:.3f}'})"))
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines += ["", "Change and p: paired against the hand-set weights on the same held-out seeds.",
              f"Signal safety audit over all {tune_runs + test_runs} runs: {tune_violations + test_violations} violations."]
    summary["runs"] = tune_runs + test_runs
    summary["candidates"] = len(candidates)
    summary["tune_seeds"] = tune_seeds
    summary["violations"] = tune_violations + test_violations
    print("\n".join(lines))
    if args.json:
        args.json.write_text(json.dumps(summary, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
