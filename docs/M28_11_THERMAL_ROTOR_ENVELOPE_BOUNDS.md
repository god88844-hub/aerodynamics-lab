# M28.11 — Worst-case thermal geometry expansion in rotor-motion clearance

`physics.structures.thermal_rotor_clearance` conservatively enlarges the previously declared moving-rotor 3D enclosing spheres (M28.10), without modifying input design or trajectories.

For each rotor with nominal propeller diameter `d`, maximum swept vertical height `h`, effective arm length `L`, and operator-declared **absolute upper** coefficient bounds `α_d, α_h, α_L` per kelvin over an absolute temperature excursion `ΔT`:

```
additional_rotor_diameter_hard_error = d * α_d * ΔT
additional_swept_height             = h * α_h * ΔT
additional_center_translation_error = L * α_L * ΔT
```

Only add nonnegative error allowances; no assumed contraction is permitted to increase clearance. All explicit existing measurement, mount, and trajectory uncertainties remain, and the complete enlarged bounds feed M28.10's **full-interval rotor-to-rotor clearance screen**. Invalid bounds, incomplete per-rotor entries, missing provenance, or arithmetic overflow fail closed.

This *only* covers the declared thermal dimensional growth and center translation for the assumed rotor enclosing cylinders. It does not model irregular blade thermal warping, composite anisotropy, rotor bending/flapping, altered center velocities, mounting stress, creep, failure of composites, electronic thermal failure or battery behavior. The temperature range and every coefficient/arm dimension remain unverified operator claims; there are no hardware hot/cold measurements or physical collision certification.

Synthetic tests: `python -m pytest tests/physics/test_thermal_rotor_clearance.py -q`. Returned physical-source authenticity and flight release fields always remain false.
