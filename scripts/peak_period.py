"""A rush hour: queue build-up and recovery (reviewer request: experiments
above capacity with queue growth, spillback, throughput and delay, to
support conclusions about congestion management).

The steady sweep in oversaturation.py holds demand constant. Congestion at a
real junction comes and goes: demand rises above capacity for a while, the
queue grows, and after the peak the controller has to clear it. Each
60-minute run follows this profile (multiples of the fixed plan's measured
capacity, 10,008 veh/h for the junction):

    0-10 min   0.6x   (steady, below capacity)
    10-15 min  ramp to 1.2x
    15-30 min  1.2x   (peak, 20% above capacity)
    30-35 min  ramp back to 0.6x
    35-60 min  0.6x   (recovery)

Entry backlog and entry at speed are on, as in oversaturation.py, so
unserved demand and spillback are measured; preemption is off (see that
script for why). The Webster plan is timed for the run's average demand.

Metrics per run, from the 1 Hz queue sample q(t) = vehicles queued on the
links + vehicles waiting to enter:
- peak queue: maximum of q(t);
- recovery time: minutes after the peak ends (30 min) until the 60 s moving
  average of q(t) is back within 5 vehicles of its pre-peak level
  (mean over 5-10 min); "not recovered" if that never happens before 60 min;
- spillback: approach-minutes with a blocked entry;
- peak throughput: vehicles leaving per hour during 15-30 min;
- delay: mean delay per arriving vehicle (entry wait + stopped delay, those
  still waiting counted with the delay so far) and the total in vehicle-hours.

Usage (from the repo root):

    python scripts/peak_period.py
    python scripts/peak_period.py --seeds 3     # quick check
"""

import argparse
import csv
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from experiment_common import (  # noqa: E402
    CONTROLLER_LABELS,
    CONTROLLERS,
    TrialSpec,
    fmt_change,
    fmt_ci,
    run_trials,
    use_utf8_stdout,
)

CAPACITY_RATE = 10008 / (4 * 3600)  # fixed plan's capacity, arrivals/s per approach
PROFILE = ((0, 0.6), (600, 0.6), (900, 1.2), (1800, 1.2), (2100, 0.6), (3600, 0.6))
DURATION_S = 3600.0
PEAK = (900, 1800)
PRE_PEAK = (300, 600)
RECOVERY_MARGIN = 5.0
SERIES_STEP_S = 30


def run_metrics(result) -> dict:
    samples = result.samples
    q = [s.queued + s.backlog for s in samples]
    t = [s.t for s in samples]
    pre = statistics.mean(v for v, ti in zip(q, t) if PRE_PEAK[0] <= ti < PRE_PEAK[1])
    recovered_at = math.nan
    window = 60
    for i in range(len(q)):
        if t[i] < PEAK[1] + window:
            continue
        if statistics.mean(q[i - window:i]) <= pre + RECOVERY_MARGIN:
            recovered_at = (t[i] - PEAK[1]) / 60
            break
    exits_peak = sum(1 for v in result.vehicles if v.exit_s is not None and PEAK[0] <= v.exit_s < PEAK[1])
    delays = [v.total_delay_s for v in result.vehicles] + list(result.backlog_waits_s)
    return {
        "peak_queue": max(q),
        "recovery_min": recovered_at,
        "spillback_approach_min": sum(s.approaches_spilled for s in samples) / 60,
        "peak_throughput_vph": exits_peak / ((PEAK[1] - PEAK[0]) / 3600),
        "mean_delay_s": statistics.mean(delays),
        "total_delay_veh_h": sum(delays) / 3600,
        "violations": sum(result.safety_violations.values()),
        "series": [q[i] for i in range(SERIES_STEP_S - 1, len(q), SERIES_STEP_S)],
    }


METRICS = [
    ("Peak queue (veh)", "peak_queue", 0),
    ("Recovery after the peak (min)", "recovery_min", 1),
    ("Spillback (approach-min)", "spillback_approach_min", 1),
    ("Peak throughput (veh/h)", "peak_throughput_vph", 0),
    ("Mean delay per vehicle (s)", "mean_delay_s", 1),
    ("Total delay (veh-h)", "total_delay_veh_h", 0),
]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--preemption", action="store_true", help="enable emergency preemption (default off)")
    parser.add_argument("--jobs", type=int, default=None)
    parser.add_argument("--csv", type=Path, help="per-run metrics")
    parser.add_argument("--series", type=Path, help="mean queue every 30 s per controller (for the figure)")
    args = parser.parse_args(argv)
    use_utf8_stdout()

    seeds = list(range(1, args.seeds + 1))
    keys = [(c, s) for c in CONTROLLERS for s in seeds]
    results = run_trials([TrialSpec(controller=c, seed=s, spawn_rate_per_s=CAPACITY_RATE, duration_s=DURATION_S,
                                    preemption=args.preemption, entry_backlog=True, insert_at_speed=True,
                                    demand_profile=PROFILE) for c, s in keys], jobs=args.jobs)
    runs: dict = {}
    for (c, _), r in zip(keys, results):
        runs.setdefault(c, []).append(run_metrics(r))

    lines = [f"Peak period (0.6x → 1.2x → 0.6x of the fixed plan's capacity over 60 min), {len(seeds)} paired seeds, "
             f"preemption {'on' if args.preemption else 'off'}.", "",
             "| Metric | " + " | ".join(CONTROLLER_LABELS[c] for c in CONTROLLERS) + " |",
             "|---|" + "---|" * len(CONTROLLERS)]
    for label, key, digits in METRICS:
        cells = []
        for c in CONTROLLERS:
            vals = [m[key] for m in runs[c]]
            ok = [v for v in vals if not math.isnan(v)]
            cell = fmt_ci(ok, digits) if ok else "—"
            if key == "recovery_min" and len(ok) < len(vals):
                cell += f" ({len(vals) - len(ok)} not recovered)"
            cells.append(cell)
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    lines.append("| Total delay vs fixed | " + " | ".join(
        "—" if c == "fixed" else fmt_change([m["total_delay_veh_h"] for m in runs["fixed"]],
                                            [m["total_delay_veh_h"] for m in runs[c]]) for c in CONTROLLERS) + " |")
    lines += ["", "Mean ± 95% CI over seeds; recovery averaged over the runs that recovered within the hour.",
              f"Signal safety audit over all {len(results)} runs: {sum(m['violations'] for v in runs.values() for m in v)} violations."]
    print("\n".join(lines))

    if args.csv:
        with args.csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            fields = [k for _, k, _ in METRICS]
            w.writerow(["controller", "seed", *fields])
            for c in CONTROLLERS:
                for s, m in zip(seeds, runs[c]):
                    w.writerow([c, s, *("" if isinstance(m[k], float) and math.isnan(m[k]) else round(m[k], 4) for k in fields)])
    if args.series:
        with args.series.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["controller", "t_s", "mean_queue"])
            for c in CONTROLLERS:
                for i, vals in enumerate(zip(*(m["series"] for m in runs[c]))):
                    w.writerow([c, (i + 1) * SERIES_STEP_S, round(statistics.mean(vals), 2)])


if __name__ == "__main__":
    main()
