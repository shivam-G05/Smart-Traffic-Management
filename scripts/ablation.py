"""Ablation of the adaptive controller (the paper's Table IV, extended).

Each variant changes one part of the controller and runs on the same
seeded traffic as the reference (the paper's adaptive controller, theta =
1.1, class weights, queued/moving multipliers 1.5/0.5, preemption on), so
every row is a paired comparison against it. Same method as benchmark.py
(Section V-A): 1800 s runs, 60 s warm-up, vehicles entering 60-1650 s.

Variants:
- the density score: plain vehicle count; no class weights; no
  queued/moving distinction;
- the switching ratio theta: 1.0 and 1.5;
- the discharge hold: on, with stop-line zones of 10 / 20 / 30 m;
- emergency preemption off.

Usage (from the repo root):

    python scripts/ablation.py
    python scripts/ablation.py --levels high=0.18 --seeds 5
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark import DEFAULT_LEVELS, trial_metrics  # noqa: E402
from experiment_common import (  # noqa: E402
    TrialSpec,
    fmt_ci,
    fmt_p,
    paired_change,
    run_trials,
    use_utf8_stdout,
)

from simulation.config import VehicleType  # noqa: E402

_ALL_ONE = {vehicle_type: 1.0 for vehicle_type in VehicleType}

# (label, controller type, controller options, preemption)
VARIANTS = [
    ("Adaptive (reference)", "adaptive", (), True),
    ("Unweighted count (weights and multipliers = 1)", "adaptive",
     (("class_weights", _ALL_ONE), ("queued_multiplier", 1.0), ("moving_multiplier", 1.0)), True),
    ("No class weights (all classes = 1)", "adaptive", (("class_weights", _ALL_ONE),), True),
    ("No queued/moving distinction (multipliers = 1)", "adaptive",
     (("queued_multiplier", 1.0), ("moving_multiplier", 1.0)), True),
    ("theta = 1.0", "adaptive", (("extension_threshold", 1.0),), True),
    ("theta = 1.5", "adaptive", (("extension_threshold", 1.5),), True),
    ("+ discharge hold, 10 m zone", "adaptive_hold", (), True),
    ("+ discharge hold, 20 m zone", "adaptive_hold", (("discharge_zone_m", 20.0),), True),
    ("+ discharge hold, 30 m zone", "adaptive_hold", (("discharge_zone_m", 30.0),), True),
    ("Preemption off", "adaptive", (), False),
    ("Fixed 20 s (for reference)", "fixed", (), True),
]


def run_ablation(levels: dict[str, float], seeds: list[int], duration_s: float, jobs: int | None):
    specs = [
        TrialSpec(controller=kind, seed=s, spawn_rate_per_s=rate, duration_s=duration_s,
                  preemption=preemption, options=options)
        for rate in levels.values() for _, kind, options, preemption in VARIANTS for s in seeds
    ]
    results = iter(run_trials(specs, jobs=jobs))
    return {level: [[trial_metrics(next(results)) for _ in seeds] for _ in VARIANTS] for level in levels}


def format_table(table, levels: dict[str, float], duration_s: float, n_seeds: int) -> str:
    lines = [
        f"Ablation of the adaptive controller: {n_seeds} paired seeds x {duration_s:g} s per row; "
        "change and p are relative to the reference at the same demand.",
        "",
        "| Variant | Demand | Mean delay (s) | Change | p | 95th-pct. delay (s) | Mean green (s) |",
        "|---|---|---|---|---|---|---|",
    ]
    for level in levels:
        reference = [m.mean_delay_s for m in table[level][0]]
        for (label, *_), runs in zip(VARIANTS, table[level]):
            delays = [m.mean_delay_s for m in runs]
            change, p = paired_change(reference, delays)
            is_reference = runs is table[level][0]
            lines.append(
                f"| {label} | {level} | {fmt_ci(delays)} | {'—' if is_reference else f'{change:+.1f}%'} "
                f"| {'—' if is_reference else fmt_p(p)} | {fmt_ci([m.p95_delay_s for m in runs], 1)} "
                f"| {fmt_ci([m.mean_green_s for m in runs], 1)} |"
            )
    runs = [m for level in levels for variant in table[level] for m in variant]
    lines += [
        "",
        "Mean ± 95% confidence interval over seeds; p = paired t-test.",
        f"Signal safety audit over all {len(runs)} runs: {sum(m.safety_violations for m in runs)} violations.",
    ]
    return "\n".join(lines)


def write_csv(path: Path, table, levels: dict[str, float], seeds: list[int]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["level", "variant", "seed", "mean_delay_s", "p95_delay_s", "mean_green_s", "throughput_vph"])
        for level in levels:
            for (label, *_), runs in zip(VARIANTS, table[level]):
                for seed, m in zip(seeds, runs):
                    writer.writerow([level, label, seed, round(m.mean_delay_s, 4), round(m.p95_delay_s, 4),
                                     round(m.mean_green_s, 4), round(m.throughput_vph, 2)])


def _parse_levels(text: str) -> dict[str, float]:
    return {name.strip(): float(rate) for name, _, rate in (item.partition("=") for item in text.split(","))}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--levels", type=_parse_levels,
                        default={k: v for k, v in DEFAULT_LEVELS.items() if k in ("medium", "high")},
                        help='name=arrivals/s/approach pairs (default: "medium=0.12,high=0.18", as Table IV)')
    parser.add_argument("--seeds", type=int, default=10, help="paired seeds per row (default: 10)")
    parser.add_argument("--duration", type=float, default=1800.0, help="simulated seconds per run (default: 1800)")
    parser.add_argument("--jobs", type=int, default=None, help="parallel processes (default: all CPU cores)")
    parser.add_argument("--csv", type=Path, help="also write every run's metrics to this CSV file")
    args = parser.parse_args(argv)

    use_utf8_stdout()
    seeds = list(range(1, args.seeds + 1))
    table = run_ablation(args.levels, seeds, args.duration, args.jobs)
    print(format_table(table, args.levels, args.duration, len(seeds)))
    if args.csv:
        write_csv(args.csv, table, args.levels, seeds)
        print(f"\nPer-seed results written to {args.csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
