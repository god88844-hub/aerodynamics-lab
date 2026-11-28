# Numerical and Scientific Verification Dossier

> **Status Notice:** All simulation solvers, CAD transformations, and protocol templates below are software-verified.
> Physical acceptance remains **UNVALIDATED / DEVELOPMENT** pending sealed custodian experimental recordings (`P0A-027`..`P0D-020`), external reviewer sign-offs (`P0A-033`..`P0D-029`), multi-machine hardware qualification (`P0A-038`, `P0D-022`, `P0D-027`), and owner Phase 0 exit (`P0D-032`).

## 1. Authoritative Registry & Open-Data Provenance

- **Registered external sources:** `59` (`data/registry.json`)
- **Tracked empirical campaigns:** `20` (all `DEVELOPMENT`; zero physical acceptance claims)
- **Clean-room Apache-2.0 airfoil coordinate sets bundled:** `3` (`data/airfoils/airfoil_manifest.json`)
- **CycloneDX-subset SBOM components:** `363` (PyPI backend `40`, PyPI CAD `76`, npm web `247`)

## 2. Core Physics & Estimation Kernels (Strict SI, Right-Handed Z-Up, Hamilton `wxyz`)

| Domain | Module | Method / Solver | Physical Scope & Caveats |
| --- | --- | --- | --- |
| C++20 Native Core | `packages/engineering-core/` | Exact parallel-axis mass/inertia & float64 RK4 (`simulate_rk4`) | Zero-dependency Godot GDExtension + CTest parity |
| Multirotor Flight | `packages/physics/scenarios/desktop_runner.py` | Double-precision RK4 + prop/motor lookup + density/weather coupling | Incompressible low-Mach; coupled weather marked `SUPPORTED_WITH_CAVEATS` |
| Atmosphere | `packages/physics/environment/isa_atmosphere.py` | US Standard Atmosphere 1976 (Troposphere & Lower Stratosphere) + Sutherland viscosity | Dry & moist ideal-gas regime up to 32 km |
| Fixed-Wing Aero | `packages/physics/aerodynamics/fixed_wing.py` & `sixdof_fixed_wing.py` | Prandtl Fourier lifting-line + Re polar coupling + 13-state 6-DoF FRD/Z-up derivatives | Fails closed above Mach 0.30 or stall AoA |
| Rotorcraft & VTOL | `packages/physics/aerodynamics/rotorcraft_vtol.py` & `pitt_peters_inflow.py` | Annular BEMT + Cheeseman-Bennett IGE + Pitt-Peters 3-state inflow + autorotation flare + aero-thermo-structural coupling | Fails closed in deep vortex-ring (`climb < -8 m/s`) or `z/R <= 0.35` |
| Propulsion Battery | `packages/physics/propulsion/thevenin_battery.py` | 2-RC polarization equivalent circuit + lumped thermal capacitance | Fails closed on cutoff sag voltage & thermal runaway |
| Autonomy & Vision | `packages/physics/autonomy/ekf_estimator.py` & `sitl_and_swarms.py` | 6-state ES-EKF + ArduPilot/PX4 lock-step + synthetic LiDAR/A*/swarm/AprilTag PnP | Virtual/synthetic (`SYNTHETIC`); real HIL gated at `P0D-018` |
| CAD & 2D Drawings | `packages/geometry/fixed_wing_cad.py` | Undoable sketch/extrude/revolve/boolean stack, Steiner assembly, 3-view SVG/DXF (`ezdxf`) | Fail-closed missing material density |

## 3. Governing Equations & Assumptions Catalog

- **6-DoF rigid-body translation & attitude:** `m * dv/dt = R(q_bw) * f_body + m * g_world; dq/dt = 0.5 * q (*) [0, omega_body]` — _Flat non-rotating Earth, constant standard gravity 9.80665 m/s^2, rigid airframe with active Hamilton wxyz quaternion._
- **Airframe equivalent drag & uniform wind:** `F_drag = -0.5 * rho * CdA * |v_world - wind_world| * (v_world - wind_world)` — _Incompressible low-Mach flight, constant uniform wind vector, no gust spectra or rotor-inflow wake coupling._
- **Ideal gas air density scaling:** `rho = P / (R_air * T), R_air = 287.058 J/(kg*K); T_max_scaled = T_max_static * (rho / 1.225)` — _Dry-air ideal-gas density approximation; high-humidity/icing/rain multiphase aerodynamics remain refused._
- **Prandtl lifting-line fixed-wing finite span aerodynamics:** `CL = pi * AR * A_1; CDi = CL^2 / (pi * AR * e); e = 1 / (1 + sum(n * (A_n/A_1)^2))` — _Incompressible attached-flow Mach <= 0.30, linear lift curve up to stall threshold; clean-room Re drag polar UNVALIDATED until wind-tunnel calibrated._
- **Cheeseman-Bennett in-ground-effect helicopter rotor scaling:** `T_IGE / T_OGE = 1 / (1 - (R / (4 * z_AGL))^2) at constant rotor shaft power` — _Valid for z_AGL / R > 0.35 in axial hover without vortex-ring descent (< -8 m/s)._

## 4. Frozen Validation Protocols (Pre-Registered, Unapproved)

- **Core component & multirotor (`data/research/frozen_protocols.json`):** `P0A026-PROP-BATTERY-COMPONENT-V1`, `P0A026-QUAD-MN3508-FLIGHT-V1`
- **Extended 4-family & weather/autonomy (`data/research/extended_protocols.json`):** `P0B012-FIXEDWING-GLIDER-V1`, `P0C014-ROTORCRAFT-VTOL-V1`, `P0D009-ADVERSE-WEATHER-V1`, `P0D019-AUTONOMY-SITL-V1`
<!-- dossier_sha256_prefix: f25de067fddd96bf -->
