# Phase 3 & Phase 4 Deepening Specification: Real NASA Telemetry, Afterburners, Ramjets, Airliner Cabin Stress & Ascent Profiles

All benchmark tables retain `DEVELOPMENT` status (`reconcile_registry.py` / `ACCEPTANCE_LEDGER.md`), while custom airframes retain `UNVALIDATED_CUSTOM`.

## 1. Real Online NASA / Industry Datasets Pinned
1. **NASA Common Research Model (`nasa_crm_transonic`):**
   - Cruise $M_\infty = 0.85$, design $C_L = 0.50$, altitude $\approx 12,500\text{ m}$ ($41,000\text{ ft}$), target cruise $L/D \in [16, 20]$ (AIAA Drag Prediction Workshop standard).
   - Paired with fuselage cabin pressurization hoop stress check ($\sigma_{\text{hoop}} = \frac{\Delta P \cdot R}{t_{\text{skin}}}$) at high altitude.
2. **GE J85-GE-13 & Pratt & Whitney F100-PW-229 (`nasa_j85_f100_propulsion`):**
   - **J85-GE-13:** Single-spool turbojet; Dry $12.1\text{ kN}$ ($\text{TSFC } 1.26$), Afterburner $18.1\text{ kN}$ ($\text{TSFC } 2.22$), $\dot{m} \approx 20.0\text{ kg/s}$, $\text{OPR } 6.8:1$.
   - **F100-PW-229:** Low-bypass turbofan ($\text{BPR } 0.36$); Dry $79.2\text{ kN}$ ($\text{TSFC } 0.73$), Afterburner $129.7\text{ kN}$ ($\text{TSFC } 2.06$), $\dot{m} \approx 113.5\text{ kg/s}$, $\text{OPR } 32.4:1$.
   - **Mach 2–6 Aerothermal Skin Heating & Ramjet/Scramjet:**
     - Adiabatic wall recovery temperature: $T_{\text{aw}} = T_\infty\!\left(1 + r\frac{\gamma - 1}{2} M^2\right)$, $r \approx 0.89$ (turbulent).
     - Afterburner wet thrust multiplier ($1.50\text{–}1.64\times$) + TSFC penalty, plus Mach $> 2.0$ Ramjet/Scramjet specific impulse transition.
3. **NASA X-15A-2 Flight 188 & Space Shuttle STS Re-entry (`nasa_x15_and_sts_reentry`):**
   - **X-15A-2 Flight 188 (Oct 3, 1967):** Mach $6.70$, altitude $31.12\text{ km}$, MA-25S ablator + Inconel-X, shock-on-shock ventral spike $\approx 1,480^\circ\text{C}$ ($2,700^\circ\text{F}$).
   - **Space Shuttle STS Re-entry:** Peak heating near Mach $23.8$ ($\approx 7.40\text{ km/s}$) at $72.5\text{ km}$, Reinforced Carbon-Carbon (RCC) nosecap limit $\approx 1,650^\circ\text{C}$.
4. **NASA Saturn V AS-501 / Apollo 11 SA-506 Staging (`nasa_saturn_v_staging`):**
   - **S-IC:** Dry $131,000\text{ kg}$, Propellant $2,169,000\text{ kg}$, $I_{sp,\text{SL}} = 263\text{ s}$ / $I_{sp,\text{vac}} = 304\text{ s}$.
   - **S-II:** Dry $36,500\text{ kg}$, Propellant $443,000\text{ kg}$, $I_{sp,\text{vac}} = 421\text{ s}$.
   - **S-IVB:** Dry $13,500\text{ kg}$, Propellant $109,000\text{ kg}$, $I_{sp,\text{vac}} = 421\text{ s}$ (LEO parking $\approx 7.8\text{ km/s}$ & TLI $\approx 11.2\text{ km/s}$).

## 2. Coupled Weather, Electronics & 10-Case Interactive Failure Atlas
- Upper-level launch wind + turbulence gust load factor ($q_{\text{max}} \cdot (1 + 0.5\text{ turb})$) and side-load structural FoS directly gate Rocket launch readiness %, alongside Stage 1/2 TPS wall temp, Liftoff $T/W$, and bolt/wiring safety.
- Expanded `Failure Atlas` modal covers all **10 interactive 1-click scenarios** inside `AerodynamicsLab.exe` (`#8 Helicopter VRS Descent`, `#9 X-15 Mach 6.7 Skin Thermal Burn`, `#10 Rocket Launch Underweight / Wind-Shear Abort`).
