# Multiphysics, CAD Motion, & Phase 4 Rocket/Hypersonic Research Specification

All models documented here follow the repository governance policy: preloaded analytical/textbook benchmarks carry `DEVELOPMENT` status until sealed physical telemetry passes independent review (`P0*/P3*/P4*` external gates), custom/invented vehicles carry `UNVALIDATED_CUSTOM`, and **human bio-wings / Leonardo da Vinci ornithopter concepts remain deferred in Phase 2 (`P2-001..008`)** until uncrewed & aerospace scopes are complete.

## 1. CAD Parity: Exploded View & Assembly Motion Study
- **Exploded View (`explode_factor` $\in [0, 1.5]$):**
  - Each sub-assembly / part (`AssemblyPartSummary`) carries an assembly vector from the vehicle's body origin (radial along arms/wings/floats, axial along nose/fuselage/tail/cable).
  - Visual vertices of non-root parts translate cleanly by $\Delta \vec{p}_i = e \cdot \vec{d}_i$, accompanied by dashed explosion guide trace lines (`wake_lines` / dashed orange-gray trace segments) connecting each displaced part back to its mounting datum.
- **Assembly Motion Study (`motion_study_active`, `motion_study_time_s`):**
  - Continuous multi-mechanism kinematic timeline driving:
    - Spinning rotors & counter-rotating propellers ($\theta = \omega t$)
    - VTOL nacelle tilt sweep ($\delta_{\text{tilt}}(t)$), Tailsitter transition pitch ($\theta_p(t)$)
    - Deflecting ailerons/elevons/flaps & rudder
    - Flapping insect wingbeat stroke + Morphing-wing tuck sweep + Cargo cable pendulum swing
    - Rocket stage-separation animation at staging $t$
- **Visual Stress / CFD Field & Wire-Mesh Overlays (`ShadingMode`):**
  - **Von Mises Structural Stress Contour:** Analytic bending/torsion/tensile $\sigma/\sigma_y$ colormap rendered directly onto triangles (`blue` low stress $\to$ `amber` yield warning $\to$ `red` $>0.8 \sigma_y$).
  - **3D Potential/Helical Airflow Streamlines & CFD Flow Ribbons:** Velocity-aligned streamline ribbons sweeping over wings, through rotor downwash tubes, and around rocket fairings (plus contract bridge for external OpenFOAM / SU2 / CalculiX JSON case export).

## 2. Missing Multiphysics Pillars (C++20 `lab_core` + Python)
1. **Aeroacoustics & Sonic Boom:**
   - **Rotor Blade-Passage Frequency (BPF) & Gutin/Lowson Loading SPL (dB(A) @ $R$):**
     $$f_{\text{BPF}} = \frac{N_b \cdot \text{RPM}}{60}, \quad \text{SPL}_{\text{total}} = 10\log_{10}\!\left(N_{\text{rot}} \cdot 10^{0.1 \cdot \text{SPL}_1}\right)$$
     scaled with tip Mach $M_{\text{tip}}$ and thrust $T$, with dipole distance attenuation $20\log_{10}(R / 15\text{ m})$.
   - **Jet Mixing Noise (Stone / Lighthill $v_e^8$ scaling):** High-subsonic/supersonic plume OASPL at 30 m.
   - **Supersonic Sonic Boom Overpressure ($\Delta P_{\text{boom}}$, Pa & psf):** Simplified Carlson/Whitham $N$-wave approximation when $M > 1.02$:
     $$\Delta P_{\text{boom}} \approx K_r K_s P_{\text{atm}}^{0.5} (M^2 - 1)^{1/8} \left(\frac{L}{h^{3/4}}\right) \left(\frac{d_{\text{eq}}}{L}\right)$$
