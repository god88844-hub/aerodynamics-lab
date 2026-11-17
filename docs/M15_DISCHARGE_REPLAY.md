# M15 — Battery Discharge Trace Replay and Measured Energy Ledger

## Why this matters

AeroForge's goal is to approach real-world predictive reliability **inside independently validated operating envelopes**, not to pretend simplified simulation is a physical test. A major gap in the M9 evidence audit is discharge-voltage and usable-capacity behavior of the actual flight battery at mission C rates. M12 fits a single resistance to isolated operator-supplied samples. M15 adds a separate, read-only **time-series comparison** of a full discharge current/voltage trace to the *unchanged* battery model.

**Crucial distinction:** the replay is *conditioned on the actual observed load current*. It tests voltage-model consistency and integrates measured delivered energy, but does **not** independently predict current demanded by a drone, unobserved capacity or aircraft endurance. Without traceable independent physical measurements it remains synthetic software verification only.

## Endpoint

`POST /api/components/discharge-replay`

Request structure (illustrative **synthetic formatting values, NOT observations**):

```json
{
  "battery_id": "generic_6s_lipo_16000mah",
  "dataset_kind": "synthetic_fixture",
  "battery_serial_or_id": "synthetic-math-battery",
  "run_id": "synthetic-comparison-run",
  "data_source": "synthetic input for programmatic verification only",
  "model_unused_for_calibration": true,
  "hardware_matches_reference_spec": false,
  "initial_soc_pct": 100,
  "predeclared_max_abs_voltage_error_v": 0.5,
  "predeclared_max_endpoint_time_error_pct": 5,
  "predeclared_max_sample_gap_s": 60,
  "samples": [
    {"t_s": 0, "current_a": 5, "terminal_voltage_v": 24, "temperature_c": 25},
    {"t_s": 30, "current_a": 5, "terminal_voltage_v": 23.9, "temperature_c": 25},
    {"t_s": 60, "current_a": 5, "terminal_voltage_v": 23.8, "temperature_c": 25},
    {"t_s": 90, "current_a": 5, "terminal_voltage_v": 23.7, "temperature_c": 25},
    {"t_s": 120, "current_a": 5, "terminal_voltage_v": 23.6, "temperature_c": 25},
    {"t_s": 150, "current_a": 5, "terminal_voltage_v": 23.5, "temperature_c": 25}
  ]
}
```

Do not mark synthetic inputs `physical_measurements`. For actual measurements, preserve the original logs and metadata about current/voltage sensor calibration, timestamp reference, pack temperature, charge process, battery age, chemistry, cell count, and initial SOC method. Evidence provenance, independent-run status and hardware identity are **self-declared only**.

### Methods

- Samples have strictly increasing timestamps from t=0; six or more samples and one positive load-current value are required.
- Trapezoidal integration of measured current computes consumed amp-hours. Trapezoidal integration of measured current multiplied by terminal voltage computes delivered watt-hours. Both depend on signal quality, measurement bandwidth and sampling cadence.
- The existing `BatteryPack` is run at the declared initial SOC, decrementing SOC using **measured** integrated current and the component's unchanged nominal capacity. The existing OCV(SOC) and pack R predict terminal voltage under the measured current. Missing R, SOC outside the OCV curve and excessive predicted sag block the operation.
- Compute voltage MAE, RMSE, bias, worst absolute error.
- Determine the first falling **warning-voltage** crossing in each trace using linear interpolation between adjacent recorded samples. Report crossing times and relative percentage error only when both crossing times occur within the supplied trace and measured time is >0. This is a conditional trace comparison, not an independently predicted mission-endurance time.
- The maximum observed C rate is compared with the pack's stated rating. Unknown ratings block a positive reported verdict.
- Sample gaps beyond the *predeclared* maximum block a positive reported verdict. Voltage and warning-time error criteria are independently predeclared.
- Any numerical pass using **synthetic data** is `SYNTHETIC_VERIFICATION_ONLY`. A physical operator-labelled match remains `REPORTED_DISCHARGE_TOLERANCES_MET_NOT_INDEPENDENTLY_AUTHENTICATED` at best. Generic or estimated pack parameters cannot earn that verdict, even when traces agree.
- The report is ephemeral. No raw log is persisted and no component, control law, battery parameter, design or flight prediction is changed.

### Scientific limitations and acceptance gates

True physical-validation equivalence **has not been achieved**. This milestone does not model temperature-sensitive resistance and capacity, rate-capacity derating, cell imbalance, cycle aging, thermal runaway, sensor uncertainty or transient ESC loads. The default 6S/12S batteries are *generic* models with explicit estimated attributes. A near-equality claim requires validated pack-specific parameterization, independent unaltered discharge logs under mission currents, multiple temperatures/ages/charge histories, uncertainty budgets and evidence of model generalization. Electrical measurement error must be bounded separately. Independent external review is required before decisions about airworthiness or safety.

Tests are synthetic unit/API/UI verification only and are not evidence of a real battery's endurance.

## Verification commands

```bash
python -m pytest tests/physics/test_discharge_replay.py tests/integration/test_discharge_replay_api.py -q
python -m pytest -q
cd apps/web
npm ci
npm audit --audit-level=moderate
npm run build
npm test
```
