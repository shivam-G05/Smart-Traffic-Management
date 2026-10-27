// Builds the revised manuscript (paper/out/Smart_Traffic_Control_revised.docx)
// from the text below and the numbers in paper/build/numbers.json
// (python paper/make_tables.py). Run from the repo root or paper/:
//   node paper/build_paper.js
const fs = require("fs");
const path = require("path");
const {
  AlignmentType, Document, Packer, Paragraph, Table, TableCell, TableRow, TextRun, WidthType, BorderStyle,
} = require("docx");
const I = require("./ieee");

const HERE = __dirname;
// NUMBERS / OUT_DIR override the inputs and output folder (used for test builds).
const N = JSON.parse(fs.readFileSync(process.env.NUMBERS || path.join(HERE, "build", "numbers.json"), "utf8"));
const OUT = path.join(process.env.OUT_DIR || path.join(HERE, "out"), "Smart_Traffic_Control_revised.docx");
const FIG = (name) => path.join(HERE, "figures", name);

const L = N.labels;
const T2 = N.table2_on;
const T2off = N.table2_off;
const O = N.over_off;
const Oon = N.over_on;
const S = N.safety;
const CTRL = ["fixed", "webster", "actuated", "max_pressure", "density_levels", "adaptive", "adaptive_hold"];
const LV = ["low", "medium", "high"];
const minus = (s) => String(s).replace(/-/g, "−");
const pct = (x) => minus(`${x > 0 ? "+" : ""}${x.toFixed(1)}%`);
const abspct = (x) => `${Math.abs(x).toFixed(1)}%`;
const d = (c, lv) => T2[c][lv].mean_delay_s;
const range = (vals) => {
  const a = Math.min(...vals), b = Math.max(...vals);
  return a.toFixed(1) === b.toFixed(1) ? `${a.toFixed(1)}%` : `${a.toFixed(1)}–${b.toFixed(1)}%`;
};
const redu = (c) => range(LV.map((lv) => -d(c, lv).vs_fixed.pct));
// For values that can have either sign: "between −6.8% and +2.9%".
const between = (vals) => `between ${pct(Math.min(...vals))} and ${pct(Math.max(...vals))}`;
const ratios = O.ratios;
const sw = (r, c, m) => O.sweep[r][c][m];
const swOn = (r, c, m) => Oon.sweep[r][c][m];
const R = (x) => ratios.find((r) => Math.abs(parseFloat(r) - x) < 1e-6);

// ---------------------------------------------------------------------------
// Title block (single column)

const authors = [
  ["Madhav Goel", "Akash Varshney", "Abhisekh Chaudhary"],
  ["Shivam Goel", "Ruchi Gupta", ""],
];
const affil = ["Dept. of Information Technology", "Ajay Kumar Garg Engineering College", "Ghaziabad, India"];
const noBorder = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const authorCell = (name) => new TableCell({
  width: { size: 3480, type: WidthType.DXA },
  borders: { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder },
  children: name ? [
    new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: name, font: I.FONT, size: I.SIZE.author })] }),
    ...affil.map((a) => new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: a, font: I.FONT, size: I.SIZE.affil, italics: a.startsWith("Dept") || a.startsWith("Ajay") })] })),
    new Paragraph({ children: [] }),
  ] : [new Paragraph({ children: [] })],
});
const titleBlock = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
    children: [new TextRun({ text: "Smart Traffic Control System Using Vehicle Density Analysis", font: I.FONT, size: I.SIZE.title })] }),
  new Table({ width: { size: 10440, type: WidthType.DXA }, columnWidths: [3480, 3480, 3480], alignment: AlignmentType.CENTER,
    rows: authors.map((row) => new TableRow({ children: row.map(authorCell) })) }),
];

// ---------------------------------------------------------------------------
// Body (two columns)

const body = [];
const add = (...items) => items.flat().forEach((x) => body.push(x));

const det0 = Object.values(N.vision.detectors)[0];
const abstractText =
  "Fixed-time signals give every approach the same green regardless of demand. This paper presents a density-aware " +
  "controller for an isolated four-arm junction and evaluates it in a seeded microscopic simulation against the fixed " +
  "plan and four re-implemented alternatives: a Webster-optimized plan, vehicle-actuated, max-pressure and three-level " +
  "density control. Each approach is scored by class-weighted vehicle counts in which a queued vehicle counts three " +
  "times a moving one; green is extended between 8 s and 45 s while the served direction dominates, change intervals " +
  "are never shortened, and an emergency preemption layer keeps full yellow and all-red. Below capacity the controller " +
  `reduced mean stopped delay by ${redu("adaptive")} relative to a 20 s fixed plan (p < 0.001), but the Webster, ` +
  `actuated and max-pressure strategies did as well (${redu("webster")}, ${redu("actuated")}, ${redu("max_pressure")}). ` +
  `Near capacity, density-only switching ended greens too early and lost ${abspct(O.capacity.adaptive.vs_fixed.pct)} of ` +
  "capacity; a discharge-hold rule that keeps green while the served queue is at the stop line restored it " +
  `(${pct(O.capacity.adaptive_hold.vs_fixed.pct)}). The queued/moving distinction, not the class weights, drives the ` +
  "score's benefit. The findings hold with kinematics calibrated to field saturation headways once the hold's zone is " +
  `re-tuned, but with the present Haar detector (${det0.precision.toFixed(0)}% precision, ${det0.recall.toFixed(0)}% ` +
  "recall) every controller would be worse than fixed timing near capacity. A per-step audit of " +
  `${S.total_runs.toLocaleString("en-US")} runs found no conflicting greens or shortened change intervals.`;

add(
  new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 80 },
    children: [new TextRun({ text: "Abstract", font: I.FONT, size: I.SIZE.abstract, bold: true, italics: true }),
      new TextRun({ text: "—", font: I.FONT, size: I.SIZE.abstract, bold: true }),
      ...I.runs(abstractText, { size: I.SIZE.abstract, bold: true })] }),
  new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 120 },
    children: [new TextRun({ text: "Index Terms", font: I.FONT, size: I.SIZE.abstract, bold: true, italics: true }),
      new TextRun({ text: "—adaptive traffic signal control, vehicle density, actuated control, max-pressure control, " +
        "emergency preemption, oversaturation, microscopic simulation", font: I.FONT,
      size: I.SIZE.abstract, bold: true })] }),
);

