from decision_engine.adaptive_controller import AdaptiveController
from decision_engine.sensing import PerceivedIntersection, SensedController, SensorModel
from simulation.config import LightState, RoadName, VehicleType
from simulation.engine import SimulationEngine
from simulation.entities.intersection import Intersection
from simulation.entities.vehicle import Vehicle


def _intersection_with(positions, vehicle_type=VehicleType.BUS, speed=0.0):
    intersection = Intersection()
    lane = intersection.roads[RoadName.NORTH].lanes[0]
    for p in sorted(positions, reverse=True):
        lane.spawn(Vehicle(vehicle_type=vehicle_type, lane_index=0, position_m=p, speed_mps=speed))
    return intersection


def _seen(controller, intersection):
    controller.update(intersection, 0.05)
    return controller._view.roads[RoadName.NORTH].lanes[0].vehicles


def test_camera_sees_only_its_view_and_reports_no_classes():
    intersection = _intersection_with([190.0, 150.0, 100.0, 205.0])  # 205 m is past the stop line
    seen = _seen(SensedController(AdaptiveController(), SensorModel(view_m=60.0)), intersection)
    assert sorted(v.position_m for v in seen) == [150.0, 190.0]
    assert {v.vehicle_type for v in seen} == {VehicleType.CAR}


def test_class_aware_sensor_keeps_vehicle_types():
    seen = _seen(SensedController(AdaptiveController(), SensorModel(class_blind=False)), _intersection_with([190.0]))
    assert seen[0].vehicle_type == VehicleType.BUS


def test_recall_drops_detections_and_phantoms_appear_at_fixed_spots():
    intersection = _intersection_with([199.0 - 2 * i for i in range(20)])
    missed = _seen(SensedController(AdaptiveController(), SensorModel(recall=0.3, seed=1)), intersection)
    assert 0 < len(missed) < 20

    phantom_ctrl = SensedController(AdaptiveController(), SensorModel(phantoms_per_approach=2, seed=3))
    empty = Intersection()
    first = sorted(v.position_m for v in _seen(phantom_ctrl, empty))
    for _ in range(20):  # several refreshes later the phantoms are still in the same places
        phantom_ctrl.update(empty, 0.05)
    later = sorted(v.position_m for v in phantom_ctrl._view.roads[RoadName.NORTH].lanes[0].vehicles)
    assert len(first) == 1 and first == later  # 2 phantoms per approach -> 1 per lane
    assert all(v.speed_mps == 0.0 for v in phantom_ctrl._view.roads[RoadName.NORTH].lanes[0].vehicles)


def test_view_refreshes_only_at_the_sensor_rate():
    intersection = _intersection_with([170.0], speed=10.0)
    ctrl = SensedController(AdaptiveController(), SensorModel(refresh_s=0.5))
    ctrl.update(intersection, 0.05)
    lane = intersection.roads[RoadName.NORTH].lanes[0]
    lane.vehicles[0].position_m = 180.0
    ctrl.update(intersection, 0.05)  # 0.1 s since refresh: stale
    assert ctrl._view.roads[RoadName.NORTH].lanes[0].vehicles[0].position_m == 170.0
    for _ in range(9):
        ctrl.update(intersection, 0.05)
    assert ctrl._view.roads[RoadName.NORTH].lanes[0].vehicles[0].position_m == 180.0


def test_commands_reach_the_real_junction():
    intersection = Intersection()
    PerceivedIntersection(intersection).set_light_state(RoadName.EAST, LightState.GREEN)
    assert intersection.roads[RoadName.EAST].light.state == LightState.GREEN


def test_sensed_controllers_keep_the_safety_rules():
    from app.core.controller_factory import build_controller
    from simulation.signal_audit import SignalAudit

    for kind in ("adaptive", "adaptive_hold", "actuated", "max_pressure"):
        engine = SimulationEngine(controller=build_controller(kind, sensor=SensorModel(recall=0.5, phantoms_per_approach=2, seed=2)),
                                  seed=2, base_spawn_rate_per_s=0.3)
        audit = SignalAudit(engine.intersection, 0.05)
        for _ in range(3000):
            engine.tick(0.05)
            audit.observe()
        assert audit.total_violations == 0, (kind, audit.first_violations)
