# Acceptance ledger

Canonical status, **20 November 2026**. [ROADMAP](ROADMAP.md) defines sequence; [PRODUCT_SPEC](PRODUCT_SPEC.md) defines scope. Historical reports remain unchanged. Software checks do not grant physical acceptance.

## Preserved baseline

Main before this PR: `8a511949a639b8b42d27a9c7ba9967b661db1c06`; [CI run 44772051060](https://github.com/god88844-hub/aerodynamics-lab/actions/runs/44772051060) passed all five jobs. Its reported suites: backend **1110 passed / 6 skipped**, CAD **27 passed**, Windows worker/contracts **26 passed**, web **148 passed**, native CTest **1 passed**, Playwright **1 passed**; Godot smoke and authenticated HTTPS scripts passed. These are baseline counts, not claims about this PR's eventual head.

The 21-file WIP baseline is preserved on remote [archive/aeroforge-wip-2026-11](https://github.com/god88844-hub/aerodynamics-lab/tree/archive/aeroforge-wip-2026-11), commit `a1d7313146b687e78468df9a5b66a3920120092c`. Two paths were already in baseline main; provenance changes in two additional paths were promoted; **17 paths retain unpromoted changes**. The exact 21-path disposition and blob identities are in [LEGACY_WIP_MANIFEST](LEGACY_WIP_MANIFEST.md); do not apply unrelated quarantined work. Repository identity is `god88844-hub/aerodynamics-lab`, GitHub ID `1459120659`; original AeroForge identities remain in provenance records.

## Foundation lock status

| Deliverable | Proof | Status |
| --- | --- | --- |
| Architecture/web boundary | [ARCHITECTURE](ARCHITECTURE.md): Godot ↔ shared `apps/api` services, local HTTP optional; web frozen | Present; owner review pending |
| M21–M27 tolerances and whole-flight joint UQ | [VALIDATION_TOLERANCES](VALIDATION_TOLERANCES.md), policy 1.0.0 | Prospective; owner/qualified review pending |
| Geometry-to-aero seam | `packages/shared-schemas/aeroforge_schemas/foundation.py`; `docs/contracts/wp1-wp3-1/geometry_aero.schema.json`, `aero_loads.schema.json`, `lock.json`; [contracts](contracts/README.md) | Machine-checked; BEMT/VLM/CFD execution unsupported; owner review pending |
| Local Godot/OCCT/solver prototype | [current PASS](prototypes/QUALIFICATION_GATE.md), [full receipts](prototypes/QUALIFICATION_GATE_LOCAL.md), [initial FAIL](prototypes/QUALIFICATION_GATE_INITIAL.md), [admission diagnosis](prototypes/ADMISSION_DIAGNOSIS.md) | PASS on recorded 16 GB laptop with adequate headroom; broader hardware matrix pending |

Current measured source is `0e3b9b7c36d4f43bceefcabb5f3402d40b870276`: 1800 focused visible frames, **60.0064147 FPS**, p95 **17.518 ms**, full CAD exercise/save/reopen/integrity successful. Actual CAD action-to-return **0.912879 s**, observed owned worker resident memory **606179328 bytes → exited**, normal bundled smoke/build **95.1656876 s** using verified cached tool archives and an existing fully installed bundled Python. This is not a fresh-download timing or a general minimum-system requirement. All raw receipts and precise timing boundaries are in the report.

The original admission correctly refused: total **16636305408**, available **2323255296**, reserve **2079538176**, worker allowance **1073741824** bytes; shortfall **830024704**. Historical free+zero bytes were not logged. No policy reduction was made. Memory/workspace guards are sampled limits, not OS hard quotas; process retirement enforces cancellation/deadlines.

**Review boundary:** keep this PR open. No tag or Slice 0A execution. WP7–WP9, CAD expansion and physics edits remain held despite local PASS.

## Twelve work packages

All 12 issue scopes remain open; prototype completion does not close a whole package. The following describes implemented paths and representative verification, with physical acceptance separately recorded.

| WP / issue / slices | What runs / verification paths | Physical status and concrete remaining dependency |
| --- | --- | --- |
| 1 #99 / 0A–0D | Project import/normalization and locked contracts: `packages/shared-schemas/aeroforge_schemas/`, `scripts/export_contracts.py`; `tests/integration/test_engineering_projects.py` | UNVALIDATED product foundation; owner lock review and remaining contract acceptance. |
| 2 #100 / 0A–0D | Godot `apps/desktop/main.gd`, native `packages/engineering-core`, supervised workers; `apps/desktop/smoke_test.gd`, local gate receipts | Software prototype PASS only; installation and 8 GB/dedicated/remote matrix pending. |
| 3 #101 / 0A–0D | Constrained solid/blade, asset round trips, mass→isolated torque: `packages/geometry/`, `tests/cad/test_cad_mass_dynamics.py`, `tests/integration/test_project_assets.py` | UNVALIDATED against physical CAD/as-built measurements. Full sketch/history/assembly/drawings and geometry→flight missing; expansion held. |
| 4 #102 / 0A–0D | Fixed scenarios `packages/physics/scenarios/`; relative wind `tests/physics/test_wind_relative_drag.py` | UNVALIDATED full world/contact/weather; saved environment/mission authoring and reference measurements pending. |
| 5 #103 / 0A–0C | Static battery/bus/powertrain `packages/physics/propulsion/`, numerical/failure screens and offline campaign scripts; battery/evidence API tests | Measured comparisons exist, broad acceptance UNVALIDATED. First dependencies: M21, M24, M25, M26 failures below. |
| 6 #104 / 0A–0C | Legacy multirotor controller/scenarios `packages/physics/controller/`, `tests/physics/test_controller.py` | Full-aircraft UNVALIDATED; four-family project representation does not implement four flight models. Requires qualified WP3–5. |
| 7 #110 / 0B–0D | Offline numerical/screening tools, no complete integrated detailed-solver workflow | UNVALIDATED; HOLD until explicit release and WP1–6 dependencies. |
| 8 #105 / 0D | Dry-air/relative-wind foundation only | UNVALIDATED coupled wet/snow/icing; HOLD; WP4–6 and matched mechanism data absent. |
| 9 #106 / 0D | Basic PID and offline HIL comparison `tests/integration/test_hil_evidence_api.py` | UNVALIDATED complete sensor/autopilot/autonomy; HOLD; latency/firmware/hardware and WP4–6 required. |
| 10 #107 / 0A–0D | Legacy manual/scenarios/offline sweeps; existing web remains frozen | UNVALIDATED complete desktop learning/invention workflow; needs supported design/run loop. |
| 11 #108 / all | Hashed ingestion, campaign comparisons and UQ: `tests/physics/test_flight_evidence.py`, `test_flight_uncertainty.py`, `tests/integration/test_public_evidence_api.py` | All 20 inspected campaigns DEVELOPMENT; new frozen confirmatory measurements, calibrated uncertainty and independent review needed. |
| 12 #109 / all, final 0D | Five CI jobs, dependency audits, packaged app/HTTPS and `tests/integration/test_database_snapshot.py` | Decision-grade release open; complete supported workflows, independent scientific review and compatibility/recovery needed. |

## Ten legacy major acceptance families

Each remains **OPEN**. “Measured comparison” below describes source-specific historical evaluations, not a passed prospective tolerance policy. The new policy cannot retrospectively turn inspected data into blind validation.

| Gate / slice | Implemented evidence | Scientific acceptance / concrete blocker |
| --- | --- | --- |
| M21 / 0A onward | Battery/replay/forecast scorers; `tests/physics/test_sit_module_benchmark.py`, `test_sit_cutoff_forecast.py`; [SIT results](campaigns/M21_6_10_SIT_MODULE_ELECTROTHERMAL.md) | UNVALIDATED battery/endurance gate. Mid/late dynamic voltage MAE 0.527/0.831 V, but 63/63 module cutoff crossings missed; [forecast](campaigns/M21_11_15_SIT_CUTOFF_FORECAST.md) misses 68/68. No blind prospective tolerance pass. |
| M22 / 0A onward | Static/transient bench comparisons; [Kotarski](campaigns/M22_KOTARSKI_SETUP3_BENCHMARK.md), [Gemfan](campaigns/M22_6_10_GEMFAN_TRANSIENTS.md); `tests/integration/test_propulsion_evidence_api.py` | Measured comparison; full installed electrical/mechanical/thermal/transient envelope UNVALIDATED. Manufacturer fits are calibration. |
| M23 / 0A onward | PID, offline HIL and [DronePropA altitude](campaigns/M23_3_7_DRONEPROPA_ALTITUDE.md); `tests/physics/test_hil_evidence.py` | UNVALIDATED complete sensors/controller. Fitted reference-response model is not end-to-end hardware/controller validation. |
| M24 / 0A–0D | [UIUC](campaigns/M24_2_6_UIUC_AXIAL_SWEEPS.md), ModERA/NeuroBEM scorers; `tests/physics/test_uiuc_axial_sweeps.py` | UIUC 42 scored points: CT MAE 0.0006850, CP MAE 0.0003007, 1 thrust-sign disagreement; no predeclared acceptance tolerance/qualified uncertainty. Installed aero/thermal UNVALIDATED. |
| M25 / all | Structure/fault screens; `tests/physics/test_uav_fd_rotor_order.py`, `test_uav_fd_esc_power.py`, `test_advanced_structure.py` | [UAV-FD ESC power](campaigns/M25_7_11_UAV_FD_ESC_POWER.md) adds healthy false alert and misses both faults; combined detects one and misses one. Assembly/fatigue/failure propagation UNVALIDATED. |
| M26 / all | Independent source/channel/energy/response scorers; `tests/physics/test_qdrone_voltage_transfer.py`, `test_m26_30_34_m300_original_evidence.py` | [QDrone](campaigns/M26_50_54_QDRONE_VOLTAGE_TRANSFER.md) remains response study, 14 V line not universal cutoff. Complete matched commands/trajectory/energy/thermal/control validation UNVALIDATED; legacy 60 kg motor-out fails in simulation. |
| M27 / all | Assumption-based Monte Carlo and [DronePropA transfer](campaigns/M27_11_15_DRONEPROPA_TRANSFER.md); `tests/physics/test_flight_uncertainty.py` | Only 2/5 whole flights inside empirical bands despite 10109/10147 covered samples. Calibrated joint flight-level coverage UNVALIDATED; predeclared probability/uncertainty budget absent from historical comparison. |
| M28 / 0A–0D | Primitive/revision/DXF placement and constrained CAD prototype; [CAD mass/dynamics](prototypes/CAD_MASS_DYNAMICS.md) | Full supported CAD/workspace incomplete; physical geometry/strength acceptance UNVALIDATED. Numerical mass/inertia agreement is verification. |
| M29 / all | Locked dependency security, deployment/recovery, CI; `.github/workflows/ci.yml` | Production acceptance incomplete: native matrix, performance/recovery/full regression/release evidence. Software security success does not validate physics. |
| M30 / final 0D | Existing packaged web/API and prototype desktop | Not eligible for decision-grade full Phase 0 release; depends on applicable M21–M29, WP1–12 and independent review. |

## Next three tasks

1. Owner review of this foundation/spec-lock PR, contract/tolerance proposal and measured PASS; no automatic tag.
2. After explicit execution approval, 0A.1: reproduce M21 cutoff failures with frozen development regressions and source roles.
3. 0A.2: investigate signed UIUC regime error, followed by 0A.3 fault detection and 0A.4 causal QDrone coupling in the [ordered roadmap](ROADMAP.md#slice-0a--dependency-ordered-backlog).

**Remaining:** 12 broad Phase 0 packages; 10 legacy major acceptance families; 4 sequential slices. These counts overlap. No milestone is closed by documentation or the local prototype PASS. Phases 1–4 stay interfaces/registries only.
