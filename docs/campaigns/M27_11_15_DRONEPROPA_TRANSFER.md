# M27.11–M27.15 — QDrone 2 altitude error across vehicles and speed settings

## M27.11 Preserve the model and define independent cohorts

Reuse the M23 altitude model, including its frozen 0.40 s filter time constant and zero additional input delay. Five healthy direct vertical missions in DronePropA are reserved for transfer scoring. Two use different QDrone 2 aircraft (D2 and D3) at the original SP1 setting. Three use the original D1 aircraft at SP2. Score the cohorts separately because they test different changes and the SP2 flights share the same airframe. [Original tracking study](M23_3_7_DRONEPROPA_ALTITUDE.md) · [Pinned transfer sources](m27_dronepropa_transfer_sources.json) · [Publisher dataset](https://doi.org/10.17632/ftdyxrr3c5.1)

## M27.12 Freeze empirical error ranges

Use the three nominal direct D1/SP1 maneuvers, held out from the earlier point-model fit, to calibrate error ranges for this separate evaluation. Define a symmetric range by the maximum absolute residual across those flights for each existing command regime, rounded upward at 1 nm for reproducible storage. The half-width is 13.857 cm during moving-reference samples and 14.338 cm in the rest of the evaluation window. The bands are empirical and do not carry a promised coverage level. Samples use the same 50 Hz time grid, commanded altitude window and 0.05 m/s reference-rate cutoff as M23. [Frozen bands](m27_dronepropa_transfer_freeze.json) · [Freeze commit](https://github.com/god88844-hub/aeroforge/commit/11ddd5ccfda96c8c1d32532d62e095fe9c37a85d)

## M27.13 Score complete flights

Evaluate the frozen model against synchronized OptiTrack altitude from the reserved flights. Count the error and band exceedance in each command regime. Whole-flight coverage requires every scored sample to lie inside its assigned band. The split, model, bands and scoring code were committed before scoring the transfer flights.

## M27.14 Transfer results

| Transfer cohort | Mean flight MAE | Worst point error | Largest band exceedance | Whole flights covered |
| --- | ---: | ---: | ---: | ---: |
| D2 and D3 at SP1 | 3.00 cm | 16.82 cm | 2.87 cm | 1/2 |
| D1 at SP2 | 2.72 cm | 14.23 cm | 0.24 cm | 1/3 |

The bands covered 10,109 of 10,147 scored samples and only two of five complete flights. D2 accounted for 36 of the 38 missed samples. The remaining two misses were separate SP2 repeats during a moving reference. The source evidence supports scoped error estimates for these direct indoor maneuvers. Timing uncertainty, independent coverage across more aircraft, and predeclared acceptance tolerances remain unresolved. [Per-flight results](m27_dronepropa_transfer_results.json)

## M27.15 Reproduction

Place the three nominal D1/SP1 direct-flight files from the M23 manifest and the five transfer files in one directory. The script verifies each publisher digest before parsing.

```console
python scripts/benchmark_dronepropa_transfer.py calibrate FLIGHT_DIRECTORY local-freeze.json
python scripts/benchmark_dronepropa_transfer.py evaluate FLIGHT_DIRECTORY local-results.json --freeze local-freeze.json
```

Compare those files with the committed calibration and results. The focused regression tests verify inclusive boundaries and retention of any whole-flight miss.
