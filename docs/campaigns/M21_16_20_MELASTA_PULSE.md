# M21.16–M21.20 — Voltage and power during a measured Melasta 10C pulse

## M21.16 Original cell experiment

Oxford Brookes researchers measured five Melasta LCO 6.8 Ah pouch cells at nominal 25 °C, with five repetitions per cell. The study applied a dynamic load history before a nominal 68 A, approximately 30 s discharge pulse. This benchmark uses Experiment I, recorded at cell level. The original ZIP matched Zenodo's published 1,205,362-byte length and MD5 `868129c8537b1163f8816e850b587a3f`. Its SHA-256 is embedded in the executable benchmark and freeze. [Study protocol](https://doi.org/10.1016/j.jpowsour.2024.235168) · [CC BY 4.0 publisher data](https://doi.org/10.5281/zenodo.12543440)

## M21.17 Reserve entire cells

Calibrate on IDs 1, 2 and 3, and retain all five measurements each from IDs 4 and 5 as holdouts. The loader checks the logged pulse step, current, duration and time order before resampling onto the common 0–29 s interval. The independent hardware grouping is the physical cell. The model and held-out analysis were fixed before reading numerical pulse outcomes from the reserved cells. [Calibration freeze](m21_melasta_pulse_freeze.json) · [Freeze commit](https://github.com/god88844-hub/aeroforge/commit/5de19f6935602dd21b7fd2050485b9d03bf783b2)

## M21.18 Predict from pre-pulse observations

Anchor each forecast on the mean voltage measured in the last 0.5 s of the preceding dynamic load. The baseline subtracts the mean signed voltage change fitted across calibration pulses. The candidate fits the change as an intercept and a square-root-of-time term. Because the anchor is loaded voltage, the initial fitted change can be signed. It is an empirical effect of the load transition and later decline, with no claim that the intercept is an ohmic resistance. Both forecasts use the prescribed 68 A to predict pulse power. Measured voltage and current during the pulse supply the verification target.

## M21.19 Held-out results

| Metric | Fixed voltage change | Time-dependent voltage change |
| --- | ---: | ---: |
| Mean run voltage MAE | 31.90 mV | 8.25 mV |
| Mean absolute 29 s voltage error | 69.33 mV | 6.81 mV |
| Largest point voltage error | 88.46 mV | 45.38 mV |
| Mean absolute average-power error | 0.228 W | 0.243 W |

The time-dependent model improved voltage tracking but slightly worsened average-power error. It overpredicted the 29 s voltage on all ten repetitions by 3.64–11.29 mV. The forecast is conditional on measured pre-pulse voltage of the same cell and applies only to the tested load history and pulse. Pack capacity, cutoff behavior and usable flight endurance remain open. [Per-cell and per-run metrics](m21_melasta_pulse_results.json)

## M21.20 Reproduction

Download `Experiment-I.zip` from Zenodo. Keep the archive bytes as published and run these commands in the backend Python environment with NumPy and SciPy.

```console
python scripts/benchmark_melasta_pulse.py calibrate Experiment-I.zip local-freeze.json
python scripts/benchmark_melasta_pulse.py evaluate Experiment-I.zip local-results.json --freeze local-freeze.json
```

Compare the two generated files with their committed counterparts. The synthetic regression test covers the pre-pulse boundary and short-record rejection.
