# M26.30–M26.34 — DJI M300 original flight telemetry energy analysis

**Scientific classification:** source-specific analysis capability, **not** validation of the AeroForge 60 kg hexacopter. No original Zenodo CSV bytes were available to this implementation session. Synthetic fixtures validate software behavior only.

The published source candidate is [Zenodo record 7643456](https://zenodo.org/records/7643456), `10.5281/zenodo.7643456` (DJI Matrice 300 multi-modal sensors). The original file must be legitimately acquired first using the M26.25–29 CLI, with independently reviewed rights and official Zenodo MD5 `e2f188e8f5cbf498c7009f422d401207`. Do **not** change the source-specific expected MD5 in production.

## Five software subphases

**M26.30 — Original source integrity.** `analyse_m300_original_energy` calls the published-source-specific original CSV inspection. It refuses absent or changed local source files, invalid published MD5, mismatched acquisition receipt, malformed rows, unexpected column widths and a file above the bounded limit. A provider MD5 match proves file byte consistency, not a physical calibration or laboratory chain of custody.

**M26.31 — Explicit time, voltage, current and sign mapping.** The operator must supply *actual header names from the retrieved original*, choose exact timestamp units (`elapsed_s`, `elapsed_ms`, `unix_s` or `unix_ms`), `V` and `A`, discharge-current positive or negative sign, current/voltage caps, source unit documentation, and an optional state-label column. This implementation cannot infer original units from column names or paper descriptions. Unverified mappings do not establish accuracy.

**M26.32 — Per-UID clock and sampling consistency.** Preserve original row ordering within each flight UID; timestamps must strictly increase. Long gaps are recorded and never filled/interpolated. Flight-state labels are counted verbatim rather than guessed from flight physics. A UID needs at least five observations and no gaps beyond the declared maximum to qualify as a complete numerical holdout. Unlabeled/incomplete recordings are not certified.

**M26.33 — Actual measured-sample terminal battery energy.** For adjacent valid pairs within a UID, the code integrates (P=VI) using the trapezoidal rule and converts to Wh; the current integral is in Ah. These are **measured battery-terminal** energy/charge over the covered recording duration, *not* total cell chemical energy, a battery aging model, a flight endurance forecast or a statement about AeroForge's separate packs. It uses explicit discharge-current sign and no synthetic interpolation. Any gaps mean the reported energy is partial and the flight cannot count as a complete heldout energy benchmark.

**M26.34 — Original-byte-recomputed frozen per-flight energy holdout.** Supply separate pinned prediction JSON with a unique model-predicted Wh and interval per declared holdout UID, a frozen model commit SHA, protocol SHA-256, operator-stated preregistration/freeze/reveal timestamps, disjoint calibration/holdout experiment groups, preregistered hard Wh error limit and robust interval coverage fraction. The source bytes and Wh are always recomputed rather than trusting claimed pass flags. Any observed critical Wh error or interval-coverage failure yields `FAIL`; missing/gapped UIDs or insufficient groups yields `INCONCLUSIVE`; only passing numerical checks yields `CONDITIONAL`. Even conditional passes keep all physical provenance, real historical blinded independence and full-aircraft accuracy flags false.

The modeled `maximum_abs_energy_error_wh` means the limit on absolute prediction residual *plus* declared hard measurement uncertainty; the observed robust interval coverage is the fraction of scored holdout UIDs whose entire measurement uncertainty interval lies inside the frozen prediction interval.

## Offline interface

First execute M26.25–29 discovery, legal/rights review, download, original checksum and header inspection. Once you possess original bytes and have independently reviewed instrument metadata, create the following local JSON files *without modifying the original*:

- `receipt.json`: actual M26.27 successful acquisition output including Zenodo DOI, original byte size, published MD5 success and computed original SHA-256.
- `mapping.json`: strict mapping with `uid_column,timestamp_column,timestamp_unit,voltage_column,voltage_unit,current_column,current_unit,discharge_current_sign,state_column,maximum_accepted_sample_gap_s,upper_voltage_v,upper_discharge_current_a,unit_source_document_reference`. `state_column` may be null.
- `protocol.json`: M26.34 frozen protocol; tests in `tests/physics/test_m26_m300_energy_holdout.py` show exact shape.
- `predictions.json`: `{"predictions":[{"uid":"...","predicted_wh":0,"lower_wh":0,"upper_wh":0}]}` for actually held-out UIDs, frozen before measurements are revealed. The illustrative zero values are **not evidence or a real model prediction**.

```bash
python scripts/audit_m300_flight_energy.py \
  --original-csv /source/M300_original.csv \
  --acquisition-receipt-json /meta/receipt.json \
  --explicit-mapping-json /meta/mapping.json account

python scripts/audit_m300_flight_energy.py \
  --original-csv /source/M300_original.csv \
  --acquisition-receipt-json /meta/receipt.json \
  --explicit-mapping-json /meta/mapping.json holdout \
  --protocol-json /meta/protocol.json \
  --predictions-json /frozen/predictions.json \
  --predictions-sha256 ACTUAL_64_CHARACTER_SHA256
```

The `account` command returns exit 0 for successful **data-processing integrity**, not physical accuracy; `holdout` returns exit 3 for numerical fail, 4 for physical inconclusive or conditional analytical result, and 2 for invalid inputs.

## Next real-world blocker

The candidate M300 data cannot validate the reference 60 kg hexacopter: their aircraft, motors, propellers, ESCs, battery, mass, controller and installation are different or unknown. Acquire **independently instrumented tests of the exact configured reference aircraft** (and compatible battery/powertrain benchmarks), independently document instruments and model freeze before holdout revelation, then satisfy the M21–M30 scientific exit gates. Keep [Issue #16](https://github.com/god88844-hub/aeroforge/issues/16) open. This batch does not complete any of the 10 remaining top-level major drone acceptance milestones.

## Synthetic regression

```bash
python -m pytest tests/physics/test_m26_m300_energy_holdout.py -q
python -m pytest -q
```
