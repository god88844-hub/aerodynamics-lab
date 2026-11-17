# M27.9 — Explicit affine ADC calibration and held-out uncertainty propagation

`physics.validation.affine_adc_holdout.audit_affine_sensor_holdouts` screens frozen predictions against an **operator-declared** sensor conversion and bounded measurement errors, using whole-run groups rather than favorable pooled statistics.

The operator provides frozen model/protocol identities, a channel and explicit calibrated output unit (e.g. V), a declared nominal ADC scale per code and offset in that unit, absolute scale/offset/calibration residual hard uncertainties, nominal half-code quantization uncertainty, and an inclusive ADC code validity range. Integer raw codes outside that range or saturated samples cannot earn a passing run.

For code `c`, the inferred engineering quantity is `y=a*c+b`. A conservative value hard bound is `U=|c|*U_a + U_b + U_cal + (|a|+U_a)*q_half`; it includes a worst-case effect of scale uncertainty on quantization. The per-sample prediction residual bound is `|prediction-y|+U`. A prediction interval only robustly encloses the measurement if `lower <= y-U` and `upper >= y+U`. Each held-out run is checked separately against explicitly declared residual tolerance and coverage fraction. At least two distinct whole experimental groups are required; invalid numeric inputs, clipping, duplicate IDs, contradictory bounds, insufficient sampling and arithmetic overflow fail closed.

**No physical certification:** This module does *not* parse independently archived raw acquisition files, verify instrument calibration certificates, prove a sensor genuinely generated any supplied ADC codes, verify traceability to a national standard, or measure actual propeller/aircraft behavior. The affine assumption can be wrong due to temperature, drift, nonlinearity, hysteresis or correlated errors. All physical source, independence and flight approval fields remain false.

Synthetic-only gate: `python -m pytest tests/physics/test_affine_adc_holdout.py -q`. Actual experimental validation remains unresolved (issue #16).
