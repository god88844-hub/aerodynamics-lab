# Windows prototype gate — FAIL

20 November 2026. **Stop for owner sign-off; do not start full WP3 expansion,
WP7–WP9 or physics tuning.** This report qualifies software behavior only.
No physical acceptance gate closes. The laptop's visible CAD session was refused
for insufficient memory headroom, so the integrated local prototype has not passed.

## Source and completed prerequisites

[PR #123](https://github.com/god88844-hub/aerodynamics-lab/pull/123) merged as
`a4992b55e9131c2d1cc4cc936f7f74e8e3ca5b9b` after all five current-head jobs passed.
Its [main-push CI](https://github.com/god88844-hub/aerodynamics-lab/actions/runs/44762469082)
also passed; [verification receipt](measurements/qualification-20261120/main-ci-a4992b5.json)
has `software_ci_verified: true`. Backend: 1110 passed, 6 skipped, 8 warnings;
CAD/assets: 26 passed; Windows worker: 25 passed including all nine lifecycle checks;
native CTest: 1 passed; frontend: 148 passed/31 files; packaged Playwright: 1 passed.
Desktop smoke and authenticated HTTPS invocations passed. All dependency audits passed.
Suites overlap; these are not unique-test totals.

[PR #124](https://github.com/god88844-hub/aerodynamics-lab/pull/124) then merged as
`f5fef554fb09c6091051e5e644bf87a2bacd9d27` after [all five jobs](https://github.com/god88844-hub/aerodynamics-lab/actions/runs/44766812125)
passed for head `5a7d1fc456ec32ead6aa9557808d190cda53ce44`: backend 1110 passed/6 skipped,
CAD/assets 27 passed, Windows worker 26 passed, frontend 148 passed/31 files, CTest 1 passed,
desktop smoke and packaged browser/HTTPS checks passed. All audits remained required and passed.

The full 21-path WIP checkpoint is preserved, unmerged, at
[`archive/aeroforge-wip-2026-11`](https://github.com/god88844-hub/aerodynamics-lab/tree/archive/aeroforge-wip-2026-11),
SHA `a1d7313146b687e78468df9a5b66a3920120092c`.
[Path-by-path disposition](measurements/qualification-20261120/wip-disposition.json):
two previously exact files, two additional provenance paths promoted with regression
checks, seventeen paths with quarantined changes. The entire archive is intact.
The [architecture](../ARCHITECTURE.md) freezes new web features and documents local
Godot → shared service/worker execution without a running HTTP server.

The [contract lock](../contracts/README.md) includes SI/frames, geometry, model/solver,
jobs/resources, evidence and the exact-geometry → surface/polar → force/moment seam.
BEMT/VLM/CFD execution remains unsupported. [Tolerance policy 1.0.0](../VALIDATION_TOLERANCES.md)
is prospective, pending owner/qualified review. All 20 inspected physical campaigns
are development evidence under that policy; none is retrospectively blind confirmation.

## Visible local observation

Protocol: [QUALIFICATION_PROTOCOL.md](QUALIFICATION_PROTOCOL.md). Source:
`b57721cc22c5b220d513126820340bd9cd6e8906`. Subsequent cancellation-test and build-receipt
metadata changes did not change the application/physics used by this visible run.
The native DLL and installed Python environments already existed; this run is separate
from installation timing. Exact context, raw intervals, input events, memory samples,
source/asset hashes and logs are in [the receipt directory](measurements/qualification-20261120).

Intel Core Ultra 7 155U, Intel integrated graphics driver 32.0.101.6790,
16,636,305,408 bytes RAM, Windows, Balanced power. Godot 4.7.2 compatibility renderer,
VSync, 1280×800 window / 930×494 viewport. A tool download and other applications
were active; this is one observed load condition, not minimum-system certification.

| Measurement | Actual result |
| --- | --- |
| Workload | 200 geometry parts; 185592 source triangle instances; 314 display LOD instances |
| Visible recording | 1800/1800 frames focused; 60.009409 mean FPS |
| Instantaneous FPS quantiles | p95 63.335233; p99 66.533599 (upper quantiles, not worst-frame performance) |
| Frame-time tail | p95 17.518 ms; p99 18.331 ms; max 20.241 ms |
| Tail FPS equivalents | 1000/p95(ms) = 57.084142; 1000/p99(ms) = 54.552398 |
| Received OS input | Two left-drag motion events; camera yaw changed −0.6 rad |
| Desktop OS peak resident | 331202560 bytes = 315.859375 MiB; console launcher measured separately |
| Import / save / reopen | 4.646033 / 4.180905 / 4.902335 s |
| Fresh process to verified reference ready | 4.75 s at 100 ms observer resolution; existing installation, OS caches uncontrolled |
| Integrity | Original/saved canonical project equality and all source/saved asset hashes passed |
| Local CAD | FAIL: `resource_admission_refused: insufficient_memory_headroom` |

Real computer-use OS input was received by Godot; no scripted orbit was used in this
interactive path. This is automated interaction, not a human usability study or sustained
continuous dragging. FPS equivalents are inverse high-percentile frame times, not
high-percentile instantaneous FPS. Raw intervals permit either calculation.

The local viewport thresholds passed. The aggregate worker memory in this run does
not characterize an admitted CAD job. Default CAD admission requires 1073741824 bytes
of growth plus 2079538176 bytes reserve on this machine: **3153280000 bytes available**.
The separately recorded pre-test observation was 2093809664 bytes. Capacity is volatile;
the refusal record governs the actual job. Reserves/tolerances were not lowered.

## Active cancellation and memory

Local normal legacy cancellation: **0.253289 s** from the instrumentation action timestamp
to return, including the marker publication before the cancel call. Actual observed worker
resident peak 85942272 bytes → exited/0 bytes; 100% of that owned worker's observed
resident memory reclaimed. Project preserved, completion absent, all observed descendants
cleaned up. This is not a claim about OS available RAM, shared pages or GPU memory.
The observer resolution is 100 ms. Local active CAD cancellation remains **UNMEASURED**
because admission refused; the legacy result cannot substitute for it.

An admitted Windows CI worker separately executes the same stop CLI used by Godot:
**0.304627100 s**, 387375104 owned resident bytes → 0 bytes, **100%** observed
resident reclamation. All observed birth-bound processes exited, the prior result
was preserved, and the cancelled job published no completion. This latest Windows
job passed **26/26** checks, including the unchanged nine lifecycle checks.
Its [source-bound cancellation receipt](measurements/qualification-20261120/windows-ci-cad-cancel.json)
records the precise process-call timer, actual owned resident bytes before/after, prior-result
preservation and absence of success for a cancelled job. The PR checkout's synthetic merge
SHA and PR head are both retained with verified equal trees. This is CI-host evidence,
not local graphical timing or hardware-tier qualification.

## Build and installation

The online attempt was interrupted while the Godot archive was incomplete; it is **not**
a successful install or a complete install-time measurement. Its partial-byte/timestamp/hash
receipt is retained. The incomplete archive was never executed. A diagnostic HTTP range
request received 781312 bytes in 20.121947 s (~38829 bytes/s).

The [authoritative fresh bundled installation receipt](measurements/qualification-20261120/fresh-bundled-install.json)
uses identical SHA-verified tool archives and 72 unchanged, lock-hash-approved cached
wheels staged as an offline bundle. Native build, Python environment and editor-import
cache did not exist before this run. Python was not supplied. Pip's own cache was disabled;
`PIP_NO_INDEX=1` and local `PIP_FIND_LINKS` supplied the wheel bytes. Download and bundle
preparation time are excluded; preinstalled Python/compiler/CMake/Ninja and uncontrolled
OS/file caches remain prerequisites. This is a fresh local installation from bundles,
not a successful cold online installation or an OS reboot measurement.

| Fresh bundled stage | Seconds / outcome |
| --- | --- |
| Create isolated Python environment | 14.574095 / PASS |
| Install all locked dependencies, verify hashes | 166.787387 / PASS |
| First CadQuery import | 20.613280 / PASS |
| Configure native build | 2.881159 / PASS |
| Compile native library, two build jobs, no object cache | 46.279478 / PASS |
| Native CTest invocation | 0.184027 / 1 test passed |
| Desktop smoke invocation | 21.684865 / FAIL: insufficient memory headroom for CAD |
| Total bootstrap until failed smoke | **283.181871 / FAIL** |

The total includes archive verification/extraction, editor import and bootstrap overhead;
editor import was not separately timed in this harness version. A follow-up `pip check`
reported no broken requirements. Exact wheel hashes and the staging helper are retained;
no wheel binaries are committed. An earlier package-download attempt also stalled and
was interrupted before dependency installation completed; its log is retained.

The [post-install fresh-process startup observation](measurements/qualification-20261120/post-install-startup-summary.json)
reached verified reference-project readiness in **2.922 s**, with nominal 100 ms polling.
It used the newly installed Python environment and newly compiled DLL. Previous bootstrap
smoke and a preliminary startup trial had run; OS/file caches were uncontrolled. This is
not a first-boot/empty-OS-cache result. The auxiliary probe was stopped after readiness;
its unfinished frame/save checks and invalid full-benchmark memory attribution are **not**
acceptance evidence. The received startup marker and observer timing remain preserved.
The preliminary trial inherited stale runtime-context text and is retained, unused, under
`local-attempts`; the final startup-only context explicitly identifies the new installation.

An earlier isolated fresh native build with supplied Python took 38.722964 s
(configure 9.923648 s, CTest invocation 2.420750 s; 1 native test passed). Its 84.772490 s
bootstrap failed the CAD smoke admission. That older receipt's generic scope text predates
expanded cache flags: cached archives and supplied Python do **not** prove a cold dependency
installation. Preserve it as an intermediate observation, not the authoritative install run.

## Verdict, remaining work and sign-off

**Local integrated gate: FAIL.** Rendering/input/integrity passed; visible local CAD admission
and active CAD cancellation did not. Full 8 GB/16 GB integrated, dedicated-GPU and explicit
remote compatibility acceptance remains incomplete. A green CI badge does not override this.

Frozen worker/direct report exact-equality and numerical checks remain verified by the
reusable-worker/CAD regressions. Historical step-halving observations remain in the earlier
benchmark reports; this batch adds no independent physical validation or new physics model.

**Ten legacy major acceptance families M21–M30 remain incomplete.** Phase 0's expanded
tracker still has [**12 open work packages, 0 closed**](https://github.com/god88844-hub/aerodynamics-lab/milestone/1); these are different tracking views,
not 22 interchangeable tasks. Contract and qualification substeps do not complete Phase 0.

Next: reproduce the local CAD/cancellation/installation gate with sufficient declared
headroom and publish the additional hardware profiles; obtain owner/qualified review of
the frozen contracts, prospective policy and gate receipts. Only a passing applicable gate
plus owner sign-off permits the agreed physics-reality work or wider CAD expansion.
