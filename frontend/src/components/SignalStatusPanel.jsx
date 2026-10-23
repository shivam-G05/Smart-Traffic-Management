import { describePhase } from "../utils/phases.js";

const LIGHT_DOT_CLASS = {
  red: "bg-red-500",
  yellow: "bg-yellow-400",
  green: "bg-green-500",
};

const CONGESTION_BADGE = {
  low: "bg-emerald-500/15 text-emerald-300",
  medium: "bg-amber-500/15 text-amber-300",
  high: "bg-red-500/25 text-red-200 ring-1 ring-red-500/70",
};

export default function SignalStatusPanel({ snapshot, explain }) {
  if (!snapshot) {
    return (
      <div className="rounded-lg border border-white/10 bg-panel p-4 text-sm text-white/50">
        Waiting for simulation data...
      </div>
    );
  }

  const roads = Object.entries(snapshot.roads);
  const density = explain?.density;
  const congestion = explain?.congestion;

  return (
    <div className="rounded-lg border border-white/10 bg-panel p-4">
      <div className="mb-1 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-white/70">
          Signal Status
        </h2>
        <span className="rounded bg-panelmuted px-2 py-1 font-mono text-xs text-white/60">
          {snapshot.active_phase}
        </span>
      </div>
      <p className="mb-3 text-right text-xs text-white/45">{describePhase(snapshot.active_phase)}</p>

      <div className="space-y-2">
        {roads.map(([name, road]) => (
          <div
            key={name}
            className={`flex flex-wrap items-center justify-between gap-2 rounded px-3 py-2 text-sm ${
              road.high_traffic_alert ? "bg-red-950/60" : "bg-panelmuted"
            }`}
          >
            <div className="flex items-center gap-2">
              <span className={`h-3 w-3 rounded-full ${LIGHT_DOT_CLASS[road.light.state]}`} />
              <span className="capitalize text-white/80">{name}</span>
              {road.congestion_level && (
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
                    CONGESTION_BADGE[road.congestion_level] ?? ""
                  }`}
                >
                  {road.congestion_level}
                </span>
              )}
              {road.has_emergency_vehicle && (
                <span className="rounded bg-red-500/20 px-1.5 py-0.5 text-xs text-red-400">
                  EMERGENCY
                </span>
              )}
            </div>
            <div className="flex gap-4 text-white/50">
              <span>Queue: {road.queue_length}</span>
              <span>Vehicles: {road.vehicle_count}</span>
              <span>Density: {road.density_score?.toFixed(1)}</span>
            </div>
          </div>
        ))}
      </div>

      {density && congestion && (
        <dl className="mt-3 space-y-1 border-t border-white/5 pt-3 text-[11px] leading-snug text-white/45">
          <div>
            <dt className="inline font-semibold text-white/65">Queue</dt>{" "}
            <dd className="inline">
              — vehicles waiting before the stop line (speed below {density.queued_speed_mps} m/s).
            </dd>
          </div>
          <div>
            <dt className="inline font-semibold text-white/65">Vehicles</dt>{" "}
            <dd className="inline">— every vehicle on that approach, moving or waiting.</dd>
          </div>
          <div>
            <dt className="inline font-semibold text-white/65">Density</dt>{" "}
            <dd className="inline">
              — how much a road "needs" green: sum of each vehicle's weight × {density.queued_multiplier} if
              waiting, × {density.moving_multiplier} if moving. Heavier vehicles (bus, truck, ambulance) weigh more.
            </dd>
          </div>
          <div>
            <dt className="inline font-semibold text-white/65">Low / Medium / High</dt>{" "}
            <dd className="inline">
              — density ≤ {congestion.low_max} is low, up to {congestion.high_min} is medium, above that is high traffic.
              The red HIGH TRAFFIC alert switches off only after density has stayed at or below{" "}
              {congestion.high_min} for {congestion.alert_hold_s}s, so it doesn't flicker.
            </dd>
          </div>
        </dl>
      )}
    </div>
  );
}
