# AI-Based Smart Traffic Management & Emergency Vehicle Clearance System

Simulation-first, software-based smart traffic management system — a custom
Python physics simulation of a 4-way intersection, streamed live to a React
dashboard, with pluggable AI decision logic that replaces fixed-timer
signals. Everything runs without hardware; the optional Milestone 10
hardware bridge (`hardware/`, Raspberry Pi or ESP32) lets real signal lights
mirror the controller, but has not yet been built and tested on a physical
board.

This repository is built **incrementally, milestone by milestone**. Each
milestone is fully working and demoable on its own before the next begins.

## Milestone roadmap

| # | Milestone | Status |
|---|-----------|--------|
| 1 | Foundation — simulation engine, real-time pipeline, fixed-timer baseline | ✅ Done |
| 2 | Virtual camera frames + OpenCV Haar Cascade vehicle detection | ✅ Done |
| 3 | Multi-object tracking (ByteTrack), persistent vehicle IDs | ✅ Done |
| 4 | Weighted traffic density estimation per lane | ✅ Done |
| 5 | Adaptive/AI signal controller (replaces fixed-timer) | ✅ Done |
| 6 | Emergency vehicle detection + signal preemption | ✅ Done |
| 7 | Analytics dashboard — historical graphs, congestion levels, reports | ✅ Done |
| 8 | SQLAlchemy persistence (SQLite by default, Postgres-ready), report export | ✅ Done |
| 9 | Fixed-timer vs adaptive live comparison, fuel/congestion savings | ✅ Done |
| 10 | Dockerization, hardening, hardware bridge, CI | ✅ Done |

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

## Milestone 2 — Virtual camera + Haar Cascade detection

### Objective

Give each road a "camera": render its approach to the stop line as an
actual image frame (not simulation JSON), run OpenCV's Haar Cascade
classifier on it to localize vehicles, and surface bounding boxes +
confidence on the dashboard — exactly the abstract's stated pipeline
(`Capture → Detect & Count`), still with zero hardware.

### Architectural decisions

- **The camera's contract is a road-state dict → an image.** `vision/camera.py`
  takes the same per-road dict the simulation already emits and renders a
  synthetic BGR frame. `vision/detector.py` takes a frame → detections and
  knows nothing about the simulation at all. Swapping in a real CCTV feed
  later means replacing `render_road_frame()`'s output with a real frame
  grab — the detector, pipeline, and dashboard are unaffected.
- **Honesty layer, not a cheat.** A single generic Haar cascade (`cars.xml`)
  is a *binary* vehicle/non-vehicle detector — it does not classify vehicle
  type, and its confidence is a cascade decision margin, not a calibrated
  probability. `vision/pipeline.py` matches each raw detection back to the
  nearest ground-truth simulated vehicle *only* to label it with a type for
  display and to compute real precision/recall — those numbers are never
  fed back into what the detector actually returned, and they're shown
  as-is on the dashboard (often well under 50% recall) rather than
  papered over. This is a genuine, documented limitation of classical Haar
  cascades applied to synthetic top-down imagery, not a simulation-specific
  bug — see the code comments in `vision/detector.py` for the full
  reasoning, and it's exactly the kind of finding worth calling out in a
  project defense rather than hiding.
- **Separate WebSocket channel (`/ws/vision`) at a separate (lower) rate.**
  Camera frames are JPEG payloads, much heavier than the `/ws/simulation`
  JSON state, and rendering + Haar detection is CPU-bound. Broadcasting
  vision at 2Hz on its own channel — computed on a dedicated worker thread
  via `loop.run_in_executor` — keeps it from ever stalling the 20Hz
  simulation tick loop.
- **Bounding boxes are burned into the JPEG server-side**, not sent as
  separate coordinates for the frontend to overlay. Simpler, and avoids a
  class of coordinate-scaling bugs between the render resolution and
  whatever size the `<img>` ends up displayed at.

### Folder structure (additions)

```
vision/
  config.py       Camera + cascade tuning constants
  camera.py       render_road_frame(), ground_truth_boxes(), encode_jpeg()
  detector.py     HaarVehicleDetector — loads cars.xml, detectMultiScale3
  pipeline.py     analyze_road() — render + detect + ground-truth matching
                  + annotated-frame drawing, all tied together
  models/
    cars.xml      Public-domain Haar cascade (andrewssobral/vehicle_detection_haarcascades)

backend/app/
  vision_runner.py   Background loop: render+detect per road at 2Hz,
                      off the event loop via a worker thread

frontend/src/
  hooks/useVisionSocket.js       WebSocket client for /ws/vision
  components/CameraFeedGrid.jsx  2x2 live camera panel grid
```

### Technologies used (Milestone 2 additions)

- **opencv-python-headless** — frame synthesis (`cv2.rectangle`/`putText`)
  and `cv2.CascadeClassifier` for detection
- **numpy** — frame buffers

### APIs (additions)

| Method | Path | Description |
|---|---|---|
| GET | `/api/vision/latest` | Latest per-road detection snapshot |
| WS | `/ws/vision` | Live camera frames + detections, 2Hz |

### Database changes

None — same reasoning as Milestone 1.

### UI screens (additions)

"Live CCTV Feeds" panel below the intersection canvas: a 2x2 grid, one
tile per road, each showing the live annotated JPEG (green box = detection
matched to a real vehicle, orange = unmatched/false positive, thin gray
outline = ground truth) plus a `detected/ground-truth` count and
`precision`/`recall` readout.

### Testing strategy (additions)

```bash
cd backend
python -m pytest -q
```

- `tests/test_vision.py` — frame shape/dtype, seeded-render determinism,
  ground-truth boxes correctly exclude out-of-view vehicles, detector loads
  the cascade and returns well-formed `Detection`s, `analyze_road()` output
  shape and valid JPEG bytes, empty-road edge case.
- `tests/test_api.py` — `/ws/vision` delivers a snapshot for all 4 roads,
  `/api/vision/latest` reflects it after connecting.

All 19 tests pass (9 from Milestone 1 + 10 new). Frontend verified visually
with a live backend + Playwright screenshot: all 4 camera tiles render live
JPEG frames with detection overlays, confidence labels, and non-trivial
(non-placeholder) precision/recall numbers pulled from the real detector
output.

### Post-Milestone-2 fix: WebSocket broadcast concurrency bug

`ConnectionManager.broadcast_json` iterated the live set of connected
clients while `await`-ing each send. A client connecting or disconnecting
mid-broadcast mutated that set during iteration, raising `RuntimeError: Set
changed size during iteration` — which the simulation/vision loops caught
and **re-raised**, permanently killing the background task. The dashboard
would freeze (the server stayed responsive, so `/api/health` still
returned 200 — only the simulation clock stopped advancing) until a manual
restart. Fixed by iterating a snapshot copy of the connection set, and by
making both loops log-and-continue on a transient error instead of dying.
Verified by hammering the server with 120 rapid connect/disconnect cycles
and confirming `sim_time` kept advancing throughout. See
`backend/tests/test_connection_manager.py`.

---

## Milestone 3 — Multi-object tracking (ByteTrack)

### Objective

