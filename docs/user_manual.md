# AeroForge User Manual

*(grows with the editor — Milestone 5; the workflow below is the target UX)*

## Concept

AeroForge lets you assemble a multi-rotor drone from real components, define
a mission scenario, and get an engineering-grade prediction of whether the
drone can fly it — including the uncertainty and credibility of that
prediction. It is an engineering study tool, not a game: if any component
would exceed its real limits, the design fails.

## Workflow

1. **Assemble** — in the 3D editor, place components (motors, propellers,
   battery, frame, flight controller) from the evidence database. The editor
   shows center of gravity and principal axes. All units are SI.
2. **Configure** — set materials, control gains, environment (air density,
   wind), and the scenario (takeoff, hover, climb, maneuvers).
3. **Simulate** — the backend runs the 6-DOF physics engine on your exact
   saved snapshot. Results plot altitude, attitude, forces, energy.
4. **Read the verdict** — every run reports:
   - **Design**: mass, CoG, inertia, propulsion summary.
   - **Results**: performance vs requirements (time-to-altitude, hover time,
     energy used).
   - **Trustworthiness**: validation status of each submodel, uncertainty
     intervals, credibility rating, and explicit caveats.
   - **Verdict**: PASS / FAIL / INCONCLUSIVE / NEEDS FURTHER VALIDATION.

## Rules to expect

- A design passes only if **every** component stays within its operating
  limits during the whole scenario.
- If your scenario is outside the validated envelope (e.g., an exotic
  geometry with no data), the report says so instead of inventing numbers.
- If uncertainty crosses a requirement threshold, the verdict is
  INCONCLUSIVE — you'll be told which parameter measurements would help most.
