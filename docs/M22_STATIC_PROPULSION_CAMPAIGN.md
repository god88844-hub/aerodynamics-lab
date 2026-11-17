# M22 — Source-pinned static propulsion operating-point audit

## Intent

The project's primary goal is simulation prediction accuracy approaching
independently measured physical results in a defined engineering envelope.
M22 implements the **software evidence-screening prerequisite** for
independent motor–ESC–propeller bench measurements. It does **not** obtain an
actual matched physical test, establish a credible thermal/dynamic flight
model, independently authenticate a motor serial or authorize flight.

The physical experimental campaign is tracked in
[GitHub issue #25](https://github.com/god88844-hub/aeroforge/issues/25).
The full-aircraft evidence blocker remains
[issue #16](https://github.com/god88844-hub/aeroforge/issues/16).

## Evidence chain and model comparison

- Input runs are **unaltered** static plateau operating-point summaries
  in exact CSV form with SI header
  `rpm,voltage_v,thrust_n,current_a`. Unlike M19 continuous telemetry,
  this CSV has no per-row timestamp and cannot support transient response,
  time-aligned power/energy or thermal stress claims.
- Declare original source SHA-256, source permission, experimental bench/fixture,
  motor/propeller/ESC serials, vehicle/pack identity, source kind and
  calibration/holdout role. A matching hash against a user-entered digest
  only protects internal byte consistency, not physical provenance.
- Supply M20 frozen protocol, a separately archived digest and **predeclared**
  absolute error tolerances in Newtons for thrust and amperes for current,
  along with hard error budgets for each measurement channel. Standard
  deviations are not hard error bounds.
- Require at least one calibration and two whole-recording holdout
  experiments. Cross-partition reuse of experiment, recording, vehicle,
  battery, motor, propeller, ESC, fixture ID or raw source hash is reported
  as leakage, even when rows agree numerically.
- The immutable manufacturer `PowertrainDataset` remains the model of
  record. Each source observation is interpolated only within existing
  measured RPM and voltage support. Unsupported points are reported rather
  than cherry-picked to create a positive score.
- Each supported sample reports measured/reference thrust and current,
  absolute residuals and conservative **samplewise** upper error bounds
  under the declared hard measurement uncertainties.
- Bench ambient air density and temperature are recorded but are not
  automatically corrected. M17's published G30 experiment used a different
  motor and a different installation, so it cannot establish an independent
  P80 III KV100 propulsion test.
- Manufacturer calibration-knot operating-point overlap is reported,
  since repeating an existing fitted table is **not** an independent
  physical generalization experiment.

At best this module can report **declared samplewise compatibility** with
the independently registered limits. The result always explicitly states:

```
PHYSICAL_PROPULSION_VALIDATION_NOT_ESTABLISHED
```

Neither a metadata signature nor a green benchmark can establish physical
airworthiness. The exact installed P80 III+G30 combination still needs
independent physical static and transient tests under properly controlled
conditions, with uncertainty and independent technical review.

## API and offline usage

`POST /api/components/propulsion-campaign-audit`

A complete JSON request has `motor_id`, `propeller_id`,
`frozen_protocol` (M20 schema), `expected_frozen_sha256` and
`runs`, each with source-hash-verified static CSV and complete
experiment/motor/propeller/ESC/fixture identifiers.

The entire valid **synthetic** example is in
`tests/physics/test_propulsion_campaign.py` and is deliberately not
an independent physical measurement.

```bash
python scripts/audit_propulsion_campaign.py --request campaign.json --output audit.json
python -m pytest tests/physics/test_propulsion_campaign.py tests/integration/test_propulsion_campaign_api.py -q
python -m pytest -q
cd apps/web && npm ci && npm audit --audit-level=moderate && npm run build && npm test
```

The CLI exits nonzero if the physical validity grant has not been
established, even if mathematical fixture comparisons agree.

## Remaining M22 / M23–M31 work

For physical M22 completion, commission or obtain independently verifiable
exact-motor-and-mount bench records, measured instrument uncertainty,
qualified safely conducted thermal/continuous-rating/transient studies,
genuine whole-run blind holdouts and independent review. No data are
fabricated by this milestone. M23 still requires hardware-in-the-loop,
followed by complete validated aerodynamics, structural behavior,
real-flight campaigns, uncertainty coverage and product release.
