# AeroForge V&V Report

**Design**: quad_mn3508_6s_15x5 — 3.708 kg, 4 rotors

**Verdict**: all gated metrics within tolerance

## Benchmarks
- [PASS] propulsion knot read-back (thrust + current) — max_relative_error=1.21e-16, points_checked=20
- [PASS] static thrust cross-voltage scatter — scatter_pct=3.89
- [PASS] full-throttle table reproduction @ 14.8 V — thrust_rel_err_pct=0, current_rel_err_pct=0, power_rel_err_pct=0, rpm_rel_err_pct=0
- [REPORTED] lumped DC motor cross-check (cal 14.8 V -> val 22.2 V) — ke_eff_v_s_per_rad=0.0232, r_eff_ohm=0.436, current_rmse_a=2.13, current_max_abs_err_a=4.68, current_max_rel_err_pct=35.2
- [PASS] hover trim equals weight — relative_error=1.95e-16

## Convergence
- [converged] time-step convergence (torque-free Euler dynamics) (tolerance 1e-06)
- [converged] adaptive solver tolerance (free fall) (tolerance 1e-08)
- [converged] closed-loop integrator convergence (takeoff scenario) (tolerance 0.002)

## Uncertainty (Monte Carlo)
- hover endurance (to 3.5 V/cell warning): best estimate 3870 s (mean 3854 s, std 240 s, 5–95 %: 3480–4230 s, n=200)
- sensitivities (endurance at parameter edges):
  - battery_capacity: 3480 – 4260 s (Δ 780 s)
  - battery_resistance: 3960 – 3750 s (Δ 210 s)
  - thrust: 3780 – 3930 s (Δ 150 s)
  - motor_mass: 3870 – 3870 s (Δ 0 s)

## Validated vs assumed
- **validated**: dynamics core (analytical solutions: free fall, spin-up, conservation laws); mass-property assembly (parallel-axis hand calculations); propulsion static table (manufacturer bench data, read-back gate); full-throttle chain reproduction
- **assumed/estimated**: rotor reaction torque k (derived from bench data with assumed eta=0.8); battery capacity/mass/IR (flagged estimates); propeller mass (flagged estimate); ESC rating (placeholder); airframe drag CdA (unsourced approximation); quasi-static bus solve; no thermal integration; no wind
