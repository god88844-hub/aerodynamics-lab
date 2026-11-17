# M29.20–M29.24 — Simulation execution limits

| Phase | Acceptance check |
| --- | --- |
| M29.20 | Screen simulations for design size and requested numerical work before starting the solver. |
| M29.21 | Check elapsed time inside the numerical loops and cap adaptive derivative evaluations. |
| M29.22 | Allow one active simulation per API process and keep read routes available. |
| M29.23 | Save a distinct operational failure report with its recorded inputs and limits. |
| M29.24 | Verify normal solver runs, refusal before execution, deadline expiry, and recovery after contention. |

## Hosted limits

The simulation API accepts up to 256 parts and 32 rotors per run. Individual
physics models may impose tighter validity constraints. The size limit applies
when running a simulation. Existing saved designs are still available.

| Scenario | Numerical work screened at admission |
| --- | --- |
| Ideal hover, fixed step | 20,000 steps based on simulated duration and step interval |
| Ideal hover, adaptive | 20,000 steps at the solver's 0.05 second maximum interval, with a separate hard ceiling of 120,000 derivative evaluations |
| Static hover | 2,000 estimated samples, including the first sample |
| Controlled hover | At least one and at most 10,000 control steps |
| Flight | Uses the existing built-in mission and controller settings |

The API checks a 45-second monotonic elapsed-time budget at numerical
checkpoints, including fixed integration steps, adaptive derivative evaluations,
and hover and flight loop iterations. This is cooperative. A native call
already in progress can return after the deadline. These defaults give the
packaged proxy headroom below its [60-second default read timeout](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_read_timeout).
Offline physics callers use the existing behavior unless they opt into a limit.

A work-limit refusal or elapsed-time stop is stored as a failed run with
`simulation_work_limit` or `simulation_time_limit`, respectively. These are
operational outcomes. The frozen input download records the requested options
and applicable limits. A busy API returns HTTP 503 with `Retry-After: 1`
without queuing the simulation or creating a run. The standard Compose API
uses one worker process.

This addresses simulation workload handling in [production engineering
issue #28](https://github.com/god88844-hub/aeroforge/issues/28). Deployment
authentication, broader capacity testing, and physical acceptance remain open.
