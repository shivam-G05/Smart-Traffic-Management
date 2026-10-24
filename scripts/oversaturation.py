"""Above-capacity experiment: fixed-timer vs. adaptive when demand exceeds
what the junction can serve (reviewer request: queue growth, spillback,
throughput and delay above capacity).

The paper's main experiments drop an arrival whose lane entry is blocked,
so above capacity the overload would silently disappear. Here every run
uses two Road options (see simulation/entities/road.py):
- entry_backlog=True: a blocked arrival waits off-map in arrival order and
  enters as soon as there is room, so unserved demand, its waiting time and
  spillback are all measured;
- insert_at_speed=True: a vehicle enters at the fastest speed from which it
  can still stop behind the one ahead. Entering at rest (the default) caps
  the road entry at roughly 2 vehicles per 3 s per approach, which is below
  what the signal discharges — the entry, not the junction, would then set
  the capacity. Measured: 8,887 veh/h at rest vs 9,533 veh/h at speed
  (fixed-time, saturated, one seed).

Two phases:
1. Capacity. Every approach is flooded (--saturation-rate arrivals/s, far
   above capacity) so a queue is always waiting; throughput after the
   warm-up is then the junction's capacity under that controller.
2. Demand sweep. Demand is set to multiples (--ratios) of the fixed-time
   capacity measured in phase 1, and both controllers run on identical
   seeded arrivals (paired by seed, as in benchmark.py).

Metrics per run (after the 60 s warm-up):
- Throughput: vehicles leaving the map per hour.
- Served: share of the vehicles that arrived in the measurement window
  (60 s to 150 s before the end) that had left by the end of the run.
- Delay (served): mean entry wait + stopped delay of those that left.
- Delay (all, lower bound): the same over every arrival in the window,
  counting vehicles still waiting with the delay accrued so far — a lower
  bound, since their wait is not over.
- Queue growth: least-squares slope of (queued on the links + backlog)
  over time, in vehicles per minute; ~0 means the queue is stable.
- Final queue: queued + backlog when the run ends.
- Spillback: share of approach-seconds whose entry was blocked (backlog
  > 0), i.e. the queue had reached the start of the 200 m approach.
- Mean green: average length of the greens that started after the warm-up
  (explains capacity differences: every phase change costs 4 s of yellow
  and all-red).

Usage (from the repo root):

    python scripts/oversaturation.py
    python scripts/oversaturation.py --ratios 0.9,1.1,1.3 --seeds 5
    python scripts/oversaturation.py --duration 600 --seeds 2 --capacity-seeds 2   # quick check
"""

import argparse
import csv
import math
import statistics
import sys
from dataclasses import dataclass, fields
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

from experiment_common import (  # noqa: E402
    CONTROLLER_LABELS,
    CONTROLLERS,
    TrialResult,
    TrialSpec,
    zone_options,
    fmt_change,
    fmt_ci,
    mean_ci,
    mean_or_nan,
    parse_controllers,
    run_trials,
    use_utf8_stdout,
)

WARMUP_S = 60.0
ENTRY_TAIL_S = 150.0
DEFAULT_RATIOS = [0.6, 0.8, 0.9, 1.0, 1.2, 1.5]
DEFAULT_SEEDS = 10
DEFAULT_CAPACITY_SEEDS = 5
DEFAULT_DURATION_S = 1800.0
# Arrivals/s per approach for the capacity runs. Demand is redrawn every
# 15 s as rate x U(0.4, 1.6), so even the lowest draw (0.6/s, 2160 veh/h
# per approach) is far above what one approach can discharge.
DEFAULT_SATURATION_RATE = 1.5


@dataclass(frozen=True)
class OverMetrics:
    demand_vph: float
    throughput_vph: float
    served_pct: float
    delay_served_s: float
    delay_all_lb_s: float
    queue_growth_vpm: float
    final_queue: float
    spillback_pct: float
    mean_green_s: float
    mean_queued: float        # vehicles queued on the links (excludes the backlog)
    first_spillback_s: float  # nan if no approach ever spilled back
    safety_violations: int    # simulation/signal_audit.py, every step (should be 0)


