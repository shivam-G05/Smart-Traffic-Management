import random

from simulation.config import (
    BASE_SPAWN_RATE_PER_S,
    SPAWN_RATE_JITTER,
    RoadName,
)
from simulation.entities.road import Road


class Intersection:
    """A single four-way intersection: four roads sharing one signal cycle."""

    def __init__(
        self,
        rng: random.Random | None = None,
        base_spawn_rate_per_s: float = BASE_SPAWN_RATE_PER_S,
    ):
        # Defaults to a fresh, unseeded Random() rather than the bare
        # `random` module — Milestone 9 needs a *shared* generator instance
        # handed to every Road it constructs (so a given seed reproduces the
        # exact same interleaved arrival sequence every run), which the
        # stateless module-level `random` functions can't provide two
        # independent, separately-seeded instances of.
        self._rng = rng if rng is not None else random.Random()
        # Configurable so scripts/benchmark.py can sweep low/medium/high
        # demand; the live dashboard always uses the config default.
        self.base_spawn_rate_per_s = base_spawn_rate_per_s
        self.roads: dict[RoadName, Road] = {
            name: Road(name, base_spawn_rate_per_s, rng=self._rng) for name in RoadName
        }
        self._reshuffle_timer = 0.0

    def update(self, dt: float) -> None:
        for road in self.roads.values():
            road.maybe_spawn(dt)
            road.update(dt)
        self._maybe_reshuffle_demand(dt)

    def _maybe_reshuffle_demand(self, dt: float) -> None:
        """Periodically skews per-road spawn rates so congestion shifts around
        the intersection over time, instead of staying uniform forever."""
        self._reshuffle_timer += dt
        if self._reshuffle_timer < 15.0:
            return
        self._reshuffle_timer = 0.0
        for road in self.roads.values():
            jitter = self._rng.uniform(1 - SPAWN_RATE_JITTER, 1 + SPAWN_RATE_JITTER)
            road.spawn_rate_per_s = max(0.02, self.base_spawn_rate_per_s * jitter)

    def set_light_state(self, road_name: RoadName, state) -> None:
        self.roads[road_name].light.set_state(state)

    def total_vehicles_active(self) -> int:
        return sum(road.total_vehicle_count() for road in self.roads.values())

    def to_state(self) -> dict:
        return {"roads": {name.value: road.to_state() for name, road in self.roads.items()}}
