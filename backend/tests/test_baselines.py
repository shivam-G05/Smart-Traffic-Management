import pytest

from app.core.controller_factory import CONTROLLER_TYPES, build_controller
from decision_engine.baselines import (
    LEVEL_GREEN_S,
    ActuatedController,
    DensityLevelController,
    MaxPressureController,
)
from decision_engine.webster import webster_green_s
from simulation.config import RoadName, VehicleType
from simulation.controllers.fixed_timer_controller import EW_GROUP, NS_GROUP, FixedTimerController
from simulation.engine import SimulationEngine
from simulation.entities.intersection import Intersection
from simulation.entities.vehicle import Vehicle
from simulation.signal_audit import SignalAudit


def _place(intersection, road_names, position_m, count_per_lane=1, speed_mps=0.0):
    for name in road_names:
        for lane in intersection.roads[name].lanes:
            for i in range(count_per_lane):
                lane.spawn(Vehicle(vehicle_type=VehicleType.CAR, lane_index=lane.lane_index,
                                   position_m=position_m - i * 7.0, speed_mps=speed_mps))


def _ns_green_length(controller, intersection, limit_s=100.0):
    elapsed = 0.0
    while controller.phase.name == "NS_GREEN" and elapsed < limit_s:
        controller.update(intersection, dt=0.05)
        elapsed += 0.05
    return elapsed


# --- Webster ---------------------------------------------------------------

def test_webster_green_grows_with_demand_and_stays_within_bounds():
    greens = [webster_green_s(rate) for rate in (0.05, 0.3, 0.5, 0.6, 0.66, 1.0)]
    assert greens == sorted(greens)
    assert greens[0] == 8.0          # light demand: Webster's optimum is below the minimum green
    assert greens[-1] == 45.0        # Y >= 0.95: no finite optimum, longest green
    assert all(8.0 <= g <= 45.0 for g in greens)


def test_webster_matches_the_formula_in_its_valid_range():
    rate = 0.5  # y = 1800/6000 = 0.3 per phase, Y = 0.6
    cycle = (1.5 * 8 + 5) / (1 - 0.6)
    assert webster_green_s(rate) == pytest.approx((cycle - 8) / 2)


def test_fixed_timer_accepts_a_custom_green():
    controller = FixedTimerController(green_s=12.0)
    assert _ns_green_length(controller, Intersection()) == pytest.approx(12.0, abs=0.06)
    assert controller.describe() == "FixedTimerController(green 12 s)"


# --- Switching rules -------------------------------------------------------

def test_actuated_ends_green_once_gapped_out_if_the_other_side_is_waiting():
    intersection = Intersection()
    _place(intersection, EW_GROUP, position_m=150.0)
    assert _ns_green_length(ActuatedController(), intersection) == pytest.approx(8.0, abs=0.06)


def test_actuated_holds_green_while_the_stop_line_zone_is_occupied():
    intersection = Intersection()
    _place(intersection, NS_GROUP, position_m=195.0)
    _place(intersection, EW_GROUP, position_m=150.0, count_per_lane=5)
    assert _ns_green_length(ActuatedController(), intersection) == pytest.approx(45.0, abs=0.06)


def test_actuated_rests_in_green_without_conflicting_demand():
    # Nothing waiting on EW: no reason to switch, so NS keeps green to the max.
    assert _ns_green_length(ActuatedController(), Intersection()) == pytest.approx(45.0, abs=0.06)


def test_max_pressure_switches_when_the_waiting_side_has_more_vehicles():
    intersection = Intersection()
    _place(intersection, NS_GROUP, position_m=150.0, count_per_lane=1)
    _place(intersection, EW_GROUP, position_m=150.0, count_per_lane=3)
    assert _ns_green_length(MaxPressureController(), intersection) == pytest.approx(8.0, abs=0.06)

    intersection = Intersection()
    _place(intersection, NS_GROUP, position_m=150.0, count_per_lane=3)
    _place(intersection, EW_GROUP, position_m=150.0, count_per_lane=1)
    assert _ns_green_length(MaxPressureController(), intersection) == pytest.approx(45.0, abs=0.06)


@pytest.mark.parametrize(
    ("cars_per_lane", "level"),
    [(0, "low"), (2, "medium"), (5, "high")],  # queued cars score 1.5 each, two lanes per road
)
def test_density_levels_pick_the_green_when_it_starts(cars_per_lane, level):
    intersection = Intersection()
    if cars_per_lane:
        _place(intersection, [RoadName.NORTH], position_m=195.0, count_per_lane=cars_per_lane)
    green = _ns_green_length(DensityLevelController(), intersection)
    assert green == pytest.approx(max(8.0, LEVEL_GREEN_S[level]), abs=0.06)


# --- Every controller obeys the same safety rules -------------------------

@pytest.mark.parametrize("controller_type", CONTROLLER_TYPES)
def test_every_controller_passes_the_signal_audit_in_heavy_traffic(controller_type):
    options = {"green_s": 25.0} if controller_type == "webster" else {}
    engine = SimulationEngine(controller=build_controller(controller_type, **options),
                              seed=4, base_spawn_rate_per_s=0.35)
    audit = SignalAudit(engine.intersection, 0.05)
    for _ in range(6000):  # 300 s
        engine.tick(0.05)
        audit.observe()
    assert audit.total_violations == 0, audit.first_violations


def test_webster_type_requires_a_green():
    with pytest.raises(ValueError):
        build_controller("webster")
