"""Fixed-timer vs. adaptive benchmark — reproduces the wait-time table.

Runs both controllers headless (no FastAPI, no WebSocket, no vision) against
identical seeded traffic at several demand levels and reports the average
wait time, throughput, and wait-time reduction with its spread across seeds.

Both sides are built through backend/app/core/controller_factory.py, exactly
like the live server, so both get Milestone 6 emergency preemption — the
controller strategy is the only variable.

"Wait time" is the same measurement the analytics dashboard uses: seconds a
vehicle actually spent stopped in a queue (Vehicle.queued_time_s), averaged
over every vehicle that left the map. Free-flow travel is never counted as
waiting.

Usage (from the repo root):

    python scripts/benchmark.py                       # 30 min x 10 seeds x 3 levels
    python scripts/benchmark.py --duration 300 --seeds 3
    python scripts/benchmark.py --csv results.csv     # also write per-seed rows
"""

import argparse
import csv
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (_REPO_ROOT, _REPO_ROOT / "backend"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from app.core.controller_factory import build_controller  # noqa: E402
from simulation.engine import SimulationEngine  # noqa: E402

# Mean arrivals per second per road. 0.12 is the live dashboard's default
# (simulation/config.py BASE_SPAWN_RATE_PER_S); low halves it, high roughly
# doubles it (close to the original 0.35 the dashboard ran at before the
# readability pass).
DEFAULT_LEVELS = {"low": 0.06, "medium": 0.12, "high": 0.25}
DEFAULT_DURATION_S = 1800.0
DEFAULT_SEEDS = 10
DEFAULT_DT = 0.05  # same 20Hz tick the live server uses


@dataclass(frozen=True)
class RunResult:
    controller: str
    level: str
    spawn_rate_per_s: float
    seed: int
    vehicles_exited: int
    avg_wait_s: float | None  # None when no vehicle exited, never a made-up 0


@dataclass(frozen=True)
class LevelSummary:
    level: str
    spawn_rate_per_s: float
    fixed_avg_wait_s: float
    adaptive_avg_wait_s: float
    fixed_throughput: float
    adaptive_throughput: float
    reduction_mean_pct: float
    reduction_sd_pct: float
    adaptive_wins: int
    seeds_compared: int


def run_once(controller_type: str, level: str, spawn_rate_per_s: float, seed: int,
             duration_s: float, dt: float) -> RunResult:
    engine = SimulationEngine(
        controller=build_controller(controller_type),
        seed=seed,
        base_spawn_rate_per_s=spawn_rate_per_s,
    )
    for _ in range(int(round(duration_s / dt))):
        engine.tick(dt)

    roads = engine.intersection.roads.values()
    exited = sum(road.total_exited() for road in roads)
    total_wait = sum(road.total_wait_time_s() for road in roads)
    return RunResult(
        controller=controller_type,
        level=level,
        spawn_rate_per_s=spawn_rate_per_s,
        seed=seed,
        vehicles_exited=exited,
        avg_wait_s=(total_wait / exited) if exited else None,
    )


def summarize(level: str, spawn_rate_per_s: float, fixed: list[RunResult],
              adaptive: list[RunResult]) -> LevelSummary:
    """Pairs runs by seed. A seed only contributes a reduction when both
    sides had departures and the fixed side had non-zero wait — otherwise
    there is nothing honest to divide by, and that seed is left out."""
    reductions = []
    wins = 0
    for f, a in zip(fixed, adaptive):
        if f.avg_wait_s is None or a.avg_wait_s is None or f.avg_wait_s == 0:
            continue
        reductions.append((f.avg_wait_s - a.avg_wait_s) / f.avg_wait_s * 100)
        wins += a.avg_wait_s < f.avg_wait_s

    def mean_wait(runs):
        waits = [r.avg_wait_s for r in runs if r.avg_wait_s is not None]
        return statistics.mean(waits) if waits else float("nan")

    return LevelSummary(
        level=level,
        spawn_rate_per_s=spawn_rate_per_s,
        fixed_avg_wait_s=mean_wait(fixed),
        adaptive_avg_wait_s=mean_wait(adaptive),
        fixed_throughput=statistics.mean(r.vehicles_exited for r in fixed),
        adaptive_throughput=statistics.mean(r.vehicles_exited for r in adaptive),
        reduction_mean_pct=statistics.mean(reductions) if reductions else float("nan"),
        reduction_sd_pct=statistics.stdev(reductions) if len(reductions) > 1 else 0.0,
        adaptive_wins=wins,
        seeds_compared=len(reductions),
    )


def run_benchmark(levels: dict[str, float], seeds: list[int], duration_s: float,
                  dt: float, progress=None) -> tuple[list[LevelSummary], list[RunResult]]:
    summaries, all_runs = [], []
    for level, rate in levels.items():
        fixed = [run_once("fixed", level, rate, s, duration_s, dt) for s in seeds]
        adaptive = [run_once("adaptive", level, rate, s, duration_s, dt) for s in seeds]
        all_runs += fixed + adaptive
        summaries.append(summarize(level, rate, fixed, adaptive))
        if progress:
            progress(f"{level} done")
    return summaries, all_runs


def format_table(summaries: list[LevelSummary], duration_s: float, n_seeds: int) -> str:
    lines = [
        f"Simulated {duration_s / 60:g} min per run, {n_seeds} seeds per level, "
        "both controllers with emergency preemption.",
        "",
        "| Traffic | Arrivals per road | Fixed avg wait | Adaptive avg wait "
        "| Wait reduction | Adaptive better | Vehicles through (fixed / adaptive) |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in summaries:
        lines.append(
            f"| {s.level} | {s.spawn_rate_per_s * 3600:.0f}/h "
            f"| {s.fixed_avg_wait_s:.2f} s | {s.adaptive_avg_wait_s:.2f} s "
            f"| {s.reduction_mean_pct:.1f}% (sd {s.reduction_sd_pct:.1f}) "
            f"| {s.adaptive_wins}/{s.seeds_compared} seeds "
            f"| {s.fixed_throughput:.0f} / {s.adaptive_throughput:.0f} |"
        )
    return "\n".join(lines)


def write_csv(path: Path, runs: list[RunResult]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["level", "spawn_rate_per_s", "seed", "controller", "vehicles_exited", "avg_wait_s"])
        for r in runs:
            writer.writerow([
                r.level, r.spawn_rate_per_s, r.seed, r.controller, r.vehicles_exited,
                "" if r.avg_wait_s is None else round(r.avg_wait_s, 3),
            ])


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
    parser.add_argument("--seeds", type=int, default=DEFAULT_SEEDS,
                        help="number of seeds per level, 1..N (default: 10)")
    parser.add_argument("--levels", type=_parse_levels,
                        default=DEFAULT_LEVELS,
                        help='name=arrivals/s/road pairs (default: "low=0.06,medium=0.12,high=0.25")')
    parser.add_argument("--dt", type=float, default=DEFAULT_DT, help="tick length in seconds (default: 0.05)")
    parser.add_argument("--csv", type=Path, help="also write every individual run to this CSV file")
    args = parser.parse_args(argv)

    seeds = list(range(1, args.seeds + 1))
    summaries, runs = run_benchmark(
        args.levels, seeds, args.duration, args.dt,
        progress=lambda msg: print(msg, file=sys.stderr, flush=True),
    )
    print(format_table(summaries, args.duration, len(seeds)))
    if args.csv:
        write_csv(args.csv, runs)
        print(f"\nPer-seed results written to {args.csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
