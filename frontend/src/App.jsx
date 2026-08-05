import IntersectionCanvas from "./components/IntersectionCanvas.jsx";
import RoadStatsCard from "./components/RoadStatsCard.jsx";
import SignalStatusPanel from "./components/SignalStatusPanel.jsx";
import { useSimulationSocket } from "./hooks/useSimulationSocket.js";

export default function App() {
  const { snapshot, connected } = useSimulationSocket();

  return (
    <div className="min-h-screen bg-[#0a0e13] px-6 py-6 text-white">
      <header className="mb-6">
        <h1 className="text-xl font-bold">AI Smart Traffic Management</h1>
        <p className="text-sm text-white/50">
          Milestone 1 — live simulation, fixed-timer baseline controller
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[640px_1fr]">
        <div className="flex justify-center">
          <IntersectionCanvas snapshot={snapshot} />
        </div>
        <div className="space-y-4">
          <RoadStatsCard snapshot={snapshot} connected={connected} />
          <SignalStatusPanel snapshot={snapshot} />
        </div>
      </div>
    </div>
  );
}
