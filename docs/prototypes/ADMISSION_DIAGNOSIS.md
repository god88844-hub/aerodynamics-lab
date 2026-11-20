# Admission diagnosis and deliverable proof

Baseline main `8a511949a639b8b42d27a9c7ba9967b661db1c06`, 20 November 2026.
All four requested deliverables exist; none is missing.

| Deliverable | Exact proof |
| --- | --- |
| WIP preservation | `origin/archive/aeroforge-wip-2026-11` resolves to `a1d7313146b687e78468df9a5b66a3920120092c`; [remote branch](https://github.com/god88844-hub/aerodynamics-lab/tree/archive/aeroforge-wip-2026-11). It is unmerged. |
| Execution and legacy decision | [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md): Godot invokes local workers/shared services under `apps/api/app/services`; no running FastAPI server is needed. `apps/web` is frozen legacy, with security/minimal compatibility maintenance only. |
| Prospective M21–M27 criteria | [`docs/VALIDATION_TOLERANCES.md`](../VALIDATION_TOLERANCES.md): policy 1.0.0, numerical limits, per-cohort simultaneous whole-flight joint coverage, preregistration and owner/qualified review pending. Twenty inspected campaigns are development evidence under this policy. |
| Geometry → aerodynamics | [`docs/contracts/README.md`](../contracts/README.md), `packages/shared-schemas/aeroforge_schemas/foundation.py` (`AeroSurface`, `PolarReference`, `AeroLoads`), and `docs/contracts/wp1-wp3-1/{geometry_aero,aero_loads}.schema.json`; content hashes/validator hashes in `lock.json`. BEMT/VLM/CFD execution remains explicitly unsupported. |

## Exact original failed bundled smoke

The recovered admission session is `3d04c53e0eb1ff2860465d44ff30678f`, recorded
at **2026-11-20 15:58:41.957307 UTC**, immediately before the bundled smoke ended
at 15:58:42.9337534 UTC. Supervisor owner PID 10776, birth identity
`134396639011838555`, corresponds to that smoke invocation. Original control records
are preserved under [`measurements/foundation-20261120/historical-failed-smoke`](measurements/foundation-20261120/historical-failed-smoke).

| Quantity | Bytes |
| --- | ---: |
| Total physical RAM | 16636305408 |
| Windows available physical RAM at admission | **2323255296** |
| Free + zero page lists at that historical instant | **NOT LOGGED — cannot reconstruct** |
| Configured reserve, max(1 GiB, total/8) | 2079538176 |
| Requested worker resident allowance | 1073741824 |
| Required available RAM for cold admission | 3153280000 |
| Admission shortfall | **830024704** |
| Controlled workspace allowance | 268435456 |
| Available disk | 21660090368 |

The earlier 2093809664-byte figure was a separate pre-test observation, not this
job's admission measurement. The exact record refuses `insufficient_memory_headroom`.
The 1 GiB allowance is a declared prototype budget, **not a validated prediction**
that every CAD operation needs 1 GiB. It was not reduced to obtain a pass.

## Metric and policy finding

`packages/desktop_worker/resources.py:memory_capacity` reads
`MEMORYSTATUSEX.ullAvailPhys` via `GlobalMemoryStatusEx`. Microsoft defines this as
immediately reusable standby + free + zero pages; it is **not free-only RAM**.
The struct layout matches the documented Windows ABI.
[Microsoft MEMORYSTATUSEX](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/ns-sysinfoapi-memorystatusex),
[PERFORMANCE_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-performance_information).

There is no evidence of the proposed wrong-metric bug. The reserve is a conservative
project policy, not an OS requirement or a validated universal iGPU prediction.
This evidence does not justify changing it merely to force a green verdict. The
rerun retains the same allowance, reserve, workspace limit and deadlines. The existing
memory/workspace checks are sampled safeguards; **no OS-enforced hard quota existed**
in #123–#125, and none is claimed here.

The dedicated 16 GiB regression supplies almost no free-only memory while sufficient
available memory admits the job, then verifies insufficient available headroom still
refuses and the worker overage check remains intact. Its parameters are test inputs,
not measured hardware estimates. New smoke receipts log PDH available/free/standby
counters separately with timestamps; those adjacent observations do not invent the
missing historical free-only value.

Run `scripts/qualify_bundled_smoke.ps1 -PythonPath ABSOLUTE_BUNDLED_PYTHON -ReceiptDirectory NEW_ABSOLUTE_DIRECTORY`.
The source must be committed first. The script preserves the normal bootstrap/smoke
logs, exit status, new admission/retirement records and memory-counter samples.
Any PASS applies only to the recorded workload and adequate-headroom condition;
the earlier failure remains preserved.
