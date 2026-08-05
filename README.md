# AI-Based Smart Traffic Management & Emergency Vehicle Clearance System

Simulation-only, software-based smart traffic management system. No hardware,
no Arduino, no Raspberry Pi — a custom Python physics simulation of a 4-way
intersection, streamed live to a React dashboard, with pluggable AI decision
logic that replaces fixed-timer signals.

This repository is built **incrementally, milestone by milestone**. Each
milestone is fully working and demoable on its own before the next begins.

## Milestone roadmap

| # | Milestone | Status |
|---|-----------|--------|
| 1 | Foundation — simulation engine, real-time pipeline, fixed-timer baseline | ✅ Done |
| 2 | Virtual camera frames + OpenCV Haar Cascade vehicle detection | Next |
| 3 | Multi-object tracking (ByteTrack), persistent vehicle IDs | Planned |
| 4 | Weighted traffic density estimation per lane | Planned |
| 5 | Adaptive/AI signal controller (replaces fixed-timer) | Planned |
| 6 | Emergency vehicle detection + signal preemption | Planned |
| 7 | Analytics dashboard — historical graphs, congestion levels, reports | Planned |
| 8 | PostgreSQL + SQLAlchemy persistence, report export | Planned |
| 9 | Fixed-timer vs adaptive live comparison, fuel/congestion savings | Planned |
| 10 | Dockerization, hardening, docs, extension hooks (real CCTV/IoT/LSTM) | Planned |

## Milestone 1 — Foundation

### Objective

Prove out the core substrate everything else builds on: a headless traffic
simulation that behaves plausibly (vehicles spawn, accelerate, queue at red
lights, cross on green, despawn) driven by a **fixed-timer** signal
controller, streamed in real time over WebSocket to a React dashboard that
renders the intersection live on canvas.

The fixed-timer controller is not just a placeholder — it's the baseline
Milestone 9 will compare the AI-adaptive controller against, so it needed to
be a real, correct implementation from day one.

### Architectural decisions

- **`SignalControllerBase` strategy interface** (`simulation/controllers/base_controller.py`).
  `FixedTimerController` is the only implementation today; Milestone 5's
  `AdaptiveController` and a future RL controller plug into the exact same
  interface. Nothing in the simulation engine, backend, or frontend needs to
  change when the controller changes — this was the one seam worth building
  early, since the prompt explicitly calls out RL-readiness as a requirement.
- **Simulation state, not simulation pixels, is streamed.** The engine emits
  plain JSON (vehicle positions, speeds, light states) over WebSocket; the
  browser draws it on an HTML5 canvas. This avoids a Pygame/OpenCV render
  step entirely for M1 — that machinery is introduced in Milestone 2, where
  it's actually needed (virtual camera frames for the CV pipeline to detect
  vehicles in).
- **No database yet.** The domain model (vehicle/lane/signal state) will
  change shape as density scoring, tracking, and emergency detection land in
  M2–M6. Persisting it now would mean migrating the schema repeatedly before
  it stabilizes. PostgreSQL is introduced in Milestone 8, once there's a
  stable shape (and an actual need — history/analytics) to persist.
- **`vision/`, `decision_engine/`, `analytics/`, `database/` exist as empty
  stub packages now**, matching the required top-level architecture, but
  contain no logic until their milestone lands.

### Folder structure

