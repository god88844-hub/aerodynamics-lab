# M26.3 — Exact-format original flight CSV channel screening

**Implemented software stage:** `physics.validation.flight_channel_csv.audit_original_flight_channel_csv` and offline CLI `scripts/audit_flight_evidence_channels.py csv`.

A recorded channel can only be read if the **actual original CSV has exactly the declared column names, order and units**, and its original bytes match the full M26 source manifest. Nothing is interpolated, converted, offset, resampled or synthesized. This is specifically for an original CSV whose header truly is `t_s,<declared-channels...>`. Unknown vendor/native formats such as TDMS, MAT, ZIP, HDF5 or any CSV with different original headers remain **unsupported until a separately validated source-specific parser is built**.

Supported explicit engineering channels/units: `rotor_rpm` (rpm), `pressure_pa` (Pa), `temperature_c` (degC), `arm_force_n` (N), `acceleration_m_s2` (m/s2), `strain_microstrain` (microstrain). These are *reader contracts*, not claims that the TU Braunschweig archive provides these columns. The reader checks every line for finite original values, strictly increasing original timestamps, no missing/extra values, a bounded original file length and a predeclared maximum interval between samples. It summarizes reported count, interval and extrema. It preserves original first timestamp rather than forcing time zero.

**Command:**
```bash
python scripts/audit_flight_evidence_channels.py \
  --root /read-only/originals csv \
  --manifest /separate/source_manifest.json \
  --relative-path flight01/original_recording.csv \
  --channels-json /separate/channels_with_units.json \
  --maximum-gap-s 0.05
```

This example filename/path and sample interval are illustrations, **not** a verified original source or experimentally approved sample rate. A channel JSON file could be `{"rotor_rpm":"rpm","pressure_pa":"Pa"}` only if those are literally the exact original columns. Never rename actual source channels in-place. Independent source permission, hardware matching, calibration authority and timebase synchronization are **not** authenticated by reading a CSV.

**Acceptance:** a narrow original CSV is internally consistent and explicitly unit-labelled, but no real-world predictive accuracy, flight safety or physically validated sensor status follows.
