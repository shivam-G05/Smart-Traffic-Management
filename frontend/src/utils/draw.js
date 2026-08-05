export const CANVAS_SIZE = 640;
const CENTER = CANVAS_SIZE / 2;
const SCALE_PX_PER_M = 1.5; // pixels per simulated metre
const STOP_LINE_POS_M = 200;
const ROAD_HALF_WIDTH_PX = 46;
const LANE_WIDTH_PX = ROAD_HALF_WIDTH_PX; // 2 lanes per road
const INTERSECTION_HALF_PX = 34;

const DIRECTION = {
  north: { x: 0, y: -1 },
  south: { x: 0, y: 1 },
  east: { x: 1, y: 0 },
  west: { x: -1, y: 0 },
};
const PERPENDICULAR = {
  north: { x: 1, y: 0 },
  south: { x: 1, y: 0 },
  east: { x: 0, y: 1 },
  west: { x: 0, y: 1 },
};

const VEHICLE_STYLE = {
  car: { color: "#60a5fa", width: 1.8 },
  motorcycle: { color: "#a78bfa", width: 0.9 },
  auto: { color: "#34d399", width: 1.5 },
  bus: { color: "#f59e0b", width: 2.2 },
  truck: { color: "#fb923c", width: 2.2 },
  ambulance: { color: "#ef4444", width: 1.9 },
  fire_truck: { color: "#dc2626", width: 2.3 },
};

const LIGHT_COLORS = {
  red: "#ef4444",
  yellow: "#eab308",
  green: "#22c55e",
};

function roadPoint(road, positionM, laneIndex, lanesPerRoad) {
  const dir = DIRECTION[road];
  const perp = PERPENDICULAR[road];
  const offsetPx = (STOP_LINE_POS_M - positionM) * SCALE_PX_PER_M;
  const laneOffset = (laneIndex - (lanesPerRoad - 1) / 2) * LANE_WIDTH_PX * 0.55;
  return {
    x: CENTER + dir.x * offsetPx + perp.x * laneOffset,
    y: CENTER + dir.y * offsetPx + perp.y * laneOffset,
  };
}

function drawRoadsAndMarkings(ctx) {
  ctx.fillStyle = "#161b22";
  ctx.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);

  ctx.fillStyle = "#22282f";
  ctx.fillRect(CENTER - ROAD_HALF_WIDTH_PX, 0, ROAD_HALF_WIDTH_PX * 2, CANVAS_SIZE);
  ctx.fillRect(0, CENTER - ROAD_HALF_WIDTH_PX, CANVAS_SIZE, ROAD_HALF_WIDTH_PX * 2);

  ctx.fillStyle = "#2b323b";
  ctx.fillRect(
    CENTER - INTERSECTION_HALF_PX,
    CENTER - INTERSECTION_HALF_PX,
    INTERSECTION_HALF_PX * 2,
    INTERSECTION_HALF_PX * 2
  );

  ctx.strokeStyle = "#3a4250";
  ctx.setLineDash([6, 8]);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(CENTER, 0);
  ctx.lineTo(CENTER, CANVAS_SIZE);
  ctx.moveTo(0, CENTER);
  ctx.lineTo(CANVAS_SIZE, CENTER);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.strokeStyle = "#e5e7eb";
  ctx.lineWidth = 2;
  Object.keys(DIRECTION).forEach((road) => {
    const perp = PERPENDICULAR[road];
    const lineCenter = roadPoint(road, STOP_LINE_POS_M, (2 - 1) / 2, 2);
    const x1 = lineCenter.x - perp.x * ROAD_HALF_WIDTH_PX;
    const y1 = lineCenter.y - perp.y * ROAD_HALF_WIDTH_PX;
    const x2 = lineCenter.x + perp.x * ROAD_HALF_WIDTH_PX;
    const y2 = lineCenter.y + perp.y * ROAD_HALF_WIDTH_PX;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  });
}

function drawTrafficLights(ctx, roads) {
  Object.entries(roads).forEach(([roadName, road]) => {
    const pos = roadPoint(roadName, STOP_LINE_POS_M + 22, 0.5, 1);
    const dir = DIRECTION[roadName];
    const perp = PERPENDICULAR[roadName];
    const boxW = 16;
    const boxH = 40;
    ctx.save();
    ctx.translate(pos.x, pos.y);
    if (dir.x !== 0) ctx.rotate(Math.PI / 2);
    ctx.fillStyle = "#0d1117";
    ctx.strokeStyle = "#30363d";
    ctx.lineWidth = 1;
    ctx.fillRect(-boxW / 2, -boxH / 2, boxW, boxH);
    ctx.strokeRect(-boxW / 2, -boxH / 2, boxW, boxH);
    ["red", "yellow", "green"].forEach((phase, i) => {
      const cy = -boxH / 2 + 8 + i * 12;
      ctx.beginPath();
      ctx.arc(0, cy, 4.5, 0, Math.PI * 2);
      ctx.fillStyle = road.light.state === phase ? LIGHT_COLORS[phase] : "#2a2f37";
      ctx.fill();
    });
    ctx.restore();
    void perp;
  });
}

function drawVehicles(ctx, roads) {
  Object.entries(roads).forEach(([roadName, road]) => {
    const dir = DIRECTION[roadName];
    road.lanes.forEach((lane) => {
      lane.vehicles.forEach((vehicle) => {
        const style = VEHICLE_STYLE[vehicle.type] ?? VEHICLE_STYLE.car;
        const pos = roadPoint(roadName, vehicle.position, lane.lane_index, road.lanes.length);
        const lengthPx = style.width * 8;
        const w = dir.x !== 0 ? lengthPx : LANE_WIDTH_PX * 0.4;
        const h = dir.y !== 0 ? lengthPx : LANE_WIDTH_PX * 0.4;
        ctx.fillStyle = style.color;
        ctx.fillRect(pos.x - w / 2, pos.y - h / 2, w, h);
        if (vehicle.emergency) {
          ctx.strokeStyle = "#ffffff";
          ctx.lineWidth = 1;
          ctx.strokeRect(pos.x - w / 2, pos.y - h / 2, w, h);
        }
      });
    });
  });
}

export function drawIntersection(canvas, snapshot) {
  if (!canvas || !snapshot) return;
  const ctx = canvas.getContext("2d");
  drawRoadsAndMarkings(ctx);
  drawTrafficLights(ctx, snapshot.roads);
  drawVehicles(ctx, snapshot.roads);
}
