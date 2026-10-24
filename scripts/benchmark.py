"""Fixed-timer vs. adaptive benchmark, following the paper's method
(Section V-A and Table II).

Both controllers run headless (no FastAPI, no WebSocket, no vision) against
identical seeded traffic at three demand levels, ten seeds each. Runs with
the same seed form matched pairs, compared with paired t-tests; every value
is the mean over seeds ± its 95% confidence interval.

Method, as in the paper:
- 1800 s per run, 50 ms step; the first 60 s are a warm-up.
- Delay statistics use the vehicles that *entered* between 60 s and 1650 s
  (the script checks they all left before the end of the run).
- Stopped delay = time a vehicle spends upstream of the stop line below
  0.5 m/s (Vehicle.queued_time_s), the same quantity the dashboard shows.
- Mean queue and time at high density come from a 1 Hz sample after the
  warm-up; "high density" = at least one approach above 6.0.
- Throughput = vehicles leaving the map after the warm-up, per hour.

Usage (from the repo root):

    python scripts/benchmark.py                       # Table II, preemption on
    python scripts/benchmark.py --no-preemption       # same, preemption off
    python scripts/benchmark.py --duration 300 --seeds 3   # quick check
    python scripts/benchmark.py --csv results.csv     # also write per-seed rows
"""

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from experiment_common import (  # noqa: E402
    TrialResult,
    TrialSpec,
    fmt_change,
    fmt_ci,
    mean_or_nan,
    percentile,
    run_trials,
    use_utf8_stdout,
)

# Mean arrivals per second per approach (paper: 1152 / 1728 / 2592 veh/h
# offered to the junction).
DEFAULT_LEVELS = {"low": 0.08, "medium": 0.12, "high": 0.18}
DEFAULT_SEEDS = 10
DEFAULT_DURATION_S = 1800.0
WARMUP_S = 60.0
# Vehicles entering in the last 150 s are not measured, so every measured
# vehicle can leave before the run ends (1650 s in a 1800 s run).
ENTRY_TAIL_S = 150.0


@dataclass(frozen=True)
class TrialMetrics:
    mean_delay_s: float
    p95_delay_s: float
    mean_queue: float
    high_density_pct: float
    throughput_vph: float
    measured_vehicles: int
    unfinished: int  # measured vehicles still on the road at the end (should be 0)


def trial_metrics(result: TrialResult, warmup_s: float = WARMUP_S,
                  entry_tail_s: float = ENTRY_TAIL_S) -> TrialMetrics:
    duration = result.spec.duration_s
    cutoff = duration - entry_tail_s
    measured = [v for v in result.vehicles if warmup_s <= v.entry_s < cutoff]
    delays = [v.stopped_delay_s for v in measured]
    after_warmup = [s for s in result.samples if s.t > warmup_s]
    exits = sum(1 for v in result.vehicles if v.exit_s is not None and v.exit_s > warmup_s)
    hours = (duration - warmup_s) / 3600
    return TrialMetrics(
        mean_delay_s=mean_or_nan(delays),
        p95_delay_s=percentile(delays, 95),
        mean_queue=mean_or_nan(s.queued for s in after_warmup),
        high_density_pct=100 * mean_or_nan(s.high_density for s in after_warmup),
        throughput_vph=exits / hours if hours > 0 else float("nan"),
        measured_vehicles=len(measured),
        unfinished=sum(1 for v in measured if v.exit_s is None),
    )


METRICS = [
    ("Mean stopped delay (s)", "mean_delay_s", 2),
    ("95th-pct. delay (s)", "p95_delay_s", 1),
    ("Mean queue (veh)", "mean_queue", 2),
    ("Time at high density (%)", "high_density_pct", 1),
    ("Throughput (veh/h)", "throughput_vph", 0),
]