// I. Introduction ------------------------------------------------------------
add(
  I.heading("Introduction"),
  I.para("Many junctions, especially in smaller cities, still run fixed-time plans dimensioned for average flows; when " +
    "demand is uneven, green is wasted on empty approaches while queues build on busy ones. SCATS and SCOOT adapt " +
    "timings from loop detectors but need dedicated infrastructure [3], [4], and low-cost alternatives estimate density " +
    "with infrared sensors, image-based density classes or camera detectors [1], [5], [6], [8]–[10]."),
  I.para("**Motivation.** Such low-cost systems are usually shown on a prototype or a few scenarios, reporting an " +
    "average gain over a fixed plan. Rarely answered are whether variable greens keep safe change intervals, how " +
    "emergency priority interacts with density timing, how the controller behaves at and above capacity, and how much " +
    "of the gain is due to density logic rather than to replacing an untuned plan with any responsive one."),
  I.para("**Novelty.** Rather than a new detector, this paper studies the timing logic of a density-based controller " +
    "under statistically paired conditions against re-implementations of the strategies of existing approaches " +
    "(Webster [2], actuated [23], max-pressure [11] and three-level density control [1]) on identical traffic. It " +
    "exposes a capacity loss of density-only switching and corrects it with a discharge hold. The controller is a " +
    "transparent rule, not a learned policy; machine learning enters through the pre-trained detector, whose accuracy " +
    "is measured, and a data-driven calibration of the score on held-out seeds. Contributions:"),
  I.bullet("a class-weighted, queue-aware density score with bounded green extension, a discharge-hold rule, and an " +
    "emergency preemption wrapper, all keeping full change intervals and a closed-form maximum red;"),
  I.bullet("a reproducible paired evaluation below, at and up to 1.5 times capacity against four strategies, with an " +
    "ablation, a peak-period test and a per-step safety audit of every run;"),
  I.bullet("validation against external values: Haar-cascade detection and tracking against exact ground truth, queue " +
    "discharge against the Highway Capacity Manual with a calibrated reaction time, imperfect sensing, and a held-out " +
    "calibration of the score weights."),
  I.para("All results are from simulation; the simulator, controllers and experiment scripts are public and regenerate " +
    "every table (github.com/shivam-G05/Smart-Traffic-Management)."),
);

// II. Related work -------------------------------------------------------------
add(
  I.heading("Related Work"),
  I.para("Fixed plans are commonly timed with Webster's cycle formula [2]; SCATS and SCOOT adapt splits and cycles over " +
    "networks [3], [4]. Actuated control extends green while stop-line detectors register vehicles and ends it on a " +
    "gap (\"gap-out\") within green limits [23]. Max-pressure control chooses phases from queue differences with " +
    "throughput guarantees [11]; reinforcement-learning controllers are widely studied but must be trained in " +
    "simulation and are harder to bound [12]. Among low-cost systems, Nsofwa and Tembo set green from low, medium or high " +
    "image-based density [1]; Kamble et al. use YOLO [7] on IP cameras to prioritize the busiest lane [6]; Pardeshi et " +
    "al. use infrared sensors on an ESP32 [5]; others adapt timing to density [9], [10], estimate it from surveillance " +
    "cameras [8], or add incident alerts [13], AI-based light design [14] or traffic prediction [15]. These mainly report " +
    "gains over fixed timing; this paper adds strong baselines on identical traffic, demand up to 1.5 times capacity and " +
    "a per-step safety check. Haar cascades [16] remain cheap on embedded hardware; ByteTrack [17] combines Kalman " +
    "prediction [18] with Hungarian assignment [19]; Nellore and Hancke give emergency vehicles visual-sensing priority [20]."),
);

