export const CANVAS_SIZE = 760;
const CENTER = CANVAS_SIZE / 2;

// Mirrors simulation/config.py
const STOP_LINE_POS_M = 200;
const INTERSECTION_EXIT_POS_M = 218;

// True scale along the direction of travel: a vehicle is drawn exactly as
// long as it is in the simulation, and the gap between two vehicles exactly
// as large as it is. That is what guarantees the canvas never shows two
// vehicles overlapping unless the simulation itself has them overlapping
// (which lane.py forbids). At 3px/m the last ~105m of each approach is on
// screen; vehicles spawn further back and drive in from the edge.
const SCALE_PX_PER_M = 3;

// One carriageway = one approach's 2 lanes. The two opposing carriageways
// together make up a road band, so the intersection box is exactly the
// overlap of the two bands. The box maps 18m onto 108px (6px/m) — steeper
// than the approach scale, so spacing only ever stretches inside it.
const CARRIAGEWAY_PX = 54;
const LANE_PX = CARRIAGEWAY_PX / 2;
const BOX_HALF_PX = CARRIAGEWAY_PX;
const SIGNAL_GAP_PX = 16;

// Points from the stop line back toward the spawn point — i.e. the
// opposite of the direction vehicles actually travel.
const DIRECTION = {
  north: { x: 0, y: -1 },
  south: { x: 0, y: 1 },
  east: { x: 1, y: 0 },
  west: { x: -1, y: 0 },
};

// Traffic keeps LEFT (matching the project's Indian context), so each
// approach gets its own carriageway on the left-hand side of its travel
// direction. Without this, opposing traffic renders on top of itself.
const CARRIAGEWAY_SIDE = {
  north: { x: 1, y: 0 },
  south: { x: -1, y: 0 },
  east: { x: 0, y: 1 },
  west: { x: 0, y: -1 },
};

const APPROACH_LABEL = {
  north: "NORTH ↓",
  south: "SOUTH ↑",
  east: "EAST ←",
  west: "WEST →",
};

// Width is exaggerated for legibility (it can't cause overlaps — lanes are
// 27px apart). Length always comes from the simulation's own value.
const VEHICLE_STYLE = {
  motorcycle: { color: "#f472b6", width: 8, label: "Motorcycle" },
  auto: { color: "#10b981", width: 11, label: "Auto" },
  car: { color: "#3b82f6", width: 13, label: "Car" },
  ambulance: { color: "#e2e8f0", width: 14, label: "Ambulance" },
  truck: { color: "#a855f7", width: 15, label: "Truck" },
  bus: { color: "#f59e0b", width: 15, label: "Bus" },
  fire_truck: { color: "#dc2626", width: 15, label: "Fire truck" },
};

// Only used if a snapshot predates vehicles carrying their own `length`.
const FALLBACK_LENGTH_M = {
  motorcycle: 2.0,
  auto: 3.2,
  car: 4.5,
  ambulance: 5.5,
  truck: 9.0,
  bus: 10.0,
  fire_truck: 10.5,
};

export const VEHICLE_LEGEND = Object.entries(VEHICLE_STYLE).map(([type, s]) => ({
  type,
  label: s.label,
  color: s.color,
}));

const STOPPED_SPEED_MPS = 0.5; // same threshold the simulation uses for "queued"

const LIGHT_COLORS = { red: "#f87171", yellow: "#fbbf24", green: "#4ade80" };
const LIGHT_OFF_COLOR = "#353b45";

const COLOR_BG = "#070b12";
const COLOR_ROAD = "#333b47";
const COLOR_BOX = "#3d4653";
const COLOR_KERB = "#5d6675";
const COLOR_MEDIAN = "#fbbf24";
const COLOR_LANE_DASH = "#cbd5e1";
const COLOR_STOP_LINE = "#f8fafc";

/** Signed distance from the canvas centre along the approach axis:
 *  positive = approach side, negative = past the intersection. */
function signedDistanceFromCenter(positionM) {
  if (positionM <= STOP_LINE_POS_M) {
    return BOX_HALF_PX + (STOP_LINE_POS_M - positionM) * SCALE_PX_PER_M;
  }
  if (positionM >= INTERSECTION_EXIT_POS_M) {
    return -(BOX_HALF_PX + (positionM - INTERSECTION_EXIT_POS_M) * SCALE_PX_PER_M);
  }
  const t = (positionM - STOP_LINE_POS_M) / (INTERSECTION_EXIT_POS_M - STOP_LINE_POS_M);
  return BOX_HALF_PX * (1 - 2 * t);
}

