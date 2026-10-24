"""Checks the simulator's queue-discharge kinematics against standard
field values (reviewer request: validate kinematic outputs against
external ground truth).

At a signal, traffic engineers measure the time between successive queued
vehicles crossing the stop line after the green starts. From the 5th
vehicle on the headway settles to the saturation headway h_s (saturation
flow 3600 / h_s per lane); the extra time taken by the first four is the
start-up lost time. The Highway Capacity Manual's base values are a
saturation flow of 1900 passenger cars per hour per lane (h_s ~ 1.9 s) and
a start-up lost time of about 2 s.

This script measures the same quantities in the simulator: fixed-time
control, every approach saturated (entry backlog + entry at safe speed, as
in scripts/oversaturation.py, so long queues form every cycle), only
greens whose lane queue held at least 8 vehicles when the green began.
It runs twice — with the full vehicle mix and with cars only, the latter
being the like-for-like comparison with the passenger-car base values.

Usage (from the repo root):

    python scripts/kinematics_check.py
    python scripts/kinematics_check.py --seeds 2 --duration 600
"""

import argparse
import json
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import experiment_common  # noqa: E402,F401  (puts the repo root on sys.path)
from experiment_common import mean_ci, use_utf8_stdout  # noqa: E402

import simulation.entities.road as road_module  # noqa: E402
from simulation.config import STOP_LINE_POS_M, LightState, VehicleType  # noqa: E402
from simulation.controllers.fixed_timer_controller import FixedTimerController  # noqa: E402
from simulation.engine import SimulationEngine  # noqa: E402

HCM_SATURATION_FLOW = 1900  # passenger cars / hour / lane (base value)
HCM_STARTUP_LOST_TIME_S = 2.0
MIN_QUEUE = 8
POSITIONS = 10  # queue positions reported
QUEUED_SPEED = 0.5


def run(args):
    seed, cars_only, duration_s, reaction_time_s = args
    if cars_only:
        # Arrival mix is a module-level table in road.py; this process only.
        road_module._VEHICLE_TYPES = [VehicleType.CAR]
        road_module._SPAWN_WEIGHTS = [1.0]
    engine = SimulationEngine(controller=FixedTimerController(), seed=seed, base_spawn_rate_per_s=1.5,
                              entry_backlog=True, insert_at_speed=True,
                              reaction_time_s=reaction_time_s)
    dt = 0.05
    lanes = [(road, lane) for road in engine.intersection.roads.values() for lane in road.lanes]
    prev_pos: dict[int, float] = {}
    prev_state = {id(lane): LightState.RED for _, lane in lanes}
    # per lane: (green start time, ids of the queued vehicles in queue order, crossing times so far)
    active: dict[int, tuple[float, list[int], list[float]]] = {}
    headways = [[] for _ in range(POSITIONS)]
    for step in range(1, int(duration_s / dt) + 1):
        engine.tick(dt)
        t = step * dt
        for road, lane in lanes:
            key = id(lane)
            state = road.light.state
            if state == LightState.GREEN and prev_state[key] != LightState.GREEN:
                queue = sorted((v for v in lane.vehicles if v.position_m < STOP_LINE_POS_M and v.speed_mps < QUEUED_SPEED),
                               key=lambda v: -v.position_m)
                active[key] = (t - dt, [v.id for v in queue], []) if len(queue) >= MIN_QUEUE and t > 60 else None
            elif state != LightState.GREEN and prev_state[key] == LightState.GREEN:
                active[key] = None
            prev_state[key] = state

            entry = active.get(key)
            for v in lane.vehicles:
                before = prev_pos.get(v.id)
                if entry and before is not None and before < STOP_LINE_POS_M <= v.position_m and state == LightState.GREEN:
                    start, order, crossings = entry
                    if len(crossings) < len(order) and order[len(crossings)] == v.id:
                        # interpolate the crossing instant within the step
                        frac = (STOP_LINE_POS_M - before) / max(1e-9, v.position_m - before)
                        crossings.append(t - dt + frac * dt)
                        i = len(crossings) - 1
                        if i < POSITIONS:
                            headways[i].append(crossings[i] - (start if i == 0 else crossings[i - 1]))
                prev_pos[v.id] = v.position_m
    return cars_only, headways


def summarize(results):
    out = {}
    for cars_only in (False, True):
        merged = [[] for _ in range(POSITIONS)]
        for flag, headways in results:
            if flag == cars_only:
                for i in range(POSITIONS):
                    merged[i].extend(headways[i])
        by_pos = [statistics.mean(h) if h else float("nan") for h in merged]
        sat = [h for i in range(4, POSITIONS) for h in merged[i]]
        hs = statistics.mean(sat)
        lost = sum(by_pos[i] - hs for i in range(4))
        out["cars only" if cars_only else "full vehicle mix"] = {
            "headway_by_position": [round(x, 2) for x in by_pos],
            "samples_by_position": [len(h) for h in merged],
            "saturation_headway_s": round(hs, 3),
            "saturation_headway_ci": round(mean_ci(sat)[1], 3),
            "saturation_flow_vphpl": round(3600 / hs),
            "startup_lost_time_s": round(lost, 2),
        }
    return out


def format_report(summary):
    lines = [
        "Queue discharge at the stop line, fixed-time control, saturated approaches "
        f"(greens with >= {MIN_QUEUE} queued vehicles in the lane).",
        "",
        "| | Saturation headway (s) | Saturation flow (veh/h/lane) | Start-up lost time (s) |",
        "|---|---|---|---|",
    ]
    for name, s in summary.items():
        lines.append(f"| Simulator, {name} | {s['saturation_headway_s']:.2f} ± {s['saturation_headway_ci']:.2f} "
                     f"| {s['saturation_flow_vphpl']} | {s['startup_lost_time_s']:.2f} |")
    lines.append(f"| HCM base values | {3600 / HCM_SATURATION_FLOW:.2f} | {HCM_SATURATION_FLOW} | ≈ {HCM_STARTUP_LOST_TIME_S:.1f} |")
    lines += ["", "Mean headway by queue position (s):", "",
              "| Position | " + " | ".join(str(i + 1) for i in range(POSITIONS)) + " |",
              "|---|" + "---|" * POSITIONS]
    for name, s in summary.items():
        lines.append(f"| {name} | " + " | ".join(f"{h:.2f}" for h in s["headway_by_position"]) + " |")
    lines.append("\nPosition 1 is measured from the start of green; the saturation headway is the mean from position 5 on.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seeds", type=int, default=5, help="seeds per vehicle mix (default: 5)")
    parser.add_argument("--duration", type=float, default=1800.0, help="simulated seconds per run (default: 1800)")
    parser.add_argument("--reaction-time", type=float, default=0.0,
                        help="driver reaction time in s (default 0, the paper's model; see lane.safe_following_speed)")
    parser.add_argument("--json", type=Path, help="also write the summary to this JSON file")
    args = parser.parse_args(argv)
    use_utf8_stdout()
    print(f"Reaction time: {args.reaction_time:g} s")
    print()
    jobs = [(s, cars, args.duration, args.reaction_time) for cars in (False, True) for s in range(1, args.seeds + 1)]
    with ProcessPoolExecutor() as pool:
        results = list(pool.map(run, jobs))
    summary = summarize(results)
    print(format_report(summary))
    if args.json:
        args.json.write_text(json.dumps(summary, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
