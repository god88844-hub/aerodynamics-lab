# M25.22–M25.26 Electronic speed controller operating limits

Physics 0.1.2 evaluates each controller's DC supply current against its declared continuous rating. All controllers share the simulated battery bus voltage. The current model assumes one ESC per motor and the same ESC model across a design. The fixture ratings below exercise decisions in software. Physical verification of current, temperature, transient capacity and failure requires independent measurements on the specified controller and installation.

| Phase | Change and reproduction |
| --- | --- |
| M25.22 | Static hover compares the symmetric per-motor branch current with one ESC rating. A 3.708 kg quad at full charge draws 2.914 A per branch and 11.656 A at the pack. An 8 A fixture stays inside its current limit, and a 2 A fixture fails at the initial sample. |
| M25.23 | Flight checks the converged current separately on every rotor. The four commands of 6, 15, 6 and 6 N produce approximately 1.373, 8.924, 1.373 and 1.373 A. A 6 A rating fails on rotor index 1 even though the mean is 3.261 A. The mission records the event and aborts. |
| M25.24 | The shared supply voltage is checked once per control tick. Equality is accepted for both available ratings. An excursion rejects the modeled operating point. Actual semiconductor damage and allowable burst duration are unknown. |
| M25.25 | The batch optimizer checks the controller at initial hover and as the pack discharges. Candidates exceeding its declared envelope receive a recorded reason and are excluded from the feasible Pareto frontier. |
| M25.26 | The stored static report and results panel show FAIL for a declared limit issue and INCONCLUSIVE for physical acceptance when the checked limits hold. The static solver stops at the controller excursion. Earlier saved reports retain their original messages and identify the former pack-current check. |

The generic 20 A controller in the component catalog has an estimated rating. Replace it with a sourced rating for the installed controller before assessing real hardware. The model does not resolve motor phase current or temperature.

Run the regression cases in `tests/physics/test_propulsion.py`, `tests/physics/test_scenarios.py`, `tests/physics/test_optimization.py`, and `tests/integration/test_api.py`. The web suite covers both current and historical saved results.
