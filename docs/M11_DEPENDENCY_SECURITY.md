# M11 — Dependency Security Remediation and Audit Gate

## Why this change was necessary

GitHub Actions' `npm ci` output for M10.8 identified **3 npm audit entries** (2 critical, 1 moderate). An independent audit in the feature-branch GitHub Node 22 runner identified:

| Package (previous lock) | Finding | Audit advisory |
|---|---|---|
| `vitest@3.2.7` | Vulnerable test-runner dependency graph | `GHSA-82fw-gwwq-j7x9` |
| `@vitest/mocker@3.2.7` | Path traversal/arbitrary file read and mock registration | `GHSA-82fw-gwwq-j7x9`, `GHSA-qxg6-89mg-rqv8` |
| `tinypool` (previous transitive dependency) | Prototype-pollution gadgets that can cause worker-code execution | `GHSA-5gmw-xhrv-c9v3`, `GHSA-85c8-ppgw-ccpr` |

The npm audit reported **2 critical and 1 moderate vulnerable packages**, not necessarily three independent exploits. These are developer/test-tooling dependencies, but their CI execution context is security relevant.

## Remediation, scope, and evidence

- Migrate `vitest` direct dev dependency from `^3.2.0` to `^5.1.0`; regenerate the *entire lockfile with npm's resolver*, not by manually editing SRI hashes.
- The migration GitHub Action installed with `npm ci`, ran TypeScript/Vite production build, then all **65 frontend tests** successfully.
- `npm audit --audit-level=moderate` reported **0 vulnerabilities** in the new resolved dependency tree.
- The lockfile now resolves `vitest@5.1.0` and `@vitest/mocker@5.1.0`; `tinypool` is not present.
- The project advertises Node.js **22.12+**, consistent with Vitest 5 requirements and the CI job's Node 22 runner.
- Permanent `web-build` GitHub Actions now fails on any npm audit report of severity moderate or above. This checks both development and production dependencies against npm's current advisory feed on every push/pull request.

## Tests, boundaries and maintenance

```bash
cd apps/web
npm ci
npm audit --audit-level=moderate
npm run build
npm test
```

Plus `pytest` on the backend in the same CI workflow. Check the CI run for **the final commit** and the merged `main` SHA, not a previous feature-branch attempt.

**Interpretation:** A zero-findings npm audit means the advisory database reported no known vulnerabilities under its audit rules *at that point in time*. It does not establish that a package, browser app, supply chain or all of AeroForge is secure. Unpublished vulnerabilities and non-npm risks remain possible. Audit failures introduced by future advisories are deliberate actionable CI failures, not reasons to bypass the check.

The temporary GitHub Actions workflow used to propose the dependency upgrade has been deleted from the final change; only the permanent project-wide CI gate remains.
