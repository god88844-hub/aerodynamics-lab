# M22 — Published P80/G30 bench data: original-source acquisition and admission plan

**Date:** 17 November 2026. **Current state:** VERIFIED ARTICLE / ORIGINAL DATASET NOT RETRIEVED / NO HARDWARE OR PHYSICAL VALIDATION. This work addresses [M22 physical-data issue #25](https://github.com/god88844-hub/aeroforge/issues/25) and [global issue #16](https://github.com/god88844-hub/aeroforge/issues/16). No actual experimental points were copied or invented.

## Evidence of a promising independent bench dataset

Denis Kotarski, Petar Piljek, Marko Pranjić and Josip Kasać, [*Concept of a Modular Multirotor Heavy Lift Unmanned Aerial Vehicle Platform*](https://doi.org/10.3390/aerospace10060528), *Aerospace* 10(6):528 (2023) reports original bench experiments on selected high-voltage propulsion units.

Its **Table 1, Setup 3** specifies a **P80 100 Kv motor**, **Alpha 80 A ESC**, and **G30 × 10.5 propeller**. The article describes an RCbenchmark 1780 acquisition rig measuring thrust, shaft drag torque, optical RPM, battery voltage and electric current. It reports separate measurement cycles starting at nominal cell voltages **4.2, 4.0 and 3.8 V**, with repeated acquisition at each PWM value and saved CSV data.

The publication's **Data Availability Statement** cites **“UAV Multirotor Propulsion—Experimental Data”** at [doi:10.7910/DVN/J5L2P4](https://doi.org/10.7910/DVN/J5L2P4) (Harvard Dataverse). This is a published pointer, NOT proof that the original data can currently be accessed or reused under a suitable license.

**Crucial hardware caveat:** The published label **“P80 100 Kv”** does not independently establish that its motor is exactly AeroForge's **P80 III KV100**, including revision/serial and mounting. AeroForge's selected installed ESC, mount and actual aircraft are not known to match the article's Alpha 80 A and rig. Even an authentic Setup 3 bench measurement cannot validate the full aircraft.

## Access and custody findings

The Harvard Dataverse DOI landing page and dataset API endpoint could not be opened from the current execution environment, including an attempted direct official API request. Consequently, **no provider file inventory, original file bytes, actual recording checksum, dataset license, setup-3 file mapping or measured value has been verified here.** [Candidate metadata record](../../data/benchmarks/propulsion/kotarski_2023_setup3_candidate.json) intentionally has `original_sha256: null`, `file_id: null` and all physical validation flags false.

The official [Dataverse Native API](https://guides.dataverse.org/en/latest/api/native-api.html) documents dataset lookup by a persistent DOI. For authorized users with network access:

```bash
# Retrieves official *metadata only*, never original observations:
python scripts/inspect_dataverse_propulsion.py --fetch-metadata --output local_metadata_report.json

# Alternatively, save the exact official API JSON separately and inspect offline:
python scripts/inspect_dataverse_propulsion.py --metadata-json provider_dataset_api.json

# If original data have been lawfully acquired separately, verify a single
# provider file ID, byte size, provider hash where supplied, and compute SHA-256:
python scripts/inspect_dataverse_propulsion.py \
    --metadata-json provider_dataset_api.json \
    --original-file /path/to/unmodified/provider-file.csv --file-id 123
```

The last command's **123 is a deliberately illustrative placeholder**: it is NOT a verified original Dataverse file identifier. Obtain the real ID from the inspected provider metadata. The tool reads bytes but never changes original sources, never downloads experiment files automatically, and never approves their license. Exit code 0 means a technical audit ran successfully, **not** that model predictions are physically validated.

## Required admission gates before a numerical AeroForge comparison

1. **Original source and rights:** retrieve Dataverse's actual released file list and verify current dataset version, license/terms, valid download permissions, original file ID, byte count and provider checksum. Preserve unmodified original file; calculate and record actual SHA-256. Distinguish provider MD5 from cryptographically strong independent custody. Record any embargo/restriction and never redistribute unlicensed data.
2. **Setup-specific identity:** identify which native original files correspond to **Setup 3**, its relevant three voltage-condition cycles and their true hardware/fixture; do not select only favorable portions or relabel other setups as P80 data.
3. **Exact hardware crosswalk:** identify original P80 revision/serial, ESC model/version, G30 geometry, measured installation, ambient conditions, power-bus configuration and measurement instruments. Reject or label any mismatch/information gaps. The nominal model-string gate deliberately **never authenticates** serial/installation identity.
4. **Calibration/holdout independence:** show the independently recorded Setup 3 dataset was not used to fit AeroForge's existing manufacturer powertrain model, calibration coefficients or model selection. Freeze model/protocol *before viewing holdouts* and predeclare thrust/current/error and uncertainty acceptance limits. Repeated PWM within one continuous bench cycle is **not** multiple independent experiments.
5. **Measurement schema:** map genuine measured original thrust/torque/RPM/current/voltage with documented conversion to SI. A static M22 operating-point view requires exactly `rpm,voltage_v,thrust_n,current_a` (5–500 points/recording). Preserve original native files and separately document any averaging, unit conversion, discarded samples and timestamps.
6. **Failure outcome:** every unsupported point, measured component limit exceedance, unbounded sensor/instrument uncertainty or missing holdout group is a failure or inconclusive result. Do not manufacture a full-vehicle validation, thermal transient prediction or success probability from static bench data.

The existing [M22 propulsion campaign](../../docs/M22_STATIC_PROPULSION_CAMPAIGN.md) is the downstream evaluator; it requires whole-run calibration/holdout splits and an M20 frozen protocol. This research branch **does not feed unverified published coefficients into the model** and does not add synthetic evidence to production benchmark files.

## Implemented read-only gates and tests

- `physics.validation.dataverse_candidate.inspect_dataverse_candidate` — exact DOI matching, released version and original provider file inventory; rejects missing, malformed or duplicate IDs/checksums.
- `inspect_original_local_file` — bounded, read-only already-obtained file verification against provider byte count/checksum and computed SHA-256. Never authenticates a download chain.
- `assess_setup_three_hardware_match` — explicit model/revision/ESC/prop/mount comparisons without promoting names to physical proof.
- `scripts/inspect_dataverse_propulsion.py` — optional live metadata lookup or offline provider JSON and read-only file inspection.
- `tests/physics/test_dataverse_candidate.py` — synthetic records testing every safety/credibility refusal. Fixtures are NOT acquired physics evidence.

Run `python -m pytest tests/physics/test_dataverse_candidate.py -q`, then full Python and frontend CI. Completing these software tests is **not** completion of physical M22, M26 or primary physical prediction equivalence.