// III. System and methods -------------------------------------------------------
add(
  I.heading("System and Methods"),
  I.subheading("Architecture and Workflow"),
  I.para("The system is a set of Python 3.12 packages with one-directional dependencies: the simulation core imports no " +
    "decision or web code, and every controller implements one interface, so controllers are interchangeable. A FastAPI " +
    "backend streams the junction at 10 Hz to a React dashboard, logs metrics to SQLite and runs side-by-side controller " +
    "comparisons on the same seed; the code has 119 automated tests (Fig. 1). Fig. 2 shows the method. Every 50 ms step the " +
    "controller reads vehicle positions, speeds and classes, scores each approach, and decides whether the green may " +
    "end; the preemption layer protects every transition with full yellow and all-red before the signal heads change. " +
    "A vision pipeline (Section III-G) runs alongside; its output is evaluated but not used for control."),
  I.figure(FIG("fig1_architecture.png"), 3.0, "Software architecture. Solid boxes form the control loop; dashed " +
    "boxes form the vision pipeline, evaluated but not used for control.", 1),
  I.figure(FIG("fig2_workflow.png"), 2.8, "Method workflow. (a) Per-step control pipeline. (b) Green-end decision; the " +
    "\"discharge hold\" test (Section III-D) is the extension added in this revision.", 2),
  I.subheading("Junction and Traffic Model"),
  I.para("Four approaches each have two lanes on a 330 m link (stop line at 200 m, junction exit at 218 m); vehicles go " +
    "straight, without turns, lane changes or pedestrians. Arrivals on each approach have deterministic headways at a " +
    "rate λ redrawn every 15 s as λ·*U*(0.4, 1.6); a vehicle enters at rest and is dropped if the entry is blocked. For " +
    "the above-capacity runs, blocked arrivals instead wait in an entry queue (so unserved demand is measured) and enter " +
    "at the highest safe speed. Table I lists the vehicle classes. Motion follows a Gipps-type safe speed [21],"),
  I.table(1, "Vehicle classes and parameters",
    ["Class", "Share (%)", "Length (m)", "*v*_{max} (m/s)", "*a* (m/s²)", "*b* (m/s²)", "Weight *w*"],
    [["Car", "55", "4.5", "14", "2.5", "4.5", "1.0"], ["Motorcycle", "25", "2.0", "15", "3.5", "5.0", "0.5"],
      ["Auto-rickshaw", "10", "3.2", "11", "2.0", "4.0", "0.8"], ["Bus", "5", "10.0", "10", "1.2", "3.0", "3.0"],
      ["Truck", "4", "9.0", "9", "1.0", "2.8", "2.5"], ["Ambulance", "0.5", "5.5", "16", "3.0", "5.0", "6.0"],
      ["Fire truck", "0.5", "10.5", "12", "1.5", "3.5", "6.0"]],
    [1100, 640, 660, 660, 660, 660, 660],
    "a, b: maximum acceleration and deceleration; w: density weight in (2)."),
  I.equation("*u*_{safe} = [2*b*(*g* + *u*_{l}²/(2*b*_{l}) − *s*_{0})]^{1/2}", 1),
  I.para("where *g* is the gap to the leader, *u*_{l} and *b*_{l} its speed and deceleration, and *s*_{0} = 2 m. On " +
    "yellow or red a vehicle brakes once its braking distance reaches the stop line. Rule (1) has no reaction time; " +
    "Section IV-G adds one and repeats the main comparisons.", { noIndent: true }),
  I.subheading("Density Score and Green Extension"),
  I.para("For approach *r* with vehicles *V*_{r} the score is"),
  I.equation("*D*_{r} = Σ_{v∈Vr} *w*_{c(v)} · *m*(*v*)", 2),
  I.para("with class weight *w* (Table I) and *m*(*v*) = 1.5 if *v* is queued (upstream of the line, below 0.5 m/s), " +
    "else 0.5: a queued vehicle needs green now. The weights are heuristic and are tested in Sections IV-E and IV-I. " +
    "The plan has two phases (north–south, east–west), each green followed by yellow *Y* = 3 s and all-red *A* = 1 s; " +
    "only green adapts. With elapsed green *t*_{g} and summed scores *D*_{A}, *D*_{W} of the active and waiting " +
    "direction, the green ends when", { noIndent: true }),
  I.equation("*t*_{g} ≥ *G*_{max}  or  (*t*_{g} ≥ *G*_{min}  and  *D*_{A} ≤ θ*D*_{W})", 3),
  I.para("with *G*_{min} = 8 s, *G*_{max} = 45 s and θ = 1.1. Since change intervals are fixed and green capped, the " +
    "red of any approach is bounded by", { noIndent: true }),
  I.equation("*R*_{max} = *A* + *G*_{max} + *Y* + *A* = 50 s", 4),
  I.para("so no approach starves. The fixed baseline uses a 20 s green (48 s cycle).", { noIndent: true }),
  I.subheading("Discharge Hold"),
  I.para("When both directions are saturated, vehicles moving off on green score 0.5 while the queue on red scores 1.5, " +
    "so rule (3) ends greens soon after *G*_{min}; each change costs *Y* + *A* = 4 s of lost service, so capacity drops " +
    "when it is scarcest (Section IV-C). The hold adds actuated control's gap-out test [23]:"),
  I.equation("*t*_{g} ≥ *G*_{max}  or  (*t*_{g} ≥ *G*_{min}  and  *n*_{z} = 0  and  *D*_{A} ≤ θ*D*_{W})", 5),
  I.para("where *n*_{z} counts served vehicles within *z* = 10 m of the stop line (chosen from 10–30 m on a separate " +
    "tuning seed). A discharging queue keeps a vehicle at the line and holds green, while a cleared queue still hands " +
    "over early; bound (4) still holds.", { noIndent: true }),
  I.subheading("Comparison Controllers"),
  I.para("Four strategies were re-implemented with the same phases, change intervals, 8–45 s green limits and exact " +
    "vehicle states, so only the switching decision differs and bound (4) holds for all. *Webster:* a fixed plan " +
    "with cycle *C*_{0} = (1.5*L* + 5)/(1 − *Y*), lost time *L* = 8 s and measured saturation flow 6000 veh/h per " +
    "approach, given the true mean demand of each run (which favors it). *Actuated:* past the minimum, green ends when " +
    "the served direction gaps out (no vehicle within 10 m of the line) and a vehicle waits [23]. *Max-pressure:* switch " +
    "when the waiting phase's upstream count exceeds the served one's [11]; this also represents busiest-lane-first " +
    "control [6]. *Density levels:* green of 10, 20 or 30 s for low, medium or high density at green start [1]."),
  I.subheading("Emergency Vehicle Preemption"),
  I.para("Preemption wraps any phase-based controller (Fig. 3). When an ambulance or fire truck is upstream of the junction exit, " +
    "a conflicting green first completes a full 3 s yellow and 1 s all-red (a green younger than 5 s is not cut); the " +
    "emergency direction then has green until the vehicle has left or for at most 20 s, and the release again passes " +
    "through full yellow and all-red before the inner controller resumes. An emergency vehicle thus waits at most 9 s. " +
    "Detection is assumed perfect, e.g. from vehicle-to-infrastructure messages."),
  I.figure(FIG("fig3_preemption.png"), 3.0, "Emergency preemption states. Every path from one direction's green to " +
    "the other's passes through a full yellow and all-red interval.", 3),
  I.subheading("Vision Pipeline"),
  I.para("A virtual camera per approach renders the 60 m before the stop line at 4 px/m and 2 Hz. The detector " +
    "equalizes, upscales three times and applies OpenCV's pre-trained vehicle Haar cascade; it localizes but does not " +
    "classify vehicles. A ByteTrack-style tracker matches Kalman-predicted boxes to high- then low-confidence detections " +
    "by Hungarian assignment on IoU. *Data and annotation:* no real images are used; frames and exact ground-truth boxes " +
    "are both generated from the simulator state, so there is no manual labelling. Nothing is trained, so there is no " +
    "training split: parameters were fixed in unseeded development runs, and seeds 1–4 are used only for evaluation. A " +
    "detection is correct if its center lies in a ground-truth box enlarged by 4 px."),
);

// IV. Experiments ---------------------------------------------------------------
const highRatio = R(1.2), capRatio = R(1.0), r15 = R(1.5);
const t2Rows = CTRL.map((c) => [L[c],
  ...LV.map((lv) => T2[c][lv].mean_delay_s.ci),
  c === "fixed" ? "—" : minus(T2[c].high.mean_delay_s.vs_fixed.text),
  T2[c].high.mean_green_s.ci.split(" ")[0]]);

add(
  I.heading("Experimental Evaluation"),
  I.subheading("Setup and Safety Audit"),
  I.para("Three demand levels below capacity were simulated: λ = 0.08, 0.12 and 0.18 veh/s per approach (1152–2592 " +
    "veh/h). Each controller and level ran ten seeds for 1800 s; a seed gives every controller the same arrivals, so runs " +
    "are paired. After a 60 s warm-up, stopped delay (time upstream of the line below 0.5 m/s) is measured for vehicles " +
    "entering until 1650 s. Results give 95% confidence intervals and paired t-tests; preemption is on unless stated. " +
    "Seed 1000 was used for tuning, 101–105 for capacity and 1–10 for reported results. In total " +
    `${S.total_runs.toLocaleString("en-US")} runs (${S.total_hours.toLocaleString("en-US")} simulated hours) were made. ` +
    "Every step of every run was audited for conflicting greens, missing yellows and yellow or all-red shorter than 3 s " +
    "or 1 s: no violation occurred, across all seven controllers and " +
    `${S.table2_on.preemptions.toLocaleString("en-US")} preemptions in the main runs. The audit caught an earlier ` +
    "preemption version that resumed without a release interval."),
  I.subheading("Comparison Below Capacity"),
  I.para(`In Table II the adaptive controller reduced delay by ${redu("adaptive")} relative to the fixed plan, in all ` +
    `seeds at every level (p < 0.001). Yet the Webster plan, actuated and max-pressure control did as well ` +
    `(${redu("webster")}, ${redu("actuated")}, ${redu("max_pressure")}; ` +
    `${between(LV.flatMap((lv) => ["webster", "actuated", "max_pressure"].map((c) => T2[c][lv].mean_delay_s.vs_adaptive.pct)))} ` +
    `relative to adaptive): below capacity the gain comes from replacing an untuned plan with short responsive greens. ` +
    `Three-level density control was worse than fixed timing at medium and high demand ` +
    `(${pct(T2.density_levels.medium.mean_delay_s.vs_fixed.pct)}, ${pct(T2.density_levels.high.mean_delay_s.vs_fixed.pct)}), ` +
    `as its 20–30 s greens outlast the queue. The hold changed delay by ` +
    `${between(LV.map((lv) => T2.adaptive_hold[lv].mean_delay_s.vs_adaptive.pct))}, and throughput by at most ` +
    `${range(CTRL.flatMap((c) => LV.map((lv) => Math.abs(T2[c][lv].throughput_vph.vs_fixed.pct)))).split("–").pop()}, ` +
    "as all levels are far below capacity."),
  I.table(2, "Mean stopped delay below capacity (s)",
    ["Controller", "Low", "Medium", "High", "High vs fixed", "Green (s)"],
    t2Rows, [1300, 860, 860, 860, 640, 520],
    "Mean ± 95% CI, ten paired seeds, preemption on. All changes vs fixed are significant (p < 0.001) except density " +
    `levels at low demand (p = ${T2.density_levels.low.mean_delay_s.vs_fixed.p}). Green: mean at high demand.`),
);

