# AeroForge — Reconciled roadmap and scientific exit count

**Repository:** `god88844-hub/aeroforge` · **Review date:** 17 November 2026 · **Basis:** original M0–M31 roadmap, merged software PRs, M9 audit and open physical-evidence issues.

## What the original 14-phase count meant

The roadmap described **M18–M31 (14 top-level milestones)** as future work at an earlier point in development. That is no longer the present software status.

The repository contains merged implementation branches:
- **M18** propulsion evidence integration: [PR #19](https://github.com/god88844-hub/aeroforge/pull/19).
- **M19** original-source telemetry ingestion: [PR #20](https://github.com/god88844-hub/aeroforge/pull/20).
- **M20** preregistration protocol audit/readiness: [PR #22](https://github.com/god88844-hub/aeroforge/pull/22).
- **M21** battery source-pinned campaign software: [PR #24](https://github.com/god88844-hub/aeroforge/pull/24); **physical exit still open** [#23](https://github.com/god88844-hub/aeroforge/issues/23).
- **M22** propulsion source-pinned campaign software: [PR #26](https://github.com/god88844-hub/aeroforge/pull/26); **physical exit still open** [#25](https://github.com/god88844-hub/aeroforge/issues/25).
- **M23** HIL/controller evidence software: [PR #30](https://github.com/god88844-hub/aeroforge/pull/30) and later combined follow-ups; actual controller hardware remains unvalidated.
- **M24–M25** analytical aerodynamic and material/rotor screening subscopes: merged, but physical/operating-envelope model-form validation remains unresolved.
- **M27–M29** numerous source hashes, conservative uncertainty bounds, rotor clearance and release audits are software-implemented via incremental PRs, but neither authenticated physical evidence nor full application/product signoff is established.
- **M26** independent full-aircraft flight validation: **not complete**.
- **M30** decision-grade Drone Lab v1 release: **not complete**.
- **M31** post-drone vehicle class expansion: **not complete**.

Thus **11 major acceptance milestone families M21–M31 are still incomplete** if M18–M20 are counted delivered for their software implementation. **10 families M21–M30** remain through a defensible drone v1 release. This is a *top-level milestone count*, not 11 untouched feature phases; M21–M29 have significant code already delivered. Additional data collection and reviewer acceptance work tied to M19/M20 is still required even though their software was merged.

If the question instead means which original M18–M31 milestones have **every scientifically required component independently accepted**, the number cannot be reduced to a confident one-number task estimate: the physical-data gate spans several already implemented software milestones. Do not mark a subsystem's physical exit closed simply because its code is merged.

## Current priority: collect original observations, not more arbitrary pass screens

1. **M21 independent exact-pack measurements** (laboratory handoff: [M21 battery](campaigns/M21_BATTERY_PHYSICAL_ACQUISITION.md)). The [VTC6 single-cell benchmark](campaigns/M21_VTC6_CELL_BENCHMARK.md) measures voltage and current discrepancy under laboratory loads. Pack-level high-C, thermal and endurance evidence remains open.
2. **M22 independent exact installed motor/ESC/propeller measurements** (handoff: [M22 propulsion](campaigns/M22_PROPULSION_BENCH_ACQUISITION.md)). A published G30 experiment with different hardware is not a match.
3. **M26 full-aircraft blind independent measured missions** (handoff: [M26 flight](campaigns/M26_INDEPENDENT_FLIGHT_ACQUISITION.md)), gated by qualified engineering/operations safety and M21–M25 subsystem evidence.
4. In parallel, **M23–M25** physical controls, thermal/aero and structural mechanism coverage; **M27** validation-envelope error coverage; **M28–M29** supported CAD and production engineering; **M30** documented release acceptance; **M31** independent per-class aircraft physics.

## What is truly validated now

The [M9 audit](audit/M9_AUDIT.md) reports an independent UIUC APC SF 10×5 propeller/momentum-theory benchmark (16 measured points, 6.40% MAPE) **within its specific propeller and experimental regime**. This is not a measured P80 III + G30×10.5 + specific ESC + installed-frame propulsion test and not a complete-aircraft trial.

The 60 kg hexacopter is an unvalidated simulated feasibility study. Its **single-motor-out scenario is unrecoverable in simulation**; do not hide or convert that into a success claim.

## No-fake-evidence rule

- Original byte hash matching a user-controlled SHA-256 only establishes internal byte consistency.
- Operator-declared calibration references, external timestamps, hard-error bounds, true independent run IDs or component serials are **not independently authenticated** by software.
- A physical experiment requires actual suitable measured hardware or a genuinely applicable externally measured hardware-equivalent source under a reviewed protocol.
- If a component exceeds known physical limits, verdict **FAIL**; if the evidence needed to assess it is absent, **INCONCLUSIVE / UNVALIDATED**, never a fabricated success.
- Software correctness, CI and analytic geometry can be objectively verified; neither is independent physical flight evidence.
- Keep [Issue #16](https://github.com/god88844-hub/aeroforge/issues/16) open until actual required source evidence and independent acceptance exist.

## PR tracking, not scientific validation

The last completed software merge chain includes [PR #47](https://github.com/god88844-hub/aeroforge/pull/47) and [PR #49](https://github.com/god88844-hub/aeroforge/pull/49). Follow-on [PR #50](https://github.com/god88844-hub/aeroforge/pull/50) and [PR #51](https://github.com/god88844-hub/aeroforge/pull/51) have new numerical-source/thermal audit code; their merge/CI state must be rechecked at the time of release, not inferred from this static roadmap.
