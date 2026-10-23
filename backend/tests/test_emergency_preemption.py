import pytest

import simulation.entities.intersection as intersection_module
from decision_engine.adaptive_controller import AdaptiveController
from decision_engine.emergency_preemption import EmergencyPreemptionController
from simulation.config import LightState, RoadName, VehicleType
from simulation.controllers.fixed_timer_controller import (
    EW_GROUP,
    NS_GROUP,
    FixedTimerController,
)
from simulation.engine import SimulationEngine
from simulation.entities.intersection import Intersection
from simulation.entities.vehicle import Vehicle
from simulation.signal_audit import SignalAudit

DT = 0.05


def _spawn_ambulance(intersection: Intersection, road_name: RoadName) -> Vehicle:
    vehicle = Vehicle(vehicle_type=VehicleType.AMBULANCE, lane_index=0, position_m=150.0, speed_mps=0.0)
    intersection.roads[road_name].lanes[0].spawn(vehicle)
    return vehicle


def _step(controller, intersection: Intersection, audit: SignalAudit | None = None) -> None:
    """One controller tick plus the light clocks the engine would advance —
    without moving vehicles, so the scenario stays exactly as set up."""
    controller.update(intersection, dt=DT)
    for road in intersection.roads.values():
        road.light.tick(DT)
    if audit is not None:
        audit.observe()


def _any_conflicting_green(intersection: Intersection) -> bool:
    ns_green = any(intersection.roads[r].light.state == LightState.GREEN for r in NS_GROUP)
    ew_green = any(intersection.roads[r].light.state == LightState.GREEN for r in EW_GROUP)
    return ns_green and ew_green


def _new(inner=None, **kwargs):
    intersection = Intersection()
    controller = EmergencyPreemptionController(inner or FixedTimerController(), clearance_s=1.0, yellow_s=3.0, **kwargs)
    audit = SignalAudit(intersection, DT, yellow_s=3.0, clearance_s=1.0)
    controller.update(intersection, dt=0.0)  # apply the inner controller's initial NS_GREEN lights
    return intersection, controller, audit


def test_ambulance_on_red_road_gets_green_after_min_green_yellow_and_clearance():
    intersection, controller, audit = _new(min_green_s=5.0)
    assert intersection.roads[RoadName.WEST].light.state != LightState.GREEN
    _spawn_ambulance(intersection, RoadName.WEST)

    max_ticks = int((5.0 + 3.0 + 1.0) / DT) + 20  # min green + yellow + clearance, plus slack
    became_green = False
    for _ in range(max_ticks):
        _step(controller, intersection, audit)
        if intersection.roads[RoadName.WEST].light.state == LightState.GREEN:
            became_green = True
            break

    assert became_green
    assert audit.total_violations == 0, audit.first_violations


def test_preemption_never_cuts_a_green_shorter_than_min_green():
    intersection, controller, audit = _new(min_green_s=5.0)
    _spawn_ambulance(intersection, RoadName.EAST)  # NS green has only just started

    ns_green_ticks = 0
    for _ in range(int(10.0 / DT)):
        _step(controller, intersection, audit)
        if intersection.roads[RoadName.NORTH].light.state == LightState.GREEN:
            ns_green_ticks += 1
        else:
            break

    assert ns_green_ticks * DT >= 5.0 - DT / 2
    assert audit.total_violations == 0, audit.first_violations


def test_no_conflicting_green_throughout_preemption():
    intersection, controller, audit = _new()
    _spawn_ambulance(intersection, RoadName.EAST)

    for _ in range(2000):
        _step(controller, intersection, audit)
        assert not _any_conflicting_green(intersection)
    assert audit.total_violations == 0, audit.first_violations


def test_ending_preemption_goes_through_yellow_and_all_red_before_handing_back():
    inner = FixedTimerController()
    intersection, controller, audit = _new(inner)

    for _ in range(int(21.0 / DT)):  # let NS_GREEN finish so SOUTH is red when the ambulance arrives
        _step(controller, intersection, audit)
    ambulance = _spawn_ambulance(intersection, RoadName.SOUTH)
    for _ in range(400):
        _step(controller, intersection, audit)
        if intersection.roads[RoadName.SOUTH].light.state == LightState.GREEN:
            break
    assert intersection.roads[RoadName.SOUTH].light.state == LightState.GREEN
    assert intersection.roads[RoadName.NORTH].light.state == LightState.GREEN  # whole direction is served

    ambulance.exited = True
    _step(controller, intersection, audit)
    assert intersection.roads[RoadName.SOUTH].light.state == LightState.YELLOW

    for _ in range(int((3.0 + 1.0) / DT) + 5):
        _step(controller, intersection, audit)

    assert controller.current_phase_name() == inner.current_phase_name() == "EW_GREEN"
    assert not _any_conflicting_green(intersection)
    assert audit.total_violations == 0, audit.first_violations


def test_taking_over_during_inner_yellow_keeps_the_full_yellow():
    inner = FixedTimerController()
    intersection, controller, audit = _new(inner)

    while inner.current_phase_name() != "NS_YELLOW":
        _step(controller, intersection, audit)
    for _ in range(int(1.0 / DT)):
        _step(controller, intersection, audit)
    _spawn_ambulance(intersection, RoadName.WEST)

    for _ in range(int(10.0 / DT)):
        _step(controller, intersection, audit)
    assert intersection.roads[RoadName.WEST].light.state == LightState.GREEN
    assert audit.total_violations == 0, audit.first_violations


def test_max_hold_cap_is_respected_even_if_emergency_never_clears():
    max_hold_s = 5.0
    intersection, controller, audit = _new(max_hold_s=max_hold_s)
    _spawn_ambulance(intersection, RoadName.NORTH)  # never cleared, so the
    # controller will keep re-preempting for NORTH every time it returns to
    # NORMAL — the cap must still bound each individual PREEMPT_GREEN hold,
    # and the cross direction must still get green in between.

    longest_hold_s = 0.0
    current_hold_s = 0.0
    ew_green_seen = False
    for _ in range(2000):
        _step(controller, intersection, audit)
        if controller._state.name == "PREEMPT_GREEN":
            current_hold_s += DT
            longest_hold_s = max(longest_hold_s, current_hold_s)
        else:
            current_hold_s = 0.0
        ew_green_seen |= intersection.roads[RoadName.EAST].light.state == LightState.GREEN

    assert longest_hold_s <= max_hold_s + DT
    assert ew_green_seen
    assert audit.total_violations == 0, audit.first_violations


@pytest.mark.parametrize("inner_cls", [FixedTimerController, AdaptiveController])
def test_change_intervals_hold_in_long_seeded_runs(monkeypatch, inner_cls):
    monkeypatch.setattr(intersection_module, "BASE_SPAWN_RATE_PER_S", 0.18)
    events = []
    controller = EmergencyPreemptionController(inner_cls(), on_event=lambda *e: events.append(e))
    engine = SimulationEngine(controller=controller, seed=7)
    audit = SignalAudit(engine.intersection, DT)

    for _ in range(int(900 / DT)):
        engine.tick(DT)
        audit.observe()

    assert sum(1 for e in events if e[1] == "EMERGENCY_PREEMPTION_START") >= 2
    assert audit.total_violations == 0, audit.first_violations
