"""Audience-facing HIGH TRAFFIC alert, with hysteresis.

`congestion_level` stays an honest instantaneous reading. But density
hovers around the "high" threshold, so driving a flashing alert straight off
it made the alert blink: in a measured 20-minute run, 43 of ~70 alerts
lasted under a second. The alert therefore switches on the moment density
goes above the threshold, and only switches off once density has stayed at
or below it for `hold_s`.
"""

from analytics.config import CONGESTION_HIGH_MIN, HIGH_TRAFFIC_ALERT_HOLD_S


class HighTrafficAlert:
    """Per-road alert state for one simulation. Uses simulation time, not
    wall-clock time, so it behaves identically however fast the sim runs."""

    def __init__(self, threshold: float = CONGESTION_HIGH_MIN, hold_s: float = HIGH_TRAFFIC_ALERT_HOLD_S):
        self.threshold = threshold
        self.hold_s = hold_s
        self._last_high_time: dict[str, float] = {}

    def update(self, road: str, density_score: float, sim_time: float) -> bool:
        if density_score > self.threshold:
            self._last_high_time[road] = sim_time
            return True
        last = self._last_high_time.get(road)
        return last is not None and sim_time - last < self.hold_s
