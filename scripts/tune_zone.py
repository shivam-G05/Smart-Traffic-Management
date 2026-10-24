"""Tunes the stop-line zone of the gap-out test (discharge hold and actuated
control) for a given car-following model, on a tuning seed that no reported
result uses.

The zone decides when a served queue has "gapped out": no vehicle within it
means the queue has cleared. Its right length depends on how far apart
discharging vehicles are, i.e. on the kinematics: with the default model
(no reaction time) followers trail by 2 m and 10 m works; with a realistic
reaction time (scripts/kinematics_check.py: 1.6 s) a discharging queue
spreads out to ~20 m gaps, so a 10 m zone empties mid-queue and ends the
green too early. Real actuated controllers set their gap (passage time) for
local conditions for the same reason.

For each zone the discharge-hold controller runs on the tuning seed at
0.6, 0.9, 1.0 and 1.2 times the fixed plan's capacity (entry backlog and
entry at speed, preemption off, as scripts/oversaturation.py) and at
saturation; the objective is the mean delay (including vehicles still
waiting) relative to the fixed plan, averaged over the four demands.

Usage (from the repo root):

    python scripts/tune_zone.py --reaction-time 1.6 --capacity 6148
    python scripts/tune_zone.py --zones 10,15,20,30          # default model
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from experiment_common import TrialSpec, run_trials, use_utf8_stdout  # noqa: E402
from oversaturation import over_metrics  # noqa: E402

TUNING_SEED = 1000
RATIOS = (0.6, 0.9, 1.0, 1.2)


def spec(controller, rate, args, zone=None):
    return TrialSpec(controller=controller, seed=TUNING_SEED, spawn_rate_per_s=rate, duration_s=args.duration,
                     preemption=False, entry_backlog=True, insert_at_speed=True, reaction_time_s=args.reaction_time,
                     options=(("discharge_zone_m", float(zone)),) if zone is not None else ())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reaction-time", type=float, default=0.0)
    parser.add_argument("--capacity", type=float, default=10008.0,
                        help="fixed plan's junction capacity in veh/h for this model (default: the default model's)")
    parser.add_argument("--zones", type=lambda s: [float(x) for x in s.split(",")], default=[10, 15, 20, 25, 30, 40])
    parser.add_argument("--duration", type=float, default=1800.0)
    parser.add_argument("--jobs", type=int, default=None)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    use_utf8_stdout()

    rates = [r * args.capacity / (4 * 3600) for r in RATIOS]
    keys = [("fixed", None, i) for i in range(len(rates))] + [("hold", z, i) for z in args.zones for i in range(len(rates))]
    keys += [("fixed", None, "sat")] + [("hold", z, "sat") for z in args.zones]
    specs = [spec("fixed" if c == "fixed" else "adaptive_hold", 1.5 if i == "sat" else rates[i], args, z) for c, z, i in keys]
    res = {k: over_metrics(r) for k, r in zip(keys, run_trials(specs, jobs=args.jobs))}

    lines = [f"Stop-line zone tuning: reaction time {args.reaction_time:g} s, tuning seed {TUNING_SEED}.", "",
             "| Zone (m) | " + " | ".join(f"delay {r:g}x (s)" for r in RATIOS) + " | Capacity (veh/h) | Mean green sat. (s) | Objective |",
             "|---|" + "---|" * (len(RATIOS) + 3)]
    fixed_delay = [res[("fixed", None, i)].delay_all_lb_s for i in range(len(rates))]
    lines.append("| fixed plan | " + " | ".join(f"{d:.1f}" for d in fixed_delay) +
                 f" | {res[('fixed', None, 'sat')].throughput_vph:.0f} | 20.0 | 1.000 |")
    scores = {}
    for z in args.zones:
        delays = [res[("hold", z, i)].delay_all_lb_s for i in range(len(rates))]
        scores[z] = statistics.mean(d / f for d, f in zip(delays, fixed_delay))
        sat = res[("hold", z, "sat")]
        lines.append(f"| {z:g} | " + " | ".join(f"{d:.1f}" for d in delays) +
                     f" | {sat.throughput_vph:.0f} | {sat.mean_green_s:.1f} | {scores[z]:.3f} |")
    best = min(scores, key=scores.get)
    violations = sum(m.safety_violations for m in res.values())
    lines += ["", f"Best zone: {best:g} m (objective = mean delay relative to the fixed plan over the four demands).",
              f"Signal safety audit over all {len(res)} runs: {violations} violations."]
    print("\n".join(lines))
    if args.json:
        args.json.write_text(json.dumps({"reaction_time_s": args.reaction_time, "best_zone_m": best,
                                         "scores": {str(k): v for k, v in scores.items()},
                                         "runs": len(res), "violations": violations}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
