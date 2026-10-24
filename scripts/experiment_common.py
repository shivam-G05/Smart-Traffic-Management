"""Shared machinery for the experiment scripts (benchmark.py,
oversaturation.py): run one seeded headless trial, record every vehicle and
a 1 Hz sample of the junction, and the paired statistics the paper reports.

Like backend/app, scripts/ is composition-root code: it is allowed to
import simulation/, decision_engine/ and analytics/ together.
"""

import math
import os
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (_REPO_ROOT, _REPO_ROOT / "backend"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import numpy as np  # noqa: E402
from scipy import stats  # noqa: E402

from analytics.config import CONGESTION_HIGH_MIN  # noqa: E402
from app.core.controller_factory import build_controller  # noqa: E402
from decision_engine.density import road_density_score  # noqa: E402
from simulation.config import LightState, RoadName  # noqa: E402
from simulation.engine import SimulationEngine  # noqa: E402


@dataclass(frozen=True)
class TrialSpec:
    controller: str              # "fixed" or "adaptive"
    seed: int
    spawn_rate_per_s: float      # mean arrivals per second per approach
    duration_s: float = 1800.0
    dt: float = 0.05             # same 20 Hz step the live server uses
    preemption: bool = True
    entry_backlog: bool = False  # see Road: keep blocked arrivals instead of dropping them
    insert_at_speed: bool = False  # see Road: enter at a safe speed instead of at rest


@dataclass(frozen=True)
class VehicleRecord:
    arrival_s: float             # when it arrived (= entry_s unless it waited in the backlog)
    entry_s: float               # when it appeared on the road
    exit_s: float | None         # None if still on the road when the run ended
    stopped_delay_s: float       # time queued upstream of the stop line (Vehicle.queued_time_s)
    entry_wait_s: float          # time spent in the entry backlog
    emergency: bool

    @property
    def total_delay_s(self) -> float:
        return self.stopped_delay_s + self.entry_wait_s


@dataclass(frozen=True)
class Sample:
    t: float
    queued: int                  # vehicles queued on the links, summed over approaches
    backlog: int                 # arrivals waiting to enter, summed over approaches
    approaches_spilled: int      # approaches whose entry is blocked (backlog > 0)
    high_density: bool           # at least one approach above CONGESTION_HIGH_MIN


@dataclass(frozen=True)
class TrialResult:
    spec: TrialSpec
    vehicles: list[VehicleRecord]
    samples: list[Sample]
    backlog_waits_s: list[float]  # vehicles still waiting to enter at the end
    green_durations_s: list[tuple[float, float]]  # (start time, length) of every completed green, both directions


def run_trial(spec: TrialSpec) -> TrialResult:
    engine = SimulationEngine(
        controller=build_controller(spec.controller, preemption=spec.preemption),
        seed=spec.seed,
        base_spawn_rate_per_s=spec.spawn_rate_per_s,
        entry_backlog=spec.entry_backlog,
        insert_at_speed=spec.insert_at_speed,
    )
    roads = list(engine.intersection.roads.values())
    lanes = [lane for road in roads for lane in road.lanes]
    steps = int(round(spec.duration_s / spec.dt))
    sample_every = int(round(1.0 / spec.dt))

    on_road: dict[int, tuple] = {}  # vehicle id -> (Vehicle, entry time)
    vehicles: list[VehicleRecord] = []
    samples: list[Sample] = []
    # One road per signal group is enough to time its greens (both roads of
    # a group always show the same light).
    group_lights = [engine.intersection.roads[RoadName.NORTH].light, engine.intersection.roads[RoadName.EAST].light]
    green_since: list[float | None] = [None, None]
    greens: list[tuple[float, float]] = []

    def record(vehicle, entry_s, exit_s):
        vehicles.append(
            VehicleRecord(
                arrival_s=entry_s - vehicle.entry_wait_s,
                entry_s=entry_s,
                exit_s=exit_s,
                stopped_delay_s=vehicle.queued_time_s,
                entry_wait_s=vehicle.entry_wait_s,
                emergency=vehicle.is_emergency,
            )
        )

    for step in range(1, steps + 1):
        engine.tick(spec.dt)
        t = step * spec.dt

        for i, light in enumerate(group_lights):
            is_green = light.state == LightState.GREEN
            if is_green and green_since[i] is None:
                green_since[i] = t
            elif not is_green and green_since[i] is not None:
                greens.append((green_since[i], t - green_since[i]))
                green_since[i] = None

        # New vehicles only ever join a lane's tail and leave from its head,
        # so comparing ids each step finds every entry and exit exactly.
        present = set()
        for lane in lanes:
            for vehicle in lane.vehicles:
                present.add(vehicle.id)
                if vehicle.id not in on_road:
                    on_road[vehicle.id] = (vehicle, t)
        for vehicle_id in sorted(on_road.keys() - present):  # sorted: deterministic record order
            vehicle, entry_s = on_road.pop(vehicle_id)
            record(vehicle, entry_s, t)

        if step % sample_every == 0:
            backlogs = [road.backlog_count for road in roads]
            samples.append(
                Sample(
                    t=round(t, 3),
                    queued=sum(road.total_queue_length() for road in roads),
                    backlog=sum(backlogs),
                    approaches_spilled=sum(1 for b in backlogs if b),
                    high_density=any(road_density_score(road) > CONGESTION_HIGH_MIN for road in roads),
                )
            )

    for vehicle, entry_s in on_road.values():
        record(vehicle, entry_s, None)
    backlog_waits = [w for road in roads for w in road.backlog_waits_s()]
    return TrialResult(
        spec=spec,
        vehicles=vehicles,
        samples=samples,
        backlog_waits_s=backlog_waits,
        green_durations_s=greens,
    )


def run_trials(specs: list[TrialSpec], jobs: int | None = None) -> list[TrialResult]:
    """Runs trials in parallel processes (each trial is independent and
    seeded, so the results are identical to running them one by one)."""
    jobs = jobs or os.cpu_count() or 1
    if jobs == 1:
        return [run_trial(spec) for spec in specs]
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(run_trial, specs))


