import { useState } from "react";

import AnalyticsDashboard from "./components/AnalyticsDashboard.jsx";
import CameraFeedGrid from "./components/CameraFeedGrid.jsx";
import ComparisonView from "./components/ComparisonView.jsx";
import HowItWorks from "./components/HowItWorks.jsx";
import IntersectionCanvas from "./components/IntersectionCanvas.jsx";
import RoadStatsCard from "./components/RoadStatsCard.jsx";
import SignalStatusPanel from "./components/SignalStatusPanel.jsx";
import TrafficAlertBanner from "./components/TrafficAlertBanner.jsx";
import { useAnalyticsSocket } from "./hooks/useAnalyticsSocket.js";
import { useExplain } from "./hooks/useExplain.js";
import { useSimulationSocket } from "./hooks/useSimulationSocket.js";
import { useVisionSocket } from "./hooks/useVisionSocket.js";

const TABS = [
  { id: "dashboard", label: "Dashboard" },
  { id: "comparison", label: "Fixed vs. Adaptive" },
  { id: "how", label: "How it works" },
];

export default function App() {
  const [tab, setTab] = useState("dashboard");
  const { snapshot, connected } = useSimulationSocket();
  const { snapshot: visionSnapshot } = useVisionSocket();
  const { snapshot: analyticsSnapshot } = useAnalyticsSocket();
  const explain = useExplain();

  return (
    <div className="min-h-screen bg-[#0a0e13] px-6 py-6 text-white">
      <header className="mb-5">
        <h1 className="text-xl font-bold">AI Smart Traffic Management</h1>
        <p className="mb-3 text-sm text-white/50">
          Adaptive, density-based signal control with emergency override, camera detection and tracking,
          live analytics, and a fixed-vs-adaptive comparison
        </p>
        <div className="flex flex-wrap gap-2">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`rounded px-3 py-1.5 text-sm ${
                tab === t.id ? "bg-cyan-600/30 text-cyan-300" : "bg-panelmuted text-white/60"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </header>

      {tab === "dashboard" && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[760px_1fr]">
          <div className="space-y-4">
            <IntersectionCanvas snapshot={snapshot} />
            <CameraFeedGrid snapshot={visionSnapshot} explain={explain} />
          </div>
          {/* The alert sits at the top of the side column rather than above the
              canvas, so its height changing never shifts the intersection view. */}
          <div className="space-y-4">
            <TrafficAlertBanner snapshot={snapshot} explain={explain} onExplain={() => setTab("how")} />
            <RoadStatsCard snapshot={snapshot} connected={connected} />
            <SignalStatusPanel snapshot={snapshot} explain={explain} />
            <AnalyticsDashboard snapshot={analyticsSnapshot} />
          </div>
        </div>
      )}
      {tab === "comparison" && <ComparisonView />}
      {tab === "how" && <HowItWorks snapshot={snapshot} explain={explain} />}
    </div>
  );
}
