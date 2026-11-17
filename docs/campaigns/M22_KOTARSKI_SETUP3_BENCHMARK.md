# M22 — Published Setup 3 static propulsion benchmark

This experiment covers the P80 100 Kv motor, Alpha 80 A ESC and G30 × 10.5 propeller described as Setup 3 by Kotarski et al. The authors measured thrust and torque with RCbenchmark 1780 load cells, speed with an optical sensor, and voltage and current at the electrical input. The paper records the P80 family label. The specific motor revision, serials and installation equivalence to the AeroForge capstone are unresolved. [Experiment, section 4.1 and Table 1](https://doi.org/10.3390/aerospace10060528)

## Source admission and split

Harvard Dataverse release 1.0 of *UAV Multirotor Propulsion—Experimental Data* is CC0 1.0. The three original Setup 3 files were retrieved through the official file API, matched to publisher byte counts and MD5s, and pinned by SHA-256 in the [frozen calibration artifact](m22_kotarski_setup3_freeze.json). The publisher's voltage labels are initial battery-cell voltages. [Release metadata and license](https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=doi:10.7910/DVN/J5L2P4)

| Original file | Dataverse file ID | Partition |
| --- | ---: | --- |
| setup3_measurement_3.8V.csv | 6940261 | Calibration |
| setup3_measurement_4.2V.csv | 6940266 | Calibration |
| setup3_measurement_4.0V.csv | 6940259 | Held-out sweep |

The shape is 11 PWM levels and four observations per level in each file. The four readings at a PWM are repeated observations in a single sweep. The 4.0 V file is a separate experimental sweep on the published setup. This is a retrospective benchmark. AeroForge uses none of the paper's fitted coefficients, which were derived from the 4.0 V data.

## Frozen calibration and score

Create a separate `MotorSpec` for the source apparatus. At each PWM from 1200 to 2000 µs, use the median of the four readings from each calibration sweep for RPM, thrust, current and measured supply voltage. Set the two model voltage planes to the source's nominal 12-cell initial settings, 45.6 and 50.4 V. The measured voltage droops during each sweep and is retained with the knots. The existing AeroForge `PowertrainDataset` interpolates thrust by measured RPM and current by measured RPM and measured bus voltage. It treats the calibration planes as nominal, so differences include this voltage-plane approximation. Torque is preserved as a source observation.

Score every rotating held-out sample inside the RPM range common to both calibration sweeps and between the nominal voltage planes. Report excluded samples, source CSV line numbers and unweighted residual MAE, RMSE, bias and maximum absolute error. Command levels 1000 and 1100 µs are stationary baseline readings and remain visible in the report. An observed or predicted value above the published 80 A ESC rating yields a sampled-limit failure. For this experiment, the published record supplies no independent uncertainty budget or decision-specific error tolerance. Acceptance is inconclusive in the absence of a sampled limit breach. The comparison addresses static conditional thrust and current for the published apparatus.

## Reproduce

Download the original-format files into DATA_DIR from `https://dataverse.harvard.edu/api/access/datafile/FILE_ID?format=original` using the listed file IDs. From the repository root with Python backend dependencies installed, run the following commands.

```console
python scripts/benchmark_kotarski_setup3.py calibrate DATA_DIR local-freeze.json
python scripts/benchmark_kotarski_setup3.py evaluate DATA_DIR local-holdout.json --freeze local-freeze.json
```
