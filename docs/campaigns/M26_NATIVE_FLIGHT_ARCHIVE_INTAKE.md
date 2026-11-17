# M26 — Safe offline intake of native original flight measurement files

**Scope:** original-byte inventory and preservation only. **It does not download, parse or accept physical flight evidence as scientifically valid.** The independent 25 kg P80III quadcopter original data described by [Pätzold et al. (2023)](https://doi.org/10.3390/atmos14091336) has **not** been obtained as part of this implementation.

## Why a native-file intake is needed

AeroForge's M19 ingestion requires a known, synchronized `t_s,terminal_voltage_v,current_a` CSV. The P80III multicopter paper describes pressure, temperature, rotor state, vibration and strain/arm-force instrumentation, potentially stored in multiple high-frequency native files. It is incorrect to silently convert these to battery telemetry or to invent missing timestamps, voltage/current, position, frame or clock alignment.

The new `physics.validation.native_flight_archive` handles **existing, originally acquired binary/native files without interpreting them**. It can inventory TDMS, MATLAB MAT, HDF5, CSV, TXT, binary DAT/BIN, and ZIP containers, reading SHA-256 in bounded chunks. It **does not extract ZIP files** or process untrusted archive members. The caller must follow applicable dataset rights and retain original raw bytes in a read-only location.

## Usage after legitimate original-data acquisition

```bash
# For each real file, calculate a read-only SHA-256 + actual byte count
python scripts/audit_native_flight_archive.py \
  --root /evidence/tu-braunschweig-originals \
  --hash-file flight01/pressure.tdms

# With an independently maintained manifest covering *all* original files,
# check actual byte counts and hashes, and list missing provenance details
python scripts/audit_native_flight_archive.py \
  --root /evidence/tu-braunschweig-originals \
  --manifest /evidence/metadata/frozen_native_source_manifest.json \
  --output /evidence/audit-outputs/native_source_audit.json
```

These are illustrative paths, not claims of a downloaded file named pressure.tdms. The manifest should be created **from the actual provider file inventory and original bytes**, never from guessed file names, fabricated recording IDs or screenshots.

Manifest schema v1.0 has exact root keys `schema_version`, `archive_id`, `publication_reference`, `archive_record_reference`, `source_permission`, `declared_vehicle_identity`, `files`. Each file must declare exact keys `relative_path`, `flight_id`, `sensor_family`, `declared_channels`, `original_sha256`, `original_byte_count`, `calibration_reference`, `clock_reference`, `source_notes`. Set any unavailable source permission, calibration/clock reference or channel list to **null or []**, never an invented value. Full valid **synthetic** examples are in `tests/physics/test_native_flight_archive.py`. Missing original files, byte mismatches, changed hashes, unsafe paths, symlinks and duplicate paths fail closed.

No human-entered hash proves a publisher or instrument created the bytes: a claimant may invent both file and SHA-256. An external reviewer must verify provider custody, licensing, actual sensor calibration, original timing and selected individual flight/test IDs. The output always sets `original_recorder_or_file_custody_authenticated=false`, `actual_channel_contents_decoded_or_verified=false`, `measurement_clock_alignment_authenticated=false`, `full_aircraft_prediction_validated=false`, and `manufacturing_or_flight_release_authorized=false`.

## Scientific next steps after a verified real archive arrives

1. Validate provider version and legal use, actual file inventory and original byte hashes with qualified source/data reviewers. Preserve all failed, aborted and marked unusable flights.
2. Read native instrument metadata with a **source-specific and licensed** decoder before claiming channels or units. Confirm which individual flights contain rotor RPM, pressure, temperature, strain, power, actual motion or autopilot commands.
3. Independently verify sensor calibration, timebases, vehicle serials, rotor-arm geometry and P80III motor revision. A name match is not a full hardware match.
4. Freeze the AeroForge model/protocol and preregister acceptance metrics **without using already exposed experiments as blind holdouts**. If model fitting has already used this study, classify it as calibration/exploratory research rather than a fresh independent benchmark.
5. Only generate the existing M19 electrical telemetry format when true original synchronized voltage/current channels are both present. Do not fill unknown channels to satisfy a required schema.
6. Only run physical comparison when original data, matched hardware, prior model/freeze, uncertainty and independent review meet the selected narrowly justified scientific claim.

## Verification

```bash
python -m pytest tests/physics/test_native_flight_archive.py -q
python -m pytest -q
cd apps/web && npm ci && npm run build && npm test
```

All regression bytes are synthetic and intentionally *not* genuine TU Braunschweig recordings. Passing tests establishes file-integrity tooling only, not M26 physical fidelity. [Issue #16](https://github.com/god88844-hub/aeroforge/issues/16) remains open.
