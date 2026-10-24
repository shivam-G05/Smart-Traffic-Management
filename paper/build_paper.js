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
const N = JSON.parse(fs.readFileSync(path.join(HERE, "build", "numbers.json"), "utf8"));
const OUT = path.join(HERE, "out", "Smart_Traffic_Control_revised.docx");
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

const abstractText =
  "Fixed-time traffic signals give every approach the same green time regardless of demand, which wastes green on " +
  "lightly used approaches and lengthens queues on busy ones. This paper presents a density-aware signal controller " +
  "for an isolated four-arm junction and evaluates it in a seeded microscopic simulation against the fixed plan and " +
  "four re-implemented alternatives: a Webster-optimized fixed plan, vehicle-actuated control, max-pressure control " +
  "and three-level density control. Each approach receives a score that weights vehicles by class and counts a " +
  "queued vehicle three times as much as a moving one; green is extended between 8 s and 45 s while the served " +
  "direction's score dominates, yellow and all-red intervals are never shortened, and an emergency preemption layer " +
  "keeps full change intervals. Below capacity the controller reduced mean stopped delay by " +
  `${redu("adaptive")} relative to the 20 s fixed plan (p < 0.001), but the Webster plan, actuated and max-pressure ` +
  `control did as well (${redu("webster")}, ${redu("actuated")} and ${redu("max_pressure")}): most of the gain comes from ` +
  "replacing an untuned plan. Near and above capacity, density-only switching ended greens too early and lost " +
  `${abspct(O.capacity.adaptive.vs_fixed.pct)} of capacity; a discharge-hold rule that keeps green while the served queue ` +
  `is still at the stop line restored it (${pct(O.capacity.adaptive_hold.vs_fixed.pct)} relative to fixed timing) and ` +
  "kept the low-demand benefit. An ablation shows that the queued/moving distinction, not the class weights, drives the " +
  `score's benefit. A per-step audit of ${S.total_runs.toLocaleString("en-US")} runs found no conflicting greens or ` +
  "shortened change intervals. Control uses simulated vehicle states: on synthetic frames the Haar-cascade detector " +
  "reached only 6% precision and 9% recall.";

add(
  new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 80 },
    children: [new TextRun({ text: "Abstract", font: I.FONT, size: I.SIZE.abstract, bold: true, italics: true }),
      new TextRun({ text: "—", font: I.FONT, size: I.SIZE.abstract, bold: true }),
      ...I.runs(abstractText, { size: I.SIZE.abstract, bold: true })] }),
  new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 120 },
    children: [new TextRun({ text: "Index Terms", font: I.FONT, size: I.SIZE.abstract, bold: true, italics: true }),
      new TextRun({ text: "—adaptive traffic signal control, vehicle density estimation, actuated control, max-pressure " +
        "control, emergency vehicle preemption, oversaturation, microscopic traffic simulation", font: I.FONT,
      size: I.SIZE.abstract, bold: true })] }),
);

// I. Introduction ------------------------------------------------------------
add(
  I.heading("Introduction"),
  I.para("Signalized intersections account for a large share of the delay in urban road networks. Many junctions, " +
    "especially in smaller cities, still run fixed-time plans in which each approach receives a preset green interval " +
    "regardless of how many vehicles are waiting. Such plans are dimensioned for average flows; when demand fluctuates " +
    "or is unevenly distributed across approaches, green time is wasted on nearly empty approaches while queues build " +
    "on busy ones."),
  I.para("Traffic-responsive systems such as SCATS and SCOOT adjust timings from detector data, but they rely on " +
    "dedicated detector infrastructure and centrally managed installations [3], [4]. Low-cost alternatives estimate " +
    "density locally with infrared sensors, image-based density classes, deep detectors on camera feeds or existing " +
    "surveillance cameras, and adapt green time accordingly [1], [5], [6], [8]–[10]."),
  I.para("**Motivation.** These low-cost systems are usually demonstrated on a prototype or a few scenarios and " +
    "report an average improvement over a fixed plan. Three questions are rarely answered: whether timing logic that " +
    "varies green keeps safe change intervals, how emergency priority interacts with density-based timing, and how the " +
    "controller behaves as demand approaches and exceeds capacity. A fourth is how much of a reported gain is due to " +
    "the density logic at all, rather than to replacing an untuned fixed plan with any demand-responsive one."),
  I.para("**Novelty and difference from existing approaches.** Rather than proposing a new detector, this paper " +
    "studies the timing logic of a density-based controller under controlled, statistically paired conditions, " +
    "against re-implementations of the strategies used by existing approaches (a Webster-optimized fixed plan [2], " +
    "vehicle-actuated control [23], max-pressure control [11] and the three-level density control of [1]) on " +
    "identical traffic. The evaluation exposes a failure mode of density-only switching near capacity, which we " +
    "correct with a discharge-hold rule taken from actuated control. Its contributions are:"),
  I.bullet("a class-weighted, queue-aware density score and a bounded green-extension controller that never shortens " +
    "yellow or all-red intervals and guarantees a maximum red time for every approach;"),
  I.bullet("a discharge-hold extension that removes the capacity loss of density-only switching near saturation;"),
  I.bullet("an emergency preemption layer that wraps any phase-based controller and keeps full change intervals on " +
    "entry and exit, with a per-step signal audit that checks these properties in every run;"),
  I.bullet("a reproducible evaluation: paired seeded runs at three demand levels below capacity and a sweep from 0.6 " +
    "to 1.5 times the measured capacity, a comparison with four re-implemented strategies, an ablation of the density " +
    "score and the hold rule, and the cost of preemption to other traffic;"),
  I.bullet("a lightweight Haar-cascade detection and tracking pipeline, evaluated against exact ground truth with " +
    "detector and tracker ablations, failure cases and tracked-speed error;"),
  I.bullet("a validation of the simulated queue discharge against Highway Capacity Manual values, a reaction-time " +
    "calibration that matches them, and a repeat of the main comparisons under the calibrated kinematics."),
  I.para("All results were obtained in simulation; no hardware prototype or recorded field footage was used. The " +
    "simulator, controllers and every experiment script are public, and each table can be regenerated from them " +
    "(github.com/shivam-G05/Smart-Traffic-Management). Section II reviews related work, Section III describes the " +
    "architecture and workflow, Section IV the models and algorithms, and Section V the experiments. Section VI " +
    "discusses implications and limitations and Section VII concludes."),
);