Milestone 2's detector re-detects vehicles from scratch every broadcast
tick with no memory of previous frames — every detection is anonymous.
Milestone 3 gives every vehicle a **persistent ID** across frames, so the
dashboard can show stable identities and a genuine cumulative "vehicles
counted" figure instead of re-summing per-frame noise (the roadmap's
"prevent duplicate counting" requirement).

### Architectural decisions

- **Implemented from scratch, not pulled in as a dependency**, consistent
  with how the detector itself was built. `vision/tracker.py` implements
  ByteTrack's core idea: a constant-velocity **Kalman filter** predicts
  where each track should be before matching, and association happens in
  **two stages** — high-confidence detections against all tracks first,
  then low-confidence detections against whatever tracks are still
  unmatched (ByteTrack's key insight: a weak detection is still evidence a
  known vehicle is there, so don't discard it outright — but a weak
  detection is never allowed to *spawn* a brand-new track, only sustain an
  existing one). Matching uses IoU cost with the Hungarian algorithm
  (`scipy.optimize.linear_sum_assignment`).
- **Thresholds adapted from the reference values, not reused blindly.**
  Real ByteTrack tunes its high/low confidence split against a detector
  whose output is roughly calibrated to [0, 1] with real detections well
  above 0.5. Our Haar Cascade's confidence (a raw cascade-stage decision
  margin, not a probability — see Milestone 2) sits mostly in 0.0–0.5, so
  `TRACK_HIGH_CONF_THRESHOLD` in `vision/config.py` is set to 0.15, not
  ByteTrack's typical ~0.6.
- **The tracker only tracks geometry — it has no concept of "real" vs
  "false positive."** It never touches ground truth. `vision/pipeline.py`
  looks up each visible track's `track_id` by exact bbox match (a track's
  `bbox` is always set to exactly the `(x, y, w, h)` of whatever detection
  matched it) and attaches it to that detection, entirely independent of
  the ground-truth type-matching already happening there.
- **A real bug, found and fixed while building this milestone:**
  `vision/camera.py`'s background noise (added in M2 for visual "sensor
  flicker") was reseeded with a *different* random pattern every
  broadcast tick. That's harmless for M2 (a fresh per-tick image is all a
  stateless detector needs), but it meant the whole frame — including the
  texture immediately around real vehicles — was completely uncorrelated
  frame to frame. Verified directly: with a fixed seed, detections landed
  at the exact same pixel position every tick; with a per-tick-varying
  seed, even a *stationary* vehicle's detection box jumped to an
  unrelated position every time. No detection could ever survive two
  consecutive ticks, so no track could ever be confirmed — `active_tracks`
  measured 0 for 20+ seconds of live traffic while `unique_vehicles_tracked`
  climbed steadily in the background. Fixed in `vision_runner.py`: the
  per-road seed is now stable over time (varies by road name only, not by
  tick), matching how a real camera's background actually behaves — only
  genuinely moving objects should change position between frames.
- **Honest finding, not tuned away:** even after that fix, most confirmed
  tracks in a live run are of *static background* false positives rather
  than real vehicles — because a static false positive is, by definition,
  perfectly stable frame to frame (trivial for the tracker to confirm),
  while a real, moving vehicle must be genuinely re-detected by the
  already-weak Haar Cascade on two consecutive ticks to earn a confirmed
  ID, compounding Milestone 2's low per-frame recall. Real vehicles do get
  confirmed — verified directly over a 36-second live window (2 genuine
  vehicle tracks confirmed, `matched: true`) — just less often than
  background artifacts. `TRACK_MIN_HITS` was deliberately left at 2 rather
  than weakened to 1 to manufacture a better-looking demo; that would
  remove the one mechanism that filters single-frame noise out of the
  displayed track list at all. This is the same honesty policy as
  Milestone 2's precision/recall numbers: report what the pipeline
  actually does, not what would look best.

### Folder structure (additions)

```
vision/
  tracker.py    KalmanBoxTracker, Track, ByteTracker

backend/app/
  vision_runner.py   now owns one persistent ByteTracker per road and
                      computes real wall-clock dt between ticks
```

### Technologies used (Milestone 3 additions)

- **scipy** — `linear_sum_assignment` (Hungarian algorithm) for detection-to-track matching

### APIs (additions)

No new endpoints — `RoadVisionFrame` (served by the existing
`/ws/vision` and `/api/vision/latest`) gains fields:

| Field | Meaning |
|---|---|
| `detections[].track_id` | Persistent id, `null` until a track is confirmed |
| `active_tracks` | Confirmed tracks visible this tick |
| `unique_vehicles_tracked` | Cumulative distinct tracks since the server started |

### Database changes

None — same reasoning as Milestones 1–2.

### UI screens (additions)

Camera tiles now draw a cyan `#<id>` label under any detection with a
confirmed track, and each tile's footer gains an `active tracks` /
`total counted` row.

### Testing strategy (additions)

```bash
cd backend
python -m pytest -q
```

- `tests/test_tracker.py` — ID persistence across frames, distinct IDs for
  separate vehicles, track removal after `max_age`, a reappearing vehicle
  gets a *new* id rather than reusing an old one, low-confidence detections
  can sustain but never spawn a track, cumulative count reflects unique
  vehicles not frames, and a direct Kalman-filter convergence check.
- `tests/test_vision.py` — updated for the new `analyze_road()` signature;
  asserts every detection carries a `track_id` field and the new count
  fields are present and sane.

All 29 tests pass (19 from Milestones 1–2 + 10 new). Diagnosed and fixed
the background-reseeding bug above using isolated scripts before touching
the test suite, then verified live: `active_tracks` went from measuring 0
for 20+ seconds straight (pre-fix) to correctly confirming and holding
stable track IDs across ticks (post-fix), confirmed visually in-browser via
Playwright screenshot — cyan `#id` labels and live active/total counts on
every camera tile.

---

## Milestone 4 — Weighted traffic density estimation

### Objective

Milestones 1–3 expose queue length and vehicle count, but treat every
vehicle as equal weight and every queued/moving vehicle as equal urgency.
Milestone 4 produces a real per-lane/per-road **density score** — the signal
the Milestone 5 adaptive controller decides green-light duration from.

### Architectural decisions

- **Lives in `decision_engine/`, not `simulation/`.** The weighting
  (`DENSITY_WEIGHTS` per vehicle type, queued/moving multipliers) is a
  decision-engine concern — tunable independently of vehicle physics — not a
  simulation fact. Adding it to `VehicleProfile` would leak decision-making
  into the framework-agnostic simulation core, which must stay usable
  without any notion of "what a controller should do with this."
- **Queued vehicles weigh 3x moving vehicles** (`QUEUED_MULTIPLIER=1.5` vs
  `MOVING_MULTIPLIER=0.5`). A vehicle stopped at the line is exactly the
  "needs green" pressure this score exists to capture; a vehicle still
  approaching at speed will often clear on its own.
- **Ambulances/fire trucks get the highest per-vehicle weight (6.0)** even
  though Milestone 6 will add hard preemption on top — this gives the
  Milestone 5 adaptive controller a mild natural bias toward emergency-
  carrying lanes even in the window before/after a hard preemption event.
