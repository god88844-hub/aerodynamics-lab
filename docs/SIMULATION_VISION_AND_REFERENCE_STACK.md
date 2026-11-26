# Aerodynamics Lab — Vision, Visual Quality & Digital-Twin Reference Architecture

**Locked design record — 26 November 2026.** This document captures the complete product vision, visual/rendering architecture, dual Digital-Twin percentage scoring rules, and reference-platform breakdown so every future builder agent shares the same engineering blueprint across `Phase 0` (Slices `0A`–`0D`) and `Phases 1`–`4`.

---

## 1. Core Vision & Product Goal

Build a **100% standalone, local, offline 3D engineering laboratory** (`apps/desktop/`, Windows primary installer, zero server/Docker requirement) where engineers, students, and inventors can **design, invent, assemble, test, and validate flying machines** in a physics-driven 3D world.

- **Primary Product:** Standalone **Godot 4.7** 3D desktop shell + **C++20 GDExtension** (`packages/engineering-core`) + **Open CASCADE / CadQuery** exact CAD workers + **Python** physics, calibration, and uncertainty quantification (`packages/physics`, `packages/geometry`, `packages/optimization`).
- **Frozen Legacy:** `apps/web/` and the `apps/api/` HTTP server stack remain frozen for security/CI compatibility only; the desktop app runs locally with no HTTP dependency.
- **Credibility Philosophy (NASA-STD-7009 / ASME V&V 10):**
  - Never claim a design "flies" unless the physical model is validated in that operating regime.
  - SI units everywhere; active Hamilton `wxyz` quaternions; double-precision authoritative vehicle state.
  - Every datum carries `source` and `uncertainty`; unsourced/typical values carry `UNVERIFIED_ESTIMATE`.
  - Exceeding any electrical, thermal, structural, or control limit latches `FAIL` (never invented post-failure motion).

---

## 2. Dual Digital-Twin Percentage System

To express virtual-vs-physical reliability clearly in percentages **without masking safety failures or unmeasured inventions**, Aerodynamics Lab computes and displays **two distinct, strictly gated percentage metrics**:

1. **Design Pass / Fail Probability (`%`)** — *"How likely is this aircraft to work vs. fail a limit?"*
   - Computed by propagating real component tolerances, operating limits (battery cutoff/sag, motor/ESC current & thermal limits, structural stress/resonance margins), and environmental/parameter uncertainties through coupled Monte Carlo / UQ runs (`P0A-016`, `P0A-028`, `P0A-032`).
   - Example: `94% Pass / 6% Limit-Violation Risk` inside the validated operating envelope.
2. **Physical Evidence Match (`%`)** — *"How closely has the simulator matched real physical tests on these parts & regimes?"*
   - Derived from normalized residuals vs. the frozen **M21–M27** tolerances (`docs/VALIDATION_TOLERANCES.md`) and M27 simultaneous whole-flight joint coverage across independent holdout experiments (`P0A-024`, `P0A-031`, `P0A-032`).
   - Reported per channel (voltage, thrust/torque, attitude, trajectory, energy, temperature) and as a gated summary—never a single pooled average that hides a failing channel.

### Hard Honesty Rules for Percentages
- **Component Limit Breach:** If any deterministic or worst-case check breaches a declared component limit, the verdict remains **`FAIL`** regardless of how high the trajectory curve match percentage is.
- **Invented Shapes or Unmeasured New Parts:** When a user creates a custom geometry or enters a new part lacking measured bench/flight data, affected parameters are labeled **`UNVERIFIED_ESTIMATE`** and the validation gate reports **`INCONCLUSIVE`**. The UI displays the analytical physics estimate alongside wide uncertainty bounds and explicitly lists which missing datasheet or bench test is required to promote the estimate to validated evidence.

---

## 3. High-End 3D Look & Rendering Architecture (Godot 4.7 Dual-Profile)

High visual fidelity comes from **physically based rendering (PBR), calibrated HDRI lighting, shader craftsmanship, and GPU acceleration**—without sacrificing baseline laptop usability or CI portability:

| Capability | Tier 2 / Dedicated-GPU Profile (`Forward+` Vulkan) | Tier 1 / Baseline Laptop & Headless CI (`gl_compatibility`) |
| --- | --- | --- |
| **Rendering Backend** | Godot 4.7 `Forward+` (Vulkan) | Godot 4.7 `gl_compatibility` (OpenGL/ANGLE; used by `ubuntu-latest` CI `xvfb-run`) |
| **Materials & CAD Clarity** | PBR metal/roughness/clearcoat presets (machined Al 6061-T6, woven CFRP, PA12, anodized aluminum) + Fusion 360-style clean silhouette/edge & selection highlights | Clean PBR/Lambertian presets + deterministic selection/gizmo clarity |
| **Lighting & Environment** | Studio & outdoor HDRI maps, directional sun + contact shadows, SDFGI / reflection probes, subtle bloom & ACES tone mapping | Fast directional + ambient hemisphere lighting, optional shadows off |
| **Physics / CAD Separation** | **Strict separation:** Exact Open CASCADE B-rep solids compute mass/inertia; procedural ImporterMesh LODs & shaders are display-only and never alter engineering inputs (`docs/HARDWARE_AND_FIDELITY.md`) | Same exact Open CASCADE solids and double-precision physics; adaptive coarser display tessellation only |

**Why Godot 4.7 instead of bundling Unreal Engine 5:** Full Unreal Engine or Omniverse/Isaac Sim runtimes add multi-GB dependencies, heavy RTX GPU floors, and break lightweight offline distribution and headless Linux CI. Godot 4.7 gives us native `Forward+` PBR visuals on GPU laptops *plus* `gl_compatibility` portability on 8 GB laptops and CI, all in one standalone Windows executable.

