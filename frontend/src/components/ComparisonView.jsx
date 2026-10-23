import { useEffect, useState } from "react";

import IntersectionCanvas from "./IntersectionCanvas.jsx";
import { useSimulationSocket } from "../hooks/useSimulationSocket.js";

const SHADOW_WS_URL =
  import.meta.env.VITE_SHADOW_WS_URL ?? "ws://127.0.0.1:8000/ws/simulation/shadow";
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

function useComparisonPoll() {
  const [comparison, setComparison] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const res = await fetch(`${API_BASE_URL}/api/comparison/latest`);
        const data = await res.json();
        if (!cancelled && data && Object.keys(data).length > 0) setComparison(data);
      } catch {
        // transient fetch error — the next poll will retry
      }
    }

    poll();
    const interval = setInterval(poll, 2000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return comparison;
}

function SideLabel({ label, controllerType }) {
  return (
    <div className="mb-2 flex items-center justify-between">
      <span className="text-sm font-semibold uppercase tracking-wide text-white/70">{label}</span>
      <span className="rounded bg-panelmuted px-2 py-1 text-xs capitalize text-white/60">
        {controllerType ?? "-"}
      </span>
    </div>
  );
}

function DeltaStrip({ comparison }) {
  if (!comparison) {
    return (
      <div className="rounded-lg border border-white/10 bg-panel p-4 text-sm text-white/50">
        Waiting for comparison data...
      </div>
    );
  }

  const { delta, primary, shadow } = comparison;
  const waitBetter = delta.avg_wait_time_s !== null && delta.avg_wait_time_s < 0;

  return (
    <div className="rounded-lg border border-white/10 bg-panel p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-white/70">
        Fixed vs. Adaptive — Live Comparison
      </h2>
      <div className="grid grid-cols-3 gap-3 text-center text-sm">
        <div className="rounded bg-panelmuted p-3">
          <div className="text-xs uppercase text-white/40">Primary total exited</div>
          <div className="text-lg font-semibold text-white/90">{primary.overall.total_exited}</div>
        </div>
        <div className="rounded bg-panelmuted p-3">
          <div className="text-xs uppercase text-white/40">Shadow total exited</div>
          <div className="text-lg font-semibold text-white/90">{shadow.overall.total_exited}</div>
        </div>
        <div className="rounded bg-panelmuted p-3">
          <div className="text-xs uppercase text-white/40">Avg wait delta (shadow - primary)</div>
          <div className={`text-lg font-semibold ${waitBetter ? "text-emerald-400" : "text-white/90"}`}>
            {delta.avg_wait_time_s === null ? "-" : `${delta.avg_wait_time_s}s`}
          </div>
        </div>
      </div>
      <dl className="mt-3 grid gap-1 text-[11px] leading-snug text-white/45 sm:grid-cols-2">
        <div>
          <dt className="inline font-semibold text-white/65">Primary</dt>{" "}
          <dd className="inline">— the simulation on the main dashboard.</dd>
        </div>
        <div>
          <dt className="inline font-semibold text-white/65">Shadow</dt>{" "}
          <dd className="inline">— an identical copy running the other controller.</dd>
        </div>
        <div>
          <dt className="inline font-semibold text-white/65">Same traffic</dt>{" "}
          <dd className="inline">
            — both start from the same random seed, so they receive the same arriving vehicles; only the controller
            differs.
          </dd>
        </div>
        <div>
          <dt className="inline font-semibold text-white/65">Total exited</dt>{" "}
          <dd className="inline">— vehicles that have fully crossed the junction and left.</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="inline font-semibold text-white/65">Avg wait delta</dt>{" "}
          <dd className="inline">
            — shadow's average wait minus primary's. Negative (green) means the shadow controller made vehicles wait
            less. Shows &ldquo;-&rdquo; until both sides have had a vehicle leave.
          </dd>
        </div>
      </dl>
    </div>
  );
}

export default function ComparisonView() {
  const { snapshot: primarySnapshot } = useSimulationSocket();
  const { snapshot: shadowSnapshot } = useSimulationSocket(SHADOW_WS_URL);
  const comparison = useComparisonPoll();

  return (
    <div className="space-y-4">
      <DeltaStrip comparison={comparison} />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <SideLabel label="Primary" controllerType={comparison?.primary?.controller_type} />
          <IntersectionCanvas snapshot={primarySnapshot} showLegend={false} />
        </div>
        <div>
          <SideLabel label="Shadow" controllerType={comparison?.shadow?.controller_type} />
          <IntersectionCanvas snapshot={shadowSnapshot} showLegend={false} />
        </div>
      </div>
    </div>
  );
}
