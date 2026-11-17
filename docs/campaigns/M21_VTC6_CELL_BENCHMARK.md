# M21.1–M21.5 — VTC6 single-cell physical benchmark

## M21.1 Published source and hardware match

Bills et al. exercised Sony–Murata US18650VTC6 cells on a BioLogic BCS-815 with an Arbin cell holder. The experiment applies an aircraft-derived electrical duty cycle to cells on a test bench. The baseline uses 54 W for 75 s, 16 W for 800 s, then 54 W for 105 s. VAH01 and VAH17 are distinct cells of the same type under the same baseline protocol. [Experiment and protocol](https://doi.org/10.1038/s41597-023-02180-5)

Obtain the three original files from release v3, published under CC BY 4.0 by Bills et al., Carnegie Mellon University. The script verifies every original against its pinned SHA-256. The publisher's versioned API also exposes the original byte lengths and MD5 values. [Dataset and license](https://doi.org/10.1184/R1/14226830.v3) · [Release metadata](https://api.figshare.com/v2/articles/14226830/versions/3)

| Original filename | Publisher file ID | Use |
| --- | ---: | --- |
| VAH01.csv | 26855147 | Initial reference performance test |
| VAH01_impedance.csv | 40183168 | Initial publisher-derived one-second impedance |
| VAH17.csv | 26855144 | Five early baseline discharge traces from a separate cell |
| VAH27.csv | 26855141 | Separate baseline cell reserved for the follow-up sampling protocol |

## M21.2 Source rows and selection

The evaluator reads original timestamps, cell voltage, signed current, discharged-charge counter, temperature and tester step markers. It treats each consecutive block of a tester cycle and step as its own segment. The first five complete normal charge/CV/rest/takeoff/cruise/landing/rest signatures at consecutive tester cycle numbers define the sample. A mission with an unexpected phase duration, an interval outside the frozen limits, or malformed measurements aborts the comparison. Every recorded discharge sample in the selected phases is included, including switching transients. The result records 1-based CSV line numbers, counting the header as line 1.

## M21.3 Frozen characterization

Capacity comes from the VAH01 initial C/5 discharge to 2.5 V using the source charge counter relative to the first loaded sample. The resistance is the mean of the first published 1-second measurements at 20% and 60% depth of discharge. The voltage curve uses the initial C/5 steps 3, 5 and 7 at 0.55–0.66 A. Undoing the fitted resistive sag gives an OCV proxy sampled at 5 percentage-point SOC intervals. The recorded C/5 terminal voltage still contains polarization and recovery effects. [Frozen parameters and original hashes](m21_vtc6_freeze.json)

## M21.4 Comparison protocol

The forecast uses AeroForge's existing one-cell OCV plus fixed resistance model. At each source timestamp, it solves for voltage and current at the publisher's nominal phase power using the high-voltage solution. The next SOC uses the previous predicted current and elapsed time by coulomb counting. Each mission starts from 100% SOC, an assumption based on the charge protocol. Measured current, voltage and temperature are used for scoring or evidence checks. Measured energy integrates the original voltage-current product within each phase, while modeled energy is the commanded power over the same sampled phase duration.

Report sample-weighted voltage and current MAE, RMSE, signed bias and maximum absolute discrepancy separately by mission and phase and across the five missions. Compare sampled measured and modeled voltage against 2.5 V, measured temperature against the study's 70 °C stop threshold, and sampled current against 30 A (10C at the cited 3 Ah nominal rating). Experiment-specific application tolerances and instrument uncertainty budgets are absent, so the pack acceptance verdict is inconclusive. The public holdouts were withheld from AeroForge fitting. The plans were frozen before evaluating their respective cells. This is a retrospective analysis with no third-party blinding or preregistration.

The initial [frozen VAH17 plan](https://github.com/god88844-hub/aeroforge/commit/31bb31543d0807c884608950c8e191b5137ff1e6) permitted intervals up to 2 s. It stopped at CSV line 18893 in tester cycle 0. The interval from the preceding takeoff sample was 10.000000475 s. This is a sampling rejection, so VAH17 has no score under that plan.

The separately frozen sampled-point plan reserves VAH27 and permits positive intervals up to 11 s to accommodate 10 s logging. The VAH01 model, phase signature, nominal-duration check (within 2 s), sample inclusion and scoring rules carry over. Evaluation uses measured time and phase only to schedule the published power input. Its scope is pointwise agreement at the recorded cadence. Errors within unsampled intervals, short limit excursions and transient timing remain unresolved.

## M21.5 Reproduction

From the repository root in the backend Python environment, place the publisher files together in a local directory. Replace DATA_DIR with that directory.

```console
python scripts/benchmark_vtc6.py calibrate DATA_DIR local-freeze.json
python scripts/benchmark_vtc6.py evaluate DATA_DIR local-vah17.json --freeze local-freeze.json
python scripts/benchmark_vtc6.py evaluate-sampled DATA_DIR local-vah27.json --freeze local-freeze.json
```

This comparison covers five early laboratory loads on one held-out cell. Those runs share hardware and are correlated. The model has no thermal, aging or multi-cell pack behavior. The recorded load profile provides no evidence of aircraft endurance or installed battery protection behavior. Pack-level acceptance requires the [qualified laboratory protocol](M21_BATTERY_PHYSICAL_ACQUISITION.md).
