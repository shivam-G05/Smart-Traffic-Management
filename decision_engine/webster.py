"""Webster's delay-minimizing cycle length, for the optimized fixed-time
baseline in the experiments (reviewer request: compare against an
optimized fixed-time plan, not only the equal 20 s greens).

Webster (1958): C0 = (1.5 L + 5) / (1 - Y), where L is the lost time per
cycle and Y the sum of the critical flow ratios y = q / s. With two
symmetric phases each phase gets an equal share of C0 - L as green.
"""

# Saturation flow of one approach (both lanes), measured in this simulator:
# the fixed 20 s plan saturated at 10,008 veh/h for the junction
# (scripts/oversaturation.py, preemption off), i.e. 2,502 veh/h per
# approach at a green of 20 s in a 48 s cycle -> 2,502 x 48 / 20 ~ 6,000.
SATURATION_FLOW_VPH = 6000.0
# Yellow + all-red, 4 s per phase, two phases.
LOST_TIME_S = 8.0
# A plan this close to Y = 1 has no finite optimum; use the longest green.
MAX_FLOW_RATIO = 0.95


def webster_green_s(
    arrival_rate_per_s: float,
    saturation_flow_vph: float = SATURATION_FLOW_VPH,
    lost_time_s: float = LOST_TIME_S,
    min_green_s: float = 8.0,
    max_green_s: float = 45.0,
) -> float:
    """Green per phase for mean arrivals of arrival_rate_per_s on every
    approach, clamped to the same [min, max] green as the adaptive
    controllers so every plan obeys the same 50 s maximum red."""
    flow_ratio_per_phase = arrival_rate_per_s * 3600 / saturation_flow_vph
    total_ratio = 2 * flow_ratio_per_phase
    if total_ratio >= MAX_FLOW_RATIO:
        return max_green_s
    cycle_s = (1.5 * lost_time_s + 5) / (1 - total_ratio)
    green_s = (cycle_s - lost_time_s) / 2
    return min(max_green_s, max(min_green_s, green_s))
