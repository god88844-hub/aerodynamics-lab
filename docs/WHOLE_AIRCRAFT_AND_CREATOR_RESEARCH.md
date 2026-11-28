# Whole-Aircraft Engineering, Creator Experimental Archetypes & Failure Atlas Research

This document consolidates the verified engineering research, open standards, creator/university experimental flight archetypes (`@NicholasRehm`, `@Project-Air`, `@Jays_rcgarage`, `@michaelrechtin`, MIT/TU Delft micro UAVs), standard parts/fastener tables, coupled subsystem math, failure atlas cases, real sound-barrier visuals, and virtual/USB RC controller design before planning edits and implementation.

---

## 1. Product Separation: Aerodynamics Lab vs. Electrophysics Lab
- **Electrophysics Lab** owns IC/semiconductor chips, digital logic, PCB trace routing/thermal analysis, ESC FET schematics, and cell-level battery electrochemistry.
- **Aerodynamics Lab** owns **flight-system electrical integration** (pack `OCV(SOC)`, `R0`, `Ah`, C-rate, thermal limit, AWG wiring harness losses) via a versioned exchange bridge ([electrophysics_powerpack_contract.json](../data/research/electrophysics_powerpack_contract.json)), **plus complete coupled propulsion & mechanisms** (motors, turbines, EDFs, compressors, intakes, nozzles, propellers, control linkages, gears, and fasteners).
- **One Unified CAD Assembly Workbench:** Build from scratch or start from any template; select certified off-the-shelf catalog parts OR unlock custom edits constrained by physical conservation laws (tagged honestly as `UNVALIDATED_CUSTOM`).

---

## 2. Standard Parts & Fasteners Data (`data/components/`)
Publicly standardized ISO/DIN/AWG/vendor engineering data collected and staged:
- **ISO 4762 / DIN 912 Metric Screws (`M2..M6`, Grade 12.9 Alloy Steel & Ti-6Al-4V Grade 5):**
  - E.g. `M3x12 (12.9)`: stress area $5.03\text{ mm}^2$, min tensile break $6,140\text{ N}$, shear capacity $\approx 3,620\text{ N}$, mass $1.00\text{ g}$, tightening torque $2.20\text{ Nm}$; Ti-6Al-4V saves ~43% mass ($0.57\text{ g}$).
  - See [iso_4762_metric_screws.json](../data/components/fasteners/iso_4762_metric_screws.json).
- **Bearings, Servos & Silicone AWG Wiring (`AWG 10..22`):**
  - `MR105ZZ` ($5\times 10\times 4\text{ mm}, 1.3\text{ g}, C_r=475\text{ N}$) & `608ZZ` ($8\times 22\times 7\text{ mm}, 12\text{ g}, C_r=3,350\text{ N}$).
  - `SG90` ($9\text{ g}, 0.157\text{ Nm}$), `MG90S` ($13.4\text{ g}, 0.216\text{ Nm}$), `DS3218` ($60\text{ g}, 2.11\text{ Nm}$).
  - `AWG 10..22` exact cross-section $\text{mm}^2$, resistance $\Omega/\text{m}$ (`3.3 mOhm/m` @ 10 AWG to `55.2 mOhm/m` @ 22 AWG), mass/m, and ampacity.
- **Micro-Turbines & EDFs:**
  - `KingTech K45G4+`: $44.1\text{ N}$, $232,000\text{ RPM}$, $150\text{ g/min}$ fuel, $720^\circ\text{C}$ EGT limit, $450\text{ g}$.
  - `JetCat P100-RX`: $100\text{ N}$, $153,000\text{ RPM}$, $312\text{ g/min}$ fuel, $730^\circ\text{C}$ EGT limit, $1,080\text{ g}$.
  - `FMS 70mm 12-Blade 6S EDF`: $21.58\text{ N}$, $68\text{ A}$ @ $22.2\text{ V}$ ($1,510\text{ W}$), $242\text{ g}$, blade $Re \approx 45,000$.

---

## 3. Whole-Aircraft & Creator Experimental Vehicle Archetypes

### A. Cargo & Slung-Load Package Carriers (`@Jays_rcgarage` / Commercial Delivery UAVs)
- **Pendulum Dynamics:** Suspended cable length $L$ adds natural swing frequency $\omega_p = \sqrt{g/L}$ and unactuated under-slung DoF.
- **Bluff-Body Cargo Box Drag & Blowback:** Rectangular packages exhibit $C_d \in [1.0, 2.1]$, generating trailing blowback $F_D = \frac{1}{2}\rho v_{\text{rel}}^2 C_d A$ and vortex shedding lateral oscillations at higher cruise speeds.
- **Off-CG Attachment Torque & Payload Drop:** Tether offset creates coupling torque $\boldsymbol{\tau} = \mathbf{r}_{\text{attach}} \times \mathbf{F}_{\text{cable}}$; releasing a parcel triggers an instantaneous step change in mass, $T/W$, and CG shift that autopilot loops must survive without attitude flip.