2. **Helicopter High-Speed & Vortex Ring State (VRS) / Gyroscopic Precession:**
   - Advance ratio $\mu = V / (\Omega R)$: advancing tip Mach $M_{\text{adv}} = M_{\text{tip}}(1 + \mu)$ ($\le 0.90$ limit), retreating stall boundary when $\mu > 0.42$ at high disk loading.
   - **Vortex Ring State (VRS):** Suspected onset inside $v_z / v_h \in [-1.2, -0.35]$ when horizontal airspeed $|V_{xy}| < 0.70\, v_h$ ($v_h = \sqrt{T / (2\rho A)}$).
   - **Gyroscopic Precession Torque:** $\tau_{\text{prec}} = I_{\text{rotor}} \Omega \dot{\theta}_{\text{rate}}$ producing 90° phase pitch/roll cross-coupling.
3. **Marine / Seaplane Propeller & Foil Cavitation ($\sigma$):**
   - Cavitation number $\sigma = \frac{P_{\text{atm}} + \rho_w g h - P_v(T)}{0.5 \rho_w V_{\text{tip}}^2}$; inception / FAIL when $\sigma < 0.35$.
4. **Electromagnetics, RF Link Budget & Faceted Stealth Radar Cross-Section (RCS):**
   - **Friis Telemetry / Link Margin (dB):** $P_{rx} = P_{tx} + G_{tx} + G_{rx} - (32.44 + 20\log_{10} f_{\text{MHz}} + 20\log_{10} d_{\text{km}}) - L_{\text{rain}}$ (ITU-R P.838 rain fade + thermal/EMI margin).
   - **Physical-Optics Triangle Facet RCS (dBsm):** Coherent/incoherent radar backscatter estimate across oriented surface normals vs incoming wave vector at X-band ($10\text{ GHz}$), demonstrating shaping/sweep scatter reduction vs blunt flat plates.
5. **Atmospheric Microburst Downburst & GPS Multipath Sensors:**
   - Axisymmetric Oseguera-Bowles microburst downflow/outflow radial-vertical wind shear field feeding disturbance checks.
   - Urban canyon **GPS multipath error** ($m$) + optical camera barrel/radial distortion model (`SYNTHETIC` provenance).

## 3. Phase 4 — Rockets, Spacecraft & Hypersonics (`P4-002`, `P4-003`, `P4-006`)
1. **Multi-Stage Tsiolkovsky Rocket Equation:**
   $$\Delta v_{\text{stage}} = I_{\text{sp}} g_0 \ln\!\left(\frac{m_{0,k}}{m_{f,k}}\right) - \Delta v_{\text{grav}} - \Delta v_{\text{drag}}, \quad m_{f,k} = m_{0,k} - m_{\text{prop},k}$$
2. **Gravity-Turn Ascent & Max-Q:** Dynamic pressure $q = \frac{1}{2}\rho(h) V^2$, max-$q$ structural/fairing load check, and Karman-line altitude ($100\text{ km}$) / LEO orbital velocity ($v_{\text{orb}} = \sqrt{\mu_\oplus / (R_\oplus + h)} \approx 7.8\text{ km/s}$).
3. **Hypersonic Aerothermodynamics & Rarefied Gas:**
   - **Sutton-Graves Convective Heat Flux:** $\dot{q}_c = k_{SG} \sqrt{\frac{\rho}{r_n}} V^3$ (Earth $k_{SG} = 1.7415 \times 10^{-4}\ \text{W}\cdot\text{m}^{-2}/(\text{kg}^{1/2}\text{m}^{-3/2}\text{s}^{-3})$) with TPS radiative equilibrium surface temperature $T_w = (\dot{q}_c / (\epsilon \sigma_{SB}))^{1/4}$.
   - **Knudsen Number:** $Kn = \lambda(h) / L_{\text{ref}}$ distinguishing continuum ($Kn < 0.01$), slip ($0.01 \le Kn < 0.1$), transitional, and free-molecular rarefied upper atmosphere.
4. **Local CFD / FEA Case Exporter & Analytical Field Mesh:**
   - Builds valid `openfoam_rans` (`blockMeshDict`/`U`/`p` summary) and `calculix_fea` (`.inp` deck summary) working directories, executes external CLI solver if installed on PATH or falls back cleanly with deterministic analytical 3D velocity streamlines & Euler-Bernoulli Von Mises fields (explicitly tagged `ANALYTICAL_FIELD_PROXY` vs external solver execution).
