import random

from simulation.config import (
    BASE_SPAWN_RATE_PER_S,
    SPAWN_RATE_JITTER,
    RoadName,
)
from simulation.entities.road import Road


def demand_multiplier(profile, t_s: float) -> float:
    """Piecewise-linear demand multiplier at time t_s for a profile of
    (time_s, multiplier) points; constant before the first and after the
    last point. An empty profile means 1.0 (constant demand)."""
    if not profile:
        return 1.0
    if t_s <= profile[0][0]:
        return profile[0][1]
    for (t0, m0), (t1, m1) in zip(profile, profile[1:]):
        if t_s <= t1:
            return m0 + (m1 - m0) * (t_s - t0) / (t1 - t0) if t1 > t0 else m1
    return profile[-1][1]


class Intersection:
    """A single four-way intersection: four roads sharing one signal cycle."""

    def __init__(
        self,
        rng: random.Random | None = None,
        base_spawn_rate_per_s: float = BASE_SPAWN_RATE_PER_S,
        entry_backlog: bool = False,
        insert_at_speed: bool = False,
        reaction_time_s: float = 0.0,
        demand_profile: tuple = (),
    ):
        # Defaults to a fresh, unseeded Random() rather than the bare
        # `random` module — Milestone 9 needs a *shared* generator instance
        # handed to every Road it constructs (so a given seed reproduces the
        # exact same interleaved arrival sequence every run), which the
        # stateless module-level `random` functions can't provide two
        # independent, separately-seeded instances of.
        self._rng = rng if rng is not None else random.Random()
        # Configurable so scripts/ experiments can sweep demand and test
        # above capacity (see Road for entry_backlog); the live dashboard
        # always uses the defaults.
        self.base_spawn_rate_per_s = base_spawn_rate_per_s
        # demand_profile (scripts/peak_period.py): (time_s, multiplier)
        # points scaling the base rate over time, e.g. a rush hour. Empty
        # (the default) keeps demand constant, exactly as before.
        self.demand_profile = tuple(demand_profile)
        self._clock_s = 0.0
        start_rate = base_spawn_rate_per_s * demand_multiplier(self.demand_profile, 0.0)
        self.roads: dict[RoadName, Road] = {
            name: Road(
                name,
                start_rate,
                rng=self._rng,
                entry_backlog=entry_backlog,
                insert_at_speed=insert_at_speed,
                reaction_time_s=reaction_time_s,
            )
            for name in RoadName
        }
        self._reshuffle_timer = 0.0

    def update(self, dt: float) -> None:
        self._clock_s += dt
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
            rate = self.base_spawn_rate_per_s * demand_multiplier(self.demand_profile, self._clock_s)
            road.spawn_rate_per_s = max(0.02, rate * jitter)

    def set_light_state(self, road_name: RoadName, state) -> None:
        self.roads[road_name].light.set_state(state)

    def total_vehicles_active(self) -> int:
        return sum(road.total_vehicle_count() for road in self.roads.values())

    def to_state(self) -> dict:
        return {"roads": {name.value: road.to_state() for name, road in self.roads.items()}}
