import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from vision.config import VISION_BROADCAST_HZ
from vision.detector import HaarVehicleDetector
from vision.pipeline import analyze_road

from app.simulation_runner import SimulationRunner
from app.ws.connection_manager import ConnectionManager

logger = logging.getLogger("vision_runner")


class VisionRunner:
    """Periodically renders a virtual camera frame per road from the latest
    simulation snapshot and runs Haar cascade detection on it. Runs at its
    own (lower) rate on a single worker thread — frame render + cascade
    detection is CPU-bound and synchronous, so it must not run inline on the
    asyncio event loop where it would stall the simulation tick broadcast.
    """

    def __init__(self, simulation_runner: SimulationRunner, manager: ConnectionManager):
        self.simulation_runner = simulation_runner
        self.manager = manager
        self.detector = HaarVehicleDetector()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vision")
        self._task: asyncio.Task | None = None
        self._latest_snapshot: dict = {}
        self._frame_counter = 0

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
                    self._frame_counter += 1
                    snapshot = await loop.run_in_executor(
                        self._executor, self._analyze_all_roads, state
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

    def _analyze_all_roads(self, state: dict) -> dict:
        roads = {}
        for road_name, road_state in state["roads"].items():
            seed = self._frame_counter * 4 + (hash(road_name) % 1000)
            roads[road_name] = analyze_road(road_name, road_state, self.detector, seed=seed)
        return {"sim_time": state["sim_time"], "roads": roads}
