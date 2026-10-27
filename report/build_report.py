#!/usr/bin/env python
"""Generate the B.Tech project report (AKGEC / AKTU Overleaf template layout).

Every number comes from paper/build/numbers.json (the same file the paper is
built from) and the appendix code is read from the repository, so the report,
the paper and the code cannot drift apart.

    python report/build_report.py        # writes report/overleaf/ and report/overleaf.zip
"""

import ast
import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "report" / "overleaf"
N = json.loads((ROOT / "paper" / "build" / "numbers.json").read_text(encoding="utf-8"))
L = N["labels"]
T2, O, Oon, S = N["table2_on"], N["over_off"], N["over_on"], N["safety"]
PK, TC, OC, ZC, SN, CB, V = N["peak"], N["table2_cal"], N["over_cal"], N["zone_cal"], N["sensing"], N["calibration"], N["vision"]
T3, K0, K1 = N["table3"], N["kinematics"]["tau0"], N["kinematics"]["tau16"]
CTRL = ["fixed", "webster", "actuated", "max_pressure", "density_levels", "adaptive", "adaptive_hold"]
SWEEP = ["fixed", "webster", "actuated", "max_pressure", "adaptive", "adaptive_hold"]
LV = ["low", "medium", "high"]
RATIOS = O["ratios"]

# --------------------------------------------------------------------------- tex helpers


class Raw(str):
    """Already-valid LaTeX; not escaped again."""


def tx(s):
    if isinstance(s, Raw):
        return s
    s = str(s)
    for a, b in [("\\", r"\textbackslash{}"), ("%", r"\%"), ("&", r"\&"), ("_", r"\_"), ("#", r"\#"),
                 ("±", r"$\pm$"), ("−", "$-$"), ("×", r"$\times$"), ("θ", r"$\theta$"), ("λ", r"$\lambda$"),
                 ("τ", r"$\tau$"), ("→", r"$\rightarrow$"), ("—", "---"), ("–", "--"), ("≥", r"$\ge$"), ("≈", r"$\approx$"), ("<", "$<$")]:
        s = s.replace(a, b)
    return Raw(s)


def minus(x):
    return Raw(str(x).replace("%", "\\%").replace("<", "$<$").replace("-", "$-$").replace("−", "$-$"))


def pct(x):
    return Raw(f"{x:+.1f}".replace("-", "$-$") + r"\%")


def abspct(x):
    return Raw(f"{abs(x):.1f}" + r"\%")


def rng(vals):
    a, b = min(vals), max(vals)
    return Raw(f"{a:.1f}\\%" if f"{a:.1f}" == f"{b:.1f}" else f"{a:.1f}--{b:.1f}\\%")


def between(vals):
    return Raw(f"between {pct(min(vals))} and {pct(max(vals))}")


def redu(c, T=T2):
    return rng([-T[c][lv]["mean_delay_s"]["vs_fixed"]["pct"] for lv in LV])


def cell(c):
    return c if isinstance(c, Raw) else tx(c)


def table(caption, label, header, rows, colspec, note=None):
    out = [r"\begin{table}[H]", r"\centering", r"\caption{%s}" % caption, r"\label{%s}" % label, r"\small",
           r"\resizebox{\ifdim\width>\textwidth\textwidth\else\width\fi}{!}{%",
           r"\begin{tabular}{%s}" % colspec, r"\toprule",
           " & ".join(r"\textbf{%s}" % cell(h) for h in header) + r" \\", r"\midrule"]
    out += [" & ".join(cell(c) for c in r) + r" \\" for r in rows]
    out += [r"\bottomrule", r"\end{tabular}}"]
    if note:
        out += [r"\par\smallskip{\footnotesize %s}" % note]
    out += [r"\end{table}", ""]
    return Raw("\n".join(out))


def figure(file, width, caption, label):
    return Raw("\n".join([r"\begin{figure}[H]", r"\centering",
                          r"\includegraphics[width=%s\textwidth]{figures/%s}" % (width, file),
                          r"\caption{%s}" % caption, r"\label{%s}" % label, r"\end{figure}", ""]))


def fill(text, vals):
    def sub(m):
        key = m.group(1)
        if key not in vals:
            raise KeyError(key)
        return str(vals[key])
    return re.sub(r"@(\w+)@", sub, text)


# --------------------------------------------------------------------------- derived values

d = lambda c, lv: T2[c][lv]["mean_delay_s"]
sw = lambda r, c, m: O["sweep"][r][c][m]
R = lambda x: next(r for r in RATIOS if abs(float(r) - x) < 1e-9)
cap_r, hi_r, r15, r06 = R(1.0), R(1.2), R(1.5), R(0.6)
det0 = list(V["detectors"].values())[0]
trk0 = list(V["tracking"].values())[0]
f1 = lambda x: "n/a" if x is None or x != x else f"{x:.1f}"
fm = lambda x: f"{x:,}"

abl = lambda v, lv: next(r for r in N["ablation"] if r["variant"].startswith(v) and r["level"] == lv)
cal_h = CB["held_out"]
cb_conds = list(cal_h["Hand-set (paper)"])
sn_conds = list(SN)
snMed, snCap = SN[sn_conds[0]], SN[sn_conds[1]]
snCtrl = snMed["controllers"]
snNames = [r["sensing"] for r in snMed["rows"]]
haar = next((n for n in snNames if n.startswith("Measured Haar")), None)
snRow = lambda cond, name: next(r for r in cond["rows"] if r["sensing"].startswith(name))


def pk_rec(c):
    r = PK[c]["recovery_min"]
    if r["not_recovered"] == r["runs"]:
        return "did not recover within the hour"
    s = f"{r['mean']:.1f} min"
    return s + (f" ({r['not_recovered']} of {r['runs']} runs did not recover)" if r["not_recovered"] else "")


def sense_text():
    hold = "adaptive_hold"
    ex, cam, r50 = snRow(snCap, "Exact states")[hold]["mean"], snRow(snCap, "Camera")[hold]["mean"], snRow(snCap, "recall 50%")[hold]["mean"]
    ph = snRow(snMed, "2 phantoms")[hold]
    s = (f"Below capacity the controllers tolerated missed detections well, because missing vehicles only shortens greens, "
         f"which costs little when queues are short. Near capacity, sensing mattered: the discharge-hold controller's delay rose "
         f"from {ex:.1f} s with exact states to {cam:.1f} s with a perfect camera view and {r50:.1f} s at 50\\% recall, against "
         f"{snCap['fixed_mean']:.1f} s for the fixed plan. Phantom detections were the most damaging error for the gap-out rule: "
         f"a phantom inside the 10 m zone never moves, so the green never gaps out and runs to the maximum (medium-demand delay "
         f"{ph['mean']:.1f} s, {minus(ph['vs_fixed']['text'])} relative to fixed timing). ")
    if haar:
        worse = lambda cond: [c for c in snCtrl if snRow(cond, "Measured Haar")[c]["mean"] > cond["fixed_mean"]]
        names = lambda lst: (", ".join(L[c].lower() for c in lst[:-1]) + " and " + L[lst[-1]].lower()) if len(lst) > 1 else L[lst[0]].lower()
        wc, wm = worse(snCap), worse(snMed)
        s += ("With the measured pipeline, " +
              ("every vehicle-reading controller was worse than the fixed plan near capacity" if len(wc) == len(snCtrl)
               else f"{names(wc)} {'was' if len(wc) == 1 else 'were'} worse than the fixed plan near capacity") +
              f" (discharge hold {snRow(snCap, 'Measured Haar')[hold]['mean']:.1f} s against {snCap['fixed_mean']:.1f} s). ")
        better = [c for c in snCtrl if c not in wm]
        if wm and better:
            s += (f"At medium demand {names(better)} still beat the fixed plan, because phantoms appear on both directions and "
                  f"largely cancel in their comparisons, whereas {names(wm)} {'was' if len(wm) == 1 else 'were'} held at long greens "
                  f"by phantoms in the stop-line zone ({snRow(snMed, 'Measured Haar')[hold]['mean']:.1f} s against "
                  f"{snMed['fixed_mean']:.1f} s). ")
    return s


def calib_text():
    cal, plain = cal_h["Calibrated"], cal_h["Plain count"]
    p = lambda x: "$<$ 0.001" if x < 0.001 else f"{x:.3f}"
    return ("On the held-out seeds the calibrated score changed delay by " +
            ", ".join(f"{pct(cal[c]['change_pct'])} ({tx(c)}, $p$ = {p(cal[c]['p'])})" for c in cb_conds) +
            " relative to the hand-set weights, whereas a plain vehicle count was worse by " +
            ", ".join(f"{pct(plain[c]['change_pct'])}" for c in cb_conds) + " respectively. ")


# --------------------------------------------------------------------------- tables

t2_rows = [[L[c], *[d(c, lv)["ci"] for lv in LV], "---" if c == "fixed" else minus(T2[c]["high"]["mean_delay_s"]["vs_fixed"]["text"]),
            T2[c]["high"]["p95_delay_s"]["ci"], T2[c]["high"]["mean_green_s"]["ci"].split(" ")[0]] for c in CTRL]
TBL_t2 = table("Mean stopped delay of the seven controllers below capacity (preemption enabled)", "tab:below",
               ["Controller", "Delay low (s)", "Delay medium (s)", "Delay high (s)", "High vs fixed", "95th pct. high (s)", "Green (s)"],
               t2_rows, "lcccccc",
               "Mean $\\pm$ 95\\% confidence interval over ten paired seeds. All changes relative to the fixed plan are significant "
               f"($p<0.001$) except density levels at low demand ($p$ = {T2['density_levels']['low']['mean_delay_s']['vs_fixed']['p']}). "
               "Green: mean green time at high demand.")

cap_rows = [[L[c], O["capacity"][c]["ci"], "---" if c == "fixed" else minus(O["capacity"][c]["vs_fixed"]["text"]), O["capacity"][c]["green"],
             Oon["capacity"][c]["ci"] if c in Oon["capacity"] else "---"] for c in CTRL if c in O["capacity"]]
TBL_cap = table("Capacity of each controller (veh/h)", "tab:capacity",
                ["Controller", "Capacity, preemption off", "vs fixed", "Mean green (s)", "Capacity, preemption on"],
                cap_rows, "lcccc", "Every approach flooded at 1.5 arrivals/s; five seeds; throughput after the 60 s warm-up.")

TBL_sweep = table("Delay including vehicles still waiting to enter (s), preemption off", "tab:sweep",
                  ["Controller", *[Raw(f"{float(r)}$\\times$") for r in RATIOS]],
                  [[L[c], *[f"{sw(r, c, 'delay_all_lb_s')['mean']:.1f}" for r in RATIOS]] for c in SWEEP],
                  "l" + "c" * len(RATIOS),
                  "Demand as a multiple of the fixed-time capacity; mean over ten paired seeds. Vehicles still waiting at the end "
                  "of a run count with the delay accrued so far, so values above capacity are lower bounds.")
TBL_thru = table("Throughput (veh/h), preemption off", "tab:throughput",
                 ["Controller", *[Raw(f"{float(r)}$\\times$") for r in RATIOS]],
                 [[L[c], *[f"{sw(r, c, 'throughput_vph')['mean']:.0f}" for r in RATIOS]] for c in SWEEP],
                 "l" + "c" * len(RATIOS), "Vehicles served per hour after the warm-up; ten paired seeds.")
queue_rows = []
for r in (cap_r, hi_r):
    for c in SWEEP:
        queue_rows.append([f"{float(r)}$\\times$", L[c], f"{sw(r, c, 'queue_growth_vpm')['mean']:.1f}",
                           f"{sw(r, c, 'spillback_pct')['mean']:.0f}", f"{sw(r, c, 'served_pct')['mean']:.0f}",
                           f"{sw(r, c, 'final_queue')['mean']:.0f}"])
TBL_queue = table("Queue growth, spillback and served share at capacity and above", "tab:queue",
                  ["Demand", "Controller", "Queue growth (veh/min)", "Spillback (% of approach-time)", "Served (%)", "Final queue (veh)"],
                  [[Raw(x) if i == 0 else x for i, x in enumerate(row)] for row in queue_rows], "llcccc",
                  "Preemption off; mean of ten paired seeds. Spillback: queue reaches the start of the link.")

peak_rows = [[L[c], f"{PK[c]['peak_queue']['mean']:.0f}", pk_rec(c), f"{PK[c]['spillback_approach_min']['mean']:.0f}",
              f"{PK[c]['peak_throughput_vph']['mean']:.0f}", "---" if c == "fixed" else minus(PK[c]["total_delay_vs_fixed"]["text"])]
             for c in SWEEP if c in PK]
TBL_peak = table("Sixty-minute peak period: queue, recovery, spillback, throughput and total delay", "tab:peak",
                 ["Controller", "Peak queue (veh)", "Time to recover", "Blocked (approach-min)", "Peak throughput (veh/h)", "Total delay vs fixed"],
                 peak_rows, "lccccc", "Demand ramps from 0.6 to 1.2 times capacity, holds for 15 min and falls back; ten paired seeds; preemption off.")

t3_rows = []
for lv in LV:
    for c in ["fixed", "adaptive", "adaptive_hold"]:
        x = T3[c][lv]
        t3_rows.append([lv.capitalize(), L[c], f"{x['ev_off']}/{x['ev_on']}", f"{x['ev_delay_off']}→{x['ev_delay_on']}",
                        f"{x['other_off']}→{x['other_on']}", Raw(f"{minus(x['other_change']['text'])} ({x['other_change']['p']})".replace("<", "$<$"))])
TBL_pre = table("Effect of emergency preemption", "tab:preemption",
                ["Demand", "Controller", "EVs off/on", "EV delay (s) off→on", "Other delay (s) off→on", "Other change ($p$)"],
                t3_rows, "llccc c".replace(" ", ""), "EV: emergency vehicles measured, pooled over ten seeds. Other change: paired change in the mean delay of all "
                "other vehicles; paired $t$-test $p$-value in parentheses.")

abl_variants = []
for r in N["ablation"]:
    if r["variant"] not in abl_variants:
        abl_variants.append(r["variant"])
abl_rows = [[r["variant"], r["level"], r["delay"], r["change"], r["p"], r["green"]] for r in N["ablation"]]
TBL_abl = table("Ablation of the adaptive controller", "tab:ablation",
                ["Variant", "Demand", "Mean delay (s)", "Change", "$p$", "Green (s)"],
                [[tx(a) for a in row] for row in abl_rows], "llcccc",
                "Preemption enabled unless stated; ten paired seeds per row; change relative to the reference at the same demand.")

det_rows = [[n, "---" if x["detections_per_frame"] < 0.01 else f1(x["precision"]), f1(x["recall"]), f"{x['detections_per_frame']:.2f}"]
            for n, x in V["detectors"].items()]
TBL_det = table("Detector accuracy and ablation (synthetic frames)", "tab:detector",
                ["Detector variant", "Precision (%)", "Recall (%)", "Detections per frame"], det_rows, "lccc",
                "Pooled over seeds 1--4; a detection is correct when its centre lies inside a ground-truth box enlarged by 4 px. "
                "---: too few detections for a meaningful precision.")
trk_rows = [[n, f1(t["coverage"]), f1(t["vehicles_confirmed"]), f1(t["id_switches_per_100_vehicles"]),
             "n/a" if t["speed_mae"] is None else f"{t['speed_mae']:.2f}"] for n, t in V["tracking"].items()]
TBL_trk = table("Tracking quality and tracked-speed error", "tab:tracking",
                ["Tracker variant", "Coverage (%)", "Vehicles confirmed (%)", "ID switches / 100 veh.", "Speed MAE (m/s)"], trk_rows, "lcccc",
                "Coverage: share of vehicle instances in view with a confirmed track. Speed MAE: confirmed tracks on real vehicles "
                "with at least three matches; n/a where the variant has no motion estimate.")

