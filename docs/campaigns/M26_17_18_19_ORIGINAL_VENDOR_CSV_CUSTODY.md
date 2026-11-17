# M26.17–M26.19 — As-obtained instrument CSV inspection, explicit SI conversion, byte-for-byte replay

**Software scope:** this is a narrow adapter for original, legally obtained **UTF-8, comma-delimited CSV instrument exports**. It does **not** download raw measurements, decode TU Braunschweig's unknown native files, or claim that their files contain any particular channels. No physical validation, sensor calibration, historical blindness or aircraft release is established.

## M26.17 — Inspect original raw headers and file completeness

`physics.validation.flight_vendor_csv_inspector.inspect_original_vendor_csv` hashes every manifest-declared original file and checks completeness of the entire evidence folder before inspecting the requested original CSV. It rechecks the exact file SHA-256 and byte length before reading its original, uninterpreted column headers and row count. It rejects empty/duplicate column labels, incomplete records, invalid UTF-8, BOM, NUL bytes, symlinks, missing originals and malformed CSV. It **does not** guess measurement units, time origin, clock calibration, sensor uncertainty or provenance.

```bash
python scripts/prepare_original_instrument_csv.py \
  --original-root /verified-local-originals \
  --source-manifest-json /metadata/original_source_manifest.json \
  --source-manifest-sha256 ACTUAL_SOURCE_MANIFEST_SHA256 \
  inspect --relative-path 'flight01/actual original file.csv'
```

Paths and SHA names are examples, **not downloaded data**.

## M26.18 — Explicit traceable single-channel conversion

`physics.validation.flight_explicit_csv_conversion.derive_original_vendor_csv_bytes` requires an exact user-supplied source mapping to known original column labels and units. The format of a mapping JSON is:

```json
{
  "source_relative_path": "flight01/actual original file.csv",
  "time_column": "instrument elapsed ms",
  "time_unit": "ms",
  "channel_column": "motor frequency Hz",
  "output_channel": "rotor_rpm",
  "channel_unit": "Hz",
  "mapping_source_reference": "calibration and source manual reference still to be authenticated"
}
```

This example is **illustrative only**. Use the real, inspected original headers and actual instrument unit documentation. Supported timestamp units are **seconds, milliseconds, microseconds and nanoseconds**. Supported explicit output channels and source units:

| Output channel | Supported source units | Conversion |
| --- | --- | --- |
| `rotor_rpm` | rpm, Hz | revolutions/min = 60 × frequency Hz |
| `pressure_pa` | Pa, kPa, bar, psi | standard pressure conversion coefficients |
| `temperature_c` | degC, K, degF | exact affine temperature conversion |
| `arm_force_n` | N, kN, lbf | declared force conversion coefficients |
| `acceleration_m_s2` | m/s2, g0 | standard g0 constant 9.80665 m/s², **not** measured local gravity |
| `strain_microstrain` | microstrain, strain | decimal × 1,000,000 |

All coefficients are **software assumptions**, even where metrologically conventional. This adapter does **not** infer whether an instrument really produced values in the declared unit, whether a sensor is physically calibrated, whether a temperature probe reports Celsius, or whether a rotor encoder reports revolutions or blade-pass frequency. These conditions require original manuals/instrument review.

Conversion uses Python `Decimal` with a fixed arithmetic context and an explicit unit allowlist; it rejects missing, nonfinite, excessive-magnitude, unordered or duplicate timestamps, unsupported unit mappings, unexpected headers and binary data. It **never resamples, filters, imputes, shifts or transcribes unknown channels**. It records unmapped original headers rather than quietly claiming they were interpreted.

The output is a clearly labeled **DERIVED** canonical CSV `t_s,<channel>`, plus a separate provenance JSON sidecar pinning original SHA-256, conversion mapping, conversion-spec SHA-256 and derived-byte SHA-256. Both outputs are new files stored **outside** the original evidence directory; neither may overwrite existing files.

```bash
python scripts/prepare_original_instrument_csv.py \
  --original-root /verified-local-originals \
  --source-manifest-json /metadata/original_source_manifest.json \
  --source-manifest-sha256 ACTUAL_SOURCE_MANIFEST_SHA256 \
  convert \
  --mapping-json /metadata/channel_mapping.json \
  --mapping-sha256 ACTUAL_CHANNEL_MAPPING_SHA256 \
  --derived-csv /derived/flight01_rotor.csv \
  --provenance-json /derived/flight01_rotor.provenance.json
```

## M26.19 — Replay and independently audit the derived file

`physics.validation.flight_derived_csv_replay.replay_derived_flight_csv` reloads the original measured bytes and the conversion sidecar, recomputes the entire conversion and requires **byte-for-byte equality** with the existing derived CSV and exact sidecar. It refuses source tampering, renamed/mismatched mappings, unsupported fields, altered output, claimed physical certification and derived data mixed into the immutable original folder.

```bash
python scripts/prepare_original_instrument_csv.py \
  --original-root /verified-local-originals \
  --source-manifest-json /metadata/original_source_manifest.json \
  --source-manifest-sha256 ACTUAL_SOURCE_MANIFEST_SHA256 \
  verify \
  --derived-csv /derived/flight01_rotor.csv \
  --provenance-json /derived/flight01_rotor.provenance.json
```

A verified transformation means **only that the software output can be reproduced from the source bytes under an operator-declared conversion**, not that the source is authentic, that the unit declaration matches the original measuring instrument, or that the model is accurate. The derived file must **not** be passed to M26.3/M26.9 as if it were an unmodified instrument original; a future explicitly provenance-aware adapter is necessary before such data can be scientifically admitted.

## Regression and physical blocker

```bash
python -m pytest tests/physics/test_m26_vendor_csv_custody.py -q
python -m pytest -q
```

Tests are all **synthetic on-disk fixtures**, not retrieved flight recordings. The critical next step remains independently acquiring the original licensed P80III instrument files, verifying their actual format, source rights, instrument identity/units and clocks, then using the supported adapter under independent review. Hardware-matched battery, propulsion and flight measurements still remain outstanding under [Issue #16](https://github.com/god88844-hub/aeroforge/issues/16). No major scientific M21–M30 acceptance milestone is certified complete by this adapter.
