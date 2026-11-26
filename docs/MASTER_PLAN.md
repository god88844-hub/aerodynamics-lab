# Master task and execution plan

21 November 2026. **Full standalone software plan; owner authorization recorded; implementation held.**

Qualification is complete. The primary product is `apps/desktop/`, the standalone Godot 3D application; shared engineering services remain usable without an HTTP server. `apps/web/` is frozen legacy (security and minimal compatibility only). Historical qualification receipts remain evidence, not a recurring development stage.

Tracking: [master issue #127](https://github.com/god88844-hub/aerodynamics-lab/issues/127), [PR #126](https://github.com/god88844-hub/aerodynamics-lab/pull/126). Proposed release marker: **`v0.0-plan-locked`**. This document does not approve merge, tagging, physical testing or physical acceptance.

## Next action and execution rules

**P0A-004 is complete** with the owner's actual authorization receipt. Merge/tag requires the three pre-merge checks and five green CI jobs; actual operation receipts are recorded afterward. **Owner authorized resuming implementation starting at P0A-016 (visual Forward+ PBR, Dual Digital-Twin % metrics, and reference architecture locked in docs/SIMULATION_VISION_AND_REFERENCE_STACK.md).** The next future software task is **P0A-016**.

1. Read `AGENTS.md`, this task's section, the linked fundamentals, `docs/SIMULATION_VISION_AND_REFERENCE_STACK.md` and the acceptance ledger. Use only the canonical local workspace in `WORKSPACE.md`.
2. When implementation is explicitly resumed, pick the first unchecked builder task in document order whose prerequisites are checked. A pending owner/custodian/reviewer task requires its real receipt; a builder cannot self-approve it or invent data.
3. Phase 0 follows numbered dependency order and WP7–WP9 follow their listed tasks. No repeated qualification stage is implied. Phases 1–4 remain interfaces/registries only until their entry gates.
4. Implement the named normal desktop/headless behavior and its verification target. Each unchecked test path below is a **planned acceptance test to implement**, not a claim that the file already exists.
5. Record the exact proof, update the canonical JSON, regenerate this document and sync every affected issue checklist. Commit after a completed milestone; merge only with the required final-head CI green.
6. Checkbox completion is a scoped task result. Scientific status is tracked separately in `ACCEPTANCE_LEDGER.md`; code, a shader, optimization or synthetic sensor output never counts as physical validation.

## Proof contract and blocked evidence

Every future `docs/acceptance/TASK-ID.md` must contain the normal entry-point command/journey; frozen project/model/controller/dependency and input hashes; test/CI URL and exact head; expected condition and measured outcome; failures/exclusions and supported domain. Physical comparisons additionally require raw dataset identity/rights, matching actual hardware/geometry/firmware/conditions, calibrated instrument/clock uncertainty, predeclared criteria and independent whole-experiment partitions/review. Targets without numbers must be frozen before confirmatory reveal; unset criteria are INCONCLUSIVE. Mark unsourced parameters `UNVERIFIED_ESTIMATE`.

A **software exit** allows the next software slice only after its specified functionality and verification pass and all physical gaps are disclosed. It does not close a **physical exit**. Independent measurements can remain blocked while dependency-ready software progresses; never check blocked evidence as complete. Final Phase 0 acceptance and future-phase entry require the explicit release/scientific gates. Work may use any suitable reference hardware, but every prediction/measurement comparison must match its own registered configuration.

Canonical state: [`planning/tasks.json`](planning/tasks.json). `python scripts/check_master_plan.py --check` verifies rendering, numbering, dependencies, coverage and the recorded GitHub-sync digest. It does not authenticate approvals, instruments or physical truth. Edit the JSON, then run `python scripts/check_master_plan.py --render`; direct checkbox-only edits fail the check.

## Work packages and slice mapping

| WP | Issue | Scope | Slices |
| --- | --- | --- | --- |
| 1 | [#99](https://github.com/god88844-hub/aerodynamics-lab/issues/99) | Foundation and contracts | 0A, 0B, 0C, 0D |
| 2 | [#100](https://github.com/god88844-hub/aerodynamics-lab/issues/100) | Standalone desktop application | 0A, 0B, 0C, 0D |
| 3 | [#101](https://github.com/god88844-hub/aerodynamics-lab/issues/101) | CAD and engineering assemblies | 0A, 0B, 0C, 0D |
| 4 | [#102](https://github.com/god88844-hub/aerodynamics-lab/issues/102) | World and experiment authoring | 0A, 0B, 0C, 0D |
| 5 | [#103](https://github.com/god88844-hub/aerodynamics-lab/issues/103) | Electrical systems and physical models | 0A, 0B, 0C, 0D |
| 6 | [#104](https://github.com/god88844-hub/aerodynamics-lab/issues/104) | Four aircraft families | 0A, 0B, 0C, 0D |
| 7 | [#110](https://github.com/god88844-hub/aerodynamics-lab/issues/110) | Interactive and detailed analysis | 0A, 0B, 0C, 0D |
| 8 | [#105](https://github.com/god88844-hub/aerodynamics-lab/issues/105) | Atmosphere and advanced weather | 0A, 0D |
| 9 | [#106](https://github.com/god88844-hub/aerodynamics-lab/issues/106) | Autonomy, sensors and multi-drone systems | 0D |
| 10 | [#107](https://github.com/god88844-hub/aerodynamics-lab/issues/107) | Learning and invention | 0A, 0B, 0C, 0D |
| 11 | [#108](https://github.com/god88844-hub/aerodynamics-lab/issues/108) | Scientific validation | 0A, 0B, 0C, 0D |
| 12 | [#109](https://github.com/god88844-hub/aerodynamics-lab/issues/109) | Production QA and release | 0A, 0B, 0C, 0D |

Tasks with several WPs appear in each relevant issue but retain one canonical ID/status; do not count their copies as extra tasks.

## Milestone checklists

- [ ] Slice 0A software exit — **P0A-039**
- [ ] Slice 0A physical exit — **P0A-040**
- [ ] Slice 0B software exit — **P0B-021**
- [ ] Slice 0B physical exit — **P0B-022**
- [ ] Slice 0C software exit — **P0C-023**
- [ ] Slice 0C physical exit — **P0C-024**
- [ ] Slice 0D software exit — **P0D-030**
- [ ] Slice 0D physical exit — **P0D-031**
- [ ] Phase 1 entry — **P1-001**; prerequisite **P0D-032**
- [ ] Phase 1 exit — **P1-008**
- [ ] Phase 2 entry — **P2-001**; prerequisite **P1-008**
- [ ] Phase 2 exit — **P2-008**
- [ ] Phase 3 entry — **P3-001**; prerequisite **P2-008**
- [ ] Phase 3 exit — **P3-008**
- [ ] Phase 4 entry — **P4-001**; prerequisite **P3-008**
- [ ] Phase 4 exit — **P4-008**

## Legacy M21–M30 acceptance crosswalk

| Major gate | Required task/evidence anchors | Current status |
| --- | --- | --- |
| M21 — battery | P0A-005, P0A-007, P0A-028, P0A-040 | OPEN; see scientific ledger |
| M22 — propulsion | P0A-014, P0A-028, P0C-017 | OPEN; see scientific ledger |
| M23 — sensors and controls | P0A-028, P0D-018, P0D-021 | OPEN; see scientific ledger |
| M24 — aero and thermal | P0A-009, P0B-014, P0C-017, P0D-011 | OPEN; see scientific ledger |
| M25 — structure and failures | P0A-012, P0C-017, P0D-027 | OPEN; see scientific ledger |
| M26 — complete flight | P0A-031, P0B-016, P0C-018, P0C-019 | OPEN; see scientific ledger |
| M27 — uncertainty | P0A-032, P0B-016, P0C-018, P0C-019, P0D-021 | OPEN; see scientific ledger |
| M28 — CAD workspace | P0D-001, P0D-027 | OPEN; see scientific ledger |
| M29 — production QA | P0D-024, P0D-025, P0D-026, P0D-027 | OPEN; see scientific ledger |
| M30 — release | P0D-031, P0D-032 | OPEN; see scientific ledger |

## Slice 0A — Multirotor design, simulation and evidence loop

<a name="p0a-001"></a>
- [x] **P0A-001 — Record the completed standalone desktop qualification** (WP1, WP2; actor: builder)
  - Prerequisites: none. Proof: [docs/prototypes/QUALIFICATION_GATE_FOLLOWUP.md](prototypes/QUALIFICATION_GATE_FOLLOWUP.md).
  - Acceptance: Keep the measured qualification PASS, source SHAs, failures and scope intact; no repeat qualification prerequisite for normal execution.
  - Recorded evidence: [docs/prototypes/QUALIFICATION_GATE_FOLLOWUP.md](prototypes/QUALIFICATION_GATE_FOLLOWUP.md), [https://github.com/god88844-hub/aerodynamics-lab/actions/runs/44790665814](https://github.com/god88844-hub/aerodynamics-lab/actions/runs/44790665814).

<a name="p0a-002"></a>
- [x] **P0A-002 — Preserve contracts, archive and development-evidence baseline** (WP1, WP11; actor: builder)
  - Prerequisites: P0A-001. Proof: [docs/contracts/wp1-wp3-1/lock.json](contracts/wp1-wp3-1/lock.json).
  - Acceptance: Contract export matches the existing lock; all 21 WIP paths remain traceable; all 20 inspected campaigns remain DEVELOPMENT; no physical gate promoted.
  - Recorded evidence: [docs/contracts/wp1-wp3-1/lock.json](contracts/wp1-wp3-1/lock.json), [docs/LEGACY_WIP_MANIFEST.md](LEGACY_WIP_MANIFEST.md), [data/registry.json](../data/registry.json).

<a name="p0a-003"></a>
- [x] **P0A-003 — Deliver the master checklist, workspace migration and GitHub task sync** (WP1, WP12; actor: builder)
  - Prerequisites: P0A-002. Proof: [docs/WORKSPACE.md](WORKSPACE.md).
  - Acceptance: All development work is under the requested workspace; 208 moved source files retain their hashes; generated plan validates and all 17 issue checklists match its digest.
  - Recorded evidence: [docs/WORKSPACE.md](WORKSPACE.md), [docs/planning/github_sync.json](planning/github_sync.json), [docs/MASTER_PLAN.md](MASTER_PLAN.md), [docs/planning/workspace_migration.json](planning/workspace_migration.json).

<a name="p0a-004"></a>
- [x] **P0A-004 — Record owner authorization for the planning lock** (WP1, WP12; actor: owner)
  - Prerequisites: P0A-003. Proof: [docs/acceptance/P0A-004.md](acceptance/P0A-004.md).
  - Acceptance: Actual owner authorization to merge/tag after the three pre-merge checks and green CI is recorded. Approval is distinct from the later operations: merge/tag/clean-main proof belongs to the PR conversation and Git refs after execution, never fabricated before merge. This request does not authorize P0A-005.
  - Recorded evidence: [docs/acceptance/P0A-004.md](acceptance/P0A-004.md).

<a name="p0a-005"></a>
- [x] **P0A-005 — Reproduce and freeze M21 cutoff regression cases** (WP5; actor: builder)
  - Prerequisites: P0A-004. Proof: [docs/acceptance/P0A-005.md](acceptance/P0A-005.md).
  - Acceptance: Reproduce the SIT 63/63 replay and 68/68 forecast missed 80 V study crossings using pinned DEVELOPMENT data; publish exact commands, time/event definitions and failing regressions before changes.
  - Language: Python.
  - Target files: `tests/acceptance/test_p0a_005.py`; `docs/acceptance/P0A-005.md`; `data/research/registry.json`.
  - Todos:
    - [x] 1. DONE — pinned DEVELOPMENT campaign rows, hashes and clock/time definitions read from docs/M21_BATTERY_CAMPAIGN.md, docs/campaigns/M21_6_10_SIT_MODULE_ELECTROTHERMAL.md, docs/campaigns/M21_11_15_SIT_CUTOFF_FORECAST.md and data/research/registry.json.
    - [x] 2. DONE — tests/acceptance/test_p0a_005.py reproduces 63/63 replay and 68/68 forecast missed 80 V crossings from the pinned workbook (full re-execution bit-identical).
    - [x] 3. DONE — exact commands, time/event definitions and failing regressions published in docs/acceptance/P0A-005.md with the pinned hashes.
    - [x] 4. DONE — packages/physics untouched; the causal fixes are P0A-006.
    - [x] 5. DONE — verification commands run and output recorded in docs/acceptance/P0A-005.md.
  - Verify: `pytest tests/acceptance/test_p0a_005.py -q` | `python scripts/reconcile_registry.py --check` | `python scripts/check_master_plan.py --check`
  - Planned verification: `pytest tests/acceptance/test_p0a_005.py`; required current-head CI.
  - Recorded evidence: [docs/acceptance/P0A-005.md](acceptance/P0A-005.md), [docs/campaigns/m21_sit_module_electrothermal_results.json](campaigns/m21_sit_module_electrothermal_results.json), [docs/campaigns/m21_sit_cutoff_forecast_results.json](campaigns/m21_sit_cutoff_forecast_results.json).

<a name="p0a-006"></a>
- [x] **P0A-006 — Correct causal battery sag and cutoff event propagation** (WP5; actor: builder)
  - Prerequisites: P0A-004, P0A-005. Proof: [docs/acceptance/P0A-006.md](acceptance/P0A-006.md).
  - Acceptance: Supported current, SOC, bus-voltage and cutoff events affect the authoritative plant and FAIL verdict; event bracketing handles equality and timestep boundaries; no future measured input or threshold tuning to confirmatory outcomes.
  - Language: Python.
  - Target files: `packages/physics/propulsion/battery.py`; `packages/physics/scenarios/runner.py`; `packages/physics/scenarios/service.py`; `scripts/benchmark_sit_causal_repair.py`; `tests/acceptance/test_p0a_005.py`; `tests/acceptance/test_p0a_006.py`; `docs/acceptance/P0A-006.md`; `docs/campaigns/m21_sit_causal_repair_delta.json`.
  - Todos:
    - [x] 1. battery.py: strict declared OCV support (fail closed below the calibrated knee region, no extrapolation), exact quadratic constant-power solve of V_bus = V_oc(SOC) - V_rc - I*R_int with voltage-collapse detection (stable upper root), max deliverable power, and deterministic sub-step cutoff/warning crossing bracketing. Existing method semantics stay byte-identical (the frozen SIT benchmarks call them).
    - [x] 2. Authoritative plant (verified: Godot -> scripts/lab_project.py run -> project_service.run_project -> simulation_service.run_simulation -> scenarios.service.run_flight -> runner.run_scenario -> LoopPowertrain.step; packages/desktop_worker/engine.py is the CAD engine, not the flight plant): causal per-tick order (solve at start-of-tick SOC), explicit demanded-power vs max-deliverable-power collapse gate, bracketed warning/cutoff events, latch-on-crossing warnings.
    - [x] 3. run_scenario converts powertrain fail-closed refusals into a named battery_voltage_collapse critical event (no invented post-failure thrust or state), records per-component verdicts (FAIL / NO_MODELED_LIMIT_BREACHED / NOT_SIMULATED) in ScenarioResult, and run_flight surfaces them.
    - [x] 4. Causality guard tests: perturbing the load after t_k leaves state and telemetry bit-identical up to and including t_k; equality and tick-edge bracketing; declared thresholds used verbatim from the component spec (no hardcoded tuning).
    - [x] 5. SIT delta: scripts/benchmark_sit_causal_repair.py re-runs the frozen calibration (cycles 1-50 only), applies the declared knee-anchor extension (component-table tail shape joined to the fitted curve; zero held-out tuning), evaluates replay + forecast with battery.py's canonical causal solver, and commits docs/campaigns/m21_sit_causal_repair_delta.json with the exact before-vs-after numbers. Frozen M21 artifacts untouched; the 4 stale strict-xfail markers in test_p0a_005.py are reconciled.
  - Verify: `pytest tests/acceptance/test_p0a_006.py tests/acceptance/test_p0a_005.py -q` | `pytest tests/physics -q` | `python scripts/check_master_plan.py --check` | `python scripts/export_contracts.py --check` | `python scripts/reconcile_registry.py --check`
  - Planned verification: `pytest tests/acceptance/test_p0a_006.py`; required current-head CI.
  - Recorded evidence: [docs/acceptance/P0A-006.md](acceptance/P0A-006.md), [docs/campaigns/m21_sit_causal_repair_delta.json](campaigns/m21_sit_causal_repair_delta.json), [tests/acceptance/test_p0a_006.py](../tests/acceptance/test_p0a_006.py).

<a name="p0a-007"></a>
- [x] **P0A-007 — Verify battery replay versus prospective endurance behavior** (WP5, WP11; actor: builder)
  - Prerequisites: P0A-004, P0A-006. Proof: [docs/acceptance/P0A-007.md](acceptance/P0A-007.md).
  - Acceptance: Separate measured-current replay from forecast demand; unchanged source rows are scored per run; cutoff misses/false alarms, endpoint error, charge/energy balances and timestep convergence are reported against frozen criteria. New physical acceptance stays open.
  - Language: Python.
  - Target files: `tests/acceptance/test_p0a_007.py`; `docs/acceptance/P0A-007.md`; `packages/physics/propulsion/battery.py`.
  - Todos:
    - [x] 1. Split the two scoring modes: measured-current replay (current is source data) and forecast demand (current is model output); never mix them in one score.
    - [x] 2. Score every unchanged source row: cutoff misses/false alarms, endpoint SOC/error, charge/energy balances.
    - [x] 3. Add timestep-convergence cases for the replay and forecast paths and record the convergence table.
    - [x] 4. Document per-run results and exclusions in docs/acceptance/P0A-007.md.
  - Verify: `pytest tests/acceptance/test_p0a_007.py -q` | `pytest tests/acceptance/test_p0a_005.py tests/acceptance/test_p0a_006.py -q`
  - Planned verification: `pytest tests/acceptance/test_p0a_007.py`; required current-head CI.
  - Recorded evidence: [docs/acceptance/P0A-007.md](acceptance/P0A-007.md), [docs/campaigns/m21_p0a_007_row_scores.json](campaigns/m21_p0a_007_row_scores.json), [tests/acceptance/test_p0a_007.py](../tests/acceptance/test_p0a_007.py).

<a name="p0a-008"></a>
- [x] **P0A-008 — Diagnose the UIUC signed-thrust disagreement** (WP5; actor: builder)
  - Prerequisites: P0A-004, P0A-007. Proof: [docs/acceptance/P0A-008.md](acceptance/P0A-008.md).
  - Acceptance: Reproduce the signed CT case with source hashes; inspect axes, advance ratio, RPM, units, power definition and near-zero measurement resolution. Record evidence for the cause; do not assume a sign flip is correct.
  - Language: Python.
  - Target files: `tests/acceptance/test_p0a_008.py`; `docs/acceptance/P0A-008.md`; `data/research/registry.json`.
  - Todos:
    - [x] 1. Reproduce the signed-CT disagreement case with original source hashes and the exact pinned rows (no repaired data).
    - [x] 2. Inspect, one at a time and recorded: coordinate axes/normal conventions, advance-ratio handling, RPM units, thrust/power sign definitions, and the near-zero measurement resolution of the source instrument.
    - [x] 3. Write the evidence-backed cause (or the shortlist with the discriminating experiment) into docs/acceptance/P0A-008.md.
    - [x] 4. Change no model behavior in this task — diagnosis only.
  - Verify: `pytest tests/acceptance/test_p0a_008.py -q` | `python scripts/reconcile_registry.py --check`
  - Planned verification: `pytest tests/acceptance/test_p0a_008.py`; required current-head CI.
  - Recorded evidence: [docs/acceptance/P0A-008.md](acceptance/P0A-008.md), [docs/campaigns/m24_uiuc_sign_disagreement_diagnosis.json](campaigns/m24_uiuc_sign_disagreement_diagnosis.json), [tests/acceptance/test_p0a_008.py](../tests/acceptance/test_p0a_008.py).

<a name="p0a-009"></a>
- [x] **P0A-009 — Correct and verify the supported signed aerodynamic regime** (WP5, WP11; actor: builder)
  - Prerequisites: P0A-004, P0A-008. Proof: [docs/acceptance/P0A-009.md](acceptance/P0A-009.md).
  - Acceptance: Analytical frame/force checks pass, source sign is preserved, extrapolation is refused or labeled, and all DEVELOPMENT sweep residuals/exclusions are published. M24 acceptance uses predeclared sign-resolution and uncertainty rules.
  - Language: Python.
  - Target files: `packages/physics/aerodynamics/`; `tests/acceptance/test_p0a_009.py`; `docs/acceptance/P0A-009.md`.
  - Todos:
    - [x] 1. Implement the corrected supported signed-thrust/signed-speed regime with explicit analytic frame/force checks (sign preservation end to end).
    - [x] 2. Refuse or explicitly label any extrapolation outside the supported signed regime.
    - [x] 3. Publish all DEVELOPMENT sweep residuals and exclusions; M24 acceptance uses only the supported envelope.
    - [x] 4. Re-run the P0A-008 diagnosis against the corrected model and record the agreement.
  - Verify: `pytest tests/acceptance/test_p0a_009.py -q` | `pytest packages/physics -q 2>/dev/null; pytest tests/physics -q`
  - Planned verification: `pytest tests/acceptance/test_p0a_009.py`; required current-head CI.
  - Recorded evidence: [docs/acceptance/P0A-009.md](acceptance/P0A-009.md), [docs/campaigns/m24_uiuc_signed_regime_delta.json](campaigns/m24_uiuc_signed_regime_delta.json), [tests/acceptance/test_p0a_009.py](../tests/acceptance/test_p0a_009.py), [packages/physics/aerodynamics/axial_prop.py](../packages/physics/aerodynamics/axial_prop.py).

<a name="p0a-010"></a>
- [x] **P0A-010 — Reproduce M25 misses and healthy-flight false alarms** (WP5; actor: builder)
  - Prerequisites: P0A-004, P0A-009. Proof: [docs/acceptance/P0A-010.md](acceptance/P0A-010.md).
  - Acceptance: Reproduce UAV-FD rotor-order and ESC-power decisions per whole recording; preserve exclusions, labels and thresholds; identify missed classes and false alarms without using labels as detector inputs.
  - Language: Python.
  - Target files: `tests/acceptance/test_p0a_010.py`; `docs/acceptance/P0A-010.md`.
  - Todos:
    - [x] 1. Reproduce the M25 decisions per WHOLE recording: rotor-order classes and ESC-power anomalies with the frozen thresholds.
    - [x] 2. Preserve all source exclusions and labels exactly; no label may leak into features.
    - [x] 3. Tabulate missed classes and false alarms per recording and identify the systematic causes.
    - [x] 4. Freeze the failure reproduction before any detector change (fixes are P0A-011).
  - Verify: `pytest tests/acceptance/test_p0a_010.py -q`
  - Planned verification: `pytest tests/acceptance/test_p0a_010.py`; required current-head CI.
  - Recorded evidence: [docs/acceptance/P0A-010.md](acceptance/P0A-010.md), [tests/acceptance/test_p0a_010.py](../tests/acceptance/test_p0a_010.py).

<a name="p0a-011"></a>
- [x] **P0A-011 — Correct fault detection without data leakage** (WP5, WP11; actor: builder)
  - Prerequisites: P0A-004, P0A-010. Proof: [docs/acceptance/P0A-011.md](acceptance/P0A-011.md).
  - Acceptance: Detection, no-alert and INCONCLUSIVE are explicit; whole-flight class/deadline/false-alarm regression cases pass; training and evaluation data remain grouped and disjoint; confirmatory performance is not inferred from development tuning.
  - Language: Python.
  - Target files: `packages/physics/validation/uav_fd_fault_detector.py`; `scripts/benchmark_p0a_011_uav_fd.py`; `scripts/p0a011_download_verified.py`; `scripts/check_master_plan.py`; `docs/campaigns/m25_p0a_011_detector_delta.json`; `tests/acceptance/test_p0a_011.py`; `docs/acceptance/P0A-011.md`.
  - Todos:
    - [x] 1. Make DETECT / NO-ALERT / INCONCLUSIVE explicit outcomes of the detector contract (an alert must name its class and deadline).
    - [x] 2. Correct the detection logic with grouped, disjoint training/evaluation recordings — no whole-recording leakage in either direction.
    - [x] 3. Add confirmation/hysteresis rules so single-sample false alarms cannot raise an alert.
    - [x] 4. Re-run the P0A-010 reproduction and record the per-class improvements and remaining misses.
  - Verify: `pytest tests/acceptance/test_p0a_010.py tests/acceptance/test_p0a_011.py -q` | `pytest tests/physics -q` | `python scripts/export_contracts.py --check` | `python scripts/reconcile_registry.py --check` | `python scripts/check_master_plan.py --check`
  - Planned verification: `pytest tests/acceptance/test_p0a_011.py`; required current-head CI.
  - Recorded evidence: [docs/acceptance/P0A-011.md](acceptance/P0A-011.md), [docs/campaigns/m25_p0a_011_detector_delta.json](campaigns/m25_p0a_011_detector_delta.json), [packages/physics/validation/uav_fd_fault_detector.py](../packages/physics/validation/uav_fd_fault_detector.py), [scripts/benchmark_p0a_011_uav_fd.py](../scripts/benchmark_p0a_011_uav_fd.py), [scripts/p0a011_download_verified.py](../scripts/p0a011_download_verified.py), [tests/acceptance/test_p0a_011.py](../tests/acceptance/test_p0a_011.py), [https://github.com/god88844-hub/aerodynamics-lab/actions/runs/45254467995](https://github.com/god88844-hub/aerodynamics-lab/actions/runs/45254467995).

<a name="p0a-012"></a>
- [x] **P0A-012 — Propagate per-rotor electrical and supported actuator failures** (WP5; actor: builder)
  - Prerequisites: P0A-011. Proof: [docs/acceptance/P0A-012.md](acceptance/P0A-012.md).
  - Acceptance: Unequal branch current, voltage, RPM, thermal or actuator limits produce FAIL on the affected component; supported loss/derating changes control authority; unknown post-failure behavior cannot create a successful trajectory.
  - Language: Python.
  - Target files: `packages/physics/propulsion/branches.py`; `packages/physics/propulsion/dataset.py`; `packages/physics/controller/mixer.py`; `packages/physics/controller/attitude.py`; `packages/physics/scenarios/runner.py`; `packages/physics/scenarios/service.py`; `tests/acceptance/test_p0a_012.py`; `docs/acceptance/P0A-012.md`.
  - Todos:
    - [x] 1. Propagate per-branch electrical state: unequal branch current, voltage, RPM, thermal and actuator limits produce FAIL on the affected component.
    - [x] 2. Model only the supported loss/derating behaviors (loss of one branch, reduced-voltage derating); unknown post-failure behavior yields INCONCLUSIVE, never a synthesized recovery.
    - [x] 3. Assert control-authority changes after derating are reflected in attainable attitude/altitude responses.
    - [x] 4. Extend the acceptance tests for each supported failure class.
  - Verify: `pytest tests/acceptance/test_p0a_012.py -q` | `pytest tests/acceptance/test_p0a_005.py tests/acceptance/test_p0a_006.py tests/acceptance/test_p0a_007.py tests/acceptance/test_p0a_008.py tests/acceptance/test_p0a_009.py tests/acceptance/test_p0a_010.py tests/acceptance/test_p0a_011.py -q` | `pytest tests/physics -q` | `python scripts/export_contracts.py --check` | `python scripts/reconcile_registry.py --check` | `python scripts/check_master_plan.py --check`
  - Planned verification: `pytest tests/acceptance/test_p0a_012.py`; required current-head CI.
  - Recorded evidence: [docs/acceptance/P0A-012.md](acceptance/P0A-012.md), [tests/acceptance/test_p0a_012.py](../tests/acceptance/test_p0a_012.py), [packages/physics/scenarios/runner.py](../packages/physics/scenarios/runner.py), [packages/physics/propulsion/branches.py](../packages/physics/propulsion/branches.py).

<a name="p0a-013"></a>
- [x] **P0A-013 — Freeze the QDrone collapse and command-provenance regression** (WP5; actor: builder)
  - Prerequisites: P0A-012. Proof: [docs/acceptance/P0A-013.md](acceptance/P0A-013.md).
  - Acceptance: Reproduce original versus battery-aware MPC observations and conditional-model failure; identify the 14 V line as study-specific, and mark logged auxiliary/drive commands as measurements rather than independently predicted commands.
  - Language: Python.
  - Target files: `tests/acceptance/test_p0a_013.py`; `docs/acceptance/P0A-013.md`; `data/research/registry.json`; `scripts/reconcile_registry.py`; `data/registry.json`.
  - Todos:
    - [x] 1. Reproduce the QDrone original-vs-battery-aware MPC observations and the conditional-model failure from the frozen source rows.
    - [x] 2. Identify and record the 14 V line as study-specific (not a pack property).
    - [x] 3. Mark logged auxiliary/drive commands as measured inputs (not free model outputs) in the registry and evidence.
    - [x] 4. Freeze the regression before any controller-coupling change (P0A-014).
  - Verify: `pytest tests/acceptance/test_p0a_013.py -q` | `pytest tests/physics -q` | `python scripts/export_contracts.py --check` | `python scripts/reconcile_registry.py --check` | `python scripts/check_master_plan.py --check`
  - Planned verification: `pytest tests/acceptance/test_p0a_013.py`; required current-head CI.
  - Recorded evidence: [docs/acceptance/P0A-013.md](acceptance/P0A-013.md), [tests/acceptance/test_p0a_013.py](../tests/acceptance/test_p0a_013.py), [data/research/registry.json](../data/research/registry.json), [data/registry.json](../data/registry.json).

<a name="p0a-014"></a>
- [x] **P0A-014 — Couple causal bus, propulsion and controller response** (WP5, WP6; actor: builder)
  - Prerequisites: P0A-013. Proof: [docs/acceptance/P0A-014.md](acceptance/P0A-014.md).
  - Acceptance: Demand, voltage/current, attainable thrust, saturation and supported controller/actuator dynamics share one plant/clock; generated commands do not depend on future telemetry; known limit violations retain FAIL and unsupported collapse remains INCONCLUSIVE.
  - Language: Python.
  - Target files: `packages/physics/controller/attitude.py`; `packages/physics/controller/pid.py`; `packages/physics/scenarios/runner.py`; `packages/physics/scenarios/service.py`; `scripts/run_capstone.py`; `tests/audit/test_m9_failure_modes.py`; `tests/acceptance/test_p0a_006.py`; `tests/acceptance/test_p0a_012.py`; `tests/acceptance/test_p0a_014.py`; `docs/acceptance/P0A-014.md`.
  - Todos:
    - [x] 1. Couple demand, bus voltage/current, attainable thrust, saturation and the supported controller/actuator dynamics on ONE plant state and ONE declared clock.
    - [x] 2. Prove no generated command depends on future telemetry (causality test over reordered/stepped clocks).
    - [x] 3. Cover the known limit interactions: bus sag -> attainable thrust -> saturation -> controller response, with boundary brackets.
    - [x] 4. Extend tests/acceptance/test_p0a_014.py for each coupling edge and the shared-clock guarantee.
  - Verify: `pytest tests/acceptance/test_p0a_014.py tests/acceptance/test_p0a_006.py tests/acceptance/test_p0a_012.py -q` | `pytest tests/physics -q` | `python scripts/export_contracts.py --check` | `python scripts/reconcile_registry.py --check` | `python scripts/check_master_plan.py --check`
  - Planned verification: `pytest tests/acceptance/test_p0a_014.py`; required current-head CI.
  - Recorded evidence: [docs/acceptance/P0A-014.md](acceptance/P0A-014.md), [tests/acceptance/test_p0a_014.py](../tests/acceptance/test_p0a_014.py), [packages/physics/scenarios/runner.py](../packages/physics/scenarios/runner.py), [packages/physics/scenarios/service.py](../packages/physics/scenarios/service.py).

<a name="p0a-015"></a>
- [x] **P0A-015 — Verify the corrected multirotor numerical model** (WP5, WP11; actor: builder)
  - Prerequisites: P0A-014. Proof: [docs/acceptance/P0A-015.md](acceptance/P0A-015.md).
  - Acceptance: Analytic force/torque, energy/charge checks, quaternion/coordinate round trips, timestep convergence, deterministic seeded reruns and failure-boundary regressions pass with declared numerical tolerances.
  - Language: Python.
  - Target files: `packages/physics/dynamics/quaternion.py`; `packages/physics/scenarios/runner.py`; `tests/acceptance/test_p0a_015.py`; `docs/acceptance/P0A-015.md`.
  - Todos:
    - [x] 1. Verify analytic force/torque identities for the corrected plant (sum of rotor contributions vs plant output).
    - [x] 2. Verify energy and charge balances over closed integrations (consumed charge == integral of current within declared numerical tolerance).
    - [x] 3. Verify quaternion/coordinate round trips (body<->world, wxyz convention) for randomized attitudes.
    - [x] 4. Add timestep-convergence and deterministic seeded-rerun cases; cover the failure-boundary regressions from P0A-012.
    - [x] 5. Publish the declared numerical tolerances in docs/acceptance/P0A-015.md.
  - Verify: `pytest tests/acceptance/test_p0a_015.py -q` | `pytest tests/physics -q` | `python scripts/export_contracts.py --check` | `python scripts/reconcile_registry.py --check` | `python scripts/check_master_plan.py --check`
  - Planned verification: `pytest tests/acceptance/test_p0a_015.py`; required current-head CI.
  - Recorded evidence: [docs/acceptance/P0A-015.md](acceptance/P0A-015.md), [tests/acceptance/test_p0a_015.py](../tests/acceptance/test_p0a_015.py), [packages/physics/dynamics/quaternion.py](../packages/physics/dynamics/quaternion.py), [packages/physics/scenarios/runner.py](../packages/physics/scenarios/runner.py).

<a name="p0a-016"></a>
- [ ] **P0A-016 — Make component sources and parameter uncertainty explicit** (WP1, WP5, WP11; actor: builder)
  - Prerequisites: P0A-015. Proof: [docs/acceptance/P0A-016.md](acceptance/P0A-016.md).
  - Acceptance: Battery/motor/ESC/wiring/material/sensor records carry units, identity, source, limits and parameter-level evidence; unsourced typical values and assumed uncertainty bands display UNVERIFIED_ESTIMATE; missing required limits refuse acceptance.
  - Language: Python.
  - Target files: `data/research/registry.json`; `data/components/`; `packages/shared-schemas/`; `tests/acceptance/test_p0a_016.py`; `docs/acceptance/P0A-016.md`.
  - Todos:
    - [ ] 1. Extend the component registry records: units, physical identity, source citation, operating limits and parameter-level evidence links for battery/motor/ESC/wiring/material/sensor records.
    - [ ] 2. Mark every unsourced typical value and assumed uncertainty band UNVERIFIED_ESTIMATE and surface that flag in the UI/exports.
    - [ ] 3. Refuse mass-property computation when a required density/source is missing (fail closed).
    - [ ] 4. Add acceptance tests asserting each record carries the mandated fields.
  - Verify: `pytest tests/acceptance/test_p0a_016.py -q` | `python scripts/reconcile_registry.py --check`
  - Planned verification: `pytest tests/acceptance/test_p0a_016.py`; required current-head CI.

<a name="p0a-017"></a>
- [ ] **P0A-017 — Deliver the standalone desktop project workflow** (WP2; actor: builder)
  - Prerequisites: P0A-015. Proof: [docs/acceptance/P0A-017.md](acceptance/P0A-017.md).
  - Acceptance: Normal Godot UI creates/imports/opens/saves/versions/reopens a supported project without an HTTP server; corrupt/missing assets and incompatible versions are handled; recovery preserves the last valid project.
  - Language: GDScript, Python.
  - Target files: `apps/desktop/main.gd`; `apps/desktop/main.tscn`; `scripts/lab_project.py`; `packages/desktop_worker/`; `tests/acceptance/test_p0a_017.py`; `docs/acceptance/P0A-017.md`.
  - Todos:
    - [ ] 1. Implement the normal Godot UI workflow: create, import, open, save, version and reopen a supported project entirely through the local worker (no HTTP server).
    - [ ] 2. Handle corrupt/missing assets and incompatible project versions with explicit recovery or refusal paths.
    - [ ] 3. Preserve project numeric identity through desktop round trips (existing JSON-authoritative tests stay green).
    - [ ] 4. Add acceptance tests driving the worker contract from the UI entry points.
    - [ ] 5. Configure the Godot 4.7 Forward+ PBR desktop profile alongside gl_compatibility fallback for Tier 1 laptops and headless Linux CI (see docs/SIMULATION_VISION_AND_REFERENCE_STACK.md).
  - Verify: `pytest tests/acceptance/test_p0a_017.py -q` | `pytest tests/integration -q`
  - Planned verification: `pytest tests/acceptance/test_p0a_017.py`; required current-head CI.

<a name="p0a-018"></a>
- [ ] **P0A-018 — Build supported multirotor geometry through the 3D editor** (WP2, WP3; actor: builder)
  - Prerequisites: P0A-017. Proof: [docs/acceptance/P0A-018.md](acceptance/P0A-018.md).
  - Acceptance: Normal UI edits supported exact body/blade geometry, transforms and dimensions with constraints, undo/redo and visible model support. Exact solids and engineering inputs remain authoritative across save/reopen; no placement-only screen is labeled full CAD.
  - Language: GDScript.
  - Target files: `apps/desktop/`; `tests/acceptance/test_p0a_018.py`; `docs/acceptance/P0A-018.md`.
  - Todos:
    - [ ] 1. Implement supported exact body/blade geometry editing in the 3D editor: transforms, dimensions and constraints through the normal UI.
    - [ ] 2. Add undo/redo with visible model support (display LOD must never alter the authored engineering geometry).
    - [ ] 3. Keep exact solids and engineering inputs authoritative in the saved project (worker-computed, UI-rendered).
    - [ ] 4. Add acceptance tests for the edit -> save -> reload -> exact-geometry identity.
    - [ ] 5. Apply Fusion-style CAD material presets (Al 6061-T6, CFRP, PA12), clean edge/selection shading, and studio/outdoor HDRI lighting in the 3D editor while keeping display LOD strictly separate from Open CASCADE solids.
  - Verify: `pytest tests/acceptance/test_p0a_018.py -q`
  - Planned verification: `pytest tests/acceptance/test_p0a_018.py`; required current-head CI.

<a name="p0a-019"></a>
- [ ] **P0A-019 — Connect component layout, materials, BOM and mass properties** (WP3, WP5, WP6; actor: builder)
  - Prerequisites: P0A-018, P0A-016. Proof: [docs/acceptance/P0A-019.md](acceptance/P0A-019.md).
  - Acceptance: Supported arbitrary rotor counts/layouts and component selection update mass, CoG, inertia, powertrain and BOM; independent analytic geometry cases pass; missing density refuses mass and flight acceptance.
  - Language: GDScript, Python.
  - Target files: `apps/desktop/`; `scripts/lab_worker.py`; `packages/physics/dynamics/`; `tests/acceptance/test_p0a_019.py`; `docs/acceptance/P0A-019.md`.
  - Todos:
    - [ ] 1. Wire supported arbitrary rotor counts/layouts and component selection from the editor into the worker mass-property assembly.
    - [ ] 2. Update mass, CoG, inertia, powertrain and BOM through the authoritative assembly; render in the UI from the same numbers.
    - [ ] 3. Add independent analytic geometry cases (known layouts -> known CoG/inertia).
    - [ ] 4. Refuse mass-property computation on missing density/source (fail closed) and surface the refusal in the UI.
  - Verify: `pytest tests/acceptance/test_p0a_019.py -q` | `pytest tests/physics/test_mass_properties.py -q`
  - Planned verification: `pytest tests/acceptance/test_p0a_019.py`; required current-head CI.

<a name="p0a-020"></a>
- [ ] **P0A-020 — Integrate geometry clearance and supported load checks** (WP3; actor: builder)
  - Prerequisites: P0A-018. Proof: [docs/acceptance/P0A-020.md](acceptance/P0A-020.md).
  - Acceptance: Rotor/obstacle/assembly clearance and datum transforms are checked from engineering geometry, including revision changes; LOD cannot change physics/clearance; screens retain analytical versus physically qualified status.
  - Language: Python, C++20.
  - Target files: `packages/engineering-core/`; `scripts/lab_cad.py`; `scripts/lab_cad_analysis.py`; `tests/acceptance/test_p0a_020.py`; `docs/acceptance/P0A-020.md`.
  - Todos:
    - [ ] 1. Implement rotor/obstacle/assembly clearance and datum-transform checks from the exact CAD geometry through the native/OCCT core.
    - [ ] 2. Guarantee revision changes re-run the clearance checks; display LOD cannot change physics or clearance results.
    - [ ] 3. Keep analytic screening results visible in the UI alongside the exact checks.
    - [ ] 4. Add acceptance tests with known-overlap and known-clear fixtures through the real worker.
  - Verify: `pytest tests/acceptance/test_p0a_020.py -q` | `pytest tests/cad -q`
  - Planned verification: `pytest tests/acceptance/test_p0a_020.py`; required current-head CI.

<a name="p0a-021"></a>
- [ ] **P0A-021 — Author a repeatable engineering test ground** (WP4, WP8; actor: builder)
  - Prerequisites: P0A-017. Proof: [docs/acceptance/P0A-021.md](acceptance/P0A-021.md).
  - Acceptance: Normal UI saves terrain, obstacles, landing/contact surfaces, wind vector, temperature, pressure and humidity with units/origin. Unsupported atmospheric/contact mechanisms are refused or unvalidated, not implemented by a visual shader.
  - Language: GDScript.
  - Target files: `apps/desktop/`; `tests/acceptance/test_p0a_021.py`; `docs/acceptance/P0A-021.md`.
  - Todos:
    - [ ] 1. Implement the engineering test-ground authoring UI: terrain, obstacles, landing/contact surfaces, wind vector, temperature, pressure and humidity with units and declared origin.
    - [ ] 2. Refuse unsupported atmospheric/contact mechanisms explicitly (fail closed with the reason).
    - [ ] 3. Serialize the authored ground with the project and verify save/reload identity.
    - [ ] 4. Add acceptance tests for authoring, serialization and refusal paths.
    - [ ] 5. Support clean PBR engineering test-ground materials and lighting cues while keeping visual shaders strictly separate from aerodynamic and contact physics.
  - Verify: `pytest tests/acceptance/test_p0a_021.py -q`
  - Planned verification: `pytest tests/acceptance/test_p0a_021.py`; required current-head CI.

<a name="p0a-022"></a>
- [ ] **P0A-022 — Author missions, controls, clocks and experiment seeds** (WP4; actor: builder)
  - Prerequisites: P0A-021. Proof: [docs/acceptance/P0A-022.md](acceptance/P0A-022.md).
  - Acceptance: Takeoff/climb/hover/descent/landing, manual commands and disturbances serialize commands, timings, controller/sensor settings and seeds; replay reproduces the frozen experiment independently of render cadence.
  - Language: GDScript, Python.
  - Target files: `apps/desktop/`; `scripts/lab_worker.py`; `tests/acceptance/test_p0a_022.py`; `docs/acceptance/P0A-022.md`.
  - Todos:
    - [ ] 1. Implement mission authoring: takeoff/climb/hover/descent/landing phases, manual commands and disturbances with serialized commands and timings.
    - [ ] 2. Serialize controller/sensor settings and experiment seeds with the mission (replay reproduces the frozen experiment identically).
    - [ ] 3. Add acceptance tests: authored mission -> replay -> identical telemetry under the declared seed.
  - Verify: `pytest tests/acceptance/test_p0a_022.py -q`
  - Planned verification: `pytest tests/acceptance/test_p0a_022.py`; required current-head CI.

<a name="p0a-023"></a>
- [ ] **P0A-023 — Run the supported design in the authoritative desktop simulation** (WP2, WP5, WP6; actor: builder)
  - Prerequisites: P0A-019, P0A-022, P0A-014. Proof: [docs/acceptance/P0A-023.md](acceptance/P0A-023.md).
  - Acceptance: A normal geometry/component/environment/mission edit changes the applicable simulated response; one double-precision integrator drives playback; pause/step/run/cancel/failure states and model limits are visible end to end.
  - Language: GDScript, Python.
  - Target files: `apps/desktop/`; `scripts/lab_worker.py`; `packages/desktop_worker/engine.py`; `packages/physics/`; `tests/acceptance/test_p0a_023.py`; `docs/acceptance/P0A-023.md`.
  - Todos:
    - [ ] 1. Run the supported design through the authoritative desktop simulation: a normal geometry/component/environment/mission edit must change the applicable simulated response.
    - [ ] 2. Drive playback from ONE double-precision integrator (no parallel approximate integrators).
    - [ ] 3. Implement pause/step/run/cancel and failure-state handling with worker supervision.
    - [ ] 4. Add acceptance tests for edit->response causality and the playback state machine.
  - Verify: `pytest tests/acceptance/test_p0a_023.py -q` | `pytest tests/acceptance/test_p0a_014.py tests/acceptance/test_p0a_019.py -q`
  - Planned verification: `pytest tests/acceptance/test_p0a_023.py`; required current-head CI.

<a name="p0a-024"></a>
- [ ] **P0A-024 — Inspect telemetry, evidence and reproducible result comparisons** (WP2, WP10, WP11; actor: builder)
  - Prerequisites: P0A-023. Proof: [docs/acceptance/P0A-024.md](acceptance/P0A-024.md).
  - Acceptance: UI compares frozen runs and source measurements with units, frames, source/model hashes, operating envelope, exclusions and uncertainty; exported results distinguish calculated, measured and synthetic channels.
  - Language: GDScript, Python.
  - Target files: `apps/desktop/`; `packages/desktop_worker/`; `tests/acceptance/test_p0a_024.py`; `docs/acceptance/P0A-024.md`.
  - Todos:
    - [ ] 1. Implement frozen-run vs source-measurement comparison in the UI: units, frames, source/model hashes, operating envelope, exclusions and uncertainty.
    - [ ] 2. Distinguish calculated, measured and interpolated values in every exported result.
    - [ ] 3. Add acceptance tests for the comparison pipeline with a frozen run and a pinned source measurement.
    - [ ] 4. Present the Dual Digital-Twin percentages: Design Pass/Fail Probability (%) from component limits/UQ and Physical Evidence Match (%) from M21-M27 tolerances, strictly gated so limit breaches remain FAIL and unmeasured parts display UNVERIFIED_ESTIMATE / INCONCLUSIVE.
  - Verify: `pytest tests/acceptance/test_p0a_024.py -q`
  - Planned verification: `pytest tests/acceptance/test_p0a_024.py`; required current-head CI.

<a name="p0a-025"></a>
- [ ] **P0A-025 — Expose numerical fidelity and bounded execution** (WP2, WP7, WP11; actor: builder)
  - Prerequisites: P0A-020, P0A-023. Proof: [docs/acceptance/P0A-025.md](acceptance/P0A-025.md).
  - Acceptance: Requested/effective timestep, backend, solver rates, numerical error and runtime budgets are recorded; interactive/offline runs of the same supported case agree within declared tolerance; cancellation and resource refusal preserve projects.
  - Language: GDScript, Python.
  - Target files: `apps/desktop/`; `packages/desktop_worker/engine.py`; `packages/physics/`; `tests/acceptance/test_p0a_025.py`; `docs/acceptance/P0A-025.md`.
  - Todos:
    - [ ] 1. Record requested vs effective timestep, backend, solver rates, numerical error and runtime budgets with every run.
    - [ ] 2. Prove interactive and offline runs of the same supported case agree within the declared tolerance (desktop worker vs headless integration).
    - [ ] 3. Expose the fidelity/budget panel in the UI from the recorded numbers (not free text).
    - [ ] 4. Add acceptance tests for the agreement bound and the recorded budgets.
  - Verify: `pytest tests/acceptance/test_p0a_025.py -q` | `pytest tests/acceptance/test_p0a_023.py -q`
  - Planned verification: `pytest tests/acceptance/test_p0a_025.py`; required current-head CI.

<a name="p0a-026"></a>
- [ ] **P0A-026 — Register component and multirotor validation protocols** (WP5, WP11; actor: builder)
  - Prerequisites: P0A-015, P0A-016. Proof: [docs/acceptance/P0A-026.md](acceptance/P0A-026.md).
  - Acceptance: Freeze model/controller/geometry versions, channels, instrument/clock uncertainties, calibration groups, held-out whole experiments, stopping rules and M21–M27 tolerances before confirmatory reveal; qualified review is required for acceptance.
  - Language: Python.
  - Target files: `data/research/registry.json`; `data/campaigns/`; `tests/acceptance/test_p0a_026.py`; `docs/acceptance/P0A-026.md`.
  - Todos:
    - [ ] 1. Freeze and register the validation protocols: model/controller/geometry versions, channels, instrument/clock uncertainties, calibration groups, held-out whole experiments, stopping rules and the M21–M27 tolerance bindings.
    - [ ] 2. Refuse protocol registration with missing calibration groups or held-out definitions (fail closed).
    - [ ] 3. Add acceptance tests asserting the frozen protocol records satisfy the registry contract.
  - Verify: `pytest tests/acceptance/test_p0a_026.py -q` | `python scripts/reconcile_registry.py --check`
  - Planned verification: `pytest tests/acceptance/test_p0a_026.py`; required current-head CI.

<a name="p0a-027"></a>
- [ ] **P0A-027 — Acquire and seal matching independent component experiments** (WP11; actor: custodian)
  - Prerequisites: P0A-026. Proof: [docs/acceptance/P0A-027.md](acceptance/P0A-027.md).
  - Acceptance: Custodian supplies legally usable exact-hardware/configuration battery, propulsion and sensor/controller measurements with original hashes, calibration and environmental records; previously inspected data cannot be relabeled blind.
  - Language: Python.
  - Target files: `data/campaigns/`; `data/research/registry.json`; `docs/acceptance/P0A-027.md`.
  - Todos:
    - [ ] 1. CUSTODIAN (requires real external receipts): obtain legally usable exact-hardware/configuration battery, propulsion and sensor/controller measurements with original file hashes.
    - [ ] 2. Record calibration groups, environmental conditions, instrument identity and clock bases per campaign; preserve source bytes unmodified.
    - [ ] 3. Register each campaign in data/research/registry.json and reconcile; mark DEVELOPMENT/holdout partition per the prospective policy.
    - [ ] 4. No acceptance tests exist by design — the custodian receipts ARE the evidence; the registry reconciliation is the machine check.
  - Verify: `python scripts/reconcile_registry.py --check` | `python scripts/export_contracts.py --check`

<a name="p0a-028"></a>
- [ ] **P0A-028 — Validate battery, propulsion and controller component envelopes** (WP5, WP11; actor: builder)
  - Prerequisites: P0A-027. Proof: [docs/acceptance/P0A-028.md](acceptance/P0A-028.md).
  - Acceptance: Each independent component experiment meets applicable M21–M23 frozen error, limit and uncertainty criteria; high-C/endpoints, transient torque/current/RPM and sensor/actuator timing are covered or explicitly outside the accepted envelope.
  - Language: Python.
  - Target files: `tests/acceptance/test_p0a_028.py`; `docs/acceptance/P0A-028.md`; `packages/physics/propulsion/`; `packages/physics/propulsion/battery.py`.
  - Todos:
    - [ ] 1. Score each independent component experiment (P0A-027 receipts) against the frozen M21–M23 error, limit and uncertainty criteria.
    - [ ] 2. Cover high-C discharge endpoints, transient torque/current/RPM and sensor/actuator timing per the frozen protocol.
    - [ ] 3. Publish per-campaign results; a criterion miss is FAILED VALIDATION, recorded — never re-banded after the fact.
    - [ ] 4. Update the component evidence records with the measured residuals.
  - Verify: `pytest tests/acceptance/test_p0a_028.py -q` | `python scripts/reconcile_registry.py --check`
  - Planned verification: `pytest tests/acceptance/test_p0a_028.py`; required current-head CI.

<a name="p0a-029"></a>
- [ ] **P0A-029 — Freeze end-to-end multirotor flight predictions** (WP6, WP11; actor: builder)
  - Prerequisites: P0A-028, P0A-023. Proof: [docs/acceptance/P0A-029.md](acceptance/P0A-029.md).
  - Acceptance: Freeze predictions, installed hardware, mission commands, payload, atmosphere, source custody and joint uncertainty construction before independent complete flights are revealed; no fitted time/trajectory alignment.
  - Language: Python.
  - Target files: `data/campaigns/`; `tests/acceptance/test_p0a_029.py`; `docs/acceptance/P0A-029.md`; `packages/physics/`.
  - Todos:
    - [ ] 1. Freeze the end-to-end flight predictions BEFORE the flights are revealed: predictions, installed hardware, mission commands, payload, atmosphere, source custody and the joint uncertainty construction.
    - [ ] 2. Cover the supported failure modes in the frozen predictions (loss/derating/saturation) per P0A-012.
    - [ ] 3. Seal the frozen set with hashes in the registry; no post-hoc edits.
    - [ ] 4. Add acceptance tests asserting the frozen set is complete and hash-bound.
  - Verify: `pytest tests/acceptance/test_p0a_029.py -q` | `python scripts/reconcile_registry.py --check`
  - Planned verification: `pytest tests/acceptance/test_p0a_029.py`; required current-head CI.

<a name="p0a-030"></a>
- [ ] **P0A-030 — Acquire sealed complete-flight and thermal/structural measurements** (WP11; actor: custodian)
  - Prerequisites: P0A-029. Proof: [docs/acceptance/P0A-030.md](acceptance/P0A-030.md).
  - Acceptance: Qualified custodian provides repeated hover/climb/descent/landing/control/disturbance/endurance trials plus applicable heat/load evidence; professional operational review is separate from software approval. Missing channels/calibration keep acceptance blocked.
  - Language: Python.
  - Target files: `data/campaigns/`; `data/research/registry.json`; `docs/acceptance/P0A-030.md`.
  - Todos:
    - [ ] 1. CUSTODIAN (requires real external receipts): obtain repeated hover/climb/descent/landing/control/disturbance/endurance flight trials on the frozen installed hardware, plus applicable heat/load evidence.
    - [ ] 2. Record telemetry channels, clocks, environmental conditions and custody per flight; keep the professional operational review separate from this acquisition.
    - [ ] 3. Register the sealed flight campaigns with original hashes; DEVELOPMENT/holdout partition per policy.
    - [ ] 4. No acceptance tests exist by design — the custodian receipts ARE the evidence.
  - Verify: `python scripts/reconcile_registry.py --check` | `python scripts/export_contracts.py --check`

<a name="p0a-031"></a>
- [ ] **P0A-031 — Score full-aircraft agreement and relevant failure modes** (WP6, WP11; actor: builder)
  - Prerequisites: P0A-030. Proof: [docs/acceptance/P0A-031.md](acceptance/P0A-031.md).
  - Acceptance: Per-flight trajectories, energy, heat/control response and failures meet the frozen M24–M26 applicable criteria; observed failures are retained, conditional replay is separate, and out-of-envelope operation is rejected.
  - Language: Python.
  - Target files: `tests/acceptance/test_p0a_031.py`; `docs/acceptance/P0A-031.md`; `packages/physics/`; `packages/desktop_worker/`.
  - Todos:
    - [ ] 1. Score per-flight trajectories, energy, heat/control response and the frozen failure-mode predictions against the sealed flights (P0A-030) using the frozen M24–M26 criteria.
    - [ ] 2. Retain observed failures; separate conditional replay from the primary blind scores.
    - [ ] 3. Publish per-flight agreement tables and all exclusions with reasons.
    - [ ] 4. Report per-channel and gated Physical Evidence Match (%) alongside the M24-M26 pass/fail scores without obscuring any failing channel.
  - Verify: `pytest tests/acceptance/test_p0a_031.py -q` | `python scripts/reconcile_registry.py --check`
  - Planned verification: `pytest tests/acceptance/test_p0a_031.py`; required current-head CI.

<a name="p0a-032"></a>
- [ ] **P0A-032 — Calibrate joint whole-flight uncertainty and generalization** (WP11; actor: builder)
  - Prerequisites: P0A-031. Proof: [docs/acceptance/P0A-032.md](acceptance/P0A-032.md).
  - Acceptance: M27 simultaneous whole-flight channel coverage and width limits pass by independent cohort, including numerical, measurement, parameter, environment and model-discrepancy uncertainty; sample coverage cannot substitute for flight coverage.
  - Language: Python.
  - Target files: `tests/acceptance/test_p0a_032.py`; `docs/acceptance/P0A-032.md`; `packages/physics/`.
  - Todos:
    - [ ] 1. Calibrate the joint whole-flight uncertainty: simultaneous M27 channel coverage and width limits per independent cohort.
    - [ ] 2. Include numerical, measurement, parameter, environment and model-discrepancy uncertainty terms explicitly (no single ±band collapse).
    - [ ] 3. Publish the calibration result and any cohort that fails the width limits as FAILED VALIDATION.
    - [ ] 4. Expose Design Pass/Fail Probability (%) from calibrated joint UQ for validated configurations, keeping unmeasured/new designs labeled UNVERIFIED_ESTIMATE / INCONCLUSIVE.
  - Verify: `pytest tests/acceptance/test_p0a_032.py -q`
  - Planned verification: `pytest tests/acceptance/test_p0a_032.py`; required current-head CI.

<a name="p0a-033"></a>
- [ ] **P0A-033 — Obtain independent multirotor credibility review** (WP11; actor: reviewer)
  - Prerequisites: P0A-032. Proof: [docs/acceptance/P0A-033.md](acceptance/P0A-033.md).
  - Acceptance: Independent reviewer reproduces each intended-use acceptance from frozen inputs and source bytes, signs the scope/uncertainty/failure dossier and identifies all unsupported configurations.
  - Language: Python.
  - Target files: `docs/acceptance/P0A-033.md`.
  - Todos:
    - [ ] 1. REVIEWER (requires real external receipts): independently reproduce each intended-use acceptance from frozen inputs and original source bytes.
    - [ ] 2. Sign the scope/uncertainty/failure dossier and identify every unsupported configuration, parameter or claim.
    - [ ] 3. Record the review in docs/acceptance/P0A-033.md with the reviewer identity and the exact reproduced commands.
  - Verify: `pytest tests/acceptance/ -q`

<a name="p0a-034"></a>
- [ ] **P0A-034 — Deliver guided learning and saved invention experiments** (WP10; actor: builder)
  - Prerequisites: P0A-024. Proof: [docs/acceptance/P0A-034.md](acceptance/P0A-034.md).
  - Acceptance: A learner can state a hypothesis, build/modify a supported drone, enter environment conditions, compare runs, inspect equations/assumptions and save a reproducible experiment through the desktop.
  - Language: GDScript, Python.
  - Target files: `apps/desktop/`; `packages/desktop_worker/`; `tests/acceptance/test_p0a_034.py`; `docs/acceptance/P0A-034.md`.
  - Todos:
    - [ ] 1. Implement the guided learning workflow: state a hypothesis, build/modify a supported drone, enter environment conditions, compare runs, inspect equations/assumptions and save a reproducible experiment — all through the normal UI.
    - [ ] 2. Bind every saved experiment to the frozen inputs needed for exact replay.
    - [ ] 3. Add acceptance tests for the save -> reopen -> reproduce identity.
  - Verify: `pytest tests/acceptance/test_p0a_034.py -q`
  - Planned verification: `pytest tests/acceptance/test_p0a_034.py`; required current-head CI.

<a name="p0a-035"></a>
- [ ] **P0A-035 — Deliver bounded sweeps and design comparisons** (WP7, WP10; actor: builder)
  - Prerequisites: P0A-034. Proof: [docs/acceptance/P0A-035.md](acceptance/P0A-035.md).
  - Acceptance: Supported parameter sweeps/optimization retain constraints, seeds, all infeasible/failed candidates and provenance; a repeat run reproduces the candidate/decision set, with no optimization-as-validation claim.
  - Language: GDScript, Python.
  - Target files: `packages/optimization/`; `apps/desktop/`; `tests/acceptance/test_p0a_035.py`; `docs/acceptance/P0A-035.md`.
  - Todos:
    - [ ] 1. Expose bounded parameter sweeps and design comparisons through the UI on the supported optimization package: constraints, seeds and all infeasible/failed candidates retained.
    - [ ] 2. Guarantee a repeat run reproduces the candidate/decision set exactly (seeded, hash-bound).
    - [ ] 3. Surface optimization-frontier caveats (no invented optimum) in the results view.
    - [ ] 4. Add acceptance tests for retention, reproduction and constraint handling.
  - Verify: `pytest tests/acceptance/test_p0a_035.py -q` | `pytest tests/physics/test_optimization.py -q`
  - Planned verification: `pytest tests/acceptance/test_p0a_035.py`; required current-head CI.

<a name="p0a-036"></a>
- [ ] **P0A-036 — Package and recover the standalone Windows application** (WP2, WP12; actor: builder)
  - Prerequisites: P0A-017. Proof: [docs/acceptance/P0A-036.md](acceptance/P0A-036.md).
  - Acceptance: A clean-user installation launches desktop, shared services and required workers without a development HTTP server; dependencies/notices are included; failed install/update/project writes recover without losing valid user data.
  - Language: GDScript, Python.
  - Target files: `apps/desktop/`; `scripts/lab_worker.py`; `packages/desktop_worker/`; `tests/acceptance/test_p0a_036.py`; `docs/acceptance/P0A-036.md`.
  - Todos:
    - [ ] 1. Package the standalone Windows application: desktop app, local shared services and required workers, with dependencies and notices included and no development HTTP server.
    - [ ] 2. Cover failed install/update/project-recovery paths with explicit user-visible handling.
    - [ ] 3. Add acceptance tests executed against the packaged layout (not the dev checkout).
  - Verify: `pytest tests/acceptance/test_p0a_036.py -q`
  - Planned verification: `pytest tests/acceptance/test_p0a_036.py`; required current-head CI.

<a name="p0a-037"></a>
- [ ] **P0A-037 — Protect regression, dependency security and compatibility** (WP12; actor: builder)
  - Prerequisites: P0A-023, P0A-036. Proof: [docs/acceptance/P0A-037.md](acceptance/P0A-037.md).
  - Acceptance: All five exact-head CI jobs and unchanged npm/backend/CAD audits pass; project migration, incompatible assets, process ownership, budgets, interrupted work, save/recovery and headless/API compatibility have regression evidence.
  - Language: Python.
  - Target files: `.github/workflows/ci.yml`; `tests/acceptance/test_p0a_037.py`; `docs/acceptance/P0A-037.md`.
  - Todos:
    - [ ] 1. Keep all five exact-head CI jobs and the unchanged npm/backend/CAD audits passing; bind results to the final PR head.
    - [ ] 2. Cover project migration, incompatible assets, process ownership, budgets, interrupted work and save/recovery headless cases in acceptance tests.
    - [ ] 3. No audit bypasses: npm audit --audit-level=moderate including development dependencies stays required.
  - Verify: `pytest tests/acceptance/test_p0a_037.py -q` | `pytest -q`
  - Planned verification: `pytest tests/acceptance/test_p0a_037.py`; required current-head CI.

<a name="p0a-038"></a>
- [ ] **P0A-038 — Qualify baseline hardware behavior for supported cases** (WP2, WP3, WP12; actor: builder)
  - Prerequisites: P0A-020, P0A-036. Proof: [docs/acceptance/P0A-038.md](acceptance/P0A-038.md).
  - Acceptance: Publish distinct 8 GB and 16 GB integrated-GPU installation/edit/run cases with CPU/GPU/OS/settings, >=30 FPS on the declared 200-part editing workload, frame-time/RAM data, <=5 s owned-worker cancellation, and correct low-memory refusal. Existing qualification is retained as one prior observation.
  - Language: Python.
  - Target files: `docs/acceptance/P0A-038.md`; `tests/acceptance/test_p0a_038.py`; `outputs/`.
  - Todos:
    - [ ] 1. Publish distinct 8 GB and 16 GB integrated-GPU installation/edit/run cases with CPU/GPU/OS/settings and measured frame-time/RAM data.
    - [ ] 2. Meet >=30 FPS on the declared 200-part editing workload and <=5 s project load on the recorded hardware.
    - [ ] 3. Take real measurements on the declared machines — synthetic or CI-host numbers do not qualify.
    - [ ] 4. Measure both Tier 1 (gl_compatibility on 8/16 GB integrated GPU) and Tier 2 (Forward+ PBR/HDRI on dedicated GPU) hardware profiles.
  - Verify: `pytest tests/acceptance/test_p0a_038.py -q`
  - Planned verification: `pytest tests/acceptance/test_p0a_038.py`; required current-head CI.

<a name="p0a-039"></a>
- [ ] **P0A-039 — Exit: usable multirotor software slice** (WP1, WP2, WP3, WP4, WP5, WP6, WP7, WP8, WP10, WP11, WP12; actor: builder)
  - Prerequisites: P0A-025, P0A-026, P0A-035, P0A-037, P0A-038. Proof: [docs/acceptance/P0A-039.md](acceptance/P0A-039.md).
  - Acceptance: All preceding software tasks required for this slice pass normal-entry-point tests and independent numerical checks; scientific ledger lists accepted, failed and still-unvalidated uses. Publish the slice dossier; this exit enables 0B software, not physical acceptance.
  - Language: Python.
  - Target files: `docs/acceptance/P0A-039.md`; `tests/acceptance/test_p0a_039.py`; `docs/ACCEPTANCE_LEDGER.md`.
  - Todos:
    - [ ] 1. Exit gate: verify every preceding software task required by this slice passes its normal-entry-point tests and independent numerical checks.
    - [ ] 2. Publish the scientific ledger listing accepted, failed and still-unvalidated capabilities — software slice exit and physical exit remain different gates.
    - [ ] 3. Record the exact commands and outputs in docs/acceptance/P0A-039.md.
  - Verify: `pytest -q` | `python scripts/check_master_plan.py --check` | `python scripts/export_contracts.py --check` | `python scripts/reconcile_registry.py --check`
  - Planned verification: `pytest tests/acceptance/test_p0a_039.py`; required current-head CI.

<a name="p0a-040"></a>
- [ ] **P0A-040 — Exit: physically accepted multirotor envelope** (WP6, WP11, WP12; actor: builder)
  - Prerequisites: P0A-033, P0A-039. Proof: [docs/acceptance/P0A-040.md](acceptance/P0A-040.md).
  - Acceptance: Independent review accepts only the demonstrated matching multirotor envelope under M21–M27; unresolved physical gates remain open and no universal drone-equivalence claim is made.
  - Language: Python.
  - Target files: `docs/acceptance/P0A-040.md`; `tests/acceptance/test_p0a_040.py`; `docs/ACCEPTANCE_LEDGER.md`.
  - Todos:
    - [ ] 1. Physical exit gate: assemble the P0A-033 signed dossier, the M21–M27 acceptance results and the open physical gates.
    - [ ] 2. Accept only the demonstrated matching multirotor envelope under the frozen criteria; make no universal drone-equivalence claim and keep unresolved physical gates open.
    - [ ] 3. Record the final envelope statement and open gates in docs/acceptance/P0A-040.md and the ledger.
  - Verify: `pytest tests/acceptance/test_p0a_040.py -q` | `python scripts/check_master_plan.py --check`
  - Planned verification: `pytest tests/acceptance/test_p0a_040.py`; required current-head CI.


## Slice 0B — Fixed-wing geometry and flight

<a name="p0b-001"></a>
- [ ] **P0B-001 — Implement constrained sketch and feature-history editing** (WP3; actor: builder)
  - Prerequisites: P0A-039. Proof: [docs/acceptance/P0B-001.md](acceptance/P0B-001.md).
  - Acceptance: Sketch dimensions/constraints, extrusion/revolve/boolean operations and dependency history are editable in the desktop; overconstraints, broken references, undo/redo and regeneration are tested.
  - Planned verification: `pytest tests/acceptance/test_p0b_001.py`; required current-head CI.

<a name="p0b-002"></a>
- [ ] **P0B-002 — Author exact wings, airfoils, blades and surfaces** (WP3; actor: builder)
  - Prerequisites: P0B-001. Proof: [docs/acceptance/P0B-002.md](acceptance/P0B-002.md).
  - Acceptance: Supported custom sections, span/chord/twist and lofts create valid exact geometry with persistent provenance; analytic volume/mass fixtures and geometry tolerances pass; unsupported surfaces are explicit.
  - Planned verification: `pytest tests/acceptance/test_p0b_002.py`; required current-head CI.

<a name="p0b-003"></a>
- [ ] **P0B-003 — Assemble joints, placements and distributed mass** (WP3; actor: builder)
  - Prerequisites: P0B-002. Proof: [docs/acceptance/P0B-003.md](acceptance/P0B-003.md).
  - Acceptance: Supported fixed joints/assemblies transform component masses and inertia to consistent datums; hierarchy edits, constraints and missing-material refusal survive project round trips.
  - Planned verification: `pytest tests/acceptance/test_p0b_003.py`; required current-head CI.

<a name="p0b-004"></a>
- [ ] **P0B-004 — Deliver versioned CAD import/export and unit-safe exchange** (WP3; actor: builder)
  - Prerequisites: P0B-003. Proof: [docs/acceptance/P0B-004.md](acceptance/P0B-004.md).
  - Acceptance: Supported STEP/IGES and display mesh exchange round-trip declared units, solid identity and project references; invalid geometry is diagnosed, and STL/display meshes never silently replace authoritative exact geometry.
  - Planned verification: `pytest tests/acceptance/test_p0b_004.py`; required current-head CI.

<a name="p0b-005"></a>
- [ ] **P0B-005 — Implement geometry-to-aerodynamics loading** (WP5; actor: builder)
  - Prerequisites: P0B-002, P0B-003. Proof: [docs/acceptance/P0B-005.md](acceptance/P0B-005.md).
  - Acceptance: Existing AeroSurface/AeroLoads contracts consume exact geometry, placements, station/polar hashes and moment datums; a geometric edit changes checked mass/inertia and appropriate aerodynamic loads; LOD independence and transform tests pass.
  - Planned verification: `pytest tests/acceptance/test_p0b_005.py`; required current-head CI.

<a name="p0b-006"></a>
- [ ] **P0B-006 — Deliver supported section/polar and wing aerodynamic models** (WP5, WP7; actor: builder)
  - Prerequisites: P0B-005. Proof: [docs/acceptance/P0B-006.md](acceptance/P0B-006.md).
  - Acceptance: Signed lift/drag/moment and supported induced-flow/wing models pass analytic and numerical cases; Reynolds/Mach/angle support and uncertainty are enforced; missing polars and unsupported viscous/stall mechanisms cannot receive success.
  - Planned verification: `pytest tests/acceptance/test_p0b_006.py`; required current-head CI.

<a name="p0b-007"></a>
- [ ] **P0B-007 — Implement fixed-wing propulsion, trim and controls** (WP5, WP6; actor: builder)
  - Prerequisites: P0B-006, P0A-014. Proof: [docs/acceptance/P0B-007.md](acceptance/P0B-007.md).
  - Acceptance: Control surfaces, throttle and supported trim/flight dynamics share one plant; thrust/energy/actuator limits and infeasible trim are explicit; analytic trim and perturbation checks pass.
  - Planned verification: `pytest tests/acceptance/test_p0b_007.py`; required current-head CI.

<a name="p0b-008"></a>
- [ ] **P0B-008 — Enforce stall, load, speed and control-authority envelopes** (WP5, WP6; actor: builder)
  - Prerequisites: P0B-007. Proof: [docs/acceptance/P0B-008.md](acceptance/P0B-008.md).
  - Acceptance: Known operating/structural/actuator limits produce FAIL; stalls and post-limit motion are supported only where modeled, otherwise unvalidated/inconclusive; boundary regressions include conflicting or absent limits.
  - Planned verification: `pytest tests/acceptance/test_p0b_008.py`; required current-head CI.

<a name="p0b-009"></a>
- [ ] **P0B-009 — Run fixed-wing takeoff, cruise, maneuver and landing** (WP2, WP4, WP6; actor: builder)
  - Prerequisites: P0B-004, P0B-008, P0A-022. Proof: [docs/acceptance/P0B-009.md](acceptance/P0B-009.md).
  - Acceptance: A supported fixed-wing design can be authored and flown from the desktop with consistent wind/contact/mission semantics; saved commands and results reproduce through the headless path.
  - Planned verification: `pytest tests/acceptance/test_p0b_009.py`; required current-head CI.

<a name="p0b-010"></a>
- [ ] **P0B-010 — Expose aerodynamic analysis adapters and convergence** (WP7, WP11; actor: builder)
  - Prerequisites: P0B-006. Proof: [docs/acceptance/P0B-010.md](acceptance/P0B-010.md).
  - Acceptance: Versioned analysis jobs declare backend/fidelity, polar/mesh/boundary inputs, progress and cancellation; supported calculations publish timestep/discretization/iteration error, without claiming planned VLM/CFD execution is already delivered.
  - Planned verification: `pytest tests/acceptance/test_p0b_010.py`; required current-head CI.

<a name="p0b-011"></a>
- [ ] **P0B-011 — Verify fixed-wing numerical and geometry sensitivity** (WP3, WP6, WP11; actor: builder)
  - Prerequisites: P0B-009, P0B-010. Proof: [docs/acceptance/P0B-011.md](acceptance/P0B-011.md).
  - Acceptance: Force/moment signs, geometry perturbations, trim, convergence, frame transforms and energy balances pass frozen verification cases; editor and headless results agree within declared numerical tolerance.
  - Planned verification: `pytest tests/acceptance/test_p0b_011.py`; required current-head CI.

<a name="p0b-012"></a>
- [ ] **P0B-012 — Register fixed-wing validation policy and frozen models** (WP11; actor: builder)
  - Prerequisites: P0B-011. Proof: [docs/acceptance/P0B-012.md](acceptance/P0B-012.md).
  - Acceptance: Create reviewed family-specific criteria/uncertainty/measurement annexes before confirmatory reveal; do not transfer multirotor thresholds or validation without an explicit justified similarity argument.
  - Planned verification: `pytest tests/acceptance/test_p0b_012.py`; required current-head CI.

<a name="p0b-013"></a>
- [ ] **P0B-013 — Acquire sealed wing and fixed-wing component measurements** (WP11; actor: custodian)
  - Prerequisites: P0B-012. Proof: [docs/acceptance/P0B-013.md](acceptance/P0B-013.md).
  - Acceptance: Custodian provides independently measured matching section/wing/installed propulsion data with calibration, source rights, full conditions and whole-experiment grouping.

<a name="p0b-014"></a>
- [ ] **P0B-014 — Validate supported wing/component loads** (WP5, WP11; actor: builder)
  - Prerequisites: P0B-013. Proof: [docs/acceptance/P0B-014.md](acceptance/P0B-014.md).
  - Acceptance: Frozen held-out forces/moments/power meet registered error/uncertainty criteria across the intended attached-flow and any explicitly supported stall regimes; unsupported extrapolation remains unvalidated.
  - Planned verification: `pytest tests/acceptance/test_p0b_014.py`; required current-head CI.

<a name="p0b-015"></a>
- [ ] **P0B-015 — Acquire sealed complete fixed-wing flights** (WP11; actor: custodian)
  - Prerequisites: P0B-014. Proof: [docs/acceptance/P0B-015.md](acceptance/P0B-015.md).
  - Acceptance: Matching aircraft, control commands, firmware, payload, environment, independent motion/energy measurements and timing/calibration records cover the registered missions.

<a name="p0b-016"></a>
- [ ] **P0B-016 — Validate full fixed-wing missions and joint uncertainty** (WP6, WP11; actor: builder)
  - Prerequisites: P0B-015. Proof: [docs/acceptance/P0B-016.md](acceptance/P0B-016.md).
  - Acceptance: Registered per-flight agreement, failure behavior, whole-flight interval coverage/width and independent cohort generalization pass; failures and excluded channels are retained.
  - Planned verification: `pytest tests/acceptance/test_p0b_016.py`; required current-head CI.

<a name="p0b-017"></a>
- [ ] **P0B-017 — Obtain independent fixed-wing credibility review** (WP11; actor: reviewer)
  - Prerequisites: P0B-016. Proof: [docs/acceptance/P0B-017.md](acceptance/P0B-017.md).
  - Acceptance: Reviewer reproduces the frozen results and signs the limited family-specific operating envelope; a multirotor qualification does not substitute.

<a name="p0b-018"></a>
- [ ] **P0B-018 — Teach wing design and comparative experiments** (WP10; actor: builder)
  - Prerequisites: P0B-009, P0B-010. Proof: [docs/acceptance/P0B-018.md](acceptance/P0B-018.md).
  - Acceptance: Desktop workflows compare span/chord/twist/airfoil/control choices with reproducible hypotheses, equations, assumptions, constraints and provenance; learning exercises disclose unvalidated regimes.
  - Planned verification: `pytest tests/acceptance/test_p0b_018.py`; required current-head CI.

<a name="p0b-019"></a>
- [ ] **P0B-019 — Qualify fixed-wing CAD application recovery and packaging** (WP12; actor: builder)
  - Prerequisites: P0B-004, P0B-009, P0B-018. Proof: [docs/acceptance/P0B-019.md](acceptance/P0B-019.md).
  - Acceptance: Install/edit/exchange/run/save/reopen/cancel/update flows pass under declared hardware budgets; existing multirotor projects and current-head security checks remain green.
  - Planned verification: `pytest tests/acceptance/test_p0b_019.py`; required current-head CI.

<a name="p0b-020"></a>
- [ ] **P0B-020 — Complete fixed-wing experiment and source library** (WP1, WP4, WP11; actor: builder)
  - Prerequisites: P0B-012. Proof: [docs/acceptance/P0B-020.md](acceptance/P0B-020.md).
  - Acceptance: Reference projects, environment/mission presets, model support and source-license/role records are versioned and reproducible; a sample project is not labeled physically accepted before its measurement gates pass.
  - Planned verification: `pytest tests/acceptance/test_p0b_020.py`; required current-head CI.

<a name="p0b-021"></a>
- [ ] **P0B-021 — Exit: fixed-wing software slice** (WP2, WP3, WP4, WP5, WP6, WP7, WP10, WP11, WP12; actor: builder)
  - Prerequisites: P0B-011, P0B-012, P0B-018, P0B-019, P0B-020. Proof: [docs/acceptance/P0B-021.md](acceptance/P0B-021.md).
  - Acceptance: All fixed-wing software acceptance paths and preserved multirotor regressions pass; publish the supported model/domain matrix and unresolved physical requirements. Enables 0C software only.
  - Planned verification: `pytest tests/acceptance/test_p0b_021.py`; required current-head CI.

<a name="p0b-022"></a>
- [ ] **P0B-022 — Exit: physically accepted fixed-wing envelope** (WP6, WP11, WP12; actor: builder)
  - Prerequisites: P0B-017, P0B-021. Proof: [docs/acceptance/P0B-022.md](acceptance/P0B-022.md).
  - Acceptance: Independent review accepts only the demonstrated wing/aircraft/mission envelope with calibrated uncertainty and explicit nontransfer limits.
  - Planned verification: `pytest tests/acceptance/test_p0b_022.py`; required current-head CI.


## Slice 0C — Helicopters, VTOL and detailed analysis

<a name="p0c-001"></a>
- [ ] **P0C-001 — Author helicopter rotor and articulated assemblies** (WP3; actor: builder)
  - Prerequisites: P0B-021. Proof: [docs/acceptance/P0C-001.md](acceptance/P0C-001.md).
  - Acceptance: Rotor blades/hubs, swashplate and supported articulated placements have exact geometry, constraints and mass/inertia; singular/unsupported mechanisms are rejected explicitly.
  - Planned verification: `pytest tests/acceptance/test_p0c_001.py`; required current-head CI.

<a name="p0c-002"></a>
- [ ] **P0C-002 — Implement qualified rotor inflow and blade-element dynamics** (WP5, WP7; actor: builder)
  - Prerequisites: P0C-001. Proof: [docs/acceptance/P0C-002.md](acceptance/P0C-002.md).
  - Acceptance: Supported BEMT/inflow/flapping equations pass analytical limiting cases and spatial/time convergence; polar envelopes, compressibility/tip limits and uncertainty are explicit; missing effects are not invented.
  - Planned verification: `pytest tests/acceptance/test_p0c_002.py`; required current-head CI.

<a name="p0c-003"></a>
- [ ] **P0C-003 — Implement rotor torque balance and helicopter control** (WP5, WP6; actor: builder)
  - Prerequisites: P0C-002. Proof: [docs/acceptance/P0C-003.md](acceptance/P0C-003.md).
  - Acceptance: Supported main/tail/coaxial rotor layouts and collective/cyclic controls propagate torque, actuator limits and saturation consistently; trim, hover and failure-boundary verification cases pass.
  - Planned verification: `pytest tests/acceptance/test_p0c_003.py`; required current-head CI.

<a name="p0c-004"></a>
- [ ] **P0C-004 — Run helicopter missions and supported autorotation** (WP4, WP6; actor: builder)
  - Prerequisites: P0C-003. Proof: [docs/acceptance/P0C-004.md](acceptance/P0C-004.md).
  - Acceptance: Hover/climb/descent/translation/landing and any supported autorotation use recorded commands and one plant; unsupported recovery/autorotation regimes remain inconclusive rather than animated success.
  - Planned verification: `pytest tests/acceptance/test_p0c_004.py`; required current-head CI.

<a name="p0c-005"></a>
- [ ] **P0C-005 — Author VTOL tilt and lift-plus-cruise configurations** (WP3, WP6; actor: builder)
  - Prerequisites: P0C-001. Proof: [docs/acceptance/P0C-005.md](acceptance/P0C-005.md).
  - Acceptance: Supported tilt mechanisms, lift/cruise powertrains, control surfaces and geometry-dependent mass/loads serialize and round-trip; invalid mechanism configurations are diagnosed.
  - Planned verification: `pytest tests/acceptance/test_p0c_005.py`; required current-head CI.

<a name="p0c-006"></a>
- [ ] **P0C-006 — Implement coupled VTOL transitions and allocation** (WP5, WP6; actor: builder)
  - Prerequisites: P0C-005, P0C-002, P0B-008. Proof: [docs/acceptance/P0C-006.md](acceptance/P0C-006.md).
  - Acceptance: Hover-to-cruise and reverse transitions preserve authoritative state, momentum/energy accounting, actuator limits and control authority; unsupported transition envelopes are rejected explicitly.
  - Planned verification: `pytest tests/acceptance/test_p0c_006.py`; required current-head CI.

<a name="p0c-007"></a>
- [ ] **P0C-007 — Couple transient electrical, actuator and thermal behavior** (WP5; actor: builder)
  - Prerequisites: P0C-003, P0C-006. Proof: [docs/acceptance/P0C-007.md](acceptance/P0C-007.md).
  - Acceptance: Dynamic bus/current/RPM/torque/heat and supported derating are consistently coupled; independently verified loss/thermal balances and latency/saturation limits pass; estimated parameters remain tagged.
  - Planned verification: `pytest tests/acceptance/test_p0c_007.py`; required current-head CI.

<a name="p0c-008"></a>
- [ ] **P0C-008 — Model installed rotor interaction and ground effects** (WP5, WP7; actor: builder)
  - Prerequisites: P0C-002, P0C-006. Proof: [docs/acceptance/P0C-008.md](acceptance/P0C-008.md).
  - Acceptance: Declared interaction/ground/off-axis models have numerical verification, calibration provenance and support envelopes; unknown installation/flow states remain unvalidated until measured.
  - Planned verification: `pytest tests/acceptance/test_p0c_008.py`; required current-head CI.

<a name="p0c-009"></a>
- [ ] **P0C-009 — Integrate geometry-dependent structural and modal analysis** (WP3, WP5, WP7; actor: builder)
  - Prerequisites: P0C-001, P0C-005. Proof: [docs/acceptance/P0C-009.md](acceptance/P0C-009.md).
  - Acceptance: Supported loads, joints/materials, stress, modal/vibration and fatigue jobs consume exact geometry and publish assumptions/convergence; analytical fixtures pass; screening is not presented as installed strength qualification.
  - Planned verification: `pytest tests/acceptance/test_p0c_009.py`; required current-head CI.

<a name="p0c-010"></a>
- [ ] **P0C-010 — Integrate detailed aerodynamic solver workers** (WP7; actor: builder)
  - Prerequisites: P0C-008, P0B-010. Proof: [docs/acceptance/P0C-010.md](acceptance/P0C-010.md).
  - Acceptance: At least the selected supported panel/VLM/CFD backends have reviewed licenses, mesh/boundary settings, progress/cancel/result contracts and code/solution verification; unimplemented backends remain absent from executable capabilities.
  - Planned verification: `pytest tests/acceptance/test_p0c_010.py`; required current-head CI.

<a name="p0c-011"></a>
- [ ] **P0C-011 — Integrate supported structural-thermal-aerodynamic coupling** (WP5, WP7; actor: builder)
  - Prerequisites: P0C-007, P0C-009, P0C-010. Proof: [docs/acceptance/P0C-011.md](acceptance/P0C-011.md).
  - Acceptance: Coupled exchanges conserve stated loads/energy, use consistent datums/clocks and converge under declared iteration/time tolerances; missing material/heat-transfer/closure inputs prevent acceptance.
  - Planned verification: `pytest tests/acceptance/test_p0c_011.py`; required current-head CI.

<a name="p0c-012"></a>
- [ ] **P0C-012 — Deliver budgeted local and remote detailed-job execution** (WP2, WP7, WP12; actor: builder)
  - Prerequisites: P0C-010, P0C-009. Proof: [docs/acceptance/P0C-012.md](acceptance/P0C-012.md).
  - Acceptance: Queue/admission/progress/cancel/retry/authentication preserve frozen inputs and owned-process cleanup; actual memory/disk/deadline failures cannot publish success; local/remote equivalent cases agree within declared tolerance.
  - Planned verification: `pytest tests/acceptance/test_p0c_012.py`; required current-head CI.

<a name="p0c-013"></a>
- [ ] **P0C-013 — Verify helicopter and VTOL coupled missions** (WP6, WP11; actor: builder)
  - Prerequisites: P0C-004, P0C-006, P0C-007, P0C-011. Proof: [docs/acceptance/P0C-013.md](acceptance/P0C-013.md).
  - Acceptance: Trim, transition, time/mesh convergence, perturbations, energy, actuator saturation and modeled fault transitions pass normal desktop/headless verification; four-family regression remains green.
  - Planned verification: `pytest tests/acceptance/test_p0c_013.py`; required current-head CI.

<a name="p0c-014"></a>
- [ ] **P0C-014 — Register rotorcraft/VTOL validation campaigns** (WP11; actor: builder)
  - Prerequisites: P0C-013. Proof: [docs/acceptance/P0C-014.md](acceptance/P0C-014.md).
  - Acceptance: Reviewed family-specific rotor, installation, control/thermal/structure and flight requirements, model freezes, uncertainty budgets and whole-experiment splits are registered before reveal.
  - Planned verification: `pytest tests/acceptance/test_p0c_014.py`; required current-head CI.

<a name="p0c-015"></a>
- [ ] **P0C-015 — Acquire sealed helicopter and installed-rotor measurements** (WP11; actor: custodian)
  - Prerequisites: P0C-014. Proof: [docs/acceptance/P0C-015.md](acceptance/P0C-015.md).
  - Acceptance: Custodian supplies compatible rotor thrust/torque/inflow/temperature/control and complete helicopter mission measurements with known geometry, calibration, clocks and licensing.

<a name="p0c-016"></a>
- [ ] **P0C-016 — Acquire sealed VTOL transition and coupling measurements** (WP11; actor: custodian)
  - Prerequisites: P0C-014. Proof: [docs/acceptance/P0C-016.md](acceptance/P0C-016.md).
  - Acceptance: Custodian supplies matching VTOL hover/transition/cruise/recovery data, actuator states, electrical/thermal loads and independent motion measurements across registered regimes.

<a name="p0c-017"></a>
- [ ] **P0C-017 — Validate installed thermal, structural and rotor effects** (WP5, WP11; actor: builder)
  - Prerequisites: P0C-015, P0C-016. Proof: [docs/acceptance/P0C-017.md](acceptance/P0C-017.md).
  - Acceptance: Independent component/installation forces, heat, strain/vibration and supported failure outcomes meet their registered criteria; apparatus-specific evidence is not transferred to unrelated geometry.
  - Planned verification: `pytest tests/acceptance/test_p0c_017.py`; required current-head CI.

<a name="p0c-018"></a>
- [ ] **P0C-018 — Validate helicopter complete missions and uncertainty** (WP6, WP11; actor: builder)
  - Prerequisites: P0C-015, P0C-017. Proof: [docs/acceptance/P0C-018.md](acceptance/P0C-018.md).
  - Acceptance: Per-flight helicopter agreement/failure requirements and calibrated joint coverage/width pass by independent cohort; autorotation is accepted only when explicitly measured and covered.
  - Planned verification: `pytest tests/acceptance/test_p0c_018.py`; required current-head CI.

<a name="p0c-019"></a>
- [ ] **P0C-019 — Validate VTOL complete missions and uncertainty** (WP6, WP11; actor: builder)
  - Prerequisites: P0C-016, P0C-017. Proof: [docs/acceptance/P0C-019.md](acceptance/P0C-019.md).
  - Acceptance: Independent transition/control/trajectory/energy/thermal outputs meet frozen requirements with whole-flight uncertainty; mode switching cannot hide unsupported or failing intervals.
  - Planned verification: `pytest tests/acceptance/test_p0c_019.py`; required current-head CI.

<a name="p0c-020"></a>
- [ ] **P0C-020 — Obtain independent rotorcraft and VTOL review** (WP11; actor: reviewer)
  - Prerequisites: P0C-018, P0C-019. Proof: [docs/acceptance/P0C-020.md](acceptance/P0C-020.md).
  - Acceptance: Reviewer reproduces each family dossier, evaluates coupled-model discrepancy and signs distinct validated operating envelopes and known failures.

<a name="p0c-021"></a>
- [ ] **P0C-021 — Deliver rotorcraft/VTOL learning and comparison workflows** (WP10; actor: builder)
  - Prerequisites: P0C-013, P0C-012. Proof: [docs/acceptance/P0C-021.md](acceptance/P0C-021.md).
  - Acceptance: Normal desktop users build supported mechanisms, compare rotor/transition choices, inspect assumptions and save reproducible detailed/interactive experiments with correct evidence labels.
  - Planned verification: `pytest tests/acceptance/test_p0c_021.py`; required current-head CI.

<a name="p0c-022"></a>
- [ ] **P0C-022 — Qualify four-family application compatibility and recovery** (WP12; actor: builder)
  - Prerequisites: P0C-021, P0C-012. Proof: [docs/acceptance/P0C-022.md](acceptance/P0C-022.md).
  - Acceptance: Install/migrate/edit/run/detailed-job/cancel/save/reopen tests and exact-head audits pass for all supported families; queues and failed remote/local jobs preserve valid projects.
  - Planned verification: `pytest tests/acceptance/test_p0c_022.py`; required current-head CI.

<a name="p0c-023"></a>
- [ ] **P0C-023 — Exit: four-family and detailed-analysis software slice** (WP2, WP3, WP4, WP5, WP6, WP7, WP10, WP11, WP12; actor: builder)
  - Prerequisites: P0C-013, P0C-014, P0C-021, P0C-022. Proof: [docs/acceptance/P0C-023.md](acceptance/P0C-023.md).
  - Acceptance: Four families and selected detailed-analysis paths work through normal entry points with declared domains, numerical verification, budgets and explicit remaining physical gaps. Enables 0D software.
  - Planned verification: `pytest tests/acceptance/test_p0c_023.py`; required current-head CI.

<a name="p0c-024"></a>
- [ ] **P0C-024 — Exit: physically accepted rotorcraft/VTOL envelopes** (WP6, WP11, WP12; actor: builder)
  - Prerequisites: P0C-020, P0C-023. Proof: [docs/acceptance/P0C-024.md](acceptance/P0C-024.md).
  - Acceptance: Independent review accepts each demonstrated rotorcraft/VTOL envelope without inheriting multirotor/fixed-wing acceptance or asserting unsupported recovery behavior.
  - Planned verification: `pytest tests/acceptance/test_p0c_024.py`; required current-head CI.


## Slice 0D — Complete supported drone laboratory

<a name="p0d-001"></a>
- [ ] **P0D-001 — Complete supported CAD, drawings and engineering handoff** (WP3; actor: builder)
  - Prerequisites: P0C-023. Proof: [docs/acceptance/P0D-001.md](acceptance/P0D-001.md).
  - Acceptance: Supported sketch/feature/assembly/joint/material operations, clearances, drawing views/dimensions, BOM and exchange work end to end with traceable revisions, units and engineering assumptions.
  - Planned verification: `pytest tests/acceptance/test_p0d_001.py`; required current-head CI.

<a name="p0d-002"></a>
- [ ] **P0D-002 — Complete component/material/source ingestion libraries** (WP1, WP3, WP5, WP11; actor: builder)
  - Prerequisites: P0D-001. Proof: [docs/acceptance/P0D-002.md](acceptance/P0D-002.md).
  - Acceptance: Versioned ingestion validates units, identities, rights, raw hashes, instrument uncertainty and whole-experiment roles; new dated custody records never overwrite historical snapshots; generic/estimated entries remain explicit.
  - Planned verification: `pytest tests/acceptance/test_p0d_002.py`; required current-head CI.

<a name="p0d-003"></a>
- [ ] **P0D-003 — Complete guided and advanced invention/optimization workflows** (WP7, WP10; actor: builder)
  - Prerequisites: P0D-001, P0C-021. Proof: [docs/acceptance/P0D-003.md](acceptance/P0D-003.md).
  - Acceptance: All four families support tutorial-to-advanced hypotheses, sweeps, constrained optimization, comparisons and reproducible reports; failed/out-of-envelope candidates remain visible and optimization does not confer validation.
  - Planned verification: `pytest tests/acceptance/test_p0d_003.py`; required current-head CI.

<a name="p0d-004"></a>
- [ ] **P0D-004 — Complete terrain, collision, contact and world authoring** (WP4; actor: builder)
  - Prerequisites: P0C-023. Proof: [docs/acceptance/P0D-004.md](acceptance/P0D-004.md).
  - Acceptance: Saved terrain/obstacles/landing/contact models and mission authoring support all declared families and coordinate/time boundaries; geometry/contact regression cases and replay integrity pass.
  - Planned verification: `pytest tests/acceptance/test_p0d_004.py`; required current-head CI.

<a name="p0d-005"></a>
- [ ] **P0D-005 — Implement spatial wind, gust, turbulence and atmospheric fields** (WP4, WP8; actor: builder)
  - Prerequisites: P0D-004. Proof: [docs/acceptance/P0D-005.md](acceptance/P0D-005.md).
  - Acceptance: Manual spatial/time fields and seeded gust/turbulence models affect relative-air forces with declared sampling/resolution; temperature/pressure/humidity change supported atmospheric properties; shaders alone cannot change the evidence status.
  - Planned verification: `pytest tests/acceptance/test_p0d_005.py`; required current-head CI.

<a name="p0d-006"></a>
- [ ] **P0D-006 — Implement supported rain and wet-operation effects** (WP5, WP8; actor: builder)
  - Prerequisites: P0D-005, P0C-011. Proof: [docs/acceptance/P0D-006.md](acceptance/P0D-006.md).
  - Acceptance: Declared rain/film/mass/drag, sensor and electrical effects couple to the plant using sourced models and parameter ranges; unsupported ingress or failure mechanisms are inconclusive, with no shader-as-physics claim.
  - Planned verification: `pytest tests/acceptance/test_p0d_006.py`; required current-head CI.

<a name="p0d-007"></a>
- [ ] **P0D-007 — Implement supported snow, icing, melting and shedding** (WP3, WP5, WP8; actor: builder)
  - Prerequisites: P0D-006. Proof: [docs/acceptance/P0D-007.md](acceptance/P0D-007.md).
  - Acceptance: Declared accumulation/heat/shape/mass/inertia/load/sensor changes and shedding affect supported physics, geometry and limits consistently; unknown ice shapes or thermal parameters remain UNVERIFIED_ESTIMATE/unvalidated.
  - Planned verification: `pytest tests/acceptance/test_p0d_007.py`; required current-head CI.

<a name="p0d-008"></a>
- [ ] **P0D-008 — Verify adverse-weather coupling and failure propagation** (WP5, WP8, WP11; actor: builder)
  - Prerequisites: P0D-007. Proof: [docs/acceptance/P0D-008.md](acceptance/P0D-008.md).
  - Acceptance: Limiting/dry cases, mass/energy balances, numerical convergence and supported loss/derating/failure paths pass; each weather mechanism has a distinct applicability and evidence status.
  - Planned verification: `pytest tests/acceptance/test_p0d_008.py`; required current-head CI.

<a name="p0d-009"></a>
- [ ] **P0D-009 — Register adverse-weather validation protocols** (WP11; actor: builder)
  - Prerequisites: P0D-008. Proof: [docs/acceptance/P0D-009.md](acceptance/P0D-009.md).
  - Acceptance: Freeze mechanism-specific rain/wet/snow/icing geometry, conditions, instruments, uncertainty and decision criteria before independent reveal; public section tests cannot automatically validate complete installed vehicles.
  - Planned verification: `pytest tests/acceptance/test_p0d_009.py`; required current-head CI.

<a name="p0d-010"></a>
- [ ] **P0D-010 — Acquire sealed compatible adverse-weather experiments** (WP11; actor: custodian)
  - Prerequisites: P0D-009. Proof: [docs/acceptance/P0D-010.md](acceptance/P0D-010.md).
  - Acceptance: Custodian provides legally usable matched mechanism/component/installation or vehicle measurements with calibrated environment, timing, geometry and uncertainty records.

<a name="p0d-011"></a>
- [ ] **P0D-011 — Validate claimed adverse-weather envelopes** (WP8, WP11; actor: builder)
  - Prerequisites: P0D-010. Proof: [docs/acceptance/P0D-011.md](acceptance/P0D-011.md).
  - Acceptance: Every advertised decision-grade weather use meets its frozen agreement, failure and uncertainty criteria; missing matched evidence remains unvalidated research use, not a passed weather gate.
  - Planned verification: `pytest tests/acceptance/test_p0d_011.py`; required current-head CI.

<a name="p0d-012"></a>
- [ ] **P0D-012 — Integrate ArduPilot SITL with one authoritative plant** (WP6, WP9; actor: builder)
  - Prerequisites: P0C-023, P0D-004. Proof: [docs/acceptance/P0D-012.md](acceptance/P0D-012.md).
  - Acceptance: Pinned firmware, controls, state exchanges and clocks use one declared integrator; commanded faults, latency/saturation, pause/step/replay and loss of link are verified without duplicate plant integration.
  - Planned verification: `pytest tests/acceptance/test_p0d_012.py`; required current-head CI.

<a name="p0d-013"></a>
- [ ] **P0D-013 — Integrate declared PX4 and controller adapter support** (WP6, WP9; actor: builder)
  - Prerequisites: P0D-012. Proof: [docs/acceptance/P0D-013.md](acceptance/P0D-013.md).
  - Acceptance: Selected supported PX4/controller configurations have versioned frame/unit/time/actuator adapters and repeatable missions; unsupported firmware/modes are refused and are not listed as working integrations.
  - Planned verification: `pytest tests/acceptance/test_p0d_013.py`; required current-head CI.

<a name="p0d-014"></a>
- [ ] **P0D-014 — Deliver timestamped camera, LiDAR and sensor experiments** (WP4, WP9; actor: builder)
  - Prerequisites: P0D-005, P0D-012. Proof: [docs/acceptance/P0D-014.md](acceptance/P0D-014.md).
  - Acceptance: Declared IMU/GNSS/barometer/camera/LiDAR noise, bias, latency, calibration and clocks are recorded; rendered observations remain SYNTHETIC and their rate/resolution never alters the authoritative plant.
  - Planned verification: `pytest tests/acceptance/test_p0d_014.py`; required current-head CI.

<a name="p0d-015"></a>
- [ ] **P0D-015 — Deliver vision, localization, mapping and navigation** (WP9, WP10; actor: builder)
  - Prerequisites: P0D-014. Proof: [docs/acceptance/P0D-015.md](acceptance/P0D-015.md).
  - Acceptance: Supported VIO/SLAM/map/navigation experiments have declared sensor models, reproducible ground-truth scoring and loss/failure cases; synthetic performance is labeled separately from hardware validation.
  - Planned verification: `pytest tests/acceptance/test_p0d_015.py`; required current-head CI.

<a name="p0d-016"></a>
- [ ] **P0D-016 — Deliver obstacle avoidance, geofences and manual overrides** (WP9; actor: builder)
  - Prerequisites: P0D-015, P0D-004. Proof: [docs/acceptance/P0D-016.md](acceptance/P0D-016.md).
  - Acceptance: Supported obstacle/geofence scenarios, perception failures, loss of navigation and operator override produce reproducible decisions and explicit limits; unavailable avoidance authority cannot create success.
  - Planned verification: `pytest tests/acceptance/test_p0d_016.py`; required current-head CI.

<a name="p0d-017"></a>
- [ ] **P0D-017 — Deliver coordinated multi-drone experiments** (WP4, WP9; actor: builder)
  - Prerequisites: P0D-016. Proof: [docs/acceptance/P0D-017.md](acceptance/P0D-017.md).
  - Acceptance: Each vehicle has independent identity/state/power/limits; shared clocks/world effects, inter-vehicle sensing/collision and bounded swarm scheduling reproduce with declared seeds and resources.
  - Planned verification: `pytest tests/acceptance/test_p0d_017.py`; required current-head CI.

<a name="p0d-018"></a>
- [ ] **P0D-018 — Integrate controller and sensor hardware-in-the-loop** (WP5, WP9; actor: builder)
  - Prerequisites: P0D-013, P0D-014. Proof: [docs/acceptance/P0D-018.md](acceptance/P0D-018.md).
  - Acceptance: Actual configured firmware, clock synchronization, actuator/sensor latency and saturation are measured and replayed; hardware disconnect/failure handling and evidence provenance are verified.
  - Planned verification: `pytest tests/acceptance/test_p0d_018.py`; required current-head CI.

<a name="p0d-019"></a>
- [ ] **P0D-019 — Register autonomy and sensor validation campaigns** (WP11; actor: builder)
  - Prerequisites: P0D-016, P0D-017, P0D-018. Proof: [docs/acceptance/P0D-019.md](acceptance/P0D-019.md).
  - Acceptance: Freeze independent real-sensor/controller missions, environment, failure classes, observables, whole-trial splits and decision criteria; simulation ground truth cannot substitute for physical observations.
  - Planned verification: `pytest tests/acceptance/test_p0d_019.py`; required current-head CI.

<a name="p0d-020"></a>
- [ ] **P0D-020 — Acquire sealed sensor/controller/autonomy measurements** (WP11; actor: custodian)
  - Prerequisites: P0D-019. Proof: [docs/acceptance/P0D-020.md](acceptance/P0D-020.md).
  - Acceptance: Custodian supplies matching hardware/firmware/calibration/clock records and repeated physical missions, including relevant disturbance and failure cases under appropriate professional review.

<a name="p0d-021"></a>
- [ ] **P0D-021 — Validate advertised sensor, autonomy and multi-drone uses** (WP9, WP11; actor: builder)
  - Prerequisites: P0D-020. Proof: [docs/acceptance/P0D-021.md](acceptance/P0D-021.md).
  - Acceptance: Registered tracking/perception/control/failure criteria and joint uncertainty pass for each claimed real-world use; unsupported algorithms, hardware and environments retain unvalidated status.
  - Planned verification: `pytest tests/acceptance/test_p0d_021.py`; required current-head CI.

<a name="p0d-022"></a>
- [ ] **P0D-022 — Qualify dedicated-GPU and remote/workstation profiles** (WP2, WP7, WP12; actor: builder)
  - Prerequisites: P0D-003, P0D-017, P0C-012. Proof: [docs/acceptance/P0D-022.md](acceptance/P0D-022.md).
  - Acceptance: Publish actual Tier 2 camera/LiDAR/editing and Tier 3 selected solver/swarm budgets, frame-time/RAM/VRAM/runtime/cancellation and correctness; no unlimited mesh/assembly guarantee or silent fidelity substitution.
  - Planned verification: `pytest tests/acceptance/test_p0d_022.py`; required current-head CI.

<a name="p0d-023"></a>
- [ ] **P0D-023 — Complete application accessibility, help and learning content** (WP2, WP10, WP12; actor: builder)
  - Prerequisites: P0D-003, P0D-016. Proof: [docs/acceptance/P0D-023.md](acceptance/P0D-023.md).
  - Acceptance: Keyboard/focus/contrast/readability/error-recovery and supported instructional journeys pass in the desktop; equations, assumptions, model/evidence status and operating limits are available at the decision point.
  - Planned verification: `pytest tests/acceptance/test_p0d_023.py`; required current-head CI.

<a name="p0d-024"></a>
- [ ] **P0D-024 — Complete production data, privacy and job hardening** (WP12; actor: builder)
  - Prerequisites: P0D-018, P0D-022. Proof: [docs/acceptance/P0D-024.md](acceptance/P0D-024.md).
  - Acceptance: Project/database migrations, schema compatibility, access controls, remote authentication, recovery/backups, bounded logs, plugin boundaries, load/performance and interrupted-job tests pass; local operation does not require cloud services.
  - Planned verification: `pytest tests/acceptance/test_p0d_024.py`; required current-head CI.

<a name="p0d-025"></a>
- [ ] **P0D-025 — Complete dependency licensing, SBOM and security acceptance** (WP12; actor: builder)
  - Prerequisites: P0D-002, P0D-024. Proof: [docs/acceptance/P0D-025.md](acceptance/P0D-025.md).
  - Acceptance: Redistributed code/data/models/notices have reviewed terms and pinned versions; SBOM is reproducible; all required audits and threat-relevant regressions pass without ignored audit failures.
  - Planned verification: `pytest tests/acceptance/test_p0d_025.py`; required current-head CI.

<a name="p0d-026"></a>
- [ ] **P0D-026 — Build reproducible standalone release installers** (WP2, WP12; actor: builder)
  - Prerequisites: P0D-025. Proof: [docs/acceptance/P0D-026.md](acceptance/P0D-026.md).
  - Acceptance: Windows installer and declared headless/other-platform distributions reproduce from frozen locks with checksums/notices and selected signing policy; unsupported platforms are not advertised as tested.
  - Planned verification: `pytest tests/acceptance/test_p0d_026.py`; required current-head CI.

<a name="p0d-027"></a>
- [ ] **P0D-027 — Run complete desktop release journeys and compatibility matrix** (WP12; actor: builder)
  - Prerequisites: P0D-001, P0D-008, P0D-017, P0D-023, P0D-026. Proof: [docs/acceptance/P0D-027.md](acceptance/P0D-027.md).
  - Acceptance: Clean installation, all-family design/edit/exchange/run/analysis/learn/save/reopen/update/cancel/recovery paths pass on advertised profiles; existing project migrations and all exact-head CI jobs remain green.
  - Planned verification: `pytest tests/acceptance/test_p0d_027.py`; required current-head CI.

<a name="p0d-028"></a>
- [ ] **P0D-028 — Assemble the complete numerical and scientific dossier** (WP11; actor: builder)
  - Prerequisites: P0A-040, P0B-022, P0C-024, P0D-011, P0D-021, P0D-027. Proof: [docs/acceptance/P0D-028.md](acceptance/P0D-028.md).
  - Acceptance: Each decision-grade claim links source/geometry/controller/model identity, numerical verification, held-out measured agreement, uncertainty coverage, failures and applicability; every unvalidated use is explicit.
  - Planned verification: `pytest tests/acceptance/test_p0d_028.py`; required current-head CI.

<a name="p0d-029"></a>
- [ ] **P0D-029 — Obtain independent Phase 0 engineering acceptance** (WP11; actor: reviewer)
  - Prerequisites: P0D-028. Proof: [docs/acceptance/P0D-029.md](acceptance/P0D-029.md).
  - Acceptance: Qualified independent reviewers reproduce and approve the stated intended uses and release limitations; owner/product approval cannot replace scientific review.

<a name="p0d-030"></a>
- [ ] **P0D-030 — Exit: complete supported drone laboratory software** (WP1, WP2, WP3, WP4, WP5, WP6, WP7, WP8, WP9, WP10, WP11, WP12; actor: builder)
  - Prerequisites: P0D-027. Proof: [docs/acceptance/P0D-030.md](acceptance/P0D-030.md).
  - Acceptance: Every Phase 0 functional requirement and all 12 work-package software checklists are implemented and verified, with traceable supported domains and honest research/physical status. This alone does not close M21–M30.
  - Planned verification: `pytest tests/acceptance/test_p0d_030.py`; required current-head CI.

<a name="p0d-031"></a>
- [ ] **P0D-031 — Release the evidence-qualified drone laboratory** (WP11, WP12; actor: builder)
  - Prerequisites: P0D-029, P0D-030. Proof: [docs/acceptance/P0D-031.md](acceptance/P0D-031.md).
  - Acceptance: Reproducible release package, independent review, operating-envelope documentation, recovery/security/compatibility results and all advertised physical claims pass; unsupported novel designs remain explicitly unvalidated.
  - Planned verification: `pytest tests/acceptance/test_p0d_031.py`; required current-head CI.

<a name="p0d-032"></a>
- [ ] **P0D-032 — Exit Phase 0 and reconcile every legacy acceptance gate** (WP1, WP11, WP12; actor: owner)
  - Prerequisites: P0D-031. Proof: [docs/acceptance/P0D-032.md](acceptance/P0D-032.md).
  - Acceptance: Owner accepts the completed Phase 0 dossier; all 12 package issues and applicable M21–M30 exits have distinct linked software/scientific evidence. Missing required evidence keeps this gate open and future phases locked.


## Phase 1 — Bio-inspired flight

**Locked future implementation.** Entry: **P1-001**; prerequisite **P0D-032**; exit **P1-008**. Until entry approval, contracts and dataset registries only.

<a name="p1-001"></a>
- [ ] **P1-001 — Authorize entry to Bio-inspired flight** (future phase; actor: owner)
  - Prerequisites: P0D-032. Proof: [docs/acceptance/P1-001.md](acceptance/P1-001.md).
  - Acceptance: Previous phase exit and Phase 0 acceptance are complete; owner explicitly authorizes this phase. Until then, interfaces and dataset registries only; no new model/product implementation.

<a name="p1-002"></a>
- [ ] **P1-002 — Define morphing/flapping geometry and measured parameter contracts** (future phase; actor: builder)
  - Prerequisites: P1-001. Proof: [docs/acceptance/P1-002.md](acceptance/P1-002.md).
  - Acceptance: Versioned geometry, articulated/flexible state, actuator/energy, source-role and bird/robot measurement interfaces are reviewed; biological measurements are not silently scaled into validated aircraft.
  - Planned verification: `pytest tests/acceptance/test_p1_002.py`; required current-head CI.

<a name="p1-003"></a>
- [ ] **P1-003 — Implement supported unsteady aeroelastic and flapping dynamics** (future phase; actor: builder)
  - Prerequisites: P1-002. Proof: [docs/acceptance/P1-003.md](acceptance/P1-003.md).
  - Acceptance: Selected equations/closures and numerical discretization have analytic/limiting/convergence checks; unsourced coefficients remain UNVERIFIED_ESTIMATE and unsupported mechanisms are rejected.
  - Planned verification: `pytest tests/acceptance/test_p1_003.py`; required current-head CI.

<a name="p1-004"></a>
- [ ] **P1-004 — Freeze bio-inspired actuation, structure and mission protocols** (future phase; actor: builder)
  - Prerequisites: P1-003. Proof: [docs/acceptance/P1-004.md](acceptance/P1-004.md).
  - Acceptance: Freeze configurations, control, compliant structure, fatigue/energy limits, intended uses and reviewed independent component/mission criteria before reveal.
  - Planned verification: `pytest tests/acceptance/test_p1_004.py`; required current-head CI.

<a name="p1-005"></a>
- [ ] **P1-005 — Acquire sealed mechanism and uncrewed mission measurements** (future phase; actor: custodian)
  - Prerequisites: P1-004. Proof: [docs/acceptance/P1-005.md](acceptance/P1-005.md).
  - Acceptance: Matching independent force/deformation/actuator/energy/trajectory data include calibration, clocks, conditions and whole-experiment splits.

<a name="p1-006"></a>
- [ ] **P1-006 — Verify and integrate the bio-inspired desktop design/run loop** (future phase; actor: builder)
  - Prerequisites: P1-005. Proof: [docs/acceptance/P1-006.md](acceptance/P1-006.md).
  - Acceptance: Build/edit/control/run/cancel/save/reopen learning workflows and all prior supported drone regressions pass with numerical error reported.
  - Planned verification: `pytest tests/acceptance/test_p1_006.py`; required current-head CI.

<a name="p1-007"></a>
- [ ] **P1-007 — Validate bio-inspired operating envelopes and joint uncertainty** (future phase; actor: builder)
  - Prerequisites: P1-006. Proof: [docs/acceptance/P1-007.md](acceptance/P1-007.md).
  - Acceptance: Frozen held-out mechanism and complete-mission criteria, failure detection, discrepancy and cohort coverage pass; drone acceptance is not inherited.
  - Planned verification: `pytest tests/acceptance/test_p1_007.py`; required current-head CI.

<a name="p1-008"></a>
- [ ] **P1-008 — Review and release the supported bio-inspired scope** (future phase; actor: reviewer)
  - Prerequisites: P1-007. Proof: [docs/acceptance/P1-008.md](acceptance/P1-008.md).
  - Acceptance: Independent qualified review accepts the limited intended uses; reproducible installation/security/recovery and a signed evidence dossier close the phase.


## Phase 2 — Human-scale and crewed systems

**Locked future implementation.** Entry: **P2-001**; prerequisite **P1-008**; exit **P2-008**. Until entry approval, contracts and dataset registries only.

<a name="p2-001"></a>
- [ ] **P2-001 — Authorize entry to Human-scale and crewed systems** (future phase; actor: owner)
  - Prerequisites: P1-008. Proof: [docs/acceptance/P2-001.md](acceptance/P2-001.md).
  - Acceptance: Previous phase exit and Phase 0 acceptance are complete; owner explicitly authorizes this phase. Until then, interfaces and dataset registries only; no new model/product implementation.

<a name="p2-002"></a>
- [ ] **P2-002 — Define human loads, apparatus mass and recovery contracts** (future phase; actor: builder)
  - Prerequisites: P2-001. Proof: [docs/acceptance/P2-002.md](acceptance/P2-002.md).
  - Acceptance: Human mass, complete apparatus, geometry, human-machine control, redundancy/recovery and engineering review requirements are explicit; the 60 kg pilot is an assumption, not total takeoff mass.
  - Planned verification: `pytest tests/acceptance/test_p2_002.py`; required current-head CI.

<a name="p2-003"></a>
- [ ] **P2-003 — Implement supported human-scale coupled models and controls** (future phase; actor: builder)
  - Prerequisites: P2-002. Proof: [docs/acceptance/P2-003.md](acceptance/P2-003.md).
  - Acceptance: Aerodynamic, structural, thermal, control and failure mechanisms have verified equations/limits, numerical convergence and sourced parameters; no extrapolated drone certification.
  - Planned verification: `pytest tests/acceptance/test_p2_003.py`; required current-head CI.

<a name="p2-004"></a>
- [ ] **P2-004 — Freeze professionally reviewed validation and risk protocols** (future phase; actor: builder)
  - Prerequisites: P2-003. Proof: [docs/acceptance/P2-004.md](acceptance/P2-004.md).
  - Acceptance: Qualified reviewers approve intended uses, instrumentation, uncertainty, independent data partitions and professional experimental requirements before reveal; software approval authorizes no human flight.
  - Planned verification: `pytest tests/acceptance/test_p2_004.py`; required current-head CI.

<a name="p2-005"></a>
- [ ] **P2-005 — Acquire sealed component and uncrewed full-scale measurements** (future phase; actor: custodian)
  - Prerequisites: P2-004. Proof: [docs/acceptance/P2-005.md](acceptance/P2-005.md).
  - Acceptance: Independent compatible structural/power/actuator/thermal and uncrewed full-scale records are supplied by qualified custodians with applicable permissions and calibration.

<a name="p2-006"></a>
- [ ] **P2-006 — Verify and integrate human-scale engineering workflows** (future phase; actor: builder)
  - Prerequisites: P2-005. Proof: [docs/acceptance/P2-006.md](acceptance/P2-006.md).
  - Acceptance: Supported design/load/control/redundancy/recovery studies reproduce through desktop/headless paths; conservation, limits, numerical error and prior-family regressions pass.
  - Planned verification: `pytest tests/acceptance/test_p2_006.py`; required current-head CI.

<a name="p2-007"></a>
- [ ] **P2-007 — Validate human-scale decision envelopes and uncertainty** (future phase; actor: builder)
  - Prerequisites: P2-006. Proof: [docs/acceptance/P2-007.md](acceptance/P2-007.md).
  - Acceptance: Predeclared held-out agreement/failure/uncertainty criteria pass for stated configurations; unsupported human/crewed operating claims remain unvalidated.
  - Planned verification: `pytest tests/acceptance/test_p2_007.py`; required current-head CI.

<a name="p2-008"></a>
- [ ] **P2-008 — Review and release the supported human-scale scope** (future phase; actor: reviewer)
  - Prerequisites: P2-007. Proof: [docs/acceptance/P2-008.md](acceptance/P2-008.md).
  - Acceptance: Independent qualified engineering review, evidence reproducibility and complete release QA accept only stated uses; no airworthiness or operational permission is inferred.


## Phase 3 — Jets and high-speed flight

**Locked future implementation.** Entry: **P3-001**; prerequisite **P2-008**; exit **P3-008**. Until entry approval, contracts and dataset registries only.

<a name="p3-001"></a>
- [ ] **P3-001 — Authorize entry to Jets and high-speed flight** (future phase; actor: owner)
  - Prerequisites: P2-008. Proof: [docs/acceptance/P3-001.md](acceptance/P3-001.md).
  - Acceptance: Previous phase exit and Phase 0 acceptance are complete; owner explicitly authorizes this phase. Until then, interfaces and dataset registries only; no new model/product implementation.

<a name="p3-002"></a>
- [ ] **P3-002 — Define compressible-flow, turbine and thermal interfaces** (future phase; actor: builder)
  - Prerequisites: P3-001. Proof: [docs/acceptance/P3-002.md](acceptance/P3-002.md).
  - Acceptance: Contracts/registries identify Mach/Reynolds/temperature ranges, gas properties, compressor/turbine data, flutter and thermal/structural boundaries with exact source/license roles.
  - Planned verification: `pytest tests/acceptance/test_p3_002.py`; required current-head CI.

<a name="p3-003"></a>
- [ ] **P3-003 — Implement selected compressible and propulsion models** (future phase; actor: builder)
  - Prerequisites: P3-002. Proof: [docs/acceptance/P3-003.md](acceptance/P3-003.md).
  - Acceptance: Supported shock/viscous/transition/propulsion mechanisms have code verification and mesh/time/iteration studies; closure assumptions and calculation-only benchmarks are explicit.
  - Planned verification: `pytest tests/acceptance/test_p3_003.py`; required current-head CI.

<a name="p3-004"></a>
- [ ] **P3-004 — Freeze flutter, propulsion and flight validation protocols** (future phase; actor: builder)
  - Prerequisites: P3-003. Proof: [docs/acceptance/P3-004.md](acceptance/P3-004.md).
  - Acceptance: Reviewed rig/vehicle matching, source partitions, numerical/measurement error, thermal/structural limits and high-speed intended-use criteria are registered before reveal.
  - Planned verification: `pytest tests/acceptance/test_p3_004.py`; required current-head CI.

<a name="p3-005"></a>
- [ ] **P3-005 — Acquire sealed compressor, thermal and high-speed measurements** (future phase; actor: custodian)
  - Prerequisites: P3-004. Proof: [docs/acceptance/P3-005.md](acceptance/P3-005.md).
  - Acceptance: Qualified custodian provides independent compatible rig/wind-tunnel/flight measurements with geometry, boundaries, calibration and clocks; CFD output is not physical data.

<a name="p3-006"></a>
- [ ] **P3-006 — Integrate and verify high-speed desktop and worker workflows** (future phase; actor: builder)
  - Prerequisites: P3-005. Proof: [docs/acceptance/P3-006.md](acceptance/P3-006.md).
  - Acceptance: Supported design/mesh/run/control/cancel/compare paths pass convergence, energy, shock/propulsion limiting cases and prior-family regressions under measured budgets.
  - Planned verification: `pytest tests/acceptance/test_p3_006.py`; required current-head CI.

<a name="p3-007"></a>
- [ ] **P3-007 — Validate high-speed envelopes and joint uncertainty** (future phase; actor: builder)
  - Prerequisites: P3-006. Proof: [docs/acceptance/P3-007.md](acceptance/P3-007.md).
  - Acceptance: Independent held-out forces/propulsion/thermal/structure/trajectory outcomes and failure limits meet registered requirements across declared regimes.
  - Planned verification: `pytest tests/acceptance/test_p3_007.py`; required current-head CI.

<a name="p3-008"></a>
- [ ] **P3-008 — Review and release the supported high-speed scope** (future phase; actor: reviewer)
  - Prerequisites: P3-007. Proof: [docs/acceptance/P3-008.md](acceptance/P3-008.md).
  - Acceptance: Qualified independent review reproduces each claimed envelope; licensing/security/compatibility/recovery and installation acceptance close the phase.


## Phase 4 — Rockets and spaceflight

**Locked future implementation.** Entry: **P4-001**; prerequisite **P3-008**; exit **P4-008**. Until entry approval, contracts and dataset registries only.

<a name="p4-001"></a>
- [ ] **P4-001 — Authorize entry to Rockets and spaceflight** (future phase; actor: owner)
  - Prerequisites: P3-008. Proof: [docs/acceptance/P4-001.md](acceptance/P4-001.md).
  - Acceptance: Previous phase exit and Phase 0 acceptance are complete; owner explicitly authorizes this phase. Until then, interfaces and dataset registries only; no new model/product implementation.

<a name="p4-002"></a>
- [ ] **P4-002 — Define variable-mass, staging and thermochemistry interfaces** (future phase; actor: builder)
  - Prerequisites: P4-001. Proof: [docs/acceptance/P4-002.md](acceptance/P4-002.md).
  - Acceptance: Versioned mass/inertia/propulsion/stage/atmosphere/orbit/re-entry contracts and licensed dataset/tool registries are reviewed; CEA or other computed thermochemistry remains calculated evidence.
  - Planned verification: `pytest tests/acceptance/test_p4_002.py`; required current-head CI.

<a name="p4-003"></a>
- [ ] **P4-003 — Implement supported ascent, staging, orbit and recovery models** (future phase; actor: builder)
  - Prerequisites: P4-002. Proof: [docs/acceptance/P4-003.md](acceptance/P4-003.md).
  - Acceptance: Changing mass/inertia, thrust, controls, staging, atmospheric/orbital dynamics and supported recovery/re-entry coupling have sourced equations and explicit validity boundaries.
  - Planned verification: `pytest tests/acceptance/test_p4_003.py`; required current-head CI.

<a name="p4-004"></a>
- [ ] **P4-004 — Freeze propulsion, trajectory and re-entry validation protocols** (future phase; actor: builder)
  - Prerequisites: P4-003. Proof: [docs/acceptance/P4-004.md](acceptance/P4-004.md).
  - Acceptance: Qualified intended-use criteria, physical limits, measurements, independent partitions, clocks and uncertainty budgets are registered before outcomes are revealed.
  - Planned verification: `pytest tests/acceptance/test_p4_004.py`; required current-head CI.

<a name="p4-005"></a>
- [ ] **P4-005 — Acquire sealed compatible propulsion and flight measurements** (future phase; actor: custodian)
  - Prerequisites: P4-004. Proof: [docs/acceptance/P4-005.md](acceptance/P4-005.md).
  - Acceptance: Qualified custodian supplies independent geometry/engine/vehicle-matched measured data with original bytes, calibration, environmental and operational records; simulations cannot substitute.

<a name="p4-006"></a>
- [ ] **P4-006 — Verify and integrate supported spaceflight engineering workflows** (future phase; actor: builder)
  - Prerequisites: P4-005. Proof: [docs/acceptance/P4-006.md](acceptance/P4-006.md).
  - Acceptance: Analytic ballistic/orbital limiting cases, mass/momentum/energy accounting, staging events and numerical convergence pass alongside desktop/headless job, cancel/recovery and prior-phase regressions.
  - Planned verification: `pytest tests/acceptance/test_p4_006.py`; required current-head CI.

<a name="p4-007"></a>
- [ ] **P4-007 — Validate spaceflight decision envelopes and uncertainty** (future phase; actor: builder)
  - Prerequisites: P4-006. Proof: [docs/acceptance/P4-007.md](acceptance/P4-007.md).
  - Acceptance: Frozen held-out propulsion/trajectory/thermal/recovery and failure requirements pass with calibrated uncertainty and no unsupported extrapolation.
  - Planned verification: `pytest tests/acceptance/test_p4_007.py`; required current-head CI.

<a name="p4-008"></a>
- [ ] **P4-008 — Review and release the supported spaceflight scope** (future phase; actor: reviewer)
  - Prerequisites: P4-007. Proof: [docs/acceptance/P4-008.md](acceptance/P4-008.md).
  - Acceptance: Qualified independent review accepts the stated limited uses; source/rights/security, reproducible distributions, compatibility and recovery gates close the phase.

Unique task count: **150**; checked **15**, unchecked **135**. These are planning tasks, not a count of physically validated milestones. All ten legacy major acceptance families and all twelve broad Phase 0 package issues remain open until their own actual exit evidence exists.
