import time

from simulation.controllers.base_controller import SignalControllerBase
from simulation.controllers.fixed_timer_controller import FixedTimerController
from simulation.entities.intersection import Intersection


class SimulationEngine:
    """Owns one intersection and one active signal controller, and advances
    both by a fixed timestep each call to tick(). Framework-agnostic —
    the FastAPI layer drives this loop, it does not know about FastAPI.
    """

    def __init__(self, controller: SignalControllerBase | None = None):
        self.intersection = Intersection()
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
            "controller": type(self.controller).__name__,
            "total_active_vehicles": self.intersection.total_vehicles_active(),
            **self.intersection.to_state(),
        }
