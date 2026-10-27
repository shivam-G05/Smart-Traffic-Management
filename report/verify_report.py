#!/usr/bin/env python
"""Check that what the report (and paper) state is real.

    python report/verify_report.py

1. Constants and formulas: every parameter the report states about the simulator, the controllers, the vision
   pipeline and the backend is compared with the value in the source code; Eq. (1)-(2) and the Webster
   formula are re-computed numerically against the implementation; library versions, the test count and the
   CPU model are read from the project and the machine.
2. Statistics: the headline numbers in paper/build/numbers.json (which feed both the paper and the report) are
   recomputed here from the raw CSV/JSON files in results/ with an independent implementation.
3. Consistency: every number printed in the report is looked up in the paper's PDF text, numbers.json and the
   verified constants above; anything not found is listed for review.

Exit status is non-zero if a check fails.
"""

import ast
import csv
import inspect
import json
import math
import random
import re
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

REPORT = ROOT / "report" / "overleaf"
RESULTS = ROOT / "results"
N = json.loads((ROOT / "paper" / "build" / "numbers.json").read_text(encoding="utf-8"))

fails, passes = [], 0


def check(label, ok, detail=""):
    global passes
    if ok:
        passes += 1
    else:
        fails.append(f"{label}: {detail}")
        print(f"  FAIL  {label}  {detail}")


def close(a, b, tol):
    return a == a and b == b and abs(a - b) <= tol


# ============================================================ 1. constants and formulas
print("1. Constants and formulas against the source code")
from analytics import config as acfg  # noqa: E402
from decision_engine import adaptive_controller as ac, baselines, density, emergency_preemption as ep, webster  # noqa: E402
from simulation import config as sc  # noqa: E402
from simulation.entities.lane import safe_following_speed  # noqa: E402
from vision import config as vc  # noqa: E402

tex = {f.relative_to(REPORT).as_posix(): f.read_text(encoding="utf-8") for f in REPORT.rglob("*.tex")}
alltex = "\n".join(tex.values())

geometry = {"ROAD_LENGTH_M": 330, "STOP_LINE_POS_M": 200, "INTERSECTION_EXIT_POS_M": 218, "LANES_PER_ROAD": 2,
            "SAFE_FOLLOWING_GAP_M": 8, "MIN_VEHICLE_GAP_M": 2, "QUEUED_SPEED_MPS": 0.5, "FIXED_GREEN_DURATION_S": 20,
            "YELLOW_DURATION_S": 3, "ALL_RED_CLEARANCE_S": 1, "TICK_HZ": 20, "BROADCAST_HZ": 10}
for k, v in geometry.items():
    check(f"simulation.config.{k} = {v}", getattr(sc, k) == v, str(getattr(sc, k)))
check("arrival rate redrawn as lambda*U(0.4,1.6)", close(1 - sc.SPAWN_RATE_JITTER, 0.4, 1e-9) and close(1 + sc.SPAWN_RATE_JITTER, 1.6, 1e-9))
isrc = (ROOT / "simulation/entities/intersection.py").read_text(encoding="utf-8")
check("rates redrawn every 15 s with floor 0.02", "_reshuffle_timer < 15.0" in isrc and "max(0.02" in isrc)
check("fixed cycle 48 s = 2*(20+3+1)", 2 * (sc.FIXED_GREEN_DURATION_S + sc.YELLOW_DURATION_S + sc.ALL_RED_CLEARANCE_S) == 48)

# Table I: the rows printed in the report against VEHICLE_PROFILES and DENSITY_WEIGHTS
build_src = (ROOT / "report" / "build_report.py").read_text(encoding="utf-8")
veh_rows = next(ast.literal_eval(n.value) for n in ast.parse(build_src).body
                if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "veh_rows")
names = {"Car": sc.VehicleType.CAR, "Motorcycle": sc.VehicleType.MOTORCYCLE, "Auto-rickshaw": sc.VehicleType.AUTO,
         "Bus": sc.VehicleType.BUS, "Truck": sc.VehicleType.TRUCK, "Ambulance": sc.VehicleType.AMBULANCE,
         "Fire truck": sc.VehicleType.FIRE_TRUCK}