kc0, kc1 = K0["cars only"], K1["cars only"]
km0, km1 = K0["full vehicle mix"], K1["full vehicle mix"]
TBL_kin = table("Queue discharge against field reference values", "tab:kinematics",
                ["Model", "Headway, cars (s)", "Sat. flow, cars (veh/h/lane)", "Sat. flow, all (veh/h/lane)", "Start-up lost time (s)"],
                [["Simulator, τ = 0 (used for main results)", f"{kc0['saturation_headway_s']:.2f}", fm(kc0["saturation_flow_vphpl"]),
                  fm(km0["saturation_flow_vphpl"]), f"{kc0['startup_lost_time_s']:.1f}"],
                 ["Simulator, τ = 1.6 s (calibrated)", f"{kc1['saturation_headway_s']:.2f}", fm(kc1["saturation_flow_vphpl"]),
                  fm(km1["saturation_flow_vphpl"]), f"{kc1['startup_lost_time_s']:.1f}"],
                 ["HCM base values [24]", "1.89", "1,900", "---", Raw("$\\approx$ 2.0")]], "lcccc",
                "Saturated fixed-time runs, five seeds; saturation headway averaged from the fifth queued vehicle on.")

cal_ctrl = ["webster", "actuated", "max_pressure", "density_levels", "adaptive", "adaptive_hold"]
cal_rows = [[L[c], *[minus(TC[c][lv]["mean_delay_s"]["vs_fixed"]["text"]) for lv in LV],
             minus(OC["capacity"][c]["vs_fixed"]["text"]) if c in OC["capacity"] else "---"] for c in cal_ctrl]
cal_rows += [[f"{L[c]}, zone {ZC['tuning']['best_zone_m']} m", *[minus(ZC["table2"][c][lv]["mean_delay_s"]["vs_fixed"]["text"]) for lv in LV],
              minus(ZC["over"]["capacity"][c]["vs_fixed"]["text"])] for c in ["actuated", "adaptive_hold"]]
TBL_cal = table("Main comparisons repeated with calibrated kinematics", "tab:calibrated",
                ["Controller", "Delay vs fixed, low", "medium", "high", "Capacity vs fixed"], cal_rows, "lcccc",
                "$\\tau$ = 1.6 s; ten paired seeds per demand level (preemption on) and five capacity seeds (preemption off). "
                "Gap-out controllers use the 10 m zone unless a re-tuned zone is stated.")


def sn_cell(cond, name, c):
    x = snRow(cond, name)[c]
    return Raw(f"{x['mean']:.1f}" if name == "Exact states" else f"{x['mean']:.1f} ({minus(x['vs_exact']['text'])})")


TBL_sn1 = table("Delay under imperfect sensing (s), medium demand", "tab:sensing-med", ["Sensing", *[L[c] for c in snCtrl]],
                [[n, *[sn_cell(snMed, n, c) for c in snCtrl]] for n in snNames], "l" + "c" * len(snCtrl),
                f"Change relative to the same controller with exact states in brackets. Fixed plan (needs no sensing): {tx(snMed['fixed'])} s.")
TBL_sn2 = table("Delay under imperfect sensing (s), 0.9 times capacity", "tab:sensing-cap", ["Sensing", *[L[c] for c in snCtrl]],
                [[n, *[sn_cell(snCap, n, c) for c in snCtrl]] for n in snNames], "l" + "c" * len(snCtrl),
                f"Delay includes time waiting to enter the road; preemption off. Fixed plan: {tx(snCap['fixed'])} s.")

params = [("motorcycle", "Motorcycle weight"), ("auto", "Auto-rickshaw weight"), ("bus", "Bus weight"), ("truck", "Truck weight"),
          ("emergency", "Emergency-vehicle weight"), ("queued_ratio", "Queued/moving ratio"), ("theta", "Switching ratio $\\theta$")]
cb_rows = [[Raw(lab), f"{CB['hand_set'][k]:.2f}", f"{CB['best_params'][k]:.2f}", "1.10" if k == "theta" else "1.00"] for k, lab in params]
cbp = lambda p: "$<$ 0.001" if p < 0.001 else f"{p:.3f}"
cb_rows += [[Raw(f"Delay, {tx(c)} (s)"), f"{cal_h['Hand-set (paper)'][c]['mean']:.2f}",
             Raw(f"{cal_h['Calibrated'][c]['mean']:.2f} ({pct(cal_h['Calibrated'][c]['change_pct'])}, $p$ {cbp(cal_h['Calibrated'][c]['p'])})"),
             Raw(f"{cal_h['Plain count'][c]['mean']:.2f} ({pct(cal_h['Plain count'][c]['change_pct'])})")] for c in cb_conds]
TBL_cb = table("Calibrated score parameters and held-out delay", "tab:calibration",
               ["Parameter / condition", "Hand-set", "Calibrated", "Plain count"], cb_rows, "lccc",
               "Delays on held-out seeds 1--10 (ten paired seeds); changes and $p$ relative to the hand-set weights.")

veh_rows = [["Car", "55", "4.5", "14", "2.5", "4.5", "1.0"], ["Motorcycle", "25", "2.0", "15", "3.5", "5.0", "0.5"],
            ["Auto-rickshaw", "10", "3.2", "11", "2.0", "4.0", "0.8"], ["Bus", "5", "10.0", "10", "1.2", "3.0", "3.0"],
            ["Truck", "4", "9.0", "9", "1.0", "2.8", "2.5"], ["Ambulance", "0.5", "5.5", "16", "3.0", "5.0", "6.0"],
            ["Fire truck", "0.5", "10.5", "12", "1.5", "3.5", "6.0"]]
TBL_veh = table("Vehicle classes and parameters used in the simulation", "tab:vehicles",
                ["Class", "Share (%)", "Length (m)", Raw("$v_{max}$ (m/s)"), Raw("$a$ (m/s$^2$)"), Raw("$b$ (m/s$^2$)"), Raw("Weight $w$")], veh_rows, "lcccccc",
                "$a$: maximum acceleration; $b$: maximum deceleration; $w$: density weight used in Eq.~\\eqref{eq:density}.")

cmp_rows = [["Fixed 20 s plan", d("fixed", "high")["ci"], "---", "Baseline"],
            ["Webster-optimized plan [2]", d("webster", "high")["ci"], minus(O["capacity"]["webster"]["vs_fixed"]["text"]), "1958"],
            ["Vehicle-actuated [23]", d("actuated", "high")["ci"], minus(O["capacity"]["actuated"]["vs_fixed"]["text"]), "2008"],
            ["Max-pressure [11]", d("max_pressure", "high")["ci"], minus(O["capacity"]["max_pressure"]["vs_fixed"]["text"]), "2013"],
            ["Three-level density control [1]", d("density_levels", "high")["ci"], minus(O["capacity"]["density_levels"]["vs_fixed"]["text"]), "2025"],
            ["Adaptive (density score)", d("adaptive", "high")["ci"], minus(O["capacity"]["adaptive"]["vs_fixed"]["text"]), Raw(r"\textbf{2026}")],
            [Raw(r"\textbf{Adaptive + discharge hold (ours)}"), d("adaptive_hold", "high")["ci"], minus(O["capacity"]["adaptive_hold"]["vs_fixed"]["text"]), Raw(r"\textbf{2026}")]]
TBL_cmp = table("Comparison with the strategies of existing work (re-implemented in the same simulator)", "tab:comparison",
                ["Method", "Delay, high demand (s)", "Capacity vs fixed", "Source year"], cmp_rows, "lccc",
                "All methods share the phase sequence, change intervals and 8--45 s green limits; delay from Table~\\ref{tab:below}, capacity from Table~\\ref{tab:capacity}.")

# --------------------------------------------------------------------------- values

vals = dict(
    TBL_t2=TBL_t2, TBL_cap=TBL_cap, TBL_sweep=TBL_sweep, TBL_thru=TBL_thru, TBL_queue=TBL_queue, TBL_peak=TBL_peak, TBL_pre=TBL_pre,
    TBL_abl=TBL_abl, TBL_det=TBL_det, TBL_trk=TBL_trk, TBL_kin=TBL_kin, TBL_cal=TBL_cal, TBL_sn1=TBL_sn1, TBL_sn2=TBL_sn2,
    TBL_cb=TBL_cb, TBL_veh=TBL_veh, TBL_cmp=TBL_cmp,
    runs=fm(S["total_runs"]), hours=fm(S["total_hours"]), preempt=fm(S["table2_on"]["preemptions"]),
    redu_ad=redu("adaptive"), redu_web=redu("webster"), redu_act=redu("actuated"), redu_mp=redu("max_pressure"),
    cap_loss=abspct(O["capacity"]["adaptive"]["vs_fixed"]["pct"]), cap_hold=pct(O["capacity"]["adaptive_hold"]["vs_fixed"]["pct"]),
    cap_web=pct(O["capacity"]["webster"]["vs_fixed"]["pct"]), cap_act=pct(O["capacity"]["actuated"]["vs_fixed"]["pct"]),
    cap_mp=pct(O["capacity"]["max_pressure"]["vs_fixed"]["pct"]), cap_ad=pct(O["capacity"]["adaptive"]["vs_fixed"]["pct"]),
    cap_ad_p=tx(O["capacity"]["adaptive"]["vs_fixed"]["p"]),
    green_ad=O["capacity"]["adaptive"]["green"], green_hold=O["capacity"]["adaptive_hold"]["green"],
    fixed_cap=fm(round(O["capacity"]["fixed"]["mean"])),
    lo_pct=f"{1152 / O['capacity']['fixed']['mean'] * 100:.0f}", hi_pct=f"{2592 / O['capacity']['fixed']['mean'] * 100:.0f}",
    p95=rng([-T2["adaptive"][lv]["p95_delay_s"]["vs_fixed"]["pct"] for lv in LV]),
    others_vs_ad=between([T2[c][lv]["mean_delay_s"]["vs_adaptive"]["pct"] for lv in LV for c in ["webster", "actuated", "max_pressure"]]),
    dl_med=pct(T2["density_levels"]["medium"]["mean_delay_s"]["vs_fixed"]["pct"]), dl_high=pct(T2["density_levels"]["high"]["mean_delay_s"]["vs_fixed"]["pct"]),
    hold_vs_ad=between([T2["adaptive_hold"][lv]["mean_delay_s"]["vs_adaptive"]["pct"] for lv in LV]),
    thru_max=Raw(f"{max(abs(T2[c][lv]['throughput_vph']['vs_fixed']['pct']) for c in CTRL for lv in LV):.1f}\\%"),
    green_ad_med=T2["adaptive"]["medium"]["mean_green_s"]["ci"].split(" ")[0],
    sw_cap_ad=f"{sw(cap_r, 'adaptive', 'delay_all_lb_s')['mean']:.1f}", sw_cap_fx=f"{sw(cap_r, 'fixed', 'delay_all_lb_s')['mean']:.1f}",
    sw_cap_hold=f"{sw(cap_r, 'adaptive_hold', 'delay_all_lb_s')['mean']:.1f}", sw_hi_hold=f"{sw(hi_r, 'adaptive_hold', 'delay_all_lb_s')['mean']:.1f}",
    sw_cap_act=f"{sw(cap_r, 'actuated', 'delay_all_lb_s')['mean']:.1f}", sw_hi_act=f"{sw(hi_r, 'actuated', 'delay_all_lb_s')['mean']:.1f}",
    qg_ad=f"{sw(cap_r, 'adaptive', 'queue_growth_vpm')['mean']:.1f}", sb_ad=f"{sw(cap_r, 'adaptive', 'spillback_pct')['mean']:.0f}",
    hold_delay_list=Raw(", ".join(minus(sw(r, "adaptive_hold", "delay_all_lb_s")["vs_fixed"]["text"]) for r in RATIOS)),
    hold_cap_p=tx(sw(cap_r, "adaptive_hold", "delay_all_lb_s")["vs_fixed"]["p"]),
    thr_hi=pct(sw(hi_r, "adaptive_hold", "throughput_vph")["vs_fixed"]["pct"]), thr_15=pct(sw(r15, "adaptive_hold", "throughput_vph")["vs_fixed"]["pct"]),
    on_ad=pct(Oon["capacity"]["adaptive"]["vs_fixed"]["pct"]), on_hold=pct(Oon["capacity"]["adaptive_hold"]["vs_fixed"]["pct"]),
    pk_fx=f"{PK['fixed']['peak_queue']['mean']:.0f}", pk_hold=f"{PK['adaptive_hold']['peak_queue']['mean']:.0f}",
    pk_act=f"{PK['actuated']['peak_queue']['mean']:.0f}", pk_ad=f"{PK['adaptive']['peak_queue']['mean']:.0f}",
    rec_fx=pk_rec("fixed"), rec_hold=pk_rec("adaptive_hold"), rec_ad=pk_rec("adaptive"), rec_mp=pk_rec("max_pressure"),
    sp_fx=f"{PK['fixed']['spillback_approach_min']['mean']:.0f}", sp_hold=f"{PK['adaptive_hold']['spillback_approach_min']['mean']:.0f}",
    sp_ad=f"{PK['adaptive']['spillback_approach_min']['mean']:.0f}",
    pt_fx=f"{PK['fixed']['peak_throughput_vph']['mean']:.0f}", pt_hold=f"{PK['adaptive_hold']['peak_throughput_vph']['mean']:.0f}",
    pt_ad=f"{PK['adaptive']['peak_throughput_vph']['mean']:.0f}",
    td_hold=minus(PK["adaptive_hold"]["total_delay_vs_fixed"]["text"]), td_act=minus(PK["actuated"]["total_delay_vs_fixed"]["text"]),
    td_ad=minus(PK["adaptive"]["total_delay_vs_fixed"]["text"]),
    pre_rate=rng([T3["adaptive"][lv]["preemptions_per_hour"] for lv in LV]).replace("\\%", ""),
    abl_un_m=abspct(abl("Unweighted", "medium")["pct"]), abl_un_h=abspct(abl("Unweighted", "high")["pct"]),
    abl_nq_m=abspct(abl("No queued", "medium")["pct"]), abl_nq_h=abspct(abl("No queued", "high")["pct"]),
    abl_nc_m=pct(abl("No class", "medium")["pct"]), abl_nc_h=pct(abl("No class", "high")["pct"]),
    abl_th_m=pct(abl("theta = 1.5", "medium")["pct"]), abl_th_h=pct(abl("theta = 1.5", "high")["pct"]),
    frames=fm(det0["frames"]), gt=fm(det0["gt_instances"]), prec=f1(det0["precision"]), rec=f1(det0["recall"]),
    persist=f1(V["failure"]["persistent_background_share"]),
    class_recall=", ".join(f"{tx(c)} {f1(v['recall'])}\\%" for c, v in V["by_class"].items()),
    dist_recall=", ".join(f"{tx(k)} {f1(v['recall'])}\\%" for k, v in V["by_distance"].items()),
    prec2x=f1(V["detectors"]["2x upscale"]["precision"]), rec2x=f1(V["detectors"]["2x upscale"]["recall"]),
    cover=f1(trk0["coverage"]), confirmed=f1(trk0["vehicles_confirmed"]),
    speed_mae=f"{trk0['speed_mae']:.2f}", speed_n=trk0["speed_n"], speed_true=f"{trk0['true_speed_mean']:.2f}",
    hw0=f"{kc0['saturation_headway_s']:.2f}", sf0=fm(kc0["saturation_flow_vphpl"]), hw1=f"{kc1['saturation_headway_s']:.2f}",
    sf1=fm(kc1["saturation_flow_vphpl"]), sf1_err=f"{abs(100 * (kc1['saturation_flow_vphpl'] - 1900) / 1900):.1f}",
    sul1=Raw(f"{kc1['startup_lost_time_s']:.1f}".replace("-", "$-$")),
    redu_cal_ad=redu("adaptive", TC), redu_cal_web=redu("webster", TC), redu_cal_act=redu("actuated", TC), redu_cal_mp=redu("max_pressure", TC),
    cal_fixed_cap=fm(round(OC["capacity"]["fixed"]["mean"])), cal_ad=pct(OC["capacity"]["adaptive"]["vs_fixed"]["pct"]),
    cal_web=pct(OC["capacity"]["webster"]["vs_fixed"]["pct"]), cal_hold10=pct(OC["capacity"]["adaptive_hold"]["vs_fixed"]["pct"]),
    cal_hold10_green=OC["capacity"]["adaptive_hold"]["green"], zone=ZC["tuning"]["best_zone_m"],
    zone_hold=pct(ZC["over"]["capacity"]["adaptive_hold"]["vs_fixed"]["pct"]), zone_act=pct(ZC["over"]["capacity"]["actuated"]["vs_fixed"]["pct"]),
    zone_web=pct(ZC["over"]["capacity"]["webster"]["vs_fixed"]["pct"]),
    sense_text=sense_text(), calib_text=calib_text(), cb_cand=CB["candidates"], cb_t0=CB["tune_seeds"][0], cb_t1=CB["tune_seeds"][-1],
    cb_m=f"{CB['best_params']['motorcycle']:.2f}", cb_a=f"{CB['best_params']['auto']:.2f}", cb_b=f"{CB['best_params']['bus']:.2f}",
    cb_t=f"{CB['best_params']['truck']:.2f}", cb_e=f"{CB['best_params']['emergency']:.2f}", cb_q=f"{CB['best_params']['queued_ratio']:.2f}",
    cb_th=f"{CB['best_params']['theta']:.2f}",
    ev_fx_off=T3["fixed"]["medium"]["ev_delay_off"], ev_fx_on=T3["fixed"]["medium"]["ev_delay_on"],
    ev_ad_off=T3["adaptive"]["medium"]["ev_delay_off"], ev_ad_on=T3["adaptive"]["medium"]["ev_delay_on"],
    oth_fx=minus(T3["fixed"]["medium"]["other_change"]["text"]), oth_ad=minus(T3["adaptive"]["medium"]["other_change"]["text"]),
    oth_hold=minus(T3["adaptive_hold"]["medium"]["other_change"]["text"]),
)
# the cap_* helpers carry a trailing "\%" already; text templates must not add another one.