function roadPoint(road, positionM, laneIndex, lanesPerRoad) {
  const dir = DIRECTION[road];
  const side = CARRIAGEWAY_SIDE[road];
  const along = signedDistanceFromCenter(positionM);
  const laneOffset = ((laneIndex + 0.5) / lanesPerRoad) * CARRIAGEWAY_PX;
  return {
    x: CENTER + dir.x * along + side.x * laneOffset,
    y: CENTER + dir.y * along + side.y * laneOffset,
  };
}

function roundedRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  if (typeof ctx.roundRect === "function") ctx.roundRect(x, y, w, h, r);
  else ctx.rect(x, y, w, h);
}

/** Screen rectangle covering one approach's carriageway, from the box edge
 * out to the canvas edge. */
function carriagewayRect(road) {
  const dir = DIRECTION[road];
  const side = CARRIAGEWAY_SIDE[road];
  const reach = CANVAS_SIZE / 2 - BOX_HALF_PX;
  const ax = CENTER + dir.x * BOX_HALF_PX;
  const ay = CENTER + dir.y * BOX_HALF_PX;
  const bx = CENTER + dir.x * (BOX_HALF_PX + reach) + side.x * CARRIAGEWAY_PX;
  const by = CENTER + dir.y * (BOX_HALF_PX + reach) + side.y * CARRIAGEWAY_PX;
  return { x: Math.min(ax, bx), y: Math.min(ay, by), w: Math.abs(bx - ax), h: Math.abs(by - ay) };
}

function drawRoads(ctx) {
  ctx.fillStyle = COLOR_BG;
  ctx.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);

  const bands = [
    { x: CENTER - CARRIAGEWAY_PX, y: 0, w: CARRIAGEWAY_PX * 2, h: CANVAS_SIZE },
    { x: 0, y: CENTER - CARRIAGEWAY_PX, w: CANVAS_SIZE, h: CARRIAGEWAY_PX * 2 },
  ];
  ctx.fillStyle = COLOR_ROAD;
  bands.forEach((b) => ctx.fillRect(b.x, b.y, b.w, b.h));
  ctx.strokeStyle = COLOR_KERB;
  ctx.lineWidth = 2;
  bands.forEach((b) => ctx.strokeRect(b.x, b.y, b.w, b.h));

  // Filled last so it covers the kerb strokes that would otherwise run
  // straight through the junction.
  ctx.fillStyle = COLOR_BOX;
  ctx.fillRect(CENTER - BOX_HALF_PX, CENTER - BOX_HALF_PX, BOX_HALF_PX * 2, BOX_HALF_PX * 2);
}

function drawCongestionOverlays(ctx, roads) {
  const pulse = 0.5 + 0.5 * Math.sin(Date.now() / 250);
  Object.entries(roads).forEach(([roadName, road]) => {
    // The red pulse follows the held alert (not the instantaneous level) so
    // it doesn't flicker when density hovers around the threshold.
    const alertOn = road.high_traffic_alert ?? road.congestion_level === "high";
    const level = road.congestion_level;
    if (!alertOn && level !== "medium") return;
    const r = carriagewayRect(roadName);
    if (alertOn) {
      ctx.fillStyle = `rgba(239,68,68,${0.12 + 0.14 * pulse})`;
      ctx.fillRect(r.x, r.y, r.w, r.h);
      ctx.strokeStyle = `rgba(239,68,68,${0.55 + 0.45 * pulse})`;
      ctx.lineWidth = 2;
      ctx.strokeRect(r.x + 1, r.y + 1, r.w - 2, r.h - 2);
    } else {
      ctx.fillStyle = "rgba(251,191,36,0.09)";
      ctx.fillRect(r.x, r.y, r.w, r.h);
    }
  });
}

