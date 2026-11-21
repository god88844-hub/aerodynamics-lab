# Spec-lock head verification and Windows regressions

The measured graphical PASS remains bound to source `0e3b9b7c36d4f43bceefcabb5f3402d40b870276`
and its immutable [report/receipts](QUALIFICATION_GATE_LOCAL.md). Later planning and
worker-robustness changes do not rewrite that observation. Final-head GitHub results
and any additional local smoke are recorded on [PR #126](https://github.com/god88844-hub/aerodynamics-lab/pull/126).
Owner review, tagging and execution holds remain unchanged.

## Failures retained

The first broader local worker run returned **39 passed / 1 failed**: an `Errno 13`
read of `approved.json` in `test_owner_exit_stops_engine_and_preserves_completed_assets`.
The isolated rerun passed, so the original environment-specific trigger is unproven.
A subsequent concurrent local run returned **36 passed / 4 failed**, all four failing
on explicit insufficient-memory admission. Those refusals are expected protection;
the successful test run must be performed with adequate headroom. No reserve was lowered.

At original PR head `c00a16b495da72c471ceeba1fee6c59befcee373`,
[CI run 44785459177](https://github.com/god88844-hub/aerodynamics-lab/actions/runs/44785459177)
reported **26 passed / 1 failed** in Windows: `test_deadline_stops_busy_native_engine_without_completion`
received `Could not terminate the owned worker process tree` instead of `job_timeout`.
The old diagnostic omitted the command exit code/stderr, so that exact runner trigger
cannot be established retrospectively. This failed attempt must not be reported green.

## Narrow foundation corrections

Windows termination is asynchronous; completion requires a signaled process handle.
See Microsoft's [TerminateProcess contract](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess).
`terminate_record` now waits at most one second on the already birth-bound handle when
the tree command returns nonzero. A still-live process remains an error, with command
code, wait result and stderr retained. Identity matching and final engine-exit/cleanup
checks are unchanged. This does not turn a command failure into unconditional success.

`read_control_bytes` retains the 64 KiB bound and retries only Windows sharing/access
errors for at most 0.5 s, including CRT `EACCES` without a `winerror` value. Persistent
locks/permissions still fail. JSON/schema/identity/hash errors are not retried as success.
The engine validates and hashes the same approval bytes rather than rereading the file;
clients use the same bounded control-record reader.

Regression evidence: an owned real process with controlled delayed exit fails before
the correction and passes afterward; a live process after a failed command still fails.
Real exclusive Windows file handles verify temporary-lock recovery and bounded
persistent-lock refusal. The four new checks are included in Windows CI; the existing
low-headroom refusal and actual lifecycle/cancellation tests remain mandatory.
The focused foundation set passed **28 tests** locally. No aerodynamic, powertrain,
CAD geometry, admission threshold, tolerance or executable-capability change is included.

These corrections establish controlled race handling. They do not prove the exact
unlogged trigger of either initial intermittent failure. Current-head CI and normal
smoke evidence must be inspected separately before review.

## Observed marker-retirement race

After adequate RAM was available, the post-fix bundled attempt at source `67c12f5`
exited 23 with `engine_exited`. Its engine log records **WinError 32 on `active.json`**:
the engine removed the marker while the supervisor briefly held a read handle without
delete sharing. This is a directly observed cleanup race, separate from memory refusal.
`unlink_control_record` now retries the same bounded Windows access/sharing conditions
for 0.5 s. A persistent reader still causes failure; completed bytes are preserved.
Two real-handle regression checks cover temporary and persistent locks. The combined
focused foundation set passes **30 tests**. Qualification capture now retains per-job
admission/completion/error records, engine logs and the actual capture-script hash.
