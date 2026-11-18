# M25.17–M25.21 Composite column compression and flight report coverage

## M25.17 Physical source

The source workbook for *Mesoscale carbon fiber lattices with foam-like weight and bulk strength* contains force and displacement recordings for wound carbon-fiber composite columns. Sheets SFig. 7a–c contain three specimen families at three lengths. Supplementary Tables 4 and 5 distinguish total specimen lengths (50, 85, 150 mm) and gauge lengths (30, 65, 130 mm). The workbook uses family identifiers e1, e2 and e5. The Fig. S7c caption calls the last family three loops, while the workbook and tables identify it as five. Retain the source identifier e5. [Study](https://doi.org/10.1038/s41467-026-72105-4) · [Source workbook](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41467-026-72105-4/MediaObjects/41467_2026_72105_MOESM12_ESM.xlsx) · [Supplement](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41467-026-72105-4/MediaObjects/41467_2026_72105_MOESM1_ESM.pdf)

## M25.18 Measured peak loads

Verify the workbook SHA-256 and specimen/axis headers before reading the records. Convert each trace's maximum recorded load from kgf to N using 9.80665 N/kgf. All nine peaks agree with the experimental entries in Supplementary Table 5 to within 1 N. Each cell represents one released trace. Repeatability and instrumentation uncertainty at the peak remain unquantified.

## M25.19 Transfer across lengths

Compare two load estimates within each family. Euler scaling predicts the 65 mm capacity from the 130 mm peak using the inverse square of gauge length. The second estimate interpolates reciprocal capacity linearly in gauge length squared between the two measured endpoints. Both predict the intermediate length without using its load in the fit. The published outcomes were already available during method selection, so this is a retrospective comparison.

| Workbook family | Measured 65 mm peak (N) | Euler estimate (N) | Reciprocal estimate (N) |
| --- | ---: | ---: | ---: |
| e1 | 228.5 | 331.1 | 279.6 |
| e2 | 836.5 | 721.8 | 509.4 |
| e5 | 1,154.2 | 2,730.2 | 1,503.9 |

Both estimates exceed the measured capacity for e1 and e5. Using either as an allowable would admit loads above the peak sustained in these tests. The results apply to these columns, lengths and fixture. The flight runner models a different load case, arm-root bending under rotor thrust. These compression results supply no installed-frame strength or flight load rating. [Per-trace results and file identity](m25_column_compression_results.json)

## M25.20 Structural verdict in a flight report

The flight API retains its structural monitor's scope and geometry notes. An observed breach of the modeled bending limit yields a structural FAIL. A within-limit bending result or a missing frame leaves installed-frame strength INCONCLUSIVE. The results panel labels the arm bending margin, displays the verdict and scope notes, and identifies saved bending failures in older reports.

## M25.21 Reproduction

With Python 3.11 and openpyxl, download the publisher workbook linked above and run the offline comparison. Compare the resulting JSON with the committed per-trace results.

```console
python scripts/benchmark_column_compression.py 41467_2026_72105_MOESM12_ESM.xlsx reproduced-column-results.json
python -m pytest tests/physics/test_flight_structure_verdict.py tests/physics/test_structural_geometry.py
```
