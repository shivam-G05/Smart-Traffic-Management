import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from vision.config import VISION_BROADCAST_HZ
from vision.detector import HaarVehicleDetector
from vision.pipeline import analyze_road
from vision.tracker import ByteTracker

from app.simulation_runner import SimulationRunner
from app.ws.connection_manager import ConnectionManager

logger = logging.getLogger("vision_runner")


class VisionRunner:
    """Periodically renders a virtual camera frame per road from the latest
    simulation snapshot and runs Haar cascade detection + tracking on it.
    Runs at its own (lower) rate on a single worker thread — frame render,
    cascade detection, and tracking are all CPU-bound and synchronous, so
    they must not run inline on the asyncio event loop where they would
    stall the simulation tick broadcast.
    """

    def __init__(self, simulation_runner: SimulationRunner, manager: ConnectionManager):
        self.simulation_runner = simulation_runner
        self.manager = manager
        self.detector = HaarVehicleDetector()
        # One tracker per road, created lazily and kept alive for the life
        # of the process — this persistent state is what makes tracking
        # (as opposed to per-tick detection) possible at all.
        self.trackers: dict[str, ByteTracker] = {}
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vision")
        self._task: asyncio.Task | None = None
        self._latest_snapshot: dict = {}
        self._last_tick_time: float | None = None

    @property
    def latest_snapshot(self) -> dict:
        return self._latest_snapshot

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())
            logger.info("Vision runner started")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._executor.shutdown(wait=False)

    async def _run(self) -> None:
        interval = 1.0 / VISION_BROADCAST_HZ
        loop = asyncio.get_event_loop()
        while True:
            try:
                state = self.simulation_runner.latest_state
                if state and state.get("roads"):
                    dt = self._elapsed_since_last_tick(default=interval)
                    snapshot = await loop.run_in_executor(
                        self._executor, self._analyze_all_roads, state, dt
                    )
                    self._latest_snapshot = snapshot
                    await self.manager.broadcast_json(snapshot)
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Keep the vision loop alive across transient errors, same as
                # the simulation loop — one bad frame must not stop the feed.
                logger.exception("Vision frame failed; continuing")
                await asyncio.sleep(interval)

    def _elapsed_since_last_tick(self, default: float) -> float:
        now = time.monotonic()
        dt = default if self._last_tick_time is None else now - self._last_tick_time
        self._last_tick_time = now
        return max(dt, 1e-3)

    def _analyze_all_roads(self, state: dict, dt: float) -> dict:
        roads = {}
        for road_name, road_state in state["roads"].items():
            # Stable per-road seed, NOT varied by tick. A per-tick-varying
            # seed (the Milestone 2 behavior) fully re-randomizes the
            # background texture every broadcast, which made even a
            # perfectly stationary real vehicle's detection box land at an
            # uncorrelated position each frame — no detection could ever
            # survive two consecutive ticks, so no track could ever be
            # confirmed. A real camera's background does not do this; the
            # texture only needs to differ *between* roads, not over time.
            seed = hash(road_name) % 1000
            tracker = self.trackers.setdefault(road_name, ByteTracker())
            roads[road_name] = analyze_road(
                road_name, road_state, self.detector, tracker, dt=dt, seed=seed
            )
        return {"sim_time": state["sim_time"], "roads": roads}
