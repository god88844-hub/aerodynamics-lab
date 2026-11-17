# M16 — Public physical flight-data research, provenance and first ingested trace

**Research date:** 2026-11-17. **Mission:** Make AeroForge simulation accuracy
approach independent physical measurements, **only within demonstrated,
bounded operating conditions**. Physical-equivalence claims require a
held-out, matched physical model and independently checked error/uncertainty;
availability of a public dataset alone is not proof.

## 1. New external *measured* evidence in the repository

Data copied byte-for-byte from the published research repository
[AdamDony/quadplane-px4-flight-data](https://github.com/AdamDony/quadplane-px4-flight-data),
under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), with
[original attribution and scientific limitations](../data/benchmarks/public/quadplane_2022/README.md).
This is a reported 2022 actual VTOL quadplane flight, not simulation telemetry
and not AeroForge's test vehicle.

File: `data/benchmarks/public/quadplane_2022/BATT.csv`, from original commit
`122ceb2cf3913725eef5cd9171a9779220c63335`, original Git blob
`1e434d8edcc26d5dfc016a557e24d5c44cffff3c`.

Verified actual source content (1,442 rows, checksum and field validation):
- Filtered pack-voltage values: 21.647–25.310 V.
- Filtered pack-current values: 0.264–72.452 A.
- Highest sampled V×I: ~1,596.97 W. **Not** an integrated energy result.
- Flight-controller discharged-charge counter: ~53.711 mAh at first sample,
  ~2,694.643 mAh at final sample; difference ~2,640.931 mAh.
  The source's headline 2,695 mAh is the final cumulative counter value,
  not the difference over these rows.
- The 0.264093 remaining-capacity fraction decrease and ~2,640.931 mAh
  discharge-counter increase imply an approximately **10,000 mAh configured
  controller capacity**. The two channels are related controller estimates,
  so this ratio is **not an independent measurement of pack capacity**.

The source's own dictionary states no per-row BATT timestamps; the original
log session is about 24.02 minutes and the actual airborne portion about
six minutes. We do **not** synthesize times, integrate measured Wh over guessed
time, or align this log to AeroForge flight trajectories. No pack serial,
pack-internal resistance, instrument calibration uncertainty or exact
AeroForge-equivalent hardware is independently available.

Result: `PUBLIC_PHYSICAL_OBSERVATIONS_AUDITED_NOT_MODEL_VALIDATION`.
Physical model equivalence: **NOT ESTABLISHED**.

## 2. Scientific dataset inventory

A machine-readable register lives in
`data/benchmarks/public_sources.json`, accessible in the API/UI.
Only the actual PX4 battery CSV above was imported in M16. All other
repositories are linked as *candidates*, **not** falsely marked ingested.

