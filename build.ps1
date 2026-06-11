# =============================================================================
# build.ps1 - MTG Sim build script (Windows)
#
# Usage:
#   .\build.ps1              # standard build
#   .\build.ps1 -OneFile     # single executable (larger, slower to start)
#   .\build.ps1 -Clean       # remove build artifacts and exit
#   .\build.ps1 -Help
#
# Output: dist\mtg_sim\mtg_sim.exe  (or dist\mtg_sim.exe with -OneFile)
# Requires: Python 3.10+, pip
#
# If you get "cannot be loaded because running scripts is disabled", run:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
# =============================================================================

param(
    [switch]$OneFile,
    [switch]$Clean,
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$AppName    = "mtg_sim"
$EntryPoint = "main.py"
$VenvDir    = ".venv"
$DistDir    = "dist"
$BuildDir   = "build"

function Log  { param($msg) Write-Host "[build] $msg" -ForegroundColor Cyan }
function Warn { param($msg) Write-Host "[build] WARNING: $msg" -ForegroundColor Yellow }
function Die  { param($msg) Write-Host "[build] ERROR: $msg" -ForegroundColor Red; exit 1 }

if ($Help) {
    Write-Host "Usage: .\build.ps1 [options]"
    Write-Host ""
    Write-Host "  -OneFile    Bundle into a single .exe file (slower startup)"
    Write-Host "  -Clean      Remove build/dist artifacts and exit"
    Write-Host "  -Help       Show this message"
    exit 0
}

if ($Clean) {
    Log "Cleaning build artifacts..."
    foreach ($dir in @($BuildDir, $DistDir)) {
        if (Test-Path $dir) { Remove-Item $dir -Recurse -Force }
    }
    if (Test-Path "$AppName.spec") { Remove-Item "$AppName.spec" -Force }
    Log "Done."
    exit 0
}

Log "Checking Python..."
$PythonCmd = $null
foreach ($candidate in @("python", "python3", "py")) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        $PythonCmd = $candidate
        break
    }
}
if (-not $PythonCmd) {
    Die "Python not found. Install Python 3.10+ from https://python.org and ensure it is on PATH."
}

$PyVersion = & $PythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$PyMajor   = [int](& $PythonCmd -c "import sys; print(sys.version_info.major)")
$PyMinor   = [int](& $PythonCmd -c "import sys; print(sys.version_info.minor)")

if ($PyMajor -lt 3 -or ($PyMajor -eq 3 -and $PyMinor -lt 10)) {
    Die "Python 3.10+ required (found $PyVersion)."
}
Log "  Python $PyVersion - OK"

if (-not (Test-Path $VenvDir)) {
    Log "Creating virtual environment in $VenvDir..."
    & $PythonCmd -m venv $VenvDir
}

$Pip         = "$VenvDir\Scripts\pip.exe"
$PyInstaller = "$VenvDir\Scripts\pyinstaller.exe"
$VenvPython  = "$VenvDir\Scripts\python.exe"

Log "Upgrading pip..."
& $Pip install --upgrade pip --quiet

Log "Installing dependencies..."
if (Test-Path "requirements.txt") {
    & $Pip install -r requirements.txt --quiet
    Log "  Installed from requirements.txt"
} else {
    Warn "No requirements.txt found - installing PyInstaller only."
}
& $Pip install pyinstaller pytest --quiet
Log "  PyInstaller + pytest ready"

if ((Test-Path "setup.py") -or (Test-Path "pyproject.toml")) {
    & $Pip install -e . --quiet
    Log "  Project installed (editable mode)"
} else {
    $SitePackages = & $VenvPython -c "import site; print(site.getsitepackages()[0])"
    $ProjectRoot  = (Get-Location).Path
    Set-Content -Path "$SitePackages\mtg_sim_dev.pth" -Value $ProjectRoot -Encoding UTF8
    Log "  Project root added to venv path via mtg_sim_dev.pth"
}

$StubCreated = $false
if (-not (Test-Path $EntryPoint)) {
    Warn "$EntryPoint not found - creating a temporary stub."
    Warn "Replace this with your real entrypoint before distributing."
    $stubContent = "import sys`nimport mtg_sim.engine`nprint('MTG Sim -- engine loaded successfully.')`nprint('TUI not yet implemented. Run tests with: python -m pytest mtg_sim/tests/')`nsys.exit(0)"
    Set-Content -Path $EntryPoint -Value $stubContent -Encoding UTF8
    $StubCreated = $true
}

Log "Running tests..."
& $VenvPython -m pytest mtg_sim/tests/ -q
if ($LASTEXITCODE -ne 0) {
    if ($StubCreated) { Remove-Item $EntryPoint -Force }
    Die "Tests failed - fix errors before building."
}
Log "  All tests passed."

$ProjectRoot = (Get-Location).Path

$PyInstallerArgs = @(
    "--name",      $AppName,
    "--distpath",  $DistDir,
    "--workpath",  $BuildDir,
    "--paths",     $ProjectRoot,
    "--noconfirm",
    "--clean"
)

if ($OneFile) {
    $PyInstallerArgs += "--onefile"
    Log "Build mode: single file"
} else {
    $PyInstallerArgs += "--onedir"
    Log "Build mode: directory (use -OneFile for a single .exe)"
}

if (Test-Path "mtg_sim")          { $PyInstallerArgs += "--add-data=mtg_sim;mtg_sim" }
if (Test-Path "config.ini")       { $PyInstallerArgs += "--add-data=config.ini;." }
if (Test-Path "requirements.txt") { $PyInstallerArgs += "--add-data=requirements.txt;." }

$PyInstallerArgs += @(
    "--hidden-import=mtg_sim",
    "--hidden-import=mtg_sim.engine",
    "--hidden-import=mtg_sim.engine.deck",
    "--hidden-import=mtg_sim.engine.game_state",
    "--hidden-import=mtg_sim.engine.simulation",
    "--hidden-import=mtg_sim.engine.config",
    "--hidden-import=mtg_sim.engine.app_state"
)

$PyInstallerArgs += $EntryPoint

Log "Running PyInstaller..."
& $PyInstaller @PyInstallerArgs

if ($StubCreated) {
    Remove-Item $EntryPoint -Force
}

if ($OneFile) {
    $Output = "$DistDir\$AppName.exe"
} else {
    $Output = "$DistDir\$AppName\$AppName.exe"
}

Write-Host ""
Log "Build complete!"
Log "  Output: $Output"
Log ""
Log "To run:"
if ($OneFile) {
    Log "  .\$DistDir\$AppName.exe"
} else {
    Log "  .\$DistDir\$AppName\$AppName.exe"
}
Log ""
Log "To clean up:  .\build.ps1 -Clean"