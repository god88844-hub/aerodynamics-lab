"""AeroForge physics core.

Simulation logic for the multi-rotor digital-twin laboratory. Every model
carries its assumptions, fidelity level, and validity domain — see
docs/validation_strategy.md. Results produced by these models must always be
reported with best estimate + uncertainty + credibility + caveats
(NASA-STD-7009 / ASME V&V 10 philosophy).

Subpackages
-----------
- dynamics:      6-DOF rigid-body dynamics, quaternions, mass properties
- aerodynamics:  airframe drag, induced velocity, ground effect
- propulsion:    motors, ESCs, propellers, battery pack
- structures:    stress/limit checks for frame members
- integration:   RK4 fallback solver + scipy ODE integration
- validation:    benchmark suite, uncertainty quantification, credibility
"""

__version__ = "0.1.0"
