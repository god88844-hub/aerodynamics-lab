# M29.9 — Original measurement bytes → thermal rotor physics → critical decision margins

`physics.validation.source_thermal_virtual_case.audit_original_source_thermal_virtual_case` ties primary source bytes to the directly recomputed analysis path:

1. Read each original ADC and frozen prediction CSV, check exact original SHA-256 digest and sample alignment using M27.10, rejecting any missing/reused/altered original bytes or independent-group violations.
2. Apply M28.11's **worst-case thermal diameter/height/mount** expansion to the exact operator-supplied M28.10 full-time rotor-pair motion case.
3. Invoke M29.8's direct computation of M27.9 calibrated ADC observation intervals, M28.10 thermally expanded geometry separations, and conservative critical failure-threshold margins. Reject untyped/mismatched channel or engineering unit. Neither fabricated "passed" fields nor previously prepared result reports are accepted in place of source numeric inputs.
4. Produce an order-stable SHA-256 fingerprint of original digest links, thermal error increments, declared provenance and the directly recomputed decision case. A negative sensor/rotor/decision gate produces `DIRECTLY_RECOMPUTED_SOURCE_THERMAL_CASE_BLOCKED`.

A reported positive `DIRECTLY_RECOMPUTED_SOURCE_THERMAL_CASE_CONSISTENT_UNVERIFIED` establishes only a mathematical consistency of **operator-provided** files and assumptions; it **cannot** independently show that the files came from a real experiment or that the error budgets bound future unknown conditions. Original file hashes may be fabricated, temperature/geometry/material limits unmeasured, model-form residuals unbounded and the threshold list incomplete. Real-world physical equivalence, flightworthiness and manufacturing or flight release flags remain false for every result.

Synthetic tests: `python -m pytest tests/physics/test_original_adc_sources.py tests/physics/test_thermal_rotor_clearance.py tests/physics/test_source_thermal_virtual_case.py -q`. Full Python CI and frontend build/test gates are required for merge; independent physical evidence issue #16 remains open.
