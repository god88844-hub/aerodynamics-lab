# M25.12–M25.16 — Printed drone-arm response to actuator stroke

## M25.12 Measurement source

Białek, Mańkowski and Krzyżaniak published processed force and displacement measurements from printed drone arms tested in a displacement-actuated fixture. The force instrument is an HBM U9C, and the fixture also used a Panasonic HG-C1100 laser sensor. The source includes carbon PETG and PLA at 25% and 100% infill. The original-format export is pinned by its publisher file ID 96716, 3,052,355 bytes and SHA-256. [RepOD v1 data and CC BY-SA 4.0 license](https://doi.org/10.18150/JG8XQS)

## M25.13 Whole-source-group split

Each material and infill configuration has five source groups with one trace at each nominal stroke from 1 to 5 mm. Reserve groups 4 and 5 and fit on groups 1–3. Treat the source group as the experimental unit, since the documentation does not identify the number of separately manufactured specimens. Require all declared stroke groups and at least 30 finite force samples per stroke. The raw laser channel stays outside this comparison because its calibration to effective arm-tip deflection is unavailable.

## M25.14 Effective force response

Use the 95th percentile of the force observations in each stroke record. This represents a robust high-load response within the stroke. Fit a through-origin linear spring for each tested material and infill, using nominal actuator displacement. The slope absorbs fixture compliance, specimen properties and geometry. The comparison baseline fits one effective slope for each material while pooling infills. All fits use only the earlier source groups. [Frozen coefficients and empirical error ranges](m25_repod_arm_response_freeze.json)

## M25.15 Empirical error range and scoring

For each configuration, freeze a symmetric error range from the maximum absolute residual across its three leave-one-source-group-out calibration comparisons. Evaluate prediction errors and the fraction of individual strokes and whole held-out groups within that range. This provides an empirical diagnostic on a small experiment, and no coverage probability or specimen safety margin. Score MAE, RMSE, bias and maximum absolute error. The protocol and calibration were frozen before reading numerical force data from the selected holdout groups.

## M25.16 Held-out results and reproduction

The [frozen fit and scoring rule](https://github.com/god88844-hub/aeroforge/commit/569bc4216ffd65d7758d8fb160544131a095f549) scored all eight held-out source groups and 40 strokes. The separate infill slopes reduced mean absolute force error from 1.390 N to 0.298 N. The model's pooled signed bias was +0.288 N and its largest absolute error was 0.789 N. [Aggregate and per-stroke results](m25_repod_arm_response_results.json)

| Material and infill | Effective stiffness (N/mm) | Model / baseline MAE (N) | Strokes within empirical range | Whole groups within range |
| --- | ---: | ---: | ---: | ---: |
| Carbon PETG, 25% | 1.391 | 0.289 / 1.770 | 7/10 | 0/2 |
| Carbon PETG, 100% | 2.378 | 0.416 / 1.156 | 7/10 | 0/2 |
| PLA, 25% | 1.046 | 0.263 / 1.541 | 10/10 | 2/2 |
| PLA, 100% | 1.925 | 0.225 / 1.093 | 2/10 | 0/2 |

The calibrated model overestimated the robust high-force statistic in all four configurations on average. The empirical range covered 26 of 40 strokes and every stroke in only two of eight holdout groups. The response model therefore provides a bounded point comparison, with insufficient evidence for a structural margin.

Download the [original processed CSV](https://repod.icm.edu.pl/api/access/datafile/96716?format=original) outside the repository. Run the following using the backend Python environment.

```console
python scripts/benchmark_repod_arm_response.py calibrate CSV local-freeze.json
python scripts/benchmark_repod_arm_response.py evaluate CSV local-results.json --freeze local-freeze.json
```

The result applies to the published fixture and nominal 1–5 mm stroke. The source lacks the geometry and measurement uncertainty required to infer Young's modulus, flight loads, ultimate strength, or fatigue life.
