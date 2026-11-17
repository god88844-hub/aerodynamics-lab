# M19 traceable telemetry evidence bundles

This directory contains **no newly acquired physical flight measurements**.
Use it to audit original, permissioned timestamped traces without altering them.
All generated numerical examples in tests are **synthetic fixtures**, not experiments.

For each real source recording, add an independently sourced `<dataset_id>/`
containing only:

- `manifest.json` with schema version 1.0, original CSV SHA-256, source
  reference/license, experiment/recording/vehicle/battery IDs, source kind,
  calibration/holdout role, instrument calibration reference if known, and a
  sampling-gap limit fixed **before** viewing predictions.
- `trace.csv` or another declared local `.csv` basename, unchanged from
  the specified original source. Header must equal the manifest column list,
  beginning `t_s,terminal_voltage_v,current_a`. Optional supported SI fields
  are `temperature_c,altitude_m,vertical_speed_m_s,wind_speed_m_s`.

Run `python scripts/audit_telemetry_ingestion.py --root data/benchmarks/telemetry`.
The audit verifies bytes, strict time order, finite values, physical positivity,
channel units and group separation. Full timestamped V×I energy accounting is
reported **only if the source satisfies its predeclared sample-gap bound**.

Calibrating and held-out traces must be disjoint by full recording, experiment,
vehicle and battery identifier, not randomly by individual rows. This strict
policy is intentionally conservative; comparisons involving the same pack or
vehicle require explicit alternative validation protocols and cannot be
automatically treated as independent here.

**Do not** copy CMU, NASA, AMOVFLY, DroneLog, PX4, or any other source here
unless the exact original bytes, applicable license and per-record timestamps
have actually been obtained and their schema documented. The preexisting
quadplane BATT.csv has **no timestamps** and must stay under its M16 audit,
not converted to this format by inventing uniform time steps.

SHA-256 equality to a user-written manifest is not an authentic chain of
custody. Dataset names, group IDs, physical/synthetic flags, instrument
calibration and hardware match are not independently authenticated. No
favorable audit can declare the aircraft simulated or physically validated.