```
backend/
  app/
    api/routes.py              REST endpoints (health, state, signal status)
    ws/connection_manager.py   WebSocket client fan-out
    core/config.py             Settings (CORS, tick/broadcast rate)
    simulation_runner.py       Background asyncio loop driving the engine
    main.py                    FastAPI app, lifespan wiring, /ws/simulation
  tests/                       pytest suite (simulation + API)
  requirements.txt

simulation/                    Framework-agnostic simulation engine
  config.py                    Vehicle profiles, road geometry, timings
  entities/
    vehicle.py, lane.py, road.py, traffic_light.py, intersection.py
  controllers/
    base_controller.py         SignalControllerBase strategy interface
    fixed_timer_controller.py  Baseline fixed-duration phase cycling
  engine.py                    SimulationEngine.tick() — ties it together

vision/            (stub — Milestone 2)
decision_engine/   (stub — Milestone 5)
analytics/         (stub — Milestone 7)
database/          (stub — Milestone 8)
shared/
  schemas.py                   Pydantic DTOs for the API/WS boundary

frontend/
  src/
    hooks/useSimulationSocket.js   WebSocket client, auto-reconnect
    components/
      IntersectionCanvas.jsx       Live canvas render of the intersection
      SignalStatusPanel.jsx        Per-road light/queue/vehicle status
      RoadStatsCard.jsx            Connection + sim overview stats
    utils/draw.js                  Canvas drawing (roads, lights, vehicles)
    App.jsx
```

### Technologies used (Milestone 1 scope)

- **Backend:** FastAPI, WebSockets, pydantic-settings, uvicorn
- **Simulation:** pure Python (no external deps) — car-following model,
  Poisson-ish arrivals, weighted random vehicle-type spawning
- **Frontend:** React 18, Vite, Tailwind CSS, HTML5 Canvas (no charting lib
  yet — introduced in Milestone 7 alongside analytics)
- **Testing:** pytest, FastAPI `TestClient` (incl. WebSocket test)

### APIs

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Liveness check |
| GET | `/api/intersection/state` | Latest full simulation snapshot |
| GET | `/api/signals/status` | Condensed per-road signal/queue status |
| WS | `/ws/simulation` | Live snapshot broadcast, ~10Hz |

### Database changes

None. See "No database yet" above.

### UI screens

Single dashboard screen: live intersection canvas (left), simulation
overview stats + per-road signal status panel (right). This is the seed the
Milestone 7 analytics dashboard and Milestone 9 comparison view extend.

### Known simplification (documented, not a bug)

The dashboard's WebSocket URL defaults to `127.0.0.1` rather than
`localhost`. On Windows, `localhost` can resolve to the IPv6 loopback
(`::1`) while uvicorn only binds the IPv4 loopback by default — the
WebSocket handshake then dies silently with no server-side error. Override
via `VITE_WS_URL` in `frontend/.env` if you bind uvicorn elsewhere.

---

## Running it

### Backend

```bash
cd smart-traffic-management-milestone1
python -m venv .venv
source .venv/Scripts/activate        # Windows Git Bash; use .venv\Scripts\Activate.ps1 in PowerShell
pip install -r backend/requirements.txt

# Run from the repo root so both `simulation`/`shared` (root) and `app` (backend/) are importable
PYTHONPATH="$(pwd):$(pwd)/backend" uvicorn app.main:app --reload --app-dir backend --port 8000
```

Backend is live at `http://127.0.0.1:8000` (docs at `/docs`).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard is live at `http://localhost:5173`.

### Testing strategy

```bash
cd backend
python -m pytest -q
```

- `tests/test_simulation.py` — pure simulation engine: vehicles spawn and
  move, stop at red, never grant conflicting NS/EW greens, every road
  eventually gets green (no starvation even in the fixed-timer baseline).
- `tests/test_api.py` — FastAPI `TestClient`: health check, WebSocket
  delivers a valid snapshot, REST state endpoint reflects it.

All 9 tests pass. Frontend was verified visually with a live backend +
Playwright screenshot: canvas renders lane markings, stop lines, per-road
traffic light boxes, vehicles colored/sized by type, and the status panel
correctly reflects live queue lengths, vehicle counts, and emergency-vehicle
flags from the WebSocket stream.

---

## Future extension points (no architectural changes required)

- Real CCTV feeds slot into `vision/` in place of virtual camera frames
- `decision_engine/` gains an `AdaptiveController` and later an
  `RLController`, both implementing `SignalControllerBase`
- `database/` adds SQLAlchemy models once the domain model stabilizes
  (Milestone 8)
- Docker Compose (backend + frontend + Postgres) lands in Milestone 10
