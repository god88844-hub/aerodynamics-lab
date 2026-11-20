# Windows prototype qualification protocol

Version 1, registered before the new measurements on 20 November 2026. This is
software qualification of the existing bounded prototype, not physical validation.
The broader hardware matrix and full CAD/flight editor acceptance remain open.

1. Commit the measurement code. Use a fresh worktree with no application, wheel,
   Godot, native-build or editor-import cache. Preinstalled Python 3.11, MinGW,
   CMake and Ninja are prerequisites, not part of the timed installation. Set
   `PIP_NO_CACHE_DIR=1`; retain archive SHA checks, all logs and stage timings via
   `scripts/build_desktop.ps1 -TimingReport NEW_ABSOLUTE_PATH`. OS/network caches
   and other processes are uncontrolled. No fresh-boot or factory-install claim.
2. Record download/extraction, isolated dependency installation, configure/build,
   CTest, editor import and smoke durations separately. A failed stage fails the
   installation check; retain partial timings and its actual cause. No unsupported
   universal time limit is invented for network-dependent installation. Record
   first launch to verified reference-project readiness at 100 ms resolution;
   the existing startup deadline is 30 s. Repeat runs are warm observations.
3. Use pinned Godot 4.7.2, compatibility renderer, VSync and the published 200-part
   exact-source workload. Launch visibly at 1280×800. After 90 warm-up frames,
   enable qualification-only left-drag orbit and wait for an actual OS Space key.
   Use the computer-use API to drag the visible viewport; no `Input.parse_input_event`
   or scripted camera orbit is permitted in this interactive path. Capture 1800
   consecutive rendered intervals, mean FPS, p95/p99 frame time and their inverse
   FPS equivalents, focus fraction and actual received mouse events/camera change.
   This is automated OS interaction, not a human usability study. Require mean
   FPS ≥30 and p95 frame time ≤33.333 ms, nonzero received drag/camera change and
   all measured frames focused. Preserve failed attempts as separate files.
4. Check original and saved/reopened asset hashes and canonical project equality.
   Observe actual desktop and descendant resident memory independently every
   100 ms, distinguishing console launcher, desktop and worker. Keep shared-page,
   sampling and GPU limitations explicit. Default worker admission and reserves
   remain unchanged. A refusal is a real failed local CAD qualification, even if
   viewport performance passes. Windows CI proves lifecycle correctness separately.
5. For an admitted CAD worker, run the supported isolated 5000-step torque case.
   Separately run the legacy 30 s reference case. Wait for each real started
   receipt plus 0.3 s, reject a job that already completed, then invoke the normal
   desktop cancel action. Record application call-to-return time with the Godot
   microsecond clock, not an estimate from test timeouts. The existing cancellation
   deadline is 5 s; output must remain incomplete and the frozen project intact.
   External birth-bound process observation must verify exit and report actual
   pre-cancel peak/after resident bytes. Report reclaimed percentage for that owned
   worker only, not system-wide RAM or GPU memory. Require ≥95% owned-worker
   resident reclamation within the 5 s cleanup deadline, at observer resolution.
   A legacy result cannot substitute for missing admitted CAD cancellation evidence.
6. Publish a formal local PASS/FAIL and the separate full-matrix/owner-review status.
   Numerical repeatability remains scoped to the same frozen backend/platform;
   retain the existing exact-repeat and RK4 step-halving evidence. Missing hardware
   profiles, owner sign-off or independent physical evidence stay explicitly open.
   Stop before full WP3 expansion, WP7–WP9 or physics tuning.
