# M23.8–M23.12 bounded control allocation

The flight and hover controllers convert a requested total thrust and body-axis torque into per-rotor thrust. With the previous solver, once a rotor was capped, the remaining rotors were asked to supply the full original request again. The capped rotor's contribution was still applied, so the aircraft could receive more total thrust than requested.

| Phase | Implementation and evidence |
| --- | --- |
| M23.8 | Reproduce the allocation error with an asymmetric Quad-X request that reaches the thrust ceiling on only one side. |
| M23.9 | Solve over all rotors at once, with zero as the lower bound and the configured per-rotor ceiling as the upper bound. Use the existing wrench objective and keep the unconstrained solution when it already fits. |
| M23.10 | Count controller steps with an out-of-bounds unconstrained request, an absolute total-thrust residual above 0.001 N, or a Euclidean body-torque residual above 0.001 N·m. Each step can count toward more than one metric. |
| M23.11 | Return `allocation_control_steps` for closed-loop flight and hover hold and display the counters in the results panel. Older saved results can omit the field. |
| M23.12 | Check the analytic bounded optimum and counter resets, then run the controller, scenario and capstone suites. Record physics version 0.1.1 for the changed allocation behavior. |

The counts describe requested and allocated thrust at the controller, before downstream motor or powertrain dynamics. The reported rotor ceiling is the configured common bound. The 0.001 thresholds are numerical reporting thresholds in their respective units. Hardware acceptance remains open pending measured sensor timing, actuator response and controller behavior, with predeclared tolerances and a physical test configuration.