- **Purely instantaneous — no wait-time accumulator added here.** No
  per-vehicle timer exists yet in `simulation/entities/vehicle.py`. Real
  cumulative wait-time tracking is deliberately deferred to Milestone 7, so
  it can be built once, correctly (measuring actual time spent queued, not
  `sim_time - spawn_time`, which would dishonestly count free-flow transit
  as "waiting") rather than bolted on early and reworked later.
- **Computed in `backend/app/simulation_runner.py`, not in
  `simulation/engine.py::to_state()`.** Enriching inside the engine would
  require `simulation/` to import `decision_engine/`, breaking the
  project's layering rule (only `backend/app/`, the composition root, is
  allowed to import both). `SimulationRunner` is the first place a
  decision-engine module gets wired in.

### Folder structure (additions)

```
decision_engine/
  density.py    DENSITY_WEIGHTS, QUEUED_MULTIPLIER, MOVING_MULTIPLIER,
                vehicle_density_weight(), lane_density_score(),
                road_density_score(), compute_intersection_density()
```

### APIs (additions)

No new endpoints — `RoadState`/`LaneState` (served by the existing
`/ws/simulation`, `/api/intersection/state`, `/api/signals/status`) gain a
`density_score: float` field.

### Database changes

None.

### UI screens (additions)

`SignalStatusPanel` gains a `Density: N.N` readout per road, alongside the
existing queue/vehicle counts. No color/tier classification yet — that's
Milestone 7's "congestion level" scope.

### Testing strategy (additions)

```bash
cd backend
python -m pytest -q
```

- `tests/test_density.py` — empty lane scores 0; a queued vehicle scores
  exactly `weight * QUEUED_MULTIPLIER` vs a moving vehicle's
  `weight * MOVING_MULTIPLIER`; one ambulance outweighs five queued cars;
  road score equals the sum of its lanes' scores.
- `tests/test_api.py` — `/api/intersection/state` carries a non-negative
  `density_score` on every road and lane.

All 33 tests pass (29 from Milestones 1–3 + 4 new). Verified live: polled
`/api/intersection/state` twice 15 seconds apart and confirmed density
scores move with real traffic (e.g. a road's score dropping as its queue
cleared through a green phase), and confirmed `SignalStatusPanel.jsx`
compiles cleanly through the Vite dev server.

---

## Milestone 5 — Adaptive/AI signal controller

### Objective

Replace the fixed 20s/3s/1s cadence with green-light duration that responds
to Milestone 4's density scores, while never weakening the yellow/all-red
safety phases the fixed-timer baseline already gets right.

### Architectural decisions

- **Priority + bounded green extension, not max-density-first or weighted
  round-robin.** `AdaptiveController` keeps `FixedTimerController`'s exact
  phase skeleton and tables (imports `Phase`, `_NEXT_PHASE`,
  `_LIGHT_BY_PHASE`, `NS_GROUP`/`EW_GROUP` rather than redefining them) and
  only changes *how long a green phase lasts*: it extends past
  `MIN_GREEN_S` (8s) while the active direction's density score exceeds the
  waiting direction's by `EXTENSION_THRESHOLD` (1.1x), capped at
  `MAX_GREEN_S` (45s). This was chosen over pure max-density-first (risks
  starving the low-traffic direction) and weighted round-robin (reacts
  slowly to a road that was empty a moment ago) because it's the easiest to
  reason about against a hard safety invariant.
- **Yellow and all-red clearance durations are never touched** — they're
  read from the exact same `simulation/config.py` constants
  (`YELLOW_DURATION_S`, `ALL_RED_CLEARANCE_S`) the fixed-timer controller
  uses. Only green duration is adaptive; everything that makes phase
  transitions safe is identical to Milestone 1's baseline.
- **`SignalControllerBase.resync()` — a new concrete (non-abstract) hook**,
  added to the base class rather than bolted onto `AdaptiveController`
  alone: re-asserts the current phase's lights without advancing internal
  timers. Not used by anything yet, but Milestone 6's emergency-preemption
  wrapper needs a way to hand control back to whichever controller it's
  wrapping without a stale-phase light glitch — designing the seam now,
  while it's cheap, beats retrofitting it under M6 pressure.
- **Controller selection via `STMS_CONTROLLER_TYPE` env var** (`fixed`
  default, `adaptive` opt-in), resolved by a new
  `backend/app/core/controller_factory.py::build_controller()` — the one
  module allowed to import both `simulation.controllers` and
  `decision_engine`, since it's composition-root code, not simulation or
  decision-engine code itself.

### Folder structure (additions)

```
decision_engine/
  adaptive_controller.py   AdaptiveController(SignalControllerBase)

backend/app/core/
  controller_factory.py    build_controller(controller_type)
```

### APIs (additions)

No new endpoints — `/api/signals/status` and `/ws/simulation` now report
`"controller": "AdaptiveController"` when `STMS_CONTROLLER_TYPE=adaptive` is set.

### Database changes

None.

### UI screens (additions)

None — `RoadStatsCard`/`SignalStatusPanel` already surface `controller` and
`active_phase`; they now reflect whichever controller is configured with no
frontend changes needed, exactly the point of the `SignalControllerBase` seam.

### Testing strategy (additions)

```bash
cd backend
python -m pytest -q
```

- `tests/test_adaptive_controller.py` — never grants conflicting NS/EW
  greens over 4000 ticks; green duration always falls within
  `[min_green_s, max_green_s]`; a lopsidedly-loaded direction extends its
  green well past `min_green_s` (the test that proves it's actually
  adaptive, not just safe).

All 36 tests pass (33 from Milestones 1–4 + 3 new). Verified live: ran the
backend with `STMS_CONTROLLER_TYPE=adaptive` and polled `/api/signals/status`
every 0.5s for 90 seconds — confirmed zero ticks with simultaneous NS+EW
green, the exact expected phase sequence
(NS_GREEN→NS_YELLOW→ALL_RED_A→EW_GREEN→EW_YELLOW→ALL_RED_B), yellow/all-red
durations matching the fixed constants (~3s/~1s), and green phases
consistently running 9–9.7s — above the 8s minimum, extended by real
(modest, not dramatic) traffic density on the active side each cycle.

---

## Milestone 6 — Emergency vehicle detection + signal preemption

### Objective

An ambulance/fire truck approaching on a red road should force/extend its
green, safely — without ever skipping the yellow/all-red clearance that
keeps every other transition safe.

### Architectural decisions

- **Control decisions use simulation ground truth
  (`Road.has_emergency_vehicle()`) exclusively — never the vision
  pipeline's detection.** Feeding the CV `is_emergency` signal into control
  would make signal safety depend on the Haar cascade's own documented poor
  recall (Milestones 2–3 found most confirmed tracks are static-background
  false positives, not real vehicles). That would be actively dangerous.
  The vision-side flag stays **display-only** — an honest "would the camera
  have caught this" indicator, deliberately separate from what drives the
  lights.
