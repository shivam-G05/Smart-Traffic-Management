from simulation.config import (
    INTERSECTION_EXIT_POS_M,
    MIN_VEHICLE_GAP_M,
    ROAD_LENGTH_M,
    SAFE_FOLLOWING_GAP_M,
    STOP_LINE_POS_M,
    LightState,
)
from simulation.entities.vehicle import Vehicle


class Lane:
    """A single queue of vehicles travelling in order along one lane of a road."""

    def __init__(self, lane_index: int):
        self.lane_index = lane_index
        self.vehicles: list[Vehicle] = []  # ordered leader-first

    def spawn(self, vehicle: Vehicle) -> None:
        self.vehicles.append(vehicle)

    def queue_length(self) -> int:
        return sum(1 for v in self.vehicles if v.position_m < STOP_LINE_POS_M and v.speed_mps < 0.5)

    def vehicle_count(self) -> int:
        return len(self.vehicles)

    def update(self, dt: float, light_state: LightState) -> None:
        leader: Vehicle | None = None
        for vehicle in self.vehicles:
            self._update_vehicle(vehicle, dt, light_state, leader)
            leader = vehicle
        self.vehicles = [v for v in self.vehicles if not v.exited]

    def _update_vehicle(
        self, vehicle: Vehicle, dt: float, light_state: LightState, leader: Vehicle | None
    ) -> None:
        profile = vehicle.profile
        target_speed = profile.max_speed_mps

        if leader is not None:
            gap = leader.position_m - leader.profile.length_m - vehicle.position_m
            if gap < SAFE_FOLLOWING_GAP_M:
                target_speed = min(target_speed, leader.speed_mps)
            if gap < MIN_VEHICLE_GAP_M:
                target_speed = 0.0

        must_stop_at_line = (
            light_state != LightState.GREEN
            and vehicle.position_m < STOP_LINE_POS_M
        )
        if must_stop_at_line:
            distance_to_line = STOP_LINE_POS_M - vehicle.position_m
            braking_distance = (vehicle.speed_mps ** 2) / (2 * profile.deceleration_mps2 + 1e-6)
            if braking_distance >= distance_to_line - 0.5:
                target_speed = min(target_speed, 0.0)

        if vehicle.speed_mps < target_speed:
            vehicle.speed_mps = min(target_speed, vehicle.speed_mps + profile.acceleration_mps2 * dt)
        elif vehicle.speed_mps > target_speed:
            vehicle.speed_mps = max(target_speed, vehicle.speed_mps - profile.deceleration_mps2 * dt)

        vehicle.position_m += vehicle.speed_mps * dt

        if vehicle.position_m >= ROAD_LENGTH_M:
            vehicle.exited = True

    def crossing_count(self) -> int:
        return sum(
            1 for v in self.vehicles if STOP_LINE_POS_M <= v.position_m < INTERSECTION_EXIT_POS_M
        )

    def to_state(self) -> dict:
        return {
            "lane_index": self.lane_index,
            "queue_length": self.queue_length(),
            "vehicle_count": self.vehicle_count(),
            "vehicles": [v.to_state() for v in self.vehicles],
        }
