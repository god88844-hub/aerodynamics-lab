# Aerodynamics Lab roadmap

Scope: [PRODUCT_SPEC](PRODUCT_SPEC.md). Current evidence: [ACCEPTANCE_LEDGER](ACCEPTANCE_LEDGER.md). Scientific criteria: [VALIDATION_TOLERANCES](VALIDATION_TOLERANCES.md). Data: [SOURCES](SOURCES.md). Plan dated **20 November 2026**.

## Current authorization

Complete the foundation/spec-lock PR and stop for owner review before tagging `v0.0-spec-lock` or executing Slice 0A. The [local prototype gate](prototypes/QUALIFICATION_GATE.md) passed on the recorded 16 GB machine with adequate headroom. Broader hardware coverage and independent review remain open. **WP7–WP9, CAD expansion and physics edits remain held.** `apps/web` stays frozen under [ARCHITECTURE](ARCHITECTURE.md).

## Phase 0 — drone invention laboratory

Deliver multirotor, fixed-wing, helicopter and VTOL drones through sequential vertical slices **0A → 0B → 0C → 0D**. Each slice preserves the preceding design/run/comparison loop and earns its own geometry, physics and physical-evidence envelope. Hardware tiers and physics fidelity remain independent under [HARDWARE_AND_FIDELITY](HARDWARE_AND_FIDELITY.md).

