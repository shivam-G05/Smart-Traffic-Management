import random

from simulation.config import (
    BASE_SPAWN_RATE_PER_S,
    SPAWN_RATE_JITTER,
    RoadName,
)
from simulation.entities.road import Road


class Intersection:
    """A single four-way intersection: four roads sharing one signal cycle."""

    def __init__(self):
        self.roads: dict[RoadName, Road] = {
            name: Road(name, BASE_SPAWN_RATE_PER_S) for name in RoadName
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
            jitter = random.uniform(1 - SPAWN_RATE_JITTER, 1 + SPAWN_RATE_JITTER)
            road.spawn_rate_per_s = max(0.02, BASE_SPAWN_RATE_PER_S * jitter)

    def set_light_state(self, road_name: RoadName, state) -> None:
        self.roads[road_name].light.set_state(state)

    def total_vehicles_active(self) -> int:
        return sum(road.total_vehicle_count() for road in self.roads.values())

    def to_state(self) -> dict:
        return {"roads": {name.value: road.to_state() for name, road in self.roads.items()}}