# --- Statistics ------------------------------------------------------------

def mean_ci(values: list[float]) -> tuple[float, float]:
    """Mean and half-width of its 95% confidence interval (t distribution)."""
    values = [v for v in values if not math.isnan(v)]
    if not values:
        return float("nan"), float("nan")
    mean = statistics.mean(values)
    if len(values) < 2:
        return mean, 0.0
    half = stats.t.ppf(0.975, len(values) - 1) * statistics.stdev(values) / math.sqrt(len(values))
    return mean, half


def paired_change(baseline: list[float], treatment: list[float]) -> tuple[float, float]:
    """Paired difference relative to the baseline mean, in percent, and the
    paired t-test p-value. Runs are paired by seed (same arrivals)."""
    pairs = [(b, t) for b, t in zip(baseline, treatment) if not (math.isnan(b) or math.isnan(t))]
    if not pairs:
        return float("nan"), float("nan")
    base = [b for b, _ in pairs]
    treat = [t for _, t in pairs]
    diffs = [t - b for b, t in pairs]
    change = statistics.mean(diffs) / statistics.mean(base) * 100 if statistics.mean(base) else float("nan")
    if len(pairs) < 2 or all(d == diffs[0] for d in diffs):
        return change, float("nan")
    return change, float(stats.ttest_rel(treat, base).pvalue)


def percentile(values: list[float], q: float) -> float:
    return float(np.percentile(values, q)) if values else float("nan")


def mean_or_nan(values) -> float:
    values = list(values)
    return statistics.mean(values) if values else float("nan")


# --- Formatting ------------------------------------------------------------

def fmt_ci(values: list[float], digits: int = 2) -> str:
    mean, half = mean_ci(values)
    if math.isnan(mean):
        return "n/a"
    return f"{mean:.{digits}f} ± {half:.{digits}f}"


def fmt_p(p: float) -> str:
    if math.isnan(p):
        return "n/a"
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def fmt_change(baseline: list[float], treatment: list[float]) -> str:
    change, p = paired_change(baseline, treatment)
    if math.isnan(change):
        return "n/a"
    return f"{change:+.1f}% (p {fmt_p(p)})"


def use_utf8_stdout() -> None:
    """Tables use ± and −; Windows consoles default to a code page that
    cannot print them."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
