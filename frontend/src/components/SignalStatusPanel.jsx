const LIGHT_DOT_CLASS = {
  red: "bg-red-500",
  yellow: "bg-yellow-400",
  green: "bg-green-500",
};

export default function SignalStatusPanel({ snapshot }) {
  if (!snapshot) {
    return (
      <div className="rounded-lg border border-white/10 bg-panel p-4 text-sm text-white/50">
        Waiting for simulation data...
      </div>
    );
  }

  const roads = Object.entries(snapshot.roads);

  return (
    <div className="rounded-lg border border-white/10 bg-panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-white/70">
          Signal Status
        </h2>
        <span className="rounded bg-panelmuted px-2 py-1 text-xs text-white/60">
          Phase: {snapshot.active_phase}
        </span>
      </div>
      <div className="space-y-2">
        {roads.map(([name, road]) => (
          <div
            key={name}
            className="flex items-center justify-between rounded bg-panelmuted px-3 py-2 text-sm"
          >
            <div className="flex items-center gap-2">
              <span
                className={`h-3 w-3 rounded-full ${LIGHT_DOT_CLASS[road.light.state]}`}
              />
              <span className="capitalize text-white/80">{name}</span>
              {road.has_emergency_vehicle && (
                <span className="rounded bg-red-500/20 px-1.5 py-0.5 text-xs text-red-400">
                  EMERGENCY
                </span>
              )}
            </div>
            <div className="flex gap-4 text-white/50">
              <span>Queue: {road.queue_length}</span>
              <span>Vehicles: {road.vehicle_count}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
