# M22.6–M22.10 — Causal thrust and current replay across Gemfan bench sweeps

## M22.6 Match the hardware and admit a separate sweep

Reuse the author's Emax ECOII-2807 1300 Kv, Gemfan Flash 7042 and Holybro Tekko32 F4 50 A bench source. Calibrate on the author's `151943` export and reserve `152432`, a separate recorded sweep of the same setup. Both original files matched their Git blobs and have pinned SHA-256 hashes. The parser omits 70 leading holdout observations that lack a recorded PWM command. Matching on timestamp, PWM, thrust and current excludes 19 in-range rows already present in the earlier setpoint files. [Source repository](https://github.com/mdttech/quadrotor-design/tree/b6f1dde3aafb1c5f564485f91406226e236ab578) · [Pinned exports](m22_gemfan_transients_sources.json)

## M22.7 Calibrate the static map

Use the final two seconds of each of the six calibration plateaus at 1,100–1,350 μs, with thrust and current medians as the steady targets. The instantaneous reference linearly interpolates these plateau medians. Only in-range PWM samples with a consecutive positive clock step of at most 0.25 s are scored.

## M22.8 Freeze the causal lag

Compare the instantaneous model with a first-order response to previously commanded targets on the native timestamps. Reinitialize from the static map after a gap, clock reset or out-of-range setting. Select the lag from a fixed grid on the calibration sweep. The chosen lag was 0.25 s for thrust and 0.16 s for current. Code and fit were committed before holdout scoring. The input parser was then updated to skip the initial rows without commands, and the calibration reproduced exactly. [Frozen settings](m22_gemfan_transients_freeze.json) · [Freeze commit](https://github.com/god88844-hub/aeroforge/commit/6869951dbb3817558af6234c428642988347a8ac)

## M22.9 Reserved sweep results

| Output | Instantaneous MAE | Lag MAE | Instantaneous maximum error | Lag maximum error |
| --- | ---: | ---: | ---: | ---: |
| Thrust | 0.234 N | 0.315 N | 5.913 N | 0.937 N |
| Current | 0.219 A | 0.127 A | 9.092 A | 1.858 A |

The lag reduced both peak errors and reduced current MAE. Mean thrust error increased, with a signed thrust bias of −0.315 N. The 291 scored observations are sequential samples from one sweep. Clock synchronization, sensor response, shaft speed and repeated independent transient tests remain open. The fitted lags describe the logged setup, including its measurement chain. [Result JSON](m22_gemfan_transients_results.json)

## M22.10 Reproduce

Download both pinned sweeps and all eight original files from the [static benchmark manifest](m22_gemfan_bench_sources.json) into one directory. Run with Python 3.11 or newer.

```console
python scripts/benchmark_gemfan_transients.py calibrate FILE_DIRECTORY local-freeze.json
python scripts/benchmark_gemfan_transients.py evaluate FILE_DIRECTORY local-results.json --freeze local-freeze.json
```

The regression test covers causal command use, reset across timestamp gaps and exclusion of reused observations.