# --------------------------------------------------------------------------- front matter

TITLE = "Smart Traffic Control System Using Vehicle Density Analysis"
STUDENTS = ["Madhav Goel", "Akash Varshney", "Abhisekh Chaudhary", "Shivam Goel"]
MENTOR = "Ruchi Gupta"
stud_lines = "\\\\\n  ".join(f"{s} (Roll No.)" for s in STUDENTS)

MAIN = r"""%% ============================================================
%% main.tex  ---  B.Tech Final Year Project Report (2026)
%% Ajay Kumar Garg Engineering College | AKTU Lucknow
%% Compiler: pdfLaTeX  (Overleaf Free Plan)
%% Bibliography: BibTeX  (NOT Biber)
%% ============================================================

\documentclass[a4paper,12pt]{report}

\usepackage[top=30mm, bottom=25mm, left=35mm, right=20mm]{geometry}
\usepackage{times}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{setspace}
\usepackage{graphicx}
\usepackage{float}
\usepackage{booktabs}
\usepackage{array}
\usepackage{multicol}
\usepackage{multirow}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{xcolor}
\usepackage{listings}
\usepackage{fancyhdr}
\usepackage{titlesec}
\usepackage[hidelinks]{hyperref}

% Fix headheight warning
\setlength{\headheight}{14pt}

% Chapter title style
\titleformat{\chapter}[display]
  {\normalfont\Large\bfseries\centering}
  {\chaptertitlename\ \thechapter}{10pt}{\Huge}
\titlespacing*{\chapter}{0pt}{-20pt}{20pt}

% Header / footer
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small\textit{\reporttitle}}
\fancyhead[R]{\small\textit{AKGEC, Ghaziabad}}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0.4pt}

% Code listings style
\lstset{
  basicstyle=\ttfamily\small,
  breaklines=true,
  frame=single,
  numbers=left,
  numberstyle=\tiny\color{gray},
  keywordstyle=\color{blue}\bfseries,
  commentstyle=\color{green!60!black},
}

%% ============================================================
%%  EDIT BELOW -- Fill in your project details
%% ============================================================
\newcommand{\reporttitle}{@TITLE@}
\newcommand{\projectgroupid}{2023-27/IT/SECTION/GID}
\newcommand{\students}{%
  @STUDENTS@}
\newcommand{\mentor}{@MENTOR@}
\newcommand{\hod}{Dr. Rahul Sharma}
\newcommand{\dept}{Department of Information Technology}
\newcommand{\college}{AJAY KUMAR GARG ENGINEERING COLLEGE, GHAZIABAD}
\newcommand{\university}{DR. A.P.J. ABDUL KALAM TECHNICAL UNIVERSITY, LUCKNOW}
\newcommand{\submissiondate}{\today}
%% ============================================================

\begin{document}

%% ---- TITLE PAGE --------------------------------------------
\begin{titlepage}
  \thispagestyle{empty}
  \begin{flushright}
    \small\textbf{Group ID: \projectgroupid}
  \end{flushright}
  \centering\vspace*{0.5cm}

  {\large\textbf{A Project Report on}\par}\vspace{0.5cm}
  {\LARGE\textbf{\reporttitle}\par}\vspace{0.5cm}

  {Submitted in Partial Fulfillment of the Requirements for the Degree of\par}
  \vspace{0.4cm}
  {\Large\textbf{Bachelor of Technology in Information Technology}\par}
  \vfill

  {Submitted by\par}\vspace{0.4cm}
  {\large\students\par}\vfill

  {Under the Supervision of\par}\vspace{0.3cm}
  {\large\textbf{\mentor}\par}\vfill

  \includegraphics[width=3cm]{AKGEC_1_0.png}\vspace{0.4cm}

  {\large\textbf{\dept}\par}
  {\large\textbf{\college}\par}
  {\large\textbf{\university}\par}\vfill
  {\large\submissiondate\par}\vspace*{0.5cm}
\end{titlepage}

%% ---- FRONT MATTER (roman numbering) -----------------------
\pagenumbering{roman}
\onehalfspacing

\newpage\input{frontmatter/Declaration}
\newpage\input{frontmatter/Certificate}
\newpage\input{frontmatter/Acknowledgements}
\newpage\input{frontmatter/Abstract}

\newpage\tableofcontents
\newpage\listoffigures
\newpage\listoftables

%% ---- MAIN CHAPTERS (arabic numbering) ---------------------
\newpage\pagenumbering{arabic}

\input{chapters/Chapter1_Introduction}
\input{chapters/Chapter2_LiteratureReview}
\input{chapters/Chapter3_Methodology}
\input{chapters/Chapter4_Implementation}
\input{chapters/Chapter5_ResultsDiscussion}
\input{chapters/Chapter6_SocietalImpact}
\input{chapters/Chapter7_UHV}
\input{chapters/Chapter8_Conclusion}

%% ---- REFERENCES -------------------------------------------
\newpage
\addcontentsline{toc}{chapter}{References}
\bibliographystyle{IEEEtran}
\bibliography{References}

%% ---- APPENDICES -------------------------------------------
\appendix
\input{appendices/AppendixA_UNAI_Certificate}
\input{appendices/AppendixB_Code}
\input{appendices/AppendixC_CV}

\end{document}
"""

DECLARATION = r"""%% frontmatter/Declaration.tex
\chapter*{Declaration}
\addcontentsline{toc}{chapter}{Declaration}

\large {\setstretch{1.0} We hereby declare that the work presented in this report, entitled as {\textbf{``\reporttitle''}}, was carried out by us. We have not submitted the matter embodied in this report for the award of any other degree or diploma of any other University or Institute. We have given due credit to the original authors and sources for all the words, ideas, diagrams, graphics, computer programs, experiments, and results that are not our original contribution. We have used quotation marks to identify verbatim sentences and given credit to the original authors and sources.}\\

{\setstretch{1.2} We have self-checked this report for plagiarism using appropriate tools and confirm that it meets the prescribed academic integrity standards.}\\


\vspace{3cm}

\noindent
\begin{tabular}{@{}ll}
    \textbf{Student Names} & \textbf{Signatures} \\[0.5cm]
@SIGROWS@
\end{tabular}

\vspace{1.5cm}
\noindent Date: \submissiondate
"""

CERTIFICATE = r"""%% frontmatter/Certificate.tex
\chapter*{Certificate}
\addcontentsline{toc}{chapter}{Certificate}

This is to certify that the project report entitled \textbf{``\reporttitle''}, submitted by the following students in partial fulfillment of the requirements for the award of the degree of \textit{Bachelor of Technology in Information Technology} to Ajay Kumar Garg Engineering College, Ghaziabad (affiliated to Dr.\ A.P.J.\ Abdul Kalam Technical University, Lucknow) is an authentic record of genuine work carried out by them under my supervision.

\vspace{0.5cm}
\noindent\textbf{Students:}\\
@CERTSTUDENTS@

\vspace{0.5cm}
\noindent The matter presented in this report has not been submitted for the award of any other degree or diploma at this or any other institution.

\vspace{3cm}

\noindent
\begin{tabular}{@{}p{7cm}p{7cm}}
    \underline{\hspace{5cm}} & \underline{\hspace{5cm}} \\
    \textbf{\mentor} & \textbf{\hod} \\
    Supervisor & Head of Department \\
    \dept & \dept \\
    \college & \college \\
\end{tabular}

\vspace{1.5cm}
\noindent Date: \submissiondate
"""

ACK = r"""%% frontmatter/Acknowledgements.tex
\chapter*{Acknowledgements}
\addcontentsline{toc}{chapter}{Acknowledgements}

We express our deepest gratitude to our project supervisor, \textbf{\mentor}, \dept, Ajay Kumar Garg Engineering College, Ghaziabad, for their invaluable guidance, constant encouragement, and constructive feedback throughout the course of this project. Their expertise and insights have been instrumental in shaping this work.

We sincerely thank \textbf{\hod}, Head of the \dept, for providing the necessary infrastructure, lab facilities, and an environment conducive to research and learning.

We extend our heartfelt thanks to the faculty members of the \dept\ for their continuous support and for imparting the foundational knowledge that has made this project possible.

We are grateful to the management of \textbf{\college} for maintaining an ecosystem that encourages innovation and applied research.

An AI assistant (Anthropic's Claude) was used in developing parts of the software and in drafting and editing this report and the related research paper; we have reviewed the content and take responsibility for it.

Finally, we acknowledge our families and friends for their unwavering moral support and patience during the entire duration of this project.

\vspace{2cm}
\noindent\textbf{Student Names:}\\[0.3cm]
@ACKSTUDENTS@

\vspace{0.5cm}
\noindent Date: \submissiondate
"""

ABSTRACT = r"""%% frontmatter/Abstract.tex
\chapter*{Abstract}
\addcontentsline{toc}{chapter}{Abstract}

Fixed-time traffic signals give every approach of a junction the same green time regardless of demand, which wastes green on lightly used approaches and lengthens queues on busy ones. This project designs, implements and evaluates a density-aware signal controller for an isolated four-arm junction. Each approach is scored from vehicle class and queue state, with a queued vehicle counting three times as much as a moving one; the green is extended between 8~s and 45~s while the served direction dominates, yellow and all-red intervals are never shortened, and an emergency-vehicle preemption layer keeps full change intervals.

The system is a complete simulation-first software stack: a Python microscopic simulator, a decision engine, a Haar-cascade detection and ByteTrack-style tracking pipeline, a FastAPI backend with a SQLite store, a React dashboard and an optional Raspberry Pi/ESP32 signal driver. It was evaluated on paired, seeded traffic against the fixed plan and four re-implemented strategies (Webster-optimized, actuated, max-pressure and three-level density control) in @runs@ runs.

Below capacity the controller reduced mean stopped delay by @redu_ad@ relative to a 20~s fixed plan, but the Webster, actuated and max-pressure strategies did as well. Near capacity, density-only switching lost @cap_loss@ of capacity; a discharge-hold rule restored it (@cap_hold@ relative to fixed timing). The queued/moving distinction, not the class weights, drives the score's benefit. The findings hold with kinematics calibrated to field saturation headways once the hold zone is re-tuned, but with the present Haar detector (@prec@\% precision, @rec@\% recall) every controller would be worse than fixed timing near capacity. A per-step audit found no conflicting greens or shortened change intervals in any run.

\vspace{0.8cm}
\noindent\textbf{Keywords:} adaptive traffic signal control, vehicle density, actuated control, max-pressure control, emergency vehicle preemption, oversaturation, microscopic simulation
"""

# --------------------------------------------------------------------------- chapters

CH1 = r"""%% Chapter1_Introduction.tex
\chapter{Introduction}
\label{chap:intro}

\section{Background and Motivation}
Signalized intersections account for a large share of the delay in urban road networks. Many junctions, especially in smaller cities, still run fixed-time plans in which each approach receives a preset green interval regardless of how many vehicles are waiting. Such plans are dimensioned for average flows; when demand fluctuates or is unevenly distributed across approaches, green time is wasted on nearly empty approaches while queues build on busy ones. Traffic in Indian cities adds further variety: motorcycles, auto-rickshaws, buses and trucks share the road with cars, and emergency vehicles must be able to cross a junction without delay.

Traffic-responsive systems such as SCATS and SCOOT adjust timings from detector data, but they rely on dedicated detector infrastructure and centrally managed installations~\cite{ref3,ref4}. Low-cost alternatives estimate density locally with infrared sensors, image-based density classes, deep detectors on camera feeds or existing surveillance cameras, and adapt green time accordingly~\cite{ref1,ref5,ref6,ref8,ref9,ref10}. These low-cost systems are usually demonstrated on a prototype or a few scenarios and report an average improvement over a fixed plan. Four questions are rarely answered: whether timing logic that varies green keeps safe change intervals; how emergency priority interacts with density-based timing; how the controller behaves as demand approaches and exceeds capacity; and how much of a reported gain is due to the density logic at all, rather than to replacing an untuned fixed plan with any demand-responsive one. This project addresses these questions.

\section{Problem Statement}
The lack of a rigorous, reproducible evaluation of low-cost density-based signal control, against strong baselines, near and above capacity, and with verified signal safety, leaves it unclear when such a controller is actually better than a well-tuned fixed or actuated plan. This project addresses the problem by building a complete simulation-first traffic management system with a density-aware controller, an emergency preemption layer and a vision pipeline, and by evaluating it on identical seeded traffic against re-implementations of the strategies used by existing approaches.

\section{Research Objectives}
The key objectives of this project are:
\begin{enumerate}
  \item To design and develop a density-aware adaptive signal controller, an emergency-vehicle preemption layer that keeps full change intervals, and a vision pipeline (detection and tracking), together with a live dashboard and a hardware bridge.
  \item To analyse and evaluate the controller against a fixed plan and four re-implemented strategies (Webster-optimized fixed, vehicle-actuated, max-pressure and three-level density control) below, at and above junction capacity.
  \item To validate the performance of the system: signal safety at every simulation step, the simulator's queue discharge against Highway Capacity Manual values, the vision pipeline against exact ground truth, and the effect of imperfect sensing.
  \item To demonstrate the societal relevance of the work: shorter waiting, safer emergency-vehicle passage and reduced idling, in line with the UN Sustainable Development Goals.
\end{enumerate}

\section{Novelty and Originality}
Rather than proposing a new detector, this project studies the \emph{timing logic} of a density-based controller under controlled, statistically paired conditions, against re-implementations of the strategies used by existing approaches: a Webster-optimized fixed plan~\cite{ref2}, vehicle-actuated control~\cite{ref23}, max-pressure control~\cite{ref11} and the three-level density control of~\cite{ref1}. The evaluation exposes a failure mode of density-only switching near capacity, which is corrected by a discharge-hold rule taken from actuated control. The role of AI and machine learning is stated plainly: the signal controller is a transparent rule, not a learned policy; machine learning enters through the pre-trained Haar-cascade detector of the vision pipeline, whose accuracy is measured, and through a data-driven calibration of the controller's parameters on held-out simulation seeds. The original contributions are listed in Section~\ref{sec:contrib}.

\section{Scope of the Project}
\textbf{Included:} a Python microscopic simulator of a four-arm junction with seven vehicle classes; fixed-time, adaptive and four comparison controllers; emergency preemption with a per-step safety audit; a virtual-camera Haar-cascade detector and ByteTrack-style tracker evaluated against exact ground truth; a FastAPI backend with WebSocket streaming and SQLite persistence; a React dashboard with analytics and live fixed-versus-adaptive comparison; a Raspberry Pi/ESP32 signal-driver bridge; Docker packaging and continuous integration; and the experiments reported in Chapter~\ref{chap:results}.

\textbf{Excluded:} turning movements, lane changes, pedestrians and multi-junction coordination; recorded or real-world camera footage; closing the control loop on detector output; reinforcement-learning controllers; and tests on a physical junction or a verified hardware deployment. These are left for future work (Section~\ref{sec:future}).

\section{Report Organisation}
Chapter 2 presents the literature review.
Chapter 3 describes the research methodology.
Chapter 4 covers the implementation details.
Chapter 5 presents results and discussion.
Chapter 6 discusses societal impact and SDG alignment.
Chapter 7 addresses Universal Human Values.
Chapter 8 concludes the report with future directions.
"""