def over_metrics(result: TrialResult, warmup_s: float = WARMUP_S,
                 entry_tail_s: float = ENTRY_TAIL_S) -> OverMetrics:
    duration = result.spec.duration_s
    hours = (duration - warmup_s) / 3600
    window = (warmup_s, duration - entry_tail_s)

    def in_window(arrival_s: float) -> bool:
        return window[0] <= arrival_s < window[1]

    arrived = [v for v in result.vehicles if in_window(v.arrival_s)]
    waiting = [w for w in result.backlog_waits_s if in_window(duration - w)]
    served = [v for v in arrived if v.exit_s is not None]
    n_arrived = len(arrived) + len(waiting)

    all_delays = [v.total_delay_s for v in arrived] + waiting
    after = [s for s in result.samples if s.t > warmup_s]
    if len(after) >= 2:
        t = np.array([s.t for s in after])
        q = np.array([s.queued + s.backlog for s in after], dtype=float)
        growth = float(np.polyfit(t, q, 1)[0]) * 60
    else:
        growth = float("nan")
    spilled = [s.t for s in result.samples if s.approaches_spilled]

    all_arrivals = sum(1 for v in result.vehicles if v.arrival_s > warmup_s) + sum(
        1 for w in result.backlog_waits_s if duration - w > warmup_s)
    return OverMetrics(
        demand_vph=all_arrivals / hours,
        throughput_vph=sum(1 for v in result.vehicles if v.exit_s is not None and v.exit_s > warmup_s) / hours,
        served_pct=100 * len(served) / n_arrived if n_arrived else float("nan"),
        delay_served_s=mean_or_nan(v.total_delay_s for v in served),
        delay_all_lb_s=mean_or_nan(all_delays),
        queue_growth_vpm=growth,
        final_queue=float(after[-1].queued + after[-1].backlog) if after else float("nan"),
        spillback_pct=100 * mean_or_nan(s.approaches_spilled / 4 for s in after),
        mean_green_s=mean_or_nan(length for start, length in result.green_durations_s if start > warmup_s),
        mean_queued=mean_or_nan(s.queued for s in after),
        first_spillback_s=spilled[0] if spilled else float("nan"),
        safety_violations=sum(result.safety_violations.values()),
    )


def _spec(controller: str, seed: int, rate: float, duration_s: float, dt: float,
          preemption: bool = True, reaction_time_s: float = 0.0,
          saturation_flow_vph: float | None = None, hold_zone_m: float | None = None) -> TrialSpec:
    return TrialSpec(controller=controller, seed=seed, spawn_rate_per_s=rate, duration_s=duration_s,
                     dt=dt, preemption=preemption, entry_backlog=True, insert_at_speed=True,
                     reaction_time_s=reaction_time_s, saturation_flow_vph=saturation_flow_vph,
                     options=zone_options(controller, hold_zone_m))


def measure_capacity(seeds: list[int], duration_s: float, saturation_rate: float, jobs: int | None,
                     dt: float = 0.05, preemption: bool = True,
                     controllers: tuple[str, ...] = CONTROLLERS,
                     reaction_time_s: float = 0.0,
                     saturation_flow_vph: float | None = None,
                     hold_zone_m: float | None = None) -> dict[str, list[OverMetrics]]:
    specs = [_spec(c, s, saturation_rate, duration_s, dt, preemption, reaction_time_s, saturation_flow_vph, hold_zone_m)
             for c in controllers for s in seeds]
    results = iter(run_trials(specs, jobs=jobs))
    return {c: [over_metrics(next(results)) for _ in seeds] for c in controllers}


def run_sweep(rates: list[float], seeds: list[int], duration_s: float, jobs: int | None,
              dt: float = 0.05, preemption: bool = True,
              controllers: tuple[str, ...] = CONTROLLERS,
              reaction_time_s: float = 0.0,
              saturation_flow_vph: float | None = None,
              hold_zone_m: float | None = None) -> list[dict[str, list[OverMetrics]]]:
    specs = [_spec(c, s, rate, duration_s, dt, preemption, reaction_time_s, saturation_flow_vph, hold_zone_m)
             for rate in rates for c in controllers for s in seeds]
    results = iter(run_trials(specs, jobs=jobs))
    return [{c: [over_metrics(next(results)) for _ in seeds] for c in controllers} for _ in rates]


