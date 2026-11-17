# M18 — Independent Static Motor+Propeller Evidence

AeroForge's highest available static propulsion fidelity is manufacturer-bench-table interpolation. **The bench table is calibration data, not independent validation.** M18 compares externally supplied measured RPM, supply voltage, thrust and electrical current against *frozen* predictions from that model, without changing the model. It fills the second major missing evidence workflow identified by `docs/audit/M9_AUDIT.md`.

## Endpoint and UI

`POST /api/components/propulsion-evidence` and the **Static propulsion evidence lab** section in the editor. Select the existing design's motor and matching propeller. Submit at least five distinct RPM points in CSV columns `id,rpm,voltage_v,thrust_gf,current_a`, along with a bench run ID, source, instrument/fixture description, declared motor+prop hardware match, a declaration that no observation was used for calibration, and **predeclared** worst-error tolerances for thrust and current. Choose either `physical_measurements` or `synthetic_fixture`; synthetic samples always produce `SYNTHETIC_VERIFICATION_ONLY`.

Illustrative JSON *format only*, no claim of real measurements:

```json
{
  "motor_id": "tmotor_mn3508_kv380",
  "propeller_id": "tmotor_p15x5_cf",
  "dataset_kind": "synthetic_fixture",
  "independent_run_id": "synthetic_verification_B",
  "evidence_source": "synthetic math fixture, not a physical laboratory",
  "hardware_matches_selected_components": true,
  "unused_for_model_calibration": true,
  "predeclared_max_thrust_error_pct": 10,
  "predeclared_max_current_error_pct": 10,
  "observations": [
    {"id": "s1", "rpm": 4000, "voltage_v": 14.8, "thrust_gf": 900, "current_a": 5.5},
    {"id": "s2", "rpm": 4100, "voltage_v": 14.8, "thrust_gf": 960, "current_a": 6.0},
    {"id": "s3", "rpm": 4200, "voltage_v": 14.8, "thrust_gf": 1000, "current_a": 6.4},
    {"id": "s4", "rpm": 4300, "voltage_v": 14.8, "thrust_gf": 1030, "current_a": 6.9},
    {"id": "s5", "rpm": 4400, "voltage_v": 14.8, "thrust_gf": 1070, "current_a": 7.2}
  ]
}
```

**Never change `dataset_kind` to `physical_measurements` for these illustrative numbers.** The dataset is submitted transiently and is not authenticated or automatically saved.

## Core prediction checks

- RPM must fall within the existing measured thrust table. Voltage must be inside the dataset's allowed range. Rejected points are listed and **invalidate any whole-run acceptance**; supported points remain visible for diagnosis.
- For each supported observation compute static thrust (`gf`) and input current (`A`) from the pre-existing motor/prop lookup; record signed relative prediction error, RMSE, MAPE, bias and worst absolute relative error.
- Require both predeclared worst-error tolerances across *all* submitted samples to be met. A favorable mean can never hide one failing operating point.
- A voltage outside the original *measured* planes, even if the simulator's bounded model can extrapolate there, **does not** receive a physical validation pass.
- Identical RPM/voltage operating points from calibration are counted but not automatically disqualifying when the test run is independently measured. Independence, hardware and instrumentation remain self-reported and not externally authenticated.
- Thermal effects, air-density corrections, blade unsteady flow, installed-interference, advance ratio and mechanical wear are **not** modeled. Static bench agreement is not validation of forward flight, aircraft endurance, stability, or mission outcome.
- Result verdicts explicitly distinguish synthetic numerical verification, untrusted provenance, missing hardware match, calibration leakage, out-of-envelope data, exceeded tolerances, and user-reported eligible held-out data. Even reported success is never certification.

## Regression

```bash
pytest tests/physics/test_propulsion_evidence.py tests/integration/test_propulsion_evidence_api.py
pytest
cd apps/web && npm ci && npm audit --audit-level=moderate && npm run build && npm test
```

**No claimed physical-model equivalence until actual independent bench files with traceable instruments, conditions and hardware are submitted.**

## Integration and rebase, November 2026

This module was recovered from unmerged PR #13, rebased onto main after
the M14 flight uncertainty, M15 battery replay, M16 public-source audit,
and M17 independent same-propeller installation evidence milestones.

The M18 endpoint is **operator-reported evidence**, not independently
authenticated validation of a motor or vehicle. A reported match never
changes the evidence credibility rating of an assembled drone without
external calibration/holdout authentication, uncertainty analysis and
independent engineering review.

Numerical overflow of relative percentage errors is treated as an
unsupported observation rather than producing nonfinite JSON or a false pass.