CH2 = r"""%% Chapter2_LiteratureReview.tex
\chapter{Literature Review}
\label{chap:lit}

\section{Historical Overview}
Fixed-time signal plans are commonly derived from Webster's delay-minimizing cycle-length formula~\cite{ref2}. Networks of signals were later coordinated with traffic-responsive systems: SCATS adjusts splits, cycle lengths and offsets from detector data~\cite{ref3}, and SCOOT optimizes the plan on line from loop-detector flows~\cite{ref4}. Vehicle-actuated control, standard in signal timing practice, extends a green while detectors near the stop line keep registering vehicles and ends it when a gap appears (``gap-out''), within minimum and maximum green limits~\cite{ref23}. Max-pressure control chooses phases from queue differences and has provable throughput guarantees~\cite{ref11}.

On the simulation side, the Gipps car-following model~\cite{ref21} and the Krau{\ss} model with its driver reaction time~\cite{ref25} are the basis of many microscopic simulators, SUMO among them~\cite{ref22}. The Highway Capacity Manual~\cite{ref24} supplies the field saturation-flow and start-up lost-time values against which a simulator can be checked. For sensing, Viola and Jones introduced boosted cascades of Haar-like features~\cite{ref16}, which remain attractive for embedded use because inference is cheap and needs no GPU; multi-object trackers combine a Kalman filter~\cite{ref18} with Hungarian assignment~\cite{ref19}, as in ByteTrack~\cite{ref17}.

\section{Recent and State-of-the-Art Work}
Reinforcement-learning controllers have been studied widely, although they must be trained in simulation and their behaviour is harder to bound~\cite{ref12}. Among low-cost density-based systems, Nsofwa and Tembo classify image-based density into low, medium and high levels and adjust signal duration, showing in simulation that this outperforms fixed timing~\cite{ref1}. Kamble et al.\ apply YOLO-based recognition~\cite{ref7} to IP-camera feeds to prioritize the busiest lane~\cite{ref6}; such detectors are accurate but demanding on low-power hardware. Pardeshi et al.\ use passive infrared sensors on an ESP32 platform~\cite{ref5}, and Patil et al.\ and Thomas et al.\ also adapt timing to measured density~\cite{ref9,ref10}. Hu et al.\ estimate density from surveillance cameras~\cite{ref8}. Related systems add incident detection and alerting~\cite{ref13}, AI-based light design~\cite{ref14} or machine-learning traffic prediction on the Edge Impulse platform~\cite{ref15}. Emergency vehicles have been given signal priority based on visual sensing~\cite{ref20}.

These works mainly report an improvement over fixed timing on a prototype or a few scenarios. This project differs in three ways: it compares against strong baselines on identical traffic, it tests demand up to 1.5 times capacity, and it verifies change-interval safety at every simulation step.

\section{Comparative Analysis of Existing Approaches}

\begin{table}[H]
\centering
\caption{Comparison of Existing Approaches}
\label{tab:litreview}
\small
\begin{tabular}{@{}p{3.3cm}p{1.1cm}p{3.6cm}p{3.1cm}p{3.6cm}@{}}
\toprule
\textbf{Author(s)} & \textbf{Year} & \textbf{Approach} & \textbf{Setting} & \textbf{Limitation (for this study)} \\
\midrule
Webster~\cite{ref2} & 1958 & Delay-optimal fixed cycle and splits & Fixed plan from mean demand & Cannot react to fluctuating or uneven demand \\
Sims and Dobinson~\cite{ref3}; Hunt et al.~\cite{ref4} & 1980, 1982 & SCATS and SCOOT: detector-based adaptive plans & Networks with loop detectors & Needs dedicated detector infrastructure \\
Koonce et al.~\cite{ref23} & 2008 & Vehicle-actuated control with gap-out & Stop-line detectors & Needs detectors; no density score \\
Varaiya~\cite{ref11} & 2013 & Max-pressure phase selection & Queue differences & Moving vehicles also leave the pressure count as a queue discharges \\
Nsofwa and Tembo~\cite{ref1} & 2025 & Three-level image-based density classes set the green & Simulation & Compared with fixed timing; no capacity or safety-interval study reported \\
Pardeshi et al.~\cite{ref5} & 2026 & Infrared sensing and density-based prioritization on ESP32 & Prototype platform & Gain reported against fixed timing \\
Kamble et al.~\cite{ref6} & 2025 & YOLO on IP-camera feeds; busiest lane first & Camera feeds & Detector is demanding on low-power hardware \\
Hu et al.~\cite{ref8} & 2023 & Density estimation from surveillance cameras & Existing camera network & Estimates density; timing logic not the focus \\
Patil et al.~\cite{ref9}; Thomas et al.~\cite{ref10} & 2024, 2025 & Timing adapted to measured density & Prototype or few scenarios & Gain reported against fixed timing \\
\bottomrule
\end{tabular}
\end{table}

\section{Identification of Research Gap}
Based on the review above, the following gaps remain in the existing literature:
\begin{enumerate}
  \item Gap 1: Low-cost density-based controllers are usually compared only with fixed timing, so it is unknown how much of their gain comes from the density logic rather than from replacing an untuned plan.
  \item Gap 2: Behaviour near and above capacity (queue growth, spillback, throughput) and the safety of change intervals under variable greens and emergency preemption are rarely examined.
  \item Gap 3: The gap between idealized sensing and the accuracy of a real, inexpensive detector is seldom quantified, nor are the density weights validated.
\end{enumerate}
The proposed project directly addresses these gaps by comparing against re-implemented Webster, actuated, max-pressure and density-level strategies on identical traffic, by sweeping demand from 0.6 to 1.5 times capacity with a per-step safety audit, and by measuring the effect of imperfect sensing and of calibrating the weights on held-out seeds.
"""

CH3 = r"""%% Chapter3_Methodology.tex
\chapter{Research Methodology}
\label{chap:meth}

\section{Research Approach}
The work is simulation-based and experimental. A software-only approach was chosen because experiments on a real junction are costly, unsafe and not repeatable, whereas a simulator lets every controller see exactly the same arrivals. A seed fixes the random arrival sequence, so runs of different controllers form matched pairs; results are reported as means with 95\% confidence intervals and compared with paired $t$-tests. The system is built incrementally, milestone by milestone, and each milestone is fully working before the next begins. Control uses exact simulated vehicle states; the vision pipeline is evaluated alongside against exact ground truth, and a separate sensing experiment measures what imperfect sensing would cost.

\section{Proposed System / Algorithm / Framework}

\subsection{Overall Architecture and Workflow}
The system consists of Python packages with one-directional dependencies: the simulation core imports no decision, analytics or web code, and every signal controller implements one interface (an update per time step and a phase name), so fixed-time, adaptive and comparison controllers can be exchanged without changes elsewhere. Figure~\ref{fig:architecture} shows the architecture and Figure~\ref{fig:workflow} the method workflow: in every step the controller senses vehicle positions, speeds and classes, scores each approach, and decides whether the current green may end; the preemption layer then protects every transition with full yellow and all-red intervals before the signal heads change.

@FIG_ARCH@
@FIG_WORKFLOW@

\subsection{Junction and Traffic Model}
The junction has four approaches, each with two lanes on a 330~m link; the stop line is at 200~m and the far edge of the junction box at 218~m. Vehicles travel straight through; turning movements, lane changes and pedestrians are not modelled. Vehicles arrive on each approach at a mean rate $\lambda$ with deterministic headways (one vehicle every $1/\lambda$~s); to create shifting imbalance, every 15~s the rate of each approach is redrawn as $\lambda\cdot U(0.4,1.6)$, with a floor of 0.02~veh/s. An arriving vehicle enters a lane at rest and is dropped if the rear of the previous vehicle is still within 8~m. For the above-capacity experiments two options are enabled instead: a blocked arrival waits in an entry queue and enters as soon as there is room, so that unserved demand and its waiting time are measured, and a vehicle enters at the highest speed from which it can still stop behind its leader. Table~\ref{tab:vehicles} lists the seven vehicle classes.

@TBL_veh@

Longitudinal motion follows a Gipps-type safe-speed rule~\cite{ref21}. A follower's speed is limited to
\begin{equation}
u_{safe} = \sqrt{2b\left(g + \frac{u_l^{2}}{2b_l} - s_0\right)}
\label{eq:safe}
\end{equation}
where $g$ is the gap to the leader's rear, $u_l$ and $b_l$ are the leader's speed and maximum deceleration, $b$ is the follower's maximum deceleration and $s_0 = 2$~m is the standstill gap. A position constraint prevents any overlap within a step. On yellow or red, a vehicle upstream of the stop line brakes once its braking distance reaches the distance to the line; a vehicle too close to stop continues. Rule~\eqref{eq:safe} has no driver reaction time; Section~\ref{sec:kin} shows that this makes queues discharge too fast, adds a reaction time $\tau$, and repeats the main comparisons with it.

\subsection{Density Estimation}
For approach $r$ with vehicle set $V_r$, the density score is
\begin{equation}
D_r = \sum_{v\in V_r} w_{c(v)}\, m(v)
\label{eq:density}
\end{equation}
where $w_{c(v)}$ is the class weight (Table~\ref{tab:vehicles}) and $m(v) = 1.5$ if vehicle $v$ is queued and $0.5$ otherwise. A vehicle is queued when it is upstream of the stop line and slower than 0.5~m/s. The weights reflect the road space and discharge time a vehicle class needs, and emergency vehicles receive a high weight so that their approach is favoured even without preemption. A queued vehicle counts three times as much as a moving one because it needs green now, whereas a moving vehicle may still be far upstream. The weights are heuristic; Section~\ref{sec:ablation} measures the contribution of each part of the score and Section~\ref{sec:calib} calibrates them. For display, an approach is labelled low ($D_r \le 3$), medium ($3 < D_r \le 6$) or high ($D_r > 6$).

\subsection{Adaptive Green Extension}
The controller uses a two-phase plan: north--south green, yellow ($Y = 3$~s), all-red ($A = 1$~s), then east--west green, yellow and all-red. Only the green duration adapts. Let $t_g$ be the elapsed green time, and $D_A$ and $D_W$ the summed scores of the active and the waiting direction. At every step the green ends when
\begin{equation}
t_g \ge G_{max} \quad\text{or}\quad \bigl(t_g \ge G_{min} \;\text{and}\; D_A \le \theta D_W\bigr)
\label{eq:green}
\end{equation}
with $G_{min} = 8$~s, $G_{max} = 45$~s and $\theta = 1.1$. The green is thus extended while the served direction's score exceeds the waiting direction's by more than 10\%. Because yellow and all-red are fixed and green is capped, the red time of any approach in normal operation is bounded by
\begin{equation}
R_{max} = A + G_{max} + Y + A = 50\ \text{s}
\label{eq:rmax}
\end{equation}
so no approach can be starved. The fixed-time baseline uses the same sequence with a 20~s green (48~s cycle).

\subsection{Discharge Hold}
\label{sec:hold}
Rule~\eqref{eq:green} has a weakness that the above-capacity experiments expose (Section~\ref{sec:cap}). When both directions are saturated, the vehicles moving off on green score 0.5 each while the queue growing on red scores 1.5 each, so $D_A \le \theta D_W$ holds soon after $G_{min}$ and greens stay short; each phase change costs $Y + A = 4$~s in which no vehicle is served, so short greens lose capacity exactly when it is scarcest. The discharge hold adds the gap-out test of actuated control~\cite{ref23}: past the minimum, a green may only end once the served direction has gapped out, i.e.\ no served vehicle is within $z$ of its stop line,
\begin{equation}
t_g \ge G_{max} \quad\text{or}\quad \bigl(t_g \ge G_{min} \;\text{and}\; n_z = 0 \;\text{and}\; D_A \le \theta D_W\bigr)
\label{eq:hold}
\end{equation}
where $n_z$ is the number of served vehicles within $z = 10$~m upstream of the stop line. A saturated queue moving off always keeps a vehicle at the line and so keeps its green up to $G_{max}$, while free-flowing arrivals cross 10~m in under a second, so a cleared queue still hands over early. The zone length was chosen from 10, 15, 20 and 30~m on a separate tuning seed that is not used in any reported result. Yellow, all-red and the green limits are unchanged, so bound~\eqref{eq:rmax} still holds.

\subsection{Comparison Controllers}
To compare against existing approaches (Chapter~\ref{chap:lit}), four strategies were re-implemented in the same simulator. They are not the original systems: like the proposed controller they read exact vehicle states, and all share its phase sequence, its 3~s yellow and 1~s all-red, and its 8--45~s green limits, so every one obeys bound~\eqref{eq:rmax} and the comparison isolates the switching decision.
\begin{itemize}
  \item \textbf{Webster fixed:} a fixed plan whose green follows Webster's formula~\cite{ref2} for the mean demand of each run: $C_0 = (1.5L + 5)/(1 - Y_f)$, with lost time $L = 8$~s, $Y_f$ the sum of the critical flow ratios $q/s$, the saturation flow $s = 6000$~veh/h per approach measured in the simulator, and each phase receiving $(C_0 - L)/2$, clamped to 8--45~s. It knows the true mean demand of the run, which favours it.
  \item \textbf{Actuated:} past the minimum, the green ends as soon as the served direction gaps out (no vehicle within 10~m of its stop line) and a vehicle waits on the other direction~\cite{ref23}; no density score is used.
  \item \textbf{Max-pressure:} the pressure of a phase is the number of vehicles upstream of its stop lines minus those downstream, which is zero with free exits~\cite{ref11}; past the minimum the controller switches as soon as the waiting phase's pressure exceeds the served one's. This also represents busiest-lane-first control~\cite{ref6}.
  \item \textbf{Density levels:} following~\cite{ref1}, when a green starts the served direction's density is classed low, medium or high and the green is set to 10, 20 or 30~s, without revision during the green.
\end{itemize}

\subsection{Emergency Vehicle Preemption}
Preemption is a wrapper around any phase-based controller (Figure~\ref{fig:preemption}). Without an emergency vehicle it passes control to the inner controller. When an ambulance or fire truck is upstream of the junction exit, it acts as follows.
\begin{itemize}
  \item \textbf{Entry:} a conflicting green first shows a full 3~s yellow, and a yellow already showing keeps its remaining time; all approaches are then red for 1~s, or for the remainder of an all-red already under way. If the emergency vehicle's approach is already green, that green is held.
  \item \textbf{Priority green:} the emergency vehicle's direction (both opposing approaches) is green until no emergency vehicle remains before the junction exit, or for at most 20~s.
  \item \textbf{Release:} the priority green ends with a full yellow and all-red, after which the inner controller restarts at the green of the direction that was held.
  \item \textbf{Minimum green:} a green shown for less than 5~s is never cut, and an approach that already has green is served first.
\end{itemize}
When no other preemption is active, an emergency vehicle waits at most $5 + 3 + 1 = 9$~s for its priority green. Emergency vehicles are detected from the simulator state, i.e.\ perfect detection is assumed; in practice the input could come from vehicle-to-infrastructure messages or visual sensing.

@FIG_PREEMPT@

\subsection{Vision Pipeline}
For each approach a virtual camera renders a $200\times240$ pixel frame of the 60~m before the stop line (4~px/m). Vehicles appear as shaded rectangles with a windshield band on a noisy road texture with lane markings. The detector converts the frame to grayscale, equalizes its histogram, upscales it three times, and applies OpenCV's cascade classifier with a pre-trained vehicle cascade~\cite{ref16} (scale factor 1.05, minimum neighbours 2, minimum size 20~px); the final-stage weight, clipped to $[0,1]$, serves as a relative confidence. A single cascade localizes vehicles but does not classify them, so on its own it cannot supply the class weights of Eq.~\eqref{eq:density}.

The tracker keeps a constant-velocity Kalman filter~\cite{ref18} on each box centre and matches predicted boxes to detections with the Hungarian algorithm~\cite{ref19} on an IoU cost (minimum IoU 0.15). As in ByteTrack~\cite{ref17}, detections with confidence $\ge 0.15$ are matched first and the remaining low-confidence detections are then matched to still-unmatched tracks; only confident detections start tracks. A track is confirmed after two matches and deleted after three frames without one.

\section{Tools, Technologies, and Platforms}

\begin{table}[H]
\centering
\caption{Tools and Technologies Used}
\label{tab:tools}
\small
\begin{tabular}{@{}p{3.5cm}p{5cm}p{6cm}@{}}
\toprule
\textbf{Category} & \textbf{Tool / Technology} & \textbf{Purpose} \\
\midrule
Programming Language & Python 3.12; JavaScript (ES modules) & Simulation, decision engine, backend; dashboard \\
Numerical / Vision   & NumPy 2.1, SciPy 1.14, OpenCV 4.10 (headless) & Statistics and Hungarian assignment; Haar cascade and image processing \\
Backend Framework    & FastAPI 0.115, Uvicorn, Pydantic 2.9, WebSockets 13 & REST API and live streaming \\
Frontend Framework   & React 18, Vite 5, Tailwind CSS 3, Recharts 2 & Live dashboard and analytics charts \\
Database             & SQLite via SQLAlchemy 2.0 and aiosqlite (PostgreSQL-ready) & Snapshots, events, report export \\
Testing / CI         & pytest 8, httpx; GitHub Actions & 119 automated tests; build and Docker smoke test \\
Packaging            & Docker and Docker Compose & Two-container deployment \\
Hardware (optional)  & Raspberry Pi (GPIO) / ESP32 & Mirror the controller's signal on LEDs or relays \\
Version Control      & Git + GitHub & Collaboration and backup \\
IDE                  & VS Code & Development \\
\bottomrule
\end{tabular}
\end{table}

\section{Data Collection and Analysis}
No real images or field data are used. Traffic is generated by the simulator with seeded random arrivals, and the camera frames and their ground-truth boxes are both rendered from the same simulator state, so annotation is automatic, exact and involves no manual labelling. Nothing is trained: the cascade is pre-trained, the controller is rule-based, and the detector and tracker parameters were fixed during development in unseeded runs, so there is no training split. Three kinds of seeds are kept apart: seed 1000 for tuning (the hold zone), seeds 101--105 for capacity measurement, and seeds 1--10 for all reported results (seeds 1--4 for the vision evaluation). In total @runs@ simulation runs (@hours@ simulated hours) were made.

Three demand levels below capacity were simulated: $\lambda = 0.08$, $0.12$ and $0.18$~veh/s per approach (1152, 1728 and 2592~veh/h offered to the junction). For each level and controller, ten seeds were run for 1800~s with a 50~ms step. The first 60~s are a warm-up, and delay statistics use the vehicles entering between 60~s and 1650~s, all of which left the network before the end of their run. For the above-capacity experiments the capacity of each controller was first measured by flooding every approach (1.5 arrivals/s; five seeds); demand was then set to 0.6, 0.8, 0.9, 1.0, 1.2 and 1.5 times the measured fixed-time capacity, with ten paired seeds per level. Preemption is enabled for all controllers unless stated.

\section{Evaluation Metrics}
The following metrics are used to evaluate the proposed system:
\begin{itemize}
  \item \textbf{Stopped delay:} the time a vehicle spends upstream of the stop line below 0.5~m/s. Because vehicles enter at rest it includes a start-up component of 0.15--0.55~s that is the same for all controllers.
  \item \textbf{Delay including waiting vehicles:} delay accrued by every vehicle, counting those still waiting to enter or at the stop line at the end of a run with the delay so far, so above capacity it is a lower bound.
  \item \textbf{Throughput and capacity:} vehicles served per hour after the warm-up; capacity is the throughput with every approach flooded.
  \item \textbf{Queue growth and spillback:} growth rate of the number of waiting vehicles (veh/min), and the share of approach-time (or approach-minutes) in which the queue reaches the start of the link; time for the queue to return to its pre-peak level after the peak.
  \item \textbf{Signal safety:} number of conflicting greens, green-to-red transitions without yellow, yellows shorter than 3~s and all-red intervals shorter than 1~s before a conflicting green, checked at every step of every run.
  \item \textbf{Detection and tracking:} precision and recall (a detection is correct when its centre lies inside a ground-truth box enlarged by 4~px), tracking coverage, ID switches per 100 vehicles, and tracked-speed mean absolute error.
  \item \textbf{Kinematic validity:} saturation headway and flow per lane, and start-up lost time, against the Highway Capacity Manual.
  \item \textbf{Statistical comparison:} 95\% confidence intervals and paired $t$-tests over the seeds (Mann--Whitney $U$ test for emergency-vehicle delay).
\end{itemize}
"""

