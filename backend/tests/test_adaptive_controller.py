from decision_engine.adaptive_controller import AdaptiveController
from simulation.config import LightState, RoadName, VehicleType
from simulation.controllers.fixed_timer_controller import EW_GROUP, NS_GROUP
from simulation.entities.intersection import Intersection
from simulation.entities.vehicle import Vehicle


def test_adaptive_controller_never_grants_conflicting_greens():
    intersection = Intersection()
    controller = AdaptiveController()
    for _ in range(4000):
        controller.update(intersection, dt=0.05)
        ns_green = any(intersection.roads[r].light.state == LightState.GREEN for r in NS_GROUP)
        ew_green = any(intersection.roads[r].light.state == LightState.GREEN for r in EW_GROUP)
        assert not (ns_green and ew_green)


def _fill_with_queued_cars(intersection: Intersection, road_names, count_per_lane: int):
    for name in road_names:
        road = intersection.roads[name]
        for lane in road.lanes:
            for _ in range(count_per_lane):
                lane.spawn(
                    Vehicle(vehicle_type=VehicleType.CAR, lane_index=lane.lane_index, position_m=190.0, speed_mps=0.0)
                )


def test_green_never_exceeds_max_or_drops_below_min():
    intersection = Intersection()
    controller = AdaptiveController(min_green_s=8.0, max_green_s=45.0)
    # No traffic anywhere: density comparison is 0 <= 0 * threshold -> ends
    # green as soon as min_green_s elapses, never before.
    ns_green_durations = []
    elapsed_in_current_green = 0.0
    in_green = False
    for _ in range(2000):
        prev_phase = controller.phase
        controller.update(intersection, dt=0.05)
        if prev_phase.name in ("NS_GREEN", "EW_GREEN"):
            if not in_green:
                in_green = True
                elapsed_in_current_green = 0.0
            elapsed_in_current_green += 0.05
            if controller.phase != prev_phase:
                ns_green_durations.append(elapsed_in_current_green)
                in_green = False

    assert ns_green_durations
    for duration in ns_green_durations:
        assert duration >= 8.0 - 1e-6
        assert duration <= 45.0 + 1e-6


def test_lopsided_density_extends_green_beyond_min():
    intersection = Intersection()
    controller = AdaptiveController(min_green_s=8.0, max_green_s=45.0, extension_threshold=1.1)
    # Heavily load the NS roads so NS's green (the controller's starting
    # phase) should extend well past min_green_s while density favors it.
    _fill_with_queued_cars(intersection, NS_GROUP, count_per_lane=10)

    elapsed = 0.0
    while controller.phase.name == "NS_GREEN" and elapsed < 200.0:
        controller.update(intersection, dt=0.05)
        elapsed += 0.05

    assert elapsed > 8.0