SWEEP_METRICS = [
    ("Realized demand (veh/h)", "demand_vph", 0),
    ("Throughput (veh/h)", "throughput_vph", 0),
    ("Served (%)", "served_pct", 1),
    ("Delay, served vehicles (s)", "delay_served_s", 1),
    ("Delay, all arrivals, lower bound (s)", "delay_all_lb_s", 1),
    ("Queue growth (veh/min)", "queue_growth_vpm", 2),
    ("Final queue (veh)", "final_queue", 0),
    ("Spillback (% of approach-time)", "spillback_pct", 1),
    ("Mean green (s)", "mean_green_s", 1),
]


def _fmt_first_spillback(values: list[float]) -> str:
    hit = [v for v in values if not math.isnan(v)]
    if not hit:
        return f"none (0/{len(values)} seeds)"
    return f"{statistics.median(hit):.0f} s median ({len(hit)}/{len(values)} seeds)"


def format_report(capacity: dict[str, list[OverMetrics]], ratios: list[float], rates: list[float],
                  sweep: list[dict[str, list[OverMetrics]]], duration_s: float, n_seeds: int,
                  n_capacity_seeds: int, saturation_rate: float, preemption: bool = True) -> str:
    controllers = list(capacity)
    base = controllers[0]

    def col(runs, attr):
        return [getattr(m, attr) for m in runs]

    lines = [
        f"Emergency preemption {'enabled' if preemption else 'disabled'}.",
        "",
        f"Capacity (every approach flooded at {saturation_rate:g} arrivals/s, {n_capacity_seeds} seeds x "
        f"{duration_s:g} s; throughput after the {WARMUP_S:g} s warm-up):",
        "",
        "| Control | Capacity (veh/h, junction) | Per approach (veh/h) | Mean green (s) | Mean queued on links (veh) |",
        "|---|---|---|---|---|",
    ]
    for c in controllers:
        mean, half = mean_ci(col(capacity[c], "throughput_vph"))
        lines.append(
            f"| {CONTROLLER_LABELS[c]} | {mean:.0f} ± {half:.0f} | {mean / 4:.0f} "
            f"| {fmt_ci(col(capacity[c], 'mean_green_s'), 1)} | {fmt_ci(col(capacity[c], 'mean_queued'), 1)} |"
        )
    for c in controllers[1:]:
        lines.append(
            f"| {CONTROLLER_LABELS[c]} vs fixed "
            f"| {fmt_change(col(capacity[base], 'throughput_vph'), col(capacity[c], 'throughput_vph'))} "
            f"| | {fmt_change(col(capacity[base], 'mean_green_s'), col(capacity[c], 'mean_green_s'))} | |"
        )

    header = " | ".join(f"{r:g}x (λ={rate:.3f}, {rate * 4 * 3600:.0f} veh/h)" for r, rate in zip(ratios, rates))
    lines += [
        "",
        f"Demand sweep ({n_seeds} paired seeds x {duration_s:g} s; demand as a multiple of the "
        "fixed-time capacity above):",
        "",
        f"| Metric | Control | {header} |",
        "|---|---|" + "---|" * len(ratios),
    ]
    for label, attr, digits in SWEEP_METRICS:
        values = {c: [col(level[c], attr) for level in sweep] for c in controllers}
        for i, c in enumerate(controllers):
            lines.append(f"| {label if i == 0 else ''} | {CONTROLLER_LABELS[c]} | "
                         + " | ".join(fmt_ci(v, digits) for v in values[c]) + " |")
        if attr != "demand_vph":
            for c in controllers[1:]:
                lines.append(f"| | {CONTROLLER_LABELS[c]} vs fixed | " + " | ".join(
                    fmt_change(f, a) for f, a in zip(values[base], values[c])) + " |")
    for c in controllers:
        lines.append(f"| First spillback | {CONTROLLER_LABELS[c]} | " + " | ".join(
            _fmt_first_spillback(col(level[c], "first_spillback_s")) for level in sweep) + " |")
    lines += [
        "",
        "Mean ± 95% confidence interval over seeds; \"vs fixed\" = paired difference relative to fixed-time "
        "control, p = paired t-test. Demand is the realized arrival rate after the warm-up.",
    ]
    runs = [m for c in controllers for m in capacity[c]] + [m for level in sweep for c in controllers for m in level[c]]
    lines.append(f"Signal safety audit over all {len(runs)} runs: {sum(m.safety_violations for m in runs)} violations.")
    return "\n".join(lines)