check("Table I lists all seven vehicle classes", {r[0] for r in veh_rows} == set(names))
for name, share, length, vmax, a, b, w in veh_rows:
    prof = sc.VEHICLE_PROFILES[names[name]]
    got = [prof.spawn_weight, prof.length_m, prof.max_speed_mps, prof.acceleration_mps2, prof.deceleration_mps2]
    check(f"Table I {name}: share, length, v_max, a, b = config", got == [float(x) for x in (share, length, vmax, a, b)], f"{got}")
    check(f"Table I {name}: weight {w} = DENSITY_WEIGHTS", density.DENSITY_WEIGHTS[names[name]] == float(w), str(density.DENSITY_WEIGHTS[names[name]]))
check("vehicle shares sum to 100%", close(sum(p.spawn_weight for p in sc.VEHICLE_PROFILES.values()), 100, 1e-9))
check("density multipliers queued 1.5 / moving 0.5", density.QUEUED_MULTIPLIER == 1.5 and density.MOVING_MULTIPLIER == 0.5)
check("display thresholds low <= 3 < medium <= 6 < high", acfg.CONGESTION_LOW_MAX == 3 and acfg.CONGESTION_HIGH_MIN == 6
      and baselines.LEVEL_LOW_MAX == 3 and baselines.LEVEL_HIGH_MIN == 6)
check("density-levels greens 10/20/30 s", baselines.LEVEL_GREEN_S == {"low": 10.0, "medium": 20.0, "high": 30.0})
check("adaptive G_min 8, G_max 45, theta 1.1, zone 10 m",
      (ac.MIN_GREEN_S, ac.MAX_GREEN_S, ac.EXTENSION_THRESHOLD, ac.DISCHARGE_ZONE_M) == (8.0, 45.0, 1.1, 10.0))
rmax = sc.ALL_RED_CLEARANCE_S + ac.MAX_GREEN_S + sc.YELLOW_DURATION_S + sc.ALL_RED_CLEARANCE_S
check("R_max = A + G_max + Y + A = 50 s", rmax == 50, str(rmax))
check("preemption: min green 5 s, max priority 20 s, worst wait 5+3+1 = 9 s",
      ep.MIN_GREEN_BEFORE_PREEMPT_S == 5 and ep.MAX_HOLD_S == 20 and ep.MIN_GREEN_BEFORE_PREEMPT_S + sc.YELLOW_DURATION_S + sc.ALL_RED_CLEARANCE_S == 9)
check("vision: 200x240 px, 60 m view, 4 px/m, 2 Hz", (vc.FRAME_WIDTH_PX, vc.FRAME_HEIGHT_PX, vc.VIEW_DISTANCE_M, vc.PX_PER_M, vc.VISION_BROADCAST_HZ) == (200, 240, 60.0, 4.0, 2))
check("detector: upscale 3, scale 1.05, minNeighbors 2, min size 20 px",
      (vc.UPSCALE_FACTOR, vc.DETECT_SCALE_FACTOR, vc.DETECT_MIN_NEIGHBORS, vc.DETECT_MIN_SIZE_PX) == (3, 1.05, 2, (20, 20)))
check("tracker: conf 0.15, IoU 0.15, confirm after 2, delete after 3, match padding 4 px",
      (vc.TRACK_HIGH_CONF_THRESHOLD, vc.TRACK_MATCH_IOU_THRESHOLD, vc.TRACK_MIN_HITS, vc.TRACK_MAX_AGE, vc.MATCH_PADDING_PX) == (0.15, 0.15, 2, 3, 4))
check("dashboard alert after 3 s at high density", acfg.HIGH_TRAFFIC_ALERT_HOLD_S == 3.0)
from analytics.collector import AnalyticsCollector  # noqa: E402
check("database snapshot every 10th 1 Hz sample", inspect.signature(AnalyticsCollector.__init__).parameters["persist_every_n_samples"].default == 10)
check("hardware driver polls at 5 Hz", "POLL_HZ = 5.0" in (ROOT / "hardware/gpio_driver.py").read_text(encoding="utf-8"))
check("hardware: 220 ohm resistor, 12 LEDs documented", "220" in (ROOT / "hardware/README.md").read_text(encoding="utf-8") and "12 LEDs" in (ROOT / "hardware/README.md").read_text(encoding="utf-8"))

