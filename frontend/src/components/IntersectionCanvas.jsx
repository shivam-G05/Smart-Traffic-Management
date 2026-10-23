import { useEffect, useRef } from "react";

import { CANVAS_SIZE, VEHICLE_LEGEND, drawIntersection } from "../utils/draw.js";

export default function IntersectionCanvas({ snapshot, showLegend = true }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    drawIntersection(canvasRef.current, snapshot);
  }, [snapshot]);

  return (
    <div className="w-full">
      <canvas
        ref={canvasRef}
        width={CANVAS_SIZE}
        height={CANVAS_SIZE}
        className="h-auto max-w-full rounded-lg border border-white/10 bg-[#070b12]"
      />

      <div
        className="mt-3 rounded-lg border border-white/10 bg-panel px-3 py-2"
        hidden={!showLegend}
      >
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-white/60">
          {VEHICLE_LEGEND.map((item) => (
            <span key={item.type} className="flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-4 rounded-[2px]"
                style={{ backgroundColor: item.color }}
              />
              {item.label}
            </span>
          ))}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-white/5 pt-2 text-[11px] text-white/60">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-4 rounded-[2px] border-2 border-red-500 bg-white/25" />
            Stopped / queued
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-4 rounded-[2px] border border-black bg-white/25" />
            Moving (yellow edge = front)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-4 rounded-[2px] border-2 border-white bg-white/25" />
            Emergency (flashing)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-4 rounded-[2px] border border-red-500 bg-red-500/40" />
            Red pulsing road = high traffic
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-4 rounded-[2px] bg-amber-400/40" />
            Amber road = building up
          </span>
        </div>
      </div>
    </div>
  );
}
