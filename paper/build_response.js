// Builds the response-to-reviewers document
// (paper/out/Response_to_Reviewers_Paper2017.docx) from the numbers in
// paper/build/numbers.json. Run: node paper/build_response.js
const fs = require("fs");
const path = require("path");
const {
  AlignmentType, BorderStyle, Document, Packer, Paragraph, ShadingType, Table, TableCell, TableRow, TextRun, WidthType,
} = require("docx");
const { FONT, runs } = require("./ieee");

const HERE = __dirname;
// NUMBERS / OUT_DIR override the inputs and output folder (used for test builds).
const N = JSON.parse(fs.readFileSync(process.env.NUMBERS || path.join(HERE, "build", "numbers.json"), "utf8"));
const OUT = path.join(process.env.OUT_DIR || path.join(HERE, "out"), "Response_to_Reviewers_Paper2017.docx");
const T2 = N.table2_on;
const O = N.over_off;
const LV = ["low", "medium", "high"];
const minus = (s) => String(s).replace(/-/g, "−");
const pct = (x) => minus(`${x > 0 ? "+" : ""}${x.toFixed(1)}%`);
const range = (vals) => {
  const a = Math.min(...vals), b = Math.max(...vals);
  return a.toFixed(1) === b.toFixed(1) ? `${a.toFixed(1)}%` : `${a.toFixed(1)}–${b.toFixed(1)}%`;
};
const redu = (c) => range(LV.map((lv) => -T2[c][lv].mean_delay_s.vs_fixed.pct));
const abl = (v, lv) => N.ablation.find((r) => r.variant.startsWith(v) && r.level === lv);

const P = (text, opts = {}) => new Paragraph({
  alignment: opts.align ?? AlignmentType.JUSTIFIED, spacing: { after: opts.after ?? 120, before: opts.before ?? 0 },
  children: runs(text, { size: opts.size ?? 22, bold: opts.bold }),
});
const H = (text, size = 26) => new Paragraph({ spacing: { before: 240, after: 120 }, keepNext: true,
  children: [new TextRun({ text, font: FONT, size, bold: true })] });

const W = 9360;
const line = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
function item(label, comment, response, changes, status) {
  const cell = (children, fill) => new TableCell({
    width: { size: W, type: WidthType.DXA },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    shading: fill ? { type: ShadingType.CLEAR, color: "auto", fill } : undefined,
    borders: { top: line, bottom: line, left: line, right: line },
    children,
  });
  const rows = [
    new TableRow({ children: [cell([P(`**${label}** — ${comment}`, { after: 0 })], "EDEDED")] }),
    new TableRow({ children: [cell([P(`**Response.** ${response}`, { after: 60 }),
      ...changes.map((c) => new Paragraph({ bullet: { level: 0 }, spacing: { after: 40 }, children: runs(c, { size: 22 }) })),
      P(`**Status:** ${status}`, { before: 60, after: 0 })])] }),
  ];
  return [new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [W], rows }), P("", { after: 160 })];
}

