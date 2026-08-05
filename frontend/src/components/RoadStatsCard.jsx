export default function RoadStatsCard({ snapshot, connected }) {
  const totalVehicles = snapshot?.total_active_vehicles ?? 0;
  const simTime = snapshot?.sim_time ?? 0;
  const controller = snapshot?.controller ?? "-";

  return (
    <div className="rounded-lg border border-white/10 bg-panel p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-white/70">
        Simulation Overview
      </h2>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <Stat label="Connection" value={connected ? "Live" : "Reconnecting..."} />
        <Stat label="Controller" value={controller} />
        <Stat label="Active Vehicles" value={totalVehicles} />
        <Stat label="Sim Time" value={`${simTime.toFixed(1)}s`} />
      </div>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded bg-panelmuted px-3 py-2">
      <div className="text-xs text-white/40">{label}</div>
      <div className="font-medium text-white/90">{value}</div>
    </div>
  );
}
