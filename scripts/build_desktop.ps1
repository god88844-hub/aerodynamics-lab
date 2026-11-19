param(
    [string]$PythonPath = "",
    [switch]$Launch
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$cachePath = Join-Path $repositoryRoot ".cache/desktop"
New-Item -ItemType Directory -Path $cachePath -Force | Out-Null

function Invoke-Checked {
    param([string]$Command, [string[]]$Arguments)
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed with exit code $LASTEXITCODE"
    }
}

function Get-VerifiedArchive {
    param([string]$Uri, [string]$Digest, [string]$Archive, [string]$Destination)
    if (!(Test-Path -LiteralPath $Archive)) {
        Invoke-WebRequest -Uri $Uri -OutFile $Archive
    }
    $actualDigest = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualDigest -ne $Digest) {
        throw "Downloaded archive failed its SHA-256 check at $Archive"
    }
    Expand-Archive -LiteralPath $Archive -DestinationPath $Destination -Force
}

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
        "-r", (Join-Path $repositoryRoot "apps/api/requirements.lock"))
}
$PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path
$env:LAB_PYTHON = $PythonPath
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
Invoke-Checked $godot @("--headless", "--path", $desktopDirectory, "--editor", "--import", "--quit")
Invoke-Checked $godot @("--headless", "--path", $desktopDirectory, "--script", "smoke_test.gd")
if ($Launch) {
    Invoke-Checked $godot @("--path", $desktopDirectory)
}
