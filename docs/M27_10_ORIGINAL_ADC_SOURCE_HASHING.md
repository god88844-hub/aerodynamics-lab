# M27.10 — Original-byte ADC and frozen prediction source pairing

`physics.validation.original_adc_sources` validates the original supplied UTF-8 CSV strings using the declared SHA-256 for *each file* before parsing or comparing any ADC reading or frozen prediction. It enforces separate original source digests for every whole-run observation/prediction pair and across all reported independent holdouts. Per-file maximum: 1 MB; per-run source rows: 5–5000. Strict exact CSV headers:

```csv
sample_id,t_s,raw_code,saturated
```

and

```csv
sample_id,t_s,prediction,lower,upper
```

The first is exact unsaturated integer ADC codes, saturation bit 0/1 and seconds from experiment origin. The second contains the frozen prediction and two error-band limits in the calibration's explicit output unit. No interpolating timestamps, imputing missing rows, modifying source bytes, rounding IDs, silently accepting clipped values or joining unrelated time grids is permitted. The exact sample IDs, row counts and decimal timestamp numbers must match, and time begins at zero and strictly increases.

After verifying original bytes, `load_original_adc_sensor_case` produces exactly the arguments for M27.9 affine conversion; `audit_original_adc_holdout_sources` executes that conversion and retains original file digests beside the numerical results.

**Evidence limitation:** Comparing original bytes to SHA-256 digests **supplied by the same operator** only checks internal consistency; anyone controlling both bytes and digest may fabricate a matching pair. M27.10 does not authenticate the recorder's identity, manufacturer certificate, test occurrence, frozen prediction time, independent whole-run acquisition, or real physical model accuracy. All physical/equivalence/release flags are false.

Synthetic tests: `python -m pytest tests/physics/test_original_adc_sources.py -q`. Actual independent acquisition evidence remains blocked under issue #16.