// II. Related work -------------------------------------------------------------
add(
  I.heading("Related Work"),
  I.subheading("Adaptive Signal Control"),
  I.para("Fixed-time plans are commonly derived from Webster's delay-minimizing cycle formula [2]. SCATS and SCOOT " +
    "adapt splits, cycle lengths and offsets across networks from loop-detector data [3], [4]. Vehicle-actuated " +
    "control extends a green while detectors near the stop line keep registering vehicles and ends it when a gap " +
    "appears (\"gap-out\"), within minimum and maximum green limits [23]. Max-pressure control chooses phases from " +
    "queue differences and has provable throughput guarantees [11], and reinforcement-learning controllers have been " +
    "studied widely, although they must be trained in simulation and their behavior is harder to bound [12]. The " +
    "controller studied here is deliberately simpler: a local, rule-based green extension with hard limits whose " +
    "behavior can be stated and checked exactly, compared directly against the Webster, actuated and max-pressure " +
    "strategies in Section V."),
  I.subheading("Low-Cost Density-Based Systems"),
  I.para("Nsofwa and Tembo classify image-based density into low, medium and high levels and adjust signal duration, " +
    "showing in simulation that this outperforms fixed timing [1]. Kamble et al. apply YOLO-based recognition to " +
    "IP-camera feeds to prioritize the busiest lane [6]; such detectors [7] are accurate but demanding on low-power " +
    "hardware. Pardeshi et al. use passive infrared sensors on an ESP32 [5], and Patil et al. and Thomas et al. also " +
    "adapt timing to measured density [9], [10]. Hu et al. estimate density from surveillance cameras [8], and related " +
    "systems add incident detection and alerting [13], AI-based light design [14] or machine-learning traffic " +
    "prediction on the Edge Impulse platform [15]. These works mainly report an improvement over fixed timing on a " +
    "prototype or a few scenarios. This paper differs in three ways: it compares against strong baselines on identical " +
    "traffic, it tests demand up to 1.5 times capacity, and it verifies change-interval safety at every simulation step."),
  I.subheading("Detection, Tracking and Emergency Priority"),
  I.para("Viola and Jones introduced boosted cascades of Haar-like features [16], which remain attractive for " +
    "embedded use because inference is cheap and needs no GPU. ByteTrack associates both high- and low-confidence " +
    "detections with existing tracks [17]; trackers of this family combine a Kalman filter for motion prediction [18] " +
    "with Hungarian assignment [19]. Nellore and Hancke give emergency vehicles signal priority based on visual " +
    "sensing [20]."),
);

// III. Architecture and workflow --------------------------------------------
add(
  I.heading("System Architecture and Workflow"),
  I.para("Fig. 1 shows the software architecture. It consists of Python packages with one-directional dependencies: " +
    "the simulation core imports no decision, analytics or web code, and every signal controller implements one " +
    "interface (an update per time step and a phase name). The fixed-time, adaptive and comparison controllers can " +
    "therefore be exchanged without changes elsewhere. The code uses Python 3.12 (NumPy, SciPy, OpenCV, FastAPI, " +
    "SQLAlchemy with SQLite) and a React dashboard, and has 101 automated tests."),
  I.figure(FIG("fig1_architecture.png"), 3.3, "Software architecture. Solid boxes form the control loop; dashed boxes " +
    "form the vision pipeline, whose output is displayed and evaluated but not used for control in this study.", 1),
  I.runIn("Simulation core", "The simulator advances the junction in 50 ms steps. In each step the active controller " +
    "first sets the light of every approach, and then all vehicles move."),
  I.runIn("Density and control", "The density estimator scores each approach from the current vehicle states " +
    "(Section IV-B). The controller uses the scores to decide when to end a green (Sections IV-C and IV-D), and the " +
    "preemption wrapper overrides it when an emergency vehicle approaches (Section IV-F)."),
  I.runIn("Vision pipeline", "At 2 Hz a virtual camera per approach renders the 60 m before the stop line; the frame is " +
    "passed to the detector and tracker (Section IV-G). The results are shown on the dashboard and compared with " +
    "ground truth, but control decisions use the simulator's vehicle states, which corresponds to ideal detection."),
  I.runIn("Backend and dashboard", "A FastAPI server streams the junction state over WebSockets at 10 Hz, samples " +
    "queue, delay, throughput and congestion level at 1 Hz, stores a snapshot in SQLite every 10 s, and exports reports " +
    "as CSV or JSON. A React dashboard draws the junction to scale, raises a high-traffic alert when an approach stays " +
    "at high density for 3 s, explains each displayed quantity, and shows a live comparison in which a second " +
    "simulation with the same random seed runs another controller."),
  I.runIn("Method workflow", "Fig. 2 summarizes the method. In every step the controller senses vehicle positions, " +
    "speeds and classes, scores each approach, and decides whether the current green may end (Fig. 2b); the " +
    "preemption layer then protects every transition with full yellow and all-red intervals before the signal heads " +
    "change."),
  I.figure(FIG("fig2_workflow.png"), 3.3, "Method workflow. (a) The per-step control pipeline. (b) The green-end " +
    "decision; the test marked \"discharge hold (new)\" (Section IV-D) is the extension added in this revision, and the " +
    "original controller skips it.", 2),
);

