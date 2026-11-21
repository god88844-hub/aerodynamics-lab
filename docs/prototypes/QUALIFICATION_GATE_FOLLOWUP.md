# Post-fix bundled qualification — PASS

20 November 2026. Runtime source **`366777dd45cc6ae6cf751ab7c0c6e085d9e754fe`**.
This is the normal bundled build/import/smoke on the same 16 GB laptop after the
Windows control-record fixes, with adequate headroom and **unchanged admission limits**.

| Check | Receipt |
| --- | --- |
| Full qualification harness | Exit **0**, success true, **95.0924463 s** |
| Bundled bootstrap/build entry point | Success true, **93.6484139 s** |
| Native build / CTest | **40.7723507 s** build; CTest **1/1 passed** |
| Normal Godot smoke | Exit **0**, **38.7291468 s** |
| CAD lifecycle | Reuse, active cancellation, fresh-session recovery passed |
| Limits and integrity | Intentional resource refusal, project preservation, restored-limit recovery and 200-part assembly/LOD checks passed |
| Cache/install scope | Existing installed bundled Python; verified cached tool archives; no fresh dependency-install/download or first-boot claim |

[Raw receipts](measurements/foundation-followup-20261120/pass) include the capture
script, actual script hash, per-session/per-job resource/approval/completion/error
records, engine logs and separately sampled OS memory. The reported dirty path was
`apps/desktop/project.godot`: `checkout-state.json` verifies only line-ending differences,
with normalized content exactly equal to Git HEAD. No runtime source edit occurred
during measurement. Intentional negative-test errors are expected and checked by the smoke.

## Preserved failures

`PATHS.json` maps shortened Windows-safe checkout paths to original capture paths.
The same folder preserves **all five** preceding post-fix local failures: four
memory-refused attempts and the WinError 32 marker-retirement failure. They remain
failed observations, never renamed successes. Their exact scope, source status and
available-memory/admission numbers are in each receipt. Some earlier capture-script
changes were uncommitted instrumentation, explicitly recorded in source status where
available; exact old capture bytes were not retained. They are not pristine-head
performance claims. The final PASS capture script is retained byte-for-byte.

The supplied Python is the already installed sibling bundled environment. The bootstrap
JSON's `python_environment_preexisted` flag checks its default cache path, not that
external supplied path; `python_environment_supplied=true` describes this run.

`f4` (`bootstrap-recovery-refusal`) passed CAD cancellation/recovery but failed the final
restored-limit job when headroom fell. `f5` (`marker-race`) had sufficient memory and failed
on `active.json` deletion; its engine log is retained. See
[the regression diagnosis](FOUNDATION_VERIFICATION.md). The obsolete pre-fix full local
backend run was stopped without a completed-suite claim; current-head full-suite
results are obtained from GitHub CI, not that interrupted run.

## Meaning of the gate

The original visible **1800-frame / 60.0064147 FPS / 17.518 ms p95** and local CAD
cancellation **0.912879 s** measurements remain bound to source `0e3b9b7` in the
[immutable graphical report](QUALIFICATION_GATE_LOCAL.md). FPS and graphical latency
were not remeasured at this later source. This follow-up proves the normal bundled
execution and recovery paths after the Windows record fixes.

The gate is a software prototype PASS on one recorded 16 GB machine with adequate
headroom. 8 GB/dedicated-GPU/remote profiles, physical acceptance and owner/qualified
review remain open. No tag, Slice 0A execution, physics edits, CAD expansion or WP7–WP9
hold release is authorized. Final PR head/merge tree and all five CI jobs belong in
[PR #126](https://github.com/god88844-hub/aerodynamics-lab/pull/126).
