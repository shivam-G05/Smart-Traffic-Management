function friendlyController(controller) {
  if (!controller) return "-";
  const base = controller.includes("AdaptiveController")
    ? "Adaptive"
    : controller.includes("FixedTimerController")
      ? "Fixed timer"
      : controller;
  return controller.startsWith("EmergencyPreemptionController") ? `${base} + emergency override` : base;
}

export default function RoadStatsCard({ snapshot, connected }) {
  const totalVehicles = snapshot?.total_active_vehicles ?? 0;
  const simTime = snapshot?.sim_time ?? 0;
  const controller = snapshot?.controller;

  return (
    <div className="rounded-lg border border-white/10 bg-panel p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-white/70">
        Simulation Overview
      </h2>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <Stat
          label="Connection"
          value={connected ? "Live" : "Reconnecting..."}
          hint="Link to the backend — updates arrive about 10 times a second"
        />
        <Stat
          label="Controller"
          value={friendlyController(controller)}
          hint={controller ?? "Which signal logic is deciding the lights"}
          monoHint={Boolean(controller)}
        />
        <Stat label="Active Vehicles" value={totalVehicles} hint="Vehicles on all four roads right now" />
        <Stat label="Sim Time" value={`${simTime.toFixed(1)}s`} hint="Simulated seconds since the backend started" />
      </div>
    </div>
  );
}

function Stat({ label, value, hint, monoHint = false }) {
  return (
    <div className="rounded bg-panelmuted px-3 py-2">
      <div className="text-xs text-white/40">{label}</div>
      <div className="font-medium text-white/90">{value}</div>
      {hint && (
        <div className={`mt-0.5 text-[10px] leading-snug text-white/35 ${monoHint ? "break-all font-mono" : ""}`}>
          {hint}
        </div>
      )}
    </div>
  );
}
