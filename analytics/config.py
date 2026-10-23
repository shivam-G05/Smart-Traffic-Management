"""Heuristic congestion-level thresholds against Milestone 4's density score.

Recalibrated after the demand rate was lowered (BASE_SPAWN_RATE_PER_S
0.35 -> 0.12) and the car-following physics fix. A 30-minute seeded
headless run measured per-road density at p50 ~2.0-2.5, p75 ~2.9-4.0,
p90 ~4.2-5.8, p97 ~6.2-8.8, max ~12-14 (adaptive at the low end, fixed at
the high end). The previous 5/15 thresholds meant "high" could never
occur at all. "high" (> 6.0) now corresponds to roughly the busiest few
percent of the time — rare enough to mean something when it fires, common
enough that an audience will actually see it.
"""

CONGESTION_LOW_MAX = 3.0    # density_score <= this -> "low"
CONGESTION_HIGH_MIN = 6.0   # density_score > this -> "high"; between the two -> "medium"

# How long density must stay at or below CONGESTION_HIGH_MIN before the
# on-screen HIGH TRAFFIC alert switches off (see analytics/alerts.py).
HIGH_TRAFFIC_ALERT_HOLD_S = 3.0
