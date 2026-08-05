from abc import ABC, abstractmethod

from simulation.entities.intersection import Intersection


class SignalControllerBase(ABC):
    """Strategy interface for deciding traffic light state each tick.

    Any controller (fixed-timer, adaptive/AI, reinforcement-learning) plugs in
    here without the simulation engine, backend, or frontend needing to change.
    """

    @abstractmethod
    def update(self, intersection: Intersection, dt: float) -> None:
        """Inspect intersection state and mutate road light states as needed."""
        raise NotImplementedError

    @abstractmethod
    def current_phase_name(self) -> str:
        """Human-readable label for the active phase, surfaced on the dashboard."""
        raise NotImplementedError