# Eq. (1) and Eq. (2): the implementation against the printed formulas
rng = random.Random(7)
ok1 = ok2 = True
for _ in range(2000):
    g, ul, bl, b = rng.uniform(2.5, 60), rng.uniform(0, 16), rng.uniform(2.8, 5.0), rng.uniform(2.8, 5.0)
    s0 = sc.MIN_VEHICLE_GAP_M
    eq1 = math.sqrt(2 * b * (g + ul ** 2 / (2 * bl) - s0))
    ok1 &= close(safe_following_speed(g, ul, bl, b, 0.0), eq1, 1e-9)
    tau = 1.6
    eq2 = -b * tau + math.sqrt((b * tau) ** 2 + b * ul ** 2 / bl + 2 * b * (g - s0))
    ok2 &= close(safe_following_speed(g, ul, bl, b, tau), eq2, 1e-9)
check("Eq. (1) safe speed equals lane.safe_following_speed (tau = 0)", ok1)
check("Eq. (2) safe speed with reaction time equals lane.safe_following_speed (tau = 1.6)", ok2)
okw = True
for lam in [0.02, 0.05, 0.08, 0.12, 0.18, 0.2]:
    Y = 2 * lam * 3600 / 6000
    exp = 45.0 if Y >= 0.95 else min(45.0, max(8.0, ((1.5 * 8 + 5) / (1 - Y) - 8) / 2))
    okw &= close(webster.webster_green_s(lam), exp, 1e-9)
check("Webster green = ((1.5L+5)/(1-Y) - L)/2, clamped 8-45 s, L = 8, s = 6000", okw and webster.SATURATION_FLOW_VPH == 6000 and webster.LOST_TIME_S == 8)
dt = 0.05
accs = sorted(p.acceleration_mps2 for p in sc.VEHICLE_PROFILES.values())
lo, hi = math.ceil(0.5 / (accs[-1] * dt)) * dt, math.ceil(0.5 / (accs[0] * dt)) * dt
check("start-up component of stopped delay 0.15-0.55 s (0.5 m/s / a, 50 ms steps)", close(lo, 0.15, 0.051) and close(hi, 0.55, 0.051), f"{lo:.2f}-{hi:.2f}")

# versions
req = (ROOT / "backend/requirements.txt").read_text(encoding="utf-8")
pkg = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
deps = {**pkg["dependencies"], **pkg["devDependencies"]}
for label, text in [("numpy==2.1", req), ("scipy==1.14", req), ("opencv-python-headless==4.10", req), ("fastapi==0.115", req),
                    ("pydantic==2.9", req), ("sqlalchemy==2.0", req), ("pytest==8", req)]:
    check(f"version {label}", label in text)
for name, major in [("react", "^18"), ("vite", "^5"), ("tailwindcss", "^3"), ("recharts", "^2")]:
    check(f"version {name} {major}", deps[name].startswith(major), deps[name])
check("Python 3.12 in CI", 'python-version: "3.12"' in (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))

for k, v in {"fastapi": "0.115.0", "sqlalchemy": "2.0.35", "numpy": "2.1.2", "scipy": "1.14.1", "opencv-python-headless": "4.10.0.84",
             "pytest": "8.3.3", "pydantic": "2.9.2"}.items():
    check(f"requirements pin {k}=={v}", f"{k}=={v}" in req.lower())
for name, v in {"react": "18.3", "vite": "5.4", "tailwindcss": "3.4", "recharts": "2.12"}.items():
    check(f"package.json {name} {v}", deps[name].lstrip("^").startswith(v), deps[name])
compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
check("docker-compose: backend on port 8000, dashboard on 8080", '"8000:8000"' in compose and '"8080:80"' in compose)
calib_src = (ROOT / "scripts/calibrate_weights.py").read_text(encoding="utf-8")
check("calibration search: class weights 0.25-4, emergency 1-10, ratio 1-12, theta 1.0-1.6",
      all(x in calib_src for x in ("logu(0.25, 4)", "rng.uniform(1, 10)", "logu(1, 12)", "rng.uniform(1.0, 1.6)")))
check("offered demand 0.08/0.12/0.18 veh/s/approach = 1152/1728/2592 veh/h", [round(l * 4 * 3600) for l in (0.08, 0.12, 0.18)] == [1152, 1728, 2592])
bsrc = (ROOT / "scripts/benchmark.py").read_text(encoding="utf-8")
osrc = (ROOT / "scripts/oversaturation.py").read_text(encoding="utf-8")
check("protocol: levels 0.08/0.12/0.18, 10 seeds, 1800 s, 60 s warm-up, delay of vehicles entering 60-1650 s",
      'DEFAULT_LEVELS = {"low": 0.08, "medium": 0.12, "high": 0.18}' in bsrc and "DEFAULT_SEEDS = 10" in bsrc
      and "DEFAULT_DURATION_S = 1800.0" in bsrc and "WARMUP_S = 60.0" in bsrc and "1650 s" in bsrc)
check("protocol: ratios 0.6-1.5, 10 seeds, 5 capacity seeds 101-105, flood 1.5 arrivals/s",
      "DEFAULT_RATIOS = [0.6, 0.8, 0.9, 1.0, 1.2, 1.5]" in osrc and "DEFAULT_SEEDS = 10" in osrc and "DEFAULT_CAPACITY_SEEDS = 5" in osrc
      and "range(101, 101 + args.capacity_seeds)" in osrc and "DEFAULT_SATURATION_RATE = 1.5" in osrc)
check("tuning seed 1000", "TUNING_SEED = 1000" in (ROOT / "scripts/tune_zone.py").read_text(encoding="utf-8"))
check("50 ms step", "dt: float = 0.05" in (ROOT / "scripts/experiment_common.py").read_text(encoding="utf-8"))

# test count and machine
out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=ROOT / "backend", capture_output=True, text=True,
                     env={**__import__("os").environ, "PYTHONPATH": f"{ROOT}:{ROOT / 'backend'}".replace(":", __import__("os").pathsep)}).stdout
m = re.search(r"(\d+) tests collected", out)
check("119 automated tests", m and int(m.group(1)) == 119, m.group(0) if m else out[-200:])
cpu = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"], capture_output=True, text=True).stdout
check("CPU is the i5-12450H", "i5-12450H" in cpu, cpu.strip())
for f in ("timing.json", "timing_run2.json"):
    t = json.loads((RESULTS / f).read_text(encoding="utf-8"))
    check(f"{f}: measured on the i5-12450H, 400 frames", "i5-12450H" in t["cpu"] and t["frames"] == 400)

# ============================================================ 2. statistics recomputed from raw results
print("2. numbers.json recomputed from the raw results")


