from simulation.config import LightState, RoadName
from simulation.controllers.fixed_timer_controller import EW_GROUP, NS_GROUP, FixedTimerController
from simulation.engine import SimulationEngine
from simulation.entities.intersection import Intersection
from simulation.entities.road import Road


def test_road_spawns_vehicles_over_time():
    road = Road(RoadName.NORTH, spawn_rate_per_s=5.0)
    for _ in range(100):
        road.maybe_spawn(dt=0.05)
    assert road.total_vehicle_count() > 0


def test_vehicle_moves_forward_on_green():
    road = Road(RoadName.NORTH, spawn_rate_per_s=0.0)
    road.light.set_state(LightState.GREEN)
    road._spawn_vehicle()
    vehicle = road.lanes[0].vehicles[0]
    start_position = vehicle.position_m
    for _ in range(200):
        road.update(dt=0.05)
    assert vehicle.position_m > start_position


def test_vehicle_stops_at_red_light():
    road = Road(RoadName.NORTH, spawn_rate_per_s=0.0)
    road.light.set_state(LightState.RED)
    road._spawn_vehicle()
    for _ in range(400):
        road.update(dt=0.05)
    vehicle = road.lanes[0].vehicles[0]
    assert vehicle.position_m < 200.0 + 1.0


def test_fixed_timer_never_grants_conflicting_greens():
    intersection = Intersection()
    controller = FixedTimerController()
    for _ in range(2000):
        controller.update(intersection, dt=0.05)
        ns_green = any(intersection.roads[r].light.state == LightState.GREEN for r in NS_GROUP)
        ew_green = any(intersection.roads[r].light.state == LightState.GREEN for r in EW_GROUP)
        assert not (ns_green and ew_green)


def test_fixed_timer_eventually_greens_every_road():
    intersection = Intersection()
    controller = FixedTimerController()
    seen_green: set[RoadName] = set()
    for _ in range(2000):
        controller.update(intersection, dt=0.05)
        for name, road in intersection.roads.items():
            if road.light.state == LightState.GREEN:
                seen_green.add(name)
    assert seen_green == set(RoadName)


def test_engine_state_serializes_all_roads():
    engine = SimulationEngine()
    for _ in range(50):
        engine.tick(dt=0.05)
    state = engine.to_state()
    assert set(state["roads"].keys()) == {r.value for r in RoadName}
    assert "active_phase" in state