CH4 = r"""%% Chapter4_Implementation.tex
\chapter{Implementation}
\label{chap:impl}

\section{System Architecture Overview}
The implementation is a layered, simulation-first system (about six thousand lines of Python plus a React front end), built milestone by milestone. A headless simulation engine advances the junction in 50~ms steps (20~Hz). In each step the active controller first sets the light of every approach, and then all vehicles move. The decision engine scores each approach from the current vehicle states and decides when a green ends; the emergency-preemption wrapper overrides it when an emergency vehicle approaches. A vision pipeline renders a virtual camera frame per approach at 2~Hz and passes it to the detector and tracker; its results are shown on the dashboard and compared with ground truth, but control decisions use the simulator's vehicle states, which corresponds to ideal detection. A FastAPI backend runs the simulation, streams the junction state over WebSockets at 10~Hz, and stores snapshots and signal events; a React dashboard draws the junction to scale; and an optional driver mirrors the signal on real lights (Figure~\ref{fig:architecture}).

\section{Module-wise Description}

\subsection{Module 1: Simulation Engine}
\textbf{Package:} \texttt{simulation/}. It contains the vehicle, lane, road, traffic-light and intersection entities, the engine loop, and the controller interface. Vehicles of seven classes (Table~\ref{tab:vehicles}) follow the Gipps-type safe-speed rule~\eqref{eq:safe} with an optional driver reaction time. The \texttt{SignalControllerBase} strategy interface (an \texttt{update} per time step and a phase name) is the one seam that lets the fixed-timer, adaptive, comparison and preemption controllers plug in without any change to the engine, the backend or the front end. Optional behaviours used by the experiments, all off by default, are the entry queue, entry at the highest safe speed, the reaction time, a time-varying demand profile and a sensor model. A \texttt{SignalAudit} checks every step for conflicting greens and shortened change intervals.

\subsection{Module 2: Decision Engine}
\textbf{Package:} \texttt{decision\_engine/}. \texttt{density.py} implements the class-weighted, queue-aware score of Eq.~\eqref{eq:density}. \texttt{adaptive\_controller.py} implements the bounded green extension of Eq.~\eqref{eq:green} and, with \texttt{hold\_while\_discharging}, the discharge hold of Eq.~\eqref{eq:hold}. \texttt{baselines.py} and \texttt{webster.py} hold the four comparison controllers, which reuse the adaptive controller's phase sequence and change intervals and replace only the single decision of whether a green may end. \texttt{emergency\_preemption.py} wraps any phase-based controller with the entry, priority-green and release states of Figure~\ref{fig:preemption}. \texttt{sensing.py} wraps a controller so that it sees the junction through a sensor model (a camera's field of view, a refresh rate, missed detections, no vehicle classes and phantom detections) while emergency preemption still reads the true flags.

\subsection{Module 3: Vision Pipeline}
\textbf{Package:} \texttt{vision/}. \texttt{camera.py} renders a virtual camera frame of the 60~m before each stop line; \texttt{detector.py} is the Haar-cascade vehicle detector; \texttt{tracker.py} is the ByteTrack-style tracker with a constant-velocity Kalman filter and Hungarian assignment; and \texttt{pipeline.py} ties them together and compares detections and tracks with ground truth. Detection takes about 137~ms per frame on an Intel Core i5-12450H laptop CPU in a single process, whereas a control decision takes about 0.01~ms.

\subsection{Module 4: Backend and Analytics}
\textbf{Packages:} \texttt{backend/app/}, \texttt{analytics/}. A FastAPI application runs the simulation, vision and analytics tasks, and exposes REST endpoints and WebSocket channels (Table~\ref{tab:api}). The analytics collector samples queue, delay, throughput and congestion level at 1~Hz, raises a high-traffic alert when an approach stays at high density for 3~s, and exports reports as CSV or JSON. A comparison runner executes a second simulation with the same random seed under another controller, so the dashboard can show fixed and adaptive control side by side.

\begin{table}[H]
\centering
\caption{Backend interfaces}
\label{tab:api}
\small
\begin{tabular}{@{}p{5.2cm}p{9.5cm}@{}}
\toprule
\textbf{Endpoint} & \textbf{Purpose} \\
\midrule
GET /api/health & Liveness check used by the Docker health check \\
GET /api/intersection/state & Current junction state (vehicles, lights, phase) \\
GET /api/vision/latest & Latest detections and tracks per approach \\
GET /api/analytics/history/\{road\} & Time series for one approach \\
GET /api/analytics/summary & Aggregate queue, delay, throughput and congestion \\
GET /api/reports/export & Report export as CSV or JSON \\
GET /api/comparison/latest & Fixed-versus-adaptive comparison metrics \\
GET /api/explain & Plain-language explanation of each displayed quantity \\
GET /api/signals/status & Signal state polled by the hardware driver \\
WS /ws/simulation, /ws/simulation/shadow & Live junction state; second simulation for comparison \\
WS /ws/vision, /ws/analytics, /ws/comparison & Live detections, analytics and comparison data \\
\bottomrule
\end{tabular}
\end{table}

\subsection{Module 5: Dashboard and Hardware Bridge}
\textbf{Directories:} \texttt{frontend/}, \texttt{hardware/}. The React dashboard (Section~\ref{sec:ui}) consumes the WebSocket channels. The hardware bridge is a pair of drivers, a Python driver for a Raspberry Pi and an Arduino/C++ sketch for an ESP32, that poll \texttt{GET /api/signals/status} at 5~Hz and drive 12 LEDs (red, yellow and green for each of four approaches, each through a 220~$\Omega$ resistor); for larger lamps an opto-isolated relay module is to be used. Nothing in the simulation, decision engine or backend changes, since the driver is a client. The bridge has not yet been built and tested on a physical board.

\section{Database / Data Model}
Persistence uses SQLAlchemy 2.0 with SQLite by default (PostgreSQL-ready). A snapshot split into two tables avoids repeating each of the four roads' columns in one wide table and matches the per-road query shape of the analytics collector. Table~\ref{tab:schema} lists the four tables.

\begin{table}[H]
\centering
\caption{Database tables}
\label{tab:schema}
\small
\begin{tabular}{@{}p{3.3cm}p{11.4cm}@{}}
\toprule
\textbf{Table} & \textbf{Columns} \\
\midrule
simulation\_runs & id, started\_at, ended\_at, controller\_type \\
snapshots & id, run\_id (FK), sim\_time, captured\_at \\
road\_snapshots & id, snapshot\_id (FK), road\_name, queue\_length, vehicle\_count, density\_score, light\_state, has\_emergency\_vehicle, total\_exited, total\_wait\_time\_s \\
signal\_events & id, run\_id (FK), sim\_time, road\_name, event\_type, phase\_name, details (JSON), created\_at \\
\bottomrule
\end{tabular}
\end{table}

A snapshot is stored every 10~s of simulated time, and signal events (phase changes and preemption states) are recorded as they occur. In the Docker deployment the SQLite file lives in a named volume, so history survives a restart.

\section{Key Algorithms}
The core algorithms are the density score, the green-end decision with discharge hold, and the preemption state machine. In pseudocode, the green-end decision evaluated at every step is:

\begin{lstlisting}[language=Python, caption={Green-end decision with discharge hold}]
def green_may_end(t_g, D_A, D_W, near_stop_line):
    if t_g >= G_MAX:                      # 45 s: hard cap
        return True
    if t_g < G_MIN:                       # 8 s: minimum green
        return False
    if HOLD and near_stop_line:           # a served vehicle within z = 10 m
        return False                      # queue still discharging: keep green
    return D_A <= THETA * D_W             # theta = 1.1
\end{lstlisting}

The preemption wrapper moves through the states \emph{inner controller}, \emph{entry yellow}, \emph{all-red clearing}, \emph{priority green}, \emph{release yellow} and \emph{release all-red}, so every path from one direction's green to the other's passes through a full yellow and all-red interval (Figure~\ref{fig:preemption}). The per-step safety audit checks this property in every run. Appendix~\ref{app:snapshots} lists the source of the main functions.

\section{User Interface}
\label{sec:ui}
The React dashboard draws the junction to scale on an HTML5 canvas from the streamed JSON state (vehicle positions, speeds and light states). Its components are: the intersection canvas; signal-status and per-road statistics cards with the density score and congestion level; a camera-feed grid with detection and tracking overlays; a traffic-alert banner; an analytics dashboard with historical graphs and report export; a comparison view that runs fixed and adaptive control on the same seed and shows the savings; and a ``how it works'' page and explain panel that describe each displayed quantity.

\section{Development and Deployment}
\begin{itemize}
  \item \textbf{Operating System:} Windows 11 for development; Ubuntu in the continuous-integration runners and Docker containers.
  \item \textbf{Key Libraries:} Python 3.12; FastAPI 0.115.0, Uvicorn 0.30.6, Pydantic 2.9.2, SQLAlchemy 2.0.35, aiosqlite 0.20.0, NumPy 2.1.2, SciPy 1.14.1, OpenCV (headless) 4.10.0.84, pytest 8.3.3; React 18.3, Vite 5.4, Tailwind CSS 3.4, Recharts 2.12.
  \item \textbf{Deployment:} \texttt{docker compose up --build} starts two containers, the backend (port 8000, with a health check) and the dashboard behind nginx (port 8080); the SQLite file persists in a named volume. A GitHub Actions workflow runs the 119-test backend suite, the front-end build and a Docker build with smoke test on every push. The optional hardware drivers run on a Raspberry Pi or ESP32.
\end{itemize}
"""

