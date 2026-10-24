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
const N = JSON.parse(fs.readFileSync(path.join(HERE, "build", "numbers.json"), "utf8"));
const OUT = path.join(HERE, "out", "Response_to_Reviewers_Paper2017.docx");
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

const otherHeading = H("Other comments received (conference system reviews)");
const children = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
    children: [new TextRun({ text: "Response to Reviewers", font: FONT, size: 32, bold: true })] }),
  P("AISUMMIT-2026 · Paper ID 2017 · \"Smart Traffic Control System Using Vehicle Density Analysis\"", { align: AlignmentType.CENTER, after: 240 }),
  P("We thank the reviewers for their comments. Below, each comment is followed by our response and the exact changes " +
    "in the revised manuscript (section, table and figure numbers refer to the revised version). Every number in the " +
    "revised paper is produced by scripts in the public repository (github.com/shivam-G05/Smart-Traffic-Management): " +
    "scripts/benchmark.py (Tables II, V and X), scripts/oversaturation.py (Tables III, IV and X, Fig. 4), " +
    "scripts/ablation.py (Table VI), scripts/vision_eval.py (Tables VII and VIII) and scripts/kinematics_check.py " +
    "(Table IX)."),
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
    ["Sec. I: new \"Motivation\" and \"Novelty and difference from existing approaches\" paragraphs; contributions list updated (discharge hold, stronger evaluation).",
      "Sec. II-A: vehicle-actuated control and gap-out added to the related work [23]; Sec. II-B ends with how this work differs."],
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
    "The ablation (Table VI) was extended from four to ten variants. It shows that the score's benefit comes from the " +
    `queued/moving distinction (removing it: ${pct(abl("No queued", "medium").pct)} and ${pct(abl("No queued", "high").pct)} delay ` +
    `at medium and high demand), not from the class weights (setting them to 1: ${pct(abl("No class", "medium").pct)} and ` +
    `${pct(abl("No class", "high").pct)}). This corrects a statement in the original Conclusion.`,
    ["Sec. IV-E (new): the four comparison controllers.", "Sec. V-C and Table II: comparison of seven controllers at three demand levels.",
      "Sec. V-D, Tables III–IV and Fig. 4 (new): capacity and delay from 0.6 to 1.5 times capacity.",
      "Sec. V-F and Table VI: ablation extended (score components, θ, discharge-hold zone, preemption).",
      "Abstract, Sec. VI-A and Sec. VII rewritten to report these results, including the corrected conclusion about class weights."],
    "Addressed."),
  ...item("Comment 1.3", "Include a figure illustrating the overall framework of the proposed method.",
    "The original Fig. 1 showed the software architecture. We added Fig. 2, a method workflow figure: (a) the per-step " +
    "control pipeline (sense, score, decide, protect, actuate) and (b) a flowchart of the green-end decision, including " +
    "the new discharge-hold test. Fig. 1 was redrawn to show the controller options.",
    ["Sec. III: new paragraph \"Method workflow\" and new Fig. 2.", "Fig. 1 updated; Fig. 3 (preemption states) redrawn."],
    "Addressed."),
  ...item("Comment 1.4", "Discuss the limitations of the proposed method and correct minor language and formatting errors.",
    "The Limitations subsection was rewritten. The bullet on under-saturated demand was removed because that condition is " +
    "now tested, and new limitations were added: the high simulated saturation flow (no driver reaction time), the " +
    "deterministic arrival model, the frequency of emergency vehicles, the use of re-implemented baselines with ideal " +
    "sensing, and the uncalibrated class weights. We also corrected a factual error: the original text described the " +
    "arrivals as a Poisson process, whereas the simulator uses deterministic headways at a rate redrawn every 15 s; " +
    "Sec. IV-A now says so. The manuscript was edited throughout for consistent terminology, units and table/figure " +
    "references.",
    ["Sec. VI-B: limitations rewritten.", "Sec. IV-A: arrival model corrected; above-capacity simulation options described.",
      "Whole manuscript: language and formatting pass; test count updated (68 → 101)."],
    "Addressed. We would welcome the reviewers' check of the language in the final version."),

  otherHeading,
  P("For completeness we list the comments received through the conference system and how far the current revision " +
    "addresses them."),
  ...item("CMT Reviewer #1 (1)", "Compare with stronger baselines such as optimized fixed-time and max-pressure control.",
    "Done together with Comment 1.2 above (Webster-optimized fixed plan, max-pressure, actuated and three-level density control).",
    ["Sec. IV-E, V-C, V-D; Tables II–IV; Fig. 4."], "Addressed."),
  ...item("CMT Reviewer #1 (2)", "Clarify the limited AI/ML contribution.",
    "The revised Introduction and Related Work state explicitly that the controller is a transparent rule-based method, " +
    "not a learned one, and position the contribution as the evaluation, the safety properties and the discharge-hold " +
    "rule. The machine-learning components (Haar cascade, Kalman/Hungarian tracking) are confined to the vision " +
    "pipeline, whose measured accuracy is reported.",
    ["Sec. I (novelty paragraph), Sec. II-A."], "Partly addressed: no learned component was added to the controller in this revision."),
  ...item("CMT Reviewer #1 (3)", "Address the gap between ideal simulator sensing and the low-performing vision pipeline.",
    "The gap is stated in the abstract, Sec. III, Sec. V-G and the limitations.",
    ["Abstract, Sec. V-G, Sec. VI-B."],
    "Partly addressed: an experiment that feeds the controller degraded (noisy) detections is planned but not yet included."),
  ...item("CMT Reviewer #1 (4) and Reviewer #2", "Evaluate oversaturated and more realistic traffic conditions; conduct experiments above capacity, including queue growth, spillback, throughput and delay.",
    "We measured each controller's capacity and swept demand from 0.6 to 1.5 times the fixed-time capacity with ten paired " +
    "seeds per level, keeping blocked arrivals in an entry queue so that unserved demand is measured. We report " +
    "throughput, delay including vehicles still waiting, queue growth and spillback.",
    ["Sec. IV-A (simulation options), IV-D (discharge hold), V-D; Tables III–IV; Fig. 4."],
    "Addressed for oversaturation. Turning traffic and stochastic arrivals remain future work (Sec. VI-B)."),
  ...item("CMT Reviewer #1 (5)", "Provide stronger validation/calibration of the heuristic density weights.",
    "The extended ablation measures each part of the score separately and shows that the class weights, as set, do not " +
    "improve delay. Calibration against local passenger-car-unit factors is stated as required.",
    ["Sec. V-F, Table VI; Sec. VI-B."], "Partly addressed: calibration of the weights is not yet done."),
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
    (trk0.speed_mae !== null ? ` (mean absolute error ${trk0.speed_mae.toFixed(2)} m/s over ${trk0.speed_n} estimates, ` +
      `mean true speed ${trk0.true_speed_mean.toFixed(2)} m/s; Table VIII)` : "") + ". " +
    "(b) The simulator's own kinematics against external field values: we measured queue discharge at the stop line as " +
    "a traffic engineer would and compared it with the Highway Capacity Manual's base saturation flow (1900 veh/h/lane, " +
    `1.89 s headway). This revealed that the model discharged cars every ${kc0.saturation_headway_s.toFixed(2)} s, far too ` +
    "fast, because its car-following rule had no driver reaction time. We added a reaction time, calibrated it to 1.6 s " +
    `(${kc1.saturation_headway_s.toFixed(2)} s, ${kc1.saturation_flow_vphpl} veh/h/lane), and repeated all main comparisons ` +
    `with the calibrated model: below capacity the adaptive controller reduced delay by ${reduCal("adaptive")} relative ` +
    `to the fixed plan, and the discharge hold reached ${pct(OC.capacity.adaptive_hold.vs_fixed.pct)} of the fixed plan's ` +
    "capacity (Table X).",
    ["Sec. IV-A: reaction time introduced as an option of rule (1).", "Sec. V-G and Table VIII: tracked-speed error against ground truth.",
      "Sec. V-H (new), Tables IX–X: queue discharge against HCM values, calibration, repeated comparisons.", "Sec. VI-B: kinematics limitation rewritten."],
    "Addressed."),
  ...item("Comment 2.2", "Add baselines/ablations (ball tracker, keypoint model, with/without RANSAC).",
    "The named components do not exist in our system; we added the corresponding baselines and ablations for the " +
    "components it does have. For the vision pipeline: detector variants with and without upscaling and histogram " +
    "equalization (Table VII), and tracker variants without the low-confidence matching stage, without the motion model, " +
    "and with immediate confirmation (Table VIII). For the controller: four re-implemented control strategies and a " +
    "ten-variant ablation (Comment 1.2).",
    ["Sec. V-G, Tables VII–VIII (vision ablations).", "Sec. IV-E, V-C, V-D, V-F, Tables II–IV and VI (controller baselines and ablation)."],
    "Addressed in the form that applies to this system."),
  ...item("Comment 2.3", "Clarify dataset splits, annotation protocol and failure cases.",
    "Sec. IV-G now has a \"Data and annotation protocol\" paragraph. No real images or manual labels are used: frames are " +
    "rendered from the simulator state and every ground-truth box comes from the same state, so labels are exact by " +
    "construction. Nothing is trained (the cascade is pre-trained and the controller is rule-based), so there is no " +
    "training split; detector and tracker parameters were fixed during development, the discharge-hold zone was chosen " +
    "on a separate tuning seed (1000), capacity was measured on seeds 101–105, and all reported results use seeds 1–10 " +
    "(vision: 1–4). Failure cases are quantified in Sec. V-G: " +
    `${V.failure.persistent_background_share.toFixed(1)}% of false positives recur at fixed background locations, and ` +
    `recall depends strongly on vehicle class and distance (overall recall ${det0.recall.toFixed(1)}%).`,
    ["Sec. IV-G: data and annotation protocol.", "Sec. V-A: seed splits.", "Sec. V-G: failure cases by type, class and distance."],
    "Addressed."),
  ...item("Comment 2.4", "Major English/formatting edit; tone down unsupported accuracy claims.",
    "The manuscript was edited throughout. Claims were qualified where the new evidence requires it: the gain below " +
    "capacity is reported against stronger baselines, not only the fixed plan; the conclusion about class weights was " +
    "corrected; the arrival model was described correctly; the simulator's kinematics are validated and their remaining " +
    "gap is stated; and all hardware values remain marked as estimates.",
    ["Abstract, Sec. IV-A, V-C, V-H, VI, VII."], "Addressed."),
];
children.splice(children.findIndex((c) => c === otherHeading), 0, ...reviewer2);

const doc = new Document({
  styles: { default: { document: { run: { font: FONT, size: 22 } } } },
  sections: [{ properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } }, children }],
});
fs.mkdirSync(path.dirname(OUT), { recursive: true });
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT); });