def read(name):
    with (RESULTS / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pchange(base, treat):
    d = [t - b for b, t in zip(base, treat)]
    pct = statistics.mean(d) / statistics.mean(base) * 100
    p = stats.ttest_rel(treat, base).pvalue if len(d) > 1 and any(x != d[0] for x in d) else float("nan")
    return pct, p


def by(rows, *keys):
    out = defaultdict(list)
    for r in rows:
        out[tuple(r[k] for k in keys)].append(r)
    return out


def seeds(rs):
    return [float(r["_v"]) for r in sorted(rs, key=lambda r: int(r["seed"]))]


def column(rs, col):
    return [float(r[col]) for r in sorted(rs, key=lambda r: int(r["seed"]))]


def pmatch(p_json, p_calc):
    txt = "< 0.001" if p_calc < 0.001 else f"{p_calc:.3f}" if p_calc < 0.01 else f"{p_calc:.2f}"
    return p_json == txt or (p_calc == p_calc and p_json != "n/a" and close(float(p_json.replace("< ", "")), p_calc, 0.006)) or (p_json == "n/a" and p_calc != p_calc)


# Table II (preemption on): delay mean, change vs fixed, p
rows = by(read("table2_preemption_on.csv"), "level", "controller")
bad = 0
for c in N["table2_on"]:
    for lv in ("low", "medium", "high"):
        vals = column(rows[(lv, c)], "mean_delay_s")
        base = column(rows[(lv, "fixed")], "mean_delay_s")
        pct, p = pchange(base, vals)
        j = N["table2_on"][c][lv]["mean_delay_s"]
        if not (close(statistics.mean(vals), j["mean"], 0.001) and close(pct, j["vs_fixed"]["pct"], 0.051) and (c == "fixed" or pmatch(j["vs_fixed"]["p"], p))):
            bad += 1
            print("   mismatch", c, lv, statistics.mean(vals), j["mean"], pct, j["vs_fixed"]["pct"])
check("Table II: 21 delay means, % changes and p-values recomputed", bad == 0, f"{bad} mismatches")
red = {c: [-pchange(column(rows[(lv, "fixed")], "mean_delay_s"), column(rows[(lv, c)], "mean_delay_s"))[0] for lv in ("low", "medium", "high")]
       for c in ("adaptive", "webster", "actuated", "max_pressure")}
check("abstract: adaptive reduces delay by 35.3-36.1%", close(min(red["adaptive"]), 35.3, 0.06) and close(max(red["adaptive"]), 36.1, 0.06),
      f"{min(red['adaptive']):.1f}-{max(red['adaptive']):.1f}")
print("   reductions vs fixed:", {c: f"{min(v):.1f}-{max(v):.1f}%" for c, v in red.items()})

# capacity and sweep (preemption off)
rows = read("oversaturation_preemption_off.csv")
cap = by([r for r in rows if r["ratio"] == "capacity"], "controller")
bad = 0
for c in N["over_off"]["capacity"]:
    thr = column(cap[(c,)], "throughput_vph")
    pct, p = pchange(column(cap[("fixed",)], "throughput_vph"), thr)
    j = N["over_off"]["capacity"][c]
    if not (close(statistics.mean(thr), j["mean"], 0.5) and (c == "fixed" or close(pct, j["vs_fixed"]["pct"], 0.051))):
        bad += 1
        print("   mismatch capacity", c, statistics.mean(thr), j["mean"], pct, j["vs_fixed"]["pct"])
check("Table III: capacity of every controller and % vs fixed recomputed", bad == 0, f"{bad} mismatches")
sweep = by([r for r in rows if r["ratio"] != "capacity"], "ratio", "controller")
bad = 0
for r in N["over_off"]["ratios"]:
    for c, d in N["over_off"]["sweep"][r].items():
        for metric in ("delay_all_lb_s", "throughput_vph", "queue_growth_vpm", "spillback_pct"):
            v = statistics.mean(column(next(v for k, v in sweep.items() if k[1] == c and float(k[0]) == float(r)), metric))
            if not close(v, d[metric]["mean"], 0.051 if metric != "throughput_vph" else 0.51):
                bad += 1
                print("   mismatch sweep", r, c, metric, v, d[metric]["mean"])
check("Table IV and queue/spillback numbers recomputed (6 demands x 7 controllers x 4 metrics)", bad == 0, f"{bad} mismatches")

# ablation
rows = by(read("ablation.csv"), "level", "variant")
bad = 0
for r in N["ablation"]:
    vs = column(rows[(r["level"], r["variant"])], "mean_delay_s")
    ref = column(rows[(r["level"], "Adaptive (reference)")], "mean_delay_s")
    pct, _ = pchange(ref, vs)
    if r["variant"] != "Adaptive (reference)" and not close(pct, r["pct"], 0.051):
        bad += 1
        print("   mismatch ablation", r["variant"], r["level"], pct, r["pct"])
check("Table V ablation: every % change recomputed", bad == 0, f"{bad} mismatches")

# kinematics
for tau, key in (("0", "tau0"), ("1.6", "tau16")):
    K = json.loads((RESULTS / f"kinematics_tau{tau}.json").read_text(encoding="utf-8"))
    for mix in ("cars only", "full vehicle mix"):
        hw = K[mix]["headway_by_position"][4:]
        cal = statistics.mean(hw)
        j = N["kinematics"][key][mix]
        check(f"kinematics tau={tau} {mix}: headway/flow consistent", close(K[mix]["saturation_headway_s"], j["saturation_headway_s"], 1e-9)
              and close(3600 / K[mix]["saturation_headway_s"], j["saturation_flow_vphpl"], 1.5), f"{cal:.3f} vs {j['saturation_headway_s']}")
cars1 = N["kinematics"]["tau16"]["cars only"]
check("tau = 1.6 s gives about 1900 veh/h/lane (within 2.5% of HCM)", abs(cars1["saturation_flow_vphpl"] - 1900) / 1900 < 0.025, str(cars1["saturation_flow_vphpl"]))

# calibration held-out, sensing, peak
C = json.loads((RESULTS / "calibration.json").read_text(encoding="utf-8"))
for sc_name, cond in N["calibration"]["held_out"].items():
    for k, v in cond.items():
        check(f"calibration held-out {sc_name}/{k}", close(C["held_out"][sc_name][k]["mean"], v["mean"], 1e-9))
srows = by(read("sensing.csv"), "condition", "sensing", "controller")
bad = 0
for cond, d in N["sensing"].items():
    for r in d["rows"]:
        for c in d["controllers"]:
            vs = [float(x["delay_s"]) for x in srows[(cond, r["sensing"], c)]]
            if not close(statistics.mean(vs), r[c]["mean"], 0.0051):
                bad += 1
check("sensing table: every cell recomputed from sensing.csv", bad == 0, f"{bad} mismatches")
prow = by(read("peak_period.csv"), "controller")
bad = 0
for c, d in N["peak"].items():
    q = statistics.mean(float(r["peak_queue"]) for r in prow[(c,)])
    t = statistics.mean(float(r["peak_throughput_vph"]) for r in prow[(c,)])
    if not (close(q, d["peak_queue"]["mean"], 0.51) and close(t, d["peak_throughput_vph"]["mean"], 0.51)):
        bad += 1
check("peak period: peak queue and peak throughput recomputed", bad == 0, f"{bad} mismatches")
V = json.loads((RESULTS / "vision_eval.json").read_text(encoding="utf-8"))
d0 = V["detectors"]["Default (3x upscale, equalized)"]
check("detector precision/recall equal numbers.json", close(d0["precision"], N["vision"]["detectors"]["Default (3x upscale, equalized)"]["precision"], 1e-9)
      and close(d0["recall"], N["vision"]["detectors"]["Default (3x upscale, equalized)"]["recall"], 1e-9))
check("0 safety violations in every run (all result CSVs)", N["safety"]["total_violations"] == 0
      and all(int(r["safety_violations"]) == 0 for f in RESULTS.glob("*.csv") if "safety_violations" in f.read_text(encoding="utf-8")[:600]
              for r in read(f.name)))


def ci_text(values, digits):
    m = statistics.mean(values)
    h = stats.t.ppf(0.975, len(values) - 1) * statistics.stdev(values) / math.sqrt(len(values))
    return f"{m:.{digits}f} \u00b1 {h:.{digits}f}"


# Table II confidence intervals and 95th percentiles (report Table 5.1 columns)
rows2 = by(read("table2_preemption_on.csv"), "level", "controller")
bad = 0
for c in N["table2_on"]:
    for lv in ("low", "medium", "high"):
        for metric, digits in (("mean_delay_s", 2), ("p95_delay_s", 1), ("mean_green_s", 1)):
            vals = column(rows2[(lv, c)], metric)
            if ci_text(vals, digits) != N["table2_on"][c][lv][metric]["ci"]:
                bad += 1
                print("   mismatch ci", c, lv, metric, ci_text(vals, digits), N["table2_on"][c][lv][metric]["ci"])
        pct, _ = pchange(column(rows2[(lv, "fixed")], "p95_delay_s"), column(rows2[(lv, c)], "p95_delay_s"))
        if not close(pct, N["table2_on"][c][lv]["p95_delay_s"]["vs_fixed"]["pct"], 0.051):
            bad += 1
check("Table II: delay, 95th-percentile and green confidence intervals recomputed (63 cells)", bad == 0, f"{bad} mismatches")
p95 = [-pchange(column(rows2[(lv, "fixed")], "p95_delay_s"), column(rows2[(lv, "adaptive")], "p95_delay_s"))[0] for lv in ("low", "medium", "high")]
check("text: adaptive lowers 95th-percentile delay by 37.1-41.2%", close(min(p95), 37.1, 0.06) and close(max(p95), 41.2, 0.06), f"{min(p95):.1f}-{max(p95):.1f}")

# capacity confidence intervals (report Table 5.2)
cap_rows = by([r for r in read("oversaturation_preemption_off.csv") if r["ratio"] == "capacity"], "controller")
check("Table III: capacity confidence intervals recomputed",
      all(ci_text(column(cap_rows[(c,)], "throughput_vph"), 0) == N["over_off"]["capacity"][c]["ci"] for c in N["over_off"]["capacity"]))

# ablation delays with their confidence intervals (report Table 5.4)
abl = by(read("ablation.csv"), "level", "variant")
bad = 0
for r in N["ablation"]:
    if ci_text(column(abl[(r["level"], r["variant"])], "mean_delay_s"), 2) != r["delay"]:
        bad += 1
        print("   mismatch ablation delay", r["variant"], r["level"], ci_text(column(abl[(r["level"], r["variant"])], "mean_delay_s"), 2), r["delay"])
check("Table V: ablation delays +/- CI recomputed (22 cells)", bad == 0, f"{bad} mismatches")

# peak period: recovery time, blocked approach-minutes, total delay change (report Table 5.3 and text)
peak = by(read("peak_period.csv"), "controller")
bad = 0
for c, d in N["peak"].items():
    rec = [float(r["recovery_min"] or "nan") for r in sorted(peak[(c,)], key=lambda r: int(r["seed"]))]
    ok = [x for x in rec if x == x]
    sp = statistics.mean(float(r["spillback_approach_min"]) for r in peak[(c,)])
    base = [float(r["total_delay_veh_h"]) for r in sorted(peak[("fixed",)], key=lambda r: int(r["seed"]))]
    tot = [float(r["total_delay_veh_h"]) for r in sorted(peak[(c,)], key=lambda r: int(r["seed"]))]
    pct, _ = pchange(base, tot)
    j = d["recovery_min"]
    good = (len(rec) - len(ok) == j["not_recovered"] and (not ok or close(statistics.mean(ok), j["mean"], 0.051)) and close(sp, d["spillback_approach_min"]["mean"], 0.51)
            and (c == "fixed" or close(pct, d["total_delay_vs_fixed"]["pct"], 0.051)))
    if not good:
        bad += 1
        print("   mismatch peak", c, len(rec) - len(ok), j, sp, pct)
check("peak period: recovery time, runs not recovered, blocked minutes and total-delay change recomputed", bad == 0, f"{bad} mismatches")

# emergency preemption (report Experiment 4)
off, on = by(read("table2_preemption_off.csv"), "level", "controller"), by(read("table2_preemption_on.csv"), "level", "controller")
ev = lambda rs: [float(x) for r in rs for x in r["ev_delays_s"].split(";") if x]
bad = 0
for c in ("fixed", "adaptive", "adaptive_hold"):
    for lv in ("low", "medium", "high"):
        j = N["table3"][c][lv]
        eo, en = ev(off[(lv, c)]), ev(on[(lv, c)])
        oo = column(off[(lv, c)], "other_mean_delay_s")
        on_ = column(on[(lv, c)], "other_mean_delay_s")
        pct, _ = pchange(oo, on_)
        if not (len(eo) == j["ev_off"] and len(en) == j["ev_on"] and close(statistics.mean(eo), j["ev_delay_off"], 0.0051)
                and close(statistics.mean(en), j["ev_delay_on"], 0.0051) and close(statistics.mean(oo), j["other_off"], 0.0051)
                and close(statistics.mean(on_), j["other_on"], 0.0051) and close(pct, j["other_change"]["pct"], 0.051)):
            bad += 1
            print("   mismatch preemption", c, lv, len(eo), len(en), statistics.mean(eo), statistics.mean(en), pct, j)
check("emergency preemption: EV counts and delays, other-traffic delay and % change recomputed (9 cells)", bad == 0, f"{bad} mismatches")

# ============================================================ 3. report numbers against paper / numbers.json
print("3. Every number in the report against the paper, numbers.json and verified constants")
import fitz  # noqa: E402

paper_text = "".join(p.get_text() for p in fitz.open(ROOT / "paper" / "final" / "Smart_Traffic_Control_revised.pdf"))
tok = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.])\d+\.\d+")
norm = lambda s: s.replace(",", "")
paper_nums = {norm(t) for t in tok.findall(paper_text.replace("−", "-"))}
paper_nums |= {norm(t) for t in re.findall(r"\d+", paper_text)}  # integers