- **Implemented as a decorator (`EmergencyPreemptionController`) wrapping
  any `SignalControllerBase`**, not a subclass of either existing
  controller — this is what lets preemption work identically under both
  fixed-timer and adaptive control, which also matters for Milestone 9
  (both sides of that comparison get preemption, isolating the
  fixed-vs-adaptive variable rather than conflating it with "only one side
  preempts").
- **State machine** (`NORMAL → FORCE_YELLOW → CLEARING → PREEMPT_GREEN →
  RELEASE_YELLOW → RELEASE_CLEARING → NORMAL`; the two release states were
  added later, see "Emergency override change-interval fix" below)
  specifically so a currently-green road is never flipped
  straight to red — it gets its normal yellow first, exactly like any other
  transition. If the target road happens to already be green with nothing
  else green, `FORCE_YELLOW`/`CLEARING` are skipped (already safe).
- **`MAX_HOLD_S` (20s) cap** on `PREEMPT_GREEN`, so an edge case (the
  ambulance despawning without crossing the stop line, or a second one
  queuing right behind it) can't freeze the intersection in one direction
  forever. A second emergency on a different road mid-preemption is not
  acted on until the current one completes and control returns to
  `NORMAL` — no interrupting one preemption with another.
- **`controller.describe()`**, a new concrete method on
  `SignalControllerBase` (default `type(self).__name__`), added because
  wrapping every controller in `EmergencyPreemptionController` would
  otherwise collapse the dashboard's `controller` field to always read
  `"EmergencyPreemptionController"`, hiding which inner strategy (fixed vs.
  adaptive) is actually active — it now reports e.g.
  `"EmergencyPreemptionController(FixedTimerController)"`.

### Folder structure (additions)

```
decision_engine/
  emergency_preemption.py   EmergencyPreemptionController(SignalControllerBase)
```

### APIs (additions)

No new endpoints — `VehicleDetection` (in `/ws/vision`, `/api/vision/latest`)
gains `is_emergency: bool`; `RoadVisionFrame` gains
`vision_emergency_detected: bool`. `/api/signals/status`'s `controller`
field now reports the composed name described above.

### Database changes

None.

### UI screens (additions)

`CameraFeedGrid` shows an amber "CAMERA: EMERGENCY?" badge per road tile
when `vision_emergency_detected` is true — visually distinct from, and
explicitly documented as separate from, `SignalStatusPanel`'s existing red
"EMERGENCY" badge (which reflects ground truth and is what actually drives
preemption).

### Testing strategy (additions)

```bash
cd backend
python -m pytest -q
```

- `tests/test_emergency_preemption.py` — an ambulance on a red road forces
  that road green within `clearance_s + yellow_s`; no conflicting NS/EW
  green ever occurs throughout a preemption event; ending a preemption
  hands control back to the wrapped controller with lights matching its
  expected phase exactly (`resync()` in action); `MAX_HOLD_S` bounds every
  individual green hold even when the emergency flag never clears.
- `tests/test_vision.py` — `is_emergency` is `True` only for
  ambulance/fire_truck ground-truth matches (both via a full `analyze_road`
  run and a deterministic synthetic-detection test that doesn't depend on
  the Haar cascade actually firing).

All 41 tests pass (36 from Milestones 1–5 + 5 new). Verified live: polled
`/api/signals/status` for 100 seconds with the default (fixed +
preemption-wrapped) controller — zero conflicting greens throughout, and
`controller` correctly reported as
`"EmergencyPreemptionController(FixedTimerController)"`. No ambulance
happened to spawn in that live window (`spawn_weight=0.5`, a genuinely rare
event) — reported honestly rather than forced; the deterministic unit tests
above are what actually prove the preemption logic itself is correct.

---

## Milestone 7 — Analytics dashboard

### Objective

Turn the instantaneous snapshots Milestones 1–6 already stream into real
historical metrics: per-road wait time, throughput, and a congestion-level
classification over time — not just "what's happening right now."

### Architectural decisions

- **Real wait-time tracking, added here as planned back in Milestone 4.**
  `Vehicle` gains `queued_time_s`, accumulated in `Lane._update_vehicle`
  only while the vehicle is genuinely stopped/queued (reusing the exact
  `Lane._is_queued` predicate `density.py` also uses) — deliberately not
  `sim_time - spawn_time`, which would dishonestly count free-flow transit
  as "waiting." `Lane`/`Road` gain `total_exited`/`total_wait_time_s`
  cumulative counters, incremented once per vehicle at the moment it exits.
- **`analytics/collector.py` is runner-agnostic** — it only ever reads
  `simulation_runner.latest_state`, never imports `SimulationRunner`
  itself. This is deliberate: Milestone 9 reuses this exact class,
  unmodified, against a second (shadow) `SimulationRunner` for the
  fixed-vs-adaptive comparison.
- **Never fabricates an average from zero departures.** Each 1Hz sample
  computes `throughput_delta` (vehicles exited since the last sample) and
  divides the wait-time delta by it only when `throughput_delta > 0`;
  otherwise `avg_wait_time_s` is `None` for that window, not `0` or a
  stale carry-forward value.
- **Congestion level is a heuristic threshold against Milestone 4's density
  score**, in `analytics/config.py`, explicitly documented as eyeballed
  from live runs rather than backfit — the same honesty policy as the
  vision pipeline's precision/recall numbers.
- **Frontend accumulates its own rolling history client-side** from the
  single-latest-sample-per-road `/ws/analytics` snapshots (deduped on
  `sim_time`), rather than polling `/api/analytics/history` on a timer —
  one fewer moving part, consistent with how `useSimulationSocket`/
  `useVisionSocket` already work. `recharts` was added as the one new
  frontend dependency — a thin wrapper over D3 primitives, not a full
  charting platform, consistent with the project's existing aversion to
  heavy frameworks.

### Folder structure (additions)

```
analytics/
  config.py       CONGESTION_LOW_MAX, CONGESTION_HIGH_MIN
  collector.py    AnalyticsCollector — samples, classifies, broadcasts

frontend/src/
  hooks/useAnalyticsSocket.js       WebSocket client for /ws/analytics
  components/AnalyticsDashboard.jsx  per-road density history + congestion badges
```

### APIs (additions)

| Method | Path | Description |
|---|---|---|
| GET | `/api/analytics/history/{road}` | Rolling sample history for one road |
| GET | `/api/analytics/summary` | Cumulative totals + avg wait per road and overall |
| WS | `/ws/analytics` | Latest per-road sample, broadcast at 1Hz |

`RoadState` (simulation schema) gains `total_exited: int` and
`total_wait_time_s: float`.

### Database changes

None yet — history lives in an in-memory rolling buffer
(`collections.deque`, capped at `history_len`). Milestone 8 adds real
persistence on top of this same data.

### UI screens (additions)

New "Analytics — Density History & Congestion" panel: a 2×2 grid of
per-road density-over-time line charts (recharts), each with a live
low/medium/high congestion badge, plus an overall avg-wait-time/total-exited
readout polled from `/api/analytics/summary`.

### Testing strategy (additions)

```bash
cd backend
python -m pytest -q
```

- `tests/test_simulation.py` — a vehicle crossing the full road length
  increments `total_exited`; queued time only accrues while genuinely
  stopped at a red light, not during free-flow travel.
- `tests/test_analytics.py` — congestion threshold classification; a
  collector correctly computes throughput/avg-wait deltas between two
  samples; zero departures never divides by zero; history respects its
  `maxlen`; summary is sane (`None`, not a fabricated number) at zero
  throughput.

All 48 tests pass (41 from Milestones 1–6 + 7 new). Verified live: ran the
backend and frontend together for several minutes, confirmed
`/api/analytics/history/{road}` accumulating real samples with
`congestion_level` correctly tracking each road's live density crossing the
low/medium/high thresholds, confirmed `/ws/analytics` broadcasting a real
per-road snapshot, and confirmed `/api/analytics/summary` eventually showing
genuine non-zero throughput and per-road average wait times that differ
meaningfully by road (e.g. one road at ~11.5s average wait vs. another at
under 1s) — not placeholder numbers. Frontend files confirmed compiling
cleanly through the Vite dev server.

---

## Milestone 8 — Persistence (SQLite by default) + report export

### Objective

Make the history Milestone 7 computes survive a restart, and let it be
exported as a report — the roadmap's originally-scoped "PostgreSQL", built
against SQLite instead, by explicit decision (see below).

### Architectural decisions

- **SQLite (`aiosqlite`), not PostgreSQL, by user decision.** The user
  doesn't have Docker or a local Postgres install; `database/session.py`'s
  `Database` class takes a plain `DATABASE_URL` string
  (`sqlite+aiosqlite:///./traffic.db` by default), so pointing it at
  `postgresql+asyncpg://...` later is a one-line config change, not a
  rewrite — the SQLAlchemy model/session code is identical either way.
- **`Base.metadata.create_all()` at startup, not Alembic** — by explicit
  user decision. Reasonable at this project's scale (a solo/portfolio
  project, not a production service with existing data to preserve across
  deploys); revisit if the schema needs to evolve without data loss later.
