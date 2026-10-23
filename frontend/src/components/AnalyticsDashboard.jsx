import { useEffect, useRef, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const ROAD_ORDER = ["north", "east", "south", "west"];
const HISTORY_WINDOW = 60; // ~60 samples at the collector's 1Hz rate = last minute

const CONGESTION_CLASS = {
  low: "bg-emerald-500/20 text-emerald-400",
  medium: "bg-amber-500/20 text-amber-400",
  high: "bg-red-500/20 text-red-400",
};

/** Accumulates the single-latest-sample-per-road WS snapshots into a
 * rolling per-road time series client-side, deduping on sim_time so a
 * socket reconnect replay doesn't double-append the same sample. */
function useRollingHistory(snapshot) {
  const [historyByRoad, setHistoryByRoad] = useState({});
  const lastSimTimeRef = useRef({});

  useEffect(() => {
    if (!snapshot) return;
    setHistoryByRoad((prev) => {
      const next = { ...prev };
      for (const [road, entry] of Object.entries(snapshot)) {
        if (!entry) continue;
        if (lastSimTimeRef.current[road] === entry.sim_time) continue;
        lastSimTimeRef.current[road] = entry.sim_time;
        next[road] = [...(prev[road] ?? []), entry].slice(-HISTORY_WINDOW);
      }
      return next;
    });
  }, [snapshot]);

  return historyByRoad;
}

function useAnalyticsSummary() {
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const base = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

    async function poll() {
      try {
        const res = await fetch(`${base}/api/analytics/summary`);
        const data = await res.json();
        if (!cancelled) setSummary(data);
      } catch {
        // transient fetch error — the next poll will retry
      }
    }

    poll();
    const interval = setInterval(poll, 3000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return summary;
}

function RoadDensityChart({ road, series }) {
  const latest = series[series.length - 1];

  return (
    <div className="rounded-lg border border-white/10 bg-panelmuted p-3">
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-medium capitalize text-white/80">{road}</span>
        {latest && (
          <span className={`rounded px-1.5 py-0.5 text-[10px] ${CONGESTION_CLASS[latest.congestion_level] ?? ""}`}>
            {latest.congestion_level}
          </span>
        )}
      </div>
      <div className="h-24 w-full">
        {series.length > 1 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={series}>
              <XAxis dataKey="sim_time" hide />
              <YAxis hide domain={[0, "dataMax + 2"]} />
              <Tooltip
                formatter={(value) => (typeof value === "number" ? value.toFixed(1) : value)}
                labelFormatter={(t) => `t=${t}s`}
                contentStyle={{
                  background: "#0f141b",
                  border: "1px solid rgba(255,255,255,0.1)",
                  fontSize: 11,
                }}
              />
              <Line
                type="monotone"
                dataKey="density_score"
                stroke="#38bdf8"
                dot={false}
                strokeWidth={1.5}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-full items-center justify-center text-[11px] text-white/30">
            Collecting samples...
          </div>
        )}
      </div>
    </div>
  );
}

export default function AnalyticsDashboard({ snapshot }) {
  const historyByRoad = useRollingHistory(snapshot);
  const summary = useAnalyticsSummary();

  return (
    <div className="rounded-lg border border-white/10 bg-panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-white/70">
          Analytics — Density History &amp; Congestion
        </h2>
        {summary && (
          <span className="text-xs text-white/50">
            Overall avg wait: {summary.overall.avg_wait_time_s ?? "-"}s · {summary.overall.total_exited} exited
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-3">
        {ROAD_ORDER.map((road) => (
          <RoadDensityChart key={road} road={road} series={historyByRoad[road] ?? []} />
        ))}
      </div>
      <dl className="mt-3 space-y-1 text-[11px] leading-snug text-white/45">
        <div>
          <dt className="inline font-semibold text-white/65">Line</dt>{" "}
          <dd className="inline">— each road's density score, sampled live once per second (last minute shown).</dd>
        </div>
        <div>
          <dt className="inline font-semibold text-white/65">Badge</dt>{" "}
          <dd className="inline">— that road's traffic level right now: low, medium or high.</dd>
        </div>
        <div>
          <dt className="inline font-semibold text-white/65">Overall avg wait</dt>{" "}
          <dd className="inline">
            — total seconds vehicles spent stopped before the stop line ÷ vehicles that have left. Driving time
            isn't counted.
          </dd>
        </div>
        <div>
          <dt className="inline font-semibold text-white/65">Exited</dt>{" "}
          <dd className="inline">— vehicles that have fully crossed the junction and left the map.</dd>
        </div>
      </dl>
    </div>
  );
}