const otherHeading = H("Conference-system reviews (CMT Reviewer #1 and Reviewer #2)");
const children = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
    children: [new TextRun({ text: "Response to Reviewers", font: FONT, size: 32, bold: true })] }),
  P("AISUMMIT-2026 · Paper ID 2017 · \"Smart Traffic Control System Using Vehicle Density Analysis\"", { align: AlignmentType.CENTER, after: 240 }),
  P("We thank the reviewers for their comments. Below, each comment is followed by our response and the exact changes " +
    "in the revised manuscript (section, table and figure numbers refer to the revised version). Every number in the " +
    "revised paper is produced by scripts in the public repository (github.com/shivam-G05/Smart-Traffic-Management): " +
    "scripts/benchmark.py (Table II, Sec. IV-D and IV-G), scripts/oversaturation.py (Tables III–IV, Fig. 4, Sec. IV-G), " +
    "scripts/peak_period.py (Fig. 5), scripts/sensing.py (Table IX), scripts/calibrate_weights.py (Table X), " +
    "scripts/ablation.py (Table V), scripts/vision_eval.py (Tables VI and VII) and scripts/kinematics_check.py " +
    "(Table VIII)."),
  P("The revision changes one of the paper's conclusions, and we state this plainly: when compared with stronger " +
    "baselines, the density-based controller's gain below capacity is matched by a Webster-optimized fixed plan, " +
    "vehicle-actuated control and max-pressure control. The revised paper reports this, identifies a failure mode of " +
    "density-only switching near capacity, and adds a discharge-hold rule that corrects it."),

  H("Reviewer 1"),
  ...item("Comment 1.1", "Clearly explain the motivation and novelty of the proposed method and how it differs from existing approaches.",
    "We added two paragraphs to the Introduction. The motivation paragraph names the questions that existing low-cost " +
    "density-based systems leave open: whether variable greens keep safe change intervals, how emergency priority " +
    "interacts with density-based timing, how the controller behaves near and above capacity, and how much of a reported " +
    "gain is due to density logic rather than to replacing an untuned fixed plan. The novelty paragraph states how this " +
    "work differs: it studies the timing logic under statistically paired conditions against re-implementations of the " +
    "strategies used by existing approaches, tests demand up to 1.5 times capacity, verifies change-interval safety at " +
    "every step, and contributes a discharge-hold rule that removes a capacity loss of density-only switching.",
    ["Sec. I: new \"Motivation\" and \"Novelty\" paragraphs; contributions list updated (discharge hold, stronger evaluation).",
      "Sec. II: vehicle-actuated control and gap-out added to the related work [23]; the section ends with how this work differs."],
    "Addressed."),
  ...item("Comment 1.2", "Strengthen the experimental results by comparing them with recent methods and including an ablation study.",
    "We re-implemented four strategies from the related work in the same simulator and compared them with the proposed " +
    "controller on identical seeded traffic (ten paired seeds per condition): a Webster-optimized fixed plan [2], " +
    "vehicle-actuated control [23], max-pressure control [11] (which also represents busiest-lane-first control [6]) " +
    "and three-level density control [1]. All share the same phase sequence and change intervals, so the comparison " +
    `isolates the switching decision. Below capacity (Table II) the proposed controller reduced delay by ${redu("adaptive")} ` +
    `relative to the 20 s fixed plan, but the Webster plan, actuated and max-pressure control did as well ` +
    `(${redu("webster")}, ${redu("actuated")}, ${redu("max_pressure")}); three-level density control was worse than the fixed ` +
    `plan at medium and high demand. Near and above capacity (Tables III and IV, Fig. 4) the original density rule lost ` +
    `${Math.abs(O.capacity.adaptive.vs_fixed.pct).toFixed(1)}% of capacity; the discharge-hold rule restored it ` +
    `(${pct(O.capacity.adaptive_hold.vs_fixed.pct)} relative to fixed timing). ` +
    "The ablation (Table V) was extended from four to ten variants. It shows that the score's benefit comes from the " +
    `queued/moving distinction (removing it: ${pct(abl("No queued", "medium").pct)} and ${pct(abl("No queued", "high").pct)} delay ` +
    `at medium and high demand), not from the class weights (setting them to 1: ${pct(abl("No class", "medium").pct)} and ` +
    `${pct(abl("No class", "high").pct)}). This corrects a statement in the original Conclusion.`,
    ["Sec. III-E (new): the four comparison controllers.", "Sec. IV-B and Table II: comparison of seven controllers at three demand levels.",
      "Sec. IV-C, Tables III–IV and Fig. 4 (new): capacity and delay from 0.6 to 1.5 times capacity.",
      "Sec. IV-E and Table V: ablation extended (score components, θ, discharge-hold zone, preemption).",
      "Abstract, Sec. V and Sec. VI rewritten to report these results, including the corrected conclusion about class weights."],
    "Addressed."),
  ...item("Comment 1.3", "Include a figure illustrating the overall framework of the proposed method.",
    "The original Fig. 1 showed the software architecture. We added Fig. 2, a method workflow figure: (a) the per-step " +
    "control pipeline (sense, score, decide, protect, actuate) and (b) a flowchart of the green-end decision, including " +
    "the new discharge-hold test. Fig. 1 was redrawn to show the controller options.",
    ["Sec. III-A: method workflow description and new Fig. 2.", "Fig. 1 updated; Fig. 3 (preemption states) redrawn."],
    "Addressed."),
  ...item("Comment 1.4", "Discuss the limitations of the proposed method and correct minor language and formatting errors.",
    "The Limitations paragraph was rewritten. The bullet on under-saturated demand was removed because that condition is " +
    "now tested, and new limitations were added: the high simulated saturation flow (no driver reaction time), the " +
    "deterministic arrival model, the frequency of emergency vehicles, the use of re-implemented baselines with ideal " +
    "sensing, and the uncalibrated class weights. We also corrected a factual error: the original text described the " +
    "arrivals as a Poisson process, whereas the simulator uses deterministic headways at a rate redrawn every 15 s; " +
    "Sec. III-B now says so. The manuscript was edited throughout for consistent terminology, units and table/figure " +
    "references.",
    ["Sec. V: limitations paragraph rewritten.", "Sec. III-B: arrival model corrected; above-capacity simulation options described.",
      "Whole manuscript: language and formatting pass; test count updated (68 → 119); condensed to seven pages."],
    "Addressed. We would welcome the reviewers' check of the language in the final version."),

  otherHeading,
  P("The reviews received through the conference system overlap with the e-mailed comments above; each is answered " +
    "here with its own changes."),
  ...item("CMT Reviewer #1 (1)", "Compare with stronger baselines such as optimized fixed-time and max-pressure control.",
    "Done together with Comment 1.2 above (Webster-optimized fixed plan, max-pressure, actuated and three-level density control).",
    ["Sec. III-E, IV-B, IV-C; Tables II–IV; Fig. 4."], "Addressed."),
  ...item("CMT Reviewer #1 (2)", "Clarify the limited AI/ML contribution.",
    "The Introduction now states the role of AI and machine learning plainly: the signal controller is a transparent " +
    "rule, not a learned policy; machine learning enters through the pre-trained Haar-cascade detector, whose accuracy, " +
    "failure cases and ablations are measured (Sec. IV-F), and through a new data-driven calibration of the controller's " +
    "parameters by search on tuning seeds with evaluation on held-out seeds (Sec. IV-I). We chose to report this " +
    "honestly rather than add a learned controller whose behavior could not be bounded the way rule (5) can.",
    ["Sec. I (novelty paragraph and contributions).", "Sec. IV-F (vision evaluation), Sec. IV-I (data-driven calibration)."],
    "Addressed by clarification and the calibration; no learned control policy was added."),
  ...item("CMT Reviewer #1 (3)", "Address the gap between ideal simulator sensing and the low-performing vision pipeline.",
    "We added an experiment in which the controllers see the junction through a sensor model instead of exact states: " +
    "a camera's 60 m view refreshed at 2 Hz without vehicle classes, recall from 100% down to 30%, phantom detections " +
    "at fixed spots, and finally the measured Haar pipeline. " + senseSummary(),
    ["Sec. IV-H (new), Table IX.", "Sec. V: sensing limitation rewritten with these results."],
    "Addressed."),
  ...item("CMT Reviewer #1 (4) and Reviewer #2", "The tested demand levels are below capacity; throughput changes are very small and conclusions about congestion management are limited. Conduct experiments above capacity, including queue growth, spillback, throughput and delay.",
    "We agree: the original three levels were only " +
    `${(1152 / O.capacity.fixed.mean * 100).toFixed(0)}–${(2592 / O.capacity.fixed.mean * 100).toFixed(0)}% of capacity, which ` +
    "is why throughput could not differ. The revision adds three experiments. (a) Capacity: every controller's capacity " +
    "was measured by flooding all approaches (Table III). (b) A steady sweep from 0.6 to 1.5 times the fixed-time " +
    "capacity, ten paired seeds per level, with blocked arrivals kept in an entry queue so that unserved demand is " +
    "measured; we report throughput, served share, delay including vehicles still waiting, queue growth rate, final " +
    "queue and spillback (Table IV, Fig. 4). (c) A 60-minute peak period in which demand rises to 1.2 times capacity and " +
    "falls back, reporting the queue over time, the peak queue, the time to clear the queue after the peak, spillback " +
    "duration, peak throughput and total delay (Fig. 5). " + peakSummary() + " These experiments exposed a failure of " +
    "the original density rule near capacity, which the new discharge-hold rule (Sec. III-D) corrects.",
    ["Sec. III-B (entry queue and entry speed for these runs), III-D (discharge hold).",
      "Sec. IV-C: capacity (Table III), steady sweep (Table IV, Fig. 4) and peak period (Fig. 5).",
      "Abstract, Sec. V and VI: conclusions about congestion management rewritten."],
    "Addressed. Turning traffic and stochastic arrivals remain future work (Sec. V)."),
  ...item("CMT Reviewer #1 (5)", "Provide stronger validation/calibration of the heuristic density weights.",
    "Two analyses were added. The extended ablation (Table V) measures each part of the score separately: the " +
    "queued/moving distinction carries the benefit, while the hand-set class weights do not help. The weights were then " +
    "calibrated from data: a random search over the class weights, the queued/moving ratio and θ on tuning seeds " +
    `${N.calibration.tune_seeds[0]}–${N.calibration.tune_seeds[N.calibration.tune_seeds.length - 1]}, with the best setting compared against the hand-set weights on held-out seeds 1–10. ` + calibSummary(),
    ["Sec. IV-E, Table V (ablation).", "Sec. IV-I (new), Table X (calibration and held-out test).", "Sec. V."],
    "Addressed in simulation; calibration against field data remains future work."),
];