def write_csv(path: Path, ratios, rates, seeds, sweep, capacity=None, capacity_seeds=(),
              saturation_rate=DEFAULT_SATURATION_RATE) -> None:
    names = [f.name for f in fields(OverMetrics)]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ratio", "spawn_rate_per_s", "seed", "controller", *names])
        for c, runs in (capacity or {}).items():  # ratio "capacity": the flooded capacity runs
            for seed, m in zip(capacity_seeds, runs):
                writer.writerow(["capacity", saturation_rate, seed, c, *(round(getattr(m, n), 4) for n in names)])
        for ratio, rate, level in zip(ratios, rates, sweep):
            for c in level:
                for seed, m in zip(seeds, level[c]):
                    writer.writerow([ratio, round(rate, 5), seed, c, *(round(getattr(m, n), 4) for n in names)])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ratios", type=lambda s: [float(x) for x in s.split(",")], default=DEFAULT_RATIOS,
                        help="demand as multiples of the fixed-time capacity (default: 0.6,0.8,0.9,1.0,1.2,1.5)")
    parser.add_argument("--seeds", type=int, default=DEFAULT_SEEDS, help="paired seeds per demand level (default: 10)")
    parser.add_argument("--capacity-seeds", type=int, default=DEFAULT_CAPACITY_SEEDS,
                        help="seeds for the capacity runs (default: 5)")
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION_S,
                        help="simulated seconds per run (default: 1800)")
    parser.add_argument("--saturation-rate", type=float, default=DEFAULT_SATURATION_RATE,
                        help="arrivals/s per approach for the capacity runs (default: 1.5)")
    parser.add_argument("--controllers", type=parse_controllers, default=CONTROLLERS,
                        help="comma-separated, fixed first (default: fixed,adaptive,adaptive_hold)")
    parser.add_argument("--reaction-time", type=float, default=0.0,
                        help="driver reaction time in s (default 0, the paper's model; see scripts/kinematics_check.py)")
    parser.add_argument("--hold-zone", type=float, default=None,
                        help="stop-line zone in m for the gap-out controllers (default 10; see scripts/tune_zone.py)")
    parser.add_argument("--saturation-flow", type=float, default=None,
                        help="veh/h per approach for the Webster baseline (default: decision_engine/webster.py)")
    parser.add_argument("--no-preemption", action="store_true",
                        help="run without emergency preemption (see the note on emergency frequency above)")
    parser.add_argument("--jobs", type=int, default=None, help="parallel processes (default: all CPU cores)")
    parser.add_argument("--csv", type=Path, help="also write every sweep run's metrics to this CSV file")
    args = parser.parse_args(argv)

    use_utf8_stdout()
    preemption = not args.no_preemption
    capacity_seeds = list(range(101, 101 + args.capacity_seeds))  # kept apart from the sweep seeds
    seeds = list(range(1, args.seeds + 1))
    capacity = measure_capacity(capacity_seeds, args.duration, args.saturation_rate, args.jobs,
                                preemption=preemption, controllers=args.controllers, reaction_time_s=args.reaction_time,
                                saturation_flow_vph=args.saturation_flow, hold_zone_m=args.hold_zone)
    fixed_capacity_vph = statistics.mean(m.throughput_vph for m in capacity["fixed"])
    rates = [r * fixed_capacity_vph / (4 * 3600) for r in args.ratios]
    sweep = run_sweep(rates, seeds, args.duration, args.jobs, preemption=preemption, controllers=args.controllers,
                      reaction_time_s=args.reaction_time, saturation_flow_vph=args.saturation_flow,
                      hold_zone_m=args.hold_zone)
    if args.reaction_time:
        print(f"Driver reaction time: {args.reaction_time:g} s (calibrated kinematics)")
        print()
    print(format_report(capacity, args.ratios, rates, sweep, args.duration, len(seeds),
                        len(capacity_seeds), args.saturation_rate, preemption))
    if args.csv:
        write_csv(args.csv, args.ratios, rates, seeds, sweep, capacity, capacity_seeds, args.saturation_rate)
        print(f"\nPer-seed results written to {args.csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
