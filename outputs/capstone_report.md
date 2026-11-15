# AeroForge capstone credibility report (M8)

**Design**: hexa_p80_60kg — 60.000 kg AUW, 6 rotors
**Elapsed**: 186.4 s

**All design goals passed: False**

- [PASS] G7_hover_in_measured_envelope
- [PASS] G1_hover_hold_stable
- [PASS] G2_climb_to_5m
- [PASS] G3_gentle_landing
- [PASS] G4_forward_maneuver
- [FAIL] G5_wind_gust_rejected
- [PASS] G6_motor_failure_outcome_recorded
- [PASS] G9_endurance_with_uncertainty
- [PASS] G8_structural_margin

## Endurance (Monte Carlo)
- best estimate 360 s (5-95 %: 240-420 s)

## V&V verdict
- needs further analysis: False

# AeroForge V&V Report

**Design**: hexa_p80_60kg — 60.000 kg, 6 rotors

**Verdict**: all gated metrics within tolerance

## Benchmarks
- [PASS] propulsion knot read-back (thrust + current) — max_relative_error=0, points_checked=42
- [REPORTED] static thrust cross-voltage scatter — scatter_pct=0
- [PASS] full-throttle table reproduction @ 47.9 V — thrust_rel_err_pct=0, current_rel_err_pct=0, power_rel_err_pct=0, rpm_rel_err_pct=0
- [REPORTED] lumped DC motor cross-check — 
- [PASS] hover trim equals weight — relative_error=1.93e-16

## Convergence
- [converged] time-step convergence (torque-free Euler dynamics) (tolerance 1e-06)
- [converged] adaptive solver tolerance (free fall) (tolerance 1e-08)
- [converged] closed-loop integrator convergence (takeoff scenario) (tolerance 0.002)

## Uncertainty (Monte Carlo)
- hover endurance (to 3.5 V/cell warning): best estimate 360 s (mean 352 s, std 47 s, 5–95 %: 297–420 s, n=40)
- sensitivities (endurance at parameter edges):
  - battery_capacity: 330 – 390 s (Δ 60 s)
  - battery_resistance: 420 – 240 s (Δ 180 s)
  - thrust: 330 – 390 s (Δ 60 s)
  - motor_mass: 360 – 360 s (Δ 0 s)

## Validated vs assumed
- **validated**: dynamics core (analytical solutions: free fall, spin-up, conservation laws); mass-property assembly (parallel-axis hand calculations); propulsion static table (manufacturer bench data, read-back gate); full-throttle chain reproduction
- **assumed/estimated**: rotor reaction torque k (derived from bench data with assumed eta=0.8); battery capacity/mass/IR (flagged estimates); propeller mass (flagged estimate); ESC rating (placeholder); airframe drag CdA (unsourced approximation); quasi-static bus solve; no thermal integration; no wind
