# M21.6–M21.10 — Transporter module voltage and temperature benchmark

## M21.6 Hardware and source

Paw and Ang tested one LiPo module assembled from four six-cell TP5000-6SR80 packs in series. The 24S1P module was loaded by a BLU400C. Thermocouples measured the four pack temperatures and ambient temperature under the study's forced-air fixture. The study associates the pack sensors with surface hot spots. The workbook contains 378 numbered discharge cycles. The pinned file is `UUT2_BatteryModule_Discharge.xlsx`, Figshare file ID 37983774, 9,397,987 bytes, SHA-256 `a4679465b35455ca429519fbc47f04f6e42bea608e0de12b978d482873456205`. The unchanged workbook stays outside the repository. [Study and Tables 2 and 5](https://doi.org/10.1016/j.est.2023.107493) · [Publisher dataset, CC BY-NC-ND 4.0](https://doi.org/10.25447/sit.21301188.v1)

## M21.7 Chronological split

Use cycles 1–50 for fitting and hold cycles 151–200 and 329–378 out as separate mid-life and late-life cohorts. Other cycles remain unused. Require finite samples, the documented column identities, and an uninterrupted 2 s sample interval from time zero. Cycle 31 failed the initial sample-clock gate. Use 5 Ah nominal capacity and integrate measured current for the model's charge state. Withhold voltage scores beyond the largest calibrated cumulative charge. Keep any observed limit crossing in an admitted source cycle, including cycles outside voltage support.

## M21.8 Frozen electrical models

Fit AeroForge's OCV-plus-fixed-resistance model for the module and for each measured pack voltage. Fit the same OCV/series form with one additional polarization state using a low-pass filter of measured current, initially zero. The candidate time constants are 2, 5, 10, 20, 40 and 80 s. Fits use nonnegative terms, a monotone OCV curve, and the published 4.2 V/cell maximum charge voltage. Voltages are fit independently, so pack predictions do not impose equality with the separately instrumented module channel. The fitted curves and time constants are effective model parameters. The selected 2 s polarization time is at sample cadence, which limits physical identification.

## M21.9 Frozen thermal models and limits

Fit a first-order surface temperature model initialized at each measured starting temperature. It uses measured ambient temperature, a fitted cooling rate from the 150–300 s low-current segment, and a heat source proportional to measured current squared. Compare instantaneous heating and a filtered heat source with time constants of 0, 2, 5, 10, 20 and 40 s. Choose gains and time constants using early cycles. Also score constant initial-temperature persistence. The two electrical and thermal models share the recorded current. The thermal prediction does not modify electrical resistance or capacity.

Use the study's strict sampled termination comparisons from Table 5. A module reading below 80.0 V, a pack reading below 19.8 V, a pack above 70 °C, or discharged capacity above 5 Ah produces a failure. The 400 A continuous nameplate current also serves as a measurement check. Report observed and modeled crossing counts, misses and false alarms. Current is a shared replay input. Compare net module energy by integrating measured current times voltage; the predicted energy uses predicted voltage over the same source timestamps. The sample times bound what can be inferred about crossings and do not reconstruct equipment reaction time. The models receive measured current and ambient temperature. The resulting test cannot establish prospective current demand, usable mission endurance or acceptance across new hardware.

## M21.10 Reproduction

Download file 37983774 from the publisher using `https://api.figshare.com/v2/file/download/37983774`. Keep it outside the repository. The offline benchmark uses the normal backend Python dependencies plus `openpyxl` for read-only import. The recorded reproduction used Python 3.11.9, NumPy 2.4.6, SciPy 1.15.3 and openpyxl 3.1.5.

```console
python scripts/benchmark_sit_module.py calibrate WORKBOOK local-fit.json
python scripts/benchmark_sit_module.py evaluate WORKBOOK local-results.json --freeze local-fit.json
```

The canonical frozen fit SHA-256 is `f959786b7d37ad82dc84780331fbd1363b63f2f109cd0bf0c4fb6cd7adbb4764`, recorded before reading the selected later-cycle numerical data. This comparison uses independent published physical measurements in a retrospective split on one repeatedly cycled module. Independent replicates, a calibrated uncertainty budget and reviewer acceptance are still required for M21.
