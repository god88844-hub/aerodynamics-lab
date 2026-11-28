# Phase 1 Technical Blueprint: Bio-Inspired Morphing, Flapping & Flexible Flight

This document specifies the complete mathematical models, coordinate contracts, dataset provenance, failure gates, and validation plan for **Phase 1 — Bio-inspired flight** (`P1-001`..`P1-008`, tracking issue [#111](https://github.com/god88844-hub/aerodynamics-lab/issues/111)).

> **Governance boundary:** Per [ROADMAP.md](ROADMAP.md) and [MASTER_PLAN.md](MASTER_PLAN.md), Phases 1–4 remain **interfaces, dataset registries, and planned specifications only** until entry gate `P1-001` unlocks. Collected public benchmarks stay tagged `DEVELOPMENT` (`UNVALIDATED`); biological traits are never extrapolated into unverified human or drone airworthiness claims.

---

## 1. Scientific Scope & Vehicle Classes

Phase 1 covers three bio-inspired flight families using a single authoritative double-precision SI plant:

1. **Articulated Morphing Gliders / Flyers (`morphing_wing`)**
   - Variable wrist/finger sweep, spanwise camber/washout, and rudderless tail-spread/tilt reflexes (reference: Stanford/Groningen *PigeonBot II*).
2. **Insect / Bird-Scale Flapping-Wing MAVs (`flapping_wing`)**
   - Periodic high-amplitude flapping strokes ($\phi(t)$) with active or passive feathering pitch ($\psi(t)$), deviation ($\theta(t)$), and low-$Re$ Leading-Edge Vortex (LEV) lift augmentation (references: TU Delft *DelFly Nimble*, *FlapSim*).
3. **Compliant-Joint & Flexible-Structure Airframes (`compliant_flex`)**
   - Distributed compliant unibody hinges and aeroelastic bending/torsion wings where deformation feeds aerodynamic incidence and fatigue (reference: TU Delft *DelFly Flex*).

---

## 2. Coordinate Frames, Kinematics & State Definitions

All variables conform strictly to [coordinates_and_units.md](fundamentals/coordinates_and_units.md) and `aeroforge_schemas.foundation.Frames`:

- **World frame (`local_right_handed_z_up`):** SI meters, $+Z$ up, gravity $g = 9.80665\text{ m/s}^2$.
- **Body frame (`right_handed_x_forward_y_left_z_up`):** $+X$ nose forward, $+Y$ left wingtip, $+Z$ dorsal up; body-to-world rotation stored as active unit Hamilton quaternion `(w, x, y, z)`.
- **Stroke plane frame (flapping wing):**
  - Stroke plane tilt angle $\beta \in [0, \pi/2]$ about $+Y_b$.
  - Instantaneous wing angles in stroke frame: stroke sweep $\phi(t)$ (half-amplitude $\Phi$, frequency $f$, angular frequency $\omega = 2\pi f$), deviation $\theta(t)$, and feathering / geometric pitch $\psi(t)$.
- **Relative airflow convention:** $\mathbf{v}_{\text{rel}} = \mathbf{v}_{\text{vehicle}} - \mathbf{v}_{\text{air}}$ in body/wing axes.

---

## 3. Governing Physical & Electromechanical Equations

### 3.1 Dimensionless Regimes & Envelope Gates
- **Strouhal number:** $St = \frac{f A}{U_\infty}$ where peak-to-peak stroke arc $A \approx 2 R \sin(\Phi)$. Bio-inspired cruising/propulsive efficiency peaks near $St \in [0.15, 0.45]$; hovering limits have $U_\infty \to 0$ with reference flapping tip speed $U_{\text{tip}} = \omega R \hat{r}_2$.
- **Reduced frequency:** $k = \frac{\omega \bar{c}}{2 U_{\text{ref}}}$. Quasi-steady approximations degrade above $k > 0.3$ without added-mass & wake-memory corrections.
- **Mach / Reynolds envelope:** $M_{\text{tip}} \le 0.25$ (incompressible flapping/morphing gate; higher $M$ refuses execution cleanly) and low-to-moderate Reynolds $Re = \frac{\rho U_{\text{ref}} \bar{c}}{\mu} \in [5\times 10^2, 5\times 10^5]$.

### 3.2 Flapping-Wing Quasi-Steady + Unsteady Aerodynamics
Per-strip blade element integration over normalized span $\hat{r} \in [r_0/R, 1]$ using wing radial moments $r_1, r_2, r_3$:
1. **Translational + LEV Suction Lift (Polhamus / Sane-Dickinson):**
   $$C_L(\alpha) = K_p \sin\alpha \cos^2\alpha + K_v \sin^2\alpha \cos\alpha + C_{L,0}, \qquad C_D(\alpha) = C_{D,0} + C_{D,\max}\sin^2\alpha$$
   capturing stalled high-AoA leading-edge vortex stabilization without unphysical steady linear blow-up.
2. **Rotational Circulation Lift:**
   $$L'_{\text{rot}}(r,t) = \rho U(r,t) \, \pi \left(\frac{3}{4} - \hat{x}_0\right) c(r)^2 \dot{\psi}(t)$$
3. **Unsteady Circulatory Lag (Theodorsen $C(k)$ & Wagner $\phi(\tau)$):**
   Harmonic circulation lag factor $C(k) = F(k) + i G(k) = \frac{H_1^{(2)}(k)}{H_1^{(2)}(k) + i H_0^{(2)}(k)}$ plus non-circulatory added-mass normal force $F'_{\text{am}} = \frac{\pi}{4}\rho c^2 (\ddot{h} + \dot{U}\sin\alpha)$.

### 3.3 Reflexive Morphing Aerodynamics
Span/tuck morph parameters $(u_{\text{wing}}, u_{\text{tail}})$ modulate planform area $S(u)$, span $b(u)$, aerodynamic center shift $\Delta x_{\text{ac}}(u)$, rolling moment from asymmetric dihedral/tuck ($C_{l_{\text{asym}}}$), and coupled yawing moment ($C_n$) for vertical-tail-free yaw damping and turbulence rejection.

### 3.4 Compliant Hinges & Flexible Wing Aeroelasticity
- **Euler-Bernoulli flexible beam:** $E I(y) \frac{\partial^4 w}{\partial y^4} + c_s \dot{w} + m'(y) \frac{\partial^2 w}{\partial t^2} = q_{\text{aero}}(y,t)$, fundamental bending frequency $f_1 = \frac{1.875^2}{2\pi}\sqrt{\frac{EI}{m' L^4}}$.
- **Failure gates (fail closed):**
  - Material strain / hinge stress exceeding endurance fatigue limit ($\sigma_{\text{max}} / S_e > 1$ or safety factor $< 1.25$).
  - Static torsional divergence $q \ge q_D$ or coupled bending-torsion flutter onset.
  - Flap actuator current / voltage sag / motor winding over-temperature ($> 95^\circ\text{C}$) using Phase 0's causal 2-RC Thevenin battery solver.