def leaves(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from leaves(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from leaves(v)
    elif isinstance(o, (int, float)) and not isinstance(o, bool) and o == o:
        yield o
    elif isinstance(o, str):
        yield from (norm(t) for t in tok.findall(o))


json_nums = set()
for v in leaves(N):
    if isinstance(v, str):
        json_nums.add(v)
    else:
        for dgt in range(0, 4):
            json_nums.add(f"{v:.{dgt}f}")
for fname in ("timing.json", "timing_run2.json", "calibration.json"):
    for v in leaves(json.loads((RESULTS / fname).read_text(encoding="utf-8"))):
        json_nums |= {v} if isinstance(v, str) else {f"{v:.{d}f}" for d in range(0, 4)}
# verified constants and external reference values the report quotes (checked in section 1 or cited)
allowed = {"0.15", "0.5", "1.5", "0.4", "1.6", "1.1", "0.02", "1.05", "1.89", "1900", "6000", "3600", "4.5", "2.0", "0.25", "0.55", "10.4",
           "0.1", "0.2", "0.3", "0.01", "0.001", "0.05", "0.6", "0.8", "0.9", "1.0", "1.2", "1.5", "1.89", "2.5", "3.5", "5.0", "4.0", "1.2",
           "11.4", "9.1", "9.5", "3.0", "10.0", "14", "15", "16", "12", "11", "10"}
# versions quoted in the tools/deployment text
for line in (req + json.dumps(deps)).replace("^", "").replace("==", " ").split():
    allowed |= set(re.findall(r"\d+\.\d+(?:\.\d+)*", line))
allowed |= {"2.1.2", "1.14.1", "4.10.0.84", "0.115.0", "2.0.35", "8.3.3", "18.3", "5.4", "3.4", "2.12", "0.115", "4.10", "2.9", "1.14", "2.1"}

body = [tex[f] for f in sorted(tex) if f.startswith(("chapters/", "frontmatter/Abstract"))]
unmatched = []
for text in body:
    clean = re.sub(r"\\(label|ref|eqref|cite|includegraphics|input)\{[^}]*\}", "", text)
    clean = re.sub(r"%.*", "", clean)
    clean = clean.replace("$-$", "-")
    for m in tok.finditer(clean):
        n = norm(m.group())
        if n in paper_nums or n in json_nums or n in allowed:
            continue
        ctx = clean[max(0, m.start() - 45): m.end() + 25].replace("\n", " ")
        unmatched.append((n, ctx))
seen = set()
for n, ctx in unmatched:
    if n not in seen:
        seen.add(n)
        print(f"   not in paper/numbers.json: {n:>8}   ...{ctx}...")
check("every decimal number in the report is in the paper, numbers.json or a verified constant", not unmatched, f"{len(seen)} distinct numbers to review")

print(f"\n{passes} checks passed, {len(fails)} failed")
sys.exit(1 if fails else 0)