// Reviewer 2 (e-mail) — placed after Reviewer 1 in the document
const V = N.vision;
const det0 = Object.values(V.detectors)[0];
const trk0 = Object.values(V.tracking)[0];
const kc0 = N.kinematics.tau0["cars only"], kc1 = N.kinematics.tau16["cars only"];
const TC = N.table2_cal, OC = N.over_cal;
const reduCal = (c) => range(LV.map((lv) => -TC[c][lv].mean_delay_s.vs_fixed.pct));
const reviewer2 = [
  H("Reviewer 2"),
  P("Several of these comments name components our paper does not have (a ball tracker, a keypoint model, RANSAC, " +
    "detector mAP), so they may have been written for another submission. We have answered each one as it applies to " +
    "our system, and would be grateful if the committee could confirm they were intended for this paper."),
  ...item("Comment 2.1", "Validate kinematic outputs against external ground truth, not only detector mAP.",
    "We validated two kinds of kinematic output. (a) The tracker's speed estimates: for every confirmed track on a real " +
    "vehicle, the Kalman velocity was compared with the vehicle's true speed" +
    (trk0.speed_mae !== null ? ` (Table VII). The result is negative and reported as such: the mean absolute error ` +
      `was ${trk0.speed_mae.toFixed(2)} m/s over ${trk0.speed_n} estimates, but the vehicles concerned moved at only ` +
      `${trk0.true_speed_mean.toFixed(2)} m/s on average, because tracks are confirmed almost only on queued vehicles; ` +
      "the pipeline therefore provides no usable kinematics for moving traffic" : "") + ". " +
    "(b) The simulator's own kinematics against external field values: we measured queue discharge at the stop line as " +
    "a traffic engineer would and compared it with the Highway Capacity Manual's base saturation flow (1900 veh/h/lane, " +
    `1.89 s headway). This revealed that the model discharged cars every ${kc0.saturation_headway_s.toFixed(2)} s, far too ` +
    "fast, because its car-following rule had no driver reaction time. We added a reaction time, calibrated it to 1.6 s " +
    `(${kc1.saturation_headway_s.toFixed(2)} s, ${kc1.saturation_flow_vphpl} veh/h/lane), and repeated all main comparisons ` +
    `with the calibrated model: below capacity the adaptive controller reduced delay by ${reduCal("adaptive")} relative ` +
    "to the fixed plan. The calibration also revealed that the discharge hold's 10 m stop-line zone, chosen for the old " +
    `kinematics, is too short for realistic vehicle spacing (capacity ${pct(OC.capacity.adaptive_hold.vs_fixed.pct)} ` +
    `relative to fixed timing); re-tuned on a separate seed to ${N.zone_cal.tuning.best_zone_m} m it reached ` +
    `${pct(N.zone_cal.over.capacity.adaptive_hold.vs_fixed.pct)} (Sec. IV-G). We report both.`,
    ["Sec. III-B and IV-G: reaction time introduced as an option of rule (1).", "Sec. IV-F and Table VII: tracked-speed error against ground truth.",
      "Sec. IV-G (new), Table VIII: queue discharge against HCM values, calibration, repeated comparisons.", "Sec. V: kinematics limitation rewritten."],
    "Addressed."),
  ...item("Comment 2.2", "Add baselines/ablations (ball tracker, keypoint model, with/without RANSAC).",
    "The named components do not exist in our system; we added the corresponding baselines and ablations for the " +
    "components it does have. For the vision pipeline: detector variants with and without upscaling and histogram " +
    "equalization (Table VI), and tracker variants without the low-confidence matching stage, without the motion model, " +
    "and with immediate confirmation (Table VII). For the controller: four re-implemented control strategies and a " +
    "ten-variant ablation (Comment 1.2).",
    ["Sec. IV-F, Tables VI–VII (vision ablations).", "Sec. III-E, IV-B, IV-C, IV-E, Tables II–V (controller baselines and ablation)."],
    "Addressed in the form that applies to this system."),
  ...item("Comment 2.3", "Clarify dataset splits, annotation protocol and failure cases.",
    "Sec. III-G now has a data and annotation protocol. No real images or manual labels are used: frames are " +
    "rendered from the simulator state and every ground-truth box comes from the same state, so labels are exact by " +
    "construction. Nothing is trained (the cascade is pre-trained and the controller is rule-based), so there is no " +
    "training split; detector and tracker parameters were fixed during development, the discharge-hold zone was chosen " +
    "on a separate tuning seed (1000), capacity was measured on seeds 101–105, and all reported results use seeds 1–10 " +
    "(vision: 1–4). Failure cases are quantified in Sec. IV-F: " +
    `${V.failure.persistent_background_share.toFixed(1)}% of false positives recur at fixed background locations, and ` +
    `recall depends strongly on vehicle class and distance (overall recall ${det0.recall.toFixed(1)}%).`,
    ["Sec. III-G: data and annotation protocol.", "Sec. IV-A: seed splits.", "Sec. IV-F: failure cases by type, class and distance."],
    "Addressed."),
  ...item("Comment 2.4", "Major English/formatting edit; tone down unsupported accuracy claims.",
    "The manuscript was edited throughout. Claims were qualified where the new evidence requires it: the gain below " +
    "capacity is reported against stronger baselines, not only the fixed plan; the conclusion about class weights was " +
    "corrected; the arrival model was described correctly; the simulator's kinematics are validated and their remaining " +
    "gap is stated; and all hardware values remain marked as estimates.",
    ["Abstract, Sec. III-B, IV-B, IV-G, V, VI."], "Addressed."),
];
children.splice(children.findIndex((c) => c === otherHeading), 0, ...reviewer2);


