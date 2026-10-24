"""Composition-root factory for picking a SignalControllerBase implementation.

This is the one module allowed to import both simulation.controllers and
decision_engine directly — backend/app is the composition root; simulation/
and decision_engine/ must never import each other or this module.
"""

from decision_engine.adaptive_controller import AdaptiveController
from decision_engine.emergency_preemption import EmergencyPreemptionController
from simulation.controllers.base_controller import SignalControllerBase
from simulation.controllers.fixed_timer_controller import FixedTimerController


CONTROLLER_TYPES = ("fixed", "adaptive", "adaptive_hold")


def build_controller(controller_type: str, on_event=None, preemption: bool = True) -> SignalControllerBase:
    if controller_type not in CONTROLLER_TYPES:
        raise ValueError(f"Unknown controller type {controller_type!r}; expected one of {CONTROLLER_TYPES}")
    if controller_type == "adaptive":
        inner: SignalControllerBase = AdaptiveController()
    elif controller_type == "adaptive_hold":
        inner = AdaptiveController(hold_while_discharging=True)
    else:
        inner = FixedTimerController()
    # The live server always preempts; preemption=False exists for the
    # experiments in scripts/ that measure what preemption costs.
    return EmergencyPreemptionController(inner, on_event=on_event) if preemption else inner
