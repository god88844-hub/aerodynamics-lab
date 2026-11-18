# M26.50–M26.54 — QDrone 2 altitude and voltage transfer across battery conditions

## M26.50 Record provenance and the experiment split

Borbolla-Burillo and colleagues tested a Quanser QDrone 2 with the original model predictive controller and a battery-aware variant. The study identifies OptiTrack as the linear position measurement system. Use the two high-voltage trajectory exports (Figures 9a and 9b) for fitting. Reserve both low-voltage trajectories (Figures 11a and 11b) and their accompanying power and energy exports (Figures 12a and 12b). The publisher files were verified against length and MD5 before SHA-256 pinning. [Study](https://doi.org/10.1080/21642583.2026.2671488) · [Original exports](https://doi.org/10.5281/zenodo.19464105) · [File manifest](m26_qdrone_voltage_sources.json)

## M26.51 Freeze conditional predictions

Start from the median measured altitude and loaded battery voltage through 0.5 s. Use two cascaded first-order responses to the logged altitude reference. Use the auxiliary reference for the battery-aware controller and the nominal reference for the original controller. Fit an electrical sag model with nonnegative coefficients on the change in mean squared motor drive voltage and its exponentially filtered value. The squared voltage is a command-derived proxy for changing demand. The fit selected a 0.10 s altitude-stage time constant and a zero coefficient on the electrical memory term. The archived drive and auxiliary reference contain in-flight information, so the comparison is conditional on the recorded commands. [Frozen models](m26_qdrone_voltage_freeze.json) · [Freeze commit](https://github.com/god88844-hub/aeroforge/commit/881607b7640ffe9ecd769ed1fd6c9360fca2a3d8)

## M26.52 Check voltage-line crossings and measured tracking

Score the first sample strictly below the study's 14 V safety line, observed altitude tracking against the nominal command, and prediction errors after 0.5 s. The line is a study operating reference. A sample below it records a voltage limit violation in this comparison. The exports give no direct controller protection flag or firmware cutoff timing.

| Reserved low-voltage flight | Voltage MAE | Measured minimum | First measured / predicted sample below 14 V | Altitude prediction MAE | Measured / predicted final altitude |
| --- | ---: | ---: | --- | ---: | ---: |
| Original MPC | 0.2325 V | 13.7277 V | 1.2075 s / 1.2075 s | 1.1820 m | 0.0007 m / 1.7035 m |
| Battery-aware MPC | 0.0318 V | 14.0911 V | None / None | 0.0143 m | 1.7062 m / 1.7050 m |

The original-controller voltage sample violated the study line. The altitude model continued to predict the commanded ascent through the observed loss of tracking. This demonstrates a missing coupling between electrical limits and commanded motion in this conditional model. The battery-aware case stayed above the study line in the recorded window. [Result JSON](m26_qdrone_voltage_results.json)

## M26.53 Reconcile energy and evidence scope

Both low-voltage trajectory exports align with their paired electrical reports on a 2.5 ms grid. Integrating the reported power reproduced the reported energy increase of 4,138.90 J and 4,468.34 J, respectively. The publisher exports provide power and integrated energy without a separately accessible calibrated current channel. The equality checks the internal consistency of those reports. The experiment gives one reserved run per controller and one published maneuver. Independent trial repeats, calibrated pack current and additional flight regimes remain open for the full-aircraft gate.

## M26.54 Reproduce

Download the six pinned exports from the manifest into one directory. Use AeroForge's Python environment with `openpyxl==3.1.5` for reading the original workbooks.

```console
python scripts/benchmark_qdrone_voltage_transfer.py calibrate FILE_DIRECTORY local-freeze.json
python scripts/benchmark_qdrone_voltage_transfer.py evaluate FILE_DIRECTORY local-results.json --freeze local-freeze.json
```
