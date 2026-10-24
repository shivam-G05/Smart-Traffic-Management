"""Turns the experiment CSVs in results/ into every table and quoted number
of the revised manuscript, so no number in the paper is typed by hand.

    python paper/make_tables.py        # from the repo root -> paper/build/numbers.json

Reads (written by the scripts in scripts/ with --csv):
    results/table2_preemption_on.csv, results/table2_preemption_off.csv
    results/ablation.csv
    results/oversaturation_preemption_off.csv, results/oversaturation_preemption_on.csv
"""

import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from scipy import stats  # noqa: E402

from experiment_common import CONTROLLER_LABELS, mean_ci, paired_change  # noqa: E402

RESULTS = ROOT / "results"
OUT = ROOT / "paper" / "build" / "numbers.json"
LEVELS = ["low", "medium", "high"]
CONTROLLERS = list(CONTROLLER_LABELS)


def read(name):
    with (RESULTS / name).open(newline="") as f:
        return list(csv.DictReader(f))


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def ci(values, digits):
    m, h = mean_ci(values)
    return f"{m:.{digits}f} ± {h:.{digits}f}"


def p_text(p):
    if math.isnan(p):
        return "n/a"
    return "< 0.001" if p < 0.001 else f"{p:.3f}" if p < 0.01 else f"{p:.2f}"


def change_text(base, treat):
    c, p = paired_change(base, treat)
    return {"pct": round(c, 1), "p": p_text(p), "text": f"{c:+.1f}%".replace("-", "−")}


def by(rows, *keys):
    out = defaultdict(list)
    for r in rows:
        out[tuple(r[k] for k in keys)].append(r)
    return out


def ordered(rows):
    return sorted(rows, key=lambda r: int(r["seed"]))


# --- Table II (paper demand levels, all controllers) ---------------------

def table2(name):
    rows = by(read(name), "level", "controller")
    metrics = {"mean_delay_s": 2, "p95_delay_s": 1, "mean_queue": 2, "high_density_pct": 1,
               "throughput_vph": 0, "mean_green_s": 1}
    out = {}
    for c in CONTROLLERS:
        out[c] = {}
        for lv in LEVELS:
            runs = ordered(rows[(lv, c)])
            base = ordered(rows[(lv, "fixed")])
            entry = {}
            for m, d in metrics.items():
                vals = [f(r[m]) for r in runs]
                entry[m] = {"mean": round(statistics.mean(vals), 3), "ci": ci(vals, d),
                            "vs_fixed": change_text([f(r[m]) for r in base], vals)}
            out[c][lv] = entry
    adaptive = {lv: ordered(rows[(lv, "adaptive")]) for lv in LEVELS}
    for c in CONTROLLERS:  # every controller against the paper's adaptive controller
        for lv in LEVELS:
            out[c][lv]["mean_delay_s"]["vs_adaptive"] = change_text(
                [f(r["mean_delay_s"]) for r in adaptive[lv]], [f(r["mean_delay_s"]) for r in ordered(rows[(lv, c)])])
    runs = read(name)
    safety = {"runs": len(runs), "hours": len(runs) * 0.5,
              "violations": int(sum(f(r["safety_violations"]) for r in runs)),
              "preemptions": int(sum(f(r["preemptions"]) for r in runs)),
              "unfinished": int(sum(f(r["unfinished"]) for r in runs)),
              "measured": int(sum(f(r["measured_vehicles"]) for r in runs))}
    return out, safety


# --- Table III (preemption effect) ---------------------------------------

def table3():
    on = by(read("table2_preemption_on.csv"), "level", "controller")
    off = by(read("table2_preemption_off.csv"), "level", "controller")
    out = {}
    for c in ("fixed", "adaptive", "adaptive_hold"):
        out[c] = {}
        for lv in LEVELS:
            r_on, r_off = ordered(on[(lv, c)]), ordered(off[(lv, c)])
            ev_on = [f(x) for r in r_on for x in r["ev_delays_s"].split(";") if x]
            ev_off = [f(x) for r in r_off for x in r["ev_delays_s"].split(";") if x]
            other_on = [f(r["other_mean_delay_s"]) for r in r_on]
            other_off = [f(r["other_mean_delay_s"]) for r in r_off]
            mw_p = stats.mannwhitneyu(ev_off, ev_on, alternative="two-sided").pvalue if ev_on and ev_off else float("nan")
            out[c][lv] = {
                "ev_off": len(ev_off), "ev_on": len(ev_on),
                "ev_delay_off": round(statistics.mean(ev_off), 2) if ev_off else None,
                "ev_delay_on": round(statistics.mean(ev_on), 2) if ev_on else None,
                "ev_p": p_text(mw_p),
                "other_off": round(statistics.mean(other_off), 2), "other_on": round(statistics.mean(other_on), 2),
                "other_change": change_text(other_off, other_on),
                "preemptions_per_hour": round(sum(f(r["preemptions"]) for r in r_on) / (len(r_on) * 0.5), 1),
            }
    return out


# --- Table IV (ablation) ---------------------------------------------------

