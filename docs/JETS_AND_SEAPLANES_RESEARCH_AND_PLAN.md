# Technical Research & Plan: Jets, High-Speed Aircraft & Seaplanes (+ Catalog Hardware Boundary)

## 1. Designer vs. Hardware Catalog Boundary (Owner Scope Lock)
Aerodynamics Lab strictly separates **user-invented airframe/aerodynamic parts** from **preloaded real hardware**:
- **Custom Designed / Invented in Aerodynamics Lab:** Fuselages, swept/transonic wings, morphing/flapping wings, custom propellers/blades, ducted shrouds, supersonic inlets/nozzles, twin-float/stepped seaplane hulls, and mounting harnesses.
- **Selected from Preloaded Catalog (`data/components/` + Native UI Picker):** Real motors (`T-Motor MN3508`, `Emax ECOII 2807`, `Coreless 7x20`, `70mm 12B EDF`), real LiPo batteries (`1S`–`12S`), ESCs, and micro-turbines (`KingTech K-45G4 45 N`, `JetCat P100-RX 100 N`). Users test whether their invented airframe works cleanly or overloads, overheats, surges, or stalls that hardware.
- **Human-Scale & Bio Human Wings (`Stage 2`):** Explicitly **deferred to future work** until reliable full-scale human-wing experimental data exists.

---

## 2. Jets & High-Speed / Compressible Aircraft (`Stage 3`)
1. **Compressibility Lift & Pitching Moment:**
   - **Prandtl-Glauert / Kármán-Tsien factor:** $\beta = \sqrt{1 - M^2}$ for $M < M_{\text{crit}}$:
     $$C_{L,c} = \frac{C_{L,0}}{\beta + \frac{M^2}{1+\beta}\frac{C_{L,0}}{2}}, \qquad \text{2D sweep theory: } M_{\perp} = M \cos\Lambda_{c/4}$$
2. **Transonic Wave Drag & Drag Divergence (Modified Korn Equation):**
   $$M_{DD} = \frac{\kappa_A}{\cos\Lambda_{c/4}} - \frac{t/c}{\cos^2\Lambda_{c/4}} - \frac{C_L}{10 \cos^3\Lambda_{c/4}}, \qquad \kappa_A \approx 0.87 \text{ (conventional NACA)}, \; 0.95 \text{ (supercritical)}$$
   $$M_{cr} \approx M_{DD} - 0.108, \qquad \Delta C_{D,\text{wave}} = 20 \, (M - M_{cr})^4 \quad (M > M_{cr})$$
3. **Brayton Cycle Turbojet / Micro-Turbine & EDF Thrust Lapse:**
   - Standard ISA stagnation pressure/temperature ratios $\theta_0 = \frac{T}{T_{\text{ref}}}(1 + \frac{\gamma-1}{2}M^2)$, $\delta_0 = \frac{P}{P_{\text{ref}}}(1 + \frac{\gamma-1}{2}M^2)^{\frac{\gamma}{\gamma-1}}$.
   - Net thrust lapse $F_n(M, h)$ & Exhaust Gas Temperature limit ($EGT \le EGT_{\max}$, e.g. $750^\circ\text{C}$ max turbine gate -> fail closed above limit).
4. **Open Reference Datasets Staged (`DEVELOPMENT`):**
   - `nasa_jet_m1p63_heated`: NASA Langley TMBWG Mach 1.63 heated nozzle temperature/velocity decay (`Exp_heated_tcl.dat`, `Exp_heated_ucl.dat`) & off-design shock-cell diamonds (`Exp_shock_tcl.dat`).
   - `nasa_tm4074_ladson_naca0012`: NASA TM-4074 high-$Re$ ($6\times 10^6$) experimental lift/drag polar (`CLCD_Ladson_expdata.dat`).

---

## 3. Seaplanes, Floatplanes & Amphibian Hulls (`Stage 1 / Hydrodynamics`)
1. **Savitsky (1964) Prismatic Planing Lift & Equilibrium:**
   - Beam speed coefficient $C_V = \frac{V}{\sqrt{g b}}$, wetted length ratio $\lambda = \frac{l_m}{b}$.
   - Zero-deadrise lift coefficient $C_{L0} = \tau^{1.1}\left(0.012\,\lambda^{0.5} + \frac{0.0055\,\lambda^{2.5}}{C_V^2}\right)$, deadrise correction $C_{L\beta} = C_{L0} - 0.0065\,\beta\,C_{L0}$.
   - Hydrodynamic dynamic lift $L_{\text{hydro}} = \frac{1}{2}\rho_{\text{water}} V^2 b^2 C_{L\beta}$, ITTC-57 skin friction $C_F = \frac{0.075}{(\log_{10} Re_w - 2)^2}$, induced pressure drag $L_{\text{hydro}}\tan\tau$.
2. **NACA Displacement-to-Planing Hump Resistance ($Fn_L \approx 0.45$):**
   - Total takeoff hump resistance $R_{\text{hump}}$ peaks near $V_{\text{hump}} \approx 0.45\sqrt{g L_{\text{hull}}}$ plus wave/spray roughness drag.
   - **Fail-closed takeoff gates:** Reserve Archimedes buoyancy $\ge 1.80\times$ weight when floating at rest; available installed thrust must satisfy $T_{\text{avail}} > 1.15\,R_{\text{hump}}$ or predict `FAIL: Stuck behind water hump speed`.
3. **Open Reference Benchmark Staged (`DEVELOPMENT`):**
   - `savitsky_1964_planing`: Exact Savitsky 1964 SNAME worked validation point ($b=3.20\text{ m}, \beta=18^\circ, \tau=4.0^\circ, \lambda=1.718, V=15.43\text{ m/s} \Rightarrow C_V=2.754, C_{L0}=0.0850, C_{L\beta}=0.0751, L=73.1\text{ kN}$).
