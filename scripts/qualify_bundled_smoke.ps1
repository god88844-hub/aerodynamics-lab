param(
    [Parameter(Mandatory)][string]$PythonPath,
    [Parameter(Mandatory)][string]$ReceiptDirectory
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
if (![IO.Path]::IsPathRooted($ReceiptDirectory) -or (Test-Path -LiteralPath $ReceiptDirectory)) {
    throw 'Use a new absolute receipt directory'
}
New-Item -ItemType Directory -Path $ReceiptDirectory | Out-Null
$PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path
$startedUtc = [DateTime]::UtcNow.ToString('o')
$before = @(Get-ChildItem -LiteralPath (Join-Path $env:APPDATA 'Godot/app_userdata/Aerodynamics Lab/cad-workers') -Directory -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name)
$stdout = Join-Path $ReceiptDirectory 'bootstrap.log'
$stderr = Join-Path $ReceiptDirectory 'bootstrap.err'
$timing = Join-Path $ReceiptDirectory 'bootstrap.json'
$metrics = Join-Path $ReceiptDirectory 'os-memory.jsonl'
$counterPaths = @('\Memory\Available Bytes', '\Memory\Free & Zero Page List Bytes',
    '\Memory\Standby Cache Normal Priority Bytes', '\Memory\Standby Cache Reserve Bytes', '\Memory\Standby Cache Core Bytes')
$clock = [Diagnostics.Stopwatch]::StartNew()
$process = Start-Process -FilePath (Get-Process -Id $PID).Path -ArgumentList @('-NoProfile', '-File',
    ('"{0}"' -f (Join-Path $PSScriptRoot 'build_desktop.ps1')), '-PythonPath', ('"{0}"' -f $PythonPath),
    '-TimingReport', ('"{0}"' -f $timing)) -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
do {
    $sample = [ordered]@{utc=[DateTime]::UtcNow.ToString('o'); elapsed_s=$clock.Elapsed.TotalSeconds; counters=@{}; error=$null}
    try {
        foreach ($counter in (Get-Counter -Counter $counterPaths -ErrorAction Stop).CounterSamples) {
            $sample.counters[$counter.Path] = [int64]$counter.CookedValue
        }
    } catch { $sample.error = $_.Exception.Message }
    $sample | ConvertTo-Json -Compress -Depth 5 | Add-Content -LiteralPath $metrics -Encoding utf8
    $process.Refresh()
} while (!$process.HasExited)
$process.WaitForExit()
$sessions = @()
$sessionRoot = Join-Path $env:APPDATA 'Godot/app_userdata/Aerodynamics Lab/cad-workers'
foreach ($session in (Get-ChildItem -LiteralPath $sessionRoot -Directory)) {
    if ($before -contains $session.Name) { continue }
    $destination = Join-Path $ReceiptDirectory ('sessions/' + $session.Name)
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    foreach ($name in @('resource-request.json','resource-admission.json','resource-usage.json','supervisor.json','ready.json','retired.json','engine.log','engine-launcher.json')) {
        $source = Join-Path $session.FullName $name
        if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination $destination }
    }
    $jobsDirectory = Join-Path $session.FullName 'jobs'
    if (Test-Path -LiteralPath $jobsDirectory) {
        foreach ($job in (Get-ChildItem -LiteralPath $jobsDirectory -Directory)) {
            $jobDestination = Join-Path $destination ('jobs/' + $job.Name)
            New-Item -ItemType Directory -Path $jobDestination -Force | Out-Null
            foreach ($name in @('resource-admission.json','started.json','prepared.json','approved.json','complete.json','error.json')) {
                $jobRecord = Join-Path $job.FullName $name
                if (Test-Path -LiteralPath $jobRecord) { Copy-Item -LiteralPath $jobRecord -Destination $jobDestination }
            }
        }
    }
    $sessions += $session.Name
}
@{source_sha=(git -C $repositoryRoot rev-parse HEAD);
    harness_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();
    source_status=(git -C $repositoryRoot status --porcelain);
    started_utc=$startedUtc;
    completed_utc=[DateTime]::UtcNow.ToString('o'); seconds=$clock.Elapsed.TotalSeconds;
    exit_code=$process.ExitCode; success=($process.ExitCode -eq 0); new_sessions=$sessions;
    memory_metric='GlobalMemoryStatusEx ullAvailPhys in admission; PDH available/free/standby counters observed separately';
    limits='Existing sampled memory/workspace/deadline guards unchanged; no OS hard quota claimed'} |
    ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $ReceiptDirectory 'qualification.json') -Encoding utf8
if ($process.ExitCode -ne 0) { throw "Bundled smoke failed: $($process.ExitCode); inspect $ReceiptDirectory" }