// Summaries for the conference-system items (imperfect sensing, calibration)
function senseSummary() {
  const conds = Object.keys(N.sensing);
  const near = N.sensing[conds[1]], med = N.sensing[conds[0]];
  const row = (cond, n) => cond.rows.find((r) => r.sensing.startsWith(n)).adaptive_hold;
  const haar = med.rows.find((r) => r.sensing.startsWith("Measured Haar"));
  return `Near capacity the discharge-hold controller's delay rose from ${row(near, "Exact").mean.toFixed(1)} s (exact ` +
    `states) to ${row(near, "Camera").mean.toFixed(1)} s with a perfect camera view and ${row(near, "recall 50%").mean.toFixed(1)} s ` +
    `at 50% recall (fixed plan ${near.fixed_mean.toFixed(1)} s); phantom detections near the stop line kept greens at the ` +
    "maximum" + (haar ? `, and with the measured pipeline delay was ${haar.adaptive_hold.mean.toFixed(1)} s at medium ` +
    `demand against ${med.fixed_mean.toFixed(1)} s for the fixed plan` : "") + ". The paper now states the detector " +
    "quality needed before the loop can be closed.";
}
function peakSummary() {
  const P = N.peak;
  const rec = (c) => {
    const r = P[c].recovery_min;
    return r.not_recovered === r.runs ? "did not clear it within the hour" : `cleared it ${r.mean.toFixed(1)} min after the peak`;
  };
  return `In the peak period the queue reached ${P.fixed.peak_queue.mean.toFixed(0)} vehicles under fixed timing and ` +
    `${P.adaptive_hold.peak_queue.mean.toFixed(0)} with the discharge hold; fixed timing ${rec("fixed")}, the hold ` +
    `${rec("adaptive_hold")}, and the original density rule ${rec("adaptive")}.`;
}
function calibSummary() {
  const h = N.calibration.held_out.Calibrated;
  return "On the held-out seeds the calibrated score changed delay by " +
    Object.entries(h).map(([c, v]) => `${pct(v.change_pct)} (${c}, p ${v.p < 0.001 ? "< 0.001" : v.p.toFixed(3)})`).join(", ") +
    " relative to the hand-set weights.";
}

const doc = new Document({
  styles: { default: { document: { run: { font: FONT, size: 22 } } } },
  sections: [{ properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } }, children }],
});
fs.mkdirSync(path.dirname(OUT), { recursive: true });
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT); });
