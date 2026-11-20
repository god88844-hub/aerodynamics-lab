# Local Windows prototype qualification — PASS

20 November 2026. **PASS for the recorded 16 GB integrated-GPU prototype with adequate
available-memory headroom.** This is software qualification. The wider hardware matrix,
physical validation and owner sign-off remain open. CAD expansion, WP7–WP9 and physics
edits stay held; no specification tag or Slice 0A execution is authorized by this report.

## Original refusal and diagnosis

[ADMISSION_DIAGNOSIS.md](ADMISSION_DIAGNOSIS.md) proves all four #123–#125 deliverables
exist. The recovered failed bundled-smoke session recorded total RAM **16636305408**,
available RAM **2323255296**, reserve **2079538176**, worker allowance **1073741824**,
required available RAM **3153280000**, and shortfall **830024704**, all in bytes.
Historical free-only RAM was **not logged**. The 2093809664-byte figure was a separate
pre-test snapshot, not this job's admission value.

The guard correctly reads Windows available RAM, including reclaimable standby pages.
No wrong-metric bug was found. The same 1 GiB worker allowance, 256 MiB controlled
workspace, 60 s deadline and max(1 GiB, total/8) reserve were retained. These are sampled
resource safeguards; no OS-enforced hard quota existed or is claimed. The low-headroom
refusal regression remains active. No policy threshold was lowered to obtain PASS.

## Complete local rerun

Measured source **`0e3b9b7c36d4f43bceefcabb5f3402d40b870276`**.
[Receipts](measurements/foundation-20261120) and `MANIFEST.json` retain normal bundled
smoke logs, PDH available/free/standby observations, session admission/retirement records,
visible frame intervals, received OS input, cancellation and cleanup. Physics, geometry,
desktop application and admission-policy source were unchanged by this diagnosis.

| Check | Observed result |
| --- | --- |
| Bundled bootstrap/smoke | **PASS**, exit 0; **95.165688 s**; previously installed bundled Python and cached verified tool archives |
| Default cold admissions | Available 4009549824, 3987771392 and 3976839168 bytes; same reserve 2079538176 and allowance 1073741824 bytes |
| First PDH sample | Available 4239872000; free + zero 301182976; standby sum 3938689024 bytes |
| Intentional negative case | 16 MiB session retires on actual resident overage; project preserved; restoring 1 GiB succeeds |
| Visible viewport | 200 parts, **60.006415 mean FPS**, p95 **17.518 ms**, p99 **18.401 ms** |
| Focus and input | **1800/1800** frames focused; received OS drags changed camera; interactive mode disables scripted orbit |
| Desktop peak resident | 329859072 bytes; console launcher separately attributed |
| Aggregate sampled worker peak | 652906496 bytes; shared pages may be counted twice |
| Local admitted CAD | **PASS**, normal constrained-body and isolated torque operations |
| Active CAD cancellation | **0.912879 s**, project preserved, completion absent |
| CAD resident reclamation | Observed worker peak 606179328 bytes → exited/0 bytes; **100% observed owned-worker resident reclamation** |
| Legacy cancellation | 0.280966 s; observed worker exited; project preserved; no completion |
| Integrity/cleanup | Canonical save/reopen equality, source/saved asset hashes, worker stop and all observed descendants passed |

PDH samples are separately timestamped observations, not exactly simultaneous free-memory
values for each admission. Available RAM is volatile. This PASS covers the adequate-headroom
condition; refusing a later loaded-machine request is expected protective behavior.
Cancellation timing runs from the instrumentation action timestamp to return, including
the marker write before the normal cancel call. Observer polling requests 100 ms; both
workers exited within the five-second criterion. Reclamation concerns owned-process
resident accounting, not system available RAM, unique shared pages or GPU memory.

## Preserved history and limits

[The initial FAIL report](QUALIFICATION_GATE_INITIAL.md) is retained byte-for-byte. Its
hash remains the one in `measurements/qualification-20261120/MANIFEST.json`; that old
manifest binds the initial publication, not the current index/report. Original failed
sessions and interrupted network attempts remain preserved.

The prior fresh bundled install measured 166.787387 s dependency installation,
46.279478 s native compile and 283.181871 s through its refused smoke. This new
95.165688 s run reuses installed Python and is **not** a fresh dependency-install claim.
Prior post-install fresh-process readiness was 2.922 s with nominal 100 ms polling and
uncontrolled OS/file caches. No cold online install or first-boot success is claimed.

The 8 GB baseline, dedicated-GPU and explicit remote profiles, full CAD, unsupported
aerodynamic backends and production packaging remain pending. The 12 Phase 0 work
packages and ten M21–M30 acceptance families remain open. No physical acceptance is
added, no `v0.0-spec-lock` tag is created and no Slice 0A physics implementation starts.