function drawMarkings(ctx) {
  const outer = [
    [0, CENTER - BOX_HALF_PX],
    [CENTER + BOX_HALF_PX, CANVAS_SIZE],
  ];

  // Median: solid, separating opposing carriageways.
  ctx.strokeStyle = COLOR_MEDIAN;
  ctx.globalAlpha = 0.75;
  ctx.lineWidth = 2;
  ctx.beginPath();
  outer.forEach(([a, b]) => {
    ctx.moveTo(CENTER, a);
    ctx.lineTo(CENTER, b);
    ctx.moveTo(a, CENTER);
    ctx.lineTo(b, CENTER);
  });
  ctx.stroke();

  // Lane dividers: dashed, inside each carriageway.
  ctx.strokeStyle = COLOR_LANE_DASH;
  ctx.globalAlpha = 0.4;
  ctx.setLineDash([9, 11]);
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  [-LANE_PX, LANE_PX].forEach((off) => {
    outer.forEach(([a, b]) => {
      ctx.moveTo(CENTER + off, a);
      ctx.lineTo(CENTER + off, b);
      ctx.moveTo(a, CENTER + off);
      ctx.lineTo(b, CENTER + off);
    });
  });
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.globalAlpha = 1;

  // Stop lines: one per approach, at that approach's edge of the box,
  // spanning only its own carriageway.
  ctx.strokeStyle = COLOR_STOP_LINE;
  ctx.lineWidth = 4;
  Object.keys(DIRECTION).forEach((road) => {
    const dir = DIRECTION[road];
    const side = CARRIAGEWAY_SIDE[road];
    const bx = CENTER + dir.x * BOX_HALF_PX;
    const by = CENTER + dir.y * BOX_HALF_PX;
    ctx.beginPath();
    ctx.moveTo(bx, by);
    ctx.lineTo(bx + side.x * CARRIAGEWAY_PX, by + side.y * CARRIAGEWAY_PX);
    ctx.stroke();
  });
}

function drawApproachLabels(ctx) {
  ctx.save();
  ctx.font = "600 13px ui-sans-serif, system-ui, sans-serif";
  ctx.fillStyle = "rgba(226,232,240,0.55)";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  Object.keys(DIRECTION).forEach((road) => {
    const dir = DIRECTION[road];
    const side = CARRIAGEWAY_SIDE[road];
    const along = BOX_HALF_PX + 285;
    ctx.fillText(
      APPROACH_LABEL[road],
      CENTER + dir.x * along + side.x * (CARRIAGEWAY_PX / 2),
      CENTER + dir.y * along + side.y * (CARRIAGEWAY_PX / 2)
    );
  });
  ctx.restore();
}

function drawTrafficLights(ctx, roads) {
  Object.entries(roads).forEach(([roadName, road]) => {
    const dir = DIRECTION[roadName];
    const side = CARRIAGEWAY_SIDE[roadName];
    // Beside its own stop line, just outside the kerb, in the corner of the
    // junction — so each signal is unambiguously tied to the queue it
    // controls, and no two signals land in the same corner.
    const pos = {
      x: CENTER + dir.x * (BOX_HALF_PX + 12) + side.x * (CARRIAGEWAY_PX + SIGNAL_GAP_PX),
      y: CENTER + dir.y * (BOX_HALF_PX + 12) + side.y * (CARRIAGEWAY_PX + SIGNAL_GAP_PX),
    };

    const boxW = 22;
    const boxH = 60;
    const dotR = 7;

    ctx.save();
    ctx.translate(pos.x, pos.y);
    if (dir.x !== 0) ctx.rotate(Math.PI / 2);

    ctx.strokeStyle = "#4b5563";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(0, boxH / 2);
    ctx.lineTo(0, boxH / 2 + 12);
    ctx.stroke();

    ctx.fillStyle = "#0b0e13";
    ctx.strokeStyle = "#99a1af";
    ctx.lineWidth = 1.5;
    roundedRect(ctx, -boxW / 2, -boxH / 2, boxW, boxH, 5);
    ctx.fill();
    ctx.stroke();

    ["red", "yellow", "green"].forEach((phase, i) => {
      const cy = -boxH / 2 + 12 + i * 18;
      const active = road.light.state === phase;
      ctx.beginPath();
      ctx.arc(0, cy, dotR, 0, Math.PI * 2);
      if (active) {
        ctx.shadowColor = LIGHT_COLORS[phase];
        ctx.shadowBlur = 16;
        ctx.fillStyle = LIGHT_COLORS[phase];
      } else {
        ctx.shadowBlur = 0;
        ctx.fillStyle = LIGHT_OFF_COLOR;
      }
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.lineWidth = 1;
      ctx.strokeStyle = "#1b1f26";
      ctx.stroke();
    });

    ctx.restore();
  });
}

