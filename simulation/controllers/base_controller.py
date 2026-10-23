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

    def describe(self) -> str:
        """Display name for the dashboard/API. Wrapping controllers (e.g.
        Milestone 6's EmergencyPreemptionController) override this to show
        which inner controller they wrap, since plain type(self).__name__
        would otherwise hide it behind the wrapper's own class name.
        """
        return type(self).__name__

    def resync(self, intersection: Intersection) -> None:
        """Re-assert the current phase's light states without advancing any
        internal timer. Default no-op; stateful controllers override this so
        a wrapper (e.g. Milestone 6's emergency preemption) can safely hand
        control back without a stale-phase light glitch.
        """
        pass

    def resume_from_all_red(self, intersection: Intersection, served_roads) -> None:
        """Called by a wrapper (Milestone 6's emergency preemption) after it
        has held every approach red for the full all-red clearance interval.
        `served_roads` had right of way just before that all-red. Phase-based
        controllers restart at the green of the other direction with fresh
        timers; the default simply re-asserts the current phase.
        """
        self.resync(intersection)
