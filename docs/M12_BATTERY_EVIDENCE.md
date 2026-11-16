# M12 — Battery Discharge Evidence Laboratory

## Purpose

AeroForge's existing first-order pack model uses a generic chemistry OCV(SOC)
curve and constant pack resistance. That is not enough to establish accurate
high-C endurance on any particular real battery, particularly at different
temperatures, states of health or aging. **M12 does not guess those missing
characteristics or retrofit optimistic results.**

This feature accepts *user-supplied* pack terminal voltage, current and SOC
points from a declared calibration run and a **separate held-out run**. It
estimates a single `R_pack` by ordinary least squares, holding the existing
OCV curve fixed, then scores only the held-out observations. The database's
battery specification, flight solver and existing endurance results are not
modified.

## API

`POST /api/components/battery-evidence`

Request:
```json
{
  "battery_id": "generic_6s_lipo_16000mah",
  "dataset_kind": "physical_measurements",
  "calibration_run_id": "documented-run-A",
  "heldout_run_id": "documented-run-B",
  "calibration_source": "measurement log A and instrument calibration reference",
  "heldout_source": "independent measurement log B and instrument calibration reference",
  "predeclared_max_abs_percentage_error_pct": 5,
  "samples": [
    {"id": "A01", "split": "calibration", "soc_pct": 40, "current_a": 20, "terminal_voltage_v": 23.0, "temperature_c": 25},
    {"id": "A02", "split": "calibration", "soc_pct": 50, "current_a": 30, "terminal_voltage_v": 22.8, "temperature_c": 25},
    {"id": "A03", "split": "calibration", "soc_pct": 60, "current_a": 40, "terminal_voltage_v": 22.4, "temperature_c": 25},
    {"id": "B01", "split": "held_out", "soc_pct": 45, "current_a": 25, "terminal_voltage_v": 22.9, "temperature_c": 25},
    {"id": "B02", "split": "held_out", "soc_pct": 55, "current_a": 35, "terminal_voltage_v": 22.6, "temperature_c": 25}
  ]
}
```

**These numbers are arbitrary illustrative request-format values, not real
bench observations. Never submit them as physical measurements.** When
experimenting with generated data, explicitly set `dataset_kind:
"synthetic_fixture"`. This always returns `SYNTHETIC_VERIFICATION_ONLY`.

## Method and checks

1. All observations are validated: finite positive current and voltage,
   SOC between 0 and 100, unique IDs, at least 3 calibration points at
   multiple currents and at least 2 held-out points. Disjoint *reported*
   run IDs and provenance strings are required. Unknown battery IDs return
   404; malformed evidence returns 422.
2. The calibration minimizes `sum((OCV_pack(SOC) - I * R - V_measured)^2)`
   with one constrained physical parameter `R > 0`. It does not fit an
   OCV offset, battery capacity, temperature correction or aging curve.
3. Held-out data have per-sample predictions and residuals, MAE, RMSE,
   voltage MAPE and maximum absolute percentage error. The separately
   declared current/SOC calibration envelope is reported.
4. The tolerance is **predeclared** by the operator. Exceedance or
   unrepresented currents/SOC are reported, not converted to a high success
   probability. C-rates are reported and compared with nominal rating when
   available. The generic reference battery resistance is scored on held-out
   data separately if the requested voltage is inside the first-order
   model's voltage-sag envelope.
5. Some measured temperatures may be recorded; no thermal or rate-dependent
   capacity correction is implied. No empirical physical validation label is
   issued automatically, even when an operator declares the inputs measured.
6. Requests do not store sensitive bench logs or mutate existing simulations.
   Users must archive their raw datasets, calibration certificates and
   provenance outside this temporary analysis endpoint.

## Why held-out data matters

A model that repeats its input calibration rows is *verified for algebra*,
not validated for predictive engineering. A separately measured run allows
assessment of generalization error for that named pack and test conditions.
Run IDs and provenance are self-declared and **not independently authenticated
by AeroForge**. Correlated samples from one original run cannot be made truly
independent by changing labels.

The calibration/holdout split is assessed, but a single pack across a
narrow SOC/current/temperature envelope does **not** establish reliable
endurance prediction for a multi-rotor aircraft under maneuver loading.
The main physical evidence gap remains separately measured pack discharge
and temperature behavior under relevant C-rates.

## Tests

```bash
python -m pytest tests/physics/test_battery_evidence.py tests/integration/test_api.py -q
python -m pytest -q
cd apps/web
npm ci
npm audit --audit-level=moderate
npm run build
npm test
```

The mathematical unit fixtures are explicitly *synthetic*, not independent
physical experiments. Browser CSV entry and result display still require
separate manual acceptance before claiming that every UI workflow works.