| Dataset | Verifiable availability | Appropriate use | Restriction |
| --- | --- | --- | --- |
| [UIUC Propeller Database](https://m-selig.ae.illinois.edu/props/propDB.html) | Published wind-tunnel tables; AeroForge already has APC static data | Propeller method verification and narrowly bounded independent benchmarks | Different prop geometries/rotor conditions cannot certify an assembled quad |
| [CMU AirLab DJI Matrice 100](https://doi.org/10.1184/R1/12683453) | Published 209 outdoor flights, raw logs, processed per-flight CSV, CC BY 4.0 | Time-stamped V/I, wind, position, attitude, payload/speed/altitude energy baseline | Different quad/motors/pack; raw archive not downloaded or byte-verified during this milestone |
| [Quadplane VTOL telemetry](https://github.com/AdamDony/quadplane-px4-flight-data) | Copied, license/commit/blob checked | Electrical-range observation and source-ingestion integrity | No per-row timestamps; quadplane configuration is not the AeroForge quad |
| [AMOVFLY](https://github.com/YujiaoHu/AMOVFLY-Dataset) | Public repository describing 270+ multirotor flight recordings with wind and battery channels | Candidate for future flight-power model studies | No top-level redistribution license found; only link until terms/record quality are verified |
| [DroneLog](https://azamatjon11.github.io/DroneLog/) | Public real PX4 logs from several quadrotor platforms; publisher declares CC BY 4.0 | Multi-platform flight telemetry ingestion / sensor-regime evaluation | No AeroForge hardware match established |
| [NASA battery data repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/) | NASA documents battery aging/load datasets | General physics/model-form research for Li-ion cycling | NASA reports direct downloads unavailable for some datasets; different chemistry/pack from high-C UAV LiPo |
| [IDF-DS fixed-wing](https://zenodo.org/records/16992976) | Published 240 fixed-wing autonomous flight logs | Future fixed-wing method testing | Current AeroForge v1 is multirotor; check record's particular license before redistribution |

Primary references:
- [Rodrigues et al., *Scientific Data* (2021)](https://www.nature.com/articles/s41597-021-00930-x):
  209 DJI Matrice 100 missions; logged battery voltage/current, wind,
  inertial/GNSS data, varying payload, speed and altitude.
- [NASA-STD-7009B, active March 2024](https://standards.nasa.gov/node/263):
  model credibility and intended use; **not** an assertion that passing CI
  makes a model physically validated.
- [ASME V&V 20 (CFD / heat transfer) and V&V 10 (solid mechanics)](https://www.asme.org/codes-standards/publications-information/verification-validation-uncertainty):
  discipline-specific verification, validation and uncertainty.
- [BIPM JCGM 100:2008 (GUM)](https://www.bipm.org/en/doi/10.59161/jcgm100-2008e):
  measurement uncertainty evaluation and reporting.

## 3. Complete physical evidence still required for *this* UAV

A scientific model near-equivalence claim cannot be obtained by finding any
public UAV data: **the geometry, motor, battery, ESC, controls, environment,
sensor processing and mass distribution must match the predicted system**.
Required evidence, tracked in [issue #16](https://github.com/god88844-hub/aeroforge/issues/16):

1. **Registered model of the exact aircraft:** photographs/CAD, measured arm
   and prop coordinates, all moving/flexible parts, rotor geometry and
   directional inertia, calibrated mass/CoG, wiring and payload.
2. **Actual motor–ESC–prop measurements:** prop ID, blade pitch and geometry,
   ESC protocol/timing, voltage/RPM/throttle/current/thrust/shaft torque,
   temperature and airflow, transient slew and mechanical/thermal failure
   boundaries, across a *blind* validation matrix not fitted by the model.
3. **Pack-specific electrical and thermal traces:** manufacturer/serial,
   chemistry, actual cells, capacity, internal impedance and OCV/SOC
   characterization, separately measured high-C discharge at mission-relevant
   loads and temperature/aging regimes, *raw synchronized* per-cell voltage,
   pack current, temperature and independent charge integration.
4. **Sensors and controller:** PX4/ArduPilot/firmware versions, parameter
   snapshots, IMU/GNSS/altimeter calibration and error covariance, actuator
   commands and achieved rotor speeds, controller saturation and logging delay.
5. **Independent environment:** wind vector/turbulence and measured sensor
   error, ambient density/pressure/temperature, ground-effect distance,
   flight envelope and atmospheric changes at each test.
6. **Structure, joints and thermal failure:** material lot, laminate layup,
   coupons, arm/attachment torque, fatigue, dynamic loading, electrical
   protection/temperature, thermal runaway prevention; independent qualified
   engineers review high-consequence designs.
7. **Independent actual mission logs:** multiple disjoint flights and crews,
   repeatable scripted commands, launch and touchdown states, actuator and
   external sensor clocks, raw data immutable with checksums; do not perform
   unsafe testing merely to satisfy a simulation claim.
8. **Validation protocol:** predeclared error tolerances and uncertainty budgets;
   sensor clock offsets bounded before examining predictions; separate
   calibration/holdout by **entire experiment, pack, and flight**, not adjacent
   samples; out-of-envelope refusal, coverage analysis, numerical convergence,
   explicit model-form discrepancy and external peer review.

**Gate:** Until all decision-critical submodels have independently traceable
holdout measurements *within the actual operating envelope*, report
`PROMISING_FURTHER_EVIDENCE_REQUIRED` or `INCONCLUSIVE`. Never
infer a percentage chance of manufacturing success from how closely
software-only fixtures match.

## 4. Implementation and verification

- Public source registry with licensing/availability/model-match annotations.
- Pinned CC BY 4.0 public real-flight battery CSV and attribution.
- Immutable Git-blob integrity check, exact six-channel schema and 1,442-row
  count, finite numeric/physical checks, monotonic cumulative counter QA,
  observed electrical envelopes, and no invented synchronization/integrals.
- Read-only `GET /api/components/public-evidence` and visible frontend panel.
- CLI `python scripts/audit_public_flight_evidence.py` (optional `--output`).
- Python physics/API integrity and tampering tests, frontend display/error tests.

```bash
python scripts/audit_public_flight_evidence.py
python -m pytest tests/physics/test_public_evidence.py tests/integration/test_public_evidence_api.py -q
python -m pytest -q
cd apps/web && npm ci && npm audit --audit-level=moderate && npm run build && npm test
```

This milestone **acquires and audits real third-party measurements**, but no
AeroForge flight *prediction-vs-experiment* metric has been established for
the new dataset. That is a distinct, deliberately outstanding milestone.