- **Two-table snapshot split** (`snapshots` + `road_snapshots`), not one
  wide table repeating each of the 4 roads' columns — avoids denormalized
  repetition and matches the per-road query shape `analytics/collector.py`
  already uses.
- **`Database` is a plain class taking `database_url` in its constructor**,
  matching the project's existing dependency-injection style
  (`ConnectionManager`, `SimulationRunner`, `VisionRunner`,
  `AnalyticsCollector` are all constructed the same way and stored on
  `app.state`) — deliberately not a module-level singleton, so tests can
  construct an isolated in-memory instance without touching the real
  `traffic.db` file the dev server writes to.
- **Two different write cadences, matching how urgent each kind of data
  is.** Periodic snapshots piggyback on `analytics/collector.py`'s existing
  1Hz sampling loop via a generic `on_sample` async callback (persisting
  every 10th sample, ~1 row/10s) — `analytics/` never has to import
  `database/` directly, keeping the layering rule intact. Signal events
  (emergency preemption start/end) are written immediately, event-driven,
  via `EmergencyPreemptionController`'s new `on_event` callback — a rare,
  timing-sensitive event shouldn't wait for the next periodic sample.
- **`backend/app/event_recorder.py` bridges a synchronous callback to an
  async DB write.** `EmergencyPreemptionController.update()` is called
  synchronously from inside `SimulationEngine.tick()`, itself called
  synchronously from `SimulationRunner`'s async loop — so `EventRecorder.record()`
  schedules the DB write with `asyncio.create_task()` rather than awaiting
  inline, so the physics tick itself never blocks on a database write.
- **The controller tracks its own `sim_time_s` by summing `dt`**, rather
  than being given the engine's `sim_time_s` directly — `update(intersection,
  dt)`'s signature is fixed by `SignalControllerBase` and every controller
  is ticked with the same `dt` every time the engine ticks, so the sum is
  numerically identical to the engine's own clock without adding a new
  argument to the interface.

### Folder structure (additions)

```
database/
  models.py    SimulationRun, Snapshot, RoadSnapshot, SignalEvent
  session.py   Database — engine + async session factory + init()/dispose()
  writer.py    create_run(), end_run(), persist_sample(), persist_event(),
               fetch_road_snapshot_rows(), fetch_signal_events()

backend/app/
  event_recorder.py   EventRecorder — sync-callback-to-async-task bridge
```

### APIs (additions)

| Method | Path | Description |
|---|---|---|
| GET | `/api/reports/export?format=json\|csv` | Road-snapshot + signal-event history for a run (current run by default) |

### Database changes

New tables: `simulation_runs`, `snapshots`, `road_snapshots`, `signal_events`
— see `database/models.py`. Created automatically on startup via
`create_all()`; the file lives at `./traffic.db` relative to wherever
uvicorn is started (repo root, per the "Running it" instructions below).

### UI screens (additions)

None — persistence and export are backend-only in this milestone.

### Testing strategy (additions)

```bash
cd backend
python -m pytest -q
```

- `tests/test_database.py` — `create_run`/`persist_sample`/
  `fetch_road_snapshot_rows` round-trip against an isolated in-memory
  SQLite instance; `persist_event`/`fetch_signal_events` round-trip;
  `end_run` sets `ended_at`; `/api/reports/export` returns well-formed JSON
  and CSV (correct headers) via the full FastAPI app.
- `backend/tests/conftest.py` now sets `STMS_DATABASE_URL` to an in-memory
  SQLite DB before any test imports the app, so running the test suite
  never touches or creates the real `traffic.db` file.

All 52 tests pass (48 from Milestones 1–7 + 4 new). Verified live: started
the backend fresh (confirmed `traffic.db` created on startup), polled the
SQLite file directly every ~11s and confirmed `snapshots`/`road_snapshots`
row counts increasing at exactly the expected ~1-per-10s cadence. An
ambulance genuinely spawned during this run and triggered a real emergency
preemption (Milestone 6) — `/api/reports/export` shows both
`EMERGENCY_PREEMPTION_START` and `EMERGENCY_PREEMPTION_END` events recorded
with real `sim_time` values (2.95s and 21.8s), proving the full chain end to
end: simulation → controller state transition → event callback → scheduled
async DB write → queryable report, all without a single fabricated number.

---

## Milestone 9 — Fixed vs. adaptive live comparison

### Objective

Run the fixed-timer and adaptive controllers side by side against identical
traffic and measure a real (not fabricated) difference in wait time and
throughput — the roadmap's "fuel/congestion savings" comparison.

### Architectural decisions

- **Prerequisite fix, landed first: seeded RNG.** Before this milestone,
  `Road._spawn_vehicle` and `Intersection._maybe_reshuffle_demand` both drew
  from the *global* `random` module. Two engines ticking concurrently on the
  same event loop would draw from that one shared stream in
  scheduling-dependent order — non-reproducible, and would silently
  confound "controller effect" with "got luckier traffic," undermining the
  entire point of a comparison. Fixed by giving `Intersection` (and every
  `Road` it constructs) a shared `random.Random(seed)` instance instead,
  threaded through `SimulationEngine(seed=...)`. `seed=None` (still the
  default for anything that doesn't ask for one) reproduces the exact
  pre-Milestone-9 unseeded behavior — fully backward compatible.
- **One shadow runner, not two symmetric named runners — by user decision.**
  The existing `app.state.simulation_runner` (whatever
  `STMS_CONTROLLER_TYPE` selects) is completely untouched. Exactly one new
  `app.state.shadow_runner` is added, running the *other* controller type
  against the same `STMS_COMPARISON_SEED` (default `42`) — so both sides
  see an identical vehicle-arrival sequence and the controller is the only
  variable. **Side effect worth knowing:** giving the primary runner a
  fixed default seed means the main dashboard's traffic pattern is now the
  same on every server restart (previously random) — a deliberate,
  documented trade-off for making the comparison (and any demo of it)
  reproducible.
- **`analytics/collector.py` is reused completely unmodified** against the
  shadow runner (`AnalyticsCollector(shadow_runner)`, no manager or DB
  hook needed) — this is exactly the payoff of Milestone 7's decision to
  keep that class runner-agnostic.
- **`backend/app/comparison.py::build_comparison_snapshot()` is a pure
  function** taking two collectors' `.summary()` output — easy to unit-test
  without any FastAPI/asyncio machinery, and it never fabricates a
  wait-time delta when either side has zero throughput (`None`, not `0`).
- **`useSimulationSocket` is parameterized to accept a URL** rather than
  writing a near-duplicate hook — `ComparisonView` calls it twice, once for
  `/ws/simulation` and once for the new `/ws/simulation/shadow`, reusing
  `IntersectionCanvas` unmodified for both sides.

### Folder structure (additions)

```
backend/app/
  comparison.py   build_comparison_snapshot(primary, shadow, ...)

