# M25.2–M25.6 — Physical rotor-order fault indicator

## M25.2 Source and whole-flight split

Baldini and colleagues published measured hexarotor flights with higher-frequency IMU logging and separately measured motor speeds. Use the unchanged CC BY 4.0 MAT recordings from release v1. The [frozen calibration record](m25_uav_fd_rotor_order_freeze.json) pins source byte lengths and SHA-256. The healthy calibration flights are `NO_FAULT1.mat` and `NO_FAULT4.mat`. The healthy holdout is `NO_FAULT5.mat`. The remaining holdouts are the two publisher-labeled faults listed in the frozen source manifest. The evaluation uses whole recordings. The method and thresholds were set before inspecting numerical observations in the holdouts. [UAV-FD source](https://zenodo.org/records/7648996) · [Test campaign paper](https://doi.org/10.1109/ICUAS57906.2023.10156060)

## M25.3 Timebase and physical support

Use `IMU_0` three-axis acceleration, six independent ESC speed logs, and the controller's estimated-altitude channel. Interpret each field against the original embedded column dictionary. Compare samples by native `TimeUS`. Divide each recording into successive two-second windows. Each window needs 300 IMU points and no IMU gap over 25 ms, including either window edge. Each ESC and altitude stream needs five samples and gaps of at most 0.5 s. Estimated altitude must be at least 1 m throughout the available readings. Every rotor-speed sample must be within 3,600–7,800 RPM. The holdout window's median motor speed must also lie within the two healthy calibration flights' observed window medians.

## M25.4 Physics-informed score and baseline

Remove the best-fit linear trend on each acceleration axis. Estimate spectral power on the nonuniform timestamps using a Lomb–Scargle periodogram. Consider integer frequency bins within 4 Hz of the median observed order-one frequency of any of the six motors, using the measured RPM divided by 60. Enforce a guard of 40% of the median IMU sampling frequency. Sum power across axes and convert the largest candidate bin into an amplitude proxy. Normalize by the square of median RPM relative to 6,000 RPM, as a simple rotating-imbalance scaling. Overlapping motor frequencies preclude attributing an alert to an individual motor. The baseline uses the vector RMS of the same detrended acceleration windows.

## M25.5 Frozen decision and evaluation

For each score use the higher-interpolated 95th percentile of the pooled eligible healthy calibration windows. A flight needs at least six eligible windows and raises an alert on two successive above-threshold windows. Missing windows break a run of exceedances. Report every exclusion reason, whether each fault was detected, and whether the healthy recording raised a false alert. A two-window decision says nothing about latency from an in-flight fault onset. In this dataset the physical labels describe the recording condition. The evaluation tests an offline vibration indicator and does not establish fault isolation, structural stiffness or airworthiness.

## M25.6 Results and reproduction

The [frozen method and thresholds](https://github.com/god88844-hub/aeroforge/commit/67f7245dac40faa193f7f7ba7b89bd6dc2717cb0) used 41 eligible calibration windows. The comparable holdout windows had median motor speed between 5,377.5 and 6,049.5 RPM. [Machine-readable results](m25_uav_fd_rotor_order_results.json)

| Publisher recording | Eligible windows | Rotor-order alert | Broad acceleration RMS alert |
| --- | ---: | --- | --- |
| Healthy | 23 | No alert | False alert |
| Fault M3 | 34 | Missed | Missed |
| Fault M4 | 31 | Detected | Missed |

The rotor-order indicator exceeded its threshold in 22 of the 31 M4 windows and in zero M3 windows. The acceleration baseline exceeded its threshold in the fault files on isolated windows, which did not satisfy the consecutive-window rule. The missed physical fault leaves this indicator unsuitable as a standalone fault clearance. Results cover three held-out recordings from this apparatus. They do not estimate fleet-level detection probabilities.

Save the original MAT files in DATA_DIR and use the repository Python environment. The raw flight files stay outside Git.

```console
python scripts/benchmark_uav_fd_rotor_order.py calibrate DATA_DIR local-freeze.json
python scripts/benchmark_uav_fd_rotor_order.py evaluate DATA_DIR local-results.json --freeze local-freeze.json
```
