# M24.2–M24.6 — APC Thin Electric 10×5 axial propeller response

## M24.2 Publisher source and hardware

UIUC Volume 1 reports wind-tunnel measurements for the APC Thin Electric 10×5. It tabulates thrust coefficient \(C_T\), shaft power coefficient \(C_P\) derived from measured torque, efficiency and advance ratio \(J=V/(nD)\). Here \(V\) is axial freestream speed, \(n\) is revolutions per second, and \(D\) is propeller diameter. The catalog separately lists APC Sport propellers. Use the Thin Electric series and the matching static file already tracked in AeroForge. [UIUC Volume 1 source and methodology](https://m-selig.ae.illinois.edu/props/volume-1/propDB-volume-1.html)

## M24.3 Freeze the sweep split

Use the full 4,005 RPM calibration sweep and combine the 6,707 and 6,710 RPM sweeps into a nominal 6,708.5 RPM plane. Use the 6,707 RPM rows below \(J=0.388\) and the 6,710 RPM rows at or above the seam. Hold out the 5,000, 6,005 and 6,018 RPM sweeps as whole records. Reserve the 4,993 RPM run from scoring because its contents were inspected during source selection. The splits, hashes and scoring rule were fixed before successful evaluation. The first ingestion attempt rejected an HTML response for the 6,005 RPM file. The corrected freeze pins the publisher's plain-text response. [Frozen protocol](m24_uiuc_axial_sweeps_freeze.json) · [Freeze commit](https://github.com/god88844-hub/aeroforge/commit/9633e7907e0222fd7b383ad54d8fb08559b4bc18)

## M24.4 Model and comparisons

Interpolate each measured coefficient linearly within each calibration plane, then blend the two plane predictions by RPM. Score only within the common calibration range of \(J=0.146\) to \(0.684\) and RPM 4,005 to 6,708.5. Compare against an equal blend of the two planes, independent of RPM, and against the matching static coefficients interpolated by RPM. The evaluation preserves the sign of thrust and uses absolute coefficient errors because relative errors diverge near zero thrust.

## M24.5 Held-out observations

The model scored 42 observations across the three held-out sweeps. Five observations fell outside the calibration range and were excluded from all three comparisons. Errors below are dimensionless. [Aggregate and per-sweep results](m24_uiuc_axial_sweeps_results.json)

| Predictor | Mean absolute \(C_T\) error | Mean absolute \(C_P\) error | Thrust sign disagreements |
| --- | ---: | ---: | ---: |
| Advance ratio and RPM | 0.0006850 | 0.0003007 | 1 |
| Advance ratio only | 0.0017483 | 0.0007095 | 0 |
| Static coefficients | 0.0488816 | 0.0091922 | 1 |

One supported observation had nonpositive thrust. It measured \(C_T=-0.0001\) at 6,018 RPM and \(J=0.671\), where the RPM-aware model predicted positive thrust. The cohort therefore gives limited evidence near the thrust zero crossing. Report interpolation accuracy for this propeller in axial freestream. Engineering acceptance remains inconclusive because the benchmark has no predeclared error tolerances or calibrated uncertainty. The data do not cover installed propulsion, vehicle dynamics, rotor interactions, or off-axis flight.

## M24.6 Reproduction

Download the six named sweep files from the publisher's `volume-1/data/` directory into a local directory. Keep the bytes as downloaded. The script checks the source hashes and parses the repo's existing matched static table, normalizing the tracked file's line endings.

```console
python scripts/benchmark_uiuc_axial_sweeps.py SWEEP_DIRECTORY local-results.json
```

Compare the output to the committed JSON. The focused tests exercise out-of-range rejection, signed interpolation, checksums and row ordering using synthetic inputs.