---

## 4. Collected & Registered Open Reference Datasets (`DEVELOPMENT`)

All datasets below retain their original publisher licenses and strictly hold `DEVELOPMENT` / `UNVALIDATED` status (never universal physical acceptance):

| ID | Dataset / Reference | License | What Is Staged Locally | What It Validates (Once P1 Opens) |
| --- | --- | --- | --- | --- |
| `delfly_flex_2026` | TU Delft DelFly Flex vs Nimble (`10.4121/eee88ebe-739b-4bff-bf4a-4dd248d91eeb.v1`) | `CC-BY-4.0` | `fig_9b_avg_forces_moments_flex_62_5.txt`, `nimble_62_5.txt`, `README.txt`, parsed `forces_moments_benchmark.json` | Compliant unibody vs rigid flapping force/moment symmetry & maneuver authority (`Hover`, `Pitch ±`, `Yaw ±`) |
| `pigeonbot` | Stanford/Groningen PigeonBot II (`10.5061/dryad.zkh1893h5`) | `CC0-1.0` | Exact `README.md`, `morph_matrix_manifest.json` (81 morph/AoA/reflex combinations × 3–21% TI%) | Rudderless morphing wing-tail Dutch-roll damping & turbulence response trends |
| `avian_inertia` | Bristol Calibrated-CT Avian Inertia (`10.5061/dryad.xsj3tx9gp`) | `CC0-1.0` | `calibration_curves.json` (`bo1` Barn Owl & `pf4` Peregrine Falcon CT density curves + PAI frames) | Segment inertia & center-of-mass sensitivity vs avian specimen data (never scaled as aircraft law) |
| `flapsim_single_thrust_flapper` | FlapSim 30g Flapper (`MingshanHe/FlapSim`) | `Apache-2.0` | `wing_parameters.json`, `robot.yaml`, `hover.yaml` | Quasi-steady flapping wing geometric moments ($r_{00..33}$) and 40 Hz hover force equilibrium |
| `avonet` | AVONET Bird Morphology (`10.6084/m9.figshare.16586228`) | `CC-BY-4.0` | Indexed cited-only manifest (21.5 MB `.xlsx` optional pack) | Species-level wing/hand-wing index morphological scaling sanity checks only |

---

## 5. Planned Phase 1 Execution Breakdown (`P1-001`..`P1-008`)

1. **`P1-001` (Owner gate):** Explicit authorization to transition from Contracts & Registries into full Phase 1 simulation & 3D workbench development.
2. **`P1-002` (Contracts & Datasets — interface work started cleanly now):** Versioned pydantic interfaces in `packages/shared-schemas/aeroforge_schemas/bioinspired.py` + `phase1_dataset_eval.py`.
3. **`P1-003` (Core Physics & C++20/Python Solvers):** Unsteady Theodorsen/LEV blade-element flapping solver, reflexive morphing stability derivatives, and compliant Euler-Bernoulli flexible beam + flutter checks with convergence verification.
4. **`P1-004` (Frozen Validation Protocols):** Lock predeclared error tolerances, cycle fatigue limits, and held-out experiment splits before confirmatory reveal.
5. **`P1-005` (Custodian Physical Receipts):** Independent wind-tunnel, load-cell, motion-capture, and battery telemetry acquisitions for target hardware.
6. **`P1-006` (Native Desktop 3D CAD & Flight Loop):** Articulated wing/feather morphing + real-time stroke animation in `apps/native/` without degrading prior Phase 0 multirotor/FW/heli/VTOL regressions (`59.9+ FPS` on Tier 1 laptops).
7. **`P1-007` (Joint Uncertainty & Envelope Scoring):** Held-out comparison with uncertainty bands (`Development` vs `Physical Match %`).
8. **`P1-008` (Independent Review & Release):** External qualified review & Phase 1 closure.
