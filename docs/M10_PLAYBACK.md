# M10.1 — Telemetry-driven 3D flight replay

This incremental AeroForge laboratory feature displays the drone's motion from recorded physics states, **not** from a scripted animation.

## Features
- Backend's decimated simulation trace includes body-to-world quaternion `q_wxyz` in scalar-first order, sampled on exactly the same indices as position.
- The 3D drone model follows saved position and attitude, with the appropriate z-up to Y-up coordinate transform.
- Time-based interpolation handles nonuniform samples; quaternion interpolation uses shortest-arc SLERP.
- Play/pause, restart, timeline scrub, 0.5×–4× playback speed and optional follow camera.
- Static powertrain studies do not fabricate trajectories.

## Validation
- `python -m pytest tests/physics/test_telemetry_playback.py -q`
- `python -m pytest -q`
- `cd apps/web && npm ci && npm run build && npm test`
- In browser, run `flight` or `hover-hold`, then play, pause and scrub. Verify static hover shows a no-trajectory notice.

## Scientific limitations

Interpolation is solely for rendering. No new CFD, FEA, physical validation or ground-collision simulation has been added. The drone mesh is a simplified schematic; the engineering verdict and uncertainty records are unchanged.
