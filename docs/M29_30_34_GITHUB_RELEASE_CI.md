# M29.30–M29.34 — GitHub CI evidence for a frozen release commit

| Phase | Implementation |
| --- | --- |
| M29.30 | Bind the candidate to an exact `main` push, repository, commit and CI workflow path. |
| M29.31 | Read the run's jobs from its explicit attempt and check each job's run and commit identity. |
| M29.32 | Require successful Python tests, frontend build and tests, npm audit, packaged browser tests and authenticated HTTPS checks. |
| M29.33 | Archive the run and job links and SHA-256 of the CI workflow from the selected commit. |
| M29.34 | Return a failing exit status for incomplete, unsuccessful or unavailable evidence. |

```console
python scripts/verify_release_ci.py FULL_MAIN_COMMIT_SHA GITHUB_ACTIONS_RUN_ID > release-ci.json
```

The verifier reads the official GitHub Actions and Contents APIs over HTTPS. For private repositories or additional rate-limit capacity, set `AEROFORGE_GITHUB_TOKEN` to an appropriate read-only token. The command exits with 0 when every software check succeeds, 1 when a check is incomplete or unsuccessful, and 2 when the run identity or API evidence is unavailable. [GitHub workflow runs](https://docs.github.com/en/rest/actions/workflow-runs#get-a-workflow-run) · [GitHub workflow jobs](https://docs.github.com/en/rest/actions/workflow-jobs#list-jobs-for-a-workflow-run-attempt)

Archive the JSON with the release review. The report covers the software checks for the selected run. M30 also requires independently measured physical evidence and engineering review.

The verifier accepted the completed `main` push at `a03d9895bb45a1f56fd30be890bdc07f27ed0b93` and rejected the corresponding pull-request run as a source for `main` acceptance. [Verified main run](https://github.com/god88844-hub/aeroforge/actions/runs/44274134100) · [Pull-request run](https://github.com/god88844-hub/aeroforge/actions/runs/44271972722)
