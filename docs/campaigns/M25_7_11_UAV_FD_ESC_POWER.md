# M25.7–M25.11 — ESC power and vibration fault indicators

## M25.7 Source and split

Use the [UAV-FD hexarotor recordings](https://zenodo.org/records/7648996) and the same two healthy calibration flights as the [rotor-order vibration benchmark](M25_2_6_UAV_FD_ROTOR_ORDER.md). The earlier three test flights informed selection of the electrical observable. They are excluded from the calibration and this evaluation. This batch reserves the previously unopened `NO_FAULT6.mat`, `FAULT_M1_10.mat`, and `FAULT_M5_10.mat` by original publisher bytes and SHA-256. [Test campaign paper](https://doi.org/10.1109/ICUAS57906.2023.10156060) · [Frozen manifest](m25_uav_fd_esc_power_freeze.json)

## M25.8 Electrical load at observed RPM

Use simultaneous voltage, current, and RPM within each ESC's own log. Use nonoverlapping two-second windows on the controller timebase, with at least five samples per required stream and gaps of at most 0.5 s including edges. Require estimated altitude at least 1 m and estimated roll and pitch within ±20 degrees. Discard windows with zero or negative voltage or current, any rotor outside 3,600–7,800 RPM, or window median RPM outside the healthy calibration support.

Compute the median of each ESC's electrical power divided by the cube of its measured RPM relative to 6,000 RPM. This is a simple propeller-load proxy. It absorbs motor, ESC and atmospheric effects and cannot identify aerodynamic torque or thrust on its own. The comparison baseline uses unadjusted median electrical power. Each model divides a channel by its own healthy reference median, then uses the largest deficit relative to the across-ESC median within that window.

## M25.9 Alarm rule and two-signal comparison

Freeze the higher-interpolated 95th percentile of the pooled eligible healthy-window deficits for each method. Each recording needs at least six eligible windows. Raise an electrical alert when the same ESC leads a deficit above the fixed threshold in two adjacent windows. An excluded window breaks the run. Report the ESC telemetry channel without assuming rotor location from a channel index.

Also score the earlier frozen rotor-order vibration rule on the three new files. Use a recording-level alert if either the regulated electrical or vibration score alerts, and leave a negative combined result inconclusive if either channel lacks coverage. The two signals use separate window qualification, so the combination compares flight decisions without assuming paired alert timestamps.

## M25.10 Evidence boundary

Report declared fault detections, misses, false alerts and exclusion counts per recording. This is a retrospective test across measured flights on one apparatus. Its scope is the offline fault indicator. Applied loads, structural strength, and real-time fail-safe response remain separate acceptance requirements.

## M25.11 Results and reproduction

The source split, thresholds and stated alarm rules were [frozen before parsing the three holdouts](https://github.com/god88844-hub/aeroforge/commit/0fd76d969d98c8bc188233313b39abfdf1273f60). The first scoring implementation matched `NO_ALERT` with a string suffix intended for positive alerts. The corrected scorer recognizes the explicit positive verdicts and reproduces the frozen decision rule. Source data, window eligibility, thresholds and individual detector outputs are unchanged. [Machine-readable results](m25_uav_fd_esc_power_results.json)

| Published source | Eligible electrical / vibration windows | Speed-normalized power | Raw power | Vibration | Combined |
| --- | ---: | --- | --- | --- | --- |
| Healthy | 26 / 26 | False alert | No alert | No alert | False alert |
| Fault M1 | 41 / 41 | Missed | Missed | Missed | Missed |
| Fault M5 | 36 / 36 | Missed | Missed | Detected | Detected |

The electrical rule added a false alert and recovered no missed fault in this held-out split. This is evidence against enabling the combined rule as a standalone clearance check. Results are based on three recordings from one rig and do not establish a population false-alarm rate.

Place the publisher's unchanged MAT files in DATA_DIR and use the repository Python environment.

```console
python scripts/benchmark_uav_fd_esc_power.py calibrate DATA_DIR local-freeze.json
python scripts/benchmark_uav_fd_esc_power.py evaluate DATA_DIR local-report.json --freeze local-freeze.json
```
