"""Enrich remaining Stage 0A tasks with the mandated execution fields.

Adds to every todo Stage 0A task (P0A-005..P0A-040):
  language         exact implementation language(s) per AGENTS.md routing
                   (GDScript = 3D desktop UI/viewport only; C++20 = real-time
                   native solver/CAD core; Python = validation campaigns,
                   datasets and legacy physics before native migration)
  target_files     exact repository paths this task implements or edits
  todos            concrete numbered steps (what to do and how)
  verify_commands  exact commands + the pre-declared acceptance gate

Run:  python scripts/enrich_plan_tasks.py          # apply + validate + save
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN = REPO_ROOT / "docs" / "planning" / "tasks.json"

A_PY = ["Python"]
A_GD = ["GDScript"]
A_GDPY = ["GDScript", "Python"]
A_PYPY = ["Python", "C++20"]


def todos(*steps: str) -> list[str]:
    return [f"{i}. {s}" for i, s in enumerate(steps, start=1)]


ENRICH: dict[str, dict] = {
    "P0A-005": {
        "language": A_PY,
        "target_files": ["tests/acceptance/test_p0a_005.py", "docs/acceptance/P0A-005.md",
                         "packages/physics/propulsion/battery.py", "data/research/registry.json"],
        "todos": todos(
            "Read docs/M21_BATTERY_EVIDENCE.md and data/research/registry.json; pin the exact DEVELOPMENT campaign rows, file hashes and clock/time definitions for the SIT replay and forecast study.",
            "Implement tests/acceptance/test_p0a_005.py: measured-current SIT replay and forecast-demand harness reproducing 63/63 replay and 68/68 missed 80 V study crossings against the frozen rows.",
            "Publish exact commands, time/event definitions and the failing regressions in docs/acceptance/P0A-005.md (with the pinned hashes).",
            "Freeze this baseline: change nothing in packages/physics in this task — the fixes are P0A-006.",
            "Run the declared verification commands and record the output in docs/acceptance/P0A-005.md."),
        "verify_commands": [
            "pytest tests/acceptance/test_p0a_005.py -q",
            "python scripts/reconcile_registry.py --check",
            "python scripts/check_master_plan.py --check"],
    },
    "P0A-006": {
        "language": A_PY,
        "target_files": ["packages/physics/propulsion/battery.py", "packages/desktop_worker/engine.py",
                         "tests/acceptance/test_p0a_006.py", "docs/acceptance/P0A-006.md"],
        "todos": todos(
            "Implement causal sag in the authoritative plant: load current -> pack R drop -> loaded bus voltage -> attainable voltage-dependent behavior, using the existing BatteryPack equations.",
            "Propagate cutoff/warning events with explicit bracketing of equality and timestep boundaries (event at t exactly on a step edge must fire deterministically).",
            "Propagate affected-component FAIL verdicts and supported bus-voltage effects into scenario results and the authoritative plant state.",
            "Guard against future-information leakage: no step may read a later SOC/current than its clock.",
            "Extend tests/acceptance/test_p0a_006.py for equality/boundary brackets and verdict propagation; re-run the frozen P0A-005 regressions and record the delta."),
        "verify_commands": [
            "pytest tests/acceptance/test_p0a_006.py tests/acceptance/test_p0a_005.py -q",
            "pytest tests/physics -q"],
    },
    "P0A-007": {
        "language": A_PY,
        "target_files": ["tests/acceptance/test_p0a_007.py", "docs/acceptance/P0A-007.md",
                         "packages/physics/propulsion/battery.py"],
        "todos": todos(
            "Split the two scoring modes: measured-current replay (current is source data) and forecast demand (current is model output); never mix them in one score.",
            "Score every unchanged source row: cutoff misses/false alarms, endpoint SOC/error, charge/energy balances.",
            "Add timestep-convergence cases for the replay and forecast paths and record the convergence table.",
            "Document per-run results and exclusions in docs/acceptance/P0A-007.md."),
        "verify_commands": [
            "pytest tests/acceptance/test_p0a_007.py -q",
            "pytest tests/acceptance/test_p0a_005.py tests/acceptance/test_p0a_006.py -q"],
    },
    "P0A-008": {
        "language": A_PY,
        "target_files": ["tests/acceptance/test_p0a_008.py", "docs/acceptance/P0A-008.md",
                         "data/research/registry.json"],
        "todos": todos(
            "Reproduce the signed-CT disagreement case with original source hashes and the exact pinned rows (no repaired data).",
            "Inspect, one at a time and recorded: coordinate axes/normal conventions, advance-ratio handling, RPM units, thrust/power sign definitions, and the near-zero measurement resolution of the source instrument.",
            "Write the evidence-backed cause (or the shortlist with the discriminating experiment) into docs/acceptance/P0A-008.md.",
            "Change no model behavior in this task — diagnosis only."),
        "verify_commands": [
            "pytest tests/acceptance/test_p0a_008.py -q",
            "python scripts/reconcile_registry.py --check"],
    },
    "P0A-009": {
        "language": A_PY,
        "target_files": ["packages/physics/aerodynamics/", "tests/acceptance/test_p0a_009.py",
                         "docs/acceptance/P0A-009.md"],
        "todos": todos(
            "Implement the corrected supported signed-thrust/signed-speed regime with explicit analytic frame/force checks (sign preservation end to end).",
            "Refuse or explicitly label any extrapolation outside the supported signed regime.",
            "Publish all DEVELOPMENT sweep residuals and exclusions; M24 acceptance uses only the supported envelope.",
            "Re-run the P0A-008 diagnosis against the corrected model and record the agreement."),
        "verify_commands": [
            "pytest tests/acceptance/test_p0a_009.py -q",
            "pytest packages/physics -q 2>/dev/null; pytest tests/physics -q"],
    },
    "P0A-010": {
        "language": A_PY,
        "target_files": ["tests/acceptance/test_p0a_010.py", "docs/acceptance/P0A-010.md"],
        "todos": todos(
            "Reproduce the M25 decisions per WHOLE recording: rotor-order classes and ESC-power anomalies with the frozen thresholds.",
            "Preserve all source exclusions and labels exactly; no label may leak into features.",
            "Tabulate missed classes and false alarms per recording and identify the systematic causes.",
            "Freeze the failure reproduction before any detector change (fixes are P0A-011)."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_010.py -q"],
    },
    "P0A-011": {
        "language": A_PY,
        "target_files": ["tests/acceptance/test_p0a_011.py", "docs/acceptance/P0A-011.md"],
        "todos": todos(
            "Make DETECT / NO-ALERT / INCONCLUSIVE explicit outcomes of the detector contract (an alert must name its class and deadline).",
            "Correct the detection logic with grouped, disjoint training/evaluation recordings — no whole-recording leakage in either direction.",
            "Add confirmation/hysteresis rules so single-sample false alarms cannot raise an alert.",
            "Re-run the P0A-010 reproduction and record the per-class improvements and remaining misses."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_010.py tests/acceptance/test_p0a_011.py -q"],
    },
    "P0A-012": {
        "language": A_PY,
        "target_files": ["packages/physics/propulsion/", "packages/physics/controller/",
                         "tests/acceptance/test_p0a_012.py", "docs/acceptance/P0A-012.md"],
        "todos": todos(
            "Propagate per-branch electrical state: unequal branch current, voltage, RPM, thermal and actuator limits produce FAIL on the affected component.",
            "Model only the supported loss/derating behaviors (loss of one branch, reduced-voltage derating); unknown post-failure behavior yields INCONCLUSIVE, never a synthesized recovery.",
            "Assert control-authority changes after derating are reflected in attainable attitude/altitude responses.",
            "Extend the acceptance tests for each supported failure class."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_012.py -q"],
    },
    "P0A-013": {
        "language": A_PY,
        "target_files": ["tests/acceptance/test_p0a_013.py", "docs/acceptance/P0A-013.md",
                         "data/research/registry.json"],
        "todos": todos(
            "Reproduce the QDrone original-vs-battery-aware MPC observations and the conditional-model failure from the frozen source rows.",
            "Identify and record the 14 V line as study-specific (not a pack property).",
            "Mark logged auxiliary/drive commands as measured inputs (not free model outputs) in the registry and evidence.",
            "Freeze the regression before any controller-coupling change (P0A-014)."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_013.py -q",
                            "python scripts/reconcile_registry.py --check"],
    },
    "P0A-014": {
        "language": A_PY,
        "target_files": ["packages/physics/controller/", "packages/physics/propulsion/",
                         "packages/desktop_worker/engine.py",
                         "tests/acceptance/test_p0a_014.py", "docs/acceptance/P0A-014.md"],
        "todos": todos(
            "Couple demand, bus voltage/current, attainable thrust, saturation and the supported controller/actuator dynamics on ONE plant state and ONE declared clock.",
            "Prove no generated command depends on future telemetry (causality test over reordered/stepped clocks).",
            "Cover the known limit interactions: bus sag -> attainable thrust -> saturation -> controller response, with boundary brackets.",
            "Extend tests/acceptance/test_p0a_014.py for each coupling edge and the shared-clock guarantee."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_014.py -q",
                            "pytest tests/acceptance/test_p0a_006.py tests/acceptance/test_p0a_012.py -q"],
    },
    "P0A-015": {
        "language": A_PY,
        "target_files": ["packages/physics/", "tests/acceptance/test_p0a_015.py",
                         "docs/acceptance/P0A-015.md"],
        "todos": todos(
            "Verify analytic force/torque identities for the corrected plant (sum of rotor contributions vs plant output).",
            "Verify energy and charge balances over closed integrations (consumed charge == integral of current within declared numerical tolerance).",
            "Verify quaternion/coordinate round trips (body<->world, wxyz convention) for randomized attitudes.",
            "Add timestep-convergence and deterministic seeded-rerun cases; cover the failure-boundary regressions from P0A-012.",
            "Publish the declared numerical tolerances in docs/acceptance/P0A-015.md."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_015.py -q",
                            "pytest tests/physics -q"],
    },
    "P0A-016": {
        "language": A_PY,
        "target_files": ["data/research/registry.json", "data/components/",
                         "packages/shared-schemas/", "tests/acceptance/test_p0a_016.py",
                         "docs/acceptance/P0A-016.md"],
        "todos": todos(
            "Extend the component registry records: units, physical identity, source citation, operating limits and parameter-level evidence links for battery/motor/ESC/wiring/material/sensor records.",
            "Mark every unsourced typical value and assumed uncertainty band UNVERIFIED_ESTIMATE and surface that flag in the UI/exports.",
            "Refuse mass-property computation when a required density/source is missing (fail closed).",
            "Add acceptance tests asserting each record carries the mandated fields."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_016.py -q",
                            "python scripts/reconcile_registry.py --check"],
    },
    "P0A-017": {
        "language": A_GDPY,
        "target_files": ["apps/desktop/main.gd", "apps/desktop/main.tscn",
                         "scripts/lab_project.py", "packages/desktop_worker/",
                         "tests/acceptance/test_p0a_017.py", "docs/acceptance/P0A-017.md"],
        "todos": todos(
            "Implement the normal Godot UI workflow: create, import, open, save, version and reopen a supported project entirely through the local worker (no HTTP server).",
            "Handle corrupt/missing assets and incompatible project versions with explicit recovery or refusal paths.",
            "Preserve project numeric identity through desktop round trips (existing JSON-authoritative tests stay green).",
            "Add acceptance tests driving the worker contract from the UI entry points."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_017.py -q",
                            "pytest tests/integration -q"],
    },
    "P0A-018": {
        "language": A_GD,
        "target_files": ["apps/desktop/", "tests/acceptance/test_p0a_018.py",
                         "docs/acceptance/P0A-018.md"],
        "todos": todos(
            "Implement supported exact body/blade geometry editing in the 3D editor: transforms, dimensions and constraints through the normal UI.",
            "Add undo/redo with visible model support (display LOD must never alter the authored engineering geometry).",
            "Keep exact solids and engineering inputs authoritative in the saved project (worker-computed, UI-rendered).",
            "Add acceptance tests for the edit -> save -> reload -> exact-geometry identity."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_018.py -q"],
    },
    "P0A-019": {
        "language": A_GDPY,
        "target_files": ["apps/desktop/", "scripts/lab_worker.py",
                         "packages/physics/dynamics/", "tests/acceptance/test_p0a_019.py",
                         "docs/acceptance/P0A-019.md"],
        "todos": todos(
            "Wire supported arbitrary rotor counts/layouts and component selection from the editor into the worker mass-property assembly.",
            "Update mass, CoG, inertia, powertrain and BOM through the authoritative assembly; render in the UI from the same numbers.",
            "Add independent analytic geometry cases (known layouts -> known CoG/inertia).",
            "Refuse mass-property computation on missing density/source (fail closed) and surface the refusal in the UI."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_019.py -q",
                            "pytest tests/physics/test_mass_properties.py -q"],
    },
    "P0A-020": {
        "language": A_PYPY,
        "target_files": ["packages/engineering-core/", "scripts/lab_cad.py",
                         "scripts/lab_cad_analysis.py", "tests/acceptance/test_p0a_020.py",
                         "docs/acceptance/P0A-020.md"],
        "todos": todos(
            "Implement rotor/obstacle/assembly clearance and datum-transform checks from the exact CAD geometry through the native/OCCT core.",
            "Guarantee revision changes re-run the clearance checks; display LOD cannot change physics or clearance results.",
            "Keep analytic screening results visible in the UI alongside the exact checks.",
            "Add acceptance tests with known-overlap and known-clear fixtures through the real worker."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_020.py -q",
                            "pytest tests/cad -q"],
    },
    "P0A-021": {
        "language": A_GD,
        "target_files": ["apps/desktop/", "tests/acceptance/test_p0a_021.py",
                         "docs/acceptance/P0A-021.md"],
        "todos": todos(
            "Implement the engineering test-ground authoring UI: terrain, obstacles, landing/contact surfaces, wind vector, temperature, pressure and humidity with units and declared origin.",
            "Refuse unsupported atmospheric/contact mechanisms explicitly (fail closed with the reason).",
            "Serialize the authored ground with the project and verify save/reload identity.",
            "Add acceptance tests for authoring, serialization and refusal paths."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_021.py -q"],
    },
    "P0A-022": {
        "language": A_GDPY,
        "target_files": ["apps/desktop/", "scripts/lab_worker.py",
                         "tests/acceptance/test_p0a_022.py", "docs/acceptance/P0A-022.md"],
        "todos": todos(
            "Implement mission authoring: takeoff/climb/hover/descent/landing phases, manual commands and disturbances with serialized commands and timings.",
            "Serialize controller/sensor settings and experiment seeds with the mission (replay reproduces the frozen experiment identically).",
            "Add acceptance tests: authored mission -> replay -> identical telemetry under the declared seed."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_022.py -q"],
    },
    "P0A-023": {
        "language": A_GDPY,
        "target_files": ["apps/desktop/", "scripts/lab_worker.py",
                         "packages/desktop_worker/engine.py", "packages/physics/",
                         "tests/acceptance/test_p0a_023.py", "docs/acceptance/P0A-023.md"],
        "todos": todos(
            "Run the supported design through the authoritative desktop simulation: a normal geometry/component/environment/mission edit must change the applicable simulated response.",
            "Drive playback from ONE double-precision integrator (no parallel approximate integrators).",
            "Implement pause/step/run/cancel and failure-state handling with worker supervision.",
            "Add acceptance tests for edit->response causality and the playback state machine."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_023.py -q",
                            "pytest tests/acceptance/test_p0a_014.py tests/acceptance/test_p0a_019.py -q"],
    },
    "P0A-024": {
        "language": A_GDPY,
        "target_files": ["apps/desktop/", "packages/desktop_worker/",
                         "tests/acceptance/test_p0a_024.py", "docs/acceptance/P0A-024.md"],
        "todos": todos(
            "Implement frozen-run vs source-measurement comparison in the UI: units, frames, source/model hashes, operating envelope, exclusions and uncertainty.",
            "Distinguish calculated, measured and interpolated values in every exported result.",
            "Add acceptance tests for the comparison pipeline with a frozen run and a pinned source measurement."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_024.py -q"],
    },
    "P0A-025": {
        "language": A_GDPY,
        "target_files": ["apps/desktop/", "packages/desktop_worker/engine.py",
                         "packages/physics/", "tests/acceptance/test_p0a_025.py",
                         "docs/acceptance/P0A-025.md"],
        "todos": todos(
            "Record requested vs effective timestep, backend, solver rates, numerical error and runtime budgets with every run.",
            "Prove interactive and offline runs of the same supported case agree within the declared tolerance (desktop worker vs headless integration).",
            "Expose the fidelity/budget panel in the UI from the recorded numbers (not free text).",
            "Add acceptance tests for the agreement bound and the recorded budgets."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_025.py -q",
                            "pytest tests/acceptance/test_p0a_023.py -q"],
    },
    "P0A-026": {
        "language": A_PY,
        "target_files": ["data/research/registry.json", "data/campaigns/",
                         "tests/acceptance/test_p0a_026.py", "docs/acceptance/P0A-026.md"],
        "todos": todos(
            "Freeze and register the validation protocols: model/controller/geometry versions, channels, instrument/clock uncertainties, calibration groups, held-out whole experiments, stopping rules and the M21–M27 tolerance bindings.",
            "Refuse protocol registration with missing calibration groups or held-out definitions (fail closed).",
            "Add acceptance tests asserting the frozen protocol records satisfy the registry contract."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_026.py -q",
                            "python scripts/reconcile_registry.py --check"],
    },
    "P0A-027": {
        "language": A_PY,
        "target_files": ["data/campaigns/", "data/research/registry.json",
                         "docs/acceptance/P0A-027.md"],
        "todos": todos(
            "CUSTODIAN (requires real external receipts): obtain legally usable exact-hardware/configuration battery, propulsion and sensor/controller measurements with original file hashes.",
            "Record calibration groups, environmental conditions, instrument identity and clock bases per campaign; preserve source bytes unmodified.",
            "Register each campaign in data/research/registry.json and reconcile; mark DEVELOPMENT/holdout partition per the prospective policy.",
            "No acceptance tests exist by design — the custodian receipts ARE the evidence; the registry reconciliation is the machine check."),
        "verify_commands": ["python scripts/reconcile_registry.py --check",
                            "python scripts/export_contracts.py --check"],
    },
    "P0A-028": {
        "language": A_PY,
        "target_files": ["tests/acceptance/test_p0a_028.py", "docs/acceptance/P0A-028.md",
                         "packages/physics/propulsion/", "packages/physics/propulsion/battery.py"],
        "todos": todos(
            "Score each independent component experiment (P0A-027 receipts) against the frozen M21–M23 error, limit and uncertainty criteria.",
            "Cover high-C discharge endpoints, transient torque/current/RPM and sensor/actuator timing per the frozen protocol.",
            "Publish per-campaign results; a criterion miss is FAILED VALIDATION, recorded — never re-banded after the fact.",
            "Update the component evidence records with the measured residuals."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_028.py -q",
                            "python scripts/reconcile_registry.py --check"],
    },
    "P0A-029": {
        "language": A_PY,
        "target_files": ["data/campaigns/", "tests/acceptance/test_p0a_029.py",
                         "docs/acceptance/P0A-029.md", "packages/physics/"],
        "todos": todos(
            "Freeze the end-to-end flight predictions BEFORE the flights are revealed: predictions, installed hardware, mission commands, payload, atmosphere, source custody and the joint uncertainty construction.",
            "Cover the supported failure modes in the frozen predictions (loss/derating/saturation) per P0A-012.",
            "Seal the frozen set with hashes in the registry; no post-hoc edits.",
            "Add acceptance tests asserting the frozen set is complete and hash-bound."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_029.py -q",
                            "python scripts/reconcile_registry.py --check"],
    },
    "P0A-030": {
        "language": A_PY,
        "target_files": ["data/campaigns/", "data/research/registry.json",
                         "docs/acceptance/P0A-030.md"],
        "todos": todos(
            "CUSTODIAN (requires real external receipts): obtain repeated hover/climb/descent/landing/control/disturbance/endurance flight trials on the frozen installed hardware, plus applicable heat/load evidence.",
            "Record telemetry channels, clocks, environmental conditions and custody per flight; keep the professional operational review separate from this acquisition.",
            "Register the sealed flight campaigns with original hashes; DEVELOPMENT/holdout partition per policy.",
            "No acceptance tests exist by design — the custodian receipts ARE the evidence."),
        "verify_commands": ["python scripts/reconcile_registry.py --check",
                            "python scripts/export_contracts.py --check"],
    },
    "P0A-031": {
        "language": A_PY,
        "target_files": ["tests/acceptance/test_p0a_031.py", "docs/acceptance/P0A-031.md",
                         "packages/physics/", "packages/desktop_worker/"],
        "todos": todos(
            "Score per-flight trajectories, energy, heat/control response and the frozen failure-mode predictions against the sealed flights (P0A-030) using the frozen M24–M26 criteria.",
            "Retain observed failures; separate conditional replay from the primary blind scores.",
            "Publish per-flight agreement tables and all exclusions with reasons."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_031.py -q",
                            "python scripts/reconcile_registry.py --check"],
    },
    "P0A-032": {
        "language": A_PY,
        "target_files": ["tests/acceptance/test_p0a_032.py", "docs/acceptance/P0A-032.md",
                         "packages/physics/"],
        "todos": todos(
            "Calibrate the joint whole-flight uncertainty: simultaneous M27 channel coverage and width limits per independent cohort.",
            "Include numerical, measurement, parameter, environment and model-discrepancy uncertainty terms explicitly (no single ±band collapse).",
            "Publish the calibration result and any cohort that fails the width limits as FAILED VALIDATION."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_032.py -q"],
    },
    "P0A-033": {
        "language": A_PY,
        "target_files": ["docs/acceptance/P0A-033.md"],
        "todos": todos(
            "REVIEWER (requires real external receipts): independently reproduce each intended-use acceptance from frozen inputs and original source bytes.",
            "Sign the scope/uncertainty/failure dossier and identify every unsupported configuration, parameter or claim.",
            "Record the review in docs/acceptance/P0A-033.md with the reviewer identity and the exact reproduced commands."),
        "verify_commands": ["pytest tests/acceptance/ -q"],
    },
    "P0A-034": {
        "language": A_GDPY,
        "target_files": ["apps/desktop/", "packages/desktop_worker/",
                         "tests/acceptance/test_p0a_034.py", "docs/acceptance/P0A-034.md"],
        "todos": todos(
            "Implement the guided learning workflow: state a hypothesis, build/modify a supported drone, enter environment conditions, compare runs, inspect equations/assumptions and save a reproducible experiment — all through the normal UI.",
            "Bind every saved experiment to the frozen inputs needed for exact replay.",
            "Add acceptance tests for the save -> reopen -> reproduce identity."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_034.py -q"],
    },
    "P0A-035": {
        "language": A_GDPY,
        "target_files": ["packages/optimization/", "apps/desktop/",
                         "tests/acceptance/test_p0a_035.py", "docs/acceptance/P0A-035.md"],
        "todos": todos(
            "Expose bounded parameter sweeps and design comparisons through the UI on the supported optimization package: constraints, seeds and all infeasible/failed candidates retained.",
            "Guarantee a repeat run reproduces the candidate/decision set exactly (seeded, hash-bound).",
            "Surface optimization-frontier caveats (no invented optimum) in the results view.",
            "Add acceptance tests for retention, reproduction and constraint handling."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_035.py -q",
                            "pytest tests/physics/test_optimization.py -q"],
    },
    "P0A-036": {
        "language": A_GDPY,
        "target_files": ["apps/desktop/", "scripts/lab_worker.py",
                         "packages/desktop_worker/", "tests/acceptance/test_p0a_036.py",
                         "docs/acceptance/P0A-036.md"],
        "todos": todos(
            "Package the standalone Windows application: desktop app, local shared services and required workers, with dependencies and notices included and no development HTTP server.",
            "Cover failed install/update/project-recovery paths with explicit user-visible handling.",
            "Add acceptance tests executed against the packaged layout (not the dev checkout)."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_036.py -q"],
    },
    "P0A-037": {
        "language": A_PY,
        "target_files": [".github/workflows/ci.yml", "tests/acceptance/test_p0a_037.py",
                         "docs/acceptance/P0A-037.md"],
        "todos": todos(
            "Keep all five exact-head CI jobs and the unchanged npm/backend/CAD audits passing; bind results to the final PR head.",
            "Cover project migration, incompatible assets, process ownership, budgets, interrupted work and save/recovery headless cases in acceptance tests.",
            "No audit bypasses: npm audit --audit-level=moderate including development dependencies stays required."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_037.py -q",
                            "pytest -q"],
    },
    "P0A-038": {
        "language": A_PY,
        "target_files": ["docs/acceptance/P0A-038.md", "tests/acceptance/test_p0a_038.py",
                         "outputs/"],
        "todos": todos(
            "Publish distinct 8 GB and 16 GB integrated-GPU installation/edit/run cases with CPU/GPU/OS/settings and measured frame-time/RAM data.",
            "Meet >=30 FPS on the declared 200-part editing workload and <=5 s project load on the recorded hardware.",
            "Take real measurements on the declared machines — synthetic or CI-host numbers do not qualify."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_038.py -q"],
    },
    "P0A-039": {
        "language": A_PY,
        "target_files": ["docs/acceptance/P0A-039.md", "tests/acceptance/test_p0a_039.py",
                         "docs/ACCEPTANCE_LEDGER.md"],
        "todos": todos(
            "Exit gate: verify every preceding software task required by this slice passes its normal-entry-point tests and independent numerical checks.",
            "Publish the scientific ledger listing accepted, failed and still-unvalidated capabilities — software slice exit and physical exit remain different gates.",
            "Record the exact commands and outputs in docs/acceptance/P0A-039.md."),
        "verify_commands": ["pytest -q",
                            "python scripts/check_master_plan.py --check",
                            "python scripts/export_contracts.py --check",
                            "python scripts/reconcile_registry.py --check"],
    },
    "P0A-040": {
        "language": A_PY,
        "target_files": ["docs/acceptance/P0A-040.md", "tests/acceptance/test_p0a_040.py",
                         "docs/ACCEPTANCE_LEDGER.md"],
        "todos": todos(
            "Physical exit gate: assemble the P0A-033 signed dossier, the M21–M27 acceptance results and the open physical gates.",
            "Accept only the demonstrated matching multirotor envelope under the frozen criteria; make no universal drone-equivalence claim and keep unresolved physical gates open.",
            "Record the final envelope statement and open gates in docs/acceptance/P0A-040.md and the ledger."),
        "verify_commands": ["pytest tests/acceptance/test_p0a_040.py -q",
                            "python scripts/check_master_plan.py --check"],
    },
}


def main() -> int:
    plan = json.loads(PLAN.read_text(encoding="utf-8-sig"))
    applied = 0
    missing = []
    for task in plan["tasks"]:
        if task["stage"] == "0A" and task["status"] == "todo":
            detail = ENRICH.get(task["id"])
            if detail is None:
                missing.append(task["id"])
                continue
            task["language"] = detail["language"]
            task["target_files"] = detail["target_files"]
            task["todos"] = detail["todos"]
            task["verify_commands"] = detail["verify_commands"]
            applied += 1
    if missing:
        raise SystemExit(f"enrichment missing for: {missing}")
    PLAN.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"enriched {applied} Stage 0A tasks with language/target_files/todos/verify_commands")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