const capRows = CTRL.filter((c) => O.capacity[c]).map((c) => [L[c], O.capacity[c].ci,
  c === "fixed" ? "—" : `${minus(O.capacity[c].vs_fixed.text)}`, O.capacity[c].green,
  Oon.capacity[c] ? Oon.capacity[c].ci : "—"]);
const sweepCtrl = ["fixed", "webster", "actuated", "max_pressure", "adaptive", "adaptive_hold"];
const sweepRows = sweepCtrl.map((c) => [L[c], ...ratios.map((r) => sw(r, c, "delay_all_lb_s").mean.toFixed(1))]);
const PK = N.peak;
const pkRec = (c) => {
  const r = PK[c].recovery_min;
  if (r.not_recovered === r.runs) return "not within the hour";
  const s = `${r.mean.toFixed(1)} min`;
  return r.not_recovered ? `${s} (${r.not_recovered} of ${r.runs} runs did not recover)` : s;
};

add(
  I.subheading("Operation Near and Above Capacity"),
  I.para("Table II's levels are only " +
    `${(1152 / O.capacity.fixed.mean * 100).toFixed(0)}–${(2592 / O.capacity.fixed.mean * 100).toFixed(0)}% of the ` +
    "fixed-time capacity. Table III gives each controller's capacity (all approaches flooded); these runs and Table IV " +
    "use preemption off, since at these demands emergency vehicles would trigger a preemption every 15–30 s. The " +
    `original adaptive rule lost ${abspct(O.capacity.adaptive.vs_fixed.pct)} of capacity (p ${O.capacity.adaptive.vs_fixed.p}) ` +
    `as its saturated greens fell to ${O.capacity.adaptive.green} s; the hold raised them to ` +
    `${O.capacity.adaptive_hold.green} s and capacity to ${pct(O.capacity.adaptive_hold.vs_fixed.pct)}. Max-pressure ` +
    `lost capacity like the original rule (${pct(O.capacity.max_pressure.vs_fixed.pct)}); actuated control ` +
    `(${pct(O.capacity.actuated.vs_fixed.pct)}) and the Webster plan (${pct(O.capacity.webster.vs_fixed.pct)}, maximum ` +
    "green above capacity) did not."),
  I.table(3, "Capacity of each controller (veh/h)",
    ["Controller", "Preemption off", "vs fixed", "Green (s)", "Preemption on"],
    capRows, [1300, 1250, 800, 640, 1050],
    "Every approach flooded at 1.5 arrivals/s; five seeds; mean saturated green."),
  I.table(4, "Delay including vehicles still waiting (s)",
    ["Controller", ...ratios.map((r) => `${parseFloat(r)}×`)], sweepRows, [1400, ...ratios.map(() => 606)],
    "Demand as a multiple of fixed-time capacity; ten paired seeds; preemption off. Values above capacity are lower bounds."),
  ...I.figure(FIG("fig5_above_capacity.png"), 2.9, "Delay (top, log scale) and throughput (bottom) against demand, " +
    "preemption off; dotted line: fixed-time capacity.", 4),
  I.para(`In Table IV and Fig. 4 the original rule beat fixed timing only at 0.6×; at capacity its delay was ` +
    `${sw(capRatio, "adaptive", "delay_all_lb_s").mean.toFixed(1)} s against ${sw(capRatio, "fixed", "delay_all_lb_s").mean.toFixed(1)} s, ` +
    `its queue grew by ${sw(capRatio, "adaptive", "queue_growth_vpm").mean.toFixed(1)} veh/min, and queues spilled back ` +
    `to the link entry during ${sw(capRatio, "adaptive", "spillback_pct").mean.toFixed(0)}% of approach-time. With the ` +
    `hold, delay was below fixed timing at every level (${ratios.map((r) => minus(sw(r, "adaptive_hold", "delay_all_lb_s").vs_fixed.text)).join(", ")} ` +
    `from 0.6× to 1.5×; not significant at 1.0×, p = ${sw(capRatio, "adaptive_hold", "delay_all_lb_s").vs_fixed.p}) and ` +
    `throughput rose by ${pct(sw(highRatio, "adaptive_hold", "throughput_vph").vs_fixed.pct)} and ` +
    `${pct(sw(r15, "adaptive_hold", "throughput_vph").vs_fixed.pct)} at 1.2× and 1.5×. Actuated control behaved like ` +
    `the hold; max-pressure degraded like the original rule. With preemption on the pattern held with smaller margins ` +
    `(capacity ${pct(Oon.capacity.adaptive.vs_fixed.pct)} and ${pct(Oon.capacity.adaptive_hold.vs_fixed.pct)}).`),
  I.para("In a 60-minute peak, demand ramped from 0.6 to 1.2 times capacity, held for 15 min and fell back (Fig. 5; ten " +
    `seeds, preemption off). The queue peaked at ${PK.fixed.peak_queue.mean.toFixed(0)} vehicles under fixed timing, ` +
    `${PK.adaptive_hold.peak_queue.mean.toFixed(0)} with the hold, ${PK.actuated.peak_queue.mean.toFixed(0)} with ` +
    `actuated and ${PK.adaptive.peak_queue.mean.toFixed(0)} with the original rule. Time to recover the pre-peak queue ` +
    `was ${pkRec("fixed")} (fixed), ${pkRec("adaptive_hold")} (hold), ${pkRec("actuated")} (actuated) and ` +
    `${pkRec("adaptive")} (original rule). ` +
    `Entries were blocked for ${PK.fixed.spillback_approach_min.mean.toFixed(0)}, ` +
    `${PK.adaptive_hold.spillback_approach_min.mean.toFixed(0)} and ${PK.adaptive.spillback_approach_min.mean.toFixed(0)} ` +
    `approach-minutes (fixed, hold, original); peak throughput was ${PK.fixed.peak_throughput_vph.mean.toFixed(0)}, ` +
    `${PK.adaptive_hold.peak_throughput_vph.mean.toFixed(0)} and ${PK.adaptive.peak_throughput_vph.mean.toFixed(0)} veh/h; ` +
    `total delay changed by ${minus(PK.adaptive_hold.total_delay_vs_fixed.text)} with the hold and ` +
    `${minus(PK.adaptive.total_delay_vs_fixed.text)} with the original rule relative to fixed timing.`),
  ...I.figure(FIG("fig6_peak_queue.png"), 2.9, "Queue including vehicles waiting to enter during the 60-minute peak " +
    "(mean of ten seeds, 2-min moving average). Shading: ramp (light) and 1.2× capacity (dark).", 5),
);

