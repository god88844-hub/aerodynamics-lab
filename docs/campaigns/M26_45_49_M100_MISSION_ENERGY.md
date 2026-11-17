# M26.45–M26.49 — Matrice 100 planned-mission energy benchmark

## M26.45 Source and configuration

Rodrigues et al. collected data on a DJI Matrice 100 with anemometer, GNSS/INS and Mauch PL-200 bus voltage and current instrumentation. AeroForge uses the publisher's synchronized per-flight exports. Logger-native recordings are a separate archive. The files are pinned by publisher file ID, byte length and local SHA-256 in the [frozen calibration](m26_m100_mission_energy_freeze.json). The source lists the recorded aircraft type and test payload. Component serials, aging and individual battery identities are unavailable for this comparison. [Experiment](https://doi.org/10.1038/s41597-021-00930-x) · [Dataset and CC BY 4.0 license](https://doi.org/10.1184/R1/12683453.v1)

| Local benchmark file | Publisher file ID | Contents |
| --- | ---: | --- |
| CMU-M100-flights.zip | 26385070 | Original publisher-processed per-flight CSV archive |
| CMU-M100-parameters.csv | 26385034 | Preplanned speed, payload, altitude and route with dates |
| CMU-M100-README.txt | 26405786 | Source descriptions and sensor ranges |

## M26.46 Whole-flight split and reference measurements

The comparison is limited to route R1, planned speed 4–12 m/s from the five source settings, planned altitude 25–100 m from the four source settings, and payload 0, 250 or 500 g. The chronological split assigns dates before 1 August 2019 to calibration and dates from 1 August onward to holdout. Only date and mission settings determine eligibility before meter checks. This reserves 25 later files over three days. The freeze identifies 151 eligible calibration flights over 13 days and five earlier files rejected by the clock-gap rule.

Use the entire published trace from the first to last included row, so startup or idle intervals within that trace are included. Reference energy is the trapezoidal integral of signed terminal voltage times current. The processed export reports positive current during powered flight, and small negative readings are retained in the signed calculation. The publisher separately describes a negative discharge sign for the logger-native battery topic. Use the published per-flight timestamp in seconds. Preserve whole-flight rejection if a gap exceeds 1 s, time is nonmonotonic, data is missing, or the readings exceed the published PL-200 range of 33 V and 200 A. No energy across unknown gaps is inferred.

## M26.47 Frozen preflight forecast

Fit recorded duration by nonnegative least squares on an intercept, inverse planned cruise speed and planned altitude. The inverse-speed coefficient represents an effective route distance, the altitude coefficient absorbs the time penalty for vertical travel, and the intercept includes fixed route and recording overhead. Fit mean electrical power on an intercept and configured payload in kilograms. Multiply the two predictions and convert joules to Wh. Fit both models only on earlier flights. Holdout predictions use the three planned parameters. Recorded duration, measured current and measured voltage are used to measure errors.

Compare with a baseline that averages earlier energies for the exact planned speed, altitude and payload combination. Use the calibration-wide mean when a combination is absent and record the fallback.

## M26.48 Scores and coverage

Report per-flight errors, aggregate energy and duration MAE/RMSE/bias/maximum absolute error, and eligibility outcomes. Before opening the later flight CSVs, freeze an empirical symmetric error band from the 90th percentile absolute Wh residual, leaving one calendar date out at a time in calibration. Measure its frequency on the later flights. The empirical band is specific to this experiment and sample, with correlation among flights on a given day. Its width represents calibration forecast error and does not supply a separate certified meter uncertainty budget.

## M26.49 Results and reproduction

The [frozen model and scorer](https://github.com/god88844-hub/aeroforge/commit/fefb6c16247c68828a5d82f65f9df20d3aac5cb0) scored 24 later flights. Flight 277 was rejected because its largest sample gap was 1.3 s. Recorded energies of scored flights spanned 15.41–27.85 Wh. The [flight-by-flight report](m26_m100_mission_energy_results.json) records both predictions and the rejection.

| Output | MAE | RMSE | Bias | Maximum absolute error |
| --- | ---: | ---: | ---: | ---: |
| Planned energy forecast (Wh) | 0.920 | 1.150 | +0.335 | 2.614 |
| Configuration baseline (Wh) | 0.949 | 1.532 | −0.102 | 4.880 |
| Recorded duration forecast (s) | 9.957 | 17.041 | −4.422 | 56.732 |

The forecast had lower overall errors, including two flights for which the baseline fell back to the calibration-wide mean. On the 22 flights with an exact configuration match, the baseline had lower MAE, 0.619 Wh against 0.881 Wh. The ±1.620 Wh band covered 19 of 24 flights (79.2%). All 19 covered flights were on 5 August, which supplied 21 of the 24 scored flights. The three September and October flights all fell outside the band. The sample provides evidence of error growth across dates and leaves operational coverage unestablished.

Download by file ID using the Figshare file API at `https://api.figshare.com/v2/file/download/FILE_ID`. Save the originals under the local names above without changing any bytes. From the repository root and backend Python environment, run the following, replacing DATA_DIR with that directory.

```console
python scripts/benchmark_m100_planned_energy.py calibrate DATA_DIR local-freeze.json
python scripts/benchmark_m100_planned_energy.py evaluate DATA_DIR local-score.json --freeze local-freeze.json
```

The benchmark evaluates planned-mission energy on the published R1 configuration. Flight acceptance requires further evidence about independent measurement uncertainty, vehicle state, applicable operating limits, and trajectories beyond this experiment.
