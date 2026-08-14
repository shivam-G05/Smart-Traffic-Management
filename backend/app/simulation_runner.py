import asyncio
import logging

from simulation.engine import SimulationEngine

from app.core.config import settings
from app.ws.connection_manager import ConnectionManager

logger = logging.getLogger("simulation_runner")


class SimulationRunner:
    """Owns the single SimulationEngine instance and drives it on a background
    asyncio task: ticks physics at tick_hz, broadcasts state at broadcast_hz.
    """

    def __init__(self, manager: ConnectionManager):
        self.engine = SimulationEngine()
        self.manager = manager
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

    async def _run(self) -> None:
        tick_dt = 1.0 / settings.tick_hz
        broadcast_every_n_ticks = max(1, settings.tick_hz // settings.broadcast_hz)
        tick_count = 0
        while True:
            try:
                self.engine.tick(tick_dt)
                tick_count += 1
                if tick_count % broadcast_every_n_ticks == 0:
                    self._latest_state = self.engine.to_state()
                    await self.manager.broadcast_json(self._latest_state)
                await asyncio.sleep(tick_dt)
            except asyncio.CancelledError:
                raise
            except Exception:
                # A transient error (e.g. a flaky client send) must never
                # permanently freeze the simulation — log and keep ticking.
                logger.exception("Simulation tick failed; continuing")
                await asyncio.sleep(tick_dt)
