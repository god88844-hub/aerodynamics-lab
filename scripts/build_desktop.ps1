param(
    [string]$PythonPath = "",
    [switch]$Launch,
    [string]$TimingReport = ""
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$cachePath = Join-Path $repositoryRoot ".cache/desktop"
$cacheWasPresent = Test-Path -LiteralPath $cachePath
$pythonWasSupplied = $PythonPath -ne ""
$nativeWasPresent = Test-Path -LiteralPath (Join-Path $cachePath "native")
$pythonWasPresent = Test-Path -LiteralPath (Join-Path $cachePath "python")
$editorWasPresent = Test-Path -LiteralPath (Join-Path $repositoryRoot "apps/desktop/.godot")
$script:buildTimings = [System.Collections.Generic.List[object]]::new()
$buildClock = [System.Diagnostics.Stopwatch]::StartNew()
$startedUtc = [DateTime]::UtcNow.ToString('o')
$buildSucceeded = $false
if ($TimingReport -ne "" -and ((Test-Path -LiteralPath $TimingReport) -or ![System.IO.Path]::IsPathRooted($TimingReport))) {
    throw "Timing report must be a new absolute path"
}
New-Item -ItemType Directory -Path $cachePath -Force | Out-Null

function Invoke-Checked {
    param([string]$Command, [string[]]$Arguments)
    $commandClock = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        & $Command @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$Command failed with exit code $LASTEXITCODE"
        }
    } finally {
        $script:buildTimings.Add(@{command=$Command; arguments=$Arguments; seconds=$commandClock.Elapsed.TotalSeconds; exit_code=$LASTEXITCODE})
    }
}

function Get-VerifiedArchive {
    param([string]$Uri, [string]$Digest, [string]$Archive, [string]$Destination)
    $downloadClock = [System.Diagnostics.Stopwatch]::StartNew()
    $wasCached = Test-Path -LiteralPath $Archive
    if (!$wasCached) {
        Invoke-WebRequest -Uri $Uri -OutFile $Archive
    }
    $actualDigest = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualDigest -ne $Digest) {
        throw "Downloaded archive failed its SHA-256 check at $Archive"
    }
    Expand-Archive -LiteralPath $Archive -DestinationPath $Destination -Force
    $script:buildTimings.Add(@{command="verified-download-and-extract"; uri=$Uri; sha256=$Digest; archive_cached=$wasCached; seconds=$downloadClock.Elapsed.TotalSeconds})
}

try {
$bindingsCommit = "e83fd0904c13356ed1d4c3d09f8bb9132bdc6b77"
$bindingsDirectory = Join-Path $cachePath "bindings"
$bindingsDownload = @{
    Uri = "https://codeload.github.com/godotengine/godot-cpp/zip/$bindingsCommit"
    Digest = "579af30c5f62c1084edb28216788188227d80a583f0114463699ac4edd22140f"
    Archive = Join-Path $cachePath "godot-cpp.zip"
    Destination = $bindingsDirectory
}
Get-VerifiedArchive @bindingsDownload
$godotDirectory = Join-Path $cachePath "godot"
$godotDownload = @{
    Uri = "https://github.com/godotengine/godot/releases/download/4.7.2-stable/Godot_v4.7.2-stable_win64.exe.zip"
    Digest = "731980f9608d61333e5baf54a2ef17210acc7a538446c0cb9969f002aca1e953"
    Archive = Join-Path $cachePath "godot.zip"
    Destination = $godotDirectory
}
Get-VerifiedArchive @godotDownload

if ($PythonPath -eq "") {
    $pythonDirectory = Join-Path $cachePath "python"
    if (!(Test-Path -LiteralPath (Join-Path $pythonDirectory "Scripts/python.exe"))) {
        Invoke-Checked "py" @("-3.11", "-m", "venv", $pythonDirectory)
    }
    $PythonPath = Join-Path $pythonDirectory "Scripts/python.exe"
    Invoke-Checked $PythonPath @("-m", "pip", "install", "--require-hashes", "--only-binary=:all:",
        "-r", (Join-Path $repositoryRoot "apps/desktop/requirements-cad.lock"))
}
$PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path
$env:LAB_PYTHON = $PythonPath
$env:LAB_CAD_PYTHON = $PythonPath
$env:LAB_TEST_CAD = "1"
Invoke-Checked $PythonPath @("-c", "import cadquery")
$sourceDirectory = Join-Path $repositoryRoot "packages/engineering-core"
$buildDirectory = Join-Path $cachePath "native"
$bindingsSource = Join-Path $bindingsDirectory "godot-cpp-$bindingsCommit"
Invoke-Checked "cmake" @("-S", $sourceDirectory, "-B", $buildDirectory, "-G", "Ninja",
    "-DCMAKE_BUILD_TYPE=Release", "-DLAB_BUILD_GDEXTENSION=ON",
    "-DPython3_EXECUTABLE=$PythonPath", "-DFETCHCONTENT_SOURCE_DIR_GODOT_CPP=$bindingsSource")
Invoke-Checked "cmake" @("--build", $buildDirectory, "--parallel", "2")
Invoke-Checked "ctest" @("--test-dir", $buildDirectory, "--output-on-failure")
$godot = Join-Path $godotDirectory "Godot_v4.7.2-stable_win64_console.exe"
$desktopDirectory = Join-Path $repositoryRoot "apps/desktop"
# A cold headless editor can crash during GDExtension documentation teardown.
# Import with a hidden graphical editor; runtime smoke checks remain headless.
$importLog = Join-Path $cachePath "editor-import.log"
$importError = Join-Path $cachePath "editor-import-error.log"
$editor = Start-Process -FilePath $godot -ArgumentList @("--path", ('"{0}"' -f $desktopDirectory),
    "--rendering-method", "gl_compatibility", "--editor", "--import", "--quit") `
    -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $importLog -RedirectStandardError $importError
if ($editor.ExitCode -ne 0) {
    Get-Content -LiteralPath $importLog
    Get-Content -LiteralPath $importError
    throw "Godot editor import failed with exit code $($editor.ExitCode)"
}
Invoke-Checked $godot @("--headless", "--path", $desktopDirectory, "--script", "smoke_test.gd")
if ($Launch) {
    Invoke-Checked $godot @("--path", $desktopDirectory)
}
$buildSucceeded = $true
} finally {
    if ($TimingReport -ne "") {
        $receipt = @{protocol="windows_empty_app_cache_build_1"; source_sha=(git -C $repositoryRoot rev-parse HEAD);
            started_utc=$startedUtc; completed_utc=[DateTime]::UtcNow.ToString('o');
            cache_preexisted=$cacheWasPresent; native_build_preexisted=$nativeWasPresent;
            python_environment_supplied=$pythonWasSupplied; python_environment_preexisted=$pythonWasPresent;
            editor_import_cache_preexisted=$editorWasPresent; cache_path=$cachePath; seconds=$buildClock.Elapsed.TotalSeconds;
            success=$buildSucceeded; stages=$script:buildTimings; pip_no_cache=$env:PIP_NO_CACHE_DIR;
            scope="Measured Windows bootstrap. Cache flags and supplied Python determine cold/warm scope. Preinstalled compiler/CMake/Ninja; OS/network caches uncontrolled; no fresh-boot claim."}
        $receipt | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $TimingReport -Encoding utf8
    }
}