// Emergency preemption (text)
const T3 = N.table3;
const t3 = (c, lv) => T3[c][lv];
add(
  I.subheading("Emergency Preemption"),
  I.para(`Emergency vehicles (1% of arrivals) triggered ${range(LV.map((lv) => T3.adaptive[lv].preemptions_per_hour)).replace(/%/g, "")} ` +
    `preemptions per hour. Preemption cut their mean stopped delay from ${t3("fixed", "medium").ev_delay_off} s to ` +
    `${t3("fixed", "medium").ev_delay_on} s under fixed timing and from ${t3("adaptive", "medium").ev_delay_off} s to ` +
    `${t3("adaptive", "medium").ev_delay_on} s under adaptive control at medium demand (p < 0.001). The cost to other ` +
    `vehicles was ${minus(t3("fixed", "medium").other_change.text)} (p ${t3("fixed", "medium").other_change.p}) under fixed ` +
    `timing but ${minus(t3("adaptive", "medium").other_change.text)} under adaptive control and ` +
    `${minus(t3("adaptive_hold", "medium").other_change.text)} with the hold, because each preemption discards the ` +
    "responsive timing; real emergency traffic is far rarer, so the real cost would be smaller."),
);

// Ablation (compact)
const abl = (v, lv) => N.ablation.find((r) => r.variant.startsWith(v) && r.level === lv);
const ablVariants = [...new Set(N.ablation.map((r) => r.variant))]
  .filter((v) => !v.startsWith("Adaptive (reference)") && !v.startsWith("Fixed 20 s"));
const ablCell = (v, lv) => { const r = abl(v, lv); return `${r.change} (${r.p})`; };
add(
  I.subheading("Ablation"),
  I.para("Table V changes one part of the controller at a time on the same seeds. Counting vehicles plainly raised " +
    `delay by ${abspct(abl("Unweighted", "medium").pct)} and ${abspct(abl("Unweighted", "high").pct)}; removing the ` +
    `queued/moving distinction raised it by ${abspct(abl("No queued", "medium").pct)} and ${abspct(abl("No queued", "high").pct)}, ` +
    `whereas equal class weights changed it by ${pct(abl("No class", "medium").pct)} and ${pct(abl("No class", "high").pct)}. ` +
    "The score's benefit thus comes from the queued/moving distinction, not the class weights. θ = 1.5 lowered delay " +
    "slightly, and the hold, with any zone, left delay unchanged below capacity."),
  I.table(5, "Ablation: change in mean delay (p)", ["Variant", "Medium", "High"],
    ablVariants.map((v) => [v.replace(" (weights and multipliers = 1)", "").replace(" (all classes = 1)", "")
      .replace(" (multipliers = 1)", "").replace("theta", "θ"), ablCell(v, "medium"), ablCell(v, "high")]),
    [2040, 1500, 1500],
    `Ten paired seeds, relative to the adaptive controller (${abl("Adaptive", "medium").delay.split(" ")[0]} s and ` +
    `${abl("Adaptive", "high").delay.split(" ")[0]} s); preemption on unless stated.`),
);

// Vision
const V = N.vision;
// Single-process timing runs (scripts/timing_check.py).
const TM = ["timing.json", "timing_run2.json"].map((f) => JSON.parse(fs.readFileSync(path.join(HERE, "..", "results", f), "utf8")));
const detEntries = Object.entries(V.detectors);
const trk0 = Object.values(V.tracking)[0];
const f1 = (x) => (x === null || Number.isNaN(x) ? "n/a" : x.toFixed(1));
const classRecall = Object.entries(V.by_class).map(([c, v]) => `${c} ${f1(v.recall)}%`).join(", ");
const distRecall = Object.entries(V.by_distance).map(([k, v]) => `${k} ${f1(v.recall)}%`).join(", ");
add(
  I.subheading("Vision Pipeline"),
  I.para(`On seeds 1–4 (${det0.frames.toLocaleString("en-US")} frames, ${det0.gt_instances.toLocaleString("en-US")} ` +
    `vehicle instances) the generic cascade reached ${f1(det0.precision)}% precision and ${f1(det0.recall)}% recall ` +
    `(Table VI). ${f1(V.failure.persistent_background_share)}% of false positives recur at the same spot, i.e. fire on ` +
    `background texture. Recall varied by class (${classRecall}) and distance (${distRecall}), lowest near the line where ` +
    "queued vehicles stand close. Only " +
    `${f1(trk0.coverage)}% of instances carried a confirmed track (Table VII). ` +
    (trk0.speed_mae !== null
      ? `Tracked speed had a mean absolute error of ${trk0.speed_mae.toFixed(2)} m/s against vehicles moving at only ` +
        `${trk0.true_speed_mean.toFixed(2)} m/s, since tracks are confirmed almost only on queued vehicles: a negative ` +
        "result, as the pipeline gives no usable kinematics for moving traffic. "
      : "") +
    "Removing the low-confidence matching stage or the motion model changed little, because recall is the limit. " +
    `In two single-process runs of ${TM[0].frames} frames on an Intel Core i5-12450H laptop CPU, detection took ` +
    `${Math.min(...TM.map((t) => t.detect_ms_mean)).toFixed(0)} and ${Math.max(...TM.map((t) => t.detect_ms_mean)).toFixed(0)} ms ` +
    `per frame on average (it varies with the CPU's power state), against ` +
    `${Math.min(...TM.map((t) => t.decision_ms_mean)).toFixed(3)}–${Math.max(...TM.map((t) => t.decision_ms_mean)).toFixed(3)} ms per control decision.`),
  I.table(6, "Detector accuracy and ablation (synthetic frames)",
    ["Detector variant", "Precision (%)", "Recall (%)", "Det./frame"],
    detEntries.map(([name, dd]) => [name, dd.detections_per_frame < 0.01 ? "—" : f1(dd.precision), f1(dd.recall),
      dd.detections_per_frame.toFixed(2)]),
    [2340, 900, 900, 900],
    "Seeds 1–4. —: too few detections for a meaningful precision."),
  I.table(7, "Tracking quality and tracked-speed error",
    ["Tracker variant", "Coverage (%)", "Confirmed (%)", "ID sw./100 veh.", "Speed MAE (m/s)"],
    Object.entries(V.tracking).map(([name, t]) => [name, f1(t.coverage), f1(t.vehicles_confirmed),
      f1(t.id_switches_per_100_vehicles), t.speed_mae === null ? "n/a" : t.speed_mae.toFixed(2)]),
    [1900, 800, 800, 800, 740],
    "Coverage: vehicle instances in view with a confirmed track. Speed MAE: confirmed tracks on real vehicles."),
);