// IV. Methodology --------------------------------------------------------------
add(
  I.heading("Methodology"),
  I.subheading("Junction and Traffic Model"),
  I.para("The junction has four approaches, each with two lanes on a 330 m link; the stop line is at 200 m and the " +
    "far edge of the junction box at 218 m. Vehicles travel straight through; turning movements, lane changes and " +
    "pedestrians are not modelled. Vehicles arrive on each approach at a mean rate λ with deterministic headways " +
    "(one vehicle every 1/λ s); to create shifting imbalance, every 15 s the rate of each approach is redrawn as " +
    "λ·*U*(0.4, 1.6), with a floor of 0.02 veh/s. An arriving vehicle enters a lane at rest and is dropped if the rear " +
    "of the previous vehicle is still within 8 m. For the above-capacity experiments (Section V-D) two options are " +
    "enabled instead: a blocked arrival waits in an entry queue and enters as soon as there is room, so that unserved " +
    "demand and its waiting time are measured, and a vehicle enters at the highest speed from which it can still stop " +
    "behind its leader, so that the link entry does not cap the flow below the signal's capacity. Table I lists the " +
    "vehicle classes."),
  I.table(1, "Vehicle classes and parameters",
    ["Class", "Share (%)", "Length (m)", "*v*_{max} (m/s)", "*a* (m/s²)", "*b* (m/s²)", "Weight *w*"],
    [["Car", "55", "4.5", "14", "2.5", "4.5", "1.0"], ["Motorcycle", "25", "2.0", "15", "3.5", "5.0", "0.5"],
      ["Auto-rickshaw", "10", "3.2", "11", "2.0", "4.0", "0.8"], ["Bus", "5", "10.0", "10", "1.2", "3.0", "3.0"],
      ["Truck", "4", "9.0", "9", "1.0", "2.8", "2.5"], ["Ambulance", "0.5", "5.5", "16", "3.0", "5.0", "6.0"],
      ["Fire truck", "0.5", "10.5", "12", "1.5", "3.5", "6.0"]],
    [1100, 640, 660, 660, 660, 660, 660],
    "a: maximum acceleration; b: maximum deceleration; w: density weight in (2)."),
  I.para("Longitudinal motion follows a Gipps-type safe-speed rule [21]. A follower's speed is limited to"),
  I.equation("*u*_{safe} = [2*b*(*g* + *u*_{l}²/(2*b*_{l}) − *s*_{0})]^{1/2}", 1),
  I.para("where *g* is the gap to the leader's rear, *u*_{l} and *b*_{l} are the leader's speed and maximum " +
    "deceleration, *b* is the follower's maximum deceleration and *s*_{0} = 2 m is the standstill gap. A position " +
    "constraint prevents any overlap within a step. On yellow or red, a vehicle upstream of the stop line brakes once " +
    "its braking distance reaches the distance to the line; a vehicle too close to stop continues. Rule (1) has no " +
    "driver reaction time; Section V-H shows that this makes queues discharge too fast, adds a reaction time τ, " +
    "and repeats the main comparisons with it.", { noIndent: true }),
  I.subheading("Density Estimation"),
  I.para("For approach *r* with vehicle set *V*_{r}, the density score is"),
  I.equation("*D*_{r} = Σ_{v∈Vr} *w*_{c(v)} · *m*(*v*)", 2),
  I.para("where *w*_{c(v)} is the class weight (Table I) and *m*(*v*) = 1.5 if vehicle *v* is queued and 0.5 " +
    "otherwise. A vehicle is queued when it is upstream of the stop line and slower than 0.5 m/s. The weights reflect " +
    "the road space and discharge time a vehicle class needs, and emergency vehicles receive a high weight so that " +
    "their approach is favored even without preemption. A queued vehicle counts three times as much as a moving one " +
    "because it needs green now, whereas a moving vehicle may still be far upstream. The weights are heuristic; " +
    "Section V-F measures the contribution of each part of the score. For display, an approach is labelled low " +
    "(*D*_{r} ≤ 3), medium (3 < *D*_{r} ≤ 6) or high (*D*_{r} > 6).", { noIndent: true }),
  I.subheading("Adaptive Green Extension"),
  I.para("The controller uses a two-phase plan: north–south green, yellow (*Y* = 3 s), all-red (*A* = 1 s), then " +
    "east–west green, yellow and all-red. Only the green duration adapts. Let *t*_{g} be the elapsed green time, and " +
    "*D*_{A} and *D*_{W} the summed scores of the active and the waiting direction. At every step the green ends when"),
  I.equation("*t*_{g} ≥ *G*_{max}  or  (*t*_{g} ≥ *G*_{min}  and  *D*_{A} ≤ θ*D*_{W})", 3),
  I.para("with *G*_{min} = 8 s, *G*_{max} = 45 s and θ = 1.1. The green is thus extended while the served direction's " +
    "score exceeds the waiting direction's by more than 10%. Because yellow and all-red are fixed and green is " +
    "capped, the red time of any approach in normal operation is bounded by", { noIndent: true }),
  I.equation("*R*_{max} = *A* + *G*_{max} + *Y* + *A* = 50 s", 4),
  I.para("so no approach can be starved. The fixed-time baseline uses the same sequence with a 20 s green (48 s cycle).",
    { noIndent: true }),
  I.subheading("Discharge Hold"),
  I.para("Rule (3) has a weakness that the above-capacity experiments expose (Section V-D). When both directions are " +
    "saturated, the vehicles moving off on green score 0.5 each while the queue growing on red scores 1.5 each, so " +
    "*D*_{A} ≤ θ*D*_{W} holds soon after *G*_{min} and greens stay short; each phase change costs *Y* + *A* = 4 s in " +
    "which no vehicle is served, so short greens lose capacity exactly when it is scarcest. The discharge hold adds " +
    "the gap-out test of actuated control [23]: past the minimum, a green may only end once the served direction has " +
    "gapped out, i.e. no served vehicle is within *z* of its stop line,"),
  I.equation("*t*_{g} ≥ *G*_{max}  or  (*t*_{g} ≥ *G*_{min}  and  *n*_{z} = 0  and  *D*_{A} ≤ θ*D*_{W})", 5),
  I.para("where *n*_{z} is the number of served vehicles within *z* = 10 m upstream of the stop line. A saturated queue " +
    "moving off always keeps a vehicle at the line and so keeps its green up to *G*_{max}, while free-flowing arrivals " +
    "cross 10 m in under a second, so a cleared queue still hands over early. The zone length was chosen from 10, 15, 20 " +
    "and 30 m on a separate tuning seed that is not used in any reported result. Yellow, all-red and the green limits " +
    "are unchanged, so bound (4) still holds.", { noIndent: true }),
  I.subheading("Comparison Controllers"),
  I.para("To compare against existing approaches (Section II), four strategies were re-implemented in the same " +
    "simulator. They are not the original systems: like the proposed controller they read exact vehicle states, and " +
    "all share its phase sequence, its 3 s yellow and 1 s all-red, and its 8–45 s green limits, so every one obeys bound " +
    "(4) and the comparison isolates the switching decision."),
  I.runIn("Webster fixed", "a fixed plan whose green follows Webster's formula [2] for the mean demand of each run: " +
    "*C*_{0} = (1.5*L* + 5)/(1 − *Y*), with lost time *L* = 8 s, *Y* the sum of the critical flow ratios *q*/*s*, the " +
    "saturation flow *s* = 6000 veh/h per approach measured in the simulator, and each phase receiving (*C*_{0} − *L*)/2, " +
    "clamped to 8–45 s. It knows the true mean demand of the run, which favors it."),
  I.runIn("Actuated", "past the minimum, the green ends as soon as the served direction gaps out (no vehicle within " +
    "10 m of its stop line) and a vehicle waits on the other direction [23]; no density score is used."),
  I.runIn("Max-pressure", "the pressure of a phase is the number of vehicles upstream of its stop lines minus those " +
    "downstream, which is zero with free exits [11]; past the minimum the controller switches as soon as the waiting " +
    "phase's pressure exceeds the served one's. This also represents busiest-lane-first control [6]."),
  I.runIn("Density levels", "following [1], when a green starts the served direction's density is classed low, medium " +
    "or high (thresholds of Section IV-B) and the green is set to 10, 20 or 30 s, without revision during the green."),
  I.subheading("Emergency Vehicle Preemption"),
  I.para("Preemption is a wrapper around any phase-based controller (Fig. 3). Without an emergency vehicle it passes " +
    "control to the inner controller. When an ambulance or fire truck is upstream of the junction exit, it acts as follows."),
  I.figure(FIG("fig3_preemption.png"), 3.3, "Emergency preemption states. Every path from one direction's green to the " +
    "other's passes through a full yellow and all-red interval.", 3),
  I.bullet("Entry: a conflicting green first shows a full 3 s yellow, and a yellow already showing keeps its remaining " +
    "time; all approaches are then red for 1 s, or for the remainder of an all-red already under way. If the emergency " +
    "vehicle's approach is already green, that green is held."),
  I.bullet("Priority green: the emergency vehicle's direction (both opposing approaches) is green until no emergency " +
    "vehicle remains before the junction exit, or for at most 20 s."),
  I.bullet("Release: the priority green ends with a full yellow and all-red, after which the inner controller restarts " +
    "at the green of the direction that was held."),
  I.bullet("Minimum green: a green shown for less than 5 s is never cut, and an approach that already has green is " +
    "served first."),
  I.para("Emergency vehicles are detected from the simulator state, i.e., perfect detection is assumed; in practice the " +
    "input could come from vehicle-to-infrastructure messages or visual sensing. When no other preemption is active, an " +
    "emergency vehicle waits at most 5 + 3 + 1 = 9 s for its priority green."),
  I.subheading("Vision Pipeline"),
  I.para("For each approach a virtual camera renders a 200 × 240 pixel frame of the 60 m before the stop line (4 px/m). " +
    "Vehicles appear as shaded rectangles with a windshield band on a noisy road texture with lane markings. The " +
    "detector converts the frame to grayscale, equalizes its histogram, upscales it three times, and applies OpenCV's " +
    "cascade classifier with a pre-trained vehicle cascade (scale factor 1.05, minimum neighbors 2, minimum size 20 px); " +
    "the final-stage weight, clipped to [0, 1], serves as a relative confidence. A single cascade localizes vehicles " +
    "but does not classify them, so on its own it cannot supply the class weights of (2)."),
  I.para("The tracker keeps a constant-velocity Kalman filter on each box center and matches predicted boxes to " +
    "detections with the Hungarian algorithm on an IoU cost (minimum IoU 0.15). As in ByteTrack, detections with " +
    "confidence ≥ 0.15 are matched first and the remaining low-confidence detections are then matched to still-unmatched " +
    "tracks; only confident detections start tracks. A track is confirmed after two matches and deleted after three " +
    "frames without one."),
  I.runIn("Data and annotation protocol", "No real images are used. Frames are rendered from the simulator state, and " +
    "the ground-truth box of every vehicle in view is computed from the same state, so annotation is automatic, exact " +
    "and involves no manual labelling. A detection is correct when its center lies inside a ground-truth box enlarged " +
    "by 4 px; each detection matches at most one vehicle, the nearest. Nothing is trained: the cascade is pre-trained, " +
    "and the detector and tracker parameters were fixed during development in unseeded runs, so there is no training " +
    "split; seeds 1–4 are used only for the evaluation in Section V-G. A track's speed is its Kalman velocity " +
    "converted to m/s (4 px/m) and is compared with the vehicle's true speed."),
);