CH5 = r"""%% Chapter5_ResultsDiscussion.tex
\chapter{Results and Discussion}
\label{chap:results}

\section{Experimental Setup}
All experiments ran on the simulator described in Chapter~\ref{chap:meth} on an Intel Core i5-12450H laptop, using the scripts in the \texttt{scripts/} folder of the repository; every table can be regenerated from them. Each controller and demand level was run for ten paired seeds of 1800~s; capacity used five seeds; seed 1000 was used for tuning, 101--105 for capacity and 1--10 for the reported results. In total @runs@ runs (@hours@ simulated hours) were made. Delay is the stopped delay defined in Chapter~\ref{chap:meth}, with 95\% confidence intervals and paired $t$-tests.

\section{Results}

\subsection{Signal Safety Audit}
Every step of every run was checked for conflicting greens, green-to-red transitions without yellow, yellows shorter than 3~s and all-red intervals shorter than 1~s before a conflicting green. Across all @runs@ runs, covering all seven controllers and @preempt@ preemption events in the main runs alone, \textbf{none of these violations occurred}. An earlier version of the preemption layer returned control to the inner controller without a release interval; this audit exposed the resulting skipped yellows, which led to the release states of Figure~\ref{fig:preemption}.

\subsection{Experiment 1: Comparison Below Capacity}
Table~\ref{tab:below} compares all controllers at the three demand levels. The proposed adaptive controller reduced mean stopped delay by @redu_ad@ relative to the 20~s fixed plan, with lower delay in all ten seeds at every level ($p<0.001$), and the 95th-percentile delay fell by @p95@. However, the Webster plan, actuated control and max-pressure control achieved the same or slightly lower delay (@redu_web@, @redu_act@ and @redu_mp@ below the fixed plan); relative to the adaptive controller their delay differed by @others_vs_ad@. Below capacity, therefore, most of the gain comes from replacing an untuned 20~s plan with shorter, demand-responsive greens (mean adaptive green @green_ad_med@~s at medium demand), which any of these strategies provides. Three-level density control was worse than the fixed plan at medium and high demand (@dl_med@ and @dl_high@), because its greens of 20--30~s for medium and high density outlast the queue. The discharge hold left delay essentially unchanged at these levels (@hold_vs_ad@ relative to the adaptive controller). Throughput changed by at most @thru_max@ because all three levels are far below capacity.

@TBL_t2@

\subsection{Experiment 2: Capacity and Operation Above Capacity}
\label{sec:cap}
The three demand levels of Table~\ref{tab:below} are only @lo_pct@--@hi_pct@\% of the junction's measured fixed-time capacity (@fixed_cap@~veh/h), so they cannot show congestion. Table~\ref{tab:capacity} gives the capacity of each controller; these runs and the steady sweep use preemption off, because emergency vehicles make up 1\% of arrivals and at these demands trigger a preemption every 15--30~s, which would otherwise dominate the timing of every controller.

@TBL_cap@

The proposed controller lost @cap_loss@ of capacity relative to fixed timing ($p$ @cap_ad_p@): with both directions saturated its greens fell to the 8~s minimum (mean @green_ad@~s), as explained in Section~\ref{sec:hold}. With the discharge hold the mean saturated green rose to @green_hold@~s and capacity to @cap_hold@ relative to fixed timing. Max-pressure control suffered the same loss as the original rule (@cap_mp@), since moving vehicles also leave its pressure count as the queue discharges, whereas actuated control (@cap_act@) and the Webster plan (@cap_web@), which runs the maximum green above capacity, did not.

Demand was then swept from 0.6 to 1.5 times the fixed-time capacity, with blocked arrivals kept in an entry queue so that unserved demand is measured (Tables~\ref{tab:sweep}--\ref{tab:queue}, Figure~\ref{fig:above}). The original adaptive controller was better than fixed timing only at 0.6$\times$ capacity and worse from 0.8$\times$ on: at capacity its delay was @sw_cap_ad@~s against @sw_cap_fx@~s for the fixed plan, its queue grew by @qg_ad@ vehicles per minute, and queues reached the start of the link during @sb_ad@\% of approach-time. With the discharge hold, delay was below fixed timing at every level (@hold_delay_list@ from 0.6$\times$ to 1.5$\times$; the difference at 1.0$\times$ was not significant, $p$ = @hold_cap_p@) and throughput above capacity rose by @thr_hi@ and @thr_15@ at 1.2$\times$ and 1.5$\times$. Among the comparison strategies, actuated control behaved similarly to the hold controller (@sw_cap_act@~s at capacity, @sw_hi_act@~s at 1.2$\times$, against @sw_cap_hold@~s and @sw_hi_hold@~s), and max-pressure control degraded like the original rule. With preemption enabled the same pattern held with smaller margins (capacity @on_ad@ for the original rule and @on_hold@ with the hold), because preemption also cuts the hold's long greens.

@TBL_sweep@
@TBL_thru@
@TBL_queue@
@FIG_ABOVE@

\subsection{Experiment 3: Sixty-Minute Peak Period}
Steady demand shows capacity but not how a controller manages a congestion episode. In a further 60-minute experiment, demand rose from 0.6 to 1.2 times the fixed-time capacity (ramping over 10--15~min), stayed there for 15~min and fell back to 0.6 by 35~min (Figure~\ref{fig:peak}; preemption off, ten paired seeds; the Webster plan timed for the average demand). The queue, including vehicles waiting to enter, peaked at @pk_fx@ vehicles under fixed timing, @pk_hold@ with the discharge hold, @pk_act@ with actuated control and @pk_ad@ with the original adaptive rule. After the peak, the queue returned to its pre-peak level in @rec_fx@ under fixed timing and @rec_hold@ with the hold, whereas the original rule @rec_ad@ and max-pressure control @rec_mp@. Approach entries were blocked for @sp_fx@ approach-minutes under fixed timing, @sp_hold@ with the hold and @sp_ad@ with the original rule. During the peak the hold served @pt_hold@~veh/h, against @pt_fx@ for fixed timing and @pt_ad@ for the original rule. Relative to fixed timing, total delay changed by @td_hold@ with the hold, @td_act@ with actuated control and @td_ad@ with the original rule. Managing a congestion episode therefore depends above all on not shortening greens while queues are saturated.

@TBL_peak@
@FIG_PEAK@

\subsection{Experiment 4: Emergency Preemption}
Emergency vehicles made up 1\% of arrivals and triggered @pre_rate@ preemptions per hour under adaptive control (Table~\ref{tab:preemption}). Preemption reduced their mean stopped delay to the start-up component of the metric under every controller (at medium demand from @ev_fx_off@~s to @ev_fx_on@~s under fixed timing and from @ev_ad_off@~s to @ev_ad_on@~s under adaptive control). The cost to other traffic depends on the controller: at medium demand it was @oth_fx@ under fixed timing, but @oth_ad@ under adaptive control and @oth_hold@ with the hold, because each preemption discards the density-responsive timing and restarts the plan at a fixed phase. Emergency vehicles are far more frequent here than in normal traffic, so the aggregate cost at a real junction would be expected to be smaller.

@TBL_pre@

\subsection{Experiment 5: Ablation}
\label{sec:ablation}
Table~\ref{tab:ablation} changes one part of the controller at a time, on the same paired seeds. Counting vehicles without weights or multipliers raised delay by @abl_un_m@ and @abl_un_h@ at medium and high demand. Removing the parts separately shows where this comes from: without the queued/moving distinction delay rose by @abl_nq_m@ and @abl_nq_h@, whereas setting every class weight to 1 changed it by @abl_nc_m@ and @abl_nc_h@. The benefit of the score therefore comes from distinguishing queued from moving vehicles, not from the class weights, which did not help as set. Raising $\theta$ to 1.5 lowered delay slightly (@abl_th_m@ and @abl_th_h@) and $\theta = 1.0$ made no difference; the discharge hold, with any zone length, did not change delay below capacity, where its benefit is not needed.

@TBL_abl@

\subsection{Experiment 6: Vision Pipeline Accuracy and Failure Cases}
The vision pipeline was evaluated on seeds 1--4 (@frames@ frames, @gt@ vehicle instances in view). On these synthetic frames the generic cascade performed poorly: precision was @prec@\% and recall @rec@\% (Table~\ref{tab:detector}). The failure cases are systematic. @persist@\% of the false positives recur at the same spot in at least 10\% of a camera's frames, i.e.\ the cascade fires on fixed background texture rather than on vehicles. Recall varies by class (@class_recall@) and by distance from the stop line (@dist_recall@); recall is lowest near the stop line, where queued vehicles stand close together. Without upscaling, or without histogram equalization, the cascade found essentially nothing. A 2$\times$ instead of 3$\times$ upscale raised precision to @prec2x@\% but cut recall to @rec2x@\%, so no setting of this generic cascade gives both.

@TBL_det@

Tracking was evaluated on the default detector's output (Table~\ref{tab:tracking}). Only @cover@\% of the vehicle instances in view carried a confirmed track, and @confirmed@\% of the vehicles were confirmed at least once. For confirmed tracks on real vehicles, the mean absolute error of the tracked speed was @speed_mae@~m/s over @speed_n@ estimates. This is not a good result: the vehicles concerned were moving at only @speed_true@~m/s on average, because tracks are confirmed almost only on nearly stationary, queued vehicles, so the error is as large as the speed itself and the pipeline provides no usable kinematics for moving traffic. Dropping the low-confidence second matching stage or the motion model changed coverage little, because the limiting factor is the detector's recall, not the association. These results are why the evaluated controllers read vehicle states from the simulator: a class-aware detector trained on the target imagery is needed before detections can drive control, and accuracy on real footage is unknown.

@TBL_trk@

\subsection{Experiment 7: Validation of the Simulated Kinematics}
\label{sec:kin}
To check the simulator's kinematics against external values, queue discharge was measured as at a real junction: the time between successive queued vehicles crossing the stop line after the green starts, in saturated fixed-time runs (five seeds). The Highway Capacity Manual's base values are 1900 passenger cars per hour per lane (a 1.89~s headway) and a start-up lost time of about 2~s~\cite{ref24}. The model used for the main results discharges cars every @hw0@~s (@sf0@~veh/h/lane; Table~\ref{tab:kinematics}): without a reaction time a follower may trail by only the 2~m standstill gap at any speed. Adding a driver reaction time $\tau$ to the safe speed, as in Krau{\ss}'s model~\cite{ref25}, and setting $\tau = 1.6$~s gives @hw1@~s (@sf1@~veh/h/lane) for cars, within @sf1_err@\% of the reference. The calibrated model still has no extra delay when a queue starts to move, so its start-up lost time (@sul1@~s) is lower than in the field.

@TBL_kin@

All comparisons were then repeated with the calibrated model ($\tau = 1.6$~s; the Webster plan recomputed with the calibrated saturation flow of 3600~veh/h per approach). Table~\ref{tab:calibrated} summarizes them. Below capacity, the reductions relative to the fixed plan were @redu_cal_ad@ for the adaptive controller and @redu_cal_web@, @redu_cal_act@ and @redu_cal_mp@ for the Webster plan, actuated and max-pressure control. The calibrated capacity of the fixed plan was @cal_fixed_cap@~veh/h; relative to it, the original adaptive rule reached @cal_ad@ and the Webster plan @cal_web@. The discharge hold, with the 10~m zone chosen for the default model, reached only @cal_hold10@ (mean saturated green @cal_hold10_green@~s): with a reaction time, vehicles leaving a queue spread out to gaps of about 20~m at speed, so a 10~m zone empties between them and the green gaps out while the queue is still discharging. The zone is therefore a kinematics-dependent parameter, as the passage time of a real actuated controller is set for local conditions. Re-tuned for the calibrated model on the tuning seed (@zone@~m), the discharge hold reached @zone_hold@ capacity relative to fixed timing and actuated control @zone_act@, against @zone_web@ for the Webster plan.

@TBL_cal@

\subsection{Experiment 8: Imperfect Sensing}
All results so far assume that the controller knows every vehicle's position, speed and class. To measure how much this matters, the vehicle-reading controllers were run behind a sensor model that reports only what a camera would: vehicles within 60~m of the stop line, refreshed at 2~Hz, without classes (as a single cascade), with each vehicle detected independently with a given recall, and optionally with phantom detections at fixed spots, like the cascade's static false positives. The last profile uses the measured pipeline of Experiment 6. Emergency preemption still reads the true emergency flags; ten paired seeds per cell. Tables~\ref{tab:sensing-med} and~\ref{tab:sensing-cap} give the results at medium demand and at 0.9 times capacity. @sense_text@Closing the loop with the present detector would therefore harm traffic; a detector must at least suppress static false positives near the stop line, and its recall matters most near capacity.

@TBL_sn1@
@TBL_sn2@

\subsection{Experiment 9: Calibration of the Density Weights}
\label{sec:calib}
The class weights and multipliers of Eq.~\eqref{eq:density} were set by hand. To calibrate them from data, a random search over the score parameters of the discharge-hold controller (four class weights and the emergency-vehicle weight, log-uniform 0.25--4 and 1--10; the queued/moving ratio, 1--12; and $\theta$, 1.0--1.6; the car weight stays 1 because rule~\eqref{eq:green} compares ratios) evaluated @cb_cand@ candidates on tuning seeds @cb_t0@--@cb_t1@ at medium demand, high demand and 0.9 times capacity, minimizing delay relative to the hand-set weights. The best candidate (motorcycle @cb_m@, auto-rickshaw @cb_a@, bus @cb_b@, truck @cb_t@, emergency @cb_e@, queued/moving ratio @cb_q@, $\theta$ = @cb_th@), the hand-set weights and a plain vehicle count were then compared on the held-out seeds 1--10 (Table~\ref{tab:calibration}). @calib_text@The plain count remained clearly worse, confirming the ablation. The calibrated parameters are fitted to this simulator's traffic and must be re-fitted against field data before deployment; the search is a simple, reproducible way to do so, not a learned controller.

@TBL_cb@

\section{Discussion}
Two results qualify the usual claim that density-based control beats fixed timing. Below capacity, the gain over an untuned 20~s plan is real but not specific to density scoring: a Webster plan tuned to the demand, actuated control and max-pressure control achieve the same. Near capacity, density-only switching is worse than fixed timing, because it ends greens while the served queue is still discharging. With the discharge hold, the proposed controller matches the best strategies below capacity and comes close to the highest capacity measured (the Webster plan's, @cap_web@), while keeping the properties that motivated it: its decisions follow a rule that can be stated in one line, its red time is bounded in closed form, and its safety is audited at every step. Its results are, however, almost identical to plain actuated control, which uses no density score at all: in this setting the gap-out test, not the score, does most of the work. The score's remaining role is to decide when a cleared green should hand over, where the ablation shows that the queued/moving distinction matters. Emergency priority and adaptive control interact: resuming after preemption with the higher-scoring direction, rather than always the held one, is a direct improvement to test.

The research questions of Section~\ref{sec:contrib} are answered as follows: variable greens keep safe change intervals (no violation in @runs@ runs); preemption serves emergency vehicles without delay but costs other traffic more under adaptive control than under fixed timing; near and above capacity the original rule fails and the hold corrects it; and a large part of the gain below capacity comes from replacing an untuned plan, not from the density score.

\section{Comparison with Existing Work}
Table~\ref{tab:comparison} compares the proposed controller with re-implementations of the strategies used by existing work, which share its phase sequence, change intervals and green limits. The original papers could not be compared directly, since they use different simulators, demands and metrics.

@TBL_cmp@

\section{Limitations}
\begin{itemize}
  \item \textbf{Simulation only.} The model has no turning movements, lane changes, pedestrians or driver variability and has not been calibrated against field data, so absolute delays are not field predictions.
  \item \textbf{Kinematics.} The model behind the main results has no driver reaction time, so its queues discharge much faster than real ones. A reaction time of 1.6~s matches the field saturation headway, but the calibrated model still lacks start-up delay, so its start-up lost time is too low; with real start-up lost time, short greens would cost more, so the original rule's capacity loss is if anything understated. The gap-out zone of the discharge hold must also suit the local vehicle spacing: 10~m for the default model, @zone@~m for the calibrated one.
  \item \textbf{Arrival model.} Arrivals follow deterministic headways at a rate redrawn every 15~s, not a Poisson process, and emergency vehicles are far more frequent than in real traffic.
  \item \textbf{Comparison controllers.} The baselines are re-implementations of the published strategies with ideal sensing, not the original systems; the Webster plan is given the true mean demand of each run.
  \item \textbf{Sensing.} The main results use exact vehicle states, and emergency vehicles are detected perfectly. The controllers need a detector far better than the present Haar pipeline, in particular one without static false positives near the stop line. The vision pipeline was tested only on synthetic frames; real footage with lighting changes, occlusion and weather is harder.
  \item \textbf{Parameters and hardware.} The calibrated score parameters are fitted to this simulator, not to field data; the congestion thresholds used for display were set by hand. A planned Raspberry Pi 4 deployment, with one camera per approach and relay-driven signal heads, is estimated at roughly INR 6,000--8,000 in components, and its detection time at 5--10 times slower than the laptop; these are estimates and must be verified on actual hardware.
\end{itemize}
"""