// Kinematics validation (text)
const K0 = N.kinematics.tau0;
const K1 = N.kinematics.tau16;
const kc0 = K0["cars only"], kc1 = K1["cars only"];
const TC = N.table2_cal;
const OC = N.over_cal;
const ZC = N.zone_cal;
const reduCal = (c) => range(LV.map((lv) => -TC[c][lv].mean_delay_s.vs_fixed.pct));
add(
  I.subheading("Validation of the Simulated Kinematics"),
  I.para("Queue discharge was measured as in the field: headways of queued vehicles crossing the line in saturated " +
    "fixed-time runs, from the fifth vehicle on. The Highway Capacity Manual base is 1900 veh/h/lane (1.89 s) with " +
    `about 2 s start-up lost time [24]. The model above discharges cars every ${kc0.saturation_headway_s.toFixed(2)} s ` +
    `(${kc0.saturation_flow_vphpl.toLocaleString("en-US")} veh/h/lane; Table VIII), because without a reaction time a follower may ` +
    "trail by the 2 m standstill gap. Adding a reaction time τ to (1), as in Krauss's model [25], with τ = 1.6 s gives " +
    `${kc1.saturation_headway_s.toFixed(2)} s (${kc1.saturation_flow_vphpl.toLocaleString("en-US")} veh/h/lane), within ` +
    `${Math.abs(100 * (kc1.saturation_flow_vphpl - 1900) / 1900).toFixed(1)}% of the reference; start-up lost time ` +
    `(${minus(kc1.startup_lost_time_s.toFixed(1))} s) stays below field values. Repeating all comparisons with τ = 1.6 s (Webster ` +
    `re-timed for 3600 veh/h), delay reductions below capacity were ${reduCal("adaptive")} for the adaptive controller ` +
    `and ${reduCal("webster")}, ${reduCal("actuated")} and ${reduCal("max_pressure")} for Webster, actuated and ` +
    `max-pressure. Relative to fixed-time capacity (${OC.capacity.fixed.mean.toLocaleString("en-US")} veh/h) the original ` +
    `rule reached ${pct(OC.capacity.adaptive.vs_fixed.pct)} and Webster ${pct(OC.capacity.webster.vs_fixed.pct)}, but the ` +
    `hold with its 10 m zone only ${pct(OC.capacity.adaptive_hold.vs_fixed.pct)}: with a reaction time, discharging ` +
    "vehicles spread to about 20 m gaps, so a 10 m zone empties between them. Like an actuated controller's passage " +
    `time, the zone depends on local kinematics; re-tuned on the tuning seed to ${ZC.tuning.best_zone_m} m, the hold ` +
    `reached ${pct(ZC.over.capacity.adaptive_hold.vs_fixed.pct)} and actuated control ` +
    `${pct(ZC.over.capacity.actuated.vs_fixed.pct)}, against ${pct(ZC.over.capacity.webster.vs_fixed.pct)} for Webster.`),
  I.table(8, "Queue discharge against field reference values",
    ["Model", "Headway, cars (s)", "Sat. flow, cars (veh/h/ln)", "Sat. flow, all (veh/h/ln)", "Start-up lost (s)"],
    [["Simulator, τ = 0", kc0.saturation_headway_s.toFixed(2), kc0.saturation_flow_vphpl.toLocaleString("en-US"),
      K0["full vehicle mix"].saturation_flow_vphpl.toLocaleString("en-US"), minus(kc0.startup_lost_time_s.toFixed(1))],
    ["Simulator, τ = 1.6 s", kc1.saturation_headway_s.toFixed(2), kc1.saturation_flow_vphpl.toLocaleString("en-US"),
      K1["full vehicle mix"].saturation_flow_vphpl.toLocaleString("en-US"), minus(kc1.startup_lost_time_s.toFixed(1))],
    ["HCM base values [24]", "1.89", "1,900", "—", "≈ 2.0"]],
    [1500, 860, 900, 900, 880],
    "Saturated fixed-time runs, five seeds; headway averaged from the fifth queued vehicle on."),
);

// Imperfect sensing (compact table)
const SN = N.sensing;
const snConds = Object.keys(SN);
const snMed = SN[snConds[0]], snCap = SN[snConds[1]];
const snCtrl = snMed.controllers;
const snRow = (cond, name) => cond.rows.find((r) => r.sensing.startsWith(name));
const snNames = snMed.rows.map((r) => r.sensing);
const haarName = snNames.find((n) => n.startsWith("Measured Haar"));
add(
  I.subheading("Imperfect Sensing"),
  I.para("To measure the cost of the exact-state assumption, the vehicle-reading controllers were run behind a sensor " +
    "model that reports only what a camera would: vehicles within 60 m, refreshed at 2 Hz, without classes, each " +
    "detected with a given recall, optionally with phantom detections at fixed spots, and finally the measured pipeline " +
    `(${haarName ? haarName.replace("Measured Haar ", "").replace(/[()]/g, "") : "as measured"}); preemption reads true ` +
    "flags. Table IX gives delay at medium demand and 0.9 times capacity. " + senseText()),
  I.table(9, "Delay under imperfect sensing (s): medium demand / 0.9× capacity",
    ["Sensing", ...snCtrl.map((c) => L[c])],
    snNames.map((name) => [name.replace(" (60 m, 2 Hz, no classes)", "").replace("Measured Haar", "Haar")
      .replace(" per approach", ""),
    ...snCtrl.map((c) => `${snRow(snMed, name)[c].mean.toFixed(1)} / ${snRow(snCap, name)[c].mean.toFixed(1)}`)]),
    [1360, 920, 920, 920, 920],
    `Ten paired seeds. Fixed plan: ${snMed.fixed_mean.toFixed(1)} / ${snCap.fixed_mean.toFixed(1)} s. 0.9×: preemption ` +
    "off, delay includes waiting to enter."),
);

function senseText() {
  const hold = "adaptive_hold";
  const capExact = snRow(snCap, "Exact states")[hold].mean;
  const capCam = snRow(snCap, "Camera")[hold];
  const capR50 = snRow(snCap, "recall 50%")[hold];
  const medPh = snRow(snMed, "2 phantoms")[hold];
  return "Below capacity missed detections cost little, as they only shorten greens. Near capacity the hold's delay " +
    `rose from ${capExact.toFixed(1)} s (exact) to ${capCam.mean.toFixed(1)} s (perfect camera) and ` +
    `${capR50.mean.toFixed(1)} s (50% recall), against ${snCap.fixed_mean.toFixed(1)} s for fixed timing. Phantoms ` +
    "were worst for gap-out rules: a phantom in the zone never moves, so green runs to the maximum (medium demand " +
    `${medPh.mean.toFixed(1)} s, ${minus(medPh.vs_fixed.text)} vs fixed). ` + (haarName ? haarSentence() : "") +
    "Closing the loop with the present detector would harm traffic; a detector must suppress static false positives " +
    "near the stop line, and recall matters most near capacity.";
}

