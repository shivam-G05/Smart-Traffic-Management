"""Composition-root factory for picking a SignalControllerBase implementation.

This is the one module allowed to import both simulation.controllers and
decision_engine directly — backend/app is the composition root; simulation/
and decision_engine/ must never import each other or this module.
"""

from decision_engine.adaptive_controller import AdaptiveController
from decision_engine.emergency_preemption import EmergencyPreemptionController
from simulation.controllers.base_controller import SignalControllerBase
from simulation.controllers.fixed_timer_controller import FixedTimerController


def build_controller(controller_type: str, on_event=None, preemption: bool = True) -> SignalControllerBase:
    inner: SignalControllerBase = AdaptiveController() if controller_type == "adaptive" else FixedTimerController()
    # The live server always preempts; preemption=False exists for the
    # experiments in scripts/ that measure what preemption costs.
    return EmergencyPreemptionController(inner, on_event=on_event) if preemption else inner
