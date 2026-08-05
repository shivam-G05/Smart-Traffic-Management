import { useEffect, useRef } from "react";

import { CANVAS_SIZE, drawIntersection } from "../utils/draw.js";

export default function IntersectionCanvas({ snapshot }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    drawIntersection(canvasRef.current, snapshot);
  }, [snapshot]);

  return (
    <canvas
      ref={canvasRef}
      width={CANVAS_SIZE}
      height={CANVAS_SIZE}
      className="rounded-lg border border-white/10 bg-[#161b22] max-w-full h-auto"
    />
  );
}
