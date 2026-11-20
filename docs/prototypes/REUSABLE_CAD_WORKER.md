# Reusable CAD worker supervision and transport

20 November 2026. Related: #100 and #110. The local CAD engine can retain its imported libraries between requests while each job keeps separate frozen inputs and results. The existing geometry and rigid-body models retain their analytical checks and physically unvalidated status.

## Process ownership

A lightweight supervisor watches the desktop owner independently of the native CAD engine. Windows process handles and creation identities, or Linux process start identities, bind control to the original process rather than a subsequently reused PID. The engine runs in a separate process group on Linux; Windows termination includes the owned launcher and its interpreter descendants.

Owner exit, explicit stop, startup failure, engine exit and active-job deadlines end the session. The supervisor terminates and waits for its engine. An idle session expires after 300 seconds measured from readiness or its latest job. Startup and active-job defaults are 30 and 60 seconds. These are prototype wall-clock limits; resource admission and remote/detached solvers remain separate work.

The startup path compares source identity before loading and advertising the engine. Each request checks the installed source/dependency identity before and after execution. A changed environment, invalid request or backend exception retires the engine. A new session loads fresh modules. An incomplete job never supplies a successful completion receipt.

The implementation uses [Python subprocess groups](https://docs.python.org/3.11/library/subprocess.html), [Windows process handles](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openprocess) and [process waits](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject). The current scope is one local engine on Windows or Linux.

## Local protocol

Protocol `desktop_worker_1` uses a single-use session directory named by its random 32-character hexadecimal session ID. Its supervisor and engine control records retain process creation identities. Requests are atomically published as `pending.json`; the engine claims each request before reading it. The request limit is 16 MiB. This is a local filesystem transport, not a remote service.

Each request contains the protocol, session ID, a fresh job ID, operation and JSON payload. Supported operations are `build-body`, `build-blade` and `cad-torque`. Payloads use the existing bounded recipe/request schemas. CAD torque additionally requires an absolute asset root; existing project asset checks still govern each file.

Outputs are derived inside `jobs/<job_id>/`: the original request bytes, startup receipt, result, error or completion receipt, and any generated CAD assets. Callers cannot supply arbitrary output paths. A completion receipt binds the protocol, session, job, original request hash and result hash. Replaying a job ID retires the session without replacing the old result.

Each build creates new geometry from that request. Torque analysis imports the frozen, hash-checked STEP bytes and recomputes mass/inertia; it does not reuse a previously calculated body. Only the loaded libraries persist between jobs. Completed assets survive worker cancellation so a current project can still be saved or used by a fresh worker.

## Headless entry point and checks

`scripts/lab_worker.py --session <absolute directory ending in session ID> --session-id <ID> --owner-pid <desktop PID>` starts supervision. `--stop` requests cleanup of the matching session. `desktop_worker.client.WorkerClient` drives the same protocol for headless verification and timing. Legacy one-shot project/CAD tools remain available.

Real process tests verify engine reuse, agreement with direct frozen dynamics, invalid-request retirement/recovery, owner-exit cleanup, forced native-engine deadlines, source-change refusal, duplicate-job protection, idle expiry, abrupt engine exit and wrong-session cancellation rejection. Existing project migration, asset integrity and one-shot CLI checks remain required.

## Desktop integration

CAD builds and applied-torque experiments share the supervised engine. The ordinary project import, verification, package and reference-flight commands retain their one-shot worker path. The interface polls job receipts while the CAD engine stays alive; completion checks bind the current session, job, input and result hashes. Changing a receipt path or request identity cannot substitute an older result.

Cancel stops the owned reusable session and retains the current project. The next CAD operation creates a new session. Application exit also stops an idle engine. The actual desktop smoke verifies one engine PID across repeated edits/analyses, active numerical-job cancellation, preserved project state, fresh-session recovery and all existing save/reopen checks.

## Rendered interaction benchmark

`apps/desktop/benchmark_worker.gd` drives the actual desktop controls through a cold CAD cycle and five warm cycles by default. Every cycle rebuilds a single constrained box, runs its one-second torque experiment and waits for the rendered frame. Width alternates between 0.20 and 0.21 m; height is 0.10 m, depth 0.02 m and declared density 500 kg/m³. Torque is 0.001 N·m about body Z and the RK4 step is 0.005 s. Each result must agree with independently calculated mass and principal-axis spin-up, using the same engine PID.

The predeclared warm target is **at most 2 seconds for every recorded warm cycle**. Cold startup remains separately visible. The report includes all samples, separate rebuild/analysis/frame-wait times, median/maximum warm latency, observer/source identity, platform/renderer context and worker cleanup. A failed numerical check, cleanup failure or exceeded warm target returns a nonzero exit code. The tool requires a graphical renderer and a new absolute JSON output path. CI tests correctness and lifecycle without asserting machine-dependent timing.

After building the desktop and configuring `LAB_PYTHON` and `LAB_CAD_PYTHON`, run the pinned Godot executable with:

```text
--path apps/desktop --rendering-method gl_compatibility --script benchmark_worker.gd -- --report=C:/absolute/new-report.json --samples=5
```

An optional `--context=C:/absolute/context.json` adds externally recorded CPU/GPU/driver/RAM/power-mode and launch visibility. Use the same source/dependency pins and preserve all cold/warm observations. These programmatic-control timings include a rendered frame; they do not measure human input delivery, 200-part viewport FPS, process memory, cold clone/download/build time or other hardware tiers. The [hardware compatibility matrix](../HARDWARE_AND_FIDELITY.md), memory admission and calibrated physical evidence remain open.