CH6 = r"""%% Chapter6_SocietalImpact.tex
\chapter{Societal Impact and SDG Alignment}
\label{chap:societal}

\section{Primary SDG Relevance}
This project directly addresses \textbf{SDG 11: Sustainable Cities and Communities}, specifically Target 11.2, which aims to provide access to safe, affordable, accessible and sustainable transport systems for all, and, through reduced congestion, Target 11.6 on the adverse environmental impact of cities.

The project contributes to this goal by showing, in a reproducible simulation, how a low-cost density-aware signal controller behaves: below capacity it shortens delay by @redu_ad@ relative to a 20~s fixed plan, and above capacity its discharge-hold rule avoids the capacity loss of naive density switching and keeps queues and spillback below those of fixed timing. It also gives emergency vehicles priority while keeping full yellow and all-red intervals, and it identifies honestly where a simple detector would make matters worse. These are simulation results; the real-world benefit depends on field validation.

\section{Secondary SDG Linkages}
Beyond the primary SDG, this project indirectly contributes to:
\begin{itemize}
  \item \textbf{SDG 3 (Good Health and Well-being), Target 3.6:} fewer road injuries is supported by a controller that never shortens change intervals (no violation in @runs@ audited runs) and by emergency-vehicle preemption that reduces ambulance delay at the junction, which can shorten response times.
  \item \textbf{SDG 9 (Industry, Innovation and Infrastructure), Target 9.1:} the system is a low-cost, open-source approach to upgrading existing infrastructure: the optional hardware bridge costs an estimated INR 6,000--8,000 in components (an estimate, not yet built).
  \item \textbf{SDG 13 (Climate Action):} shorter queues and fewer stops reduce idling time and therefore fuel use and emissions. The project does not measure emissions; this is an expected, unquantified effect.
\end{itemize}

\section{Stakeholder Impact Analysis}

\begin{table}[H]
\centering
\caption{Stakeholder Impact Matrix}
\label{tab:stakeholders}
\small
\begin{tabular}{@{}p{4cm}p{2.5cm}p{8cm}@{}}
\toprule
\textbf{Stakeholder Group} & \textbf{Type} & \textbf{Nature of Impact} \\
\midrule
Commuters and drivers (cars, motorcycles, auto-rickshaws, buses, trucks) & Primary & Shorter waiting at junctions; fewer stops \\
Emergency services (ambulance, fire) & Primary & Faster, safe passage through junctions through preemption \\
Municipal and traffic authorities & Secondary & Low-cost, transparent controller with bounded red time and auditable safety; reproducible evaluation method \\
Researchers and students & Secondary & Open-source simulator, baselines and experiment scripts that regenerate every table \\
Residents and the environment & Tertiary & Less idling and congestion near junctions (expected, not measured) \\
\bottomrule
\end{tabular}
\end{table}

\section{Ethical Considerations}
\textbf{Data privacy.} The project uses no real camera footage and no personal data: frames are rendered from the simulator and the ground truth is exact. A real deployment with cameras must count vehicles without storing images or identifying plates or people, and comply with applicable privacy rules. \textbf{Bias.} The density weights are heuristic and favour larger vehicles and emergency vehicles by design; they were tested, and calibrated on held-out seeds, but only in simulation, and should be reviewed against local passenger-car-unit factors so that no road user class is systematically disadvantaged. \textbf{Safety.} Green times are bounded, change intervals are never shortened and the signal audit checks each step, but the controller has not been tested on a real junction and must not be deployed on live roads without independent safety validation and a fail-safe fallback to fixed timing. \textbf{Misuse.} Emergency preemption could be abused if the emergency flag can be spoofed; a real system needs authenticated vehicle-to-infrastructure messages and rate limits. \textbf{Honesty of claims.} Results are reported as simulation results, negative findings (the weak vision pipeline, the capacity loss of the original rule, the equal performance of simpler baselines) are stated plainly, and the use of an AI assistant in development and writing is disclosed.
"""

CH7 = r"""%% Chapter7_UHV.tex
\chapter{Universal Human Values and Harmony with Nature}
\label{chap:uhv}

\section{Impact on the Material Order}
The project uses little material resource: the system runs as software on an ordinary computer, and the optional signal bridge needs a Raspberry Pi or ESP32 board, twelve LEDs with resistors, and (for larger lamps) relay modules. Its purpose is to reduce a material waste, the fuel burnt by vehicles idling in queues at a signal, by shortening waiting time (@redu_ad@ lower delay below capacity in simulation, and shorter queues near capacity with the discharge hold). The effect on energy use is expected but was not measured. Because the controller is software that can run on an existing signal's hardware, little electronic waste is generated; the main lifecycle cost is the energy of the board and of any cameras.

\section{Impact on the Plant / Bio Order}
The project does not act on vegetation directly. Indirectly, shorter queues and less idling mean lower exhaust emissions near junctions, which benefits roadside plants and urban green space. This is an expected, unquantified benefit; the project does not model emissions.

\section{Impact on the Animal Order}
The project has no direct effect on animal habitats. Smoother traffic flow and less idling reduce local air pollution and noise from stop-and-go traffic, which benefits urban wildlife and domestic animals, and drivers who are not stopped for long are less likely to take risks near the junction. As above, these effects are indirect and were not measured.

\section{Impact on the Human Order}
The human benefits are the central aim. Commuters spend less time waiting; emergency vehicles cross the junction with priority (their stopped delay falls to the start-up component of the metric in every controller) while all other road users are protected by full yellow and all-red intervals that are never shortened (no violation in @runs@ audited runs); and the bounded red time of 50~s means that no approach is starved. The design is transparent: a one-line rule, not a black box, so that authorities and citizens can understand and question it. The project is offered as an open, reproducible resource that students and municipalities can reuse, supporting access to knowledge and fair treatment of all road-user classes. Its honest reporting of limitations supports trust: it states that the gain below capacity is matched by simpler strategies and that the present vision detector cannot yet be trusted to drive the signal.

\section{Overall Mutual Fulfilment}
The project aims at a win-win outcome across all four orders. For people, it shortens waiting, protects safety and gives emergency vehicles priority; for the material order it reduces fuel wasted in idling at little hardware cost; and for the plant and animal orders it lowers, indirectly, emissions and noise at junctions. These benefits reinforce one another rather than trade off: the same shorter queues serve commuters, emergency responders and the environment. The solution is synergistic with the well-being of the material, plant and animal orders and does not exploit them. Care is needed that efficiency does not override safety or fairness, which is why change intervals are protected, red time is bounded, and the claims of the report are limited to what the simulation shows.
"""

CH8 = r"""%% Chapter8_Conclusion.tex
\chapter{Conclusion and Future Scope}
\label{chap:conc}

\section{Summary}
This project addressed the problem that low-cost density-based signal controllers are rarely evaluated against strong baselines, near and above capacity, or for signal safety. The following was accomplished:
\begin{itemize}
  \item Designed and developed a complete simulation-first traffic management system: a microscopic simulator, a density-aware adaptive controller with a discharge hold, an emergency-preemption layer, a Haar-cascade and ByteTrack-style vision pipeline, a FastAPI backend with SQLite persistence, a React dashboard, a hardware bridge, Docker packaging and CI with 119 tests (Chapters~\ref{chap:meth} and~\ref{chap:impl}).
  \item Achieved a reduction of mean stopped delay below capacity of @redu_ad@ relative to a 20~s fixed plan, and with the discharge hold restored and exceeded the fixed plan's capacity (@cap_hold@), as shown in the results chapter (Chapter~\ref{chap:results}).
  \item Demonstrated alignment with SDG 11, with secondary links to SDG 3, 9 and 13 (Chapter~\ref{chap:societal}).
\end{itemize}

\section{Conclusions}
Based on the experimental results and analysis, the following conclusions are drawn:
\begin{enumerate}
  \item Conclusion 1: Below capacity, the density-based controller reduces delay by @redu_ad@ relative to a 20~s fixed plan, but a Webster-optimized plan, actuated control and max-pressure control do as well; most of the gain comes from replacing an untuned plan, not from the density score.
  \item Conclusion 2: Near capacity, density-only switching ended greens too early and lost @cap_loss@ of capacity. A discharge-hold rule restored it (@cap_hold@ relative to fixed timing), lowered delay from 0.6 to 1.5 times capacity (not significantly at 1.0$\times$) and kept queues and spillback below those of fixed timing in a 60-minute peak.
  \item Conclusion 3: The queued/moving distinction, not the class weights, accounts for the benefit of the density score; data-driven calibration gave only modest, condition-dependent gains.
  \item Conclusion 4: Signal safety held in every run (no conflicting green or shortened change interval in @runs@ runs). The findings hold with kinematics calibrated to field saturation headways once the hold's zone is re-tuned (@zone@~m).
  \item Conclusion 5: The present Haar-cascade detector (@prec@\% precision, @rec@\% recall on synthetic frames) is too weak to drive control: with it, every vehicle-reading controller would be worse than fixed timing near capacity.
\end{enumerate}

\section{Original Contributions}
\label{sec:contrib}
The original contributions of this project are:
\begin{enumerate}
  \item A class-weighted, queue-aware density score with a bounded green-extension controller that never shortens yellow or all-red intervals and guarantees a maximum red time, a discharge-hold extension that removes the capacity loss of density-only switching, and an emergency-preemption layer that wraps any phase-based controller and keeps full change intervals, with a per-step signal audit.
  \item An empirical evaluation demonstrating, on paired seeded runs, how the controller compares with four re-implemented strategies below, at and above capacity, in a peak period, under calibrated kinematics and under imperfect sensing, including an ablation and a held-out calibration of the score.
  \item A publicly available codebase at \url{https://github.com/shivam-G05/Smart-Traffic-Management}, in which every table can be regenerated by a script, and a revised research paper reporting the results.
\end{enumerate}

\section{Limitations}
Results are from simulation only: the model has no turning movements, lane changes, pedestrians or driver variability, and arrivals are not Poisson. The main kinematic model has no driver reaction time (a calibrated variant is also reported), the baselines are re-implementations with ideal sensing, the vision pipeline was tested only on synthetic frames and is too weak to drive control, and the hardware bridge has not been built and tested on a physical board. The limitations were managed by calibrating the kinematics against the Highway Capacity Manual, by repeating the comparisons under the calibrated model, by measuring the effect of imperfect sensing, and by labelling every estimate as an estimate.

\section{Future Scope}
\label{sec:future}
Future work can extend this project in the following directions:
\begin{itemize}
  \item \textbf{Short-term:} improve resumption after preemption (return to the higher-scoring direction); add Poisson arrivals and turning movements; train a class-aware detector that suppresses static false positives near the stop line.
  \item \textbf{Medium-term:} close the loop between detection and control with that detector on real footage; test the controller in an established simulator such as SUMO~\cite{ref22}; build and verify the Raspberry Pi/ESP32 prototype and its timing on actual hardware; calibrate the class weights against local passenger-car-unit factors and field data.
  \item \textbf{Long-term:} pilot at a real junction with independent safety validation; extend to coordinated multi-junction corridors; study reinforcement-learning controllers with the same safety audit; broader deployment with municipal authorities.
\end{itemize}
"""

# --------------------------------------------------------------------------- bibliography

BIB = r"""%% References.bib
%% Entries ref1--ref25 are the references of the research paper.

@article{ref1,
  author  = {Nsofwa, K. and Tembo, S.},
  title   = {Density based traffic control system},
  journal = {Int. J. Traffic Transp. Eng.},
  year    = {2025},
  volume  = {14},
  number  = {1},
  pages   = {1--8},
}

@techreport{ref2,
  author      = {Webster, F. V.},
  title       = {Traffic signal settings},
  institution = {Road Research Laboratory},
  address     = {London, U.K.},
  type        = {Road Res. Tech. Paper},
  number      = {39},
  year        = {1958},
}

@article{ref3,
  author  = {Sims, A. G. and Dobinson, K. W.},
  title   = {The {Sydney} coordinated adaptive traffic ({SCAT}) system philosophy and benefits},
  journal = {IEEE Trans. Veh. Technol.},
  year    = {1980},
  month   = may,
  volume  = {29},
  number  = {2},
  pages   = {130--137},
  doi     = {10.1109/TVT.1980.23833},
}

@article{ref4,
  author  = {Hunt, P. B. and Robertson, D. I. and Bretherton, R. D. and Royle, M. C.},
  title   = {The {SCOOT} on-line traffic signal optimisation technique},
  journal = {Traffic Eng. Control},
  year    = {1982},
  volume  = {23},
  number  = {4},
  pages   = {190--192},
}

@article{ref5,
  author  = {Pardeshi, K. and Bable, P. and Bhalerao, M. and Desai, M.},
  title   = {Adaptive traffic signal control system using density-based prioritization algorithm on {ESP} 32 platform},
  journal = {Int. J. Eng. Res. Technol.},
  year    = {2026},
  month   = may,
  volume  = {15},
  number  = {5},
  doi     = {10.5281/zenodo.20205923},
}

@article{ref6,
  author  = {Kamble, V. B. and Mundhe, O. N. and Walunjkar, C. M. and Kale, G. A.},
  title   = {{AI}-driven smart traffic management system},
  journal = {Int. J. Multidiscip. Sci. Manage.},
  year    = {2025},
  volume  = {2},
  number  = {2},
  pages   = {66--72},
}

@inproceedings{ref7,
  author    = {Redmon, J. and Divvala, S. and Girshick, R. and Farhadi, A.},
  title     = {You only look once: Unified, real-time object detection},
  booktitle = {Proc. IEEE Conf. Comput. Vis. Pattern Recognit. (CVPR)},
  address   = {Las Vegas, NV, USA},
  year      = {2016},
  pages     = {779--788},
  doi       = {10.1109/CVPR.2016.91},
}

@article{ref8,
  author  = {Hu, Z. and Lam, W. H. K. and Wong, S. C. and Chow, A. H. F. and Ma, W.},
  title   = {Turning traffic surveillance cameras into intelligent sensors for traffic density estimation},
  journal = {Complex Intell. Syst.},
  year    = {2023},
  month   = dec,
  volume  = {9},
  number  = {6},
  pages   = {7171--7195},
  doi     = {10.1007/s40747-023-01117-0},
}

@article{ref9,
  author  = {Patil, S. V. and Kureshi, S. and Gaikwad, A.},
  title   = {Vehicle density based traffic signal control system},
  journal = {Int. J. Novel Res. Develop.},
  year    = {2024},
  month   = may,
  volume  = {9},
  number  = {5},
  pages   = {g284--g288},
}

@inproceedings{ref10,
  author    = {Thomas, C. M. and Nair, A. B. and Varghese, A. E. and Kumar, A. B. and Seena, A. P.},
  title     = {Adaptive traffic signal control using real-time vehicle density},
  booktitle = {AIP Conf. Proc.},
  year      = {2025},
  volume    = {3260},
  pages     = {020031},
  doi       = {10.1063/5.0263715},
}

@article{ref11,
  author  = {Varaiya, P.},
  title   = {Max pressure control of a network of signalized intersections},
  journal = {Transp. Res. C, Emerg. Technol.},
  year    = {2013},
  month   = nov,
  volume  = {36},
  pages   = {177--195},
  doi     = {10.1016/j.trc.2013.08.014},
}

@article{ref12,
  author  = {Wei, H. and Zheng, G. and Gayah, V. and Li, Z.},
  title   = {Recent advances in reinforcement learning for traffic signal control},
  journal = {ACM SIGKDD Explor. Newsl.},
  year    = {2021},
  month   = jan,
  volume  = {22},
  number  = {2},
  pages   = {12--18},
  doi     = {10.1145/3447556.3447565},
}

@article{ref13,
  author  = {Alzamzami, O. and Alsaggaf, Z. and AlMalki, R. and Alghamdi, R. and Babour, A. and Al Khuzayem, L.},
  title   = {Passable: An intelligent traffic light system with integrated incident detection and vehicle alerting},
  journal = {Sensors},
  year    = {2025},
  month   = sep,
  volume  = {25},
  number  = {18},
  pages   = {5760},
  doi     = {10.3390/s25185760},
}

@inproceedings{ref14,
  author    = {Phakathi, T. G. and Sumbwanyambe, M. and Hlalele, T. S.},
  title     = {Designing intelligent traffic light system with the application of artificial intelligence},
  booktitle = {Proc. Int. Conf. Artif. Intell., Big Data, Comput. Data Commun. Syst.},
  year      = {2025},
  pages     = {1--9},
  doi       = {10.1145/3759023.3759090},
}

@article{ref15,
  author  = {Tolani, M. and others},
  title   = {Machine learning based adaptive traffic prediction and control using edge impulse platform},
  journal = {Sci. Rep.},
  year    = {2025},
  month   = may,
  volume  = {15},
  pages   = {17161},
  doi     = {10.1038/s41598-025-00762-4},
}

@inproceedings{ref16,
  author    = {Viola, P. and Jones, M.},
  title     = {Rapid object detection using a boosted cascade of simple features},
  booktitle = {Proc. IEEE Comput. Soc. Conf. Comput. Vis. Pattern Recognit. (CVPR)},
  address   = {Kauai, HI, USA},
  year      = {2001},
  pages     = {I-511--I-518},
  doi       = {10.1109/CVPR.2001.990517},
}

@incollection{ref17,
  author    = {Zhang, Y. and others},
  title     = {{ByteTrack}: Multi-object tracking by associating every detection box},
  booktitle = {Computer Vision -- ECCV 2022},
  publisher = {Springer},
  address   = {Cham, Switzerland},
  year      = {2022},
  pages     = {1--21},
  doi       = {10.1007/978-3-031-20047-2_1},
}

@article{ref18,
  author  = {Kalman, R. E.},
  title   = {A new approach to linear filtering and prediction problems},
  journal = {J. Basic Eng.},
  year    = {1960},
  month   = mar,
  volume  = {82},
  number  = {1},
  pages   = {35--45},
  doi     = {10.1115/1.3662552},
}

@article{ref19,
  author  = {Kuhn, H. W.},
  title   = {The {Hungarian} method for the assignment problem},
  journal = {Naval Res. Logist. Quart.},
  year    = {1955},
  month   = mar,
  volume  = {2},
  number  = {1--2},
  pages   = {83--97},
  doi     = {10.1002/nav.3800020109},
}

@article{ref20,
  author  = {Nellore, K. and Hancke, G. P.},
  title   = {Traffic management for emergency vehicle priority based on visual sensing},
  journal = {Sensors},
  year    = {2016},
  month   = nov,
  volume  = {16},
  number  = {11},
  pages   = {1892},
  doi     = {10.3390/s16111892},
}

@article{ref21,
  author  = {Gipps, P. G.},
  title   = {A behavioural car-following model for computer simulation},
  journal = {Transp. Res. B, Methodol.},
  year    = {1981},
  month   = apr,
  volume  = {15},
  number  = {2},
  pages   = {105--111},
  doi     = {10.1016/0191-2615(81)90037-0},
}

@inproceedings{ref22,
  author    = {Lopez, P. A. and others},
  title     = {Microscopic traffic simulation using {SUMO}},
  booktitle = {Proc. 21st Int. Conf. Intell. Transp. Syst. (ITSC)},
  address   = {Maui, HI, USA},
  year      = {2018},
  pages     = {2575--2582},
  doi       = {10.1109/ITSC.2018.8569938},
}

@techreport{ref23,
  author      = {Koonce, P. and others},
  title       = {Traffic signal timing manual},
  institution = {Federal Highway Administration},
  address     = {Washington, DC, USA},
  number      = {FHWA-HOP-08-024},
  year        = {2008},
}

@book{ref24,
  title     = {Highway Capacity Manual 2010},
  publisher = {Transportation Research Board},
  address   = {Washington, DC, USA},
  year      = {2010},
}

@phdthesis{ref25,
  author  = {Krau{\ss}, S.},
  title   = {Microscopic modeling of traffic flow: Investigation of collision free vehicle dynamics},
  school  = {Univ. of Cologne},
  address = {Cologne, Germany},
  year    = {1998},
}
"""