// V. Experiments ---------------------------------------------------------------
const highRatio = R(1.2), capRatio = R(1.0), r09 = R(0.9), r06 = R(0.6), r15 = R(1.5), r08 = R(0.8);
const t2Rows = CTRL.map((c) => [L[c],
  ...LV.map((lv) => T2[c][lv].mean_delay_s.ci),
  minus(T2[c].high.mean_delay_s.vs_fixed.text),
  T2[c].high.p95_delay_s.ci, T2[c].high.mean_green_s.ci.split(" ")[0]]);

add(
  I.heading("Experimental Evaluation"),
  I.subheading("Setup"),
  I.para("Three demand levels below capacity were simulated: λ = 0.08, 0.12 and 0.18 veh/s per approach (1152, 1728 " +
    "and 2592 veh/h offered to the junction). For each level and controller, ten random seeds were run for 1800 s with " +
    "a 50 ms step. A seed gives every controller the same arrival sequence, so runs form matched pairs. The first 60 s " +
    "are a warm-up, and delay statistics use the vehicles entering between 60 s and 1650 s, all of which left the " +
    "network before the end of their run. Stopped delay is the time a vehicle spends upstream of the stop line below " +
    "0.5 m/s; because vehicles enter at rest it includes a start-up component of 0.15–0.55 s that is the same for all " +
    "controllers. Per-seed values are compared with paired t-tests over the ten seeds, and 95% confidence intervals " +
    "are given. Preemption is enabled for all controllers unless stated."),
  I.para("For the above-capacity experiments, the capacity of each controller was first measured by flooding every " +
    "approach (1.5 arrivals/s; five seeds); demand was then set to 0.6, 0.8, 0.9, 1.0, 1.2 and 1.5 times the measured " +
    `fixed-time capacity, with ten paired seeds per level. In total ${S.total_runs.toLocaleString("en-US")} runs ` +
    `(${S.total_hours.toLocaleString("en-US")} simulated hours) were made. Separate seeds were used for tuning (seed 1000), ` +
    "capacity measurement (101–105) and the reported results (1–10)."),
  I.subheading("Signal Safety Audit"),
  I.para("Every step of every run was checked for conflicting greens, green-to-red transitions without yellow, yellows " +
    "shorter than 3 s and all-red intervals shorter than 1 s before a conflicting green. Across all " +
    `${S.total_runs.toLocaleString("en-US")} runs, covering all seven controllers and ` +
    `${(S.table2_on.preemptions).toLocaleString("en-US")} preemption events in the main runs alone, none of these ` +
    "violations occurred. An earlier version of the preemption layer returned control to the inner controller without " +
    "a release interval; this audit exposed the resulting skipped yellows, which led to the release states of Fig. 3."),
  I.subheading("Comparison Below Capacity"),
  I.para(`Table II compares all controllers at the three demand levels. The proposed adaptive controller reduced mean ` +
    `stopped delay by ${redu("adaptive")} relative to the 20 s fixed plan, with lower delay in all ten seeds at every ` +
    `level (p < 0.001), and the 95th-percentile delay fell by ${range(LV.map((lv) => -T2.adaptive[lv].p95_delay_s.vs_fixed.pct))}. ` +
    `However, the Webster plan, actuated control and max-pressure control achieved the same or slightly lower delay ` +
    `(${redu("webster")}, ${redu("actuated")} and ${redu("max_pressure")} below the fixed plan). Relative to the adaptive ` +
    `controller their delay differed by ${range(LV.flatMap((lv) => ["webster", "actuated", "max_pressure"].map((c) => T2[c][lv].mean_delay_s.vs_adaptive.pct)))}. ` +
    `Below capacity, therefore, most of the gain comes from replacing an untuned 20 s plan with shorter, demand-responsive ` +
    `greens (mean adaptive green ${T2.adaptive.medium.mean_green_s.ci.split(" ")[0]} s), which any of these strategies ` +
    `provides. Three-level density control was worse than the fixed plan at medium and high demand ` +
    `(${pct(T2.density_levels.medium.mean_delay_s.vs_fixed.pct)} and ${pct(T2.density_levels.high.mean_delay_s.vs_fixed.pct)}), ` +
    `because its greens of 20–30 s for medium and high density outlast the queue. The discharge hold left delay ` +
    `essentially unchanged at these levels (${range(LV.map((lv) => T2.adaptive_hold[lv].mean_delay_s.vs_adaptive.pct))} ` +
    `relative to the adaptive controller). Throughput changed by at most ` +
    `${range(CTRL.flatMap((c) => LV.map((lv) => Math.abs(T2[c][lv].throughput_vph.vs_fixed.pct)))).split("–").pop()} ` +
    `because all three levels are far below capacity.`),
  I.table(2, "Controllers below capacity (preemption enabled)",
    ["Controller", "Delay low (s)", "Delay medium (s)", "Delay high (s)", "High vs fixed", "95th pct. high (s)", "Green (s)"],
    t2Rows, [1180, 820, 820, 820, 680, 760, 460],
    "Mean ± 95% confidence interval over ten paired seeds. All changes relative to the fixed plan are significant (p < 0.001) " +
    `except density levels at low demand (p = ${T2.density_levels.low.mean_delay_s.vs_fixed.p}). Green: mean green at high demand.`),
);

