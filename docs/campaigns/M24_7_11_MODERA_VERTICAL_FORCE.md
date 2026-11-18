# M24.7–M24.11 — Vertical force under uneven rotor commands on the MODERA bench

## M24.7 Matched static fixture

The Universitat Politècnica de València MODERA v1 release pairs CAD geometry with force-balance observations of the same small quadcopter. The mounted vehicle was tested in still air in an anechoic chamber. Balance-axis Fz points upward at every heading. Rotor command order is front right, rear left, front left, rear right. This comparison uses Fz. The publisher also provides forces and moments in a balance frame that changes orientation relative to the vehicle. The CC BY-SA 4.0 dataset is limited to research and education by its publisher. [MODERA v1 data and terms](https://doi.org/10.5281/zenodo.17457069)

## M24.8 Admit common commands and reserve whole throttle pairs

The publisher recorded 133 command rows at each of seven fixture headings. Match commands to their published setpoint grid within 1e-8. Three rows are off-grid, and 18 additional observations lack a matching command at all seven headings. The remaining 130 configurations have seven measurements each. Use the median Fz as the prediction target and retain the force range across repeated headings as a variability diagnostic.

Reserve six whole low/high throttle pairs, including all six motor arrangements and all seven heading repeats for each pair. This gives 36 held-out commands and 252 measured repetitions. The other 94 commands provide seven equal-throttle and 87 mixed-throttle calibration configurations. The split and calibration were committed before numerical scoring of reserved Fz. [Frozen protocol and fitted coefficients](m24_modera_vertical_force_freeze.json) · [Freeze commit](https://github.com/god88844-hub/aeroforge/commit/30fd93a223b91d7e8c4812b958a313c68bc978eb)

## M24.9 Calibrate the force comparisons

The additive reference predicts half the sum of the Fz medians for the two matching equal-throttle commands. Estimate an empirical correction proportional to squared throttle separation. Compare a pooled coefficient with separate coefficients for adjacent and diagonally opposite high-command rotors. These fixture terms describe command-to-force residuals. The source provides neither isolated single-rotor measurements nor measured rotor speed for this comparison, so the fit cannot identify the aerodynamic cause.

## M24.10 Score reserved commands

| Predictor | Mean absolute error (N) | Mean signed error (N) | Maximum absolute error (N) |
| --- | ---: | ---: | ---: |
| Additive | 0.870 | −0.848 | 2.662 |
| Pooled correction | 0.322 | −0.041 | 1.432 |
| Separate arrangement corrections | 0.321 | −0.041 | 1.414 |

The pooled correction reduced aggregate mean absolute error by 63%. Separate adjacent and diagonal coefficients changed aggregate MAE by less than 0.001 N. The between-heading Fz range had a median of 1.281 N across held-out commands, larger than either corrected model's mean absolute error against the configuration medians. Repeats capture variability of this setup, and the experiment provides no calibrated prediction intervals or flight acceptance thresholds. The conclusion applies to static vertical force on this mounted quadcopter for the tested commands. [Per-command results and coverage](m24_modera_vertical_force_results.json)

## M24.11 Reproduce the comparison

Download the original `experimental_data.zip` from the publisher and extract its `forces.zip` member without unpacking the acoustic recordings. Zenodo lists outer archive MD5 `7db17fe4e723571fcffd2e7da6fed637`. This benchmark retrieved an HTTP byte range containing the member and directory, verified the member and seven nested CSV CRCs, and pinned the original 57,735-byte `forces.zip` by SHA-256. The full outer archive MD5 was not verified for the byte-range retrieval. [Publisher archive](https://zenodo.org/records/17457069/files/experimental_data.zip?download=1)

```console
python -c "from pathlib import Path; from zipfile import ZipFile; Path('forces.zip').write_bytes(ZipFile('experimental_data.zip').read('forces.zip'))"
python scripts/benchmark_modera_vertical_force.py calibrate forces.zip local-freeze.json
python scripts/benchmark_modera_vertical_force.py evaluate forces.zip local-results.json --freeze local-freeze.json
```

Compare both files to their committed counterparts. Synthetic regression tests check canonical command matching and that calibration skips reserved numerical Fz values.
