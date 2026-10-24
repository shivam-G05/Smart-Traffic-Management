"""Composition-root factory for picking a SignalControllerBase implementation.

This is the one module allowed to import both simulation.controllers and
decision_engine directly — backend/app is the composition root; simulation/
and decision_engine/ must never import each other or this module.
"""

from decision_engine.adaptive_controller import AdaptiveController
from decision_engine.baselines import ActuatedController, DensityLevelController, MaxPressureController
from decision_engine.emergency_preemption import EmergencyPreemptionController
from decision_engine.sensing import SensedController, SensorModel
from simulation.controllers.base_controller import SignalControllerBase
from simulation.controllers.fixed_timer_controller import FixedTimerController

# The first three can run the live dashboard (STMS_CONTROLLER_TYPE); the
# rest are comparison baselines for the experiments in scripts/.
CONTROLLER_TYPES = (
    "fixed",
    "adaptive",
    "adaptive_hold",
    "webster",
    "actuated",
    "max_pressure",
    "density_levels",
)


def build_controller(controller_type: str, on_event=None, preemption: bool = True,
                     sensor: SensorModel | None = None, **options) -> SignalControllerBase:
    """options are passed to the inner controller's constructor: e.g.
    green_s for "webster" (required) or "fixed", and the scoring parameters
    of AdaptiveController for the ablation experiments."""
    if controller_type not in CONTROLLER_TYPES:
        raise ValueError(f"Unknown controller type {controller_type!r}; expected one of {CONTROLLER_TYPES}")
    if controller_type == "adaptive":
        inner: SignalControllerBase = AdaptiveController(**options)
    elif controller_type == "adaptive_hold":
        inner = AdaptiveController(hold_while_discharging=True, **options)
    elif controller_type == "actuated":
        inner = ActuatedController(**options)
    elif controller_type == "max_pressure":
        inner = MaxPressureController(**options)
    elif controller_type == "density_levels":
        inner = DensityLevelController(**options)
    elif controller_type == "webster":
        if "green_s" not in options:
            raise ValueError("'webster' needs green_s (see decision_engine/webster.py)")
        inner = FixedTimerController(**options)
    else:
        inner = FixedTimerController(**options)
    if sensor is not None:
        # Imperfect sensing (scripts/sensing.py): the controller sees the
        # junction through the sensor model; preemption still sees the truth.
        inner = SensedController(inner, sensor)
    # The live server always preempts; preemption=False exists for the
    # experiments in scripts/ that measure what preemption costs.
    return EmergencyPreemptionController(inner, on_event=on_event) if preemption else inner
