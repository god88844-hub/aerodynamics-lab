# Flight dynamics and aerodynamics

Use [coordinates/units](coordinates_and_units.md), [contracts](../contracts/README.md)
and [V&V](vv_and_pirt.md). Physics implementation is held during spec-lock review.

## Existing rigid-body model

For constant mass `m`, constant positive-definite body inertia `I`, body angular
velocity `omega`, non-gravitational body force `F` and body moment `tau` about CoG:

```text
dr_E/dt = v_E
dv_E/dt = R(q_EB) F_B / m + [0,0,−g]
dq_EB/dt = 0.5 q_EB ⊗ [0,omega_B]
domega_B/dt = I⁻¹ (tau_B − omega_B × (I omega_B))
```

`packages/physics/dynamics/rigid_body.py` implements this local, nonrotating flat-Earth
rigid-body scope with RK4 and quaternion normalization. It does not model flexible
structure, variable mass or general articulated aircraft. Moment transfer from a load
at body position `r` uses `tau_CoG = tau_at_r + (r−r_CoG) × F` with one stated datum.
Euler's body-frame rotational equation is derived in
[MIT classical mechanics, Chapter 2](https://ocw.mit.edu/courses/8-09-classical-mechanics-iii-fall-2014/6fe39e8d5ce4ce746ca256dfea665eda_MIT8_09F14_Chapter_2.pdf).

Relative velocity is vehicle minus air, `v_rel = v_vehicle − v_air`, transformed
into the required body/surface frame. For declared reference area `S_ref`, speed `V`
and measured/qualified coefficients, `D = rho V² S_ref C_D / 2` and
`L = rho V² S_ref C_L / 2` give magnitudes in declared wind axes. Drag opposes
relative velocity. Signed coefficients, axes and moment reference must remain explicit.
See NASA's [drag equation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/drag-equation/)
and [lift equation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/lift-equation/).

Propeller conventions: `C_T = T/(rho n² D⁴)` and `C_P = P_shaft/(rho n³ D⁵)`,
where `n` is revolutions/s and `D` diameter. Electrical input power is not shaft power.
Preserve measured negative thrust near windmilling; near-zero relative errors and
unresolved measurement signs cannot establish accuracy. Source definitions and the
existing [UIUC campaign](../campaigns/M24_2_6_UIUC_AXIAL_SWEEPS.md) govern each table.
Ideal isolated steady hover momentum theory gives `T = 2 rho A v_i²`,
`P_ideal = T v_i`, with disk area `A` and induced velocity at the disk `v_i`;
it neglects swirl/profile losses, installation and interactions.
[NASA propeller thrust](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/propeller-thrust/)
describes the momentum basis. This is not a complete BEMT solver.

## CAD-to-aero fidelity ladder

| Level | Intended model and geometry | Current status / qualification needed |
| --- | --- | --- |
| 1 | Analytical/table/lumped models; prospective blade-element/momentum model using exact blade stations and qualified polars | Legacy static tables/rigid-body screening exist. BEMT execution is planned and refused by the contract. Need Reynolds/Mach/inflow, power and installed-force comparisons. |
| 2 | Panel/VLM/vortex methods for supported lifting surfaces and appropriate attached-flow regimes | Planned; no executable capability granted. Need solver verification/convergence, geometry/polar sensitivity and independent load data; stall/viscous effects cannot be assumed. |
| 3 | Viscous CFD and supported coupled models with explicit mesh/boundaries/closure | Planned; no executable capability granted. Need discretization/iteration studies, turbulence/transition discrepancy and matched measurements. More cells alone do not establish validity. |

This is a model hierarchy, separate from hardware Tier 1/2/3. Exact geometry, surface
placement, moment datum, polar provenance, source hashes and applicability live in
`AeroSurface`/`AeroLoads`. Display LOD is never an aerodynamic input. No automatic
switch may silently change a model or transfer validation to a different geometry.

## Limits and evidence

Applicable voltage/current/RPM/temperature/stress/control limits must affect both
verdict and supported plant response. A known excursion is FAIL even if subsequent
breakup/reboot dynamics are unsupported. Missing limits or unsupported aerodynamics
are INCONCLUSIVE/unvalidated, never invented success. Density, drag, inertia or
other parameters without traceable support carry `UNVERIFIED_ESTIMATE` and an
explicit range/assumption. A formula alone supplies no hardware-specific parameter.
Qualification follows [VALIDATION_TOLERANCES](../VALIDATION_TOLERANCES.md);
current component comparisons do not qualify full-aircraft flight.
