# M22.1–M22.5 — Static thrust and current for the Emax/Gemfan propulsion bench

## M22.1 Matched bench source

The builder identifies an Emax ECOII-2807 1300 Kv motor, Gemfan Flash 7042 propeller and Holybro Tekko32 F4 50 A ESC. The source describes the bench test as using the same combination as the as-built quadrotor. Eight original RCbenchmark setpoint CSVs contain a fixed ESC command, thrust in gram-force, current and bus voltage. Each CSV was checked against the publisher's Git blob and pinned by SHA-256. The RPM labels in filenames identify the records. Both measured RPM columns are zero in the selected exports. [Builder report and source](https://github.com/mdttech/quadrotor-design/tree/b6f1dde3aafb1c5f564485f91406226e236ab578) · [Source manifest](m22_gemfan_bench_sources.json)

## M22.2 Freeze four calibration setpoints and four holdouts

Fit on records `RPM_2130`, `RPM_8000`, `RPM_11850` and `RPM_14100`. Hold out records `RPM_5740`, `RPM_9600`, `RPM_10750` and `RPM_12270`. Each record supplies one median thrust and current target after checking for a single PWM setting and finite channel values. Convert gram-force to newtons with 0.00980665 N/gf. Retain the interquartile range, timestamp discontinuities and negative thrust counts as measurement context. The files contain repeated samples of one bench configuration. [Calibration freeze](m22_gemfan_bench_freeze.json) · [Freeze commit](https://github.com/god88844-hub/aeroforge/commit/7c905f80901e949b211c31a4716931b6832967c7)

## M22.3 Compare steady predictors

Interpolate the four calibration medians by PWM. Separately, fit a power law for each output with logged bus voltage multiplied by normalized command above 1,000 μs as the drive proxy. The voltage-adjusted model is conditioned on measured bus voltage, and both comparisons stay inside calibration PWM support. The model form and fit were committed before reading the numerical holdout targets.

## M22.4 Held-out results

| Model | Thrust MAE | Current MAE |
| --- | ---: | ---: |
| PWM interpolation | 0.096 N | 0.435 A |
| Voltage-adjusted power law | 1.075 N | 1.633 A |

The interpolation current error reached 1.37 A at the 1,400 μs setpoint. At the lowest calibration command, negative thrust samples and broad thrust spread indicate limited measurement quality. The results quantify static error on four reserved settings from this bench. Independent repeated runs, measured shaft speed, transient response and installed-aircraft acceptance remain open. [Per-setpoint results](m22_gemfan_bench_results.json)

## M22.5 Reproduce

Download the eight files named in the manifest into one directory and run the benchmark with Python 3.11 or newer.

```console
python scripts/benchmark_gemfan_bench.py calibrate FILE_DIRECTORY local-freeze.json
python scripts/benchmark_gemfan_bench.py evaluate FILE_DIRECTORY local-results.json --freeze local-freeze.json
```

The regression test verifies that the interpolator rejects commands beyond calibration support.
