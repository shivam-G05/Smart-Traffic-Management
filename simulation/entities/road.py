import random

from simulation.config import LANES_PER_ROAD, VEHICLE_PROFILES, RoadName, VehicleType
from simulation.entities.lane import Lane
from simulation.entities.traffic_light import TrafficLight
from simulation.entities.vehicle import Vehicle

_VEHICLE_TYPES = list(VEHICLE_PROFILES.keys())
_SPAWN_WEIGHTS = [VEHICLE_PROFILES[t].spawn_weight for t in _VEHICLE_TYPES]


class Road:
    def __init__(self, name: RoadName, spawn_rate_per_s: float):
        self.name = name
        self.lanes = [Lane(i) for i in range(LANES_PER_ROAD)]
        self.light = TrafficLight()
        self.spawn_rate_per_s = spawn_rate_per_s
        self._spawn_accumulator = 0.0

    def maybe_spawn(self, dt: float) -> None:
        self._spawn_accumulator += self.spawn_rate_per_s * dt
        while self._spawn_accumulator >= 1.0:
            self._spawn_accumulator -= 1.0
            self._spawn_vehicle()

    def _spawn_vehicle(self) -> None:
        lane = min(self.lanes, key=lambda l: l.vehicle_count())
        if lane.vehicles and lane.vehicles[-1].position_m < 6.0:
            return  # spawn point still occupied, skip this arrival
        vehicle_type: VehicleType = random.choices(_VEHICLE_TYPES, weights=_SPAWN_WEIGHTS, k=1)[0]
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
        return any(
            v.is_emergency for lane in self.lanes for v in lane.vehicles if not v.exited
        )

    def to_state(self) -> dict:
        return {
            "name": self.name.value,
            "light": self.light.to_state(),
            "queue_length": self.total_queue_length(),
            "vehicle_count": self.total_vehicle_count(),
            "has_emergency_vehicle": self.has_emergency_vehicle(),
            "lanes": [lane.to_state() for lane in self.lanes],
        }
