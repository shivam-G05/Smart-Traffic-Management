import { describePhase, isEmergencyPhase } from "../utils/phases.js";

const GROUP = { north: "ns", south: "ns", east: "ew", west: "ew" };
const GROUP_LABEL = { ns: "North + South", ew: "East + West" };
const OTHER_GROUP = { ns: "ew", ew: "ns" };

const capitalize = (s) => s.charAt(0).toUpperCase() + s.slice(1);

function controllerKind(controller = "") {
  if (controller.includes("AdaptiveController")) return "adaptive";
  if (controller.includes("FixedTimerController")) return "fixed";
  return null;
}

/** What the running controller is actually doing about this road, in plain
 * words — each sentence mirrors the real rule in decision_engine/, using the
 * live constants from /api/explain. */
function controllerResponse(roadName, road, snapshot, explain) {
  if (isEmergencyPhase(snapshot.active_phase)) {
    return `${describePhase(snapshot.active_phase)}. Normal timing is paused until the emergency vehicle is through.`;
  }
  if (!explain) return null;

  const kind = controllerKind(snapshot.controller);
  const { fixed_timer: fixed, adaptive } = explain;
  const t = road.light.time_in_state ?? 0;
  const mine = GROUP_LABEL[GROUP[roadName]];
  const other = GROUP_LABEL[OTHER_GROUP[GROUP[roadName]]];

  if (road.light.state === "yellow") return "The light is yellow — the signal is already changing over.";

  if (road.light.state === "green") {
    if (kind === "adaptive") {
      return t < adaptive.min_green_s
        ? `Green for ${t.toFixed(0)}s. The adaptive controller guarantees ${adaptive.min_green_s}s, then keeps it green while ${mine} are more than ${adaptive.extension_threshold}× busier than ${other}, up to ${adaptive.max_green_s}s.`
        : `Adaptive response: green held ${t.toFixed(0)}s — past the ${adaptive.min_green_s}s minimum — because ${mine} are busier than ${other}. Hard limit ${adaptive.max_green_s}s.`;
    }
    if (kind === "fixed") {
      return `Fixed timer: green lasts exactly ${fixed.green_s}s whatever the traffic — ${Math.max(0, fixed.green_s - t).toFixed(0)}s left. No extra time for this queue.`;
    }
  }

  if (road.light.state === "red") {
    if (kind === "adaptive") {
      return `Waiting for green. This queue adds to ${mine}'s density, so the adaptive controller ends ${other}'s green as soon as they are no longer more than ${adaptive.extension_threshold}× busier (after their ${adaptive.min_green_s}s minimum).`;
    }
    if (kind === "fixed") {
      return "Fixed timer: waits its turn on the fixed cycle — it cannot react to this queue.";
    }
  }
  return null;
}

function ExplainLink({ onExplain }) {
  if (!onExplain) return null;
  return (
    <button
      onClick={onExplain}
      className="rounded bg-white/10 px-2.5 py-1 text-xs text-white/75 hover:bg-white/15 hover:text-white"
    >
      What do these numbers mean? →
    </button>
  );
}

export default function TrafficAlertBanner({ snapshot, explain, onExplain }) {
  if (!snapshot) return null;

  const roads = Object.entries(snapshot.roads);
  const high = roads
    .filter(([, r]) => r.high_traffic_alert ?? r.congestion_level === "high")
    .sort((a, b) => b[1].density_score - a[1].density_score);
  const medium = roads.filter(([, r]) => r.congestion_level === "medium" && !r.high_traffic_alert);
  const emergencies = roads.filter(([, r]) => r.has_emergency_vehicle);
  const limit = explain?.congestion.high_min;
  const waitingFactor = explain
    ? explain.density.queued_multiplier / explain.density.moving_multiplier
    : null;

  return (
    <div className="space-y-2">
      {emergencies.length > 0 && (
        <div className="rounded-lg border-2 border-sky-400/80 bg-sky-950/60 px-4 py-2.5 text-sm text-sky-100">
          <span className="font-bold tracking-wide">EMERGENCY VEHICLE</span> approaching on{" "}
          {emergencies.map(([n]) => capitalize(n)).join(", ")} —{" "}
          {isEmergencyPhase(snapshot.active_phase)
            ? describePhase(snapshot.active_phase)
            : "priority green is being arranged"}
          .
        </div>
      )}

      {high.length > 0 ? (
        <div className="rounded-lg border-2 border-red-500/80 bg-red-950/50 p-4 shadow-[0_0_24px_rgba(239,68,68,0.25)]">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <span className="relative flex h-3 w-3">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
                <span className="relative inline-flex h-3 w-3 rounded-full bg-red-500" />
              </span>
              <h2 className="text-base font-bold tracking-wide text-red-200">HIGH TRAFFIC DETECTED</h2>
            </div>
            <ExplainLink onExplain={onExplain} />
          </div>

          <ul className="mt-3 space-y-3">
            {high.map(([name, road]) => (
              <li key={name}>
                <p className="text-sm text-white/90">
                  <span className="font-semibold">{capitalize(name)}</span> — density{" "}
                  <span className="font-mono">{road.density_score.toFixed(1)}</span>
                  {limit != null &&
                    (road.density_score > limit ? (
                      <> (high traffic is above {limit})</>
                    ) : (
                      <span className="text-amber-200/90">
                        {" "}
                        — easing; the alert clears after {explain.congestion.alert_hold_s}s at or below {limit}
                      </span>
                    ))}{" "}
                  · {road.queue_length} waiting · light{" "}
                  {road.light.state}
                </p>
                <p className="mt-0.5 text-sm leading-relaxed text-red-100/80">
                  {controllerResponse(name, road, snapshot, explain)}
                </p>
              </li>
            ))}
          </ul>

          {waitingFactor && (
            <p className="mt-3 text-[11px] text-white/45">
              Density adds up each vehicle's weight (a bus counts more than a car), and a waiting vehicle counts{" "}
              {waitingFactor}× as much as a moving one.
            </p>
          )}
        </div>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-emerald-500/30 bg-emerald-950/30 px-4 py-2.5">
          <p className="text-sm text-emerald-200">
            <span className="mr-2 inline-block h-2.5 w-2.5 rounded-full bg-emerald-400" />
            Traffic flowing normally{limit != null && <> — no road above density {limit}</>}
            {medium.length > 0 && (
              <span className="text-amber-200/80">
                {" "}
                · building up:{" "}
                {medium.map(([n, r]) => `${capitalize(n)} (${r.density_score.toFixed(1)})`).join(", ")}
              </span>
            )}
          </p>
          <ExplainLink onExplain={onExplain} />
        </div>
      )}
    </div>
  );
}
