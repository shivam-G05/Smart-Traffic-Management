"""Milestone 7: samples a SimulationRunner's latest_state at sample_hz,
turning the cumulative per-road counters Milestone 7 added to `simulation/`
(total_exited, total_wait_time_s) into real-time throughput and average
wait-time deltas, plus a heuristic congestion classification, kept in a
rolling per-road history buffer.

Runner-agnostic by design (only ever reads `.latest_state`) — Milestone 9
reuses this class unmodified against a second (shadow) SimulationRunner for
the fixed-vs-adaptive comparison.
"""

import asyncio
import logging
from collections import deque

from analytics.config import CONGESTION_HIGH_MIN, CONGESTION_LOW_MAX

logger = logging.getLogger("analytics_collector")


def classify_congestion(density_score: float) -> str:
    if density_score <= CONGESTION_LOW_MAX:
        return "low"
    if density_score <= CONGESTION_HIGH_MIN:
        return "medium"
    return "high"


class AnalyticsCollector:
    def __init__(
        self,
        simulation_runner,
        manager=None,
        sample_hz: float = 1.0,
        history_len: int = 600,
        on_sample=None,
        persist_every_n_samples: int = 10,
    ):
        self.simulation_runner = simulation_runner
        self.manager = manager  # optional ConnectionManager for /ws/analytics
        self.sample_hz = sample_hz
        # Optional async callback(state: dict) -> None, invoked every
        # persist_every_n_samples samples (Milestone 8's database writer) —
        # kept generic here so analytics/ never has to import database/.
        self.on_sample = on_sample
        self.persist_every_n_samples = max(1, persist_every_n_samples)
        self._sample_count = 0
        self._history: dict[str, deque] = {}
        self._prev_totals: dict[str, tuple[int, float]] = {}
        self._history_len = history_len
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())
            logger.info("Analytics collector started")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        interval = 1.0 / self.sample_hz
        while True:
            try:
                self.sample()
                if self.manager is not None:
                    await self.manager.broadcast_json(self.latest_snapshot())
                if self.on_sample is not None:
                    self._sample_count += 1
                    if self._sample_count % self.persist_every_n_samples == 0:
                        state = self.simulation_runner.latest_state
                        if state:
                            await self.on_sample(state)
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                raise
            except Exception:
                # A transient sampling error must not kill collection
                # permanently, same policy as the simulation/vision loops.
                logger.exception("Analytics sample failed; continuing")
                await asyncio.sleep(interval)

    def latest_snapshot(self) -> dict:
        """The most recent sample for every road, in the same shape
        broadcast over /ws/analytics."""
        return {road: (history[-1] if history else None) for road, history in self._history.items()}

    def sample(self) -> None:
        state = self.simulation_runner.latest_state
        if not state or not state.get("roads"):
            return

        sim_time = state["sim_time"]
        for road_name, road in state["roads"].items():
            history = self._history.setdefault(road_name, deque(maxlen=self._history_len))
            total_exited = road["total_exited"]
            total_wait_time_s = road["total_wait_time_s"]
            prev_exited, prev_wait = self._prev_totals.get(road_name, (total_exited, total_wait_time_s))

            throughput_delta = total_exited - prev_exited
            wait_delta = total_wait_time_s - prev_wait
            # Never fabricate an average from zero departures in this window.
            avg_wait_time_s = round(wait_delta / throughput_delta, 2) if throughput_delta > 0 else None

            self._prev_totals[road_name] = (total_exited, total_wait_time_s)
            history.append(
                {
                    "sim_time": sim_time,
                    "density_score": road["density_score"],
                    "queue_length": road["queue_length"],
                    "throughput_delta": throughput_delta,
                    "avg_wait_time_s": avg_wait_time_s,
                    "congestion_level": classify_congestion(road["density_score"]),
                }
            )

    def history(self, road: str) -> list[dict]:
        return list(self._history.get(road, []))

    def summary(self) -> dict:
        state = self.simulation_runner.latest_state
        roads = state.get("roads", {}) if state else {}

        roads_summary = {}
        total_exited_all = 0
        total_wait_all = 0.0
        for road_name, road in roads.items():
            total_exited = road["total_exited"]
            total_wait_time_s = road["total_wait_time_s"]
            avg_wait = round(total_wait_time_s / total_exited, 2) if total_exited > 0 else None
            roads_summary[road_name] = {
                "total_exited": total_exited,
                "avg_wait_time_s": avg_wait,
                "density_score": road["density_score"],
                "congestion_level": classify_congestion(road["density_score"]),
            }
            total_exited_all += total_exited
            total_wait_all += total_wait_time_s

        overall_avg_wait = round(total_wait_all / total_exited_all, 2) if total_exited_all > 0 else None
        return {
            "roads": roads_summary,
            "overall": {"total_exited": total_exited_all, "avg_wait_time_s": overall_avg_wait},
        }