// Above capacity
const capRows = CTRL.filter((c) => O.capacity[c]).map((c) => [L[c], O.capacity[c].ci,
  c === "fixed" ? "—" : `${minus(O.capacity[c].vs_fixed.text)}`, O.capacity[c].green,
  Oon.capacity[c] ? Oon.capacity[c].ci : "—"]);
const sweepCtrl = ["fixed", "webster", "actuated", "max_pressure", "adaptive", "adaptive_hold"];
const sweepRows = sweepCtrl.map((c) => [L[c], ...ratios.map((r) => sw(r, c, "delay_all_lb_s").mean.toFixed(1))]);
const thruRows = sweepCtrl.map((c) => [L[c], ...ratios.map((r) => Math.round(sw(r, c, "throughput_vph").mean).toString())]);

add(
  I.subheading("Operation Near and Above Capacity"),
  I.para("The three demand levels of Table II are only " +
    `${(1152 / O.capacity.fixed.mean * 100).toFixed(0)}–${(2592 / O.capacity.fixed.mean * 100).toFixed(0)}% of the ` +
    "junction's measured fixed-time capacity, so they cannot show congestion. Table III gives the capacity of each " +
    "controller; these runs and Table IV use preemption off, because emergency vehicles make up 1% of arrivals and at " +
    "these demands trigger a preemption every 15–30 s, which would otherwise dominate the timing of every controller."),
  I.table(3, "Capacity of each controller",
    ["Controller", "Capacity, preempt. off (veh/h)", "vs fixed", "Mean green (s)", "Capacity, preempt. on (veh/h)"],
    capRows, [1250, 1300, 900, 700, 1300],
    "Every approach flooded at 1.5 arrivals/s; five seeds; throughput after the 60 s warm-up."),
  I.para(`The proposed controller lost ${abspct(O.capacity.adaptive.vs_fixed.pct)} of capacity relative to fixed timing ` +
    `(p ${O.capacity.adaptive.vs_fixed.p}): with both directions saturated its greens fell to the 8 s minimum ` +
    `(mean ${O.capacity.adaptive.green} s), as explained in Section IV-D. With the discharge hold the mean saturated green ` +
    `rose to ${O.capacity.adaptive_hold.green} s and capacity to ${pct(O.capacity.adaptive_hold.vs_fixed.pct)} relative ` +
    `to fixed timing. Max-pressure control suffered the same loss as the original rule ` +
    `(${pct(O.capacity.max_pressure.vs_fixed.pct)}), since moving vehicles also leave its pressure count as the queue ` +
    `discharges, whereas actuated control (${pct(O.capacity.actuated.vs_fixed.pct)}) and the Webster plan ` +
    `(${pct(O.capacity.webster.vs_fixed.pct)}), which runs the maximum green above capacity, did not.`),
  I.table(4, "Delay including vehicles still waiting (s), preemption off",
    ["Controller", ...ratios.map((r) => `${parseFloat(r)}×`)], sweepRows, [1400, ...ratios.map(() => 600)],
    "Demand as a multiple of the fixed-time capacity; mean over ten paired seeds. Vehicles still waiting at the end of a " +
    "run count with the delay accrued so far, so values above capacity are lower bounds."),
  ...I.figure(FIG("fig5_above_capacity.png"), 3.3, "Delay (top, log scale) and throughput (bottom) against demand, " +
    "preemption off. The dotted line marks the fixed-time capacity.", 4),
  I.para(`Table IV and Fig. 4 show the consequence. The original adaptive controller's advantage disappeared by 0.8× ` +
    `capacity and reversed from 0.9×: at capacity its delay was ${sw(capRatio, "adaptive", "delay_all_lb_s").mean.toFixed(1)} s ` +
    `against ${sw(capRatio, "fixed", "delay_all_lb_s").mean.toFixed(1)} s for the fixed plan, its queue grew by ` +
    `${sw(capRatio, "adaptive", "queue_growth_vpm").mean.toFixed(1)} vehicles per minute, and queues reached the start of ` +
    `the link during ${sw(capRatio, "adaptive", "spillback_pct").mean.toFixed(0)}% of approach-time. With the discharge ` +
    `hold, delay was below fixed timing at every level (${ratios.map((r) => minus(sw(r, "adaptive_hold", "delay_all_lb_s").vs_fixed.text)).join(", ")} ` +
    `from 0.6× to 1.5×; the difference at 1.0× was not significant, p = ${sw(capRatio, "adaptive_hold", "delay_all_lb_s").vs_fixed.p}) ` +
    `and throughput above capacity rose by ${pct(sw(highRatio, "adaptive_hold", "throughput_vph").vs_fixed.pct)} ` +
    `and ${pct(sw(r15, "adaptive_hold", "throughput_vph").vs_fixed.pct)} at 1.2× and 1.5×. ` +
    `Among the comparison strategies, actuated control behaved similarly to the hold controller ` +
    `(${sw(capRatio, "actuated", "delay_all_lb_s").mean.toFixed(1)} s at capacity, ${sw(highRatio, "actuated", "delay_all_lb_s").mean.toFixed(1)} s at 1.2×, ` +
    `against ${sw(capRatio, "adaptive_hold", "delay_all_lb_s").mean.toFixed(1)} s and ${sw(highRatio, "adaptive_hold", "delay_all_lb_s").mean.toFixed(1)} s), ` +
    `and max-pressure control degraded like the original rule. With preemption enabled the same pattern held with ` +
    `smaller margins (capacity ${pct(Oon.capacity.adaptive.vs_fixed.pct)} for the original rule and ` +
    `${pct(Oon.capacity.adaptive_hold.vs_fixed.pct)} with the hold), because preemption also cuts the hold's long greens.`),
);

