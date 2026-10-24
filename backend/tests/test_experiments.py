import importlib.util
import math
import random
import sys
from pathlib import Path

from simulation.config import MIN_VEHICLE_GAP_M, VEHICLE_PROFILES, LightState, RoadName
from simulation.controllers.fixed_timer_controller import FixedTimerController
from simulation.engine import SimulationEngine
from simulation.entities.road import Road

from decision_engine.adaptive_controller import AdaptiveController

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = _load("experiment_common")
benchmark = _load("benchmark")
oversaturation = _load("oversaturation")


def _arrivals_so_far(road: Road) -> int:
    return road.total_exited() + road.total_vehicle_count() + road.backlog_count


def _run_red_road(**road_kwargs) -> Road:
    """A single road held at red under heavy demand — the entry jams fast."""
    road = Road(RoadName.NORTH, spawn_rate_per_s=2.0, rng=random.Random(1), **road_kwargs)
    road.light.set_state(LightState.RED)
    for _ in range(1200):  # 60 s
        road.maybe_spawn(0.05)
        road.update(0.05)
    return road


# --- Simulation options the experiments rely on ---------------------------

def test_spawn_rate_is_configurable_per_engine():
    quiet = SimulationEngine(seed=3, base_spawn_rate_per_s=0.05)
    busy = SimulationEngine(seed=3, base_spawn_rate_per_s=0.4)
    for _ in range(1200):
        quiet.tick(0.05)
        busy.tick(0.05)
    assert busy.intersection.total_vehicles_active() > quiet.intersection.total_vehicles_active()


def test_default_road_drops_blocked_arrivals():
    road = _run_red_road()
    assert road.backlog_count == 0
    assert _arrivals_so_far(road) < 120  # 2/s for 60 s offered, most dropped at the jammed entry


def test_entry_backlog_keeps_every_arrival():
    road = _run_red_road(entry_backlog=True)
    # Nothing lost: every arrival is on the road or still waiting. (1200
    # float additions of 0.1 land just under 120, hence 119.)
    assert _arrivals_so_far(road) == 119
    assert road.backlog_count > 0
    assert len(road.backlog_waits_s()) == road.backlog_count
    assert all(w > 0 for w in road.backlog_waits_s())


def test_vehicles_admitted_from_the_backlog_carry_their_entry_wait():
    road = Road(RoadName.NORTH, spawn_rate_per_s=2.0, rng=random.Random(1), entry_backlog=True)
    road.light.set_state(LightState.GREEN)
    for _ in range(600):
        road.maybe_spawn(0.05)
        road.update(0.05)
    waits = [v.entry_wait_s for lane in road.lanes for v in lane.vehicles]
    assert any(w > 0 for w in waits)


def test_backlog_makes_paired_runs_draw_identical_arrivals():
    def rng_state_after(controller):
        engine = SimulationEngine(controller=controller, seed=11, base_spawn_rate_per_s=0.6,
                                  entry_backlog=True, insert_at_speed=True)
        for _ in range(6000):
            engine.tick(0.05)
        return engine.intersection._rng.getstate()

    # Same number of random draws in the same order => identical arrival
    # sequence, even though the two controllers jam the entries differently.
    assert rng_state_after(FixedTimerController()) == rng_state_after(AdaptiveController())


def test_insert_at_speed_enters_moving_and_never_overlaps():
    road = Road(RoadName.NORTH, spawn_rate_per_s=2.0, rng=random.Random(2),
                entry_backlog=True, insert_at_speed=True)
    road.light.set_state(LightState.RED)
    road.maybe_spawn(0.5)  # first arrival, empty lane
    first = road.lanes[0].vehicles[0] if road.lanes[0].vehicles else road.lanes[1].vehicles[0]
    assert first.speed_mps == VEHICLE_PROFILES[first.vehicle_type].max_speed_mps

    for _ in range(2400):  # 120 s against a red light: queue builds back to the entry
        road.maybe_spawn(0.05)
        road.update(0.05)
        for lane in road.lanes:
            for leader, follower in zip(lane.vehicles, lane.vehicles[1:]):
                gap = leader.position_m - leader.profile.length_m - follower.position_m
                assert gap >= MIN_VEHICLE_GAP_M - 1e-6
    assert road.backlog_count > 0  # the queue really did reach the entry


# --- Experiment machinery -------------------------------------------------

def test_same_trial_spec_gives_identical_results():
    spec = common.TrialSpec(controller="adaptive", seed=5, spawn_rate_per_s=0.12, duration_s=120)
    a, b = common.run_trial(spec), common.run_trial(spec)
    assert a.vehicles == b.vehicles and a.samples == b.samples


def test_trial_records_entries_exits_samples_and_greens():
    result = common.run_trial(common.TrialSpec("fixed", seed=1, spawn_rate_per_s=0.12, duration_s=200))
    assert len(result.samples) == 200
    exited = [v for v in result.vehicles if v.exit_s is not None]
    assert exited and all(v.exit_s > v.entry_s for v in exited)
    assert result.green_durations_s and all(length > 0 for _, length in result.green_durations_s)


def test_paired_change_and_confidence_interval():
    change, p = common.paired_change([10.0, 10.0, 10.0], [6.0, 7.0, 8.0])
    assert math.isclose(change, -30.0)
    assert p < 0.05
    mean, half = common.mean_ci([1.0, 2.0, 3.0])
    assert mean == 2.0 and half > 0
    assert math.isnan(common.paired_change([], [])[0])


def test_benchmark_measures_every_vehicle_to_completion():
    levels = {"low": 0.08}
    table = benchmark.run_benchmark(levels, seeds=[1], duration_s=300, jobs=1)
    for controller in ("fixed", "adaptive"):
        for m in table["low"][controller]:
            assert m.measured_vehicles > 0
            assert m.unfinished == 0
            assert m.p95_delay_s >= m.mean_delay_s
    text = benchmark.format_table(table, levels, 300, 1, preemption=True)
    assert "Mean stopped delay" in text and "Throughput" in text


def test_oversaturated_run_cannot_serve_all_demand():
    result = common.run_trial(oversaturation._spec("fixed", 101, 1.5, duration_s=250, dt=0.05))
    m = oversaturation.over_metrics(result)
    assert m.demand_vph > m.throughput_vph > 0
    assert m.queue_growth_vpm > 0
    assert m.spillback_pct > 0
    assert m.delay_all_lb_s >= m.delay_served_s
