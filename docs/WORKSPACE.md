# Local project workspace

The owner's canonical development folder is **`C:\Users\Simulation apps\flights simulation`**.
Keep source checkouts, local datasets, caches, build outputs, test state and worktrees
inside this folder. On CI use the runner's checked-out workspace. Installed system
tools and Codex-managed plugins remain application infrastructure.

| Location | Purpose |
| --- | --- |
| Repository root | Active `feature/foundation-spec-lock` checkout for PR #126; primary application is `apps/desktop/` |
| `data/local/source-physical/` | Existing local source files; ignored, not redistributed or physical acceptance |
| `.local/legacy-codex/work/` | Earlier worktrees and tool environments, preserved and Git links repaired |
| `.local/legacy-codex/outputs/` | Earlier local reports and measurements |
| `.local/legacy-godot-userdata/` | Preserved prior desktop worker/application state |
| `.local/pre-migration/aeroforge.db` | Backup of the pre-existing local database; the original remains untouched |
| `.local/tmp/`, `.local/appdata/`, `.local/results/` | New development scratch files, local application state and results |

The migration on 21 November 2026 moved the previous Codex `work` and `outputs`
directories into this workspace; it did not discard unmerged work. The older checkout
already in this folder was clean at `23028761a6763df74411c973d895fc506ec41e1a`.
Its Git history and ignored local database were preserved while checking out PR #126.

Historical immutable receipts retain their original absolute paths and dates. Those
paths describe past measurements; use the locations above for new work. Do not rewrite
old receipts or dataset hashes to make them look newly acquired. The dated registry's
`../source-physical` paths are historical custody paths, not current launch instructions.

For local PowerShell work, set scratch/application state for that process before tests
or launching the desktop:

```powershell
$workspaceRoot = 'C:\Users\Simulation apps\flights simulation'
Set-Location -LiteralPath $workspaceRoot
$env:TEMP = Join-Path $workspaceRoot '.local/tmp'
$env:TMP = $env:TEMP
$env:APPDATA = Join-Path $workspaceRoot '.local/appdata'
$env:LOCALAPPDATA = Join-Path $workspaceRoot '.local/localappdata'
New-Item -ItemType Directory -Force -Path $env:TEMP,$env:APPDATA,$env:LOCALAPPDATA | Out-Null
```

Create new virtual environments under `.venv/` or `.local/`, using the committed locks.
The relocated backend interpreter at `.local/legacy-codex/work/locked-backend/Scripts/python.exe`
is available for this planning check. Relocated executable wrappers may contain old
paths; use `python -m pip`/`python -m pytest`, or recreate a locked environment inside
this workspace. Do not resume development in an archived checkout or recreate the old
Codex workspace. Product installations may use their user's selected locations; this
rule controls this project's development work.