// Emergency preemption
const T3 = N.table3;
const t3Rows = [];
for (const lv of LV) {
  for (const c of ["fixed", "adaptive", "adaptive_hold"]) {
    const x = T3[c][lv];
    t3Rows.push([`${lv[0].toUpperCase()}${lv.slice(1)}`, L[c], `${x.ev_off}/${x.ev_on}`,
      `${x.ev_delay_off}→${x.ev_delay_on}`, `${x.other_off}→${x.other_on}`,
      `${minus(x.other_change.text)} (${x.other_change.p})`]);
  }
}
add(
  I.subheading("Emergency Preemption"),
  I.para(`Emergency vehicles made up 1% of arrivals and triggered ${range(LV.map((lv) => T3.adaptive[lv].preemptions_per_hour)).replace(/%/g, "")} ` +
    "preemptions per hour under adaptive control (Table V). Preemption reduced their mean stopped delay to the start-up " +
    "component of the metric under every controller. The cost to other traffic depends on the controller: it is small " +
    "under fixed timing, and larger under adaptive control because each preemption discards the density-responsive " +
    "timing and restarts the plan at a fixed phase. Emergency vehicles are far more frequent here than in normal " +
    "traffic, so the aggregate cost at a real junction would be expected to be smaller."),
  I.table(5, "Effect of emergency preemption",
    ["Demand", "Controller", "EVs off/on", "EV delay (s) off→on", "Other delay (s) off→on", "Other change (p)"],
    t3Rows, [760, 1150, 720, 1000, 1000, 1110],
    "EV: emergency vehicles measured, pooled over ten seeds (EV delay: Mann–Whitney U test p ≤ " +
    `${["fixed", "adaptive", "adaptive_hold"].flatMap((c) => LV.map((lv) => T3[c][lv].ev_p)).filter((p) => p !== "< 0.001").sort().pop() || "0.001"}). ` +
    "Other change: paired change in the mean delay of all other vehicles, paired t-test p-value in parentheses."),
);

// Ablation
const ablRows = N.ablation.map((r) => [r.variant, r.level, r.delay, r.change, r.p, r.green]);
const abl = (v, lv) => N.ablation.find((r) => r.variant.startsWith(v) && r.level === lv);
add(
  I.subheading("Ablation"),
  I.para("Table VI changes one part of the controller at a time, on the same paired seeds. Counting vehicles without " +
    `weights or multipliers raised delay by ${abspct(abl("Unweighted", "medium").pct)} and ${abspct(abl("Unweighted", "high").pct)} ` +
    "at medium and high demand. Removing the parts separately shows where this comes from: without the queued/moving " +
    `distinction delay rose by ${abspct(abl("No queued", "medium").pct)} and ${abspct(abl("No queued", "high").pct)}, ` +
    `whereas setting every class weight to 1 changed it by ${pct(abl("No class", "medium").pct)} and ${pct(abl("No class", "high").pct)}. ` +
    "The benefit of the score therefore comes from distinguishing queued from moving vehicles, not from the class " +
    "weights, which did not help and need calibration before use (Section VI-B). The ratio θ mattered little, and the " +
    "discharge hold, with any zone length, did not change delay below capacity, where its benefit is not needed."),
  I.table(6, "Ablation of the adaptive controller", ["Variant", "Demand", "Mean delay (s)", "Change", "p", "Green (s)"],
    ablRows, [2080, 640, 900, 640, 560, 500],
    "Preemption enabled unless stated; ten paired seeds per row; change relative to the reference at the same demand."),
);

