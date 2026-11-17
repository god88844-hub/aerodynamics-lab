# M26.4 — Whole-flight required-signal evidence coverage

**Implemented software stage:** `physics.validation.flight_channel_coverage.audit_original_flight_channel_coverage` and CLI `scripts/audit_flight_evidence_channels.py coverage`.

Run full M26.1 source inventory checks, then M26.3 exact-original-CSV source checks and produce a **per-required-channel availability matrix across distinct declared flight IDs**. Report the number of distinct source-claimed whole flights per channel rather than treating multiple time windows or sensor files from one mission as independent. Identical original bytes reused under two flight IDs are explicitly refused. A channel counts toward reported coverage only if its original CSV bytes and time grid pass, and operator-provided clock and calibration references exist. For reported coverage to be complete, the manifest must also contain a nonempty operator-supplied source rights declaration. All other unparsed native files remain explicitly listed as unknown.

**Command:**
```bash
python scripts/audit_flight_evidence_channels.py \
  --root /read-only/originals coverage \
  --manifest /separate/source_manifest.json \
  --sources-json /separate/selected_original_csv_sources.json \
  --required-channels rotor_rpm,pressure_pa \
  --minimum-flights 2
```

The JSON source selection is a list where each item has `relative_path`, `channels_with_units`, and `maximum_declared_sample_gap_s`. All values must originate from the actual unmodified supported original CSV. A successful report merely means that **operator-asserted** source files, signal names, numerical sampling, calibration/clock references, and rights metadata agree; it cannot prove a real flight took place, that the sensor was calibrated correctly, that two flights were independent, or that predictive errors meet frozen thresholds. The output *always* refuses full-vehicle physical model validation and flight release.

**Scientific use after independent source review:** demonstrate which genuine original signals can support which *narrow, preregistered* tests in M24/25/26; mark missing full 6DOF state, power, battery, input commands, wind, motor/ESC revision or original sample streams **INCONCLUSIVE** rather than inventing them. The actual TU Braunschweig archive is not retrieved by this software stage. Source blocker [#16](https://github.com/god88844-hub/aeroforge/issues/16) remains open.