# --------------------------------------------------------------------------- appendices

APP_A = r"""%% appendices/AppendixA_UNAI_Certificate.tex
\chapter{SDG Compliance Certificate}
\label{app:unai}

\thispagestyle{empty}
\begin{center}
{\Large\textbf{Certificate of Compliance with United Nations\\[4pt]
Sustainable Development Goals}}
\end{center}

\vspace{0.3cm}

This is to certify that the project titled \textbf{\reporttitle} submitted by
the following final year students of the Bachelor of Technology in Information Technology at Ajay Kumar Garg Engineering College, Ghaziabad
has been reviewed and found to be in alignment with the UN Sustainable
Development Goals (SDGs) listed below. All efforts have been made to ensure
no other SDGs are compromised or negatively impacted.

\vspace{0.4cm}

% Replace \square with \checkmark for SDGs your project aligns with.
\begin{multicols}{2}
\noindent
\begin{tabbing}
\hspace{0.6cm}\=\hspace{4.2cm}\=\kill
\textbf{No. }\> \textbf{SDG Name}\>\textbf{$\surd$}\\[3pt]
1  \> No Poverty                     \> $\square$ \\[2pt]
2  \> Zero Hunger                    \> $\square$ \\[2pt]
3  \> Good Health \& Well-being      \> $\checkmark$ \\[2pt]
4  \> Quality Education              \> $\square$ \\[2pt]
5  \> Gender Equality                \> $\square$ \\[2pt]
6  \> Clean Water and Sanitation     \> $\square$ \\[2pt]
7  \> Affordable and Clean Energy    \> $\square$ \\[2pt]
8  \> Decent Work \& Economic Growth \> $\square$ \\[2pt]
9  \> Industry, Innovation \& Infra. \> $\checkmark$ \\[2pt]
\end{tabbing}

\columnbreak

\noindent
\begin{tabbing}
\hspace{0.6cm}\=\hspace{4.2cm}\=\kill
\textbf{No.}\>\textbf{SDG Name}\>\textbf{$\surd$}\\[3pt]
10 \> Reduced Inequalities           \> $\square$ \\[2pt]
11 \> Sustainable Cities \& Comm.    \> $\checkmark$ \\[2pt]
12 \> Responsible Consumption        \> $\square$ \\[2pt]
13 \> Climate Action                 \> $\checkmark$ \\[2pt]
14 \> Life Below Water               \> $\square$ \\[2pt]
15 \> Life on Land                   \> $\square$ \\[2pt]
16 \> Peace, Justice \& Institutions \> $\square$ \\[2pt]
17 \> Partnerships for the Goals     \> $\square$ \\[2pt]
\end{tabbing}
\end{multicols}

\vspace{0.5cm}

\noindent
\begin{tabular}{@{}p{7.5cm}p{6cm}@{}}
\textbf{Signatures of Students} & \textbf{Signature of Supervisor} \\[0.5cm]
@APPSIG@
Date: \submissiondate & Date: \submissiondate \\
\end{tabular}
"""


def src(path, kind, name, cls=None):
    """Source of a function/class from the repo, ASCII only (listings cannot print other glyphs)."""
    text = (ROOT / path).read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, kind) and node.name == name:
            seg = ast.get_source_segment(text, node)
            if node.col_offset:
                first, *rest = seg.split("\n")
                seg = "\n".join([first] + [l[node.col_offset:] if l.strip() else l for l in rest])
            return re.sub(r"[^\x00-\x7f]", "-", seg)
    raise KeyError(name)


def listing(caption, code):
    return "\\begin{lstlisting}[language=Python, caption={%s}]\n%s\n\\end{lstlisting}\n" % (caption, code)


APP_B = "\n".join([
    r"%% appendices/AppendixB_Code.tex",
    r"%% Project Snapshots and Description (code read from the repository by report/build_report.py)",
    r"\chapter{Project Snapshots and Description}", r"\label{app:snapshots}", "",
    r"\section{Module 1: Density Score (\texttt{decision\_engine/density.py})}",
    r"\textbf{Description:} The class-weighted, queue-aware density score of Eq.~\eqref{eq:density}: every vehicle contributes its class weight times a multiplier that is 1.5 if the vehicle is queued and 0.5 if it is moving. Default weights are in \texttt{DENSITY\_WEIGHTS} (car 1.0, motorcycle 0.5, auto-rickshaw 0.8, bus 3.0, truck 2.5, ambulance and fire truck 6.0).", "",
    listing("[Module 1] Lane density score", src("decision_engine/density.py", ast.FunctionDef, "lane_density_score")),
    r"\section{Module 2: Adaptive Controller with Discharge Hold (\texttt{decision\_engine/adaptive\_controller.py})}",
    r"\textbf{Description:} The green-end decision of Eqs.~\eqref{eq:green} and~\eqref{eq:hold}. A green never ends before the minimum or runs past the maximum; between them it may end only when the served direction no longer out-scores the waiting one by the threshold and, with the hold, has gapped out.", "",
    listing("[Module 2] Green-end decision", "\n\n".join(src("decision_engine/adaptive_controller.py", ast.FunctionDef, n)
                                                       for n in ("_should_end_phase", "_green_ready_to_end", "_still_discharging"))),
    r"\section{Module 3: Haar-Cascade Vehicle Detector (\texttt{vision/detector.py})}",
    r"\textbf{Description:} The detector applied to each virtual camera frame; it localizes vehicles but does not classify them.", "",
    listing("[Module 3] Detector", src("vision/detector.py", ast.FunctionDef, "detect")),
    r"\section{Module 4: Database Models (\texttt{database/models.py})}",
    r"\textbf{Description:} The two-table snapshot split (a snapshot and one row per road) used by the analytics collector, as in Table~\ref{tab:schema}.", "",
    listing("[Module 4] Snapshot tables", src("database/models.py", ast.ClassDef, "Snapshot") + "\n\n" + src("database/models.py", ast.ClassDef, "RoadSnapshot")),
    r"\vspace{0.5cm}", r"\noindent\textbf{Full Source Code Repository:}",
    r"\url{https://github.com/shivam-G05/Smart-Traffic-Management}", ""])

CV_TEMPLATE = r"""
%% ================================================================
%%  STUDENT @IDX@  (one full page)
%% ================================================================
\newpage
\thispagestyle{fancy}

\begin{center}
  {\Large\textbf{Curriculum Vitae}}
\end{center}

\vspace{0.3cm}

\noindent
\begin{minipage}[t]{0.72\textwidth}
  \begin{tabular}{@{}p{3.5cm}p{7cm}}
    \textbf{Full Name}      & @NAME@ \\[4pt]
    \textbf{Roll No.}       & XXXXXXXXXX \\[4pt]
    \textbf{Branch}         & Information Technology \\[4pt]
    \textbf{Batch}          & 2023 -- 2027 \\[4pt]
    \textbf{Date of Birth}  & DD Month YYYY \\[4pt]
    \textbf{Email}          & student@akgec.ac.in \\[4pt]
    \textbf{Mobile}         & +91-XXXXXXXXXX \\[4pt]
    \textbf{LinkedIn}       & linkedin.com/in/your-profile \\[4pt]
    \textbf{GitHub}         & github.com/your-username \\
  \end{tabular}
\end{minipage}
\hfill
\begin{minipage}[t]{0.24\textwidth}
  \centering
  \setlength{\fboxsep}{0pt}
  \fbox{\rule{3.5cm}{0pt}\rule{0pt}{4.5cm}}\\[2pt]
  {\small Passport Size Photo}
\end{minipage}

\vspace{0.5cm}\hrule\vspace{0.4cm}

\noindent\textbf{Educational Qualifications}
\vspace{0.2cm}

\begin{tabular}{@{}p{2.5cm}p{5cm}p{3cm}p{1.5cm}@{}}
\toprule
\textbf{Degree} & \textbf{Institution} & \textbf{Board/University} & \textbf{Year} \\
\midrule
B.Tech (IT)    & AKGEC, Ghaziabad       & AKTU Lucknow & 2027 \\
Class XII       & School Name            & Board Name   & 2023 \\
Class X         & School Name            & Board Name   & 2021 \\
\bottomrule
\end{tabular}

\vspace{0.4cm}\hrule\vspace{0.4cm}

\noindent\textbf{Technical Skills}
\vspace{0.2cm}

\begin{tabular}{@{}p{3.5cm}p{9cm}@{}}
\textbf{Languages}   & [to be filled by the student] \\[3pt]
\textbf{Web / UI}    & [to be filled by the student] \\[3pt]
\textbf{Databases}   & [to be filled by the student] \\[3pt]
\textbf{Tools}       & [to be filled by the student] \\[3pt]
\textbf{Others}      & [to be filled by the student] \\
\end{tabular}

\vspace{0.4cm}\hrule\vspace{0.4cm}

\noindent\textbf{Projects}
\vspace{0.2cm}

\noindent\textbf{1. \reporttitle} \hfill \textit{2023--2027}\\
Final year project: a simulation-first smart traffic management system with a density-aware adaptive signal controller, emergency-vehicle preemption, a vision pipeline and a live dashboard.

\noindent\textbf{2. [Project Title]} \hfill \textit{[Month Year]}\\
[Brief one-line description of another project.]

\vspace{0.4cm}\hrule\vspace{0.4cm}

\noindent\textbf{Internships / Work Experience}
\vspace{0.2cm}

\noindent\textbf{[Company / Organisation Name]} \hfill \textit{[Month Year -- Month Year]}\\
Role: [Intern / Role Title]\\
[Brief description of work done.]

\vspace{0.4cm}\hrule\vspace{0.4cm}

\noindent\textbf{Certifications and Achievements}
\begin{itemize}\setlength\itemsep{1pt}
  \item [Certification Name -- Issuing Body (Year)]
  \item [Achievement / Award (Year)]
\end{itemize}

\vspace{0.4cm}\hrule\vspace{0.4cm}

\noindent\textbf{Declaration}\\[3pt]
I hereby declare that all information furnished above is true to the best of
my knowledge.

\vspace{0.6cm}
\noindent Date: \submissiondate \hfill Signature: \underline{\hspace{4cm}}
"""

APP_C = ("%% appendices/AppendixC_CV.tex\n%% Student CVs --- one student per page\n"
         "\\chapter{Student Curriculum Vitae}\n\\label{app:cv}\n" +
         "".join(CV_TEMPLATE.replace("@IDX@", str(i + 1)).replace("@NAME@", s) for i, s in enumerate(STUDENTS)) + "\n")

# --------------------------------------------------------------------------- write

figs = {
    "FIG_ARCH": figure("fig1_architecture.png", "0.75", "Software architecture. Solid boxes form the control loop; dashed boxes form the vision pipeline, whose output is displayed and evaluated but not used for control in this study.", "fig:architecture"),
    "FIG_WORKFLOW": figure("fig2_workflow.png", "0.62", "Method workflow. (a) The per-step control pipeline. (b) The green-end decision; the test marked ``discharge hold'' is the extension added to the original controller.", "fig:workflow"),
    "FIG_PREEMPT": figure("fig3_preemption.png", "0.85", "Emergency preemption states. Every path from one direction's green to the other's passes through a full yellow and all-red interval.", "fig:preemption"),
    "FIG_ABOVE": figure("fig5_above_capacity.png", "0.7", "Delay (top, log scale) and throughput (bottom) against demand, preemption off. The dotted line marks the fixed-time capacity.", "fig:above"),
    "FIG_PEAK": figure("fig6_peak_queue.png", "0.85", "Queue including vehicles waiting to enter during a 60-minute peak period (mean of ten seeds, 2-minute moving average, preemption off). Shading: demand ramping (light) and at 1.2 times the fixed-time capacity (dark).", "fig:peak"),
}
vals.update(figs)

sig_rows = "\n".join(f"    {s} (Roll No.) & \\underline{{\\hspace{{4cm}}}} \\\\[0.5cm]" for s in STUDENTS)
cert_students = " \\quad\n".join(f"{s} (Roll No.)" for s in STUDENTS)
ack_students = " \\\\\n".join(STUDENTS)
right = ["", "\\textbf{\\mentor}", "\\dept", "\\college"]
app_sig = "".join(st + " \\dotfill & " + right[i] + " \\\\[0.4cm]\n" for i, st in enumerate(STUDENTS))

files = {
    "main.tex": MAIN.replace("@TITLE@", TITLE).replace("@STUDENTS@", stud_lines).replace("@MENTOR@", MENTOR),
    "frontmatter/Declaration.tex": DECLARATION.replace("@SIGROWS@", sig_rows),
    "frontmatter/Certificate.tex": CERTIFICATE.replace("@CERTSTUDENTS@", cert_students),
    "frontmatter/Acknowledgements.tex": ACK.replace("@ACKSTUDENTS@", ack_students),
    "frontmatter/Abstract.tex": fill(ABSTRACT, vals),
    "chapters/Chapter1_Introduction.tex": fill(CH1, vals),
    "chapters/Chapter2_LiteratureReview.tex": fill(CH2, vals),
    "chapters/Chapter3_Methodology.tex": fill(CH3.replace("@FIG_ARCH@", "@FIG_ARCH@"), vals),
    "chapters/Chapter4_Implementation.tex": fill(CH4, vals),
    "chapters/Chapter5_ResultsDiscussion.tex": fill(CH5, vals),
    "chapters/Chapter6_SocietalImpact.tex": fill(CH6, vals),
    "chapters/Chapter7_UHV.tex": fill(CH7, vals),
    "chapters/Chapter8_Conclusion.tex": fill(CH8, vals),
    "References.bib": BIB,
    "appendices/AppendixA_UNAI_Certificate.tex": APP_A.replace("@APPSIG@", app_sig),
    "appendices/AppendixB_Code.tex": APP_B,
    "appendices/AppendixC_CV.tex": APP_C,
}

if OUT.exists():
    shutil.rmtree(OUT)
for rel, text in files.items():
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")
(OUT / "figures").mkdir(exist_ok=True)
for f in ["fig1_architecture.png", "fig2_workflow.png", "fig3_preemption.png", "fig5_above_capacity.png", "fig6_peak_queue.png"]:
    shutil.copy(ROOT / "paper" / "figures" / f, OUT / "figures" / f)
print("wrote", len(files), "files to", OUT)

zpath = ROOT / "report" / "overleaf.zip"
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(OUT.rglob("*")):
        if f.is_file():
            z.write(f, f.relative_to(OUT).as_posix())
print("zip:", zpath, zpath.stat().st_size // 1024, "KB")
