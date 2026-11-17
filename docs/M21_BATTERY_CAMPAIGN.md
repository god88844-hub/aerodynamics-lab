# M21 — Source-pinned battery campaign comparison (software scope)

**Status:** The campaign *software* has been implemented. **No independently
observed high-C battery experiment has been acquired or authenticated.**
Experimental acceptance work tracked in [issue #23](https://github.com/god88844-hub/aeroforge/issues/23)
and whole-aircraft evidence in [issue #16](https://github.com/god88844-hub/aeroforge/issues/16)
remain unsatisfied. Do not label the M21 physical test campaign complete.

## Objective

Make the first-order `OCV(SOC)+single pack resistance` model answer a
**strictly bounded, reproducible question:** does its terminal-voltage
trajectory, *conditioned on externally observed current and declared initial
SOC*, agree with held-out original time-series measurements under a
predeclared voltage error criterion?

This is **not** an autonomous prediction of load-current demand, energy
consumption, actual flight endurance, safe operation, pack temperature or
manufacturing reliability. The model currently omits thermal and aging
dependence, rate-dependent usable capacity, cell imbalance, hysteresis and
failure mechanisms. None of these omissions can be ignored.

## Evidence chain

- Supply M19 `InlineTelemetryDataset` manifests plus **unaltered, SHA-256
  checked original CSV bytes** for full individual discharge recordings.
  Require `t_s,terminal_voltage_v,current_a` and preferably
  `temperature_c`. The no-timestamp PX4 battery data from M16 cannot be
  used to manufacture time-dependent battery validation evidence.
- Supply the exact M20 `ValidationProtocol` model/design/controller version
  and separately precommitted canonical protocol digest. Required voltage
  error limits, recording/experiment IDs, pack serials and sampling limits
  are cross-checked. Calibration and holdout partitions must be separated
  by whole experiments, battery identities, vehicle identities and file
  hashes; a relabelled or duplicated run is never a blind holdout.
- Reuse M15's fixed OCV+R battery equations, M19 SHA-256 source audit, and
  M20 preregistration gate. The original readings determine current input;
  the model is **never refit** to the held-out observations.
- Report per-recording samplewise voltage MAE, RMSE, worst absolute
  discrepancy, measured charge and Wh, warning-voltage crossing time,
  observed C-rate, endpoint visibility, sample density and evidence gaps.
- Interpret hard declared measurement bounds conservatively. With residual
  magnitude `|r|` and declared absolute measurement bound `U`, the
  samplewise absolute discrepancy enclosure is
  `[max(0, |r|-U), |r|+U]`. Only the **samplewise compatibility** of these
  measured points is assessed against predeclared voltage tolerance.
  A positive or unknown time-alignment error blocks any claim of a full
  continuous-time enclosure. Standard uncertainty is not a hard error
  bound and cannot grant a positive enclosure.

### Scientific safeguards

M21 **never** asserts physical-validation equivalence because actual
instrument chains, declared errors, preregistration timing, battery identity,
real test independence and model-form discrepancy are not independently
authenticated. A generic reference pack is not a validated actual pack,
even with perfect numerical agreement. The presence of temperature samples
does not validate pack-temperature prediction: none is modeled.

**All numerical test fixtures are synthetic.** Some tests deliberately label
synthetic numbers as `reported_physical_measurements` to verify that a
user-controlled metadata label cannot authenticate an experiment. These
fixtures are adversarial software checks, not observations.

### API

`POST /api/components/battery-campaign-audit`

```json
{
  "battery_model_id": "generic_6s_lipo_16000mah",
  "frozen_protocol": { "schema_version": "1.0" },
  "expected_frozen_sha256": null,
  "runs": [
    {
      "evidence": {
        "manifest": { "schema_version": "1.0" },
        "csv_text": "t_s,terminal_voltage_v,current_a,temperature_c\\n..."
      },
      "initial_soc_pct": 100,
      "hardware_match_self_reported": false,
      "unused_for_calibration_self_reported": false,
      "illustrative_endpoint_error_limit_pct": 5
    }
  ]
}
```

The snippet illustrates **shape only** and is deliberately not a valid
complete evidence payload. `illustrative_endpoint_error_limit_pct` is a
descriptive replay option, **not** an externally frozen M20 criterion and
must never support an independently validated endurance claim. Do not
substitute invented calibration certificates, current/voltage readings or
source hashes.

For a complete synthetic example, see
`tests/physics/test_battery_campaign.py`. The app's battery campaign
panel takes this JSON and never changes the stored simulated drone.

Offline:

```bash
python scripts/audit_battery_campaign.py --request actual_campaign.json --output audit.json
```

The CLI exits nonzero while independent physical validation is not
established, even when all software comparisons were mathematically
consistent. This prevents pipelines accidentally equating a successful
numerical comparison with flight qualification.

## Verification and future physical testing

```bash
python -m pytest tests/physics/test_battery_campaign.py tests/integration/test_battery_campaign_api.py -q
python -m pytest -q
cd apps/web && npm ci && npm audit --audit-level=moderate && npm run build && npm test
```

To meet the **actual M21 scientific gate** requires independent qualified
laboratory measurements of the selected real battery packs at relevant C
rates, temperatures, ages and charge histories, with immutable original
logs, calibrated instruments and safety review. The resulting model must
then demonstrate generalization on blind holdouts over the predeclared
mission envelope, including transient and failure modes. No software agent
can fabricate that evidence.