// Vision (Reviewer 2: ground truth, ablations, protocol, failure cases)
const V = N.vision;
const detEntries = Object.entries(V.detectors);
const det0 = detEntries[0][1];
const trkEntries = Object.entries(V.tracking);
const trk0 = trkEntries[0][1];
const f1 = (x) => (x === null || Number.isNaN(x) ? "n/a" : x.toFixed(1));
const classRecall = Object.entries(V.by_class).map(([c, v]) => `${c} ${f1(v.recall)}%`).join(", ");
const distRecall = Object.entries(V.by_distance).map(([k, v]) => `${k} ${f1(v.recall)}%`).join(", ");
add(
  I.subheading("Vision Pipeline: Accuracy, Failure Cases and Ablation"),
  I.para(`The vision pipeline was evaluated on seeds 1–4 (${det0.frames.toLocaleString("en-US")} frames, ` +
    `${det0.gt_instances.toLocaleString("en-US")} vehicle instances in view) with the protocol of Section IV-G. On these ` +
    `synthetic frames the generic cascade performed poorly: precision was ${f1(det0.precision)}% and recall ` +
    `${f1(det0.recall)}% (Table VII). The failure cases are systematic. ${f1(V.failure.persistent_background_share)}% of ` +
    "the false positives recur at the same spot in at least 10% of a camera's frames, i.e. the cascade fires on fixed " +
    `background texture rather than on vehicles. Recall varies by class (${classRecall}) and by distance from the stop ` +
    `line (${distRecall}). Without upscaling, or without histogram equalization, the cascade found almost nothing, which ` +
    "is why both pre-processing steps are used."),
  I.table(7, "Detector accuracy and ablation (synthetic frames)",
    ["Detector variant", "Precision (%)", "Recall (%)", "Detections per frame"],
    detEntries.map(([name, d]) => [name, f1(d.precision), f1(d.recall), d.detections_per_frame.toFixed(2)]),
    [2300, 900, 900, 900],
    "Pooled over seeds 1–4; a detection is correct when its center lies inside a ground-truth box enlarged by 4 px."),
  I.para(`Tracking was evaluated on the default detector's output (Table VIII). Only ${f1(trk0.coverage)}% of the ` +
    `vehicle instances in view carried a confirmed track, and ${f1(trk0.vehicles_confirmed)}% of the vehicles were ` +
    "confirmed at least once. For confirmed tracks on real vehicles, the tracked speed was compared with the true speed: " +
    (trk0.speed_mae !== null
      ? `the mean absolute error was ${trk0.speed_mae.toFixed(2)} m/s over ${trk0.speed_n} estimates, against a mean true ` +
        `speed of ${trk0.true_speed_mean.toFixed(2)} m/s. `
      : "too few confirmed tracks had enough matches for a speed estimate. ") +
    "Dropping the low-confidence second matching stage or the motion model changed coverage little, because the " +
    "limiting factor is the detector's recall, not the association; confirming tracks after one match raised coverage " +
    "but also confirmed single-frame false positives. These results are why the evaluated controllers read vehicle " +
    "states from the simulator: a class-aware detector trained on the target imagery is needed before detections can " +
    "drive control, and accuracy on real footage is unknown. On an Intel Core i5-12450H laptop CPU, detection took about " +
    "137 ms per frame in a single process, whereas a control decision took 0.01 ms; a Raspberry Pi 4 is estimated, not " +
    "measured, to be 5–10 times slower."),
  I.table(8, "Tracking quality and tracked-speed error",
    ["Tracker variant", "Coverage (%)", "Vehicles confirmed (%)", "ID switches /100 veh.", "Speed MAE (m/s)"],
    trkEntries.map(([name, t]) => [name, f1(t.coverage), f1(t.vehicles_confirmed), f1(t.id_switches_per_100_vehicles),
      t.speed_mae === null ? "n/a" : t.speed_mae.toFixed(2)]),
    [1900, 800, 900, 800, 600],
    "Coverage: share of vehicle instances in view with a confirmed track. Speed MAE: confirmed tracks on real vehicles " +
    "with at least three matches; n/a where the variant has no motion estimate."),
);

// Kinematics validation (Reviewer 2: validate against external ground truth)
const K0 = N.kinematics.tau0;
const K1 = N.kinematics.tau16;
const kc0 = K0["cars only"], km0 = K0["full vehicle mix"], kc1 = K1["cars only"], km1 = K1["full vehicle mix"];
const TC = N.table2_cal;
const OC = N.over_cal;
const reduCal = (c) => range(LV.map((lv) => -TC[c][lv].mean_delay_s.vs_fixed.pct));
const calCtrl = ["webster", "actuated", "max_pressure", "density_levels", "adaptive", "adaptive_hold"];
add(
  I.subheading("Validation of the Simulated Kinematics"),
  I.para("To check the simulator's kinematics against external values, queue discharge was measured as at a real " +
    "junction: the time between successive queued vehicles crossing the stop line after the green starts, in " +
    "saturated fixed-time runs (five seeds, greens with at least eight queued vehicles in the lane). The headway from " +
    "the fifth vehicle on gives the saturation headway, and the extra time of the first four the start-up lost time. " +
    "The Highway Capacity Manual's base values are 1900 passenger cars per hour per lane (a 1.89 s headway) and a " +
    `start-up lost time of about 2 s [24]. The model used so far discharges cars every ${kc0.saturation_headway_s.toFixed(2)} s ` +
    `(${kc0.saturation_flow_vphpl.toLocaleString("en-US")} veh/h/lane; Table IX): without a reaction time a follower may ` +
    "trail by only the 2 m standstill gap at any speed. Adding a driver reaction time τ to the safe speed (1), as in " +
    `Krauss's model [25], and setting τ = 1.6 s gives ${kc1.saturation_headway_s.toFixed(2)} s ` +
    `(${kc1.saturation_flow_vphpl.toLocaleString("en-US")} veh/h/lane) for cars, within ` +
    `${Math.abs(100 * (kc1.saturation_flow_vphpl - 1900) / 1900).toFixed(1)}% of the reference. The calibrated model ` +
    `still has no extra delay when a queue starts to move, so its start-up lost time (${kc1.startup_lost_time_s.toFixed(1)} s) ` +
    "is lower than in the field."),
  I.table(9, "Queue discharge against field reference values",
    ["Model", "Headway, cars (s)", "Sat. flow, cars (veh/h/ln)", "Sat. flow, all (veh/h/ln)", "Start-up lost time (s)"],
    [["Simulator, τ = 0 (used above)", kc0.saturation_headway_s.toFixed(2), kc0.saturation_flow_vphpl.toLocaleString("en-US"),
      km0.saturation_flow_vphpl.toLocaleString("en-US"), kc0.startup_lost_time_s.toFixed(1)],
    ["Simulator, τ = 1.6 s (calibrated)", kc1.saturation_headway_s.toFixed(2), kc1.saturation_flow_vphpl.toLocaleString("en-US"),
      km1.saturation_flow_vphpl.toLocaleString("en-US"), kc1.startup_lost_time_s.toFixed(1)],
    ["HCM base values [24]", "1.89", "1,900", "—", "≈ 2.0"]],
    [1700, 800, 900, 900, 700],
    "Saturated fixed-time runs, five seeds; saturation headway averaged from the fifth queued vehicle on."),
  I.para("All comparisons were then repeated with the calibrated model (τ = 1.6 s; the Webster plan recomputed with the " +
    "calibrated saturation flow of 3600 veh/h per approach). Table X summarizes them. Below capacity, the reductions " +
    `relative to the fixed plan were ${reduCal("adaptive")} for the adaptive controller and ${reduCal("webster")}, ` +
    `${reduCal("actuated")} and ${reduCal("max_pressure")} for the Webster plan, actuated and max-pressure control. ` +
    `The calibrated capacity of the fixed plan was ${OC.capacity.fixed.mean.toLocaleString("en-US")} veh/h; relative to ` +
    `it, the original adaptive rule reached ${pct(OC.capacity.adaptive.vs_fixed.pct)} and the discharge hold ` +
    `${pct(OC.capacity.adaptive_hold.vs_fixed.pct)}.`),
  I.table(10, "Main comparisons repeated with calibrated kinematics",
    ["Controller", "Delay vs fixed, low", "medium", "high", "Capacity vs fixed"],
    calCtrl.map((c) => [L[c], ...LV.map((lv) => minus(TC[c][lv].mean_delay_s.vs_fixed.text)),
      OC.capacity[c] ? minus(OC.capacity[c].vs_fixed.text) : "—"]),
    [1700, 900, 800, 800, 1000],
    "τ = 1.6 s; ten paired seeds per demand level (preemption on) and five capacity seeds (preemption off)."),
);