---

## 4. Reference Simulation Landscape & Mapping to Aerodynamics Lab

How industry-standard simulation and graphics tools map onto Aerodynamics Lab's modular architecture:

| Reference Platform / Tool | Core Strength We Learn From | How Aerodynamics Lab Implements / Bridges It |
| --- | --- | --- |
| **PX4 + Gazebo (gz-sim) + ROS 2** | Real firmware in lock-step; ECS separation; sensor noise models (IMU, GPS, barometer, LiDAR, camera); DART/ODE/Bullet physics | Built-in zero-setup controller + double-precision 6-DoF authoritative integrator in base installer; **ArduPilot first + PX4 SITL** adapters (`P0D`); explicit sensor noise/latency/bias models (`P0A-022`, `P0D`) |
| **JSBSim** | Pure C++ data-driven 6-DoF FDM; explicit stability/body frames; validated nonlinear aero coefficient tables | Explicit right-handed SI frames, Hamilton `wxyz` quaternions, versioned coefficient tables & analytic checks (`packages/physics`), expanding to fixed-wing (`0B`) and helicopter/VTOL (`0C`) |
| **NVIDIA Isaac Sim + Pegasus** | OpenUSD stage, RTX ray-traced material-aware sensors, GPU parallelism for RL/vision | Capability-gated synthetic camera/LiDAR experiments in Tier 2 (`P0D`, WP9) clearly tagged **SYNTHETIC** (never physical evidence); hardware-tiered worker budgets |
| **gym-pybullet-drones** | Fast pure-Python headless stepping, multi-agent swarm & RL iteration | Fast headless Python runner (`scripts/lab_project.py`, `packages/optimization`), deterministic seeds, scaling to multi-drone experiments (`0D`) |
| **Webots / AirSim** | Clean socket/RPC controller decoupling, weather/wind effects, cross-platform workflow | Process-isolated supervised CAD/sim workers (`packages/desktop_worker`), editable engineering test grounds & weather (wind, gusts, rain/snow/icing in `0A`/`0D`) |
| **SIMNET / XFLR5 / OpenVSP / OpenFOAM** | Real-time lifting-line + BEMT airframe sizing; airfoil/VLM polar tools; full RANS/LES CFD | Tiered fidelity bridge (`docs/HARDWARE_AND_FIDELITY.md`): Live flight (analytical/BEMT/ROM tables in `0A`) -> Design loop (Panel/VLM/lifting-line in `0B`) -> Detailed analysis (capped local/remote CFD/FEA/thermal workers in `0C`), refusing unsupported regimes rather than guessing |
| **Fusion 360 / Blender / Unreal Engine** | Parametric constrained CAD + PBR/HDRI/tone-mapped viewport realism | **Open CASCADE** exact B-rep solids + constrained sketches/assemblies (`0A`–`0D`) rendered through Godot 4.7 `Forward+` PBR + HDRI studio/field environments |

---

## 5. Standalone Installer vs. Optional Add-Ons

- **Base Windows Installer (Zero Setup, 100% Offline):** Desktop executable, native C++20 core, Open CASCADE/CadQuery CAD runtime, built-in 6-DoF/BEMT/electrothermal/structural physics, built-in flight controller, starter designs, lessons, and compact reference benchmarks.
- **Optional Add-Ons / Data Packs / Tier 2–3 Workers:** Multi-GB raw external research datasets, optional ArduPilot/PX4 SITL firmware binaries, and heavy local/remote CFD/FEA solvers (e.g., OpenFOAM/CalculiX) connected through versioned resource-admitted worker contracts.

---

## 6. Builder Handoff Map Across Phases & Todos

Any future builder agent resuming this repository must follow:
1. `AGENTS.md` (operational rules & boundary checks)
2. `docs/ROADMAP.md` and `docs/MASTER_PLAN.md` (canonical state in `docs/planning/tasks.json`)
3. `docs/ACCEPTANCE_LEDGER.md` (scientific status vs. software completion)
4. This document (`docs/SIMULATION_VISION_AND_REFERENCE_STACK.md`) for visual fidelity, Digital-Twin `%` semantics, and ecosystem boundaries.

- **Phase 0 (Slices `0A` -> `0B` -> `0C` -> `0D`):**
  - `0A`: Multirotor exact CAD, component provenance (`P0A-016`), Godot 4.7 Forward+ PBR/HDRI & `gl_compatibility` desktop loop (`P0A-017`–`P0A-025`), dual Digital-Twin `%` evidence inspection (`P0A-024`, `P0A-031`, `P0A-032`), guided learning (`P0A-034`–`P0A-035`), hardware qualification (`P0A-038`), software exit (`P0A-039`), physical exit (`P0A-040`).
  - `0B`: Fixed-wing CAD-to-aero bridge (panel/VLM/lifting-line) & flight loop (`P0B-001`–`P0B-022`).
  - `0C`: Helicopters, VTOL transitions, and detailed local/remote CFD/FEA/thermal workers (`P0C-001`–`P0C-024`).
  - `0D`: Complete supported CAD, wet/snow/icing weather, autonomy/sensors/swarms (ArduPilot/PX4), learning, and release (`P0D-001`–`P0D-032`).
- **Phases 1–4 (`INTERFACES_AND_REGISTRIES_ONLY` until prerequisite exits & owner entry gates):**
  - `Phase 1`: Bio-inspired morphing/flapping/flexible flight (`P1-001`–`P1-008`).
  - `Phase 2`: Human-scale and crewed engineering (`P2-001`–`P2-008`).
  - `Phase 3`: Jets, compressible/high-speed & turbine/thermal (`P3-001`–`P3-008`).
  - `Phase 4`: Rockets, staging, orbital/re-entry & recovery (`P4-001`–`P4-008`).
