# M23.3–M23.7 — QDrone 2 altitude tracking against independent motion capture

## M23.3 Flight records and channel identity

DronePropA contains indoor flight recordings from Quanser QDrone 2 vehicles. Select the six healthy recordings from unit D1 and speed setting SP1 for the stepped and direct vertical missions. The study reports OptiTrack position accuracy of approximately 3 mm after calibration. Table 1's source descriptions for measured and reference positions appear transposed. The authors' MATLAB code identifies `commander_data` row 24 as measured Z and row 28 as desired Z. The calibration records also show the planned altitude plateaus in row 28. [Primary study](https://doi.org/10.1016/j.dib.2025.111589) · [Author channel definitions](https://github.com/DrIsmailCode/DronePropA-Motion-Trajectories-Dataset/blob/07b0c260352d7c9b4dd9fb8bf503c9bc7e019647/plot_data_commander.m.txt) · [Publisher records and CC BY 4.0 terms](https://doi.org/10.17632/ftdyxrr3c5.1)

## M23.4 Whole-flight experiment split

Fit on the three stepped climb and descent flights, and reserve all three direct climb and descent flights. Each file is pinned by its Mendeley SHA-256. The model, split, selected parameters and error metrics were committed before opening numerical holdout trajectories. [Source manifest](m23_dronepropa_altitude_sources.json) · [Calibration freeze](m23_dronepropa_altitude_freeze.json) · [Freeze commit](https://github.com/god88844-hub/aeroforge/commit/18d01b629d72141c22a7aa7a9950f27ca51b26c3)

## M23.5 Command-driven tracking model

Align the logged desired and motion-capture altitude channels on their shared recorded time at 50 Hz. Hold each recorded command forward until its next timestamp. The model starts from the first desired altitude and uses two cascaded unity-gain first-order stages. Choose their common time constant and additional nonnegative input delay from the fixed grids by mean calibration flight MAE. Calibration selected 0.40 s per stage and zero added pure delay. The model uses the recorded desired altitude; in-flight measured altitude is used only when scoring.

Evaluate from the first to last commanded sample at or above 0.19 m. Also score samples where the absolute command change over one evaluation interval is at least 0.05 m/s. Compare with the desired altitude itself as the instantaneous tracking reference.

## M23.6 Held-out tracking errors

| Direct vertical mission | Instantaneous tracking MAE | Causal model MAE | Largest causal model error |
| --- | ---: | ---: | ---: |
| R1 | 7.95 cm | 2.73 cm | 13.45 cm |
| R2 | 7.75 cm | 2.84 cm | 14.34 cm |
| R3 | 7.62 cm | 3.04 cm | 14.04 cm |
| Mean across flights | 7.78 cm | 2.87 cm | — |

During moving-reference samples, the mean flight MAE decreased from 26.78 cm to 3.76 cm. The scoped evidence applies to altitude tracking on the recorded indoor maneuvers of this single vehicle. The declared calibration accuracy describes the position instrument and supplies no end-to-end timing or model uncertainty interval. Engineering acceptance remains inconclusive pending predeclared tolerances, timing characterization and broader independent flight conditions. [Per-flight metrics](m23_dronepropa_altitude_results.json)

## M23.7 Reproduction

Download the six files named in the manifest into one directory. Use the backend Python environment with NumPy and SciPy.

```console
python scripts/benchmark_dronepropa_altitude.py calibrate FLIGHT_DIRECTORY local-freeze.json
python scripts/benchmark_dronepropa_altitude.py evaluate FLIGHT_DIRECTORY local-results.json --freeze local-freeze.json
```

Compare the output with the two committed JSON files. The synthetic regression tests cover causal command use and rejection of duplicated timestamp ticks.
