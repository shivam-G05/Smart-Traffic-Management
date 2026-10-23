const BASE_PHASES = {
  NS_GREEN: "North & South have green",
  NS_YELLOW: "North & South on yellow — about to stop",
  ALL_RED_A: "All red — safety gap before East & West go",
  EW_GREEN: "East & West have green",
  EW_YELLOW: "East & West on yellow — about to stop",
  ALL_RED_B: "All red — safety gap before North & South go",
};

const EMERGENCY_PHASES = {
  FORCE_YELLOW: (road) => `Emergency on ${road}: other traffic switched to yellow`,
  CLEARING: (road) => `Emergency on ${road}: all red to clear the junction`,
  PREEMPT_GREEN: (road) => `Emergency on ${road}: priority green until it passes`,
  RELEASE_YELLOW: (road) => `Emergency on ${road} is through: its green goes to yellow`,
  RELEASE_CLEARING: (road) => `Emergency on ${road} is through: all red before normal control resumes`,
};

const EMERGENCY_PATTERN = /^EMERGENCY_(FORCE_YELLOW|CLEARING|PREEMPT_GREEN|RELEASE_YELLOW|RELEASE_CLEARING)_(\w+)$/;

/** Plain-English meaning of a controller phase code like "NS_GREEN" or
 * "EMERGENCY_PREEMPT_GREEN_west". Falls back to the raw code. */
export function describePhase(phase) {
  if (!phase) return "";
  if (BASE_PHASES[phase]) return BASE_PHASES[phase];
  const match = EMERGENCY_PATTERN.exec(phase);
  if (match) return EMERGENCY_PHASES[match[1]](match[2]);
  return phase;
}

export function isEmergencyPhase(phase) {
  return typeof phase === "string" && phase.startsWith("EMERGENCY_");
}

export const PHASE_GLOSSARY = [
  ...Object.entries(BASE_PHASES).map(([code, meaning]) => ({ code, meaning })),
  { code: "EMERGENCY_FORCE_YELLOW_<road>", meaning: EMERGENCY_PHASES.FORCE_YELLOW("<road>") },
  { code: "EMERGENCY_CLEARING_<road>", meaning: EMERGENCY_PHASES.CLEARING("<road>") },
  { code: "EMERGENCY_PREEMPT_GREEN_<road>", meaning: EMERGENCY_PHASES.PREEMPT_GREEN("<road>") },
  { code: "EMERGENCY_RELEASE_YELLOW_<road>", meaning: EMERGENCY_PHASES.RELEASE_YELLOW("<road>") },
  { code: "EMERGENCY_RELEASE_CLEARING_<road>", meaning: EMERGENCY_PHASES.RELEASE_CLEARING("<road>") },
];
