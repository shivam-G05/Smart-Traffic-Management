"""Milestone 9: computes a fixed-vs-adaptive comparison snapshot from two
AnalyticsCollector summaries — one for the primary SimulationRunner
(whichever controller STMS_CONTROLLER_TYPE selects), one for a shadow
runner running the *other* controller type against an identical (same-seed)
vehicle arrival sequence, so the controller is the only variable being
compared.
"""


def build_comparison_snapshot(
    primary_collector,
    shadow_collector,
    primary_controller_type: str,
    shadow_controller_type: str,
) -> dict:
    primary_summary = primary_collector.summary()
    shadow_summary = shadow_collector.summary()

    primary_overall = primary_summary["overall"]
    shadow_overall = shadow_summary["overall"]

    avg_wait_delta = None
    if primary_overall["avg_wait_time_s"] is not None and shadow_overall["avg_wait_time_s"] is not None:
        # shadow - primary: negative means the shadow controller achieved a
        # lower average wait time over the run so far.
        avg_wait_delta = round(shadow_overall["avg_wait_time_s"] - primary_overall["avg_wait_time_s"], 2)

    return {
        "primary": {"controller_type": primary_controller_type, **primary_summary},
        "shadow": {"controller_type": shadow_controller_type, **shadow_summary},
        "delta": {
            "avg_wait_time_s": avg_wait_delta,
            "throughput": shadow_overall["total_exited"] - primary_overall["total_exited"],
        },
    }