function haarSentence() {
  const worse = (cond) => snCtrl.filter((c) => snRow(cond, "Measured Haar")[c].mean > cond.fixed_mean);
  const names = (list) => list.map((c) => L[c].toLowerCase()).join(", ").replace(/, ([^,]*)$/, " and $1");
  const wCap = worse(snCap), wMed = worse(snMed);
  let s = "With the measured pipeline, ";
  s += wCap.length === snCtrl.length ? "every controller was worse than fixed timing near capacity. "
    : `${names(wCap)} ${wCap.length === 1 ? "was" : "were"} worse than fixed timing near capacity. `;
  const better = snCtrl.filter((c) => !wMed.includes(c));
  if (wMed.length && better.length) {
    s += `At medium demand ${names(better)} still beat it, as phantoms on both directions largely cancel, while ` +
      `${names(wMed)} ${wMed.length === 1 ? "was" : "were"} held at long greens by phantoms in the zone. `;
  }
  return s;
}

// Weight calibration (text)
const CB = N.calibration;
const cbConds = Object.keys(CB.held_out["Hand-set (paper)"]);
const cbP = (p) => (p < 0.001 ? "< 0.001" : p.toFixed(3));
const bp = CB.best_params;
add(
  I.subheading("Calibration of the Density Weights"),
  I.para("The hand-set weights were calibrated by a random search over the class weights, the queued/moving ratio and " +
    `θ of the hold controller (${CB.candidates} candidates on tuning seeds ${CB.tune_seeds[0]}–${CB.tune_seeds[CB.tune_seeds.length - 1]}, ` +
    "medium, high and 0.9× demand). The best setting (motorcycle " +
    `${bp.motorcycle.toFixed(2)}, auto-rickshaw ${bp.auto.toFixed(2)}, bus ${bp.bus.toFixed(2)}, truck ${bp.truck.toFixed(2)}, ` +
    `emergency ${bp.emergency.toFixed(2)}, queued/moving ratio ${bp.queued_ratio.toFixed(2)}, θ = ${bp.theta.toFixed(2)}) ` +
    "was compared with the hand-set weights on held-out seeds 1–10 (Table X): " + calibText()),
  I.table(10, "Held-out delay with calibrated score parameters (s)",
    ["Condition", "Hand-set", "Calibrated", "Plain count"],
    cbConds.map((cond) => [cond, CB.held_out["Hand-set (paper)"][cond].mean.toFixed(2),
      `${CB.held_out.Calibrated[cond].mean.toFixed(2)} (${pct(CB.held_out.Calibrated[cond].change_pct)})`,
      `${CB.held_out["Plain count"][cond].mean.toFixed(2)} (${pct(CB.held_out["Plain count"][cond].change_pct)})`]),
    [1400, 1000, 1400, 1240],
    "Held-out seeds 1–10, ten paired seeds; change relative to the hand-set weights."),
);

function calibText() {
  const cal = CB.held_out.Calibrated;
  const plain = CB.held_out["Plain count"];
  let s = "delay changed by " + cbConds.map((c) => `${pct(cal[c].change_pct)} (p ${cbP(cal[c].p)}, ${c})`).join(", ") +
    ", while a plain count was " + cbConds.map((c) => pct(plain[c].change_pct)).join(", ") + ". ";
  s += "Calibration thus gives modest, condition-dependent gains, and the parameters must be re-fitted on field data " +
    "before deployment; the search is a reproducible procedure, not a learned controller.";
  return s;
}

// V. Discussion ---------------------------------------------------------------
add(
  I.heading("Discussion"),
  I.para("Two results qualify the usual claim that density control beats fixed timing. Below capacity, the gain over " +
    "an untuned plan is matched by Webster, actuated and max-pressure control. Near capacity, density-only switching is " +
    "worse than fixed timing because it ends greens while the queue is still discharging. With the hold, the controller " +
    "matches the best strategies below capacity and nears the highest capacity measured (Webster's, " +
    `${pct(O.capacity.webster.vs_fixed.pct)}), while its rule fits in one line, its red time is bounded and its safety is ` +
    "audited. Its results are, however, close to plain actuated control: the gap-out test does most of the work, and " +
    "the score's role is to decide when a cleared green hands over. Resuming after preemption with the higher-scoring " +
    "direction is a direct improvement to test."),
  I.para("**Limitations.** Results are from simulation only, without turns, lane changes, pedestrians or driver " +
    "variability, so absolute delays are not field predictions. The main model has no reaction time and discharges " +
    "queues too fast; the calibrated model fixes the headway but still underestimates start-up lost time, which would " +
    "make short greens costlier, and the hold's zone must be tuned to local spacing. Arrivals are not Poisson, and " +
    "emergency vehicles are far more frequent than in reality. The baselines are re-implementations with ideal sensing, " +
    "and Webster knows the true demand. Control uses exact states and perfect emergency detection; the vision pipeline " +
    "was tested only on synthetic frames and is far too weak to drive control. The calibrated weights fit this " +
    "simulator, not field data. A Raspberry Pi 4 deployment (about INR 6,000–8,000 in parts, estimated 5–10 times " +
    "slower detection than the laptop) remains to be verified."),
);

// VI. Conclusion ----------------------------------------------------------------
add(
  I.heading("Conclusion"),
  I.para("A density-aware signal controller with a queue-aware score, bounded green extension, a discharge hold and " +
    "safe emergency preemption was compared with a fixed plan and four re-implemented strategies on identical traffic. " +
    `It reduced delay below capacity by ${redu("adaptive")}, as did Webster, actuated and max-pressure control. Near ` +
    `capacity the original rule lost ${abspct(O.capacity.adaptive.vs_fixed.pct)} of capacity; the hold restored it ` +
    `(${pct(O.capacity.adaptive_hold.vs_fixed.pct)}) and lowered delay from 0.6 to 1.5 times capacity. The findings hold ` +
    "under calibrated kinematics with a re-tuned zone, no run violated a change interval, and the queued/moving " +
    "distinction, not the class weights, carries the score's benefit. Future work will close the loop with a class-aware " +
    "detector trained on real footage, test in SUMO [22] with turning traffic and stochastic arrivals, improve " +
    "resumption after preemption, and measure the controller on embedded hardware at a real junction."),
);

add(
  I.unnumberedHeading("Acknowledgment"),
  I.para("The authors thank the Department of Information Technology, Ajay Kumar Garg Engineering College, Ghaziabad, " +
    "for its support. An AI assistant (Anthropic's Claude) was used in developing parts of the software and in drafting " +
    "and editing this manuscript; the authors reviewed the content and take responsibility for it."),
  I.unnumberedHeading("References"),
);

