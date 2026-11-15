"""Flight control: PID loops, cascade attitude controller, mixer, and the
deterministic closed-loop simulation harness.

Model status (M3): perfect state knowledge (no sensor noise/delay yet — those
arrive with the sensor models in M4), ideal actuators (controller commands
per-motor thrust; the sourced powertrain's static map bounds them when a
dataset is attached). Control runs at a fixed discrete period with the plant
integrated by RK4 substeps between control ticks.
"""

from physics.controller.attitude import ControlGains, QuadcopterController
from physics.controller.mixer import Mixer
from physics.controller.pid import PID
from physics.controller.simulation import Disturbance, TelemetryResult, run_controlled_simulation

__all__ = [
    "ControlGains",
    "Disturbance",
    "Mixer",
    "PID",
    "QuadcopterController",
    "TelemetryResult",
    "run_controlled_simulation",
]