// VI. Discussion ---------------------------------------------------------------
add(
  I.heading("Discussion"),
  I.subheading("Implications"),
  I.para("Two results qualify the usual claim that density-based control beats fixed timing. Below capacity, the " +
    "gain over an untuned 20 s plan is real but not specific to density scoring: a Webster plan tuned to the demand, " +
    "actuated control and max-pressure control achieve the same. Near capacity, density-only switching is worse than " +
    "fixed timing, because it ends greens while the served queue is still discharging. With the discharge hold, the " +
    "proposed controller matches the best strategies below capacity and comes close to the highest capacity measured " +
    `(the Webster plan's, ${pct(O.capacity.webster.vs_fixed.pct)}), while keeping the properties that motivated it: its ` +
    "decisions follow a rule that can be stated in one line, its red time is bounded in closed form, and its safety is " +
    "audited at every step. Its results are, however, almost identical to plain actuated control, which uses no density " +
    "score at all: in this setting the gap-out test, not the score, does most of the work. The score's remaining role is " +
    "to decide when a cleared green should hand over, where Table VI shows that the queued/moving distinction matters. " +
    "Emergency priority and adaptive control " +
    "interact: resuming after preemption with the higher-scoring direction, rather than always the held one, is a " +
    "direct improvement to test."),
  I.subheading("Limitations"),
  I.bullet("Simulation only. The model has no turning movements, lane changes, pedestrians or driver variability and " +
    "has not been calibrated against field data, so absolute delays are not field predictions."),
  I.bullet("Kinematics. The model behind the main results has no driver reaction time, so its queues discharge much " +
    "faster than real ones (Table IX). A reaction time of 1.6 s matches the field saturation headway, and Section V-H " +
    "repeats the comparisons with it, but the calibrated model still lacks start-up delay, so its start-up lost time is " +
    "too low; with real start-up lost time, short greens would cost more, so the original rule's capacity loss is if " +
    "anything understated."),
  I.bullet("Arrival model. Arrivals follow deterministic headways at a rate redrawn every 15 s, not a Poisson process, " +
    "and emergency vehicles are far more frequent than in real traffic."),
  I.bullet("Comparison controllers. The baselines are re-implementations of the published strategies with ideal sensing, " +
    "not the original systems; the Webster plan is given the true mean demand of each run."),
  I.bullet("Ideal sensing. The controller and preemption layer read exact vehicle states. The vision pipeline was " +
    "tested only on synthetic frames and does not classify vehicles; real footage with lighting changes, occlusion " +
    "and weather is harder."),
  I.bullet("Heuristic parameters. The class weights, multipliers and congestion thresholds were set by hand; Section " +
    "V-F shows that the class weights do not help as set, so they need calibration against local passenger-car-unit " +
    "factors."),
  I.para("A planned Raspberry Pi 4 deployment, with one camera per approach and relay-driven signal heads, is estimated " +
    "at roughly INR 6,000–8,000 in components; this cost and the hardware timing in Table VII are estimates that must be " +
    "verified on actual hardware."),
);

// VII. Conclusion ----------------------------------------------------------------
add(
  I.heading("Conclusion"),
  I.para("This paper presented and evaluated a density-aware traffic signal controller with a class-weighted, " +
    "queue-aware density score, bounded green extension, a discharge-hold rule and an emergency preemption layer that " +
    "keeps full change intervals. Compared on identical seeded traffic with a fixed plan and four re-implemented " +
    `strategies, it reduced mean stopped delay below capacity by ${redu("adaptive")} relative to the 20 s fixed plan, as ` +
    "did a Webster-optimized plan, actuated and max-pressure control. Near capacity the original density rule lost " +
    `${abspct(O.capacity.adaptive.vs_fixed.pct)} of capacity; the discharge hold restored and exceeded the fixed plan's ` +
    `capacity (${pct(O.capacity.adaptive_hold.vs_fixed.pct)}) and gave lower delay than fixed timing from 0.6 to 1.5 ` +
    "times capacity. No run violated a change interval. The queued/moving distinction, not the class weights, accounted " +
    "for the benefit of the density score."),
  I.para("Future work will close the loop between detection and control with a class-aware detector trained on real " +
    "footage, calibrate the class weights against local passenger-car-unit factors, test the controller in an " +
    "established simulator such as SUMO [22] with turning traffic and stochastic arrivals, improve resumption after " +
    "preemption, and measure its performance on embedded hardware at a real junction."),
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