frontend/src/
  components/ComparisonView.jsx   side-by-side canvases + delta metrics
```

### APIs (additions)

| Method | Path | Description |
|---|---|---|
| GET | `/api/comparison/latest` | Latest primary/shadow summaries + delta |
| WS | `/ws/simulation/shadow` | Live shadow-runner snapshot (same shape as `/ws/simulation`) |
| WS | `/ws/comparison` | Latest comparison snapshot, broadcast at 1Hz |

### Database changes

None — the shadow runner is intentionally not persisted (only the primary
run is), keeping Milestone 8's `traffic.db` scoped to the run a user
actually configured, not doubled by an internal comparison artifact.

### UI screens (additions)

New "Fixed vs. Adaptive" tab (alongside the existing "Dashboard" tab in
`App.jsx`): a delta strip (total exited per side, avg-wait-time delta) above
two side-by-side `IntersectionCanvas` views, one per controller.

### Testing strategy (additions)

```bash
cd backend
python -m pytest -q
```

- `tests/test_simulation.py` — two `SimulationEngine(seed=42)` instances
  ticked identically produce identical `total_active_vehicles` at every
  step over 1000 ticks; an unseeded engine still works exactly as before
  (no regression for every pre-Milestone-9 call site).
- `tests/test_comparison.py` — delta computed correctly when both sides
  have throughput; delta is `None` (not a fabricated number) when either
  side has zero throughput; same seed produces identical arrivals on the
  very first tick, before either controller's own logic could diverge
  anything.

All 57 tests pass (52 from Milestones 1–8 + 5 new). Verified live: started
the backend fresh and confirmed `/ws/simulation` and `/ws/simulation/shadow`
report matching `total_active_vehicles` (12 and 12) at nearly the same
`sim_time`, with `controller` correctly showing
`EmergencyPreemptionController(FixedTimerController)` on the primary and
`EmergencyPreemptionController(AdaptiveController)` on the shadow —
confirming the seed match and correct "other controller" selection.
`/api/comparison/latest` starts at `null`/`0` (honestly, before either side
has had a vehicle exit) and updates live as the run progresses — after a
few minutes it showed `{"primary": {"total_exited": 29, "avg_wait_time_s":
7.1}, "shadow": {"total_exited": 35, "avg_wait_time_s": 4.67}, "delta":
{"avg_wait_time_s": -2.43, "throughput": 6}}`: on identical seeded traffic,
the adaptive controller (shadow) moved 6 more vehicles through with a 2.43s
lower average wait time than the fixed-timer baseline (primary) — a real
measured result from this run, not a target number worked backward from.

Note: those figures were measured at the original `BASE_SPAWN_RATE_PER_S`
of 0.35. That was subsequently lowered to 0.12 for dashboard readability
(see "Dashboard rendering pass" below), so a re-run produces smaller
absolute numbers — less contention means less for an adaptive controller to
win back. Re-measure rather than quoting the above if the demand rate
changes again — `scripts/benchmark.py` does that across several demand
levels and seeds; see "Benchmark — fixed vs. adaptive" below.

---

## Dashboard rendering pass (post-Milestone 9)

A readability pass over the live intersection canvas
(`frontend/src/utils/draw.js`), prompted by the view being hard to read at a
glance. Two of the findings were genuine geometry bugs, not styling:

- **Opposing traffic was drawn on top of itself.** Every approach's lanes
  were offset from the band centre by the same `±12.65px`, so a north-bound
  vehicle that had cleared the junction occupied the exact same lane column
  (x=307) as south-bound vehicles still approaching it. Fixed by giving each
  approach its own **carriageway** on the left-hand side of its travel
  direction (keep-left, matching the project's Indian context), so the two
  directions never share pixels and the solid median line now means
  something.
- **All four stop lines collapsed onto the canvas centre.** `STOP_LINE_POS_M`
  mapped to offset 0, i.e. the exact middle of the intersection box, so the
  four stop lines drew as a single plus-shape through the junction instead of
  four lines at its edges. Fixed with an explicit piecewise position mapping:
  the stop line maps to the box edge, `STOP_LINE_POS_M → INTERSECTION_EXIT_POS_M`
  interpolates across the box, and beyond that continues out the far side —
  so queue, junction, and exit now read as three distinct zones.
- **Traffic lights were mispositioned**, sitting partly inside the junction
  box and (for two of the four approaches) landing almost on top of each
  other in the same corner. Each signal now sits in its own corner beside its
  own stop line, on its own approach's side.
- **Moving vs. stopped was indistinguishable.** Vehicles now show a red
  outline with a dimmed body when queued (`speed < 0.5 m/s`, the same
  threshold the simulation itself uses) versus a dark outline plus a yellow
  leading-edge "headlight" bar when rolling, which doubles as a heading cue.
- **Vehicle types were hard to tell apart** — the palette was re-spaced
  across the hue wheel, and a legend sits under the canvas mapping colour →
  type alongside the moving/stopped/emergency states. (Vehicle lengths were
  later switched to true scale — see the overlap fix below.)
- **Traffic volume reduced** (`BASE_SPAWN_RATE_PER_S` 0.35 → 0.12, jitter
  0.9 → 0.6) and the canvas enlarged 640 → 760px. Measured live afterwards:
  the intersection settles at ~16 vehicles total across all four roads with
  queues of 1–3, so individual vehicles are followable while congestion still
  genuinely builds and clears.

---

## Overlap fix, high-traffic alert, and on-screen explanations

Prompted by vehicles visibly passing over each other, and by the need for the
dashboard to show an audience — in plain words — when traffic is high, what the
system does about it, and what every number means.

### Vehicles passing through each other — a real physics bug

Measured before touching anything, in a 30-minute seeded headless run: same-lane
vehicles overlapped by up to **14.75m**, and on **7,180 ticks** a follower was
*ahead* of its leader (fixed-timer run; the adaptive run showed the same failure
at a lower rate). The car-following rule only reacted inside
`SAFE_FOLLOWING_GAP_M` (8m), but a car at 14 m/s needs ~22m to stop — so
followers ran into and through stopped queues. Cross-traffic both inside the
junction at once was rare (5s of 1800s), so that was not the cause.

- **`simulation/entities/lane.py`** — Gipps-style safe speed: a vehicle may only
  travel as fast as still lets it stop `MIN_VEHICLE_GAP_M` behind its leader,
  assuming the leader brakes as hard as it can. A hard position clamp backs this
  up so no timestep can ever produce an overlap.
- **`simulation/entities/road.py`** — the spawn check measured clearance to the
  last vehicle's *nose*, so a 10m bus could have a new vehicle spawned inside it.
  It now measures to its rear.
- **After:** 0 overlaps and 0 pass-throughs over the same 30-minute runs, with
  throughput unchanged (851 vs. 854 vehicles through, fixed vs. adaptive).
  Regression test: `test_vehicles_never_overlap_or_pass_through_each_other`
  (heavy demand against a long red — exactly the case that used to break).
- **Renderer at true scale.** `draw.js` had been drawing vehicles longer than
  their real gaps, which would overlap on screen even with correct physics.
  Lengths now come from the simulation (`length` is in each vehicle's state) at
  3px/m, with the junction mapped at 6px/m, so the drawing can never overlap
  unless the simulation does. Checked live across 462 same-lane pairs: smallest
  drawn gap 6.0px — exactly the 2m minimum gap.
- **`ROAD_LENGTH_M` 260 → 330** so vehicles drive off the edge of the view
  instead of vanishing mid-screen. Side effect caught and fixed:
  `Road.has_emergency_vehicle()` counted an ambulance until it left the *map*,
  which would now have held every other road at red for several extra seconds.
  It now counts only emergency vehicles that haven't cleared the junction
  (`INTERSECTION_EXIT_POS_M`) — which is what "hold green until it passes" means.

### High-traffic signal for the audience

- **Thresholds recalibrated from measurement.** At the current demand rate,
  per-road density measured p50 ≈ 2.0–2.5, p90 ≈ 4.2–5.8, p97 ≈ 6.2–8.8, max ≈
  12–14. The old thresholds (low ≤ 5, high > 15) meant "high" could *never*
  happen, so any alert would never have appeared. Now low ≤ 3.0, high > 6.0
  (`analytics/config.py`). Instantaneous "high" on at least one road: 35% of the
  time under the fixed timer vs. 14% under adaptive.
- **Alert hysteresis (`analytics/alerts.py`).** Density hovers around the
  threshold, so an alert driven straight off it blinked: 43 of ~70 alerts lasted
  under a second. The `high_traffic_alert` flag switches on the moment density
  goes above 6.0 and off only after 3s at or below it. Measured hold options:
  2s still left ~half the alerts under 3s; **3s** left none, median alert 6.4s
  (fixed) / 3.4s (adaptive). The low/medium/high badges still show the honest
  instant reading; only the flashing alert is held.
- **On screen:** a pulsing red carriageway plus a "HIGH TRAFFIC · density N" tag
  on the canvas, and a banner at the top of the side column naming each busy
  road and — in words that mirror the real rule — what the running controller is
  doing about it (e.g. adaptive "holding green past the 8s minimum because North
  + South are busier" vs. fixed "green lasts exactly 20s whatever the traffic").

### Every number explained

- **`GET /api/explain`** returns every constant the numbers are computed from
  (density weights and factors, congestion thresholds, alert hold, fixed and
  adaptive timings, emergency hold, tracking thresholds), read from the modules
  that use them — so explanations on screen quote live values, never copies.
- **Density breakdown.** Each road's state now carries `density_breakdown`: the
  exact formula itemized per (vehicle type, waiting/moving), summing to its
  `density_score` (`decision_engine/density.py::road_density_breakdown`).
- **"How it works" tab:** the five-step pipeline (with an explicit note that the
  lights are decided from exact vehicle positions, and the camera pipeline runs
  alongside for display), a live worked density calculation for the busiest
  road, the three controller rules with the one currently running highlighted,
  every phase code, and a glossary of every term on the dashboard, grouped by
  panel.
- **Inline meanings** under Simulation Overview, Signal Status, the CCTV grid,
  Analytics, and the comparison view.

---

## Emergency override change-interval fix

An offline audit (every tick of 30-minute seeded runs) found that the
Milestone 6 override only guaranteed "never two conflicting greens". It
did not guarantee the change intervals around a preemption:

- **Hand-back skipped yellow and all-red.** Ending a preemption called
  `inner.resync()`, which instantly re-applied the inner controller's
  frozen phase. The emergency road could go green → red directly and the
  cross direction could go green in the same tick (about 100–145 green→red
  jumps and 40–75 short clearances per 10 × 30 min runs).
- **Entry cut short yellow / all-red already in progress**, and the
  non-conflicting partner road (e.g. South while serving North) was
  flipped green → red.
- **Flash greens.** A preemption could cut a green that had just started,
  and a vehicle held past `MAX_HOLD_S` re-triggered preemption at once.

Fix (`decision_engine/emergency_preemption.py`):

- Two new states, `RELEASE_YELLOW` and `RELEASE_CLEARING`: leaving
  preemption shows the full yellow and all-red, then calls the new
  `SignalControllerBase.resume_from_all_red(intersection, served_roads)`,
  which restarts the fixed/adaptive controller at the green of the
  direction that was held, with fresh timers.
- On entry, a yellow already showing keeps its remaining time and an
  all-red in progress only runs its remaining clearance (read from each
  light's `time_in_state_s`).
- `PREEMPT_GREEN` serves the emergency road's whole direction.
- `MIN_GREEN_BEFORE_PREEMPT_S = 5`: a green showing for less than this is
  not cut. An approach that already has green is served first.

`simulation/signal_audit.py` (`SignalAudit`) checks conflicting greens,
green→red, yellow→green, short yellow and short all-red each tick. The
tests in `tests/test_emergency_preemption.py` use it, including two
900-second seeded runs (fixed and adaptive) that must record zero
violations.

## Milestone 10 — Dockerization, hardening, and the hardware bridge

**Objective:** run the whole stack with one command, prove it in CI, and let
real signal heads follow the controller.

### Containers

```bash
docker compose up --build      # dashboard at http://localhost:8080
```

- `backend/Dockerfile` — built from the **repo root** (the backend imports
  `simulation/`, `decision_engine/`, `analytics/`, `database/`, `vision/` and
  `shared/`, so they must be in the build context). Runs as a non-root user,
  keeps the SQLite file in `/data` (a named volume, so history survives a
  restart), and has a `HEALTHCHECK` on `/api/health`.
- `frontend/Dockerfile` — two stages: Vite build, then nginx serving the
  static bundle. `frontend/nginx.conf` proxies `/api/` and `/ws/` to the
  backend container, so the dashboard runs on a single origin and the
  WebSocket upgrade headers are set (with a 1-hour read timeout, otherwise the
  live feed is cut).
- `VITE_*` values are **build args**, not runtime env vars — Vite bakes them
  into the bundle. `VITE_API_BASE_URL=""` makes the REST calls relative
  (`/api/...`) so they flow through the nginx proxy.
- `docker-compose.yml` sets `STMS_CONTROLLER_TYPE` (defaults to `adaptive`
  here), the container database path, and the CORS origin; the frontend waits
  for the backend's healthcheck via `depends_on: condition: service_healthy`.

### CI (`.github/workflows/ci.yml`)

Three jobs on every push: the backend test suite, the frontend build, and a
Docker job that builds both images, starts the stack, waits for the
healthcheck, smoke-tests the API and the dashboard proxy, and asserts that
`sim_time` actually advances (a container that boots but whose simulation
loop is dead would otherwise pass). Logs upload as an artifact on failure.

### Hardware bridge (`hardware/`)

`hardware/gpio_driver.py` (Raspberry Pi) and
`hardware/esp32_signal_driver/` (ESP32) poll `GET /api/signals/status` and
mirror each approach's light on three GPIO pins. Both are **clients** — no
simulation, decision-engine or backend code changes for hardware, which is the
same interface argument as Milestone 5's controller swap. Both implement a
blinking-yellow failsafe after three consecutive failed polls, and both ship a
power-on self test for checking wiring. `hardware/traffic-signal.service`
starts the Pi driver at boot. See `hardware/README.md` for the pin map, wiring
rules, and the conflict-monitor requirement for any real-road installation.

### Verification

`docker compose` could not be run on the development machine (Docker Desktop
belongs to another Windows profile there), so the container stack is verified
by the CI job rather than locally. What *was* verified locally: `pytest` (68
passed), the frontend build with the compose build args (WebSocket URLs baked
correctly, REST calls relative, no `127.0.0.1:8000` left in the bundle),
`docker-compose.yml` and the workflow YAML parsing, `STMS_CORS_ORIGINS` JSON
parsing into `Settings`, and `gpio_driver.py` in `--dry-run` mirroring the live
backend (including the failsafe when the backend was stopped).

## Benchmark — fixed vs. adaptive

Milestone 9's live comparison is a single run at whatever demand the
dashboard uses. `scripts/benchmark.py` produces the repeatable version: both
controllers, headless, against identical seeded traffic at three demand
levels, 10 seeds each.

```bash
python scripts/benchmark.py                    # ~2 min: 30 min simulated x 10 seeds x 3 levels
python scripts/benchmark.py --csv results.csv  # also write every individual run
python scripts/benchmark.py --duration 300 --seeds 3   # quick check
```

Measured with the defaults:

| Traffic | Arrivals per road | Fixed avg wait | Adaptive avg wait | Wait reduction | Adaptive better | Vehicles through (fixed / adaptive) |
|---|---|---|---|---|---|---|
| low | 216/h | 6.85 s | 4.47 s | 34.7% (sd 4.8) | 10/10 seeds | 421 / 422 |
| medium | 432/h | 7.16 s | 4.57 s | 36.2% (sd 2.9) | 10/10 seeds | 841 / 837 |
| high | 900/h | 7.50 s | 4.84 s | 35.5% (sd 3.8) | 10/10 seeds | 1638 / 1613 |

What these numbers are, and are not:

- **Wait time** is time a vehicle actually spent stopped in a queue
  (`Vehicle.queued_time_s`, Milestone 7), averaged over every vehicle that
  left the map — not total travel time.
- **Both sides are built through `controller_factory.build_controller()`**,
  so both get emergency preemption; the controller strategy is the only
  difference. Each seed gives both sides the exact same arrivals.
- **Throughput is unchanged** (within 1.5%): the adaptive controller cuts
  waiting, it does not push more vehicles through. At high demand it moves
  slightly fewer, since longer greens mean fewer phase changes.
- **These are simulation results**, from this project's own traffic model
  and the vehicle positions it knows exactly — not measurements from a
  real intersection or from the camera pipeline.

The demand level is the one simulation input the script varies, via
`SimulationEngine(base_spawn_rate_per_s=...)`; everything else uses the
live dashboard's constants. `tests/test_benchmark.py` keeps the script
runnable.

## Running it

### Backend

```bash
cd Final-Year-Project   # the repo root, whatever you cloned it as
python -m venv .venv
source .venv/Scripts/activate        # Windows Git Bash; use .venv\Scripts\Activate.ps1 in PowerShell
pip install -r backend/requirements.txt

