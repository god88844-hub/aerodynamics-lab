# M24.12–M24.16 NeuroBEM body-axis force benchmark

## M24.12 Published same-airframe measurements

Use the University of Zurich Robotics and Perception Group's processed flight segments from the NeuroBEM study. The experimental platform used an Armattan Chameleon 6-inch frame, Hobbywing XRotor 2306 motors, 5-inch three-blade propellers, BetaFlight and motion capture in a hangar. The paper gives a mass of 752 g while the archive README gives 772 g. This comparison scores specific force in m/s², so it requires no choice between those mass values. [Project and paper](https://rpg.ifi.uzh.ch/NeuroBEM.html) · [Publisher archive and official test set](https://download.ifi.uzh.ch/rpg/NeuroBEM/)

The publisher combines onboard IMU and inferred motion-capture data to estimate body-axis acceleration. On the calibration flights the released acceleration agrees with the body-frame derivative of inertial velocity after removing gravity, with each component's median absolute difference below 0.1 m/s². Use the released values as body-axis specific force. Use measured body velocity as an indoor proxy for air-relative velocity, with no independent ventilation measurement. The bench also uses processed measured rotor rates in rad/s. It answers a conditional force-model question with these inputs supplied at each time step.

## M24.13 Freeze calibration and reserve the official test set

Calibrate on all available processed segments of `2021-02-18-16-43-54`, `2021-02-18-17-20-37`, `2021-02-23-10-52-00` and `2021-02-23-14-24-07`. The group covers linear oscillation, CPC and lemniscate maneuvers in the publisher's flight manifest. Reserve every segment named in the publisher's `testset.txt` before opening its sample values. A flight ID may appear in only one partition. Calibration uses equal total weight for each flight and weights samples by their time support within each flight. The held-out score uses elapsed time weights, since the release contains segments sampled at different rates.

## M24.14 Predeclared comparisons

Fit nonnegative coefficients by least squares on the calibration flights. The thrust-only baseline supplies body-z specific force proportional to the sum of squared rotor angular speeds. The airframe baseline adds the same isotropic quadratic drag law used by AeroForge. A third candidate adds an in-plane term proportional to body x/y velocity and the sum of rotor angular speeds, opposing translation. Rotor angular speeds are scaled by 1000 rad/s to condition the fit. Use fixed coefficients in scoring and report per-axis and vector RMSE for each holdout and all holdouts, with speed bands below 5, 5 to below 10, and at least 10 m/s.

The freeze contains the fitted coefficients and hashes of each calibration segment. The evaluation records the hashes of the previously unopened holdout segments. The benchmark uses the same physical vehicle across these flights. Acceptance of full-aircraft predictions, end-to-end flight control, component-specific thrust, and thermal behavior requires distinct evidence. No physical acceptance criterion is set for these retrospective scores.

## M24.15 Held-out results

The published test set contains 13 segments from 13 distinct recorded flights, with 215,829 samples, 539.54 seconds of recorded motion and a peak recorded speed of 17.72 m/s. RMSE combines errors along all three body axes.

| Recorded speed | Samples | Thrust-only RMSE (m/s²) | Airframe-drag RMSE (m/s²) |
| --- | ---: | ---: | ---: |
| All | 215,829 | 3.289 | 1.833 |
| Below 5 m/s | 120,726 | 0.876 | 0.710 |
| 5 to below 10 m/s | 62,422 | 3.404 | 1.840 |
| At least 10 m/s | 32,681 | 6.817 | 3.722 |

Quadratic drag lowered RMSE on every holdout. The largest remaining axis error was body z, at 1.528 m/s² overall and 3.102 m/s² at or above 10 m/s. The fitted coefficient for the added in-plane rotor drag term was zero before the test split was scored. This candidate therefore matched the quadratic baseline. These results use observed rotor speeds and velocity. Predicting thrust and trajectory from commanded speeds requires separate validation, and M24's full aerodynamic and thermal acceptance remains open.

## M24.16 Reproduce from the publisher files

Download `processed_data.zip` and `testset.txt` from the [University of Zurich archive](https://download.ifi.uzh.ch/rpg/NeuroBEM/). Extract the publisher's CSVs, and place `testset.txt` in the same directory as the `merged_*.csv` files. The evaluation uses the archived calibration parameters. Compare the SHA-256s and numeric scores with the committed JSON. The fixture tests cover time weighting and body-axis convention.

```console
python scripts/benchmark_neurobem_force.py PATH_TO_CSV_DIRECTORY --freeze reproduced-freeze.json
python scripts/benchmark_neurobem_force.py PATH_TO_CSV_DIRECTORY --evaluate docs/campaigns/m24_neurobem_force_freeze.json --results reproduced-results.json
python -m pytest tests/physics/test_neurobem_force.py
```

The fitted coefficients and comparison plan were committed as `b4fd3a3d59816ed329c3e9e568cc7b711e8803f5` before downloading the reserved segments. The archive identified the measured dataset by a 657,316,788-byte transfer and ETag `272ddbb4-5c4b60dad1746`. The individual SHA-256s identify the exact extracted records used for calibration and scoring.
