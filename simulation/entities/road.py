import random

from simulation.config import (
    INTERSECTION_EXIT_POS_M,
    LANES_PER_ROAD,
    SAFE_FOLLOWING_GAP_M,
    VEHICLE_PROFILES,
    RoadName,
    VehicleType,
)
from simulation.entities.lane import Lane
from simulation.entities.traffic_light import TrafficLight
from simulation.entities.vehicle import Vehicle

_VEHICLE_TYPES = list(VEHICLE_PROFILES.keys())
_SPAWN_WEIGHTS = [VEHICLE_PROFILES[t].spawn_weight for t in _VEHICLE_TYPES]


class Road:
    def __init__(self, name: RoadName, spawn_rate_per_s: float, rng: random.Random | None = None):
        self.name = name
        self.lanes = [Lane(i) for i in range(LANES_PER_ROAD)]
        self.light = TrafficLight()
        self.spawn_rate_per_s = spawn_rate_per_s
        self._spawn_accumulator = 0.0
        # Defaults to the global `random` module (unseeded, today's
        # behavior). Milestone 9 passes a shared random.Random(seed)
        # instance so two engines can be compared against identical
        # vehicle-arrival sequences.
        self._rng = rng if rng is not None else random

    def maybe_spawn(self, dt: float) -> None:
        self._spawn_accumulator += self.spawn_rate_per_s * dt
        while self._spawn_accumulator >= 1.0:
            self._spawn_accumulator -= 1.0
            self._spawn_vehicle()

    def _spawn_vehicle(self) -> None:
        lane = min(self.lanes, key=lambda l: l.vehicle_count())
        if lane.vehicles:
            last = lane.vehicles[-1]
            # Measure clearance to the last vehicle's *rear*, not its nose —
            # a 10m bus whose nose had passed 6m still covered the spawn
            # point, so new vehicles used to appear inside it.
            if last.position_m - last.profile.length_m < SAFE_FOLLOWING_GAP_M:
                return  # spawn point still occupied, skip this arrival
        vehicle_type: VehicleType = self._rng.choices(_VEHICLE_TYPES, weights=_SPAWN_WEIGHTS, k=1)[0]
        lane.spawn(Vehicle(vehicle_type=vehicle_type, lane_index=lane.lane_index))

    def update(self, dt: float) -> None:
        self.light.tick(dt)
        for lane in self.lanes:
            lane.update(dt, self.light.state)

    def total_queue_length(self) -> int:
        return sum(lane.queue_length() for lane in self.lanes)

    def total_vehicle_count(self) -> int:
        return sum(lane.vehicle_count() for lane in self.lanes)

    def has_emergency_vehicle(self) -> bool:
        """An emergency vehicle that still has to get through this junction.
        Once it has crossed INTERSECTION_EXIT_POS_M it no longer needs a
        green, even though it stays on the map until ROAD_LENGTH_M — counting
        it until then would hold every other road at red for no reason."""
        return any(
            v.is_emergency and v.position_m < INTERSECTION_EXIT_POS_M
            for lane in self.lanes
            for v in lane.vehicles
            if not v.exited
        )

    def total_exited(self) -> int:
        return sum(lane.total_exited for lane in self.lanes)

    def total_wait_time_s(self) -> float:
        return sum(lane.total_wait_time_s for lane in self.lanes)

    def to_state(self) -> dict:
        return {
            "name": self.name.value,
            "light": self.light.to_state(),
            "queue_length": self.total_queue_length(),
            "vehicle_count": self.total_vehicle_count(),
            "has_emergency_vehicle": self.has_emergency_vehicle(),
            "total_exited": self.total_exited(),
            "total_wait_time_s": round(self.total_wait_time_s(), 2),
            "lanes": [lane.to_state() for lane in self.lanes],
        }