# Run from the repo root so both `simulation`/`shared` (root) and `app` (backend/) are importable
PYTHONPATH="$(pwd):$(pwd)/backend" uvicorn app.main:app --reload --app-dir backend --port 8000
```

Backend is live at `http://127.0.0.1:8000` (docs at `/docs`). Creates
`traffic.db` (SQLite) in the current directory on first run — see Milestone 8.

Optional environment variables (`STMS_` prefix, see `backend/app/core/config.py`):

| Variable | Default | Effect |
|---|---|---|
| `STMS_CONTROLLER_TYPE` | `fixed` | `adaptive` switches the primary dashboard to the Milestone 5 adaptive controller (both always get Milestone 6 emergency preemption) |
| `STMS_DATABASE_URL` | `sqlite+aiosqlite:///./traffic.db` | Point at a `postgresql+asyncpg://...` DSN to use Postgres instead — no code change needed |
| `STMS_COMPARISON_SEED` | `42` | Shared seed for the primary + Milestone 9 shadow runner, so both see identical vehicle arrivals |

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard is live at `http://localhost:5173`.

### Running the tests

```bash
cd backend
python -m pytest -q
```

72 tests across `tests/test_simulation.py`, `tests/test_api.py`,
`tests/test_connection_manager.py`, `tests/test_vision.py`,
`tests/test_tracker.py`, `tests/test_density.py`,
`tests/test_adaptive_controller.py`, `tests/test_emergency_preemption.py`,
`tests/test_analytics.py`, `tests/test_database.py`,
`tests/test_comparison.py`, and `tests/test_benchmark.py` — see each
milestone section above for what's covered where.

---

## Future extension points (no architectural changes required)

- Real CCTV feeds slot into `vision/` in place of virtual camera frames
- `decision_engine/` gains a future `RLController` alongside the existing
  `AdaptiveController`, implementing the same `SignalControllerBase`
  interface — nothing upstream needs to change
- `database/session.py`'s `Database` class already takes a plain
  `DATABASE_URL`; swapping SQLite for Postgres is a one-line config change
- Adding a Postgres service to `docker-compose.yml` (Milestone 10 ships
  backend + frontend, with SQLite on a named volume) needs only the
  service and an `STMS_DATABASE_URL` pointing at it
- The adaptive controller decides from the simulation's exact vehicle
  positions; a camera-driven mode would feed it counts from `vision/`
  instead, through the same density functions
