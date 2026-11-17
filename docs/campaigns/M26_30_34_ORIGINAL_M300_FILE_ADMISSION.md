# M26.30–M26.34 — Original M300 source access, inspection and admission boundary

These five development subphases extend the merged M26.25–M26.29 candidate acquisition. They provide a bounded, fully reproducible path **only for a locally acquired, authenticated-by-provider-checksum original DJI M300 CSV**. The source file could not be downloaded in this environment; all regression files are **synthetic** and test software behavior, never observed physical flights.

## M26.30: official-provider alternate download
`zenodo_official_fallback.alternate_zenodo_original_download` accepts a validated plan for the exact Zenodo record [7643456](https://zenodo.org/records/7643456), DOI `10.5281/zenodo.7643456`, and provider MD5 `e2f188e8f5cbf498c7009f422d401207`. It tries only the two constructed official URLs: the fixed Zenodo API content endpoint, then the original file's Zenodo landing download endpoint. It requires an operator rights-review reference, bounds the transfer by published byte count and 25 MB maximum, rejects arbitrary redirects and overwriting existing output, and accepts **only exact provider MD5 and size matched bytes**. A transport error leaves acquisition **incomplete**. A checksum mismatch is an error, not proof of an alternate valid file.

## M26.31: original column missingness
`zenodo_original_quality.audit_original_m300_field_quality` rechecks original file byte length, provider MD5, locally calculated SHA-256, UTF-8 CSV structure, unique exact source column labels, every row, and blank-cell counts per original column. No data is imputed or silently discarded.

## M26.32: original timebase and contiguous blocks
`zenodo_original_time_segments.audit_original_m300_time_segments` requires an explicitly documented original time column, declared time unit and maximum sampling gap. It refuses missing, nonnumeric, repeated, nonmonotone or nonfinite timestamps. The segment report is a gap-based **continuous-recording grouping only**; splitting one file into blocks does not create independent physical flights or blind holdouts.

## M26.33: documented channel probes
`zenodo_original_channel_probe.inspect_declared_original_m300_channel` requires an exact source header, an explicit supported channel/unit combination and instrument-unit documentation reference. It computes actual on-disk numeric extrema in the declared base units, while rejecting blank/nonfinite cells. It **does not** independently verify that the declared units, sensor calibration, or actual battery hardware are correct.

## M26.34: reproducible exploratory report
`zenodo_m300_exploratory_report.build_original_m300_exploratory_report` rehashes and re-runs the above quality, time and channel checks, binds their results to a deterministic SHA-256, and explicitly marks full 60 kg hexacopter validation and flight release **false**. The published DJI Matrice 300 and AeroForge's 60 kg hexacopter are different hardware; no flight-data comparison across those airframes can be treated as matched-aircraft validation.

## Running the source workflow
The CLI `scripts/profile_zenodo_m300_original.py` supports two explicit operations:

```bash
python scripts/profile_zenodo_m300_original.py retry-official-download \
  --plan-json /metadata/zenodo_plan.json \
  --plan-sha256 ACTUAL_SHA256_OF_PLAN_JSON \
  --original-out /originals/m300_source.csv

python scripts/profile_zenodo_m300_original.py profile-local \
  --original-file /originals/m300_source.csv \
  --receipt-json /metadata/provider_receipt.json \
  --receipt-sha256 ACTUAL_SHA256_OF_RECEIPT_JSON \
  --mapping-json /metadata/operator_reviewed_mappings.json \
  --mapping-sha256 ACTUAL_SHA256_OF_MAPPING_JSON
```

The mapping JSON requires `original_time_column`, `original_time_unit`, `declared_max_sample_gap_s`, `reference_aircraft`, and a `channel_mappings` array. Each channel mapping requires `original_column`, `claimed_channel`, `claimed_original_unit`, and `instrument_unit_document_reference`. Values must come from the **actual inspected original CSV header and instrument specifications**, not the synthetic test example. Source file data must be legally accessed and the separate rights review completed.

Tests:

```bash
python -m pytest tests/physics/test_m26_30_34_m300_original_evidence.py -q
python -m pytest -q
```

## Outstanding physical work
Provider checksum verification does not independently prove physical source custody, experiment instrumentation, controller/clock calibration, true holdout independence, source license rights or matched hardware. Even successful M300 inspection cannot validate AeroForge's reference propulsion system or the entire 60 kg reference aircraft. [Issue #16](https://github.com/god88844-hub/aeroforge/issues/16) remains open. This batch does **not** reduce the remaining ten M21–M30 major scientific/product acceptance families through Drone v1.
