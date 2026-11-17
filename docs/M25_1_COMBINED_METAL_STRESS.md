# M25.1 — Isotropic ductile-metal combined bending and torsion screen

**Status:** Analytic model-only structural check. It is **not** an independently
validated failure model for the actual aircraft or a structural approval.
The physical component-failure and structural validation campaign remains
outstanding under [issue #16](https://github.com/god88844-hub/aeroforge/issues/16).

## Model and applicability

AeroForge M10.7 checks static circular tube cantilever bending, and M10.8
checks tube-axis torsion and joint allowables **independently**. These checks
must not be naively combined into an overall positive strength guarantee.
M25.1 adds the elementary isotropic ductile-metal, linear-elastic combination
at the maximum-bending outer fiber of a circular tube:

\[
\sigma_\mathrm{VM} = \sqrt{\sigma_b^2 + 3\tau_t^2}
\]

where \(\sigma_b=M c/I\), \(\tau_t=T c/J\),
\(J=2I\), \(c=D_o/2\), with **explicitly supplied** per-rotor
tip thrust and arm-axis torque. The effective span remains the conservative
\(\max(\mathrm{declared\ span},\mathrm{planar\ rotor\ radius})\),
from M10.7. For a requested safety factor \(N\), the nominal yield
allowable is \(\sigma_y/N\).

This formula is an analytical static stress-screen criterion only and
**is restricted to** material `alu_6061_t6` (ductile isotropic Aluminum
6061-T6) in the current AeroForge source database.

### Material applicability is a hard gate

The reference drone frames are listed as `cfrp_quasi_iso`. For carbon-fiber
laminates, unknown fiber directions/layups, polymer printed components and
other anisotropic or brittle systems, the module **refuses** a metal von Mises
strength pass and reports `UNSUPPORTED_MATERIAL_FAILURE_MODEL`.
It does not pretend that composite's nominal "yield" field is true ductile yield.

The code takes the existing material's stated published nominal yield
and reports its database uncertainty separately; it does **not** convert
the source's uncertainty percentage to a statistically justified failure
probability or independently certified allowable. The user must state
the source of the static load cases, not silently use arbitrary thrust.

### Finite and zero-load behavior

All dimensions and loads pass the existing structural-envelope validation;
an axial torque must be explicitly specified for each rotor. Known exceedance
reports `EXCEEDS_DECLARED_COMBINED_STATIC_ALLOWABLE`. Unsupported material,
missing torque, absent evidence, numeric overflow or zero load cannot produce
a positive screen. A within-limit result remains
`ANALYTICAL_ISOTROPIC_STATIC_SCREEN_ONLY` and never grants structural
physical validation or flightworthiness.

## User interface and API

`POST /api/components/combined-metal-screen` accepts a full existing
`DroneDesign`, 1–32 explicit load cases, an evidence-source string
and a requested safety factor from 1 to 10. Example **synthetic** load case:

```json
{
  "cases": [{
    "name": "synthetic_test_only",
    "thrusts_n": [5, 5, 5, 5],
    "axial_torques_n_m": [0.1, 0.1, 0.1, 0.1]
  }],
  "safety_factor": 1.5,
  "load_case_source": "Synthetic analytic fixture — not a real flight load"
}
```

The required `design` field is omitted from this shape illustration;
the UI supplies the currently active design directly. For carbon reference
frames, the API returns the expected *unsupported material* verdict.
The result is read-only; no original aircraft, frame or component is modified.

## Scientific blockers

M25.1 cannot predict or certify actual:
- CFRP failure, interlaminar shear, fiber buckling or adhesive joints;
- bolted connections, fastener torque, clamped-root compliance or stress concentrations;
- beam shear interaction outside the simplified circular tube idealization;
- vibration/fatigue, thermal creep, buckling, impact, nonlinear fracture or manufacturing defects;
- complex 3D load sharing or independently measured flight-load distributions;
- operating life, probability of structural survival or airworthiness.

These require qualified structural engineering, sourced coupon/connection
experiments, appropriate multiaxial failure criteria, independent bench tests,
validated geometry and predeclared real-world prediction-error tolerance.

## Software verification

```bash
python -m pytest tests/physics/test_combined_metal.py tests/integration/test_combined_metal_api.py -q
python -m pytest -q
cd apps/web && npm ci && npm audit --audit-level=moderate && npm run build && npm test
```

These are analytical numerical tests and source-consistency checks only.