function drawVehicles(ctx, roads) {
  const blinkOn = Math.floor(Date.now() / 260) % 2 === 0;

  Object.entries(roads).forEach(([roadName, road]) => {
    const dir = DIRECTION[roadName];
    const travel = { x: -dir.x, y: -dir.y };
    const alongY = dir.x === 0;

    road.lanes.forEach((lane) => {
      lane.vehicles.forEach((vehicle) => {
        const style = VEHICLE_STYLE[vehicle.type] ?? VEHICLE_STYLE.car;
        const lengthM = vehicle.length ?? FALLBACK_LENGTH_M[vehicle.type] ?? FALLBACK_LENGTH_M.car;
        const lengthPx = lengthM * SCALE_PX_PER_M;
        const nose = roadPoint(roadName, vehicle.position, lane.lane_index, road.lanes.length);
        // A vehicle's simulated position is its front bumper (it stops with
        // its nose at the stop line), so the body extends back along `dir`.
        const pos = {
          x: nose.x + dir.x * (lengthPx / 2),
          y: nose.y + dir.y * (lengthPx / 2),
        };
        const w = alongY ? style.width : lengthPx;
        const h = alongY ? lengthPx : style.width;
        const x = pos.x - w / 2;
        const y = pos.y - h / 2;
        const stopped = (vehicle.speed ?? 0) < STOPPED_SPEED_MPS;

        ctx.globalAlpha = stopped ? 0.78 : 1;
        roundedRect(ctx, x, y, w, h, 2.5);
        ctx.fillStyle = style.color;
        ctx.fill();
        ctx.globalAlpha = 1;

        // Red outline = stopped/queued, dark outline = rolling.
        ctx.lineWidth = stopped ? 2 : 1.25;
        ctx.strokeStyle = stopped ? "#ef4444" : "#0b1220";
        ctx.stroke();

        if (!stopped) {
          // Headlight bar on the leading edge — doubles as a heading cue.
          const halfLen = Math.max(0.5, lengthPx / 2 - 1.5);
          const halfWid = (style.width / 2) * 0.7;
          const perpV = { x: -travel.y, y: travel.x };
          const fx = pos.x + travel.x * halfLen;
          const fy = pos.y + travel.y * halfLen;
          ctx.beginPath();
          ctx.moveTo(fx - perpV.x * halfWid, fy - perpV.y * halfWid);
          ctx.lineTo(fx + perpV.x * halfWid, fy + perpV.y * halfWid);
          ctx.strokeStyle = "#fde68a";
          ctx.lineWidth = 2;
          ctx.stroke();
        }

        if (vehicle.emergency) {
          ctx.lineWidth = 2;
          ctx.strokeStyle = blinkOn ? "#ffffff" : "#2563eb";
          roundedRect(ctx, x - 2.5, y - 2.5, w + 5, h + 5, 4);
          ctx.stroke();
        }
      });
    });
  });
}

/** Pill-shaped label anchored beside a carriageway so it grows away from
 * the road rather than covering vehicles. */
function drawTag(ctx, text, x, y, side) {
  ctx.save();
  ctx.font = "700 12px ui-sans-serif, system-ui, sans-serif";
  const h = 22;
  const w = ctx.measureText(text).width + 14;
  let left = x - w / 2;
  let top = y - h / 2;
  if (side.x > 0) left = x;
  if (side.x < 0) left = x - w;
  if (side.y > 0) top = y;
  if (side.y < 0) top = y - h;
  roundedRect(ctx, left, top, w, h, 6);
  ctx.fillStyle = "#7f1d1d";
  ctx.fill();
  ctx.strokeStyle = "#ef4444";
  ctx.lineWidth = 1.5;
  ctx.stroke();
  ctx.fillStyle = "#fee2e2";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, left + w / 2, top + h / 2);
  ctx.restore();
}

function drawCongestionTags(ctx, roads) {
  Object.entries(roads).forEach(([roadName, road]) => {
    if (!(road.high_traffic_alert ?? road.congestion_level === "high")) return;
    const dir = DIRECTION[roadName];
    const side = CARRIAGEWAY_SIDE[roadName];
    const x = CENTER + dir.x * (BOX_HALF_PX + 150) + side.x * (CARRIAGEWAY_PX + 10);
    const y = CENTER + dir.y * (BOX_HALF_PX + 150) + side.y * (CARRIAGEWAY_PX + 10);
    drawTag(ctx, `HIGH TRAFFIC · density ${road.density_score.toFixed(1)}`, x, y, side);
  });
}

export function drawIntersection(canvas, snapshot) {
  if (!canvas || !snapshot) return;
  const ctx = canvas.getContext("2d");
  drawRoads(ctx);
  drawCongestionOverlays(ctx, snapshot.roads);
  drawMarkings(ctx);
  drawApproachLabels(ctx);
  drawTrafficLights(ctx, snapshot.roads);
  drawVehicles(ctx, snapshot.roads);
  drawCongestionTags(ctx, snapshot.roads);
}
