# M21.11–M21.15 — Pre-cutoff forecast on the 24S laboratory module

## M21.11 Source and split

Reuse the same bound SIT module and independently published measurements in the [electrical and thermal study](M21_6_10_SIT_MODULE_ELECTROTHERMAL.md). The earlier fit uses discharge cycles 1–50. This follow-up reserves cycles 51–150 for empirical calibration and cycles 201–250 and 279–328 for evaluation. The two previously evaluated cohorts are excluded. Each admitted cycle is part of the same repeatedly tested module. [Experimental paper](https://doi.org/10.1016/j.est.2023.107493) · [Dataset](https://doi.org/10.25447/sit.21301188.v1)

## M21.12 State at forecast issuance

Issue a forecast at 370 s after accepting the source timestamps and measuring current and voltage through that sample. Start with the earlier one-polarization model and its integrated charge and polarization state. The uncorrected forecast uses that model directly. To update the comparison model, estimate an OCV offset from the median module residual during the 300–320 s rest interval (current below 1 A). Estimate a series-resistance correction from the median residual and current during the 354–370 s loaded interval (current at least 90 A). Each correction interval needs five observations. A negative corrected series resistance makes the updated forecast ineligible. The intervals were selected during development using the earlier cycles and the published test sequence.

## M21.13 Final-load forecast

Simulate samples from 372 to 426 s assuming the 9 kW final load in the published study. The fixed end time covers the schedule window inferred from the earlier development cycles and the duration in Table 3. Advance charge and polarization using the previous current, then solve the electrical equation for the stable high-voltage root of the nominal constant-power load. Use the predicted current in the next step. The integration stops if the model leaves its trained charge support or the constant power is unavailable. The forecast after 370 s uses the nominal power and its own simulated state. Later recorded current, voltage and record length are reserved for scoring.

## M21.14 Empirical cutoff warning and censoring

Calibrate a one-sided voltage margin from the 95th percentile of the worst optimistic voltage error per earlier comparison cycle. Evaluate whole-compared-segment coverage, point forecast misses, and warning misses at the study's 80 V threshold. An observed or predicted point crossing fails the sampled limit screen. The lower-band crossing warns of possible undervoltage. For comparison, an observed crossing is detected when the corresponding point or warning first crosses at or before the recorded crossing. Compare only matched timestamps through each source record's end. Counts of warnings without a recorded crossing are reported separately for files ending before 426 s, since the recording can stop before a crossing is captured. Empirical coverage on a single module cannot support flight release.

## M21.15 Reproduction

Use the pinned local original workbook and backend setup described in the earlier report.

```console
python scripts/benchmark_sit_cutoff_forecast.py calibrate WORKBOOK local-guard.json
python scripts/benchmark_sit_cutoff_forecast.py evaluate WORKBOOK local-report.json --freeze local-guard.json
```

The source and model are frozen in the earlier benchmark. The holdout labels, time windows, update equation and empirical warning rule in this commit are frozen before numerical inspection of the specified evaluation cycles. The frozen guard uses 100 earlier cycles and has a one-sided margin of 1.207804065 V.
`16c92466dc5f4f4af8820cdb194524f61c57724dc02a81280acace33937b2664` is the SHA-256 of the canonical frozen guard JSON.