| WP / GitHub issue | Scope | Slice progression and dependencies |
| --- | --- | --- |
| 1 / [#99](https://github.com/god88844-hub/aerodynamics-lab/issues/99) | Foundation | 0A first: archive, identity, units/frames, project/jobs/evidence contracts; maintain through 0D. |
| 2 / [#100](https://github.com/god88844-hub/aerodynamics-lab/issues/100) | Desktop | 0A qualified prototype and normal save/edit/run/cancel loop after WP1; extend per slice. |
| 3 / [#101](https://github.com/god88844-hub/aerodynamics-lab/issues/101) | CAD/assembly | 0A supported multirotor assembly; 0B wing geometry; 0C rotor/mechanisms; 0D complete supported drawings/exchange. Requires WP1–2; expansion held. |
| 4 / [#102](https://github.com/god88844-hub/aerodynamics-lab/issues/102) | World/experiments | 0A saved environment, commands, seeds, relative wind and reproducible missions after WP1–2; extend through 0D. |
| 5 / [#103](https://github.com/god88844-hub/aerodynamics-lab/issues/103) | Electronics/physics | 0A resolve audited multirotor failures and couple applicable limits; 0B–0C extend qualified aero/thermal/structural models. Requires declared geometry, data and WP4. |
| 6 / [#104](https://github.com/god88844-hub/aerodynamics-lab/issues/104) | Four aircraft families | 0A multirotor; 0B fixed wing; 0C helicopter/VTOL. Each requires WP3–5 support and matching measurements. |
| 7 / [#110](https://github.com/god88844-hub/aerodynamics-lab/issues/110) | Detailed analysis | HOLD. Future 0B interfaces, 0C cancellable qualified workers, 0D complete analysis experience. Requires locked WP1–3, approved gate, WP4–6 and explicit hold release. |
| 8 / [#105](https://github.com/god88844-hub/aerodynamics-lab/issues/105) | Weather/wet/snow/icing | HOLD. Future 0D coupled effects and per-mechanism measurements after WP4–6. User-entered climate alone does not implement these mechanisms. |
| 9 / [#106](https://github.com/god88844-hub/aerodynamics-lab/issues/106) | Autonomy/multiple drones | HOLD. Future 0D autopilot/sensor/vision/navigation/swarm experiments after WP4–6; latency, synchronization and hardware evidence required. |
| 10 / [#107](https://github.com/god88844-hub/aerodynamics-lab/issues/107) | Learning/invention | 0A hypothesis/design/run/compare; 0B–0D guided family experiments and optimization preserving assumptions. Requires a supported loop. |
| 11 / [#108](https://github.com/god88844-hub/aerodynamics-lab/issues/108) | Validation | Every slice: frozen models, independent measurements, uncertainty and review. Starts with 0A M21–M27. |
| 12 / [#109](https://github.com/god88844-hub/aerodynamics-lab/issues/109) | QA/release | Every slice: security/reproducibility/recovery; 0D final Phase 0 release after applicable gates. |

### Slice 0A — dependency-ordered backlog

This is a plan awaiting owner approval, **not authorization to edit physics now**. Use any suitable reference hardware; predictions and measurements must match each campaign's actual configuration and conditions. The 60 kg hexacopter is one study, not a universal mandatory reference.

| Order | Task | Dependency and concrete acceptance evidence |
| --- | --- | --- |
| 0A.0 | Review spec-lock: contracts, prototype, tolerances, registry | Owner review before tag/execution; qualified scientific review remains required for confirmatory acceptance. |
| 0A.1 | Reproduce **M21 cutoff misses**, freeze correction experiment | [SIT module](campaigns/M21_6_10_SIT_MODULE_ELECTROTHERMAL.md) and [cutoff forecast](campaigns/M21_11_15_SIT_CUTOFF_FORECAST.md): 63/63 and 68/68 missed 80 V study crossings. Establish endpoint definitions, voltage/current timing, causal inputs, event bracketing and low-SOC regression cases before changes. These datasets are DEVELOPMENT. |
| 0A.2 | Investigate **M24 UIUC thrust-sign error** | After 0A.1 baseline/partition controls. Check axes, coefficient definitions, units, near-zero/sign resolution, advance ratio and shaft/electrical power in [UIUC sweeps](campaigns/M24_2_6_UIUC_AXIAL_SWEEPS.md). Cause is unproven; no blanket sign flip. Require signed regime metrics and registered uncertainty. |
| 0A.3 | Resolve **M25 fault misses and healthy false alarms** | After 0A.1–2 data/metric controls. Reproduce [rotor-order](campaigns/M25_2_6_UAV_FD_ROTOR_ORDER.md) and [ESC power](campaigns/M25_7_11_UAV_FD_ESC_POWER.md); partition whole experiments, report per-class detection deadlines/false alarms, prohibit label lookup and leakage. |
| 0A.4 | Resolve **M26 QDrone collapse/control coupling** | Requires battery/event and propulsion/actuator/fault support from 0A.1–3. [QDrone transfer](campaigns/M26_50_54_QDRONE_VOLTAGE_TRANSFER.md) uses a **14 V study line**, not a universal hardware cutoff. Couple voltage, available thrust/current and controller demand; forecast without future measurements. |
| 0A.5 | Qualify component/control/aero/structural envelopes (M21–M25) | Follow [fundamentals](fundamentals/vv_and_pirt.md) and tolerances. Independent compatible battery, motor/ESC/prop, sensor/controller, thermal and structure measurements; qualify each mechanism or retain unsupported verdicts. Acquire experiments when public data lack channels/calibration. |
| 0A.6 | Freeze complete-flight/joint uncertainty campaigns (M26–M27) | After 0A.4–5. Freeze model and whole-experiment partitions before confirmatory reveal; repeated missions, simultaneous whole-flight channel coverage, numerical error and out-of-envelope rejection. All 20 inspected campaigns stay DEVELOPMENT. |
| 0A.7 | Integrate supported desktop multirotor invention loop | After approved WP1–3 and adequate model support: edit supported design, configure environment/mission, run/cancel, inspect limits/provenance, save/reopen/reproduce, compare evidence. Unsupported geometry/mechanisms cannot receive success verdicts. |
| 0A.8 | Review multirotor slice | WP10 learning walkthrough; WP11 independent review; WP12 installation, security, compatibility, performance/recovery. Missing physical evidence keeps gates open. No universal drone-validation claim. |

### Slices 0B–0D

**0B — fixed wing:** supported wing/airfoil/polar geometry and complete mission loop; qualify aerodynamic envelope, stall limitations and component/control behavior against matching experiments. Detailed solvers stay contract-only until WP7 is explicitly released.

**0C — helicopters/VTOL:** independently qualify rotor/control mechanisms and transitions, geometry-dependent loads and supported thermal/structural coupling. Detailed workers require WP7 approval, measured budgets and convergence. Multirotor validation does not automatically transfer.

**0D — complete supported drone laboratory:** finish weather, autonomy, learning, CAD/drawings and release after explicit hold releases. Qualify each wet/icing/sensor/failure mechanism and operating envelope; publish independent review and limitations.

## Legacy acceptance crosswalk

| Gate | Slice role |
| --- | --- |
| M21 battery | 0A cutoff/sag/endurance; new power systems in 0B–0D. |
| M22 propulsion | 0A installed motor/ESC/prop response; extend per family. |
| M23 controls/sensors | 0A timing/actuator/closed-loop response; extend per family/autonomy. |
| M24 aero/thermal | 0A sign/inflow/thermal envelope; wing/rotor/weather models in 0B–0D. |
| M25 structures/failure | 0A faults/limits; geometry/joints/fatigue/thermal failures per slice. |
| M26 full flight | Independent complete missions per slice/family. |
| M27 uncertainty | Joint whole-flight coverage/discrepancy per slice. |
| M28 editor/CAD | Incremental supported geometry 0A–0C; complete supported workspace 0D. |
| M29 production QA | Exact-head checks/security/reproducibility throughout; compatibility/recovery 0D. |
| M30 release | Supported slice releases first; full Phase 0 only after applicable 0D gates. |

M0–M20 remain history, not proof of M21–M30 acceptance. M31 splits into Phase 0 families and future phases. **12 open package issues and 10 open legacy major acceptance families** are overlapping scopes, not 22 sequential tasks. Current proof and blockers are in the ledger.

## Phases 1–4 — locked future scope

Only interfaces and dataset registries are permitted until Phase 0 acceptance and explicit owner authorization. No implementation:

| Phase / issue | Future scope | Contract/registry preparation only |
| --- | --- | --- |
| 1 / #111 | Bio-inspired flight | Morphing/flapping, flexible structures and actuator interfaces; PigeonBot/morphology/inertia registry. |
| 2 / #112 | Human-scale/crewed | Human loads, redundancy/recovery and independent review requirements. The 60 kg pilot case remains an unvalidated feasibility study. |
| 3 / #113 | Jets/high speed | Compressibility, turbine, flutter, thermal interfaces; NASA CFD/compressor registry. |
| 4 / #114 | Rockets/spaceflight | Variable mass/inertia, staging, trajectory/re-entry interfaces; CEA/RocketPy/OpenRocket terms/benchmarks. Calculated thermochemistry remains calculation. |
