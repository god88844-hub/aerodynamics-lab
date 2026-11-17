# M26.25–M26.29 — Acquire actual public flight evidence, without substituting M300 flights for a 60 kg hexacopter

**Status:** five source-acquisition **software phases** implemented. **The actual source CSV has not been successfully obtained in this environment**; it is a research candidate, not an imported physical experiment. A direct landing-page download attempt and API access did not return the original file. Do not claim original source SHA-256, sensor calibration, official rights, or a successful independent model comparison.

## Concrete research source and boundary

Palamas and Kolios, *Drone onboard multi-modal sensor dataset*, Zenodo record [7643456](https://zenodo.org/records/7643456), DOI [10.5281/zenodo.7643456](https://doi.org/10.5281/zenodo.7643456). The publication describes actual instrument flight telemetry from a **DJI Matrice 300**, including trajectory, orientation, acceleration, voltage/current, wind and mission-state labels. The visible published CSV is approximately **15.6 MB**, and its provider-listed file MD5 is `e2f188e8f5cbf498c7009f422d401207`. The original CSV header, instrument units and actual independent source bytes are **not known** before a successful download. The landing page's rights/license entry was not sufficient in this review to verify a reuse license; do not copy source data into the repository or redistribute without review. The published M300 is **not** the AeroForge reference 60 kg hexacopter with P80 III KV100/G30 propulsion. No exact installed motor, ESC, pack, serial, mounting geometry, or controller correspondence is established.

## Five implementations

**M26.25 — Official source metadata validation:** `zenodo_flight_candidate.inspect_zenodo_m300_record` checks an original Zenodo API response (v1/v2 style) for the exact DOI, record ID, published dataset title, bounded original file list, provider MD5 and file size. This checks *provider-shaped metadata*, not network authenticity or experimental truth.

**M26.26 — Constrained original download plan:** `zenodo_original_download.plan_original_zenodo_download` constructs the official `https://zenodo.org/api/records/7643456/files/.../content` endpoint directly from the validated provider file key, never accepts arbitrary user-supplied download URLs, and requires an explicit external rights-review reference. The review reference is operator-supplied and is not an automated legal approval.

**M26.27 — Controlled original-byte acquisition:** `download_zenodo_original` performs an opt-in HTTPS request with redirects disabled, bounded time and expected file size, and independently computes source MD5/SHA-256 while writing only a new file (never overwriting another). Failed checks remove only the partial file that the process itself created. Redirect-required or unavailable endpoints fail visibly; neither synthetic replacement nor guessed raw values are used. If you obtain the file through Zenodo's browser UI instead, preserve it byte-for-byte and use the local inspector after recording its source context.

**M26.28 — Real-size CSV schema inspection:** `zenodo_original_csv_schema.inspect_downloaded_m300_csv` accepts up to **25 MB**, covering the advertised 15.6 MB candidate beyond the older 8 MB parser limit. It requires original checksum and acquisition receipt agreement and reads the *actual* original CSV headers, row count and rows containing missing cells. Unknown units, encoding issues, clock calibration, data gaps and bad CSV structure are not silently repaired.

**M26.29 — Specific scientific suitability screen:** `zenodo_m300_suitability.classify_m300_evidence_suitability` can flag source-specific CSV/parser evaluation only if the original source and provider-linked headers have been checked. It never marks M300 telemetry as qualifying the 60 kg AeroForge hexacopter, P80 III powertrain, actual battery pack, end-to-end flight predictions or flight safety.

## Reproducible command line

Retrieve official provider metadata **only when the source is accessible**, storing the raw JSON separately:

```bash
python scripts/acquire_zenodo_m300_evidence.py discover \
  --fetch --save-metadata /separate/source_metadata_7643456.json
```

Inventory an already obtained metadata JSON (offline):

```bash
python scripts/acquire_zenodo_m300_evidence.py discover \
  --metadata-json /separate/source_metadata_7643456.json
```

After independently reviewing source rights/terms for your intended activity, plan the *original file* download. Do not invent a review reference or assert permissions you have not actually examined:

```bash
python scripts/acquire_zenodo_m300_evidence.py plan \
  --metadata-json /separate/source_metadata_7643456.json \
  --rights-review-ref 'actual rights review documentation reference'
```

To **attempt** an original transfer, replace `plan` with `download` and append `--output /separate/originals/m300_original.csv`. The tool can return an error if the provider requires a redirect or access is blocked; that is not an invitation to bypass access controls. Capture the printed acquisition receipt in a separate JSON file only after successful acquisition. Run:

```bash
python scripts/acquire_zenodo_m300_evidence.py inspect \
  --source-file /separate/originals/m300_original.csv \
  --acquisition-receipt /separate/source_receipt_7643456.json
python scripts/acquire_zenodo_m300_evidence.py classify \
  --metadata-json /separate/source_metadata_7643456.json \
  --acquisition-receipt /separate/source_receipt_7643456.json \
  --csv-inspection-report /separate/inspected_columns_7643456.json \
  --reference-aircraft '60 kg hexacopter'
```

No automatic source retrieval is performed in default/offline invocation. Outputs use **synthetic** fixtures for CI; the successful-stream test intentionally changes the known provider MD5 *only inside its isolated test monkeypatch* to permit locally fabricated bytes. The production MD5 stays bound to the published record.

## Remaining critical science

The article/documentation and local source checks cannot prove independent physical validation. **M21** demands exact battery pack discharge experiments; **M22** demands P80 III KV100/G30/installed ESC and mount performance measurements; **M23** requires controller/sensor HIL tests; **M24–25** need actual aerodynamic, thermal and structural validation; **M26** needs repeated, independently instrumented matched-aircraft flights frozen before independent holdout revelation. The known 60 kg hexacopter single-motor-out failure remains unrecoverable in simulation. [Issue #16](https://github.com/god88844-hub/aeroforge/issues/16) stays **OPEN**.

These phases complete a significant **ingestion capability**, but **zero new major scientific/product acceptance families** are claimed complete by them. The ten M21–M30 exit milestones still require the independent scientific/product evidence in the original roadmap.