### B. VTOL Tailsitters & Thrust-Vectoring Flyers (`@NicholasRehm` / `dRehmFlight`)
- Hover vertically on prop(s), pitch smoothly through high-$\alpha$ post-stall transition into horizontal wing-borne cruise.
- Control authority during hover depends on **propwash slipstream** over elevons:
  $$V_{\text{slip}} = \sqrt{V_\infty^2 + \frac{2\,T}{\rho\,A_{\text{disk}}}}$$
  coupled with thrust-vectoring gimbal pitch/yaw deflection. Fail closed if hover $T/W < 1.10$ or control pitching moment cannot balance aero-pivot torque during mid-transition.

### C. Sub-100g Micro Flyers, Ducted/Shrouded Drones & Flying Wings (`@michaelrechtin`, `@Project-Air`, MIT)
- **Low-$Re$ Laminar Separation ($Re \approx 20,000\text{--}100,000$):** Sharp $C_d$ rise and $C_{L,\max}$ loss unless cambered/thin low-$Re$ profiles are used.
- **Ducted Fan / Shroud Lip Suction:** Area diffusion ratio $\sigma_d = A_{\text{exit}}/A_{\text{rotor}}$ raises static figure-of-merit thrust up to $\sqrt{2\,\sigma_d}$ while introducing lip pitching moment in crosswind.
- **Flying Wings / Blended-Wing-Bodies:** Require swept tips + reflex camber ($C_{m,0} > 0$) + washout twist so pitching-moment derivative $C_{m_\alpha} < 0$ remains longitudinally stable without a tailplane.

### D. Coupled Whole-Aircraft Jet Subsystems (`Phase 3` — `@Project-Air` / Supersonic Aero)
Every part connected to the engine is parameterized and coupled:
1. **Inlet Recovery (`MIL-E-5008B`):** Subsonic $\eta_r \approx 0.97\text{--}1.0$; supersonic $\eta_r(M_0) = 1 - 0.075\,(M_0 - 1)^{1.35}$ (accounts for oblique/normal shock total pressure loss) + spillage drag when capture area exceeds engine mass flow.
2. **Choked Nozzle Flow & C-D Expansion:**
   $$\dot{m}_{\text{choked}} = \frac{A^* P_t}{\sqrt{T_t}}\sqrt{\frac{\gamma}{R}}\left(\frac{2}{\gamma+1}\right)^{\frac{\gamma+1}{2(\gamma-1)}}, \qquad F_{\text{net}} = \dot{m} V_e + (P_e - P_a) A_e - \dot{m} V_0$$
3. **Fuel Tank Placement & Burn CoG Shift:** Fuel mass fraction drops continuously during mission burn, updating total weight, inertia $I_{yy}$, and trim AoA.

---

## 4. Real Visual Physics Effects & Virtual + USB RC Controller
- **Sound Barrier & Compressible Visuals (OpenGL 3.3 Core):** Exact **Mach Shock Cone** at $\mu = \arcsin(1/M)$ + **Prandtl–Glauert condensation disk** for $M \ge 0.95$, steepened shock $C_p$ contour across upper wing, and **supersonic exhaust shock diamonds** spaced along nozzle exit scaled from `nasa_jet_m1p63_heated`.
- **Real Mechanisms:** Spinning blades/rotors proportional to RPM, visible wing upward flex bending $w(y)$ from Euler-Bernoulli load, deflecting ailerons/elevators/rudders driven by control commands, seaplane float wake/spray, and red/amber overload highlighting.
- **Virtual & USB RC Transmitter (`dRehmFlight` / `ELRS` Style):** Interactive dual-stick on-screen RC HUD (`Throttle/Yaw`, `Pitch/Roll`, `Flaps/Gear/Mode` switches, live telemetry readouts) plus GLFW USB HID joystick/gamepad input directly driving closed-loop flight stabilization and payload release!

---

## 5. Failure Atlas
All 10 structured historical & physical failure archetypes are saved in [failure_atlas.json](../data/failure_examples/failure_atlas.json) covering battery collapse, QDrone sag, UAV-FD motor/ESC faults, CFRP buckling + bolt shear, slung cargo blowback, jet surge/EGT limit, tailsitter propwash stall, seaplane hump lock, insect fatigue/tip-Mach failure, and icing stall.
