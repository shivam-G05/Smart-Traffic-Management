import { useState } from "react";

import { VEHICLE_LEGEND } from "../utils/draw.js";
import { PHASE_GLOSSARY, isEmergencyPhase } from "../utils/phases.js";

const ROADS = ["north", "east", "south", "west"];
const VEHICLE_INFO = Object.fromEntries(VEHICLE_LEGEND.map((v) => [v.type, v]));
const LEVEL_CLASS = {
  low: "bg-emerald-500/15 text-emerald-300",
  medium: "bg-amber-500/15 text-amber-300",
  high: "bg-red-500/25 text-red-200 ring-1 ring-red-500/70",
};

const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const fmt = (n) => (Number.isInteger(n) ? String(n) : String(Number(n.toFixed(2))));

function Section({ title, subtitle, children }) {
  return (
    <section className="rounded-lg border border-white/10 bg-panel p-5">
      <h2 className="text-base font-semibold text-white/90">{title}</h2>
      {subtitle && <p className="mt-1 text-sm text-white/50">{subtitle}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

const PIPELINE = [
  ["Watch", "A virtual camera turns each road into an image, like a CCTV frame."],
  ["Detect", "OpenCV's Haar Cascade draws a box around each vehicle it recognises."],
  ["Track", "ByteTrack links boxes frame to frame so each vehicle keeps one ID."],
  ["Score", "Every road gets a density score from the vehicles on it."],
  ["Decide", "The controller uses those scores to choose how long each green lasts."],
];

function Pipeline() {
  return (
    <>
      <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {PIPELINE.map(([title, text], i) => (
          <li key={title} className="rounded-lg bg-panelmuted p-3">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-cyan-600/30 text-xs font-bold text-cyan-200">
                {i + 1}
              </span>
              <span className="font-semibold text-white/90">{title}</span>
            </div>
            <p className="mt-2 text-sm leading-relaxed text-white/60">{text}</p>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-xs leading-relaxed text-white/45">
        To be precise about what drives the lights: steps 4–5 use the simulation's exact vehicle positions.
        Steps 1–3 run alongside on every frame to show what a real camera would see — including its real,
        imperfect accuracy — but they do not control the signals.
      </p>
    </>
  );
}

function WeightChips({ explain }) {
  return (
    <div className="flex flex-wrap gap-2">
      {Object.entries(explain.density.weights).map(([type, weight]) => (
        <span
          key={type}
          className="flex items-center gap-1.5 rounded bg-panelmuted px-2 py-1 text-xs text-white/70"
        >
          <span
            className="inline-block h-2.5 w-4 rounded-[2px]"
            style={{ backgroundColor: VEHICLE_INFO[type]?.color }}
          />
          {VEHICLE_INFO[type]?.label ?? type}
          <span className="font-mono text-white">{fmt(weight)}</span>
        </span>
      ))}
    </div>
  );
}

function chipClass(active) {
  return `rounded px-3 py-1.5 text-sm ${
    active ? "bg-cyan-600/30 text-cyan-200" : "bg-panelmuted text-white/60 hover:text-white/85"
  }`;
}

function LiveDensity({ snapshot, explain }) {
  const [picked, setPicked] = useState(null); // null = follow the busiest road

  if (!snapshot) return <p className="text-sm text-white/50">Waiting for simulation data...</p>;

  const roads = snapshot.roads;
  const busiest = ROADS.reduce((best, r) =>
    (roads[r]?.density_score ?? 0) > (roads[best]?.density_score ?? 0) ? r : best
  );
  const roadName = picked ?? busiest;
  const road = roads[roadName];
  const rows = road.density_breakdown ?? [];
  const { low_max: lowMax, high_min: highMin } = explain.congestion;
  const score = road.density_score;

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        <button onClick={() => setPicked(null)} className={chipClass(picked === null)}>
          Busiest road (auto)
        </button>
        {ROADS.map((r) => (
          <button key={r} onClick={() => setPicked(r)} className={chipClass(picked === r)}>
            {cap(r)} · {roads[r].density_score.toFixed(1)}
          </button>
        ))}
      </div>

      <p className="mt-4 text-sm text-white/70">
        Right now on <b className="text-white">{cap(roadName)}</b>
        {picked === null && " (the busiest road)"}: light is <b className="text-white">{road.light.state}</b>,{" "}
        {road.queue_length} waiting, {road.vehicle_count} vehicles in total.
      </p>

      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[540px] text-left text-sm">
          <thead className="text-xs uppercase text-white/40">
            <tr>
              <th className="py-2 pr-3 font-medium">Vehicle</th>
              <th className="py-2 pr-3 font-medium">State</th>
              <th className="py-2 pr-3 text-right font-medium">Count</th>
              <th className="py-2 pr-3 text-right font-medium">Weight</th>
              <th className="py-2 pr-3 text-right font-medium">State factor</th>
              <th className="py-2 text-right font-medium">Points</th>
            </tr>
          </thead>
          <tbody className="font-mono text-white/80">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-3 font-sans text-white/45">
                  No vehicles on this road right now — density is 0.
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={`${row.type}-${row.state}`} className="border-t border-white/5">
                  <td className="py-2 pr-3 font-sans">
                    <span
                      className="mr-2 inline-block h-2.5 w-4 rounded-[2px] align-middle"
                      style={{ backgroundColor: VEHICLE_INFO[row.type]?.color }}
                    />
                    {VEHICLE_INFO[row.type]?.label ?? row.type}
                  </td>
                  <td className={`py-2 pr-3 font-sans ${row.state === "queued" ? "text-red-300" : "text-white/60"}`}>
                    {row.state === "queued" ? "waiting" : "moving"}
                  </td>
                  <td className="py-2 pr-3 text-right">{row.count}</td>
                  <td className="py-2 pr-3 text-right">× {fmt(row.weight)}</td>
                  <td className="py-2 pr-3 text-right">× {fmt(row.multiplier)}</td>
                  <td className="py-2 text-right text-white">= {fmt(row.contribution)}</td>
                </tr>
              ))
            )}
          </tbody>
          <tfoot>
            <tr className="border-t border-white/20">
              <td colSpan={5} className="py-2 pr-3 font-semibold text-white/85">
                Density score (sum of points)
              </td>
              <td className="py-2 text-right font-mono text-base font-bold text-white">{score.toFixed(2)}</td>
            </tr>
          </tfoot>
        </table>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 text-sm text-white/70">
        <span>Traffic level:</span>
        <span className="font-mono text-white">{score.toFixed(2)}</span>
        <span>
          {score <= lowMax
            ? `is ≤ ${lowMax}`
            : score <= highMin
              ? `is between ${lowMax} and ${highMin}`
              : `is above ${highMin}`}
        </span>
        <span>→</span>
        <span className={`rounded px-2 py-0.5 text-xs font-semibold uppercase ${LEVEL_CLASS[road.congestion_level] ?? ""}`}>
          {road.congestion_level}
        </span>
      </div>
    </div>
  );
}

function ControllerRules({ snapshot, explain }) {
  const live = snapshot?.controller ?? "";
  const running = isEmergencyPhase(snapshot?.active_phase)
    ? "emergency"
    : live.includes("AdaptiveController")
      ? "adaptive"
      : live.includes("FixedTimerController")
        ? "fixed"
        : null;
  const { fixed_timer: f, adaptive: a, emergency: e } = explain;

  const card = (id, title, body) => (
    <div
      className={`rounded-lg border p-4 ${
        running === id ? "border-cyan-500/60 bg-cyan-950/30" : "border-white/10 bg-panelmuted"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-semibold text-white/90">{title}</h3>
        {running === id && (
          <span className="rounded bg-cyan-600/30 px-2 py-0.5 text-[10px] font-semibold uppercase text-cyan-200">
            active now
          </span>
        )}
      </div>
      <div className="mt-2 space-y-1.5 text-sm leading-relaxed text-white/65">{body}</div>
    </div>
  );

  return (
    <div className="grid gap-3 lg:grid-cols-3">
      {card(
        "fixed",
        "Fixed timer (baseline)",
        <>
          <p>
            Green {f.green_s}s → yellow {f.yellow_s}s → all red {f.all_red_s}s, then the other direction gets the
            same.
          </p>
          <p>It never looks at traffic. This is how most signals work today, and what the adaptive controller is compared against.</p>
        </>
      )}
      {card(
        "adaptive",
        "Adaptive (density-based)",
        <>
          <p>Every green lasts at least {a.min_green_s}s.</p>
          <p>
            After that it adds up density for the two roads with green and the two roads waiting. If the green side
            is more than {a.extension_threshold}× busier, green continues; otherwise it switches.
          </p>
          <p>
            Green never goes past {a.max_green_s}s, and yellow ({f.yellow_s}s) and all-red ({f.all_red_s}s) are never
            shortened.
          </p>
        </>
      )}
      {card(
        "emergency",
        "Emergency override (always on)",
        <>
          <p>
            If an ambulance or fire truck is approaching, any other green turns yellow ({f.yellow_s}s), then all red
            ({f.all_red_s}s), then its direction gets green. A green that has just started is kept for at least{" "}
            {e.min_green_before_preempt_s}s first.
          </p>
          <p>
            Green is held until it is through the junction, or {e.max_hold_s}s at most. Its green then goes yellow and
            all red too, and the other direction gets the next green.
          </p>
        </>
      )}
    </div>
  );
}

function PhaseTable({ phase }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {PHASE_GLOSSARY.map(({ code, meaning }) => {
        const active =
          code === phase || (code.includes("<road>") && phase?.startsWith(code.replace("<road>", "")));
        return (
          <div
            key={code}
            className={`rounded px-3 py-2 ${active ? "bg-cyan-950/50 ring-1 ring-cyan-500/60" : "bg-panelmuted"}`}
          >
            <div className="font-mono text-xs text-white/80">{code}</div>
            <div className="text-sm text-white/60">{meaning}</div>
          </div>
        );
      })}
    </div>
  );
}

function Glossary({ explain }) {
  const d = explain.density;
  const c = explain.congestion;
  const minHits = explain.tracking?.min_hits;

  const groups = [
    {
      title: "Simulation Overview",
      terms: [
        ["Connection", "Live means the dashboard is receiving updates from the backend (about 10 per second). Reconnecting means the link dropped and it is retrying automatically."],
        ["Controller", "Which signal logic is deciding the lights. \"Fixed timer + emergency override\" means fixed timing with the ambulance/fire-truck override on top."],
        ["Active Vehicles", "Total vehicles currently on all four roads."],
        ["Sim Time", "Seconds of simulated time since the backend started."],
      ],
    },
    {
      title: "Signal Status",
      terms: [
        ["Phase", "The controller's current step, e.g. NS_GREEN. Every code is listed in the table above."],
        ["Coloured dot", "That road's traffic light right now."],
        ["Queue", `Vehicles waiting before the stop line — moving slower than ${d.queued_speed_mps} m/s.`],
        ["Vehicles", "Every vehicle on that road: waiting, crossing, or driving away."],
        ["Density", `How much a road needs green: each vehicle's weight × ${fmt(d.queued_multiplier)} if waiting or × ${fmt(d.moving_multiplier)} if moving, all added up. See the live calculation above.`],
        ["Low / Medium / High", `Traffic level from density: up to ${c.low_max} is low, up to ${c.high_min} is medium, above ${c.high_min} is high traffic.`],
        ["EMERGENCY", "An ambulance or fire truck still has to get through this junction. This is what triggers the emergency override."],
      ],
    },
    {
      title: "Intersection view",
      terms: [
        ["Red outline on a vehicle", `Stopped or waiting (slower than ${d.queued_speed_mps} m/s).`],
        ["Yellow front edge", "Moving — the yellow edge is the front, so it shows which way the vehicle is going."],
        ["Flashing white/blue ring", "Emergency vehicle (ambulance or fire truck)."],
        ["Red pulsing road + HIGH TRAFFIC alert", `Switches on the moment a road's density goes above ${c.high_min}, and switches off only after it has stayed at or below ${c.high_min} for ${c.alert_hold_s}s — so it doesn't flicker when traffic hovers around the limit. The low/medium/high badges always show the instant reading.`],
        ["Amber tint on a road", `Traffic is building up — density above ${c.low_max}.`],
        ["Thick white line", "Stop line — vehicles wait here on red."],
        ["Yellow centre line", "Separates the two directions of travel."],
        ["Dashed line", "Separates the two lanes going the same way."],
        ["Vehicle length", "Drawn at true length and true spacing, so a bus really is as long as it looks next to a car."],
      ],
    },
    {
      title: "Live CCTV feeds",
      terms: [
        ["det / gt", "Boxes the camera's detector found in this frame / real vehicles actually in the camera's view."],
        ["Green / orange box", "Green: the box is on a real vehicle. Orange: a false alarm — nothing real there."],
        ["Gray outline", "Where the real vehicles actually are (the answer key used to score the detector)."],
        ["Number on a box", "Detector confidence — higher means more certain. It is a score, not a percentage."],
        ["Precision", "Of all boxes drawn, the share that are on real vehicles (boxes on real vehicles ÷ all boxes)."],
        ["Recall", "Of all real vehicles in view, the share that got a box (vehicles found ÷ vehicles in view)."],
        ["Cyan #N", `Tracking ID: the same vehicle keeps the same number from frame to frame${minHits ? `, once it has been matched in ${minHits} frames` : ""}.`],
        ["Active tracks", "Vehicles the tracker is following in this frame."],
        ["Total counted", "Every track started since the backend started. It includes short-lived false alarms, so it is higher than the real number of vehicles."],
        ["CAMERA: EMERGENCY?", "The camera matched an ambulance or fire truck in this frame. Shown for comparison only — the lights are controlled from exact vehicle positions, not from the camera."],
      ],
    },
    {
      title: "Analytics",
      terms: [
        ["Density history line", "Each road's density score, sampled once per second, for the last minute."],
        ["Overall avg wait", "Total seconds vehicles spent stopped before the stop line, divided by vehicles that have left. Driving time is not counted."],
        ["Exited", "Vehicles that have fully crossed the junction and left the map."],
      ],
    },
    {
      title: "Fixed vs. Adaptive tab",
      terms: [
        ["Primary", "The simulation shown on the main dashboard."],
        ["Shadow", "An identical copy running the other controller, side by side."],
        ["Same traffic", "Both start from the same random seed, so they receive the same arriving vehicles — only the controller differs."],
        ["Avg wait delta", "Shadow's average wait minus primary's. Negative means the shadow controller made vehicles wait less."],
      ],
    },
  ];

  return (
    <div className="grid gap-5 xl:grid-cols-2">
      {groups.map((group) => (
        <div key={group.title}>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-white/60">{group.title}</h3>
          <dl className="space-y-2">
            {group.terms.map(([term, meaning]) => (
              <div key={term} className="rounded bg-panelmuted px-3 py-2">
                <dt className="text-sm font-semibold text-white/85">{term}</dt>
                <dd className="mt-0.5 text-sm leading-relaxed text-white/60">{meaning}</dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
    </div>
  );
}

export default function HowItWorks({ snapshot, explain }) {
  if (!explain) {
    return (
      <div className="rounded-lg border border-white/10 bg-panel p-6 text-sm text-white/50">
        Loading the live formula values from the backend...
      </div>
    );
  }

  const { queued_multiplier: q, moving_multiplier: m } = explain.density;

  return (
    <div className="space-y-5">
      <Section title="How it works in five steps" subtitle="From camera to traffic light.">
        <Pipeline />
      </Section>

      <Section
        title="Live density calculation"
        subtitle={`Worked out from the vehicles on the road right now, with the same formula the controller uses. Each vehicle type has a weight; a waiting vehicle is multiplied by ${fmt(q)} and a moving one by ${fmt(m)}.`}
      >
        <WeightChips explain={explain} />
        <div className="mt-4">
          <LiveDensity snapshot={snapshot} explain={explain} />
        </div>
      </Section>

      <Section
        title="How the lights are decided"
        subtitle="The highlighted card is the logic running at this moment. Every number here is read live from the backend."
      >
        <ControllerRules snapshot={snapshot} explain={explain} />
      </Section>

      <Section title="Signal phase codes" subtitle="The code shown in Signal Status. The current one is highlighted.">
        <PhaseTable phase={snapshot?.active_phase} />
      </Section>

      <Section title="What every number means" subtitle="Grouped by where it appears on the dashboard.">
        <Glossary explain={explain} />
      </Section>
    </div>
  );
}
