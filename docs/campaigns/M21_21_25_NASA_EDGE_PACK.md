# M21.21–M21.25 NASA Edge 540 pack voltage under recorded load

## Physical recording and scope

NASA released six sets of ground recordings from an Edge 540 aircraft in an instrumented chamber. Its powertrain uses two pairs of series-connected battery packs. Analyze the voltage and current channels named LLF20V and LLF20C at the same installed battery position across records. The authors describe separate motor and battery current sensors. The first archive's 40 V channel minus its two 20 V channels is identically zero in the forward branch, so that voltage sum supplies no independent confirmation. The publisher archive contains time series without pack serial numbers or per-channel calibration certificates. [NASA archive and citation](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/) · [NASA ground verification study](https://ntrs.nasa.gov/citations/20190025952)

## Calibration, reserve and scoring plan

Use every record in Set1 for fitting. Reserve all records in Sets 2–6. Hash the original archive and each MAT record. Each eligible record must have finite current and voltage on a common 200 Hz clock. Use consecutive complete one-second blocks and record ineligible files. Each mean current carries its sign. Each mean voltage is a terminal observation. The reference energy integrates the native current–voltage product.

For each run, anchor voltage and inputs using the first five seconds. Estimate subsequent block voltage from the recorded load. The baseline subtracts a nonnegative coefficient times the change in accumulated Ah. The second model also subtracts a nonnegative resistance times the change in current. Fit by least squares with equal total weight per calibration record. Use no further observed voltage to update either prediction. This compares a linear charge model with AeroForge's first-order resistance-sag assumption over the recorded workload. It produces a conditional voltage replay.

Report mean absolute and root mean square voltage error, largest optimistic error, error at the minimum one-second voltage and net energy error per run. Summarize median whole-run MAE, the number of runs improved by sag, and the worst optimistic error even if a run contradicts the model. These are descriptive metrics. Charge reserve, initial SOC, physical cutoff, thermal behavior, instrument uncertainty and pack-specific endurance acceptance require additional evidence.

## Results

The [model and scoring freeze](https://github.com/god88844-hub/aeroforge/commit/b82b9b3efcfee3ea23ed412f0f5823e765b3237b) used nine runs. Its fitted resistance was 0.05686 Ω at the monitored installation. All 44 reserved runs met the declared channel and timestamp requirements. They contributed 111,765 scored seconds (31.05 h), with one-second mean currents from −2.96 to 53.16 A.

| Across 44 reserved runs | Charge only | Charge and sag |
| --- | ---: | ---: |
| Median run voltage MAE | 0.758 V | 0.279 V |
| Median absolute run net energy error | 5.501 Wh | 1.129 Wh |
| Largest optimistic voltage error | 30.393 V | 30.836 V |

Including sag reduced voltage MAE on every reserved run. The largest error in each model occurred in HIRF38. Its source channel recorded a one-second mean of −12.453 V, while the sag model predicted 18.383 V. This is the only reserved record with a negative one-second mean pack voltage. It remains in all scores. The archive does not establish the physical cause of this reading. Voltage behavior there and the full operating envelope remain inconclusive. Net energy uses the same recorded current as the prediction and shares its uncertainty. [Run-by-run scores and source hashes](m21_edge_pack_results.json)

## Reproduction

Download the [original ZIP](https://phm-datasets.s3.amazonaws.com/NASA/15.+HIRF+Battery+Data+Set.zip) and keep it compressed. The script verifies its SHA-256, reads the nested archives and uses NumPy and SciPy. The first command fits only Set1. The second applies the published coefficient file only to Sets 2–6.

```console
python scripts/benchmark_edge_pack.py publisher.zip reproduced-freeze.json
python scripts/benchmark_edge_pack.py publisher.zip reproduced-results.json --evaluate docs/campaigns/m21_edge_pack_freeze.json
python -m pytest tests/physics/test_edge_pack.py
```
