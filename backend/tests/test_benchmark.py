import importlib.util
from pathlib import Path

from simulation.engine import SimulationEngine

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "benchmark.py"
_spec = importlib.util.spec_from_file_location("benchmark", _SCRIPT)
benchmark = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(benchmark)


def test_spawn_rate_is_configurable_per_engine():
    quiet = SimulationEngine(seed=3, base_spawn_rate_per_s=0.05)
    busy = SimulationEngine(seed=3, base_spawn_rate_per_s=0.4)
    for _ in range(1200):
        quiet.tick(0.05)
        busy.tick(0.05)
    assert busy.intersection.total_vehicles_active() > quiet.intersection.total_vehicles_active()


def test_same_seed_gives_identical_runs():
    a = benchmark.run_once("fixed", "medium", 0.12, seed=5, duration_s=120, dt=0.05)
    b = benchmark.run_once("fixed", "medium", 0.12, seed=5, duration_s=120, dt=0.05)
    assert a == b


def test_benchmark_produces_a_row_per_level_and_a_run_per_seed():
    levels = {"low": 0.06, "high": 0.25}
    summaries, runs = benchmark.run_benchmark(levels, seeds=[1, 2], duration_s=300, dt=0.05)

    assert [s.level for s in summaries] == ["low", "high"]
    assert len(runs) == 2 * 2 * 2  # levels x seeds x controllers
    for s in summaries:
        assert s.seeds_compared <= 2
        assert s.fixed_throughput > 0 and s.adaptive_throughput > 0

    table = benchmark.format_table(summaries, 300, 2)
    assert table.count("\n| low |") == 1 and table.count("\n| high |") == 1


def test_zero_departures_never_produce_a_reduction():
    empty = benchmark.RunResult("fixed", "x", 0.1, 1, 0, None)
    other = benchmark.RunResult("adaptive", "x", 0.1, 1, 0, None)
    summary = benchmark.summarize("x", 0.1, [empty], [other])
    assert summary.seeds_compared == 0
    assert summary.adaptive_wins == 0