const refs = [
  "K. Nsofwa and S. Tembo, \"Density based traffic control system,\" *Int. J. Traffic Transp. Eng.*, vol. 14, no. 1, pp. 1–8, 2025.",
  "F. V. Webster, \"Traffic signal settings,\" Road Research Laboratory, London, U.K., Road Res. Tech. Paper no. 39, 1958.",
  "A. G. Sims and K. W. Dobinson, \"The Sydney coordinated adaptive traffic (SCAT) system philosophy and benefits,\" *IEEE Trans. Veh. Technol.*, vol. 29, no. 2, pp. 130–137, May 1980, doi: 10.1109/TVT.1980.23833.",
  "P. B. Hunt, D. I. Robertson, R. D. Bretherton, and M. C. Royle, \"The SCOOT on-line traffic signal optimisation technique,\" *Traffic Eng. Control*, vol. 23, no. 4, pp. 190–192, 1982.",
  "K. Pardeshi, P. Bable, M. Bhalerao, and M. Desai, \"Adaptive traffic signal control system using density-based prioritization algorithm on ESP 32 platform,\" *Int. J. Eng. Res. Technol.*, vol. 15, no. 5, May 2026, doi: 10.5281/zenodo.20205923.",
  "V. B. Kamble, O. N. Mundhe, C. M. Walunjkar, and G. A. Kale, \"AI-driven smart traffic management system,\" *Int. J. Multidiscip. Sci. Manage.*, vol. 2, no. 2, pp. 66–72, 2025.",
  "J. Redmon, S. Divvala, R. Girshick, and A. Farhadi, \"You only look once: Unified, real-time object detection,\" in *Proc. IEEE Conf. Comput. Vis. Pattern Recognit. (CVPR)*, Las Vegas, NV, USA, 2016, pp. 779–788, doi: 10.1109/CVPR.2016.91.",
  "Z. Hu, W. H. K. Lam, S. C. Wong, A. H. F. Chow, and W. Ma, \"Turning traffic surveillance cameras into intelligent sensors for traffic density estimation,\" *Complex Intell. Syst.*, vol. 9, no. 6, pp. 7171–7195, Dec. 2023, doi: 10.1007/s40747-023-01117-0.",
  "S. V. Patil, S. Kureshi, and A. Gaikwad, \"Vehicle density based traffic signal control system,\" *Int. J. Novel Res. Develop.*, vol. 9, no. 5, pp. g284–g288, May 2024.",
  "C. M. Thomas, A. B. Nair, A. E. Varghese, A. B. Kumar, and A. P. Seena, \"Adaptive traffic signal control using real-time vehicle density,\" in *AIP Conf. Proc.*, vol. 3260, Art. no. 020031, 2025, doi: 10.1063/5.0263715.",
  "P. Varaiya, \"Max pressure control of a network of signalized intersections,\" *Transp. Res. C, Emerg. Technol.*, vol. 36, pp. 177–195, Nov. 2013, doi: 10.1016/j.trc.2013.08.014.",
  "H. Wei, G. Zheng, V. Gayah, and Z. Li, \"Recent advances in reinforcement learning for traffic signal control,\" *ACM SIGKDD Explor. Newsl.*, vol. 22, no. 2, pp. 12–18, Jan. 2021, doi: 10.1145/3447556.3447565.",
  "O. Alzamzami, Z. Alsaggaf, R. AlMalki, R. Alghamdi, A. Babour, and L. Al Khuzayem, \"Passable: An intelligent traffic light system with integrated incident detection and vehicle alerting,\" *Sensors*, vol. 25, no. 18, Art. no. 5760, Sep. 2025, doi: 10.3390/s25185760.",
  "T. G. Phakathi, M. Sumbwanyambe, and T. S. Hlalele, \"Designing intelligent traffic light system with the application of artificial intelligence,\" in *Proc. Int. Conf. Artif. Intell., Big Data, Comput. Data Commun. Syst.*, 2025, pp. 1–9, doi: 10.1145/3759023.3759090.",
  "M. Tolani et al., \"Machine learning based adaptive traffic prediction and control using edge impulse platform,\" *Sci. Rep.*, vol. 15, Art. no. 17161, May 2025, doi: 10.1038/s41598-025-00762-4.",
  "P. Viola and M. Jones, \"Rapid object detection using a boosted cascade of simple features,\" in *Proc. IEEE Comput. Soc. Conf. Comput. Vis. Pattern Recognit. (CVPR)*, Kauai, HI, USA, 2001, pp. I-511–I-518, doi: 10.1109/CVPR.2001.990517.",
  "Y. Zhang et al., \"ByteTrack: Multi-object tracking by associating every detection box,\" in *Computer Vision – ECCV 2022*, Cham, Switzerland: Springer, 2022, pp. 1–21, doi: 10.1007/978-3-031-20047-2_1.",
  "R. E. Kalman, \"A new approach to linear filtering and prediction problems,\" *J. Basic Eng.*, vol. 82, no. 1, pp. 35–45, Mar. 1960, doi: 10.1115/1.3662552.",
  "H. W. Kuhn, \"The Hungarian method for the assignment problem,\" *Naval Res. Logist. Quart.*, vol. 2, nos. 1–2, pp. 83–97, Mar. 1955, doi: 10.1002/nav.3800020109.",
  "K. Nellore and G. P. Hancke, \"Traffic management for emergency vehicle priority based on visual sensing,\" *Sensors*, vol. 16, no. 11, Art. no. 1892, Nov. 2016, doi: 10.3390/s16111892.",
  "P. G. Gipps, \"A behavioural car-following model for computer simulation,\" *Transp. Res. B, Methodol.*, vol. 15, no. 2, pp. 105–111, Apr. 1981, doi: 10.1016/0191-2615(81)90037-0.",
  "P. A. Lopez et al., \"Microscopic traffic simulation using SUMO,\" in *Proc. 21st Int. Conf. Intell. Transp. Syst. (ITSC)*, Maui, HI, USA, 2018, pp. 2575–2582, doi: 10.1109/ITSC.2018.8569938.",
  "P. Koonce et al., \"Traffic signal timing manual,\" Federal Highway Administration, Washington, DC, USA, Rep. FHWA-HOP-08-024, 2008.",
  "*Highway Capacity Manual 2010*. Washington, DC, USA: Transportation Research Board, 2010.",
  "S. Krauß, \"Microscopic modeling of traffic flow: Investigation of collision free vehicle dynamics,\" Ph.D. dissertation, Univ. of Cologne, Cologne, Germany, 1998.",
];
refs.forEach((r, i) => add(I.reference(i + 1, r)));

const doc = new Document({
  creator: "Madhav Goel, Akash Varshney, Abhisekh Chaudhary, Shivam Goel, Ruchi Gupta",
  title: "Smart Traffic Control System Using Vehicle Density Analysis (revised)",
  styles: { default: { document: { run: { font: I.FONT, size: I.SIZE.body } } } },
  numbering: I.numbering,
  sections: [{ properties: { page: I.PAGE }, children: titleBlock }, I.twoColumnSection(body)],
});

fs.mkdirSync(path.dirname(OUT), { recursive: true });
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log("wrote", OUT);
});
