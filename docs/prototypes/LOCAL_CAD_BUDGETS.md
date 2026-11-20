# Local CAD resource admission and sampled limits

Package 2 (#100), with shared job-contract work for #110. Contract `local_cad_resources_1` declares memory bytes, controlled workspace bytes and per-job wall time. It extends the existing local worker request with an optional versioned resource object; omitted values receive the documented default. This does not add a remote executor or change any physical model.

The initial default is a **1 GiB process-tree resident allowance, 256 MiB controlled workspace and 60 s per job**. These are explicit prototype policy allowances, not universal resource estimates or proof that an arbitrary CAD job fits. The earlier measured case used about 584 MiB of sampled worker resident memory. Other geometry and backends require their own observations.

Admission retains the requested memory/workspace allowances. It requires available memory for their remaining growth plus **max(1 GiB, one eighth of observed physical RAM)** for desktop/OS/iGPU/other-work headroom, and remaining workspace growth plus 64 MiB disk headroom. Already resident warm-engine memory is accounted once. Operator wall-time constraints may lower the effective wall time and are recorded. Invalid/nonfinite values and unsupported fields fail. Capacity observation failure cannot produce admission.

Windows capacity uses [GlobalMemoryStatusEx](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-globalmemorystatusex); Linux uses `/proc/meminfo` MemAvailable. Disk capacity uses [Python disk_usage](https://docs.python.org/3.11/library/shutil.html#shutil.disk_usage). These are volatile snapshots, not atomic reservations across application instances. The reserve formula is a conservative policy buffer, not a measured guarantee of OS/iGPU needs.

The limits use sampled process-tree resident memory and controlled workspace occupancy. Shared pages can be counted more than once and short-lived peaks/children can be missed. They are **not OS hard memory or disk quotas**. CPU/GPU enforcement, global admission reservations, remote scheduling and hardware-tier acceptance remain pending. Numerical tolerances, exact geometry and engineering inputs must never be silently reduced to fit a budget. Physical validation remains separate.

## Executed lifecycle boundary

The supervisor admits a session before launching its native engine, directs temporary
files into the controlled workspace and observes the owned process tree every 0.1 s.
Each request retains the session limits and gets a fresh capacity check. Runtime
overage retires the engine and cannot publish successful completion. A prepared
result needs supervisor approval bound to session/job/request/result hashes; both
Python and Godot clients verify that approval. Publication overhead is checked too.
Existing completed assets remain available; changed limits require a fresh session.

The desktop's **Worker limits** dialog exposes memory/workspace MiB and job seconds,
the last requested/effective allowance and refusal reason. No remote executor is added.

Windows transient read sharing locks are handled after the temporary writer is closed:
retry `os.replace` for access/sharing errors 5/32/33 for at most 0.5 s. A persistent
lock raises an error and preserves the previous complete record. Real held-open
Windows handle regressions cover release/retry and bounded failure. This can delay
a sampling cycle, so sampling is not a hard real-time or OS quota guarantee.

`tests/cad/test_reusable_worker.py` retains the nine lifecycle checks;
`test_worker_resources.py` adds capacity refusal before launch, actual startup resident
overage, actual CAD workspace overage with prior-asset preservation/recovery, approval
tampering and session-limit mismatch. Windows CI runs these alongside sharing-lock
and pure admission checks. Local admission refusal on a busy laptop is a recorded
environmental failure, never a reason to lower reserves silently or claim qualification.