def ablation():
    rows = read("ablation.csv")
    groups = by(rows, "level", "variant")
    variants = list(dict.fromkeys(r["variant"] for r in rows))
    out = []
    for lv in ("medium", "high"):
        ref = [f(r["mean_delay_s"]) for r in ordered(groups[(lv, variants[0])])]
        for v in variants:
            vals = [f(r["mean_delay_s"]) for r in ordered(groups[(lv, v)])]
            greens = [f(r["mean_green_s"]) for r in ordered(groups[(lv, v)])]
            ch = change_text(ref, vals)
            out.append({"variant": v, "level": lv, "delay": ci(vals, 2), "green": f"{statistics.mean(greens):.1f}",
                        "change": "—" if v == variants[0] else ch["text"],
                        "p": "—" if v == variants[0] else ch["p"], "pct": ch["pct"]})
    return out


# --- Above capacity ------------------------------------------------------

def oversat(name):
    rows = read(name)
    cap_rows = by([r for r in rows if r["ratio"] == "capacity"], "controller")
    sweep_rows = by([r for r in rows if r["ratio"] != "capacity"], "ratio", "controller")
    ratios = sorted({r["ratio"] for r in rows if r["ratio"] != "capacity"}, key=float)
    capacity = {}
    for c in CONTROLLERS:
        if not cap_rows.get((c,)):
            continue
        thr = [f(r["throughput_vph"]) for r in ordered(cap_rows[(c,)])]
        capacity[c] = {"ci": ci(thr, 0), "mean": round(statistics.mean(thr)),
                       "green": f"{statistics.mean(f(r['mean_green_s']) for r in cap_rows[(c,)]):.1f}",
                       "vs_fixed": change_text([f(r["throughput_vph"]) for r in ordered(cap_rows[("fixed",)])], thr)}
    sweep = {}
    for ratio in ratios:
        sweep[ratio] = {}
        base = ordered(sweep_rows[(ratio, "fixed")])
        for c in CONTROLLERS:
            runs = ordered(sweep_rows[(ratio, c)])
            if not runs:
                continue
            entry = {}
            for m, d in (("delay_all_lb_s", 1), ("throughput_vph", 0), ("spillback_pct", 1),
                         ("queue_growth_vpm", 1), ("served_pct", 1), ("mean_green_s", 1), ("final_queue", 0)):
                vals = [f(r[m]) for r in runs]
                entry[m] = {"mean": round(statistics.mean(vals), 2), "ci": ci(vals, d),
                            "vs_fixed": change_text([f(r[m]) for r in base], vals)}
            sweep[ratio][c] = entry
    safety = {"runs": len(rows), "violations": int(sum(f(r["safety_violations"]) for r in rows))}
    return {"capacity": capacity, "sweep": sweep, "ratios": ratios, "safety": safety}


def audit_violations(md_name):
    """The ablation CSV keeps only delays; its audit total is in the report."""
    for line in (RESULTS / md_name).read_text(encoding="utf-8").splitlines():
        if line.startswith("Signal safety audit"):
            return int(line.rsplit(":", 1)[1].split()[0])
    raise ValueError(f"no audit line in {md_name}")


def main():
    t2_on, safety_on = table2("table2_preemption_on.csv")
    t2_off, safety_off = table2("table2_preemption_off.csv")
    t2_cal, safety_cal = table2("table2_calibrated.csv")
    abl = ablation()
    over_off = oversat("oversaturation_preemption_off.csv")
    over_on = oversat("oversaturation_preemption_on.csv")
    over_cal = oversat("oversaturation_calibrated.csv")
    abl_runs = read("ablation.csv")
    abl_violations = audit_violations("ablation.md")
    numbers = {
        "labels": CONTROLLER_LABELS,
        "table2_on": t2_on, "table2_off": t2_off, "table2_cal": t2_cal,
        "table3": table3(),
        "ablation": abl,
        "over_off": over_off, "over_on": over_on, "over_cal": over_cal,
        "vision": json.loads((RESULTS / "vision_eval.json").read_text(encoding="utf-8")),
        "kinematics": {
            "tau0": json.loads((RESULTS / "kinematics_tau0.json").read_text(encoding="utf-8")),
            "tau16": json.loads((RESULTS / "kinematics_tau1.6.json").read_text(encoding="utf-8")),
        },
        "safety": {
            "table2_on": safety_on, "table2_off": safety_off, "table2_cal": safety_cal,
            "ablation_runs": len(abl_runs), "ablation_violations": abl_violations,
            "over_off": over_off["safety"], "over_on": over_on["safety"], "over_cal": over_cal["safety"],
        },
    }
    total_runs = (safety_on["runs"] + safety_off["runs"] + safety_cal["runs"] + len(abl_runs)
                  + over_off["safety"]["runs"] + over_on["safety"]["runs"] + over_cal["safety"]["runs"])
    total_violations = (safety_on["violations"] + safety_off["violations"] + safety_cal["violations"] + abl_violations
                        + over_off["safety"]["violations"] + over_on["safety"]["violations"]
                        + over_cal["safety"]["violations"])
    numbers["safety"]["total_runs"] = total_runs
    numbers["safety"]["total_hours"] = total_runs * 0.5
    numbers["safety"]["total_violations"] = total_violations
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(numbers, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote", OUT, "-", total_runs, "runs,", total_violations, "violations")


if __name__ == "__main__":
    main()
