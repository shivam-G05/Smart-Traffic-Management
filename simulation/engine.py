import random
import time

from simulation.config import BASE_SPAWN_RATE_PER_S
from simulation.controllers.base_controller import SignalControllerBase
from simulation.controllers.fixed_timer_controller import FixedTimerController
from simulation.entities.intersection import Intersection


class SimulationEngine:
    """Owns one intersection and one active signal controller, and advances
    both by a fixed timestep each call to tick(). Framework-agnostic —
    the FastAPI layer drives this loop, it does not know about FastAPI.
    """

    def __init__(
        self,
        controller: SignalControllerBase | None = None,
        seed: int | None = None,
        base_spawn_rate_per_s: float = BASE_SPAWN_RATE_PER_S,
        entry_backlog: bool = False,
        insert_at_speed: bool = False,
        reaction_time_s: float = 0.0,
    ):
        # seed=None (default) reproduces today's behavior exactly: an
        # unseeded, non-reproducible Intersection. Milestone 9 passes a
        # concrete seed so two engines (fixed vs. adaptive) draw identical
        # vehicle-arrival sequences, isolating the controller as the only
        # variable in the comparison.
        rng = random.Random(seed) if seed is not None else None
        self.intersection = Intersection(
            rng=rng,
            base_spawn_rate_per_s=base_spawn_rate_per_s,
            entry_backlog=entry_backlog,
            insert_at_speed=insert_at_speed,
            reaction_time_s=reaction_time_s,
        )
        self.controller: SignalControllerBase = controller or FixedTimerController()
        self.sim_time_s = 0.0
        self._start_wall_time = time.monotonic()

    def tick(self, dt: float) -> None:
        self.controller.update(self.intersection, dt)
        self.intersection.update(dt)
        self.sim_time_s += dt

    def set_controller(self, controller: SignalControllerBase) -> None:
        self.controller = controller

    def to_state(self) -> dict:
        return {
            "sim_time": round(self.sim_time_s, 2),
            "active_phase": self.controller.current_phase_name(),
            "controller": self.controller.describe(),
            "total_active_vehicles": self.intersection.total_vehicles_active(),
            **self.intersection.to_state(),
        }
