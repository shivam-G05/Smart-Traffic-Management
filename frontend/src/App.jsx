import CameraFeedGrid from "./components/CameraFeedGrid.jsx";
import IntersectionCanvas from "./components/IntersectionCanvas.jsx";
import RoadStatsCard from "./components/RoadStatsCard.jsx";
import SignalStatusPanel from "./components/SignalStatusPanel.jsx";
import { useSimulationSocket } from "./hooks/useSimulationSocket.js";
import { useVisionSocket } from "./hooks/useVisionSocket.js";

export default function App() {
  const { snapshot, connected } = useSimulationSocket();
  const { snapshot: visionSnapshot } = useVisionSocket();

  return (
    <div className="min-h-screen bg-[#0a0e13] px-6 py-6 text-white">
      <header className="mb-6">
        <h1 className="text-xl font-bold">AI Smart Traffic Management</h1>
        <p className="text-sm text-white/50">
          Milestone 3 — multi-object tracking (ByteTrack) on top of Haar Cascade detection
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[640px_1fr]">
        <div className="space-y-4">
          <div className="flex justify-center">
            <IntersectionCanvas snapshot={snapshot} />
          </div>
          <CameraFeedGrid snapshot={visionSnapshot} />
        </div>
        <div className="space-y-4">
          <RoadStatsCard snapshot={snapshot} connected={connected} />
          <SignalStatusPanel snapshot={snapshot} />
        </div>
      </div>
    </div>
  );
}
