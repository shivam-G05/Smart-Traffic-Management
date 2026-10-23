import asyncio
import logging

from analytics.alerts import HighTrafficAlert
from analytics.collector import classify_congestion
from decision_engine.density import compute_intersection_density, road_density_breakdown
from simulation.config import RoadName
from simulation.controllers.base_controller import SignalControllerBase
from simulation.engine import SimulationEngine

from app.core.config import settings
from app.ws.connection_manager import ConnectionManager

logger = logging.getLogger("simulation_runner")


class SimulationRunner:
    """Owns the single SimulationEngine instance and drives it on a background
    asyncio task: ticks physics at tick_hz, broadcasts state at broadcast_hz.
    """

    def __init__(
        self,
        manager: ConnectionManager,
        controller: SignalControllerBase | None = None,
        seed: int | None = None,
    ):
        self.engine = SimulationEngine(controller=controller, seed=seed)
        self.manager = manager
        self._high_traffic_alert = HighTrafficAlert()
        self._task: asyncio.Task | None = None
        self._latest_state: dict = {}

    @property
    def latest_state(self) -> dict:
        return self._latest_state

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())
            logger.info("Simulation runner started")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            logger.info("Simulation runner stopped")

    def _stamp_density(self, state: dict) -> None:
        """Enrich a to_state() dict with Milestone 4 density scores.

        Deliberately done here, not in simulation/engine.py::to_state() —
        simulation/ must stay decision-engine-agnostic (see decision_engine
        module docstring); backend/app is the composition root allowed to
        wire the two together.
        """
        scores = compute_intersection_density(self.engine.intersection)
        for road_name, road_state in state["roads"].items():
            road_score = scores[road_name]
            road_state["density_score"] = round(road_score["road_score"], 2)
            # Stamped at the 10Hz broadcast rate (not just the 1Hz analytics
            # sample) so the dashboard's high-traffic alert reacts live, and
            # classified by the exact same function the analytics collector
            # uses, so the two can never disagree.
            road_state["congestion_level"] = classify_congestion(road_state["density_score"])
            road_state["high_traffic_alert"] = self._high_traffic_alert.update(
                road_name, road_state["density_score"], state["sim_time"]
            )
            road_state["density_breakdown"] = road_density_breakdown(
                self.engine.intersection.roads[RoadName(road_name)]
            )
            for lane_state, lane_score in zip(road_state["lanes"], road_score["lane_scores"]):
                lane_state["density_score"] = round(lane_score, 2)

    async def _run(self) -> None:
        tick_dt = 1.0 / settings.tick_hz
        broadcast_every_n_ticks = max(1, settings.tick_hz // settings.broadcast_hz)
        tick_count = 0
        while True:
            try:
                self.engine.tick(tick_dt)
                tick_count += 1
                if tick_count % broadcast_every_n_ticks == 0:
                    state = self.engine.to_state()
                    self._stamp_density(state)
                    self._latest_state = state
                    await self.manager.broadcast_json(self._latest_state)
                await asyncio.sleep(tick_dt)
            except asyncio.CancelledError:
                raise
            except Exception:
                # A transient error (e.g. a flaky client send) must never
                # permanently freeze the simulation — log and keep ticking.
                logger.exception("Simulation tick failed; continuing")
                await asyncio.sleep(tick_dt)
