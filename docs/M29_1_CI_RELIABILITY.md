# M29.1 — Reliable and bounded GitHub CI execution

This milestone changes CI scheduling and permissions only. It does not modify
flight physics, evidence data, simulation claims, or test acceptance gates.

## Changes

- **Least privilege:** top-level `permissions: contents: read`; no default
  write token privileges are required for checkout, Python dependencies or
  npm tests. The repository's GitHub Actions permission settings may impose
  further restrictions, which remain outside this source file.
- **Per-head concurrency:** duplicate `push` and `pull_request` workflows
  for the same repository/head branch share a concurrency group. Newer runs
  can cancel earlier *stale* runs, including expensive duplicate full suites.
  Different branches and fork repositories have isolated groups. The protected
  `main` branch always has a separate group.
- **Explicit duration bounds:** Python job 30 minutes, web job 20 minutes.
  A timeout is a CI failure, not a physics success or evidence upgrade.

The jobs still run the unchanged complete `pytest`, `npm ci`,
`npm audit --audit-level=moderate`, `npm run build` and `npm test`
commands on all relevant pushed or pull-request source revisions.

## Release rules

A final version may merge only when a **completed successful run on the exact
final head SHA** has both full Python tests and frontend/security jobs. A
canceled old run must never be presented as a successful final verification.
After merge, check new `main` CI for that exact merge SHA.

These changes improve repeatable regression discipline, but cannot prove
physical validation of any model or component. Additional security work still
includes dependency pinning, secret and software supply-chain review, image
scanning, deployment testing, performance targets and availability analysis.
