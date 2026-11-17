# M26.40–M26.44 — NanoBench vertical flight benchmark

## M26.40 Published source and aircraft

Ullah and Baca's NanoBench dataset uses a Crazyflie 2.1 with retroreflective tracking markers and a wireless charging deck. The publisher reports 40.85 g as the measured flying mass. The five pinned recording metadata files identify aircraft CF_01 on firmware 2025.12.1. The manifest records publisher paths, Git object IDs, byte lengths, SHA-256s, and whole-flight split assignments. Each selected CSV and its metadata must match its SHA-256. [Experiment](https://arxiv.org/abs/2603.09908v2) · [Data and BSD 3-Clause license](https://github.com/syediu/nanobench/tree/934a1ab92c458cad99c9278a5cb63bf68af6e56c) · [Source receipt](../../data/benchmarks/flight/nanobench_source_receipt.json)

| Split | Publisher recording |
| --- | --- |
| Calibration | A1b_multisine_sysid_rep1, A1b_multisine_sysid_rep2 |
| Held-out climb | B12_staircase_climb_rep1 |
| Held-out circles | B2_circle_medium_rep1, B2_circle_medium_rep2 |

## M26.41 Timebase and windows

The publisher aligns the flight and Vicon clocks using gyroscope and Vicon angular-rate correlation, then resamples at nominal 100 Hz. Pre-resampling Vicon, motor, and battery sample counts are retained by recording. The benchmark uses the published aligned timebase without further fitting of clock offsets or filling of gaps. Vicon vertical velocity comes from differentiated, smoothed position.

Within each flight, use successive windows of nominal 50, 100, or 200 intervals. Adjacent windows at the same horizon share a boundary sample. Reject windows with a gap over 20 ms, a duration more than 20 ms away from nominal, nonfinite input or reference values, implausible quaternion normalization, invalid PWM or voltage, or initial Vicon altitude below 0.4 m. Calibration also requires at least 0.4 m throughout a window. Holdout excursions below that height remain in the score and are counted separately. The height cutoff defines the study scope and carries no flight safety claim.

## M26.42 Frozen vertical model

Use Newton's vertical force balance with standard gravity and measured flight mass. Body-up thrust is proportional to the sum of squared per-motor PWM duty times measured battery voltage squared. Project it onto world vertical using the Vicon attitude. The thrust coefficient and effective drag area are nonnegative and fitted from measured vertical impulse over 0.5 s calibration windows. The fit uses measured calibration velocity for the drag integral. The source does not provide a rotor thrust calibration for this specific vehicle; the fitted coefficient is an effective representation.

Forecast vertical position and velocity with AeroForge's RK4 and quadratic drag implementations. Initialize each window from Vicon altitude and vertical velocity. Thereafter use predicted vertical velocity for drag. Published PWM, battery voltage, Vicon attitude, and horizontal Vicon speed remain inputs throughout. The integrator linearly evaluates the combined thrust input and horizontal speed between source observations. The comparison baseline predicts constant initial vertical velocity over the same windows. [Frozen calibration](m26_nanobench_vertical_freeze.json)

## M26.43 Scoring and empirical coverage

For each of the three whole held-out flights and each duration, score endpoint altitude and vertical velocity against the Vicon export. Report MAE, RMSE, signed bias, maximum absolute error, source CSV lines and rejected-window counts. Report coverage of symmetric bands whose half widths were fixed at the 90th percentile absolute residual from each calibration flight forecast in turn with the other flight's fitted model. These empirical bands reflect two calibration flights and correlated windows. They carry no probabilistic safety or population-level guarantee. The comparator, model and eligibility rules are committed before numerical evaluation of the held-out CSVs.

## M26.44 Reproduction

Download the pinned CSVs and paired YAML files listed in the source manifest into one directory, leaving their bytes intact. Run the following from the AeroForge repository root in the backend Python environment, substituting that directory for DATA_DIR.

```console
python scripts/benchmark_nanobench_vertical.py calibrate DATA_DIR local-freeze.json
python scripts/benchmark_nanobench_vertical.py evaluate DATA_DIR local-score.json --freeze local-freeze.json
```

The verdict concerns a conditional vertical replay. Full flight acceptance requires independent evidence for complete vehicle and control responses, prediction without ground-truth inputs during replay, and decision-specific tolerances and measurement uncertainty.