def run_benchmark(levels: dict[str, float], seeds: list[int], duration_s: float,
                  preemption: bool = True, jobs: int | None = None,
                  dt: float = 0.05) -> dict[str, dict[str, list[TrialMetrics]]]:
    """Returns {level: {"fixed": [metrics per seed], "adaptive": [...]}}."""
    specs = [
        TrialSpec(controller=c, seed=s, spawn_rate_per_s=rate, duration_s=duration_s,
                  dt=dt, preemption=preemption)
        for rate in levels.values() for c in ("fixed", "adaptive") for s in seeds
    ]
    results = iter(run_trials(specs, jobs=jobs))
    table: dict[str, dict[str, list[TrialMetrics]]] = {}
    for level in levels:
        table[level] = {c: [trial_metrics(next(results)) for _ in seeds] for c in ("fixed", "adaptive")}
    return table


def format_table(table: dict, levels: dict[str, float], duration_s: float, n_seeds: int,
                 preemption: bool) -> str:
    names = list(levels)
    lines = [
        f"Fixed-time vs adaptive, preemption {'enabled' if preemption else 'disabled'}: "
        f"{n_seeds} paired seeds x {duration_s:g} s per level.",
        "",
        "| Metric | Control | " + " | ".join(
            f"{n} (λ={levels[n]:g}, {levels[n] * 4 * 3600:.0f} veh/h)" for n in names) + " |",
        "|---|---|" + "---|" * len(names),
    ]
    for label, attr, digits in METRICS:
        fixed = {n: [getattr(m, attr) for m in table[n]["fixed"]] for n in names}
        adaptive = {n: [getattr(m, attr) for m in table[n]["adaptive"]] for n in names}
        lines.append(f"| {label} | Fixed | " + " | ".join(fmt_ci(fixed[n], digits) for n in names) + " |")
        lines.append("| | Adaptive | " + " | ".join(fmt_ci(adaptive[n], digits) for n in names) + " |")
        lines.append("| | Change | " + " | ".join(fmt_change(fixed[n], adaptive[n]) for n in names) + " |")
    lines += [
        "",
        "Mean ± 95% confidence interval over seeds. Change = paired difference relative to "
        "fixed-time control, p = paired t-test.",
    ]
    unfinished = sum(m.unfinished for n in names for c in ("fixed", "adaptive") for m in table[n][c])
    measured = sum(m.measured_vehicles for n in names for c in ("fixed", "adaptive") for m in table[n][c])
    lines.append(f"Measured vehicles: {measured}; still on the road at the end of their run: {unfinished}.")
    return "\n".join(lines)


def write_csv(path: Path, table: dict, levels: dict[str, float], seeds: list[int]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["level", "spawn_rate_per_s", "seed", "controller", *TrialMetrics.__dataclass_fields__])
        for level, rate in levels.items():
            for controller in ("fixed", "adaptive"):
                for seed, m in zip(seeds, table[level][controller]):
                    writer.writerow([level, rate, seed, controller, *(round(getattr(m, f), 4) if isinstance(
                        getattr(m, f), float) else getattr(m, f) for f in TrialMetrics.__dataclass_fields__)])


def _parse_levels(text: str) -> dict[str, float]:
    levels = {}
    for item in text.split(","):
        name, _, rate = item.partition("=")
        levels[name.strip()] = float(rate)
    return levels


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION_S,
                        help="simulated seconds per run (default: 1800)")
    parser.add_argument("--seeds", type=int, default=DEFAULT_SEEDS, help="seeds per level, 1..N (default: 10)")
    parser.add_argument("--levels", type=_parse_levels, default=DEFAULT_LEVELS,
                        help='name=arrivals/s/approach pairs (default: "low=0.08,medium=0.12,high=0.18")')
    parser.add_argument("--no-preemption", action="store_true", help="run both controllers without preemption")
    parser.add_argument("--jobs", type=int, default=None, help="parallel processes (default: all CPU cores)")
    parser.add_argument("--csv", type=Path, help="also write every seed's metrics to this CSV file")
    args = parser.parse_args(argv)

    use_utf8_stdout()
    seeds = list(range(1, args.seeds + 1))
    preemption = not args.no_preemption
    table = run_benchmark(args.levels, seeds, args.duration, preemption=preemption, jobs=args.jobs)
    print(format_table(table, args.levels, args.duration, len(seeds), preemption))
    if args.csv:
        write_csv(args.csv, table, args.levels, seeds)
        print(f"\nPer-seed results written to {args.csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
